"""The fitted-preprocessing factory every trainer shares.

One ``ColumnTransformer`` builder, shared by every trainer, is what makes
the ``BaseTrainer`` contract meaningful: every trainer accepts the same raw
feature frame, so swapping ``trainer=`` never changes what the caller must
hand over. Fitted preprocessing belongs to the training pipeline, and
preprocessing and model serialize together, so they cannot drift apart at
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


def transformed_feature_names(
    preprocessor, input_cols: list[str], n_features: int | None = None
) -> list[str]:
    """Names for the *design matrix* columns, not the input columns.

    One-hot encoding makes those two different lists, which is the whole
    reason this exists: an importance vector is indexed by the transformed
    width, so labelling it with the raw feature list silently mislabels
    every bar after the first categorical.

    Degrades rather than raises in both directions, because a diagnostic
    must not be able to fail a run.

    Args:
        preprocessor: A **fitted** transformer, ideally one exposing
            ``get_feature_names_out()``.
        input_cols: Fallback names for a transformer that does not.
        n_features: Expected width. When given and the resolved names do
            not match it, generic ``f0..fN`` names are used instead, which
            is less misleading than a confidently wrong label.

    Returns:
        One name per design-matrix column.
    """
    try:
        names = [str(name) for name in preprocessor.get_feature_names_out()]
    except Exception as e:
        logger.debug("get_feature_names_out unavailable (%s); using input columns", e)
        names = [str(c) for c in input_cols]
    if n_features is not None and len(names) != n_features:
        logger.warning(
            "Resolved %d feature name(s) for a %d-column design matrix; falling "
            "back to positional names",
            len(names),
            n_features,
        )
        return [f"f{i}" for i in range(n_features)]
    return names
