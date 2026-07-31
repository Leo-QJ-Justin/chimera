"""``LogisticRegressionTrainer``: the linear classification baseline.

Its own class rather than a row in a generic estimator table: a family is
defined by its search space as much as by its constructor, and logistic
regression's is coupled (penalty, solver and ``l1_ratio`` are only legal in
certain combinations). That coupling has nowhere to live in a shared
lookup table.
"""

import logging

from sklearn.linear_model import LogisticRegression

from .sklearn_common import SklearnEstimatorTrainer

logger = logging.getLogger(__name__)


class LogisticRegressionTrainer(SklearnEstimatorTrainer):
    """Regularised linear classifier, fitted inside its preprocessing."""

    kind = "logreg"

    def _build_model(self):
        if self.task != "classification":
            raise ValueError(
                f"trainer.kind='logreg' is a classifier, not task={self.task!r}; "
                "use trainer=random_forest (or another regressor) instead"
            )
        return LogisticRegression(random_state=self.seed, **self.params)

    def _get_param_space(self, trial) -> dict:
        # Suggest the solver first and derive the penalty from it: elasticnet
        # exists only under saga, and l1_ratio is read only under elasticnet,
        # so sampling them independently would spend trials on illegal
        # combinations. The derived keys survive because hyperparameter_tune
        # records the resolved dict, not just what Optuna suggested.
        solver = trial.suggest_categorical("solver", ["lbfgs", "saga"])
        space = {
            "C": trial.suggest_float("C", 1e-3, 1e2, log=True),
            "solver": solver,
            "class_weight": trial.suggest_categorical("class_weight", [None, "balanced"]),
        }
        if solver == "saga":
            space["penalty"] = "elasticnet"
            space["l1_ratio"] = trial.suggest_float("l1_ratio", 0.0, 1.0)
        return space
