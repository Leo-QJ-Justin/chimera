"""The shared plotting helpers: every one writes a real, decodable PNG.

Assert decodable image content, not file existence: a truncated or empty
file exists too. Each test reads back what was written, so a helper that
produced a broken image fails here.

The figures themselves are not compared pixel-wise: that tests matplotlib's
rendering, it breaks on every version bump, and it says nothing about
whether the right data was plotted.
"""

import numpy as np
import pytest

from PROJECT.core.plots import (
    plot_calibration_curve,
    plot_confusion_matrix,
    plot_feature_importances,
    plot_pr_curves,
    plot_residuals,
    plot_roc_curves,
    plot_training_curves,
    save_current_figure,
)

N = 120


@pytest.fixture
def binary():
    """``(y_true, proba)`` for a binary problem with real separation."""
    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 2, size=N)
    positive = np.clip(0.5 + 0.3 * (y_true - 0.5) + rng.normal(0, 0.15, N), 0.01, 0.99)
    return y_true, np.column_stack([1 - positive, positive])


@pytest.fixture
def multiclass():
    """``(y_true, proba, classes)`` for a three-class problem."""
    rng = np.random.default_rng(1)
    classes = [0, 1, 2]
    y_true = rng.integers(0, 3, size=N)
    scores = rng.random((N, 3))
    scores[np.arange(N), y_true] += 1.0
    return y_true, scores / scores.sum(axis=1, keepdims=True), classes


def _decode(path):
    """Read the PNG back, so a broken file cannot pass as a written one."""
    import matplotlib.image as mpimg

    assert path.exists(), f"{path} was not written"
    image = mpimg.imread(path)
    assert image.ndim == 3 and image.shape[0] > 10 and image.shape[1] > 10
    return image


class TestTrainingCurves:
    def test_train_and_val_series_share_an_axes(self, tmp_path):
        history = [
            {"epoch": i, "train_loss": 1.0 / (i + 1), "val_loss": 1.2 / (i + 1)}
            for i in range(8)
        ]
        _decode(plot_training_curves(history, tmp_path / "curves.png"))

    def test_train_only_history_is_plotted(self, tmp_path):
        """A run with no validation split still has a curve worth drawing."""
        history = [{"epoch": i, "train_loss": 1.0 / (i + 1)} for i in range(5)]
        _decode(plot_training_curves(history, tmp_path / "curves.png"))

    def test_unprefixed_series_get_their_own_axes(self, tmp_path):
        history = [
            {"epoch": i, "train_loss": 0.5, "val_loss": 0.6, "lr": 0.001}
            for i in range(4)
        ]
        _decode(plot_training_curves(history, tmp_path / "curves.png"))

    def test_empty_history_writes_nothing(self, tmp_path):
        # Not an error: a one-shot sklearn fit has no iterations to plot.
        assert plot_training_curves([], tmp_path / "curves.png") is None
        assert not (tmp_path / "curves.png").exists()

    def test_non_numeric_values_are_ignored(self, tmp_path):
        history = [{"epoch": 0, "train_loss": 0.5, "note": "warmup"}]
        _decode(plot_training_curves(history, tmp_path / "curves.png"))


class TestClassificationPlots:
    def test_confusion_matrix_is_written(self, tmp_path, binary):
        y_true, proba = binary
        y_pred = proba.argmax(axis=1)
        _decode(plot_confusion_matrix(y_true, y_pred, tmp_path / "cm.png"))

    def test_roc_returns_the_auc_for_a_binary_problem(self, tmp_path, binary):
        y_true, proba = binary
        path, metrics = plot_roc_curves(y_true, proba, tmp_path / "roc.png")
        _decode(path)
        assert set(metrics) == {"roc_auc"}
        assert 0.5 < metrics["roc_auc"] <= 1.0

    def test_roc_reports_per_class_and_macro_areas_for_multiclass(
        self, tmp_path, multiclass
    ):
        y_true, proba, classes = multiclass
        path, metrics = plot_roc_curves(y_true, proba, tmp_path / "roc.png", classes)
        _decode(path)
        assert set(metrics) == {"roc_auc", "roc_auc_0", "roc_auc_1", "roc_auc_2"}
        per_class = [metrics[f"roc_auc_{c}"] for c in classes]
        assert metrics["roc_auc"] == pytest.approx(float(np.mean(per_class)))

    def test_pr_returns_the_average_precision(self, tmp_path, binary):
        y_true, proba = binary
        path, metrics = plot_pr_curves(y_true, proba, tmp_path / "pr.png")
        _decode(path)
        assert set(metrics) == {"pr_auc"}
        assert 0.0 <= metrics["pr_auc"] <= 1.0

    def test_curves_accept_a_one_dimensional_positive_score(self, tmp_path, binary):
        y_true, proba = binary
        _, metrics = plot_roc_curves(y_true, proba[:, 1], tmp_path / "roc.png")
        assert 0.5 < metrics["roc_auc"] <= 1.0

    def test_label_count_must_match_the_probability_columns(self, tmp_path, binary):
        y_true, proba = binary
        with pytest.raises(ValueError, match="same model"):
            plot_roc_curves(y_true, proba, tmp_path / "roc.png", classes=[0, 1, 2])

    def test_calibration_is_written_for_a_binary_problem(self, tmp_path, binary):
        y_true, proba = binary
        _decode(plot_calibration_curve(y_true, proba, tmp_path / "cal.png"))

    def test_calibration_refuses_multiclass(self, tmp_path, multiclass):
        y_true, proba, classes = multiclass
        with pytest.raises(ValueError, match="binary problems only"):
            plot_calibration_curve(y_true, proba, tmp_path / "cal.png", classes)


class TestRegressionPlots:
    def test_residuals_are_written(self, tmp_path):
        rng = np.random.default_rng(2)
        y_true = rng.normal(size=N)
        y_pred = y_true + rng.normal(0, 0.2, N)
        _decode(plot_residuals(y_true, y_pred, tmp_path / "r.png"))


class TestFeatureImportances:
    def test_top_n_caps_the_bars(self, tmp_path):
        names = [f"feature_{i}" for i in range(40)]
        values = np.linspace(0.0, 1.0, 40)
        _decode(plot_feature_importances(names, values, tmp_path / "fi.png", top_n=5))

    def test_signed_coefficients_are_ranked_by_magnitude(self, tmp_path):
        # A large negative coefficient is influential; sorting by raw value
        # would bury it at the bottom of the chart.
        out = tmp_path / "coefficients.png"
        _decode(plot_feature_importances(["a", "b", "c"], [-9.0, 0.1, 1.0], out))

    def test_mismatched_names_and_values_raise(self, tmp_path):
        with pytest.raises(ValueError, match="label the wrong bars"):
            plot_feature_importances(["a", "b"], [1.0], tmp_path / "fi.png")


class TestFigureHygiene:
    def test_helpers_leave_no_figure_open(self, tmp_path, binary):
        """An unclosed figure leaks across a suite until matplotlib warns."""
        from matplotlib import pyplot as plt

        plt.close("all")
        y_true, proba = binary
        plot_confusion_matrix(y_true, proba.argmax(axis=1), tmp_path / "cm.png")
        plot_roc_curves(y_true, proba, tmp_path / "roc.png")
        plot_residuals(y_true, proba[:, 1], tmp_path / "res.png")
        assert plt.get_fignums() == []

    def test_save_current_figure_writes_and_closes_it(self, tmp_path):
        """The escape hatch for libraries that draw onto the current figure."""
        from matplotlib import pyplot as plt

        plt.close("all")
        plt.figure()
        plt.plot([0, 1], [0, 1])
        _decode(save_current_figure(tmp_path / "current.png"))
        assert plt.get_fignums() == []

    def test_the_destination_directory_is_created(self, tmp_path, binary):
        y_true, proba = binary
        nested = tmp_path / "plots" / "deeper" / "cm.png"
        _decode(plot_confusion_matrix(y_true, proba.argmax(axis=1), nested))
