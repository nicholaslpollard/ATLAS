from __future__ import annotations

from datetime import timezone
from pathlib import Path

import packages.data.historical_news_v1_source_integrity_v2 as module


class _Settings:
    def __init__(self, root: Path) -> None:
        self.root = root

    def resolved_path(self, value: str) -> Path:
        return self.root / value


def _parent_report() -> dict[str, object]:
    return {
        "status": "FAIL",
        "closeout_fingerprint": "parent-closeout",
        "acquisition_run_fingerprint": module.EXPECTED_ACQUISITION_RUN_FINGERPRINT,
        "corpus_fingerprint": module.EXPECTED_CORPUS_FINGERPRINT,
        "raw_provider_records": module.EXPECTED_RAW_PROVIDER_RECORDS,
        "normalized_articles": module.EXPECTED_NORMALIZED_ARTICLES,
        "global_normalized": {
            "row_count": module.EXPECTED_NORMALIZED_ARTICLES,
            "distinct_article_ids": module.EXPECTED_NORMALIZED_ARTICLES,
            "duplicate_article_id_rows": 0,
            "duplicate_article_id_samples": [],
        },
        "failed_partitions": ["2015-07", "2026-08"],
        "errors": ["2 monthly partitions failed integrity checks"],
        "partition_reports": [
            {
                "month": "2015-07",
                "status": "FAIL",
                "errors": [
                    "3 raw provider records have updated_at before created_at",
                    "3 normalized rows have updated_at before created_at",
                ],
            },
            {
                "month": "2026-08",
                "status": "FAIL",
                "errors": [
                    "1 raw provider records have updated_at before created_at",
                    "1 normalized rows have updated_at before created_at",
                ],
            },
        ],
    }


def _diagnostic_report() -> dict[str, object]:
    anomalies = []
    for expected in module.EXPECTED_CHRONOLOGY_ANOMALIES:
        anomalies.append(
            {
                "month": expected["month"],
                "article_id": expected["article_id"],
                "provider_record_sha256": expected["provider_record_sha256"],
                "created_at": expected["created_at_utc"],
                "updated_at": expected["updated_at_utc"],
                "pit_available_at": expected["updated_at_utc"],
            }
        )
    return {
        "status": "ANOMALIES_FOUND",
        "anomaly_count": 4,
        "all_raw_records_found": True,
        "all_raw_normalized_hashes_match": True,
        "all_pit_equals_updated": True,
        "all_pit_before_created": True,
        "anomalies": anomalies,
    }


def test_v2_contract_fingerprint_is_frozen_and_source_only() -> None:
    manifest = module.source_integrity_v2_manifest()

    assert (
        manifest["fingerprint"]
        == module.HISTORICAL_NEWS_V1_SOURCE_INTEGRITY_V2_FINGERPRINT
        == "2a2039ba8ca495f1ea04a7ffd0719ccb95021d48917098899c4d93e5599df632"
    )
    assert manifest["expected_corpus_fingerprint"] == module.EXPECTED_CORPUS_FINGERPRINT
    assert manifest["expected_failed_partitions"] == ["2015-07", "2026-08"]
    assert manifest["chronology_disposition"]["generic_tolerance_seconds"] is None
    assert (
        manifest["chronology_disposition"]["unexpected_additional_anomaly_policy"]
        == "FAIL_CLOSED"
    )
    authority = manifest["authority"]
    assert authority["source_integrity_acceptance_only"] is True
    assert authority["source_mutation"] is False
    assert authority["provider_calls"] is False
    assert authority["predictor_generation"] is False
    assert authority["strategy_outcome_access"] is False
    assert authority["paper_authority"] is False
    assert authority["live_authority"] is False


def test_effective_pit_uses_later_provider_timestamp() -> None:
    normal = module.effective_pit_available_at(
        "2026-08-17T15:55:31Z",
        "2026-08-17T15:56:00Z",
    )
    inverted = module.effective_pit_available_at(
        "2026-08-17T15:56:00Z",
        "2026-08-17T15:55:31Z",
    )

    assert (
        normal.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        == "2026-08-17T15:56:00Z"
    )
    assert (
        inverted.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        == "2026-08-17T15:56:00Z"
    )


def test_v2_accepts_only_exact_hash_bound_chronology_anomalies(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module,
        "run_historical_news_v1_closeout",
        lambda *_args, **_kwargs: _parent_report(),
    )
    requested_months: list[set[str] | None] = []

    def _diagnostic(*_args, months=None, **_kwargs):
        requested_months.append(months)
        return _diagnostic_report()

    monkeypatch.setattr(
        module,
        "run_historical_news_v1_chronology_diagnostic",
        _diagnostic,
    )

    report = module.run_historical_news_v1_source_integrity_v2(
        _Settings(tmp_path),
        workers=4,
    )

    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert requested_months == [{"2015-07", "2026-08"}]
    assert report["authority"]["source_integrity_accepted"] is True
    assert len(report["effective_pit_corrections"]) == 4
    assert [
        int(item["forward_adjustment_seconds"])
        for item in report["effective_pit_corrections"]
    ] == [18, 16, 1, 29]


def test_v2_fails_closed_if_a_provider_hash_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module,
        "run_historical_news_v1_closeout",
        lambda *_args, **_kwargs: _parent_report(),
    )
    diagnostic = _diagnostic_report()
    anomalies = diagnostic["anomalies"]
    assert isinstance(anomalies, list)
    anomalies[0] = dict(anomalies[0])
    anomalies[0]["provider_record_sha256"] = "0" * 64
    monkeypatch.setattr(
        module,
        "run_historical_news_v1_chronology_diagnostic",
        lambda *_args, **_kwargs: diagnostic,
    )

    report = module.run_historical_news_v1_source_integrity_v2(
        _Settings(tmp_path),
        workers=4,
    )

    assert report["status"] == "FAIL"
    assert report["authority"]["source_integrity_accepted"] is False
    assert "chronology anomaly identity/hash/timestamps changed" in report["errors"]
