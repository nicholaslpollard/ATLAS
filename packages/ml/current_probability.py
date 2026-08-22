from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.ml.evaluation import validate_probabilities
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.final_acceptance import ML_FINAL_ACCEPTANCE_CONTRACT_VERSION, MLFinalAcceptance
from packages.ml.label_policy import ML_PREDICTION_LABEL_PROBABILITY_FIELDS
from packages.ml.model_registry import accepted_model_id, model_registry_fingerprint


CURRENT_ML_PROBABILITY_CONTRACT_VERSION = (
    "current-ml-probability-v1-accepted-phase10-final-fit-raw-threeclass"
)


class CurrentMLProbabilityError(RuntimeError):
    pass


class AcceptedProductionProbabilityProvider:
    """Read-only inference adapter for the accepted Phase 10 final-fit model.

    This adapter returns raw three-class probability evidence only. It deliberately
    exposes no argmax trade direction, promotion threshold, position sizing, or order.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.final = MLFinalAcceptance(settings)
        self.predictors = tuple(ML_PRODUCTION_CORE_FEATURE_NAMES)
        self.model_id = accepted_model_id()
        self.model_fingerprint = model_registry_fingerprint()
        self._model: Any | None = None

    @staticmethod
    def _json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise CurrentMLProbabilityError(f"missing {label}: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CurrentMLProbabilityError(f"invalid JSON for {label}: {path}") from exc

    def _verified_model_path(self) -> Path:
        report = self._json(self.final.report_path(), "Phase 10 final acceptance report")
        if report.get("contract_version") != ML_FINAL_ACCEPTANCE_CONTRACT_VERSION:
            raise CurrentMLProbabilityError("Phase 10 final acceptance contract changed")
        if report.get("accepted") is not True:
            raise CurrentMLProbabilityError("Phase 10 final model is not accepted")
        if report.get("model_id") != self.model_id:
            raise CurrentMLProbabilityError("accepted model id changed")
        if report.get("model_fingerprint") != self.model_fingerprint:
            raise CurrentMLProbabilityError("accepted model fingerprint changed")
        artifact = report.get("final_model_artifact")
        if not isinstance(artifact, dict):
            raise CurrentMLProbabilityError("accepted final model artifact is missing")
        path = self.final.registry_root() / str(artifact["relative_path"])
        if not path.is_file() or sha256_file(path) != str(artifact["sha256"]):
            raise CurrentMLProbabilityError("accepted final model artifact hash changed")

        production = self._json(self.final.production_manifest_path(), "production model manifest")
        if production.get("model_id") != self.model_id:
            raise CurrentMLProbabilityError("production manifest model id changed")
        if production.get("model_fingerprint") != self.model_fingerprint:
            raise CurrentMLProbabilityError("production manifest model fingerprint changed")
        if production.get("final_fit_artifact_present") is not True:
            raise CurrentMLProbabilityError("production manifest has no final fit")
        manifest_artifact = production.get("final_model_artifact")
        if not isinstance(manifest_artifact, dict) or manifest_artifact.get("sha256") != artifact.get("sha256"):
            raise CurrentMLProbabilityError("production/final acceptance model hashes disagree")
        return path

    def model(self):
        if self._model is None:
            self._model = joblib.load(self._verified_model_path())
            classes = np.asarray(getattr(self._model, "classes_", []))
            if not np.array_equal(classes, np.asarray([0, 1, 2])):
                raise CurrentMLProbabilityError("accepted model class order changed")
        return self._model

    def predict_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        missing = [name for name in self.predictors if name not in frame.columns]
        if missing:
            raise CurrentMLProbabilityError(
                "current probability frame is missing accepted predictors: " + ", ".join(missing)
            )
        x = frame.loc[:, list(self.predictors)].to_numpy(dtype=np.float32, copy=True)
        probabilities = validate_probabilities(self.model().predict_proba(x))
        fields = tuple(ML_PREDICTION_LABEL_PROBABILITY_FIELDS)
        out = pd.DataFrame(index=frame.index)
        out["ml_probability_contract_version"] = CURRENT_ML_PROBABILITY_CONTRACT_VERSION
        out["ml_model_id"] = self.model_id
        out["ml_model_fingerprint"] = self.model_fingerprint
        out[fields[0]] = probabilities[:, 0]
        out[fields[1]] = probabilities[:, 1]
        out[fields[2]] = probabilities[:, 2]
        return out
