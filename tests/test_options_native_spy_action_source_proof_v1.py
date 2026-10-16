from __future__ import annotations

from datetime import date
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from packages.data.alpaca_v2_acquisition import _extract_action_records
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data import options_native_spy_action_source_proof_v1 as proof
from packages.data import options_native_stock_input_review_v1 as review
from test_options_native_stock_input_review_v1 import source, reseal, write_json


def fixture_archive(tmp_path, pages):
    """Construct invented original provider pages and matching original ledger."""
    rows = []
    compressed = bytearray()
    receipts = []
    for number, page in enumerate(pages):
        raw = json.dumps(page, sort_keys=True, separators=(",", ":")).encode()
        compressed.extend(gzip.compress(raw, mtime=0))
        receipts.append({"sha256": hashlib.sha256(raw).hexdigest(),
                         "uncompressed_bytes": len(raw)})
        rows.extend(_extract_action_records(page, number))
    bundle = tmp_path / "complete_pages.concat.json.gz"
    ledger = tmp_path / "native_actions.jsonl.gz"
    bundle.write_bytes(bytes(compressed))
    ledger.write_bytes(gzip.compress(("\n".join(json.dumps(r) for r in rows) + "\n").encode(), mtime=0))
    manifest = {"pages": receipts, "page_count": len(pages), "action_record_count": len(rows),
                "raw_bundle": {"member_count": len(pages)}}
    return manifest, ledger, bundle


def test_two_original_gzip_pages_reconcile_every_record_and_preserve_revision_candidates(tmp_path):
    pages = [
        {"corporate_actions": {"cash_dividends": [
            {"symbol": "SPY", "ex_date": "2019-12-20", "rate": 1.569992},
            {"symbol": "ABC", "ex_date": "2019-12-20", "rate": 0.5}]}},
        {"corporate_actions": {"cash_dividends": [
            {"symbol": "SPY", "ex_date": "2019-12-20", "rate": 1.57},
            {"symbol": "SPY", "ex_date": "2020-03-20", "rate": 1.4}],
            "reorganizations": [{"old_symbol": "SPY", "new_symbol": "SPY"}]}},
    ]
    manifest, ledger, bundle = fixture_archive(tmp_path, pages)
    result = proof.reconcile_raw_actions(manifest, ledger, bundle)
    assert result["verified_raw_pages"] == 2
    assert result["reconciled_native_records"] == 5
    assert [r["payload"]["rate"] for r in result["prior_window_selection"]] == [1.569992, 1.57]
    assert len(result["expanded_record_selection"]) == 4
    assert result["expanded_record_selection"][-1]["effective_date_state"] == "UNKNOWN_EFFECTIVE_DATE"
    assert all(r["historical_available_at_utc"] is None and r["point_in_time_qualified"] is False
               for r in result["expanded_record_selection"])


def test_empty_spy_candidates_never_substitute_no_action_proof(tmp_path):
    manifest, ledger, bundle = fixture_archive(tmp_path, [
        {"corporate_actions": {"cash_dividends": [{"symbol": "XYZ", "ex_date": "2019-12-20"}]}}
    ])
    result = proof.reconcile_raw_actions(manifest, ledger, bundle)
    assert result["expanded_record_selection"] == []
    assert result["verified_raw_pages"] == 1


@pytest.mark.parametrize("fault", [
    "source_sha", "wrong_bytes", "missing_member", "extra_member", "truncated_gzip",
    "unmatching_ledger", "missing_ledger", "extra_ledger", "invalid_json",
    "invalid_spy_date", "inflated_page_bound", "expanded_total_bound",
    "native_gzip_corrupt", "malformed_receipt",
])
def test_all_raw_source_faults_fail_closed(tmp_path, monkeypatch, fault):
    pages = [{"corporate_actions": {"cash_dividends": [
        {"symbol": "SPY", "ex_date": "2019-12-20", "rate": "1.25"}]}}]
    manifest, ledger, bundle = fixture_archive(tmp_path, pages)
    if fault == "source_sha":
        manifest["pages"][0]["sha256"] = "0" * 64
    elif fault == "wrong_bytes":
        manifest["pages"][0]["uncompressed_bytes"] += 1
    elif fault == "missing_member":
        bundle.write_bytes(b"")
    elif fault == "extra_member":
        bundle.write_bytes(bundle.read_bytes() + bundle.read_bytes())
    elif fault == "truncated_gzip":
        bundle.write_bytes(bundle.read_bytes()[:-4])
    elif fault == "unmatching_ledger":
        altered = [{"action_type": "cash_dividends", "source_page_index": 0,
                    "source_record_index": 0,
                    "payload": {"symbol": "SPY", "ex_date": "2019-12-20", "rate": "2.00"}}]
        ledger.write_bytes(gzip.compress((json.dumps(altered[0]) + "\n").encode(), mtime=0))
    elif fault == "missing_ledger":
        ledger.write_bytes(gzip.compress(b"", mtime=0))
    elif fault == "extra_ledger":
        ledger.write_bytes(gzip.compress(gzip.decompress(ledger.read_bytes()) * 2, mtime=0))
    elif fault == "invalid_json":
        body = b"{bad json"
        bundle.write_bytes(gzip.compress(body, mtime=0))
        manifest["pages"][0] = {"sha256": hashlib.sha256(body).hexdigest(), "uncompressed_bytes": len(body)}
    elif fault == "invalid_spy_date":
        pages[0]["corporate_actions"]["cash_dividends"][0]["ex_date"] = "tomorrow"
        manifest, ledger, bundle = fixture_archive(tmp_path, pages)
    elif fault == "inflated_page_bound":
        monkeypatch.setattr(proof, "MAX_PAGE_BYTES", 2)
    elif fault == "expanded_total_bound":
        monkeypatch.setattr(proof, "MAX_ACTION_EXPANDED", 2)
    elif fault == "native_gzip_corrupt":
        ledger.write_bytes(ledger.read_bytes()[:-4])
    elif fault == "malformed_receipt":
        manifest["pages"][0]["sha256"] = "bad"
    with pytest.raises((ValueError, OSError, EOFError)):
        proof.reconcile_raw_actions(manifest, ledger, bundle)


def test_original_source_proof_reuses_review_without_any_bar_rereads(source):
    # The pre-existing fixture uses one "fixture" raw-page action container.
    # Align its invented ledger label with the actual raw payload before sealing.
    for row in source["actions"]:
        row["action_type"] = "fixture"
    reseal(source)
    report = review.review_options_native_stock_inputs(source["settings"], binding=source["binding"])
    output = source["settings"].project_root / "data/research/options_native_stock_input_review_v1/fixture.json"
    write_json(output, report)
    binding = proof.StockReviewBinding(
        path=output.relative_to(source["settings"].project_root).as_posix(),
        fingerprint=report["report_fingerprint"],
        retained_packet_fingerprint=source["binding"].report_fingerprint,
    )
    for _, path, _ in source["units"]:
        path.unlink(missing_ok=True)
    result = proof.build_spy_action_source_proof(source["settings"], binding=binding)
    assert result["scanned_page_count"] == 1
    assert result["reconciled_action_records"] == 4
    assert result["original_prior_window_candidates_reconciled"] == 2
    assert len(result["spy_action_candidates"]) == 3
    assert result["source_scans"]["daily_units"] == result["source_scans"]["minute_units"] == 0
    assert result["historical_pit_publication_qualified"] is False
    assert result["economic_log_returns"] is result["forecast_total_variance"] is None
    assert result["pilot_input_acceptance"] is False
    assert result["report_fingerprint"] == _fingerprint(
        {k: v for k, v in result.items() if k != "report_fingerprint"}
    )


def test_resigned_stock_report_will_not_gain_forecast_authority(source):
    for row in source["actions"]:
        row["action_type"] = "fixture"
    reseal(source)
    report = review.review_options_native_stock_inputs(source["settings"], binding=source["binding"])
    report["pilot_input_acceptance"] = True
    report["report_fingerprint"] = _fingerprint(
        {k: v for k, v in report.items() if k != "report_fingerprint"}
    )
    path = source["settings"].project_root / "data/research/options_native_stock_input_review_v1/fixture.json"
    write_json(path, report)
    binding = proof.StockReviewBinding(
        path.relative_to(source["settings"].project_root).as_posix(),
        report["report_fingerprint"],
        source["binding"].report_fingerprint,
    )
    with pytest.raises(proof.ActionSourceProofError, match="scope or authority"):
        proof.build_spy_action_source_proof(source["settings"], binding=binding)


def test_reconciler_rejects_duplicate_source_member_even_with_convenient_ledger(tmp_path):
    page = {"corporate_actions": {"cash_dividends": [{"symbol": "SPY", "ex_date": "2019-12-20"}]}}
    manifest, ledger, bundle = fixture_archive(tmp_path, [page])
    manifest["page_count"] = 2
    manifest["raw_bundle"]["member_count"] = 2
    manifest["pages"].append(dict(manifest["pages"][0]))
    manifest["action_record_count"] = 2
    bundle.write_bytes(bundle.read_bytes() * 2)
    ledger.write_bytes(gzip.compress(gzip.decompress(ledger.read_bytes()) * 2, mtime=0))
    with pytest.raises(ValueError, match="native action"):
        proof.reconcile_raw_actions(manifest, ledger, bundle)
