from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from packages.core.settings import AtlasSettings
from packages.data.historical_news_v1_chronology_diagnostic import (
    run_historical_news_v1_chronology_diagnostic,
)
from packages.data.historical_news_v1_closeout import (
    CLOSEOUT_CONTRACT,
    EXPECTED_ACQUISITION_RUN_FINGERPRINT,
    EXPECTED_NORMALIZED_ARTICLES,
    EXPECTED_RAW_PROVIDER_RECORDS,
    HISTORICAL_NEWS_V1_CLOSEOUT_CONTRACT_FINGERPRINT,
    _atomic_write_json,
    _canonical_hash,
    _parse_timestamp,
    run_historical_news_v1_closeout,
)
from packages.data.historical_news_v1_contract import (
    HISTORICAL_NEWS_V1_CONTRACT,
    HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
)


SOURCE_INTEGRITY_V2_CONTRACT: str = (
    "atlas-historical-news-v1-source-integrity-closeout-v2"
)
EXPECTED_CORPUS_FINGERPRINT: str = (
    "a5a26ed8b0093db16060c03d5ecb883a03322e61d7fe7217549b678dc1b3a1b0"
)
EFFECTIVE_PIT_POLICY: str = "MAX_CREATED_AT_UPDATED_AT_CONSERVATIVE"
EXPECTED_FAILED_PARTITIONS: tuple[str, ...] = ("2015-07", "2026-08")

EXPECTED_CHRONOLOGY_ANOMALIES: tuple[dict[str, str], ...] = (
    {
        "month": "2015-07",
        "article_id": "5663867",
        "provider_record_sha256": (
            "b42ab322cfa90748d88ec05b3a131010c1aa3fd3ad652a74a7f7fe173545d892"
        ),
        "created_at_utc": "2015-07-11T17:16:44Z",
        "updated_at_utc": "2015-07-11T17:16:43Z",
    },
    {
        "month": "2015-07",
        "article_id": "5663581",
        "provider_record_sha256": (
            "bf1fcd057e8954657375189de6d7258a9f28974de823157292cc44390c6b51c7"
        ),
        "created_at_utc": "2015-07-11T17:18:40Z",
        "updated_at_utc": "2015-07-11T17:18:24Z",
    },
    {
        "month": "2015-07",
        "article_id": "5663495",
        "provider_record_sha256": (
            "4102199e696980778232f51ca4d951aa43bc2e937f9a1572ed25e40ebb0abdad"
        ),
        "created_at_utc": "2015-07-11T17:19:58Z",
        "updated_at_utc": "2015-07-11T17:19:40Z",
    },
    {
        "month": "2026-08",
        "article_id": "61242877",
        "provider_record_sha256": (
            "723b94335a5d9d3f2043867078d7120e1a38bf7e4c7851c30edeba7954d16ee7"
        ),
        "created_at_utc": "2026-08-17T15:56:00Z",
        "updated_at_utc": "2026-08-17T15:55:31Z",
    },
)


def _utc_text(value: object) -> str:
    parsed = _parse_timestamp(value)
    if parsed is None:
        raise ValueError("timestamp is required")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def effective_pit_available_at(
    created_at: object,
    updated_at: object,
) -> datetime:
    created = _parse_timestamp(created_at)
    updated = _parse_timestamp(updated_at)
    if created is None or updated is None:
        raise ValueError("created_at and updated_at are required for effective PIT")
    return max(created, updated)


def source_integrity_v2_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": SOURCE_INTEGRITY_V2_CONTRACT,
        "acquisition_contract": HISTORICAL_NEWS_V1_CONTRACT,
        "acquisition_contract_fingerprint": HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
        "parent_closeout_contract": CLOSEOUT_CONTRACT,
        "parent_closeout_contract_fingerprint": (
            HISTORICAL_NEWS_V1_CLOSEOUT_CONTRACT_FINGERPRINT
        ),
        "expected_acquisition_run_fingerprint": EXPECTED_ACQUISITION_RUN_FINGERPRINT,
        "expected_corpus_fingerprint": EXPECTED_CORPUS_FINGERPRINT,
        "expected_raw_provider_records": EXPECTED_RAW_PROVIDER_RECORDS,
        "expected_normalized_articles": EXPECTED_NORMALIZED_ARTICLES,
        "expected_failed_partitions": list(EXPECTED_FAILED_PARTITIONS),
        "expected_chronology_anomalies": list(EXPECTED_CHRONOLOGY_ANOMALIES),
        "chronology_disposition": {
            "provider_fields_preserved_unchanged": True,
            "generic_tolerance_seconds": None,
            "unexpected_additional_anomaly_policy": "FAIL_CLOSED",
            "changed_expected_anomaly_policy": "FAIL_CLOSED",
            "effective_pit_available_at": EFFECTIVE_PIT_POLICY,
            "rule": "MAX(CREATED_AT,UPDATED_AT)",
            "reason": (
                "FINAL_RETRIEVED_TEXT_MUST_NOT_BE_MADE_AVAILABLE_BEFORE_EITHER_"
                "PROVIDER_TIMESTAMP"
            ),
        },
        "authority": {
            "source_integrity_acceptance_only": True,
            "source_mutation": False,
            "provider_calls": False,
            "predictor_generation": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    payload["fingerprint"] = _canonical_hash(payload)
    return payload


HISTORICAL_NEWS_V1_SOURCE_INTEGRITY_V2_FINGERPRINT: str = str(
    source_integrity_v2_manifest()["fingerprint"]
)


def _expected_v1_partition_errors(month: str) -> list[str]:
    if month == "2015-07":
        return [
            "3 raw provider records have updated_at before created_at",
            "3 normalized rows have updated_at before created_at",
        ]
    if month == "2026-08":
        return [
            "1 raw provider records have updated_at before created_at",
            "1 normalized rows have updated_at before created_at",
        ]
    return []


def _anomaly_identity(item: dict[str, object]) -> dict[str, str]:
    return {
        "month": str(item.get("month") or ""),
        "article_id": str(item.get("article_id") or ""),
        "provider_record_sha256": str(item.get("provider_record_sha256") or ""),
        "created_at_utc": _utc_text(item.get("created_at")),
        "updated_at_utc": _utc_text(item.get("updated_at")),
    }


def run_historical_news_v1_source_integrity_v2(
    settings: AtlasSettings,
    *,
    workers: int = 4,
    progress: Callable[[str], None] | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    errors: list[str] = []

    parent_output = settings.resolved_path(
        "data/news/manifests/alpaca/historical_news_v1_closeout_v1_recheck.json"
    )
    parent = run_historical_news_v1_closeout(
        settings,
        workers=workers,
        output_path=parent_output,
        progress=progress,
    )

    if parent.get("corpus_fingerprint") != EXPECTED_CORPUS_FINGERPRINT:
        errors.append("corpus fingerprint changed from the diagnosed corpus")
    if int(parent.get("raw_provider_records", -1)) != EXPECTED_RAW_PROVIDER_RECORDS:
        errors.append("raw provider-record total changed")
    if int(parent.get("normalized_articles", -1)) != EXPECTED_NORMALIZED_ARTICLES:
        errors.append("normalized article total changed")

    failed_partitions = tuple(sorted(str(x) for x in parent.get("failed_partitions", [])))
    if failed_partitions != EXPECTED_FAILED_PARTITIONS:
        errors.append(
            "V1 failed partitions differ from the frozen chronology-anomaly set"
        )

    parent_errors = [str(value) for value in parent.get("errors", [])]
    if parent_errors != ["2 monthly partitions failed integrity checks"]:
        errors.append("V1 closeout has failures beyond the frozen chronology anomalies")

    partition_reports = {
        str(item.get("month")): item
        for item in parent.get("partition_reports", [])
        if isinstance(item, dict)
    }
    for month in EXPECTED_FAILED_PARTITIONS:
        actual = sorted(
            str(value)
            for value in partition_reports.get(month, {}).get("errors", [])
        )
        expected = sorted(_expected_v1_partition_errors(month))
        if actual != expected:
            errors.append(f"{month}: V1 partition errors changed")

    for month, item in partition_reports.items():
        if month in EXPECTED_FAILED_PARTITIONS:
            continue
        if item.get("status") != "PASS" or item.get("errors"):
            errors.append(f"{month}: unexpected non-chronology V1 failure")

    diagnostic = run_historical_news_v1_chronology_diagnostic(
        settings,
        months=set(EXPECTED_FAILED_PARTITIONS),
    )
    if int(diagnostic.get("anomaly_count", -1)) != len(EXPECTED_CHRONOLOGY_ANOMALIES):
        errors.append("chronology anomaly count changed")
    if diagnostic.get("all_raw_records_found") is not True:
        errors.append("not all chronology anomalies bind to raw provider records")
    if diagnostic.get("all_raw_normalized_hashes_match") is not True:
        errors.append("chronology anomaly raw/normalized hash binding failed")
    if diagnostic.get("all_pit_equals_updated") is not True:
        errors.append("stored V1 PIT no longer equals provider updated_at")
    if diagnostic.get("all_pit_before_created") is not True:
        errors.append("frozen chronology anomaly shape changed")

    observed = sorted(
        (_anomaly_identity(item) for item in diagnostic.get("anomalies", [])),
        key=lambda item: (
            item["month"],
            item["article_id"],
            item["provider_record_sha256"],
        ),
    )
    expected = sorted(
        (dict(item) for item in EXPECTED_CHRONOLOGY_ANOMALIES),
        key=lambda item: (
            item["month"],
            item["article_id"],
            item["provider_record_sha256"],
        ),
    )
    if observed != expected:
        errors.append("chronology anomaly identity/hash/timestamps changed")

    corrections: list[dict[str, object]] = []
    for item in diagnostic.get("anomalies", []):
        created = _parse_timestamp(item.get("created_at"))
        updated = _parse_timestamp(item.get("updated_at"))
        if created is None or updated is None:
            errors.append("chronology anomaly is missing required timestamps")
            continue
        effective = effective_pit_available_at(created, updated)
        if effective < created or effective < updated:
            errors.append("effective PIT policy is not conservative")
        corrections.append(
            {
                "month": str(item.get("month") or ""),
                "article_id": str(item.get("article_id") or ""),
                "provider_record_sha256": str(
                    item.get("provider_record_sha256") or ""
                ),
                "stored_pit_available_at": _utc_text(item.get("pit_available_at")),
                "effective_pit_available_at": (
                    effective.astimezone(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                ),
                "forward_adjustment_seconds": (
                    effective - updated
                ).total_seconds(),
            }
        )
    corrections.sort(
        key=lambda item: (str(item["month"]), str(item["article_id"]))
    )

    report: dict[str, object] = {
        "status": "PASS" if not errors else "FAIL",
        "contract": SOURCE_INTEGRITY_V2_CONTRACT,
        "contract_fingerprint": HISTORICAL_NEWS_V1_SOURCE_INTEGRITY_V2_FINGERPRINT,
        "parent_closeout_contract": CLOSEOUT_CONTRACT,
        "parent_closeout_contract_fingerprint": (
            HISTORICAL_NEWS_V1_CLOSEOUT_CONTRACT_FINGERPRINT
        ),
        "parent_closeout_status": parent.get("status"),
        "parent_closeout_fingerprint": parent.get("closeout_fingerprint"),
        "acquisition_run_fingerprint": parent.get("acquisition_run_fingerprint"),
        "corpus_fingerprint": parent.get("corpus_fingerprint"),
        "raw_provider_records": parent.get("raw_provider_records"),
        "normalized_articles": parent.get("normalized_articles"),
        "global_normalized": parent.get("global_normalized"),
        "failed_partitions_under_v1": list(failed_partitions),
        "chronology_anomalies": diagnostic.get("anomalies", []),
        "effective_pit_policy": EFFECTIVE_PIT_POLICY,
        "effective_pit_corrections": corrections,
        "errors": errors,
        "authority": {
            "source_integrity_accepted": not errors,
            "source_integrity_acceptance_only": True,
            "source_mutation": False,
            "provider_calls": False,
            "predictor_generation": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    report["acceptance_fingerprint"] = _canonical_hash(report)

    final_output = output_path or settings.resolved_path(
        "data/news/manifests/alpaca/"
        "historical_news_v1_source_integrity_v2.json"
    )
    _atomic_write_json(final_output, report)
    return report
