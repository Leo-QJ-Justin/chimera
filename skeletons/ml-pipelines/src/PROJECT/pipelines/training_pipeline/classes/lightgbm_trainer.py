"""``LightGBMTrainer``: the native fit path, with ``eval_set`` early stopping.

Why its early stopping needs a fit path of its own: it wants the
**transformed** validation matrix at fit time, and a sklearn ``Pipeline``
cannot carry one - ``pipeline.fit(X, y, model__eval_set=...)`` hands the
booster *untransformed* validation data, which either raises or, worse,
silently stops on a garbage curve.

So the two halves are fitted in order (preprocessor on train, booster on
the transformed matrices) and only then assembled into the shared
``Pipeline`` artifact, which makes a LightGBM run indistinguishable from
any other at serving time.

Cross-validation and tuning still go through the base's sklearn path,
where there is no validation split to stop on: those runs train the full
``n_estimators`` by design, and the early-stopped fit is what the final
``train`` produces.
"""

import logging
from inspect import signature

import pandas as pd

from ..modules.history import booster_history
from ..modules.model_logging import log_flavor_model
from .sklearn_common import PipelineArtifactTrainer

logger = logging.getLogger(__name__)


def _import_lightgbm():
    """Guarded import: the failure must name the install, not the traceback."""
    try:
        import lightgbm
    except ImportError as e:
        raise ImportError(
            "trainer.kind='lightgbm' requires the optional dependency: "
            "`uv add lightgbm` (or install the 'lightgbm' extra)"
        ) from e
    return lightgbm


class LightGBMTrainer(PipelineArtifactTrainer):
    """Gradient-boosted trees with validation-driven early stopping.

    Args:
        early_stopping_rounds: Rounds without improvement on the
            validation split before the booster stops. None (or no
            validation split) trains the full ``n_estimators``.
        log_period: Rounds between eval-log lines; 0 silences them.
    """

    kind = "lightgbm"
    scale_numeric = False

    def __init__(
        self,
        params: dict | None = None,
        *,
        early_stopping_rounds: int | None = 50,
        log_period: int = 0,
        **kwargs,
    ):
        super().__init__(params, **kwargs)
        self.early_stopping_rounds = early_stopping_rounds
        self.log_period = log_period
        self.best_iteration: int | None = None

    def extra_spec(self) -> dict:
        return {
            "early_stopping_rounds": self.early_stopping_rounds,
            "log_period": self.log_period,
        }

    def _build_model(self):
        lightgbm = _import_lightgbm()
        booster = (
            lightgbm.LGBMRegressor
            if self.task == "regression"
            else lightgbm.LGBMClassifier
        )
        return booster(random_state=self.seed, **self.params)

    def _get_param_space(self, trial) -> dict:
        return {
            "num_leaves": trial.suggest_int("num_leaves", 15, 150),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 50, 500, step=50),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        }

    def train(
        self,
        X: pd.DataFrame,
        y,
        X_val: pd.DataFrame | None = None,
        y_val=None,
        **kwargs,
    ) -> "LightGBMTrainer":
        lightgbm = _import_lightgbm()
        preprocessor = self.new_preprocessor()
        X_train_t = preprocessor.fit_transform(self.align(X))
        booster = self._build_model()

        fit_kwargs = dict(kwargs)
        # Filled in place by the record_evaluation callback below; stays empty
        # when there is no eval set to record.
        evals_result: dict = {}
        if X_val is not None and y_val is not None:
            X_val_t = preprocessor.transform(self.align(X_val))
            # LightGBM 4.7 renamed `eval_set` to `eval_X`/`eval_y` and warns on
            # the old name; earlier 4.x has only the old one. Probing the
            # signature keeps the supported range wide and the log clean.
            if "eval_X" in signature(booster.fit).parameters:
                fit_kwargs.update({"eval_X": X_val_t, "eval_y": y_val})
            else:
                fit_kwargs["eval_set"] = [(X_val_t, y_val)]
            # Capture only: the orchestrator replays history into the tracker,
            # so the trainer stays free of tracking and plotting code.
            callbacks = [lightgbm.record_evaluation(evals_result)]
            if self.early_stopping_rounds:
                callbacks.append(
                    lightgbm.early_stopping(self.early_stopping_rounds, verbose=False)
                )
            if self.log_period:
                callbacks.append(lightgbm.log_evaluation(period=self.log_period))
            fit_kwargs["callbacks"] = callbacks
        else:
            logger.warning(
                "No validation split given; LightGBM will train the full "
                "n_estimators with no early stopping"
            )

        booster.fit(X_train_t, y, **fit_kwargs)
        self.best_iteration = getattr(booster, "best_iteration_", None)
        self.history = booster_history(evals_result)
        self.assemble(preprocessor, booster)
        logger.info(
            "Trained %s on %d rows (best_iteration=%s of %s)",
            self.model_type,
            len(X),
            self.best_iteration,
            self.params.get("n_estimators"),
        )
        return self

    def training_summary(self) -> dict:
        return {
            "best_iteration": self.best_iteration,
            "early_stopping_rounds": self.early_stopping_rounds,
        }

    def get_params(self) -> dict:
        params = super().get_params()
        params["early_stopping_rounds"] = self.early_stopping_rounds
        if self.best_iteration is not None:
            params["best_iteration"] = self.best_iteration
        return params

    def log_model(self, tracker, input_example=None) -> None:
        """The bare booster, in the ``mlflow.lightgbm`` flavor.

        The flavor stores a LightGBM model, not a sklearn pipeline, so the
        logged model takes the *transformed* design matrix - which is what
        the example is transformed into here, so the recorded signature
        describes what the artifact actually accepts.
        """
        self.check_fitted()
        example = None if input_example is None else self.transformed(input_example)
        log_flavor_model(
            tracker,
            "lightgbm",
            self.estimator,
            input_example=example,
            predictions=None if example is None else self.estimator.predict(example),
        )
