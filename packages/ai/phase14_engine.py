from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Callable

from packages.ai.analyst import IndependentAIAnalyst
from packages.ai.openai_provider import OpenAIResponsesReviewProvider
from packages.ai.phase14_policy import (
    PHASE14_BROKER_WRITES,
    PHASE14_EXTERNAL_DELIVERY_ENABLED,
    PHASE14_ORDER_WRITES,
    PHASE14_POSITION_WRITES,
    PHASE14_PRODUCTION_ML_WRITES,
    phase14_policy_fingerprint,
    phase14_policy_payload,
)
from packages.ai.phase14_source import Phase14ReviewInputResolver
from packages.ai.provider import AIReviewProvider
from packages.alerts.builder import build_alert_artifact
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.schemas.ai_review import AIReviewRecord


PHASE14_MANIFEST_CONTRACT_VERSION = (
    "phase14-manifest-v1-hash-bound-structured-ai-review-engine-vs-ai-alert-artifacts"
)
PHASE14_NO_REVIEW_DISPOSITION = "NO_ACCEPTED_PHASE13_REVIEW_READY_CASES"


class Phase14EngineError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class Phase14AuditEngine:
    def __init__(
        self,
        settings: AtlasSettings,
        *,
        provider: AIReviewProvider | None = None,
    ) -> None:
        self.settings = settings
        self.input_resolver = Phase14ReviewInputResolver(settings)
        self._provider = provider
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "ai_review" / "phase14" / "v1"

    def manifest_path(self, as_of_date: date) -> Path:
        return self.root / "manifests" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def review_dir(self, as_of_date: date, instrument_id: str) -> Path:
        safe = hashlib.sha256(instrument_id.encode("utf-8")).hexdigest()[:20]
        return self.root / "reviews" / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / safe

    @staticmethod
    def _write_json(path: Path, payload: object) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
        return sha256_file(path)

    def _resolve_provider(self) -> AIReviewProvider:
        if self._provider is not None:
            return self._provider
        return OpenAIResponsesReviewProvider()

    def run(
        self,
        *,
        as_of_date: date | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        review_input = self.input_resolver.resolve(as_of_date)
        policy = phase14_policy_payload()
        policy_fp = phase14_policy_fingerprint()
        provider_initialized = False
        provider_calls = 0
        records: list[dict[str, object]] = []
        dispositions = {"APPROVE": 0, "CAUTIOUS": 0, "REJECT": 0}

        if review_input.review_ready_count == 0:
            if progress is not None:
                progress("no accepted Phase 13 review-ready cases; AI provider and alert generation skipped")
        else:
            try:
                provider = self._resolve_provider()
            except Exception as exc:
                raise Phase14EngineError(
                    f"Phase 14 AI provider initialization failed: {type(exc).__name__}"
                ) from exc
            provider_initialized = True
            analyst = IndependentAIAnalyst(provider)
            for index, (case, research, case_sha) in enumerate(
                zip(
                    review_input.review_ready_cases,
                    review_input.phase12_research_cases,
                    review_input.phase13_case_sha256,
                    strict=True,
                ),
                start=1,
            ):
                if progress is not None:
                    progress(
                        f"Phase 14 AI audit {index}/{review_input.review_ready_count}: {case.ticker}"
                    )
                try:
                    completed = analyst.review_case(case, research)
                except Exception as exc:
                    raise Phase14EngineError(
                        f"Phase 14 AI review failed closed for {case.ticker}: {type(exc).__name__}"
                    ) from exc
                provider_calls += 1
                out_dir = self.review_dir(review_input.as_of_date, case.instrument_id)
                raw_path = out_dir / "provider_response.json"
                raw_sha = self._write_json(raw_path, completed.provider_response.raw_response)
                review_record = AIReviewRecord(
                    instrument_id=case.instrument_id,
                    ticker=case.ticker,
                    as_of_date=case.as_of_date,
                    phase13_case_sha256=case_sha,
                    phase13_case_contract_version=case.contract_version,
                    prompt_contract_version=completed.prompt.contract_version,
                    prompt_fingerprint=completed.prompt.fingerprint,
                    provider=completed.provider_response.provider,
                    model=completed.provider_response.model,
                    response_id=completed.provider_response.response_id,
                    raw_response_path=str(raw_path.resolve()),
                    raw_response_sha256=raw_sha,
                    reviewed_at_utc=datetime.now(UTC),
                    review=completed.review,
                    disposition_is_trade_signal=False,
                    ai_changed_deterministic_case=False,
                    ai_created_order=False,
                )
                review_path = out_dir / "ai_review.json"
                review_path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text(review_path, review_record.model_dump_json(indent=2) + "\n")
                review_sha = sha256_file(review_path)

                alert = build_alert_artifact(
                    case,
                    phase13_case_sha256=case_sha,
                    review_record=review_record,
                    ai_review_sha256=review_sha,
                )
                alert_path = out_dir / "alert.json"
                atomic_write_text(alert_path, alert.model_dump_json(indent=2) + "\n")
                alert_sha = sha256_file(alert_path)
                dispositions[review_record.review.disposition.value] += 1
                records.append(
                    {
                        "instrument_id": case.instrument_id,
                        "ticker": case.ticker,
                        "phase13_case_sha256": case_sha,
                        "prompt_fingerprint": completed.prompt.fingerprint,
                        "provider": completed.provider_response.provider,
                        "model": completed.provider_response.model,
                        "disposition": review_record.review.disposition.value,
                        "raw_response_path": str(raw_path.resolve()),
                        "raw_response_sha256": raw_sha,
                        "review_path": str(review_path.resolve()),
                        "review_sha256": review_sha,
                        "alert_path": str(alert_path.resolve()),
                        "alert_sha256": alert_sha,
                    }
                )

        source_payload = {
            "contract_version": PHASE14_MANIFEST_CONTRACT_VERSION,
            "as_of_date": review_input.as_of_date.isoformat(),
            "phase14_input_fingerprint": review_input.source_fingerprint,
            "policy_fingerprint": policy_fp,
            "review_hashes": [item["review_sha256"] for item in records],
            "alert_hashes": [item["alert_sha256"] for item in records],
        }
        manifest: dict[str, object] = {
            "contract_version": PHASE14_MANIFEST_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "as_of_date": review_input.as_of_date.isoformat(),
            "phase14_input": review_input.public_dict(),
            "policy": policy,
            "policy_fingerprint": policy_fp,
            "phase13_case_count": review_input.phase13_case_count,
            "phase13_review_ready_count": review_input.review_ready_count,
            "ai_review_count": len(records),
            "alert_artifact_count": len(records),
            "disposition_counts": dispositions,
            "records": records,
            "no_review_disposition": (
                PHASE14_NO_REVIEW_DISPOSITION if review_input.review_ready_count == 0 else None
            ),
            "provider_initialized": provider_initialized,
            "provider_calls": provider_calls,
            "external_delivery_enabled": PHASE14_EXTERNAL_DELIVERY_ENABLED,
            "external_deliveries": 0,
            "production_ml_writes": PHASE14_PRODUCTION_ML_WRITES,
            "broker_writes": PHASE14_BROKER_WRITES,
            "order_writes": PHASE14_ORDER_WRITES,
            "position_writes": PHASE14_POSITION_WRITES,
            "execution_present": False,
            "pass": True,
        }
        path = self.manifest_path(review_input.as_of_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
        manifest["manifest_path"] = str(path.resolve())
        return manifest
