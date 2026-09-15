from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Final


ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_ID: Final = (
    "atlas-orb-stocks-in-play-5m-literature-v2-preoutcome-20260915"
)
ORB_STOCKS_IN_PLAY_LITERATURE_V2_POLICY_ID: Final = (
    "orb_stocks_in_play_5m_literature_v2"
)

# This contract is frozen before any v2 outcome is opened.  It is deliberately
# separate from orb_stocks_in_play_5m_v1 so the accepted successor evidence is
# immutable and the literature-fidelity hypothesis cannot rewrite its history.
_CONTRACT = {
    "contract_id": ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_ID,
    "policy_id": ORB_STOCKS_IN_PLAY_LITERATURE_V2_POLICY_ID,
    "economic_family_id": "opening_range",
    "scope": "DEVELOPMENT_ONLY",
    "development_start": "2016-01-04",
    "development_end": "2026-04-30",
    "opening_range_start_et": "09:30",
    "opening_range_end_exclusive_et": "09:35",
    "decision_time_et": "09:35",
    "opening_price_min": 5.0,
    "prior_average_daily_share_volume_sessions": 14,
    "prior_average_daily_share_volume_min": 1_000_000,
    "atr_sessions": 14,
    "atr_min_dollars": 0.50,
    "opening_relvol_lookback_sessions": 14,
    "opening_relvol_min": 1.0,
    "daily_relvol_rank_max": 20,
    "direction_rule": "FIRST_5M_CANDLE_OPEN_TO_CLOSE;DOJI_ABSTAIN",
    "entry_rule": "DIRECTIONAL_STOP_AT_OPENING_RANGE_BOUNDARY_AFTER_09:35",
    "gap_through_stop_fill_rule": (
        "FILL_AT_FIRST_POST_0935_BAR_OPEN_IF_OPEN_BEYOND_STOP_OTHERWISE_STOP_PRICE_ON_CROSS"
    ),
    "same_minute_entry_stop_rule": "UNORDERED_NONCOMPARABLE",
    "stop_rule": "0.10_X_PRIOR_ATR14_FROM_EXECUTED_ENTRY",
    "exit_rule": "EOD_LAST_REGULAR_BAR_IF_STOP_NOT_HIT",
    "max_trades_per_symbol_session": 1,
    "cost_grid_bps": [0, 10, 25, 50, 100],
    "primary_cost_bps": 50,
    "stress_cost_bps": 100,
    "portfolio_sizing": "DIAGNOSTIC_ONLY_NOT_AUTHORITY",
    "path_thresholds_pct": [1, 2, 3, 5],
    "historical_option_pnl_claimed": False,
    "consumed_master_reads": 0,
    "future_blind_reads": 0,
    "provider_reads": 0,
    "broker_reads": 0,
    "broker_writes": 0,
    "paper_authority": False,
    "live_authority": False,
    "strategy_promotion_authority": False,
    "selector_promotion_authority": False,
    "confluence_authority": False,
    "option_trading_authority": False,
    "scientific_note": (
        "B35/opening-range DEVELOPMENT-motivated challenger; DEVELOPMENT can diagnose "
        "but cannot self-validate or promote."
    ),
}

ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT: Final = MappingProxyType(_CONTRACT)


def contract_payload() -> dict[str, object]:
    """Return a JSON-safe copy of the frozen pre-outcome contract."""

    return json.loads(json.dumps(_CONTRACT))


def contract_fingerprint() -> str:
    payload = json.dumps(
        _CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT: Final = (
    "1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb"
)

if contract_fingerprint() != ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT:
    raise RuntimeError("ORB literature-v2 scientific contract fingerprint drifted")
