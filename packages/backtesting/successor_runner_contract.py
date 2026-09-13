from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Iterable

from packages.backtesting.b35_development_source import B35_DEVELOPMENT_SOURCE_CONTRACT
from packages.backtesting.reference_v2_lake_adapter import REFERENCE_V2_LAKE_ADAPTER_CONTRACT_VERSION
from packages.strategies.successor_implementation_bundle import SUCCESSOR_IMPLEMENTATION_BUNDLE_FINGERPRINT
from packages.strategies.successor_practitioner_lab import (
    B35_CHALLENGERS,
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    NEW_FAMILIES,
    RETAINED_FAMILIES,
    SUCCESSOR_LAB_FINGERPRINT,
)
from packages.strategies.successor_practitioner_rules import ALL_SUCCESSOR_POLICY_IMPLEMENTATIONS


SUCCESSOR_RUNNER_CONTRACT: Final[str] = (
    "atlas-successor-development-runner-contract-v1-preoutcome-no-authority"
)
DAILY_SOURCE_ID: Final[str] = "alpaca_sip_v2_research_daily_development"
MINUTE_SOURCE_ID: Final[str] = "alpaca_sip_v2_canonical_minute_b35_development"
DAILY_GROUP_BUCKETS: Final[int] = 64
COST_GRID_BPS: Final[tuple[int, ...]] = (0, 10, 25, 50, 100)
ARTIFACT_ORDER: Final[tuple[str, ...]] = (
    "preoutcome_contract.json",
    "source_manifest.json",
    "execution_profile.json",
    "groups/<group>/output.json",
    "groups/<group>/receipt.json",
    "standalone_results",
    "context",
    "confluence",
    "summary.json",
)


@dataclass(frozen=True, slots=True)
class SuccessorPolicyRoute:
    policy_id: str
    economic_family_id: str
    native_timeframe: str
    source_id: str
    evaluator_contract_id: str
    same_family_for_multiplicity: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _require_sha256(value: str, label: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value


def _project_relative_locator(path: Path, *, project_root: Path) -> str:
    root = Path(project_root).resolve()
    resolved = Path(path).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"source file escapes project root: {resolved}") from exc
    if not relative.parts:
        raise ValueError("source file locator cannot be the project root itself")
    return relative.as_posix()


def daily_group_token(instrument_id: str) -> str:
    """Stable, runtime-profile-independent group for complete daily histories."""
    if not instrument_id:
        raise ValueError("instrument_id is required")
    digest = hashlib.sha256(instrument_id.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") % DAILY_GROUP_BUCKETS
    return f"daily_{bucket:02d}"


def successor_policy_routes() -> tuple[SuccessorPolicyRoute, ...]:
    routes: list[SuccessorPolicyRoute] = []
    implemented = {item.policy_id: item for item in ALL_SUCCESSOR_POLICY_IMPLEMENTATIONS}
    challenger_ids = {item.policy_id for item in B35_CHALLENGERS}

    for family in RETAINED_FAMILIES:
        for policy_id in family.canonical_policy_ids:
            timeframe = family.native_timeframes[0]
            if timeframe == "1d":
                source_id = DAILY_SOURCE_ID
                evaluator = "accepted_reference_daily_v1"
            elif timeframe == "1m":
                source_id = MINUTE_SOURCE_ID
                evaluator = "accepted_b35_intraday_v1"
            else:
                raise RuntimeError(f"unsupported retained timeframe: {timeframe}")
            routes.append(
                SuccessorPolicyRoute(
                    policy_id=policy_id,
                    economic_family_id=family.family_id,
                    native_timeframe=timeframe,
                    source_id=source_id,
                    evaluator_contract_id=evaluator,
                    same_family_for_multiplicity=False,
                )
            )

    family_by_policy = {
        policy_id: family.family_id
        for family in NEW_FAMILIES
        for policy_id in family.canonical_policy_ids
    }
    family_by_policy.update({item.policy_id: item.economic_family_id for item in B35_CHALLENGERS})
    for policy_id in sorted(implemented):
        item = implemented[policy_id]
        if item.native_timeframe == "1d":
            source_id = DAILY_SOURCE_ID
            evaluator = "successor_practitioner_daily_v1"
        elif item.native_timeframe == "1m":
            source_id = MINUTE_SOURCE_ID
            evaluator = "successor_intraday_v1"
        else:
            raise RuntimeError(f"unsupported successor timeframe: {item.native_timeframe}")
        routes.append(
            SuccessorPolicyRoute(
                policy_id=policy_id,
                economic_family_id=family_by_policy[policy_id],
                native_timeframe=item.native_timeframe,
                source_id=source_id,
                evaluator_contract_id=evaluator,
                same_family_for_multiplicity=policy_id in challenger_ids,
            )
        )

    ordered = tuple(sorted(routes, key=lambda item: item.policy_id))
    ids = [item.policy_id for item in ordered]
    if len(ids) != 28 or len(ids) != len(set(ids)):
        raise RuntimeError(f"successor runner expected 28 unique policy routes, got {len(ids)}")
    if sum(item.native_timeframe == "1d" for item in ordered) != 18:
        raise RuntimeError("successor runner daily policy routing drifted")
    if sum(item.native_timeframe == "1m" for item in ordered) != 10:
        raise RuntimeError("successor runner minute policy routing drifted")
    return ordered


def source_contracts(*, daily_source_fingerprint: str, minute_source_fingerprint: str) -> dict[str, object]:
    return {
        DAILY_SOURCE_ID: {
            "adapter_contract": REFERENCE_V2_LAKE_ADAPTER_CONTRACT_VERSION,
            "source_root_id": "data/v2_build/alpaca_sip_v2/derived/research_daily/<source_fp16>",
            "manifest_id": "data/v2_build/alpaca_sip_v2/manifests/research_daily.json",
            "source_fingerprint": _require_sha256(daily_source_fingerprint, "daily source fingerprint"),
            "price_adjustment": "SPLIT_ADJUSTED",
            "bar_clock": "FINALIZED_1D_REGULAR_CLOSE",
            "protected_rows_permitted": 0,
            "future_blind_rows_permitted": 0,
        },
        MINUTE_SOURCE_ID: {
            "adapter_contract": B35_DEVELOPMENT_SOURCE_CONTRACT,
            "source_root_id": "data/v2_build/alpaca_sip_v2/canonical/stocks/1m",
            "manifest_id": "data/v2_build/alpaca_sip_v2/manifests/native_acquisition_plan.jsonl.gz",
            "source_fingerprint": _require_sha256(minute_source_fingerprint, "minute source fingerprint"),
            "price_adjustment": "RAW_UNADJUSTED",
            "bar_clock": "LEFT_EDGE_1M_AVAILABLE_AT_TIMESTAMP_PLUS_1M",
            "missing_minutes": "ABSENCE_REMAINS_ABSENCE",
            "protected_rows_permitted": 0,
            "future_blind_rows_permitted": 0,
        },
    }


def frozen_grouping_contract() -> dict[str, object]:
    return {
        "profile_independent": True,
        "daily": {
            "rule": "COMPLETE_INSTRUMENT_HISTORY_KEPT_TOGETHER",
            "group_count": DAILY_GROUP_BUCKETS,
            "partition_key": "sha256(instrument_id)[0:8]-as-uint64-mod-64",
            "token_format": "daily_00..daily_63",
            "runtime_profile_may_change_group_membership": False,
        },
        "minute": {
            "rule": "ACCEPTED_B35_SYMBOL_BATCH_GROUPS",
            "partition_key": "EXACT_SORTED_NATIVE_PLAN_SYMBOL_TUPLE",
            "unit_order": "YEAR_MONTH_BATCH_INDEX_UNIT_ID",
            "runtime_profile_may_change_group_membership": False,
        },
    }


def frozen_outcome_contract() -> dict[str, object]:
    return {
        "cost_grid_bps_all_in_round_trip": list(COST_GRID_BPS),
        "daily": {
            "entry": "NEXT_REGULAR_SESSION_OPEN_AFTER_SIGNAL_CLOSE",
            "forward_horizons_sessions": [1, 5, 20],
            "exit": "REGULAR_CLOSE_OF_NTH_SUBSEQUENT_SESSION",
            "mfe_mae_window": "NEXT_OPEN_THROUGH_20TH_SUBSEQUENT_REGULAR_SESSION",
            "strategy_specific_stop_target": False,
            "insufficient_future_status": "INSUFFICIENT_FUTURE",
            "all_horizons_diagnostic_only": True,
        },
        "intraday": {
            "base_semantics": "ACCEPTED_B35_INTRADAY_OUTCOMES_V1",
            "entry": "NEXT_OBSERVED_REGULAR_MINUTE_MAX_5M_DELAY",
            "target": "FIXED_2R_FROM_STRUCTURAL_STOP",
            "same_minute_stop_target_tie": "STOP_WINS_CONSERVATIVE",
            "time_exit": "FIRST_OBSERVED_REGULAR_BAR_1555_THROUGH_1559_ET",
            "new_policy_stop_anchors": {
                "pract_vwap_reclaim_reject_v1": "ADVERSE_SIDE_SIGNAL_BAR_EXTREME",
                "pract_session_failed_break_reclaim_v1": "SIGNAL_BAR_EXTREME_BEYOND_RECLAIMED_LEVEL",
                "gap_quality_condition_long_v2": "PREVIOUS_REGULAR_CLOSE",
                "orb_stocks_in_play_5m_v1": "OPPOSITE_5M_OPENING_RANGE_BOUNDARY",
                "orb_15m_close_retest_v2": "OPPOSITE_15M_OPENING_RANGE_BOUNDARY",
                "premarket_relvol_quality_v2": "INHERITED_PREMARKET_CONSOLIDATION_BOUNDARY",
            },
        },
        "standalone_before_conditioning": True,
        "standalone_before_confluence": True,
        "same_outcome_refit_or_search_permitted": False,
    }


def frozen_authority_contract() -> dict[str, object]:
    return {
        "strategy_authority": "RESEARCH",
        "historical_outcomes_opened_by_preflight": False,
        "protected_master_rows_read": 0,
        "future_blind_rows_read": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
    }


def build_successor_runner_contract(*, daily_source_fingerprint: str, minute_source_fingerprint: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": SUCCESSOR_RUNNER_CONTRACT,
        "development_scope": [DEVELOPMENT_START, DEVELOPMENT_END],
        "successor_lab_fingerprint": SUCCESSOR_LAB_FINGERPRINT,
        "successor_implementation_bundle_fingerprint": SUCCESSOR_IMPLEMENTATION_BUNDLE_FINGERPRINT,
        "sources": source_contracts(
            daily_source_fingerprint=daily_source_fingerprint,
            minute_source_fingerprint=minute_source_fingerprint,
        ),
        "policy_routes": [item.as_dict() for item in successor_policy_routes()],
        "grouping": frozen_grouping_contract(),
        "artifact_order": list(ARTIFACT_ORDER),
        "outcomes": frozen_outcome_contract(),
        "authority": frozen_authority_contract(),
        "scientific_identity_excludes_runtime_profile": True,
    }
    payload["fingerprint"] = canonical_sha256(payload)
    return payload


def minute_symbol_groups(units: Iterable[object]) -> tuple[tuple[tuple[str, ...], tuple[object, ...]], ...]:
    grouped: dict[tuple[str, ...], list[object]] = {}
    for unit in units:
        symbols = tuple(getattr(unit, "symbols"))
        grouped.setdefault(symbols, []).append(unit)
    return tuple(
        (
            symbols,
            tuple(
                sorted(
                    grouped[symbols],
                    key=lambda item: (
                        int(getattr(item, "year")),
                        int(getattr(item, "month")),
                        int(getattr(item, "batch_index")),
                        str(getattr(item, "unit_id")),
                    ),
                )
            ),
        )
        for symbols in sorted(grouped)
    )


def build_source_binding_payload(
    *,
    token: str,
    source_id: str,
    files: Iterable[tuple[Path, str]],
    project_root: Path,
) -> dict[str, object]:
    if source_id not in {DAILY_SOURCE_ID, MINUTE_SOURCE_ID}:
        raise ValueError(f"unsupported successor source id: {source_id}")
    records = sorted(
        (
            {
                "relative_path": _project_relative_locator(path, project_root=project_root),
                "sha256": _require_sha256(expected, "source file SHA-256"),
            }
            for path, expected in files
        ),
        key=lambda item: str(item["relative_path"]),
    )
    if not records:
        raise ValueError("source-binding group requires at least one file")
    return {
        "contract": SUCCESSOR_RUNNER_CONTRACT,
        "token": token,
        "source_id": source_id,
        "files": records,
        "outcome_rows_opened": 0,
        "authority": frozen_authority_contract(),
    }
