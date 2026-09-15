from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Final

from packages.strategies.successor_orb_stocks_in_play_literature_v2_contract import (
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT,
)


ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_CONTRACT_ID: Final = (
    "atlas-orb-stocks-in-play-5m-literature-v2-development-analysis-preoutcome-20260915"
)

_CONTRACT = {
    "contract_id": ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_CONTRACT_ID,
    "base_strategy_contract_fingerprint": ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT,
    "scope": "DEVELOPMENT_ONLY",
    "development_start": "2016-01-04",
    "development_end": "2026-04-30",
    "accepted_successor_source_verification_fingerprint": (
        "a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3"
    ),
    "minute_grouping": "EXACT_SORTED_NATIVE_PLAN_SYMBOL_TUPLE",
    "opening_snapshot": "EXACT_0930_THROUGH_0934_ET_REGULAR_MINUTE_BARS;REQUIRE_5_BARS",
    "daily_price_reconstruction": {
        "price_factor": "unadjusted_close / split_adjusted_close",
        "raw_ohlc": "split_adjusted_ohlc * price_factor",
        "factor_requirement": "FINITE_POSITIVE",
    },
    "prior_average_daily_share_volume": (
        "PROVIDER_NATIVE_SPLIT_ADJUSTED_DAILY_VOLUME_AS_SUPPLIED;"
        "SIMPLE_MEAN_PRIOR_14_INSTRUMENT_SESSIONS_SHIFT_1;"
        "NO_INVERSE_PRICE_FACTOR_VOLUME_TRANSFORM"
    ),
    "opening_relvol": (
        "CURRENT_EXACT_FIRST5_SHARE_VOLUME / SIMPLE_MEAN_PRIOR_14_EXACT_FIRST5_VOLUMES"
    ),
    "opening_relvol_history_requirement": (
        "EXACT_PREVIOUS_14_XNYS_SESSIONS_EACH_REQUIRE_EXACT_FIRST5_BARS"
    ),
    "cross_sectional_rank": "ELIGIBLE_RV_DESC_THEN_TICKER_THEN_INSTRUMENT_ID;TOP_20",
    "entry_execution": {
        "direction": "FIRST5_OPEN_TO_CLOSE;DOJI_ABSTAIN",
        "stop": "OPENING_RANGE_HIGH_LONG_OR_LOW_SHORT",
        "gap_through": "FIRST_POST_0935_BAR_OPEN_IF_BEYOND_STOP",
        "otherwise": "STOP_PRICE_ON_CROSS",
    },
    "stop_execution": {
        "level": "0.10_X_PRIOR_ATR14_FROM_EXECUTED_ENTRY",
        "same_minute_entry_stop": "UNORDERED_NONCOMPARABLE",
        "later_gap_through": "BAR_OPEN_IF_OPEN_BEYOND_STOP",
        "otherwise": "STOP_PRICE_ON_CROSS",
    },
    "time_exit": "LAST_OBSERVED_REGULAR_SESSION_BAR_CLOSE",
    "path_measurement": {
        "entry_bar_extremes": "EXCLUDED",
        "exit_bar_extremes": "EXCLUDED",
        "terminal_exit_return": "INCLUDED",
        "thresholds_pct": [1, 2, 3, 5],
        "same_minute_both_thresholds": "UNORDERED",
    },
    "cost_grid_bps_all_in_round_trip": [0, 10, 25, 50, 100],
    "primary_cost_bps": 50,
    "stress_cost_bps": 100,
    "execution_funnel": (
        "VERIFY_AND_OPENING_SNAPSHOT_ALL_ACCEPTED_GROUPS_THEN_FULL_SESSION_ONLY_TOP20_CANDIDATES"
    ),
    "restart_safe_group_artifacts": True,
    "scientific_identity_excludes_runtime_worker_count": True,
    "historical_option_pnl_claimed": False,
    "consumed_master_reads": 0,
    "future_blind_reads": 0,
    "provider_reads": 0,
    "broker_reads": 0,
    "broker_writes": 0,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
    "option_trading_authority": False,
}

ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_CONTRACT: Final = MappingProxyType(_CONTRACT)


def contract_payload() -> dict[str, object]:
    return json.loads(json.dumps(_CONTRACT))


def contract_fingerprint() -> str:
    raw = json.dumps(_CONTRACT, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT: Final = (
    "3c4538098af3ca3c19f147547c50b92429ed9e8ec3ed284193c59dce3268a44e"
)

if contract_fingerprint() != ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT:
    raise RuntimeError("ORB literature-v2 DEVELOPMENT analysis contract fingerprint drifted")
