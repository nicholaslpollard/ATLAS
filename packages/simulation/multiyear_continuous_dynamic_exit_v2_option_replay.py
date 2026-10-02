from __future__ import annotations

"""Continuous Dynamic Exit V2 for historical EOD CALL diagnostics.

V2 does not re-select the entry opportunity.  For every accepted daily-LONG case with
the already-required strictly-prior path evidence, it derives a continuous stop and
target from that case's *training-only* distribution:

    downside_anchor = mean(mean_MAE, max(0, -P25 gross return))
    upside_anchor   = mean(mean_MFE, max(0,  P75 gross return))

The anchors are clipped to the already researched static envelope:
    stop   in [1%, 3%]
    target in [2%, 5%]

The target is then raised, if necessary, to preserve the existing minimum 1.5x
target/stop design constraint.  Because stop <= 3%, that guard never requires a
target above 4.5% and therefore stays inside the frozen 5% ceiling.

These levels use only fields already carried from the opportunity's strictly-prior
training cell. Current-case outcome, current-fold outcome and option exit evidence
never influence the stop/target derivation.

Historical option semantics remain the same as the strategy-aligned EOD replay:
- CALL entry = accepted first later-session qualified EOD ask;
- stock STOP/TARGET/TIME resolves the exit session;
- option exit attempt = exact EOD bid on that stock exit session;
- no forward search after a missing/illiquid exact-session option exit;
- protected 2026 outcomes remain unread.

Outputs remain modeled diagnostics, not verified fills or strategy/PAPER/LIVE authority.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import math
from pathlib import Path
import statistics
from typing import Any, Callable, Sequence

from packages.backtesting.recurrent_successor_daily_exit_sweep import (
    DailyPathCase,
    resolve_daily_exit,
)
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_demand_quote_cache_v1 import CONTRACT as QUOTE_CONTRACT
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import (
    _decode_snapshot_rows,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    CONTRACT as HANDOFF_CONTRACT,
    _check_signature,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    SCENARIO_CONTRACT as BASE_SCENARIO_CONTRACT,
)
from packages.simulation.multiyear_strategy_aligned_eod_option_replay_v1 import (
    _exit_row_qualified,
)

SCENARIO_CONTRACT = "atlas-multiyear-continuous-dynamic-exit-v2-option-scenario"
REPLAY_CONTRACT = "atlas-multiyear-continuous-dynamic-exit-v2-option-replay"
DIAGNOSTIC_CONTRACT = (
    "atlas-multiyear-continuous-dynamic-exit-v2-paired-observation-diagnostics"
)
SCENARIO_REL = (
    "data/options/derived/multiyear_continuous_dynamic_exit_v2_option_scenario"
)
REPLAY_REL = "data/options/derived/multiyear_continuous_dynamic_exit_v2_option_replay"
DIAGNOSTIC_REL = (
    "data/options/derived/"
    "multiyear_continuous_dynamic_exit_v2_paired_observation_diagnostics"
)

STOP_MIN = 0.01
STOP_MAX = 0.03
TARGET_MIN = 0.02
TARGET_MAX = 0.05
MIN_TARGET_TO_STOP = 1.5
PROTECTED_2026_START = date(2026, 1, 1)


class ContinuousDynamicExitV2Error(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ContinuousExitChoice:
    stop_fraction: float
    target_fraction: float
    downside_anchor: float
    upside_anchor: float
    mean_mae: float
    mean_mfe: float
    downside_p25: float
    upside_p75: float
    training_sample_size: int
    training_start: date
    training_end: date

    @property
    def policy_id(self) -> str:
        return (
            f"CONTINUOUS_V2_STOP_{self.stop_fraction:.6f}_"
            f"TARGET_{self.target_fraction:.6f}"
        )


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def derive_continuous_exit_choice(case: DailyPathCase) -> ContinuousExitChoice:
    """Derive stop/target from prior-only training-cell distribution evidence."""
    item = case.opportunity
    values = (
        float(item.training_mean_mae),
        float(item.training_mean_mfe),
        float(item.training_p25_gross_return),
        float(item.training_p75_gross_return),
    )
    if not all(math.isfinite(value) for value in values):
        raise ContinuousDynamicExitV2Error(
            "continuous exit training distribution contains non-finite values"
        )
    if item.training_sample_size < 1:
        raise ContinuousDynamicExitV2Error("continuous exit has empty training sample")
    if item.training_end >= item.signal_session:
        raise ContinuousDynamicExitV2Error(
            "continuous exit training cutoff is not before signal"
        )

    mean_mae = max(0.0, float(item.training_mean_mae))
    mean_mfe = max(0.0, float(item.training_mean_mfe))
    downside_p25 = max(0.0, -float(item.training_p25_gross_return))
    upside_p75 = max(0.0, float(item.training_p75_gross_return))

    downside_anchor = (mean_mae + downside_p25) / 2.0
    upside_anchor = (mean_mfe + upside_p75) / 2.0

    stop_fraction = _clip(downside_anchor, STOP_MIN, STOP_MAX)
    target_fraction = _clip(upside_anchor, TARGET_MIN, TARGET_MAX)
    target_fraction = max(
        target_fraction,
        MIN_TARGET_TO_STOP * stop_fraction,
    )
    target_fraction = min(target_fraction, TARGET_MAX)
    if not (
        STOP_MIN <= stop_fraction <= STOP_MAX
        and TARGET_MIN <= target_fraction <= TARGET_MAX
        and target_fraction + 1e-12 >= MIN_TARGET_TO_STOP * stop_fraction
    ):
        raise ContinuousDynamicExitV2Error(
            "continuous exit bounds/risk-reward invariant failed"
        )

    return ContinuousExitChoice(
        stop_fraction=stop_fraction,
        target_fraction=target_fraction,
        downside_anchor=downside_anchor,
        upside_anchor=upside_anchor,
        mean_mae=mean_mae,
        mean_mfe=mean_mfe,
        downside_p25=downside_p25,
        upside_p75=upside_p75,
        training_sample_size=int(item.training_sample_size),
        training_start=item.training_start,
        training_end=item.training_end,
    )


def _choice_payload(choice: ContinuousExitChoice) -> dict[str, Any]:
    return {
        "policy_id": choice.policy_id,
        "method": "CONTINUOUS_DYNAMIC_EXIT_V2_PRIOR_TRAINING_DISTRIBUTION",
        "stop_fraction": choice.stop_fraction,
        "target_fraction": choice.target_fraction,
        "downside_anchor": choice.downside_anchor,
        "upside_anchor": choice.upside_anchor,
        "mean_mae": choice.mean_mae,
        "mean_mfe": choice.mean_mfe,
        "downside_p25": choice.downside_p25,
        "upside_p75": choice.upside_p75,
        "training_sample_size": choice.training_sample_size,
        "training_start": choice.training_start.isoformat(),
        "training_end": choice.training_end.isoformat(),
        "stop_bounds": [STOP_MIN, STOP_MAX],
        "target_bounds": [TARGET_MIN, TARGET_MAX],
        "minimum_target_to_stop_ratio": MIN_TARGET_TO_STOP,
        "time_exit": "FIFTH_ENTRY_SESSION_REGULAR_CLOSE",
        "same_session_collision": "STOP_WORST_CASE",
        "gap_through_stop": "SESSION_OPEN_IF_WORSE_THAN_STOP",
        "gap_through_target": "TARGET_PRICE_NO_POSITIVE_SLIPPAGE",
        "current_case_outcome_used": False,
        "current_fold_outcome_used": False,
        "option_exit_source_used": False,
    }


def build_continuous_dynamic_exit_v2_scenario(
    base_scenario: dict[str, Any],
    plan: dict[str, Any],
    handoff: dict[str, Any],
    daily_cases: Sequence[DailyPathCase],
    *,
    safe_last_signal_session: date,
    read_verified_body: Callable[
        [dict[str, Any], dict[str, Any]],
        tuple[dict[str, Any], bytes, dict[str, Any]],
    ],
    expected_original_cases: int = 14902,
) -> dict[str, Any]:
    for doc, field in (
        (base_scenario, "scenario_fingerprint"),
        (plan, "plan_fingerprint"),
        (handoff, "handoff_fingerprint"),
    ):
        _check_signature(doc, field)

    if (
        base_scenario.get("contract") != BASE_SCENARIO_CONTRACT
        or base_scenario.get("original_case_denominator") != expected_original_cases
        or len(base_scenario.get("cases", [])) != expected_original_cases
        or base_scenario.get("provider_requests") != 0
        or base_scenario.get("protected_2026_outcomes_read") != 0
        or base_scenario.get("historical_fills_verified") != 0
        or base_scenario.get("historical_account_pnl_authority") is not False
        or base_scenario.get("future_exit_used_for_entry_admission") is not False
        or plan.get("contract") != QUOTE_CONTRACT
        or handoff.get("contract") != HANDOFF_CONTRACT
        or base_scenario.get("quote_plan_fingerprint") != plan.get("plan_fingerprint")
        or base_scenario.get("handoff_fingerprint") != handoff.get("handoff_fingerprint")
        or handoff.get("quote_plan_fingerprint") != plan.get("plan_fingerprint")
        or handoff.get("provider_requests") != 0
        or handoff.get("protected_2026_outcomes_read") != 0
    ):
        raise ContinuousDynamicExitV2Error(
            "continuous dynamic option source lineage or authority changed"
        )

    base_by_id = {row["case_id"]: row for row in base_scenario["cases"]}
    daily_by_id = {case.opportunity.opportunity_id: case for case in daily_cases}
    handoff_by_id = {row["case_right_id"]: row for row in handoff["rows"]}
    request_by_id = {row["request_identity"]: row for row in plan["requests"]}
    if (
        len(base_by_id) != expected_original_cases
        or len(daily_by_id) != len(daily_cases)
        or not set(daily_by_id).issubset(base_by_id)
        or len(handoff_by_id) != handoff.get("original_right_memberships")
        or len(request_by_id) != plan.get("unique_physical_quote_queries")
    ):
        raise ContinuousDynamicExitV2Error(
            "continuous dynamic option denominator changed"
        )

    decoded: dict[str, list[dict[str, Any]]] = {}
    decoded_sha: dict[str, str] = {}
    counts: Counter[str] = Counter()
    by_year: dict[str, Counter[str]] = {
        str(year): Counter() for year in range(2021, 2027)
    }
    stop_values: list[float] = []
    target_values: list[float] = []
    output: list[dict[str, Any]] = []

    for base in sorted(
        base_scenario["cases"],
        key=lambda row: (row["decision_at_utc"], row["case_id"]),
    ):
        cid = base["case_id"]
        signal_day = date.fromisoformat(base["signal_session"])
        result: dict[str, Any] = {
            "case_id": cid,
            "year": base["year"],
            "ticker": base["ticker"],
            "policy_id": base["policy_id"],
            "signal_session": base["signal_session"],
            "decision_at_utc": base["decision_at_utc"],
            "economic_family_id": None,
            "selector_score": None,
            "continuous_exit_policy": None,
            "stock_exit": None,
            "call": base.get("call"),
            "strategy_aligned_status": None,
            "strategy_exit_option_mark": None,
            "future_option_exit_used_for_entry_admission": False,
            "protected_2026_outcomes_read": 0,
        }

        if signal_day > safe_last_signal_session:
            status = "PROTECTED_2026_STOCK_HORIZON_WITHHELD"
        else:
            stock_case = daily_by_id.get(cid)
            if stock_case is None:
                status = "CONTINUOUS_EXIT_INELIGIBLE_NO_PRIOR_PATH_EVIDENCE"
            else:
                item = stock_case.opportunity
                result["economic_family_id"] = item.economic_family_id
                result["selector_score"] = item.selector_score
                choice = derive_continuous_exit_choice(stock_case)
                result["continuous_exit_policy"] = _choice_payload(choice)
                stop_values.append(choice.stop_fraction)
                target_values.append(choice.target_fraction)

                resolved = resolve_daily_exit(
                    stock_case,
                    stop_fraction=choice.stop_fraction,
                    target_fraction=choice.target_fraction,
                )
                if resolved.exit_session_date >= PROTECTED_2026_START:
                    raise ContinuousDynamicExitV2Error(
                        "continuous stock exit crossed protected 2026 boundary"
                    )
                result["stock_exit"] = {
                    "disposition": resolved.disposition,
                    "session_offset": resolved.exit_session_offset,
                    "session_et": resolved.exit_session_date.isoformat(),
                    "stock_exit_price_per_unit": str(resolved.exit_price_per_unit),
                    "same_session_collision": resolved.same_session_collision,
                    "gap_through_stop": resolved.gap_through_stop,
                    "gap_through_target": resolved.gap_through_target,
                }

                call = base.get("call")
                if call is None:
                    status = "NO_DATED_CALL_RIGHT"
                elif call.get("status") != "ENTRY_READY_MODELED_STANDARD_EOD":
                    status = "CALL_ENTRY_SOURCE_NOT_CAUSALLY_READY"
                else:
                    entry = call.get("entry")
                    if not isinstance(entry, dict):
                        raise ContinuousDynamicExitV2Error(
                            "entry-ready CALL lost EOD entry"
                        )
                    entry_day = date.fromisoformat(entry["session_et"])
                    if resolved.exit_session_date <= entry_day:
                        status = "STOCK_EXIT_NOT_AFTER_OPTION_EOD_ENTRY"
                    else:
                        slot = handoff_by_id.get(call["case_right_id"])
                        if slot is None:
                            raise ContinuousDynamicExitV2Error(
                                "continuous CALL lost handoff slot"
                            )
                        request = request_by_id.get(slot.get("quote_request_identity"))
                        if request is None:
                            raise ContinuousDynamicExitV2Error(
                                "continuous CALL lost selected quote request"
                            )
                        source_id = slot.get("quote_source_request_identity")
                        body_sha = slot.get("quote_body_sha256")
                        if (
                            source_id != entry.get("physical_quote_request_identity")
                            or body_sha != entry.get("physical_quote_body_sha256")
                        ):
                            raise ContinuousDynamicExitV2Error(
                                "continuous CALL physical source changed"
                            )
                        if source_id not in decoded:
                            source_ticket, raw, receipt = read_verified_body(
                                request, slot
                            )
                            if (
                                source_ticket.get("request_identity") != source_id
                                or receipt.get("body_sha256") != body_sha
                                or receipt.get("safe_summary", {}).get("observed_rows")
                                    != slot.get("observed_quote_rows")
                            ):
                                raise ContinuousDynamicExitV2Error(
                                    "continuous physical receipt changed"
                                )
                            decoded[source_id] = _decode_snapshot_rows(
                                raw,
                                source_ticket,
                                slot["observed_quote_rows"],
                            )
                            decoded_sha[source_id] = body_sha
                        elif decoded_sha[source_id] != body_sha:
                            raise ContinuousDynamicExitV2Error(
                                "shared continuous source SHA changed"
                            )

                        exit_day = resolved.exit_session_date
                        selected_from = date.fromisoformat(request["from_inclusive"])
                        selected_to = date.fromisoformat(request["to_exclusive"])
                        if not selected_from <= exit_day < selected_to:
                            status = "STRATEGY_EXIT_OUTSIDE_SELECTED_OPTION_WINDOW"
                        else:
                            exact = [
                                row
                                for row in decoded[source_id]
                                if row["session_et"] == exit_day.isoformat()
                            ]
                            if len(exact) > 1:
                                raise ContinuousDynamicExitV2Error(
                                    "duplicate option rows on exact continuous exit session"
                                )
                            if not exact:
                                status = "STRATEGY_EXIT_SESSION_OPTION_SOURCE_MISSING"
                            elif not _exit_row_qualified(exact[0]):
                                status = "STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP"
                                result["strategy_exit_option_mark"] = {
                                    "session_et": exact[0]["session_et"],
                                    "updated_at_utc": exact[0]["updated_at_utc"],
                                    "bid_per_share": exact[0]["bid"],
                                    "two_sided": exact[0]["two_sided"],
                                    "positive_bid_size": exact[0]["positive_bid_size"],
                                    "positive_reported_volume":
                                        exact[0]["positive_reported_volume"],
                                }
                            else:
                                status = "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY"
                                result["strategy_exit_option_mark"] = {
                                    "session_et": exact[0]["session_et"],
                                    "updated_at_utc": exact[0]["updated_at_utc"],
                                    "bid_per_share": exact[0]["bid"],
                                    "displayed_bid_size_contracts":
                                        exact[0]["bid_size_contracts"],
                                    "reported_volume_contracts":
                                        exact[0]["reported_volume_contracts"],
                                    "underlying_price_same_snapshot":
                                        exact[0]["underlying_price_same_snapshot"],
                                    "two_sided": True,
                                    "positive_bid_size": True,
                                    "positive_reported_volume": True,
                                }

        result["strategy_aligned_status"] = status
        counts[status] += 1
        by_year[result["year"]][status] += 1
        output.append(result)

    if len(output) != expected_original_cases:
        raise ContinuousDynamicExitV2Error(
            "continuous dynamic full denominator changed"
        )

    def distribution(values: list[float]) -> dict[str, Any]:
        if not values:
            return {
                "count": 0,
                "min": None,
                "p25": None,
                "median": None,
                "mean": None,
                "p75": None,
                "max": None,
            }
        ordered = sorted(values)
        n = len(ordered)

        def q(p: float) -> float:
            if n == 1:
                return ordered[0]
            pos = (n - 1) * p
            lo = int(math.floor(pos))
            hi = int(math.ceil(pos))
            if lo == hi:
                return ordered[lo]
            frac = pos - lo
            return ordered[lo] * (1.0 - frac) + ordered[hi] * frac

        return {
            "count": n,
            "min": ordered[0],
            "p25": q(0.25),
            "median": q(0.5),
            "mean": statistics.fmean(ordered),
            "p75": q(0.75),
            "max": ordered[-1],
        }

    report = {
        "contract": SCENARIO_CONTRACT,
        "status": "MODELED_CONTINUOUS_DYNAMIC_EXIT_V2_EOD_CALL_SCENARIO",
        "base_scenario_fingerprint": base_scenario["scenario_fingerprint"],
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "original_case_denominator": expected_original_cases,
        "safe_last_signal_session": safe_last_signal_session.isoformat(),
        "strategy_exit_policy": {
            "policy_id": "CONTINUOUS_DYNAMIC_EXIT_V2",
            "time_exit_sessions": 5,
            "case_specific_levels": True,
        },
        "parameterization": {
            "downside_anchor": "MEAN_OF_MEAN_MAE_AND_ABS_NEGATIVE_P25_RETURN",
            "upside_anchor": "MEAN_OF_MEAN_MFE_AND_POSITIVE_P75_RETURN",
            "stop_bounds": [STOP_MIN, STOP_MAX],
            "target_bounds": [TARGET_MIN, TARGET_MAX],
            "minimum_target_to_stop_ratio": MIN_TARGET_TO_STOP,
            "entry_selector_reused": True,
            "exit_engine_re_vetoes_entry": False,
            "current_case_outcome_used": False,
            "current_fold_outcome_used": False,
            "option_exit_source_used_to_set_levels": False,
        },
        "continuous_exit_policy_cases": len(stop_values),
        "stop_distribution": distribution(stop_values),
        "target_distribution": distribution(target_values),
        "source_ready_strategy_aligned_round_trips":
            counts["STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY"],
        "entry_ready_but_exact_strategy_exit_source_gap": (
            counts["STRATEGY_EXIT_SESSION_OPTION_SOURCE_MISSING"]
            + counts["STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP"]
            + counts["STRATEGY_EXIT_OUTSIDE_SELECTED_OPTION_WINDOW"]
        ),
        "stock_exit_not_after_option_eod_entry":
            counts["STOCK_EXIT_NOT_AFTER_OPTION_EOD_ENTRY"],
        "unique_physical_quote_histories_decoded": len(decoded),
        "future_option_exit_used_for_entry_admission": False,
        "provider_standard_100_share_multiplier_is_model_assumption": True,
        "independent_occ_deliverable_multiplier_verified": 0,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "by_status": dict(sorted(counts.items())),
        "by_year": {
            year: dict(sorted(counter.items()))
            for year, counter in by_year.items()
        },
        "cases": output,
    }
    report["scenario_fingerprint"] = _fingerprint(report)
    return report


def build_continuous_paired_diagnostics(
    scenario: dict[str, Any],
    *,
    option_slippage_per_share: str = "0.00",
    option_entry_fee_per_contract: str = "0.65",
    option_exit_fee_per_contract: str = "0.65",
) -> dict[str, Any]:
    _check_signature(scenario, "scenario_fingerprint")
    if (
        scenario.get("contract") != SCENARIO_CONTRACT
        or scenario.get("provider_requests") != 0
        or scenario.get("protected_2026_outcomes_read") != 0
        or scenario.get("strategy_evidence_authority") is not False
    ):
        raise ContinuousDynamicExitV2Error(
            "continuous paired scenario authority changed"
        )

    slip = Decimal(option_slippage_per_share)
    fee_in = Decimal(option_entry_fee_per_contract)
    fee_out = Decimal(option_exit_fee_per_contract)
    if min(slip, fee_in, fee_out) < 0:
        raise ContinuousDynamicExitV2Error("negative modeled option cost")

    rows: list[dict[str, Any]] = []
    for case in scenario["cases"]:
        if (
            case.get("strategy_aligned_status")
            != "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY"
        ):
            continue
        call = case.get("call")
        mark = case.get("strategy_exit_option_mark")
        policy = case.get("continuous_exit_policy")
        if (
            not isinstance(call, dict)
            or not isinstance(call.get("entry"), dict)
            or not isinstance(mark, dict)
            or not isinstance(policy, dict)
        ):
            raise ContinuousDynamicExitV2Error(
                "continuous source-ready pair lost policy/entry/exit"
            )
        ask = Decimal(str(call["entry"]["ask_per_share"]))
        bid = Decimal(str(mark["bid_per_share"]))
        debit = (ask + slip) * Decimal(100) + fee_in
        credit = max(Decimal("0"), bid - slip) * Decimal(100) - fee_out
        pnl = credit - debit
        net_return = pnl / debit
        rows.append({
            "case_id": case["case_id"],
            "year": case["year"],
            "ticker": case["ticker"],
            "stop_fraction": policy["stop_fraction"],
            "target_fraction": policy["target_fraction"],
            "entry_session_et": call["entry"]["session_et"],
            "exit_session_et": mark["session_et"],
            "entry_ask_per_share": str(ask),
            "exit_bid_per_share": str(bid),
            "modeled_net_pnl_per_contract": str(pnl.quantize(Decimal("0.01"))),
            "modeled_net_return_on_premium": str(
                net_return.quantize(Decimal("0.00000001"))
            ),
        })

    def summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        returns = [
            float(Decimal(item["modeled_net_return_on_premium"]))
            for item in items
        ]
        pnls = [
            float(Decimal(item["modeled_net_pnl_per_contract"]))
            for item in items
        ]
        return {
            "pairs": len(items),
            "mean_net_return_on_premium": (
                None if not returns else statistics.fmean(returns)
            ),
            "median_net_return_on_premium": (
                None if not returns else statistics.median(returns)
            ),
            "probability_positive": (
                None
                if not returns
                else sum(value > 0.0 for value in returns) / len(returns)
            ),
            "mean_net_pnl_per_contract": (
                None if not pnls else statistics.fmean(pnls)
            ),
            "median_net_pnl_per_contract": (
                None if not pnls else statistics.median(pnls)
            ),
        }

    by_year: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_year[row["year"]].append(row)

    result = {
        "contract": DIAGNOSTIC_CONTRACT,
        "status": (
            "CONTINUOUS_DYNAMIC_EXIT_V2_PAIRED_EOD_OBSERVATION_DIAGNOSTIC_"
            "NOT_CAUSAL_PORTFOLIO"
        ),
        "scenario_fingerprint": scenario["scenario_fingerprint"],
        "conditioning_on_future_exit_source": True,
        "causal_portfolio_result": False,
        "overall": summary(rows),
        "by_year": {
            year: summary(items) for year, items in sorted(by_year.items())
        },
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "rows": rows,
    }
    result["diagnostic_fingerprint"] = _fingerprint(result)
    return result


def persist_scenario(
    settings: AtlasSettings,
    value: dict[str, Any],
) -> tuple[Path, str]:
    return _persist_signed(
        settings,
        value,
        field="scenario_fingerprint",
        stem=SCENARIO_REL,
        label="CONTINUOUS_DYNAMIC_EXIT_V2_OPTION_SCENARIO",
    )


def persist_replay(
    settings: AtlasSettings,
    value: dict[str, Any],
) -> tuple[Path, str]:
    return _persist_signed(
        settings,
        value,
        field="replay_fingerprint",
        stem=REPLAY_REL,
        label="CONTINUOUS_DYNAMIC_EXIT_V2_OPTION_REPLAY",
    )


def persist_diagnostics(
    settings: AtlasSettings,
    value: dict[str, Any],
) -> tuple[Path, str]:
    return _persist_signed(
        settings,
        value,
        field="diagnostic_fingerprint",
        stem=DIAGNOSTIC_REL,
        label="CONTINUOUS_DYNAMIC_EXIT_V2_PAIRED_DIAGNOSTICS",
    )


def _persist_signed(
    settings: AtlasSettings,
    value: dict[str, Any],
    *,
    field: str,
    stem: str,
    label: str,
) -> tuple[Path, str]:
    import json

    settings.assert_external_storage_binding("options")
    _check_signature(value, field)
    path = settings.resolved_path(f"{stem}_{value[field][:16]}.json")
    raw = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise ContinuousDynamicExitV2Error(f"existing {label} path invalid")
        if path.read_text(encoding="utf-8") != raw:
            raise ContinuousDynamicExitV2Error(f"immutable {label} differs")
        return path, "REUSED_IMMUTABLE_" + label
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(raw)
        handle.flush()
    return path, "WRITTEN_IMMUTABLE_" + label
