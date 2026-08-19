from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import roc_auc_score

from packages.ml.label_policy import ML_PREDICTION_LABEL_CLASSES


ML_PROBABILITY_EVALUATION_CONTRACT_VERSION = (
    "ml-probability-evaluation-v1-logloss-brier-auc-ece-accuracy"
)
ML_PROBABILITY_ECE_BINS = 15
ML_MULTICLASS_BRIER_NORMALIZATION = "SUM_OVER_CLASSES_MEAN_OVER_ROWS"
ML_PROBABILITY_ROW_SUM_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class ProbabilityMetrics:
    rows: int
    log_loss: float
    multiclass_brier: float
    accuracy: float
    macro_ovr_auc: float | None
    macro_ece: float


def class_indices(labels: np.ndarray) -> np.ndarray:
    mapping = {label: index for index, label in enumerate(ML_PREDICTION_LABEL_CLASSES)}
    values = np.asarray(labels)
    result = np.empty(values.shape[0], dtype=np.int8)
    for label, index in mapping.items():
        result[values == label] = index
    unknown = ~np.isin(values, np.asarray(ML_PREDICTION_LABEL_CLASSES, dtype=object))
    if bool(np.any(unknown)):
        bad = sorted({str(value) for value in values[unknown]})
        raise ValueError("unknown prediction labels: " + ", ".join(bad))
    return result


def validate_probabilities(probabilities: np.ndarray) -> np.ndarray:
    values = np.asarray(probabilities, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(ML_PREDICTION_LABEL_CLASSES):
        raise ValueError("probabilities must have one column per locked prediction class")
    if not bool(np.isfinite(values).all()):
        raise ValueError("probabilities contain non-finite values")
    if bool((values < 0.0).any()) or bool((values > 1.0).any()):
        raise ValueError("probabilities must lie in [0, 1]")
    row_sums = values.sum(axis=1)
    if not bool(
        np.allclose(
            row_sums,
            1.0,
            atol=ML_PROBABILITY_ROW_SUM_TOLERANCE,
            rtol=ML_PROBABILITY_ROW_SUM_TOLERANCE,
        )
    ):
        raise ValueError("probability rows must sum to 1")

    # Multiclass probability estimators can accumulate tiny floating-point row-sum
    # error, especially when their inputs were standardized in float32. Once a row
    # has passed the strict numerical-validity tolerance above, normalize it exactly
    # before metrics or persisted prediction artifacts consume it.
    return values / row_sums[:, np.newaxis]


def _macro_ece(y_index: np.ndarray, probabilities: np.ndarray, *, bins: int) -> float:
    if bins < 2:
        raise ValueError("ECE requires at least two bins")
    n = int(y_index.shape[0])
    if n == 0:
        raise ValueError("cannot evaluate an empty prediction set")
    edges = np.linspace(0.0, 1.0, bins + 1)
    class_eces: list[float] = []
    for class_index in range(probabilities.shape[1]):
        confidence = probabilities[:, class_index]
        truth = (y_index == class_index).astype(np.float64)
        assignments = np.minimum(np.searchsorted(edges, confidence, side="right") - 1, bins - 1)
        assignments = np.maximum(assignments, 0)
        ece = 0.0
        for bin_index in range(bins):
            mask = assignments == bin_index
            count = int(mask.sum())
            if count == 0:
                continue
            ece += (count / n) * abs(float(confidence[mask].mean()) - float(truth[mask].mean()))
        class_eces.append(ece)
    return float(np.mean(class_eces))


def probability_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
    *,
    ece_bins: int = ML_PROBABILITY_ECE_BINS,
) -> ProbabilityMetrics:
    probs = validate_probabilities(probabilities)
    y_index = class_indices(np.asarray(labels))
    if y_index.shape[0] != probs.shape[0]:
        raise ValueError("label/probability row counts differ")
    rows = int(y_index.shape[0])
    if rows == 0:
        raise ValueError("cannot evaluate an empty prediction set")

    clipped = np.clip(probs, np.finfo(np.float64).eps, 1.0)
    log_loss = float(-np.log(clipped[np.arange(rows), y_index]).mean())
    one_hot = np.eye(probs.shape[1], dtype=np.float64)[y_index]
    brier = float(np.square(probs - one_hot).sum(axis=1).mean())
    accuracy = float((np.argmax(probs, axis=1) == y_index).mean())
    try:
        auc = float(
            roc_auc_score(
                y_index,
                probs,
                labels=np.arange(probs.shape[1]),
                multi_class="ovr",
                average="macro",
            )
        )
    except ValueError:
        auc = None
    ece = _macro_ece(y_index, probs, bins=ece_bins)
    return ProbabilityMetrics(
        rows=rows,
        log_loss=log_loss,
        multiclass_brier=brier,
        accuracy=accuracy,
        macro_ovr_auc=auc,
        macro_ece=ece,
    )
