from __future__ import annotations

"""Broader PIT 2022 CALL EOD source envelope using immutable prior-session chains.

The existing V1 cache is intentional: exact OCC/from/to identity is independent
of selection plan, so a future expansion must never re-request the same series.
"""

from decimal import Decimal
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_additive_2022_shards_v1 import prepare_additive_shard
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError, _fingerprint
from packages.data.marketdata_2022_selected_quote_campaign_v1 import (
    CONTRACT as V1_CACHE_CONTRACT, freeze_quote_plan, run_selected_quote_histories,
)

POLICY_VERSION = "atlas-2022-PIT-call-full-captured-strike-window-v2"
WIDE_POLICY = (
    "ALL_PRIOR_SESSION_CALLS_WITHIN_8_PERCENT_OF_ORIGINAL_RAW_OPEN_"
    "ORIGINAL_28_TO_60_DAY_MONTHLY_EXPIRATION_EOD_ONLY"
)
WINDOW = Decimal("0.08")
PLAN_REL = "data/options/manifests/marketdata_2022_broad_quote_plans_v2"
MAX_LAST_SHARD = 70


def freeze_broad_quote_plan(
    settings: AtlasSettings, *, last_shard_inclusive: int = 15,
    preparer: Callable[..., Any] = prepare_additive_shard,
) -> dict[str, Any]:
    """Broaden existing source-only selection, NOT the historical source request.

    Individual quote GETs remain the original V1 contract's physical cache
    identity. Already stored V1 exact OCC/year-start/expiry requests are reused.
    """
    if type(last_shard_inclusive) is not int or not 0 <= last_shard_inclusive <= MAX_LAST_SHARD:
        raise CandidateChainCacheError("broad quote shard bound outside 0..70")
    plan = freeze_quote_plan(
        settings, last_shard_inclusive=last_shard_inclusive,
        preparer=preparer, candidate_limit=None, strike_window=WINDOW,
        quote_selection_policy=WIDE_POLICY,
    )
    if plan["contract"] != V1_CACHE_CONTRACT or plan["selection_policy"] != WIDE_POLICY:
        raise CandidateChainCacheError("broad selection unexpectedly changed physical quote cache")
    plan["broad_acquisition_envelope_v2"] = {
        "policy_version": POLICY_VERSION,
        "stock_input": "ACCEPTED_NATIVE_RAW_1DAY_ENTRY_OPEN",
        "candidate_side": "LONG_SINGLE_LEG_CALL",
        "strike_window_fraction_each_side": str(WINDOW),
        "candidate_strikes": "ALL_PRIOR_SESSION_CALLS_RETURNED_INSIDE_INDIVIDUAL_PIT_WINDOW",
        "minimum_rank_filter": False,
        "same_day_eod_liquidity_or_outcome_filter": False,
        "captured_expiration_per_original_opportunity": 1,
        "expiration_basis": "ORIGINAL_ACCEPTED_MONTHLY_28_TO_60_DTE",
        "alternate_expiration_sources_acquired": False,
        "additional_expiration_coverage": "REQUIRES_SEPARATE_FROZEN_SOURCE_QUERIES",
        "original_monthly_pilot_in_this_additive_plan": False,
        "other_years_in_this_plan": False,
        "exact_quote_identity": "OCC_SYMBOL_2022_01_01_THROUGH_EXCLUSIVE_EXPIRY_PLUS_ONE",
        "reuses_prior_exact_v1_quote_receipts": True,
        "option_intraday_0935_fill_or_pnl_authority": False,
    }
    unsigned = dict(plan)
    unsigned.pop("plan_fingerprint")
    plan["plan_fingerprint"] = _fingerprint(unsigned)
    return plan


def run_broad_quote_histories(
    settings: AtlasSettings, plan: dict[str, Any], **kwargs: Any,
) -> dict[str, Any]:
    """Use the audited V1 exact-query cache, never a new competing cache."""
    unsigned = dict(plan)
    fp = unsigned.pop("plan_fingerprint", None)
    envelope = plan.get("broad_acquisition_envelope_v2")
    if (fp != _fingerprint(unsigned)
            or plan.get("selection_policy") != WIDE_POLICY
            or not isinstance(envelope, dict)
            or envelope.get("policy_version") != POLICY_VERSION
            or envelope.get("strike_window_fraction_each_side") != str(WINDOW)
            or envelope.get("alternate_expiration_sources_acquired") is not False
            or envelope.get("reuses_prior_exact_v1_quote_receipts") is not True):
        raise CandidateChainCacheError("broad PIT envelope/plan altered before provider read")
    return run_selected_quote_histories(settings, plan, **kwargs)
