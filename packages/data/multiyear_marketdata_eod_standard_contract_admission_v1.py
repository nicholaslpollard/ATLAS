from __future__ import annotations

"""Causal EOD admission audit using already accepted MarketData chain evidence.

This module performs no provider requests and admits no historical trades. It
rechecks the exact historical chain receipt/body that supplied each selected OCC
symbol, freezes MarketData's documented default exclusion of non-standard
contracts, and measures two distinct source populations:

* causal entry-ready source shape: only facts available at the EOD entry snapshot;
* later exit-liquidity source shape: evaluated only at the later snapshot.

The provider-standard classification supports a 100-share *model assumption* for
an EOD scenario. It is not independent OCC deliverable/multiplier proof and does
not create historical execution or P&L authority.
"""

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    _fingerprint,
    _paths,
    _valid_receipt,
)
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import (
    CONTRACT as EOD_PROBE_CONTRACT,
)
from packages.data.multiyear_option_quote_bridge_v1 import (
    CONTRACT as SELECTION_CONTRACT,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    CONTRACT as HANDOFF_CONTRACT,
    _check_signature,
)
from packages.providers.marketdata_app.client import array_rows

CONTRACT = "atlas-multiyear-marketdata-eod-standard-contract-admission-v1"
OUTPUT_REL = (
    "data/options/derived/"
    "multiyear_marketdata_eod_standard_contract_admission_v1"
)
OCC = re.compile(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$")

PROVIDER_STANDARD_SEMANTICS = {
    "provider": "MarketData.app",
    "retrieved_on": "2026-10-01",
    "chain_docs": "https://www.marketdata.app/docs/api/options/chain/",
    "nonstandard_docs": (
        "https://www.marketdata.app/education/options/non-standard-options/"
    ),
    "documented_claims": {
        "historical_chain_is_end_of_day": True,
        "chain_nonstandard_parameter_defaults_false": True,
        "nonstandard_false_excludes_nonstandard_contracts": True,
        "nonstandard_contracts_include_adjusted_contracts_from_corporate_actions": True,
        "standard_equity_chain_uses_100_share_contract_model": True,
    },
}
PROVIDER_STANDARD_SEMANTICS_FINGERPRINT = _fingerprint(
    PROVIDER_STANDARD_SEMANTICS
)


class EodStandardContractAdmissionError(ValueError):
    pass


def _selected_chain_evidence(
    settings: AtlasSettings,
    selection_row: dict[str, Any],
    memo: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    identity = selection_row.get("source_request_identity")
    if not isinstance(identity, str) or len(identity) != 64:
        raise EodStandardContractAdmissionError(
            "selected chain request identity is invalid"
        )
    if identity not in memo:
        paths = _paths(settings, identity)
        if (
            paths.receipt.is_symlink()
            or paths.body.is_symlink()
            or not paths.receipt.is_file()
            or not paths.body.is_file()
        ):
            raise EodStandardContractAdmissionError(
                "selected chain receipt/body is unavailable"
            )
        receipt = _read_object(paths.receipt)
        try:
            params = receipt["params"]
            endpoint = receipt["endpoint"]
            ticker = selection_row["ticker"]
            if (
                receipt.get("request_identity") != identity
                or endpoint != f"options/chain/{ticker}/"
                or not isinstance(params, dict)
                or set(params) != {"date", "expiration", "strike"}
                or params.get("expiration") != selection_row["expiration"]
            ):
                raise EodStandardContractAdmissionError(
                    "selected chain request semantics changed"
                )
            request = {
                "request_identity": identity,
                "ticker": ticker,
                "endpoint": endpoint,
                "params": params,
                "bounded_query": True,
            }
            valid = _valid_receipt(paths, request)
            if valid is None or valid.get("status") != "COMPLETE":
                raise EodStandardContractAdmissionError(
                    "selected chain source is not a complete verified receipt"
                )
            raw = paths.body.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
            rows = array_rows(payload)
            symbols = {
                str(row.get("optionSymbol"))
                for row in rows
                if isinstance(row.get("optionSymbol"), str)
            }
            memo[identity] = {
                "request_identity": identity,
                "body_sha256": valid["body_sha256"],
                "snapshot_date": params["date"],
                "expiration": params["expiration"],
                "strike_window": params["strike"],
                "nonstandard_parameter_present": False,
                "provider_default_nonstandard_false_applies": True,
                "provider_standard_chain_classification": True,
                "symbols": symbols,
            }
        except (
            OSError, ValueError, TypeError, KeyError, RuntimeError,
            json.JSONDecodeError,
        ) as exc:
            if isinstance(exc, EodStandardContractAdmissionError):
                raise
            raise EodStandardContractAdmissionError(
                "selected chain source cannot be reverified"
            ) from exc

    evidence = memo[identity]
    symbol = selection_row.get("option_symbol")
    match = OCC.fullmatch(symbol) if isinstance(symbol, str) else None
    expected_right = "C" if selection_row.get("right") == "call" else "P"
    if (
        match is None
        or match.group(1) != selection_row.get("ticker")
        or match.group(3) != expected_right
        or symbol not in evidence["symbols"]
        or evidence["body_sha256"] != selection_row.get("source_body_sha256")
    ):
        raise EodStandardContractAdmissionError(
            "selected OCC identity no longer matches verified standard-filter chain"
        )
    return {
        key: value
        for key, value in evidence.items()
        if key != "symbols"
    }


def local_standard_chain_verifier(
    settings: AtlasSettings,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a memoized zero-provider verifier for selected physical chains."""
    settings.assert_external_storage_binding("options")
    memo: dict[str, dict[str, Any]] = {}

    def verify(selection_row: dict[str, Any]) -> dict[str, Any]:
        return _selected_chain_evidence(settings, selection_row, memo)

    return verify


def _entry_shape(row: dict[str, Any]) -> bool:
    entry = row["entry"]
    return bool(
        entry.get("documented_same_row_stock_option_snapshot")
        and entry.get("updated_is_1600_et")
        and entry.get("two_sided")
        and entry.get("positive_displayed_size")
        and entry.get("positive_reported_volume")
    )


def _exit_shape(row: dict[str, Any]) -> bool:
    exit_row = row["exit"]
    return bool(
        exit_row.get("documented_same_row_stock_option_snapshot")
        and exit_row.get("updated_is_1600_et")
        and exit_row.get("two_sided")
        and exit_row.get("positive_displayed_size")
        and exit_row.get("positive_reported_volume")
        and row.get("forced_exit_strictly_before_expiry_candidate")
    )


def build_eod_standard_contract_admission_audit(
    selection: dict[str, Any],
    handoff: dict[str, Any],
    eod_probe: dict[str, Any],
    *,
    verify_standard_chain: Callable[[dict[str, Any]], dict[str, Any]],
    expected_original_cases: int = 14902,
) -> dict[str, Any]:
    """Measure causal EOD admission shape without using future exit data at entry."""
    for doc, field in (
        (selection, "selection_fingerprint"),
        (handoff, "handoff_fingerprint"),
        (eod_probe, "probe_fingerprint"),
    ):
        _check_signature(doc, field)

    if (
        selection.get("contract") != SELECTION_CONTRACT
        or handoff.get("contract") != HANDOFF_CONTRACT
        or eod_probe.get("contract") != EOD_PROBE_CONTRACT
        or handoff.get("selection_fingerprint")
            != selection["selection_fingerprint"]
        or eod_probe.get("source_handoff_fingerprint")
            != handoff["handoff_fingerprint"]
        or selection.get("original_case_denominator") != expected_original_cases
        or selection.get("original_right_memberships")
            != expected_original_cases * 2
        or handoff.get("original_case_denominator") != expected_original_cases
        or handoff.get("original_right_memberships")
            != expected_original_cases * 2
        or eod_probe.get("original_case_denominator") != expected_original_cases
        or eod_probe.get("original_right_memberships")
            != expected_original_cases * 2
        or selection.get("provider_requests") != 0
        or handoff.get("provider_requests") != 0
        or eod_probe.get("provider_requests") != 0
        or eod_probe.get("historical_option_trades_admitted") != 0
        or eod_probe.get("historical_account_pnl_authority") is not False
    ):
        raise EodStandardContractAdmissionError(
            "source lineage, denominator or authority changed"
        )

    selected = {
        row["case_id"]: row for row in selection.get("cases", [])
    }
    if len(selected) != selection.get("selected_case_right_memberships"):
        raise EodStandardContractAdmissionError(
            "selected case/right identities are not unique"
        )
    probe_rows = eod_probe.get("rows")
    if (
        not isinstance(probe_rows, list)
        or len(probe_rows) != eod_probe.get("dated_pair_work_items")
    ):
        raise EodStandardContractAdmissionError("EOD probe denominator changed")

    counts: Counter[str] = Counter()
    by_year = {
        str(year): Counter() for year in range(2021, 2027)
    }
    output_rows: list[dict[str, Any]] = []
    verified_chain_ids: set[str] = set()

    for row in sorted(probe_rows, key=lambda item: item["case_right_id"]):
        case_right_id = row["case_right_id"]
        source = selected.get(case_right_id)
        if source is None:
            raise EodStandardContractAdmissionError(
                "dated EOD row lost selected chain lineage"
            )
        if (
            source.get("option_symbol") != row.get("option_symbol")
            or source.get("ticker") != row.get("ticker")
            or source.get("right") != row.get("right")
            or str(source.get("decision_at_utc", "")) == ""
        ):
            raise EodStandardContractAdmissionError(
                "selected chain and EOD probe identity differ"
            )

        standard = verify_standard_chain(source)
        if standard.get("provider_standard_chain_classification") is not True:
            raise EodStandardContractAdmissionError(
                "selected chain verifier did not prove standard-filter source"
            )
        verified_chain_ids.add(standard["request_identity"])

        entry_ready = _entry_shape(row)
        exit_ready = _exit_shape(row)
        provider_standard = True
        causal_entry_ready = entry_ready and provider_standard
        later_exit_ready = exit_ready and provider_standard
        both_ready = causal_entry_ready and later_exit_ready

        year = str(row["year"])
        if year not in by_year:
            raise EodStandardContractAdmissionError("unexpected signal year")

        counts["DATED_RIGHTS"] += 1
        counts["PROVIDER_STANDARD_AT_SELECTION"] += provider_standard
        counts["ENTRY_EOD_CLOCK_LIQUIDITY_SOURCE_SHAPE"] += entry_ready
        counts["LATER_EXIT_EOD_CLOCK_LIQUIDITY_SOURCE_SHAPE"] += exit_ready
        counts["CAUSAL_ENTRY_READY_MODEL_SOURCE_SHAPE"] += causal_entry_ready
        counts["ENTRY_AND_LATER_EXIT_MODEL_SOURCE_SHAPE"] += both_ready
        by_year[year]["DATED_RIGHTS"] += 1
        by_year[year]["PROVIDER_STANDARD_AT_SELECTION"] += provider_standard
        by_year[year][
            "CAUSAL_ENTRY_READY_MODEL_SOURCE_SHAPE"
        ] += causal_entry_ready
        by_year[year][
            "LATER_EXIT_EOD_CLOCK_LIQUIDITY_SOURCE_SHAPE"
        ] += later_exit_ready
        by_year[year][
            "ENTRY_AND_LATER_EXIT_MODEL_SOURCE_SHAPE"
        ] += both_ready

        output_rows.append({
            "case_right_id": case_right_id,
            "original_case_id": row["original_case_id"],
            "year": year,
            "right": row["right"],
            "ticker": row["ticker"],
            "option_symbol": row["option_symbol"],
            "decision_at_utc": source["decision_at_utc"],
            "selected_chain_request_identity":
                source["source_request_identity"],
            "selected_chain_body_sha256":
                source["source_body_sha256"],
            "selected_chain_snapshot_date":
                standard["snapshot_date"],
            "selected_chain_nonstandard_parameter_present":
                standard["nonstandard_parameter_present"],
            "provider_default_nonstandard_false_applies":
                standard["provider_default_nonstandard_false_applies"],
            "provider_standard_chain_classification": provider_standard,
            "provider_standard_100_share_model_multiplier": (
                100 if provider_standard else None
            ),
            "independent_occ_deliverable_multiplier_verified": False,
            "entry_source_shape_ready_without_future_exit": entry_ready,
            "causal_entry_ready_model_source_shape": causal_entry_ready,
            "later_exit_source_shape_ready": later_exit_ready,
            "entry_and_later_exit_model_source_shape": both_ready,
            "future_exit_used_for_entry_admission": False,
            "historical_trade_admitted": False,
            "historical_account_pnl_authority": False,
        })

    if counts["DATED_RIGHTS"] != eod_probe["dated_pair_work_items"]:
        raise EodStandardContractAdmissionError(
            "causal admission denominator changed"
        )

    result = {
        "contract": CONTRACT,
        "status": (
            "PROVIDER_STANDARD_EOD_CAUSAL_ADMISSION_AUDIT_"
            "MODELED_MULTIPLIER_ONLY"
        ),
        "selection_fingerprint": selection["selection_fingerprint"],
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "eod_probe_fingerprint": eod_probe["probe_fingerprint"],
        "provider_standard_semantics": PROVIDER_STANDARD_SEMANTICS,
        "provider_standard_semantics_fingerprint":
            PROVIDER_STANDARD_SEMANTICS_FINGERPRINT,
        "original_case_denominator": expected_original_cases,
        "original_right_memberships": expected_original_cases * 2,
        "dated_pair_work_items": counts["DATED_RIGHTS"],
        "unique_verified_selected_chain_requests": len(verified_chain_ids),
        "provider_standard_at_selection":
            counts["PROVIDER_STANDARD_AT_SELECTION"],
        "entry_eod_clock_liquidity_source_shape":
            counts["ENTRY_EOD_CLOCK_LIQUIDITY_SOURCE_SHAPE"],
        "causal_entry_ready_model_source_shape":
            counts["CAUSAL_ENTRY_READY_MODEL_SOURCE_SHAPE"],
        "later_exit_eod_clock_liquidity_source_shape":
            counts["LATER_EXIT_EOD_CLOCK_LIQUIDITY_SOURCE_SHAPE"],
        "entry_and_later_exit_model_source_shape":
            counts["ENTRY_AND_LATER_EXIT_MODEL_SOURCE_SHAPE"],
        "future_exit_used_for_entry_admission": False,
        "provider_standard_100_share_multiplier_is_model_assumption": True,
        "independent_occ_deliverable_multiplier_verified": 0,
        "historical_option_trades_admitted": 0,
        "historical_account_pnl": None,
        "historical_account_pnl_authority": False,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "by_year": {
            year: dict(sorted(counter.items()))
            for year, counter in by_year.items()
        },
        "rows": output_rows,
    }
    result["audit_fingerprint"] = _fingerprint(result)
    return result


def persist_eod_standard_contract_admission_audit(
    settings: AtlasSettings,
    report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "audit_fingerprint")
    if (
        report.get("contract") != CONTRACT
        or report.get("provider_requests") != 0
        or report.get("future_exit_used_for_entry_admission") is not False
        or report.get("historical_option_trades_admitted") != 0
        or report.get("historical_account_pnl_authority") is not False
        or report.get("independent_occ_deliverable_multiplier_verified") != 0
    ):
        raise EodStandardContractAdmissionError("audit authority changed")
    path = settings.resolved_path(
        f"{OUTPUT_REL}_{report['audit_fingerprint'][:16]}.json"
    )
    raw = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise EodStandardContractAdmissionError(
                "existing audit path is invalid"
            )
        if path.read_text(encoding="utf-8") != raw:
            raise EodStandardContractAdmissionError(
                "immutable audit path already contains different bytes"
            )
        return path, "REUSED_IMMUTABLE_EOD_STANDARD_ADMISSION_AUDIT"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(raw)
        handle.flush()
    return path, "WRITTEN_IMMUTABLE_EOD_STANDARD_ADMISSION_AUDIT"
