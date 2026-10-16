from __future__ import annotations

"""Source-only SPY action-page/ledger reconciliation for the frozen 2020 pilot.

Neither the raw corporate-action archive nor recorded effective dates establish
when an event became knowable in 2019/2020. Never infer adjusted returns here.
"""

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterator
import zlib

from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_acquisition import _extract_action_records
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import _action_symbols
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_pilot_input_packet_v1 import FEATURE_CUTOFF
from packages.data.options_native_stock_input_review_v1 import (
    CONTRACT as STOCK_REVIEW_CONTRACT,
    MAX_ACTION_COMPRESSED,
    MAX_ACTION_EXPANDED,
    MAX_METADATA,
    _file,
    _gzip_records,
    _json,
)
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-options-native-spy-action-source-proof-v1"
MAX_REVIEW_BYTES = 512 * 1024
MAX_PAGE_BYTES = 32 * 1024 * 1024
MAX_PAGES = 10000
MAX_SELECTED = 256
START = date(2019, 10, 1)
END = date(2020, 3, 31)
PRIOR_START = date(2019, 12, 4)
PRIOR_END = date(2020, 1, 3)


class ActionSourceProofError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StockReviewBinding:
    path: str = "data/research/options_native_stock_input_review_v1/9caee69b5d0fc180.json"
    fingerprint: str = "9caee69b5d0fc18075451f7b4b8c46ec3c8db817d4b0b0d3ed311bf9712748e7"
    retained_packet_fingerprint: str = "92c4d71997ec3225d5040f00375fc4ad66d654be6ce4a6cb81136a87d75374dc"


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ActionSourceProofError(reason)


def _json_bytes(raw: bytes) -> Any:
    def reject_constant(value: str) -> None:
        raise ActionSourceProofError("nonfinite JSON constant in source")
    return json.loads(raw, parse_constant=reject_constant)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False)


def _gzip_members(path: Path) -> Iterator[bytes]:
    """Read each concatenated original gzip member separately, within hard bounds."""
    pending = b""
    total = 0
    with path.open("rb") as handle:
        while True:
            if not pending:
                pending = handle.read(65536)
            if not pending:
                return
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
            body = bytearray()
            while not decoder.eof:
                if not pending:
                    pending = handle.read(65536)
                _require(bool(pending), "truncated original corporate-action gzip member")
                allowed = MAX_PAGE_BYTES + 1 - len(body)
                _require(allowed > 0, "original corporate-action page exceeds byte bound")
                piece = decoder.decompress(pending, allowed)
                body.extend(piece)
                total += len(piece)
                _require(len(body) <= MAX_PAGE_BYTES and total <= MAX_ACTION_EXPANDED,
                         "original corporate-action expansion exceeds byte bound")
                pending = decoder.unconsumed_tail or decoder.unused_data
            _require(not decoder.unconsumed_tail, "original gzip member has unconsumed compressed bytes")
            _require(not decoder.flush(), "original gzip member retained unexpected unflushed bytes")
            yield bytes(body)


def _event_dates(record: dict[str, Any]) -> list[date]:
    payload = record["payload"]
    dates: list[date] = []
    for key in ("ex_date", "effective_date", "execution_date"):
        value = payload.get(key)
        if value is None:
            continue
        _require(isinstance(value, str), f"SPY {key} is not an ISO date")
        try:
            dates.append(date.fromisoformat(value))
        except ValueError as exc:
            raise ActionSourceProofError(f"SPY {key} is malformed") from exc
    return dates


def _project(record: dict[str, Any], page_sha: str, lo: date, hi: date) -> dict[str, Any] | None:
    payload = record["payload"]
    if "SPY" not in _action_symbols(payload):
        return None
    dates = _event_dates(record)
    if dates and not any(lo <= day <= hi for day in dates):
        return None
    return {
        "action_type": record["action_type"],
        "source_page_index": record["source_page_index"],
        "source_record_index": record["source_record_index"],
        "manifest_recorded_source_page_sha256": page_sha,
        "payload": payload,
        "effective_date_state": "RECORDED_DATES_REQUIRE_TYPE_SPECIFIC_REVIEW" if dates else "UNKNOWN_EFFECTIVE_DATE",
        "historical_available_at_utc": None,
        "point_in_time_qualified": False,
    }


def reconcile_raw_actions(
    manifest: dict[str, Any], ledger: Path, bundle: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Compare every original decoded page record against exact native ledger order."""
    pages = manifest.get("pages")
    _require(isinstance(pages, list) and 1 <= len(pages) <= MAX_PAGES
             and len(pages) == manifest.get("page_count"), "source page count invalid")
    _require(manifest.get("raw_bundle", {}).get("member_count") == len(pages),
             "original gzip member count is not the accepted page count")
    native = iter(_gzip_records(ledger))
    selected: list[dict[str, Any]] = []
    old_window: list[dict[str, Any]] = []
    total = 0
    observed_pages = 0
    try:
        for page_index, body in enumerate(_gzip_members(bundle)):
            _require(page_index < len(pages), "unlisted original gzip page")
            receipt = pages[page_index]
            _require(isinstance(receipt, dict), "malformed action-page receipt")
            expected_sha = receipt.get("sha256")
            _require(isinstance(expected_sha, str) and len(expected_sha) == 64
                     and all(c in "0123456789abcdef" for c in expected_sha),
                     "invalid original action-page digest")
            _require(hashlib.sha256(body).hexdigest() == expected_sha,
                     f"original action-page {page_index} digest mismatch")
            if receipt.get("uncompressed_bytes") is not None:
                _require(type(receipt["uncompressed_bytes"]) is int
                         and receipt["uncompressed_bytes"] == len(body),
                         "original action-page byte count changed")
            raw_page = _json_bytes(body)
            _require(isinstance(raw_page, dict), "original action page must be a JSON object")
            source_rows = _extract_action_records(raw_page, page_index)
            for row in source_rows:
                try:
                    next_record = next(native)
                except StopIteration as exc:
                    raise ActionSourceProofError("native ledger shorter than original pages") from exc
                _require(_canonical(next_record) == _canonical(row),
                         f"native action does not match original page {page_index}, ordinal {total}")
                total += 1
                candidate = _project(row, expected_sha, START, END)
                if candidate is not None:
                    selected.append(candidate)
                    _require(len(selected) <= MAX_SELECTED, "SPY action projection exceeds count bound")
                previous = _project(row, expected_sha, PRIOR_START, PRIOR_END)
                if previous is not None:
                    old_window.append(previous)
                    _require(len(old_window) <= MAX_SELECTED, "prior-window action projection exceeds count bound")
            observed_pages += 1
            if progress is not None and observed_pages % 50 == 0:
                progress(f"original pages checked {observed_pages}/{len(pages)}; ledger records {total}")
        _require(observed_pages == len(pages), "original gzip page count incomplete")
        _require(next(native, None) is None, "native ledger longer than original pages")
        _require(total == manifest.get("action_record_count"), "accepted action population disagrees with raw pages")
    except (OSError, EOFError, zlib.error, UnicodeError, json.JSONDecodeError) as exc:
        raise ActionSourceProofError("corrupt original action page or native gzip/JSON stream") from exc
    return {
        "verified_raw_pages": observed_pages,
        "reconciled_native_records": total,
        "expanded_record_selection": selected,
        "prior_window_selection": old_window,
        "all_raw_pages_matched_native_ledger": True,
    }


def build_spy_action_source_proof(
    settings: AtlasSettings,
    *,
    binding: StockReviewBinding = StockReviewBinding(),
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Reuse the original uploaded stock review; no stock bar or option reads."""
    path = settings.resolved_path(binding.path)
    _require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_REVIEW_BYTES,
             "pinned cached-stock report missing, linked or oversized")
    review = _json_bytes(path.read_bytes())
    _require(isinstance(review, dict)
             and _fingerprint({k: v for k, v in review.items() if k != "report_fingerprint"}) == binding.fingerprint
             and review.get("report_fingerprint") == binding.fingerprint,
             "pinned cached-stock review fingerprint drifted")
    required = {
        "contract": STOCK_REVIEW_CONTRACT,
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "feature_cutoff_utc": FEATURE_CUTOFF.isoformat(),
        "retained_packet_fingerprint": binding.retained_packet_fingerprint,
        "economic_log_returns": None,
        "forecast_total_variance": None,
        "pilot_input_acceptance": False,
        "requested_minute_observations": 22,
        "present_minute_observations": 22,
        "missing_minute_clocks": [],
    }
    _require(all(review.get(k) == v for k, v in required.items()),
             "retained stock input scope or authority drifted")
    _require(review.get("authority") == dict(AUTHORITY) | {"raw_source_scans": 3},
             "retained stock input authority changed")
    old_action = review.get("corporate_actions")
    _require(isinstance(old_action, dict) and old_action.get("historical_publication_qualified") is False,
             "retained corporate-action publication authority changed")
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    snapshot, snap_receipt = _json(layout, layout.manifests / "source_snapshot.json",
                                   old_action["source_snapshot_sha256"])
    manifest, manifest_receipt = _json(layout, layout.manifests / "corporate_actions.json",
                                       old_action["action_manifest_sha256"])
    _require(manifest.get("native_actions") == snapshot.get("corporate_actions_native")
             and manifest.get("raw_bundle") == snapshot.get("corporate_actions_raw_bundle")
             and manifest.get("page_count") == snapshot.get("corporate_action_page_count")
             and manifest.get("action_record_count") == snapshot.get("corporate_action_record_count")
             == old_action["cached_record_count"],
             "accepted source snapshot or manifest differs from the retained review")
    ledger = layout.corporate_actions / "native_actions.jsonl.gz"
    bundle = layout.source / "corporate_actions" / "complete_pages.concat.json.gz"
    for key, target, expected in (
        ("native_actions", ledger, old_action["native_actions_sha256"]),
        ("raw_bundle", bundle, old_action["raw_bundle_sha256"]),
    ):
        _require(Path(str(manifest[key].get("path"))).absolute() == target.absolute()
                 and manifest[key].get("sha256") == expected,
                 f"original {key} binding differs from inspected report")
        _file(layout, target, MAX_ACTION_COMPRESSED, expected)
    if progress:
        progress("stock packet reused; verifying original action pages against full native action ledger")
    matched = reconcile_raw_actions(manifest, ledger, bundle, progress=progress)
    _require(matched["prior_window_selection"] == old_action["selected_spy_records"],
             "original raw-page SPY projection disagrees with retained stock review")
    output = {
        "contract": CONTRACT,
        "status": "COMPLETE_SOURCE_RECONCILIATION_WITH_AVAILABILITY_GAPS",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "prior_stock_review_fingerprint": binding.fingerprint,
        "prior_stock_review_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_snapshot_sha256": snap_receipt["sha256"],
        "action_manifest_sha256": manifest_receipt["sha256"],
        "native_actions_sha256": old_action["native_actions_sha256"],
        "raw_bundle_sha256": old_action["raw_bundle_sha256"],
        "scanned_page_count": matched["verified_raw_pages"],
        "reconciled_action_records": matched["reconciled_native_records"],
        "date_window": [START.isoformat(), END.isoformat()],
        "spy_action_candidates": matched["expanded_record_selection"],
        "original_prior_window_candidates_reconciled": len(matched["prior_window_selection"]),
        "source_page_hashes_verified": True,
        "native_ledger_exactly_matches_original_pages": True,
        "historical_pit_publication_qualified": False,
        "action_effective_date_coverage_qualified": False,
        "undated_candidates_dont_prove_coverage": True,
        "cash_dividend_history_is_not_price_adjustment_authority": True,
        "economic_log_returns": None,
        "forecast_total_variance": None,
        "pilot_input_acceptance": False,
        "source_scans": {"daily_units": 0, "minute_units": 0, "raw_option_histories": 0,
                         "native_action_ledger": 1, "original_action_bundle": 1},
        "authority": dict(AUTHORITY) | {"raw_source_scans": 2},
    }
    output["report_fingerprint"] = _fingerprint(output)
    return output
