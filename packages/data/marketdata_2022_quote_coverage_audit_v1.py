from __future__ import annotations

"""Read-only coverage audit for frozen 2022 PIT-wide CALL quote histories.

Uses original D: plan, body, attempt and receipt. Never requests provider data,
writes a new immutable receipt, assumes missing EOD days mean no trading, or
certifies at-decision option execution.
"""

from datetime import date
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.marketdata_2022_broad_quote_campaign_v2 import (
    PLAN_REL, POLICY_VERSION, WIDE_POLICY, WINDOW,
)
from packages.data.marketdata_2022_selected_quote_campaign_v1 import (
    CONTRACT as QUOTE_CONTRACT, _read_intact_quote,
)
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, _fingerprint,
)
from packages.data.marketdata_candidate_expansion_v1 import _read_object

CONTRACT = "atlas-marketdata-2022-quote-coverage-audit-v1"


def audit_frozen_quote_coverage(
    settings: AtlasSettings, *, last_shard_inclusive: int = 15,
) -> dict[str, Any]:
    """Verify exact original source receipts and sum coverage, ZERO provider GETs."""
    if type(last_shard_inclusive) is not int or not 0 <= last_shard_inclusive <= 70:
        raise CandidateChainCacheError("audit shard bound must be 0..70")
    path = settings.resolved_path(
        f"{PLAN_REL}/through_shard_{last_shard_inclusive:03d}.json"
    )
    if path.is_symlink() or not path.is_file():
        raise CandidateChainCacheError("frozen broad quote plan missing or linked")
    plan = _read_object(path)
    unsigned = dict(plan)
    stored_fp = unsigned.pop("plan_fingerprint", None)
    envelope = plan.get("broad_acquisition_envelope_v2")
    if (stored_fp != _fingerprint(unsigned)
            or plan.get("contract") != QUOTE_CONTRACT
            or plan.get("selection_policy") != WIDE_POLICY
            or plan.get("last_shard_inclusive") != last_shard_inclusive
            or not isinstance(envelope, dict)
            or envelope.get("policy_version") != POLICY_VERSION
            or envelope.get("strike_window_fraction_each_side") != str(WINDOW)
            or envelope.get("alternate_expiration_sources_acquired") is not False
            or envelope.get("reuses_prior_exact_v1_quote_receipts") is not True):
        raise CandidateChainCacheError("frozen broad quote plan fingerprint/policy changed")
    tickets = plan.get("requests")
    if (not isinstance(tickets, list)
            or len(tickets) != plan.get("unique_exact_quote_series")
            or len({x.get("request_identity") for x in tickets}) != len(tickets)
            or plan.get("provider_reads_in_planning") != 0):
        raise CandidateChainCacheError("frozen exact quote census altered")
    complete = gaps = pending = bytes_total = observed_rows = 0
    positive_volume_rows = zero_volume_rows = no_positive_volume_histories = 0
    first: date | None = None
    last: date | None = None
    charges = 0
    for ticket in tickets:
        # _read_intact_quote verifies SHA, original intent, receipt fingerprint,
        # exact query identity, original byte count, schema and row timestamps.
        receipt = _read_intact_quote(settings, ticket)
        if receipt is None:
            pending += 1
            continue
        bytes_total += receipt["body_bytes"]
        charges += receipt["rate_limit"]["consumed"]
        if receipt["status"] == "EXACT_QUERY_SOURCE_GAP":
            gaps += 1
            continue
        if receipt["status"] != "COMPLETE_SOURCE_ONLY":
            raise CandidateChainCacheError("unexpected exact quote receipt status")
        complete += 1
        safe = receipt["safe_summary"]
        observed_rows += safe["observed_rows"]
        positive_volume_rows += safe["positive_volume_rows"]
        zero_volume_rows += safe["zero_volume_rows"]
        if safe["positive_volume_rows"] == 0:
            no_positive_volume_histories += 1
        first_day = date.fromisoformat(safe["first_session"])
        last_day = date.fromisoformat(safe["last_session"])
        first = first_day if first is None else min(first, first_day)
        last = last_day if last is None else max(last, last_day)
    result = {
        "contract": CONTRACT,
        "status": "COMPLETE_SOURCE_ONLY" if pending == 0 else "PARTIAL_PENDING",
        "frozen_plan_fingerprint": stored_fp,
        "source_shards": f"0..{last_shard_inclusive}",
        "selected_candidate_memberships": plan["selected_candidate_memberships"],
        "source_gap_ledger_entries_not_physical_404_count": len(plan["source_gaps"]),
        "unique_exact_quote_series": len(tickets),
        "complete_exact_histories": complete,
        "exact_quote_no_data_gaps": gaps,
        "pending_exact_histories": pending,
        "total_observed_eod_rows": observed_rows,
        "rows_with_positive_reported_volume": positive_volume_rows,
        "rows_with_zero_reported_volume": zero_volume_rows,
        "histories_with_no_positive_reported_volume": no_positive_volume_histories,
        "first_observed_session": first.isoformat() if first else None,
        "last_observed_session": last.isoformat() if last else None,
        "verified_original_raw_body_bytes": bytes_total,
        "sum_original_provider_reported_charges": charges,
        "provider_requests_this_audit": 0,
        "historical_eod_only_no_0935_fill_or_option_pnl_authority": True,
    }
    result["audit_fingerprint"] = _fingerprint(result)
    return result
