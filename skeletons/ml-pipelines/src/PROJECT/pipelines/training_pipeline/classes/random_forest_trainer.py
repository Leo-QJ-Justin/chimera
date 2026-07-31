"""``RandomForestTrainer``: bagged trees for either task.

The strong tabular baseline that needs no early stopping and no tuning to
be useful, which is why it is the default trainer in the shipped config.
"""

import logging

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from .sklearn_common import SklearnEstimatorTrainer

logger = logging.getLogger(__name__)


class RandomForestTrainer(SklearnEstimatorTrainer):
    """Random forest, fitted inside its preprocessing."""

    kind = "random_forest"
    # Splits are scale-invariant, so scaling would cost a transform and blur
    # the feature values in any importance plot drawn from the artifact.
    scale_numeric = False
    # Bagged trees stop when the forest is grown, not when a validation curve
    # turns, so the fit never reads val. Its runs pool train+val and select on
    # a k-fold CV estimate (R1.10).
    uses_val_in_fit = False

    def _build_model(self):
        forest = (
            RandomForestRegressor if self.task == "regression" else RandomForestClassifier
        )
        return forest(random_state=self.seed, n_jobs=-1, **self.params)

    def _get_param_space(self, trial) -> dict:
        return {
            "n_estimators": trial.suggest_int("n_estimators", 100, 600, step=50),
            "max_depth": trial.suggest_int("max_depth", 3, 20),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 20),
            # None means "all features", which turns the forest into bagged
            # trees; it is a real setting, so it stays in the space.
            "max_features": trial.suggest_categorical(
                "max_features", ["sqrt", "log2", None]
            ),
        }
