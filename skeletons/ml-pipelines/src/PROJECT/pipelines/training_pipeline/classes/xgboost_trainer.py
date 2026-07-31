"""``XGBoostTrainer``: the other boosting family, with its own fit path.

Same reason LightGBM has one: early stopping needs the **transformed**
validation matrix at fit time, which a sklearn ``Pipeline.fit`` signature
cannot carry. The difference from LightGBM is in the wiring -
``early_stopping_rounds`` is a *constructor* argument in xgboost >= 1.6,
not a fit argument or a callback, and setting it without an ``eval_set``
raises. So it is attached in :meth:`train`, only once there is something
to stop on, which also leaves ``_build_model`` usable for the base's CV
and tuning paths.
"""

import logging

import pandas as pd

from ..modules.model_logging import log_flavor_model
from .sklearn_common import PipelineArtifactTrainer

logger = logging.getLogger(__name__)


def _import_xgboost():
    """Guarded import: the failure must name the install, not the traceback."""
    try:
        import xgboost
    except ImportError as e:
        raise ImportError(
            "trainer.kind='xgboost' requires the optional dependency: "
            "`uv add xgboost` (or install the 'xgboost' extra)"
        ) from e
    return xgboost


class XGBoostTrainer(PipelineArtifactTrainer):
    """Gradient-boosted trees with validation-driven early stopping.

    Args:
        early_stopping_rounds: Rounds without improvement on the
            validation split before the booster stops. None (or no
            validation split) trains the full ``n_estimators``.
        log_period: Rounds between eval-log lines; 0 silences them.
    """

    kind = "xgboost"
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
        xgboost = _import_xgboost()
        booster = (
            xgboost.XGBRegressor if self.task == "regression" else xgboost.XGBClassifier
        )
        return booster(random_state=self.seed, **self.params)

    def _get_param_space(self, trial) -> dict:
        return {
            # xgboost's `eta`, under the sklearn API's name for it.
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 2, 10),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
            "n_estimators": trial.suggest_int("n_estimators", 50, 500, step=50),
        }

    def train(
        self,
        X: pd.DataFrame,
        y,
        X_val: pd.DataFrame | None = None,
        y_val=None,
        **kwargs,
    ) -> "XGBoostTrainer":
        preprocessor = self.new_preprocessor()
        X_train_t = preprocessor.fit_transform(self.align(X))
        booster = self._build_model()

        fit_kwargs = dict(kwargs)
        if X_val is not None and y_val is not None:
            if self.early_stopping_rounds:
                booster.set_params(early_stopping_rounds=self.early_stopping_rounds)
            fit_kwargs["eval_set"] = [(preprocessor.transform(self.align(X_val)), y_val)]
            fit_kwargs.setdefault("verbose", self.log_period or False)
        else:
            logger.warning(
                "No validation split given; XGBoost will train the full "
                "n_estimators with no early stopping"
            )

        booster.fit(X_train_t, y, **fit_kwargs)
        # None until a stopping round actually fires, so it doubles as the
        # record of whether early stopping engaged.
        self.best_iteration = getattr(booster, "best_iteration", None)
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
        """The bare booster, in the ``mlflow.xgboost`` flavor.

        The flavor stores an XGBoost model, not a sklearn pipeline, so the
        example is transformed first and the recorded signature describes
        what the artifact actually accepts.
        """
        self.check_fitted()
        example = None if input_example is None else self.transformed(input_example)
        log_flavor_model(
            tracker,
            "xgboost",
            self.estimator,
            input_example=example,
            predictions=None if example is None else self.estimator.predict(example),
        )
