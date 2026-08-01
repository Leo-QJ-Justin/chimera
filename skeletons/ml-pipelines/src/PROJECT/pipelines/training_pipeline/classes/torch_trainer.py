"""``TorchTrainer``: the deep-learning harness behind the trainer contract.

Everything that used to be a standalone DL training pipeline lives here as
one trainer: the epoch loop, early stopping, the plateau scheduler, the
NaN guard, checkpointing, device setup and the sanity check are all
internals (``../modules/``), and the outside world sees only
``train / predict / evaluate / save / load``.

Decisions worth knowing before editing (D7):

- **Same preprocessing as every other trainer**, and it is part of the
  artifact - so a torch run accepts the same raw feature frame a LightGBM
  run does, categoricals included.
- **One monitored metric.** ``trainer.torch.monitor: {name, mode}`` drives
  early stopping *and* the LR schedule, so no metric ever needs a
  ``Const - error`` inversion to look higher-is-better.
- **Best weights are restored after the loop**, so ``evaluate``, the
  metrics in metadata and the logged MLflow model all describe the model
  that will be served. ``checkpoint_last.pt`` keeps the raw final state for
  resuming, and checkpoints are dicts, never pickled modules.
- **Labels are encoded to 0..K-1 internally** and mapped back on predict:
  ``CrossEntropyLoss`` needs contiguous class indices, the rest of the
  project speaks the original labels.
- **The tuner is this family's own**, as every family's is. What makes
  torch's distinctive is not that it scores on a holdout - both boosters do
  too - but that a suggestion has two possible destinations: ``params__*``
  keys change the checkpoint's shapes, ``options__*`` keys change what the
  loop does, and the winners are routed to both. ``cross_validate`` needs
  no override - the base runs this trainer's own ``train`` per fold
  (R1.11), which is expensive by construction and says so in the log
  rather than hiding it.

The architecture is the MLP in ``../modules/architectures.py``; another one
is another trainer class overriding :meth:`_build_model`, not a lookup key
inside this one.
"""

import copy
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

import joblib
import numpy as np
import pandas as pd

from ....schemas import ChoiceSpace, FloatSpace, IntSpace, ParamSpace, TorchTrainerConfig
from ...evaluation_pipeline.modules.metrics import compute_metrics, log_metrics, prefixed
from ..modules.architectures import MLP, count_parameters
from ..modules.callbacks import (
    EarlyStoppingMonitor,
    NaNGuard,
    current_lr,
    make_scheduler,
)
from ..modules.checkpointing import (
    BEST_CHECKPOINT,
    LAST_CHECKPOINT,
    load_checkpoint,
    resume,
    save_checkpoint,
    strip_module_prefix,
)
from ..modules.datasets import TabularTensorDataset, make_loaders
from ..modules.device import describe_device, setup_device, wrap_model
from ..modules.loops import accuracy, evaluate, predict, run_one_epoch
from ..modules.model_logging import log_flavor_model
from ..modules.sanity import overfit_single_batch
from .base_trainer import (
    TUNE_HOLDOUT_FRACTION,
    BaseTrainer,
    FitFrames,
    _import_optuna,
    resolve_tune_metric,
)

logger = logging.getLogger(__name__)

PREPROCESSOR_FILENAME = "preprocessor.joblib"


class TorchTrainer(BaseTrainer):
    """Plain-torch training loop wrapped in the ``BaseTrainer`` contract.

    Args:
        params: Architecture hyperparameters (``hidden_sizes``, ``dropout``).
        options: Harness knobs; validated as
            :class:`~PROJECT.schemas.TorchTrainerConfig`, so the defaults
            live in exactly one place.
        input_dim: Design-matrix width. Recorded at training time; supplied
            by :meth:`load` so the module can be rebuilt before its weights
            land.
        n_outputs: Head width (class count, or 1 for regression). Same
            provenance as ``input_dim``.
        classes: Original class labels in encoding order. Same provenance.
    """

    kind = "torch"
    # The epoch loop monitors val every epoch (early stopping, LR schedule,
    # best-checkpoint choice), so val must stay outside the training data:
    # standing-val protocol (R1.10).
    uses_val_in_fit = True

    # Defaults for the search, prefixed by destination exactly as the
    # suggestions are; `trainer.tune.space` narrows any of them and `false`
    # drops one. Dropping either architecture knob turns architecture search
    # off entirely and keeps the configured `hidden_sizes` (see
    # _get_param_space): a width without a depth describes no network.
    TUNABLE: ClassVar[dict[str, ParamSpace]] = {
        "params__hidden_width": ChoiceSpace(choices=[32, 64, 128, 256]),
        "params__depth": IntSpace(low=1, high=3),
        "params__dropout": FloatSpace(low=0.0, high=0.5),
        "options__lr": FloatSpace(low=1e-4, high=1e-2, log=True),
        "options__weight_decay": FloatSpace(low=1e-8, high=1e-2, log=True),
    }

    def __init__(
        self,
        params: dict | None = None,
        *,
        options: dict | None = None,
        input_dim: int | None = None,
        n_outputs: int | None = None,
        classes: list | None = None,
        **kwargs,
    ):
        super().__init__(params, **kwargs)
        self.options = TorchTrainerConfig(**(options or {}))
        self.input_dim = input_dim
        self.n_outputs = n_outputs
        self.classes = classes
        self.preprocessor = None
        self.device = None
        self._optimizer = None
        self._best_state: dict | None = None
        self._last_state: dict | None = None
        self.summary: dict = {}

    def extra_spec(self) -> dict:
        """Harness knobs plus the shapes :meth:`load` needs to rebuild."""
        return {
            "options": self.options.model_dump(),
            "input_dim": self.input_dim,
            "n_outputs": self.n_outputs,
            "classes": self.classes,
        }

    # ------------------------------------------------------- abstract hooks

    def _build_model(self):
        """A fresh ``nn.Module`` for the recorded shapes.

        Zero-argument and side-effect free, so it doubles as the factory the
        overfit-single-batch check needs (that check must not pollute the
        run's model with 100 steps of single-batch gradient).
        """
        if not self.input_dim:
            raise RuntimeError("input_dim is unknown; train() or load() sets it")
        return MLP(
            input_dim=self.input_dim,
            hidden_sizes=list(self.params.get("hidden_sizes", [128, 64])),
            n_classes=self.n_outputs,
            dropout=self.params.get("dropout", 0.0),
        )

    def _get_param_space(self, trial, space: dict) -> dict:
        """One trial's suggestion, keyed by destination.

        ``params__*`` keys are architecture (they change checkpoint shapes),
        ``options__*`` keys are harness. The prefixes are what let
        :meth:`hyperparameter_tune` route a suggestion without a hardcoded
        list of which knob is which.

        The layer list is *derived*: a width and a depth are two numbers
        Optuna can sample, a list of layer sizes is not. It survives into
        ``params`` because the tuner records this resolved dict per trial.
        """
        architecture = ("params__hidden_width", "params__depth")
        resolved = {
            name: entry.suggest(trial, name)
            for name, entry in space.items()
            if name not in architecture
        }
        if all(name in space for name in architecture):
            width = space["params__hidden_width"].suggest(trial, "params__hidden_width")
            depth = space["params__depth"].suggest(trial, "params__depth")
            resolved["params__hidden_sizes"] = [
                width // (2**i) or 1 for i in range(depth)
            ]
        return resolved

    # ------------------------------------------------------------------ fit

    def fit_frames(self, X: dict, y: dict) -> FitFrames:
        """The standing-val protocol: fit on train, val stays the referee.

        Val is handed back as the referee frames rather than pooled into the
        fit, because the epoch loop reads it every epoch - early stopping,
        the LR schedule and the best-checkpoint choice all monitor it, and
        rows inside the training data cannot referee any of that (R1.10).
        Test is untouched either way.
        """
        return FitFrames(X["train"], y["train"], X["val"], y["val"], ["train"])

    def train(
        self,
        X: pd.DataFrame,
        y,
        X_val: pd.DataFrame | None = None,
        y_val=None,
        **kwargs,
    ) -> "TorchTrainer":
        import torch

        options = self.options
        if options.deterministic_cudnn:
            # Costs speed and raises on ops without deterministic kernels,
            # which is why it is opt-in config rather than a default.
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
            logger.info("Deterministic cuDNN kernels pinned (opt-in)")

        self.preprocessor = self.new_preprocessor()
        X_train_t = self._to_array(self.preprocessor.fit_transform(self.align(X)))
        y_train_e = self._encode_targets(y, fit=True)
        self.input_dim = X_train_t.shape[1]

        matrices, targets = [X_train_t], [y_train_e]
        positions = {"train": list(range(len(X_train_t)))}
        if X_val is not None and y_val is not None:
            X_val_t = self._to_array(self.preprocessor.transform(self.align(X_val)))
            matrices.append(X_val_t)
            targets.append(self._encode_targets(y_val, fit=False))
            positions["val"] = list(range(len(X_train_t), len(X_train_t) + len(X_val_t)))
        else:
            logger.warning(
                "No validation split given; only train_* metrics exist this "
                "run, so monitor.name must name one of them"
            )

        dataset = TabularTensorDataset(
            np.vstack(matrices),
            np.concatenate(targets),
            target_dtype="long" if self._is_classification else "float",
        )
        loaders = make_loaders(
            dataset,
            positions,
            batch_size=options.batch_size,
            num_workers=options.num_workers,
            pin_memory=options.pin_memory,
            seed=self.seed,
            subsample_frac=options.subsample_frac,
        )

        self.device = setup_device(options)
        # Wrap (and move) before building the optimizer: the optimizer must
        # own the parameters of the object that is actually stepped.
        self.model = wrap_model(self._build_model(), self.device)
        self._optimizer = torch.optim.Adam(
            self.model.parameters(), lr=options.lr, weight_decay=options.weight_decay
        )
        loss_fn = self._loss_fn()
        # Injected, never baked into the loops: a regression run must not
        # inherit a hardcoded argmax accuracy.
        metric_fn = accuracy if self._is_classification else None

        if options.sanity_check:
            overfit_single_batch(
                self._build_model,
                loaders["train"],
                self.device,
                metric_fn=metric_fn,
                loss_fn=loss_fn,
            )

        self._run_epochs(loaders, loss_fn, metric_fn, self._maybe_resume())
        self.fitted = True
        return self

    def _run_epochs(self, loaders, loss_fn, metric_fn, start_epoch: int) -> None:
        """The loop: epoch -> evaluate -> schedule -> early-stop."""
        options = self.options
        monitor = options.monitor
        # EarlyStopping persists the best weights to a path; the run dir does
        # not exist from in here (save() owns it), so the library writes to a
        # scratch dir and the best state is carried back in memory.
        with tempfile.TemporaryDirectory() as scratch:
            early_stopping = EarlyStoppingMonitor(
                patience=options.patience, run_dir=scratch, mode=monitor.mode
            )
            scheduler = make_scheduler(
                self._optimizer,
                mode=monitor.mode,
                factor=options.lr_factor,
                patience=options.lr_patience,
                min_lr=options.min_lr,
            )
            nan_guard = NaNGuard()
            stopped_early = False
            epoch = start_epoch - 1

            for epoch in range(start_epoch, start_epoch + options.epochs):
                metrics = self._one_epoch(loaders, loss_fn, metric_fn, epoch)
                monitored = self._monitored_value(metrics)
                if not nan_guard.check(monitored):
                    if nan_guard.should_stop:
                        logger.error(
                            "Stopping: %d consecutive non-finite epochs",
                            nan_guard.consecutive,
                        )
                        stopped_early = True
                        break
                    # A diverged epoch must not reach the checkpointer.
                    continue

                scheduler.step(monitored)
                if early_stopping(monitored, self.model):
                    logger.info(
                        "Early stopping at epoch %d (best %s = %.6f)",
                        epoch,
                        monitor.name,
                        early_stopping.best_value,
                    )
                    stopped_early = True
                    break

            self._restore_best(early_stopping.best_path)

        self.summary = {
            "epochs_run": epoch - start_epoch + 1,
            "last_epoch": epoch,
            "early_stopped": stopped_early,
            "monitor": monitor.model_dump(),
            "best_value": early_stopping.best_value,
            "final_metrics": self.history[-1] if self.history else {},
            "device": describe_device(self.device),
            "n_parameters": count_parameters(self.model),
            "input_dim": self.input_dim,
        }

    def _one_epoch(self, loaders, loss_fn, metric_fn, epoch: int) -> dict:
        """One train pass, one eval pass, one history record."""
        train = run_one_epoch(
            self.model, loaders["train"], loss_fn, self._optimizer, self.device, metric_fn
        )
        metrics = {
            "train_loss": train["loss"],
            # The LR this epoch *used*, recorded before the scheduler may
            # change it - ReduceLROnPlateau no longer logs its own decays.
            "lr": current_lr(self._optimizer),
        }
        if metric_fn is not None:
            metrics["train_metric"] = train["metric"]
        if "val" in loaders:
            val = evaluate(self.model, loaders["val"], loss_fn, self.device, metric_fn)
            metrics["val_loss"] = val["loss"]
            if metric_fn is not None:
                metrics["val_metric"] = val["metric"]
        self.history.append({"epoch": epoch, **metrics})
        logger.info(
            "Epoch %d | %s", epoch, " | ".join(f"{k} {v:.4f}" for k, v in metrics.items())
        )
        return metrics

    def _restore_best(self, best_path: Path) -> None:
        """Serve the best-monitored weights, not whichever epoch was last.

        The raw final state is snapshotted first so ``checkpoint_last.pt``
        stays honest and ``resume: continue`` really continues from the last
        epoch rather than silently from the best one.
        """
        if not Path(best_path).exists():
            logger.warning("No best checkpoint written; keeping final weights")
            self._best_state = None
            self._last_state = None
            return
        self._last_state = strip_module_prefix(
            {k: v.detach().cpu().clone() for k, v in self.model.state_dict().items()}
        )
        checkpoint = load_checkpoint(best_path, self.model, map_location="cpu")
        self._best_state = checkpoint["model_state_dict"]
        logger.info("Restored best-monitored weights into the served model")

    # -------------------------------------------------------- score and tune

    def evaluate(
        self, X: pd.DataFrame, y, metrics: list[str | Callable] | None = None
    ) -> dict[str, float]:
        """Score a frame with the project's metric definitions."""
        self.check_fitted()
        return compute_metrics(y, self.predict(X), task=self.task, metrics=metrics)

    def evaluate_run(
        self,
        X: dict,
        y: dict,
        X_fit: pd.DataFrame,
        y_fit,
        *,
        metric: str,
        cv: int,
        basis: str,
        split: str,
    ) -> dict[str, float]:
        """Every named split scored, plus the CV estimate under ``basis: cv``.

        Val stayed outside the fit, so it is a genuinely held-out number and
        is published as one; train is scored too, as the overfitting
        reference. ``X_fit``/``y_fit`` are accepted and unread - this
        protocol scores the named splits, and the signature is the same for
        every family.

        Under ``selection.basis: cv`` the fit above is untouched - this
        family's epoch loop still needs its standing referee - but the
        number ``best.json`` records becomes a procedure CV over the
        train+val pool, where each fold carves its own referee (R1.11). That
        is what a pooled family's ``cv_`` number already is, so the two rank
        against each other. It costs ``cv`` full epoch loops, which the CV
        log line says out loud rather than hiding. The std travels with the
        mean because a selection criterion is a random variable: two runs
        0.002 apart on a fold spread of 0.05 have not been distinguished
        (Cawley & Talbot 2010).
        """
        metrics: dict[str, float] = {}
        for name in ("train", "val", "test"):
            split_metrics = self.evaluate(X[name], y[name])
            log_metrics(split_metrics, name)
            metrics.update(prefixed(split_metrics, name))
        if basis != "cv":
            return metrics

        logger.info(
            "selection.basis=cv: %s keeps its standing-val fit, and best.json "
            "reads a procedure-CV estimate on train+val instead of %s_%s",
            self.model_type,
            split,
            metric,
        )
        # Pooled in split order, so a temporal run's pool stays chronological,
        # which is what lets a fold carve its stopping subset off the end of
        # its own training window rather than out of the middle of it.
        X_pool = pd.concat([X["train"], X["val"]])
        y_pool = pd.concat([y["train"], y["val"]])
        stats = self.cross_validate(X_pool, y_pool, cv=cv, metrics=[metric])[metric]
        logger.info(
            "CV estimate on train+val: %s = %.4f +/- %.4f over %d folds",
            metric,
            stats["mean"],
            stats["std"],
            cv,
        )
        metrics[f"cv_{metric}"] = stats["mean"]
        metrics[f"cv_{metric}_std"] = stats["std"]
        return metrics

    def selection_key(self, *, metric: str, basis: str, split: str) -> tuple[str, str]:
        """The configured split's score, unless the run asked for the CV basis.

        Val stayed outside the fit, so ``selection.split`` names a real
        out-of-sample number and is honoured. ``selection.basis: cv`` trades
        it for the procedure-CV estimate every family can publish, which is
        what makes runs of different families rankable in one output
        directory (R1.11).
        """
        if basis == "cv":
            return "cv", f"cv_{metric}"
        return split, f"{split}_{metric}"

    def fresh(self) -> "TorchTrainer":
        """An unfitted twin, minus the knobs that belong to the real run.

        A CV fold is a sibling fit, exactly as a tuning trial is: it must
        not re-run the sanity check or resume from the run's checkpoint,
        so both reuse :meth:`_candidate`.
        """
        return self._candidate({})

    def hyperparameter_tune(
        self,
        X: pd.DataFrame,
        y,
        n_trials: int = 100,
        cv: int | Any = 5,
        metric: str | None = None,
        direction: str | None = None,
        space: dict | None = None,
        **optuna_kwargs,
    ) -> dict:
        """Optuna over one carved holdout, which every trial early-stops on.

        ``cv`` is **not read here**: k-fold would multiply an already
        expensive fit by ``cv``, and the epoch loop needs a standing referee
        anyway. It still sets the fold count of the selection CV under
        ``selection.basis: cv``.

        The holdout is carved by
        :meth:`BaseTrainer._carve_stopping_subset`, so a temporal run's
        trials stop against the chronological tail rather than a random
        subset - a monitor that has seen the future is the leak D9 exists to
        prevent.

        Known bias: trials are scored on the same holdout they early-stopped
        against, so the selected score is optimistic. The honest number
        remains the training pipeline's untouched test split.

        Args:
            n_trials: Optuna trials; each costs one full epoch loop.
            cv: Ignored by this search (see above).
            metric: A project metric alias; None -> the task default.
            direction: None -> inferred from the metric.
            space: ``trainer.tune.space`` overrides of :attr:`TUNABLE`.

        Returns:
            The best parameters found, already folded into ``params`` /
            ``options`` so the next :meth:`train` uses them.

        Raises:
            ImportError: If optuna is not installed.
        """
        optuna = _import_optuna()
        metric, direction = resolve_tune_metric(self.task, metric, direction)
        merged = self._merged_space(space)
        X_tune, y_tune, X_holdout, y_holdout = self._carve_stopping_subset(
            self.align(X), np.asarray(y), TUNE_HOLDOUT_FRACTION
        )
        logger.info(
            "Tuning %s over %d trials: %s (%s), %d rows fitted against a "
            "%d-row holdout per trial, searching %s",
            self.model_type,
            n_trials,
            metric,
            direction,
            len(X_tune),
            len(X_holdout),
            sorted(merged),
        )

        def objective(trial) -> float:
            resolved = self._get_param_space(trial, merged)
            # The space derives values Optuna never sees as suggestions
            # (hidden_sizes from a width and a depth), so the resolved dict
            # is recorded here and read back from the winning trial.
            trial.set_user_attr("resolved_params", resolved)
            candidate = self._candidate(resolved)
            candidate.train(X_tune, y_tune, X_holdout, y_holdout)
            return candidate.evaluate(X_holdout, y_holdout, metrics=[metric])[metric]

        study = optuna.create_study(direction=direction, **optuna_kwargs)
        # show_progress_bar is off: the bar writes to stderr and interleaves
        # with the run's log file, which is the thing anyone reads afterwards.
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        self.best_params = dict(study.best_trial.user_attrs["resolved_params"])
        params, options = self._route(self.best_params)
        self.params.update(params)
        self.options = TorchTrainerConfig(**{**self.options.model_dump(), **options})
        logger.info(
            "Tuned %s over %d trials: best %s=%.6f with %s",
            self.model_type,
            n_trials,
            metric,
            study.best_value,
            self.best_params,
        )
        return self.best_params

    def _candidate(self, suggestion: dict) -> "TorchTrainer":
        """A sibling trainer carrying one trial's suggestion."""
        params, options = self._route(suggestion)
        return type(self)(
            params={**self.params, **params},
            # Sanity checks and resumes belong to the real run, not a trial.
            options={
                **self.options.model_dump(),
                **options,
                "sanity_check": False,
                "resume_from": None,
            },
            task=self.task,
            seed=self.seed,
            numeric_features=self.numeric_features,
            categorical_features=self.categorical_features,
            cv_mode=self.cv_mode,
        )

    @staticmethod
    def _route(suggestion: dict) -> tuple[dict, dict]:
        """Split a ``params__``/``options__`` suggestion by destination."""

        def taking(prefix: str) -> dict:
            return {
                key[len(prefix) :]: value
                for key, value in suggestion.items()
                if key.startswith(prefix)
            }

        return taking("params__"), taking("options__")

    # -------------------------------------------------------------- predict

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        outputs = self._raw_outputs(X)
        if not self._is_classification:
            return outputs.reshape(-1)
        return np.asarray(self.classes)[outputs.argmax(axis=1)]

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray | None:
        if not self._is_classification:
            return None
        import torch

        logits = torch.from_numpy(self._raw_outputs(X))
        return torch.softmax(logits, dim=1).numpy()

    @property
    def classes_(self) -> np.ndarray | None:
        return None if self.classes is None else np.asarray(self.classes)

    def _raw_outputs(self, X: pd.DataFrame) -> np.ndarray:
        """Batched forward pass over an aligned, transformed frame."""
        self.check_fitted()
        matrix = self._design_matrix(X)
        dataset = TabularTensorDataset(
            matrix,
            np.zeros(len(matrix)),
            target_dtype="long" if self._is_classification else "float",
        )
        # make_loaders only shuffles the split named "train", so this loader
        # keeps dataset order and the output stays positionally alignable.
        loaders = make_loaders(
            dataset,
            {"predict": list(range(len(matrix)))},
            batch_size=self.options.batch_size,
            seed=self.seed,
        )
        return predict(self.model, loaders["predict"], self.device)

    def _design_matrix(self, X: pd.DataFrame) -> np.ndarray:
        """The float32 matrix the module actually consumes."""
        return self._to_array(self.preprocessor.transform(self.align(X)))

    # ----------------------------------------------------------- persistence

    def training_summary(self) -> dict:
        return {**self.summary, "history": self.history}

    def get_params(self) -> dict:
        params = super().get_params()
        params.update({f"torch_{k}": v for k, v in self.options.model_dump().items()})
        params["input_dim"] = self.input_dim
        if self.summary:
            params["n_parameters"] = self.summary["n_parameters"]
            params["device"] = self.summary["device"]
        return params

    def log_model(self, tracker, input_example=None) -> None:
        """The served module, in the ``mlflow.pytorch`` flavor.

        ``self.model`` already carries the best-monitored weights, so this
        logs the model that will be served. Any device wrapper is unwrapped
        first - a saved ``DataParallel`` will not load on a CPU host - and
        the module is logged as a CPU copy, because MLflow validates the
        (CPU) input example against it at save time. The example is the
        transformed design matrix, since the flavor stores a module rather
        than a pipeline.
        """
        self.check_fitted()
        example = None if input_example is None else self._design_matrix(input_example)
        served = copy.deepcopy(getattr(self.model, "module", self.model)).cpu().eval()
        log_flavor_model(
            tracker,
            "pytorch",
            served,
            input_example=example,
            predictions=None if example is None else self._raw_outputs(input_example),
        )

    def save(self, run_dir: str | Path) -> dict[str, str]:
        import torch

        self.check_fitted()
        run_dir = Path(run_dir)
        # The served model was rewound to the best-monitored weights, so the
        # last checkpoint is written from the snapshot taken before rewinding
        # - otherwise `resume: continue` would silently be `from_best`.
        save_checkpoint(
            run_dir / LAST_CHECKPOINT,
            self.model,
            self._optimizer,
            epoch=self.summary.get("last_epoch", -1),
            metrics=self.summary.get("final_metrics", {}),
            state_dict=self._last_state,
        )
        joblib.dump(self.preprocessor, run_dir / PREPROCESSOR_FILENAME)
        files = {
            "preprocessor": PREPROCESSOR_FILENAME,
            "checkpoint_last": LAST_CHECKPOINT,
        }
        if self._best_state is not None:
            torch.save(self._best_state, run_dir / BEST_CHECKPOINT)
            files["checkpoint_best"] = BEST_CHECKPOINT
        return files

    @classmethod
    def load(cls, run_dir: str | Path) -> "TorchTrainer":
        run_dir = Path(run_dir)
        trainer = cls.from_spec(cls.read_spec(run_dir))
        files = cls.read_files(run_dir)
        trainer.preprocessor = joblib.load(run_dir / files["preprocessor"])
        trainer.device = setup_device(trainer.options)
        trainer.model = wrap_model(trainer._build_model(), trainer.device)
        # The best checkpoint is the served one; the last is only for resuming.
        checkpoint = files.get("checkpoint_best", files["checkpoint_last"])
        load_checkpoint(run_dir / checkpoint, trainer.model, map_location=trainer.device)
        trainer.fitted = True
        return trainer

    # --------------------------------------------------------------- parts

    @property
    def _is_classification(self) -> bool:
        return self.task == "classification"

    def _loss_fn(self):
        """Cross-entropy for classification, MSE for a scalar head."""
        from torch import nn

        if self._is_classification:
            return nn.CrossEntropyLoss()
        mse = nn.MSELoss()
        # Squeeze the head's trailing dim: MSELoss between (B, 1) and (B,)
        # broadcasts to a (B, B) error matrix and silently trains on nonsense.
        return lambda outputs, targets: mse(outputs.squeeze(-1), targets)

    def _encode_targets(self, y, fit: bool) -> np.ndarray:
        """Original labels -> contiguous class indices (classification only)."""
        y = np.asarray(y)
        if not self._is_classification:
            if fit:
                self.n_outputs = 1  # scalar regression head
            return y.astype(np.float32)
        if fit:
            self.classes = np.unique(y).tolist()
            self.n_outputs = len(self.classes)
            if self.n_outputs < 2:
                raise ValueError(
                    f"Only {self.n_outputs} class present in the training split; "
                    "a classifier needs at least two"
                )
        unseen = set(np.unique(y).tolist()) - set(self.classes)
        if unseen:
            raise ValueError(
                f"Labels {sorted(unseen)} appear outside the training split - "
                "the model has no output unit for them"
            )
        return np.searchsorted(np.asarray(self.classes), y).astype(np.int64)

    def _monitored_value(self, metrics: dict) -> float:
        name = self.options.monitor.name
        if name not in metrics:
            raise KeyError(
                f"monitor.name={name!r} is not among this epoch's metrics "
                f"{sorted(metrics)} - fix the config or emit the metric"
            )
        return metrics[name]

    def _maybe_resume(self) -> int:
        """Load a prior run's checkpoint; return the first epoch to run."""
        options = self.options
        if not options.resume_from:
            return 0
        path = resume(options.resume_from, mode=options.resume)
        checkpoint = load_checkpoint(
            path, self.model, self._optimizer, map_location=self.device
        )
        if options.resume == "continue":
            return int(checkpoint["epoch"]) + 1
        # from_best: branch from the best weights but count epochs afresh -
        # the trajectory after a rewind is a new one.
        return 0

    @staticmethod
    def _to_array(frame) -> np.ndarray:
        """Transformer output (pandas or ndarray) as a float32 matrix."""
        values = frame.to_numpy() if hasattr(frame, "to_numpy") else np.asarray(frame)
        return values.astype(np.float32)
