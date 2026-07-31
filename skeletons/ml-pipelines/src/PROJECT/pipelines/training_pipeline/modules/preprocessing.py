"""The fitted-preprocessing factory every trainer shares.

One ``ColumnTransformer`` builder, used by all three trainers, is what
makes the ``BaseTrainer`` contract meaningful: every trainer accepts the
same raw feature frame, so swapping ``model=`` never changes what the
caller must hand over. It is also the D6 rule in code - fitted
preprocessing belongs to the training pipeline, and it serializes
together with the estimator so the two halves cannot drift apart at
serving time.

Stateless *factory*, stateful *product*: this module builds an unfitted
transformer, which is why it lives in ``modules/`` while the fitted thing
lives inside a trainer in ``classes/``.
"""

import logging

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

logger = logging.getLogger(__name__)


def build_preprocessor(
    numeric: list[str], categorical: list[str], scale_numeric: bool = True
) -> ColumnTransformer:
    """Impute + scale numerics, impute + one-hot categoricals.

    Args:
        numeric: Numeric feature columns.
        categorical: Categorical feature columns.
        scale_numeric: Standardise numerics. Tree ensembles do not need
            it (splits are scale-invariant) but it costs nothing and
            keeps one code path; neural nets and linear models do need
            it, so the default is on.

    Returns:
        An **unfitted** ``ColumnTransformer`` emitting pandas output, so
        feature names survive the transform and post-hoc importance/SHAP
        stays readable.
    """
    if not numeric and not categorical:
        raise ValueError(
            "No feature columns given: a preprocessor over nothing would "
            "produce an empty design matrix"
        )
    numeric_steps: list[tuple] = [("impute", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric_steps.append(("scale", StandardScaler()))
    categorical_steps = [
        ("impute", SimpleImputer(strategy="most_frequent")),
        # handle_unknown="ignore": an unseen category at serving time is an
        # all-zero row, not a crash.
        ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ]
    preprocessor = ColumnTransformer(
        [
            ("numeric", Pipeline(numeric_steps), numeric),
            ("categorical", Pipeline(categorical_steps), categorical),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    preprocessor.set_output(transform="pandas")
    return preprocessor
