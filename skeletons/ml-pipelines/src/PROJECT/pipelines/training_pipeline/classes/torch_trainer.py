"""``TorchTrainer``: the deep-learning harness behind the trainer contract.

Everything that used to be a standalone DL training pipeline lives here
as one trainer: the epoch loop, early stopping, the plateau scheduler,
the NaN guard, checkpointing, device setup and the sanity check are all
internals (``../modules/``), and the outside world sees only
``train / predict / evaluate / save / load``.

Decisions worth knowing before editing (D7):

- **Same preprocessing as every other trainer.** The fitted
  ``ColumnTransformer`` is part of the artifact, so a torch run accepts
  the same raw feature frame a LightGBM run does - categoricals included.
  That is what makes the registry swap in ``run_inference.py`` possible.
- **One monitored metric.** ``trainer.torch.monitor: {name, mode}`` drives
  early stopping *and* the LR schedule, so no metric ever needs a
  ``Const - error`` inversion to look higher-is-better.
- **Best weights are restored after the loop.** ``evaluate`` and the
  metrics recorded in metadata therefore describe the model that will be
  served, not whatever the last epoch happened to produce.
  ``checkpoint_last.pt`` still carries the raw final state for resuming.
- **Checkpoints are dicts, never pickled modules** - see
  ``../modules/checkpointing.py``.
- **Labels are encoded to 0..K-1 internally** and mapped back on predict,
  because ``CrossEntropyLoss`` requires contiguous class indices while
  the rest of the project speaks the original labels.
- **``cross_validate`` and the base tuner are overridden.** A torch module
  is not a sklearn estimator, and k-fold epoch training is expensive
  enough that silently doing it would be a trap. See the two methods.
"""

import logging
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from ....schemas import TorchTrainerConfig
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
)
from ..modules.datasets import TabularTensorDataset, make_loaders
from ..modules.device import describe_device, setup_device, wrap_model
from ..modules.loops import accuracy, evaluate, predict, run_one_epoch
from ..modules.preprocessing import build_preprocessor
from ..modules.sanity import overfit_single_batch
from .base_trainer import BaseTrainer, _import_optuna

logger = logging.getLogger(__name__)

PREPROCESSOR_FILENAME = "preprocessor.joblib"

# name -> builder(input_dim, n_outputs, params). Add an architecture here and
# in configs/trainer/<name>.yaml; nothing else in the trainer changes.
ARCHITECTURES = {
    "mlp": lambda input_dim, n_outputs, params: MLP(
        input_dim=input_dim,
        hidden_sizes=list(params.get("hidden_sizes", [128, 64])),
        n_classes=n_outputs,
        dropout=params.get("dropout", 0.0),
    ),
}

# Tuning defaults per task: (project metric alias, optimisation direction).
_TUNE_DEFAULT = {
    "classification": ("f1_macro", "maximize"),
    "regression": ("rmse", "minimize"),
}


class TorchTrainer(BaseTrainer):
    """Plain-torch training loop wrapped in the ``BaseTrainer`` contract.

    Args:
        name: Architecture key in :data:`ARCHITECTURES`.
        params: Architecture hyperparameters (widths, dropout, ...).
        options: Harness knobs; validated as
            :class:`~PROJECT.schemas.TorchTrainerConfig`, so the defaults
            live in exactly one place.
        input_dim: Design-matrix width. Recorded at training time;
            supplied by :meth:`load` so the module can be rebuilt before
            its weights land.
        n_outputs: Head width (class count, or 1 for regression). Same
            provenance as ``input_dim``.
        classes: Original class labels in encoding order. Same provenance.
    """

    kind = "torch"

    def __init__(
        self,
        name: str,
        params: dict | None = None,
        *,
        options: dict | None = None,
        input_dim: int | None = None,
        n_outputs: int | None = None,
        classes: list | None = None,
        **kwargs,
    ):
        super().__init__(name, params, **kwargs)
        self.options = TorchTrainerConfig(**(options or {}))
        self.input_dim = input_dim
        self.n_outputs = n_outputs
        self.classes = classes
        self.preprocessor = None
        self.device = None
        self._optimizer = None
        self._best_state: dict | None = None
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

        Zero-argument and side-effect free, so it doubles as the factory
        the overfit-single-batch check needs (that check must not pollute
        the run's model with 100 steps of single-batch gradient).
        """
        if self.name not in ARCHITECTURES:
            raise KeyError(
                f"Unknown torch architecture {self.name!r}; registered: "
                f"{sorted(ARCHITECTURES)}. Add a builder to ARCHITECTURES and a "
                "configs/trainer/<name>.yaml."
            )
        if not self.input_dim:
            raise RuntimeError("input_dim is unknown; train() or load() sets it")
        return ARCHITECTURES[self.name](self.input_dim, self.n_outputs, self.params)

    def _get_param_space(self, trial) -> dict:
        """Search space, split by destination.

        ``params__*`` keys are architecture (they change checkpoint
        shapes), ``options__*`` keys are harness. The prefixes are what
        let :meth:`hyperparameter_tune` route a suggestion without a
        hardcoded list of which knob is which.
        """
        width = trial.suggest_categorical("params__hidden_width", [32, 64, 128, 256])
        depth = trial.suggest_int("params__depth", 1, 3)
        return {
            "params__hidden_sizes": [width // (2**i) or 1 for i in range(depth)],
            "params__dropout": trial.suggest_float("params__dropout", 0.0, 0.5),
            "options__lr": trial.suggest_float("options__lr", 1e-4, 1e-2, log=True),
            "options__weight_decay": trial.suggest_float(
                "options__weight_decay", 1e-8, 1e-2, log=True
            ),
        }

    # ------------------------------------------------------------------ fit

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
        self.preprocessor = build_preprocessor(
            self.numeric_features, self.categorical_features
        )
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

        start_epoch = self._maybe_resume()
        self._run_epochs(loaders, loss_fn, metric_fn, start_epoch)
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
        """Serve the best weights, not the last ones.

        Without this, ``evaluate`` and the metrics written into metadata
        would describe an epoch nobody chose - the one that happened to be
        last when patience ran out.
        """
        if not Path(best_path).exists():
            logger.warning("No best checkpoint written; keeping final weights")
            self._best_state = None
            return
        checkpoint = load_checkpoint(best_path, self.model, map_location="cpu")
        self._best_state = checkpoint["model_state_dict"]
        logger.info("Restored best-monitored weights into the served model")

    # ------------------------------------------------- CV and tuning overrides

    def _cv_estimator(self, overrides: dict | None = None):
        """Not available: a torch module is not a sklearn estimator.

        Raises:
            NotImplementedError: Always. ``sk_cross_validate`` would need
                a ``fit``/``predict`` adapter *and* k-fold epoch training,
                which is expensive enough that it must be an explicit
                choice rather than something the base quietly does.
        """
        raise NotImplementedError(
            "TorchTrainer has no sklearn CV estimator. Use hyperparameter_tune "
            "(which holds out a validation split per trial), or wrap the model "
            "in a skorch NeuralNetClassifier if k-fold CV is genuinely needed."
        )

    def hyperparameter_tune(
        self,
        X: pd.DataFrame,
        y,
        n_trials: int = 100,
        cv: int | object = 5,
        metric: str | None = None,
        direction: str = "maximize",
        **optuna_kwargs,
    ) -> dict:
        """Optuna over a held-out validation split, not k-fold CV.

        Overrides the base because k-fold would multiply an already
        expensive fit by ``cv``. ``cv`` is therefore **ignored** and a
        single stratified holdout is carved from ``X``.

        The other deviation: ``metric`` here is a *project metric alias*
        (``"f1_macro"``, ``"rmse"``) scored through :meth:`evaluate`, not
        a sklearn scoring string - there is no sklearn scorer to hand a
        torch module to. When ``metric`` is None both it and ``direction``
        come from the task.

        Returns:
            The best parameters found, already folded into ``params`` /
            ``options`` so the next :meth:`train` uses them.
        """
        optuna = _import_optuna()
        if metric is None:
            metric, direction = _TUNE_DEFAULT[self.task]
        stratify = y if self._is_classification else None
        X_tune, X_holdout, y_tune, y_holdout = train_test_split(
            X, y, test_size=0.2, random_state=self.seed, stratify=stratify
        )

        def objective(trial) -> float:
            suggestion = self._get_param_space(trial)
            candidate = self._candidate(suggestion)
            candidate.train(X_tune, y_tune, X_holdout, y_holdout)
            return candidate.evaluate(X_holdout, y_holdout, metrics=[metric])[metric]

        study = optuna.create_study(direction=direction, **optuna_kwargs)
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        self.best_params = dict(study.best_params)
        self._apply(self._get_best_suggestion(study))
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
            self.name,
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

    def _apply(self, suggestion: dict) -> None:
        """Fold a winning suggestion into this trainer's own config."""
        params, options = self._route(suggestion)
        self.params.update(params)
        self.options = TorchTrainerConfig(**{**self.options.model_dump(), **options})

    @staticmethod
    def _route(suggestion: dict) -> tuple[dict, dict]:
        """Split a ``params__``/``options__`` suggestion by destination."""
        params = {
            k[len("params__") :]: v
            for k, v in suggestion.items()
            if k.startswith("params__")
        }
        options = {
            k[len("options__") :]: v
            for k, v in suggestion.items()
            if k.startswith("options__")
        }
        return params, options

    def _get_best_suggestion(self, study) -> dict:
        """Re-derive the winning trial's routed values.

        ``study.best_params`` holds the *suggested* names
        (``params__hidden_width``), not the derived ones
        (``params__hidden_sizes``), so the space is replayed against a
        fixed trial to recover what the model was actually built with.
        """
        return self._get_param_space(_FixedTrial(study.best_params))

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
        matrix = self._to_array(self.preprocessor.transform(self.align(X)))
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

    def save(self, run_dir: str | Path) -> dict[str, str]:
        import torch

        self.check_fitted()
        run_dir = Path(run_dir)
        save_checkpoint(
            run_dir / LAST_CHECKPOINT,
            self.model,
            self._optimizer,
            epoch=self.summary.get("last_epoch", -1),
            metrics=self.summary.get("final_metrics", {}),
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


class _FixedTrial:
    """Replays recorded suggestions so a search space can be re-derived.

    Optuna ships ``FixedTrial``, but importing it would make optuna a hard
    dependency of a module that must import without it.
    """

    def __init__(self, params: dict):
        self._params = params

    def suggest_int(self, name, *args, **kwargs):
        return self._params[name]

    def suggest_float(self, name, *args, **kwargs):
        return self._params[name]

    def suggest_categorical(self, name, *args, **kwargs):
        return self._params[name]
