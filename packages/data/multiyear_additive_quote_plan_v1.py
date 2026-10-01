from __future__ import annotations

"""Add newly PIT-selectable option identities without rewriting accepted quote demand.

Existing selected case/right memberships retain their exact immutable request
identity and window. Only case/rights that become selectable after additional
PIT chain source acquisition receive a new demand frozen at the current Starter
window. This prevents paid churn and keeps old 2021 source lineage auditable.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, date, datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import (
    CONTRACT as QUOTE_CONTRACT, PLAN_REL, _write_new, freeze_quote_demand,
)
from packages.data.multiyear_option_quote_bridge_v1 import (
    CONTRACT as SELECTION_CONTRACT,
    OUTPUT_REL as SELECTION_OUTPUT_REL,
)

CONTRACT = "atlas-multiyear-additive-option-quote-demand-v1"
EASTERN = ZoneInfo("America/New_York")


class AdditiveQuotePlanError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AdditiveLineageNode:
    plan_path: Path | None
    plan: dict[str, Any]
    selection_path: Path | None
    selection: dict[str, Any]


def _signed(value: dict[str, Any], field: str) -> None:
    if not isinstance(value, dict):
        raise AdditiveQuotePlanError("signed source must be an object")
    unsigned = dict(value)
    signature = unsigned.pop(field, None)
    if not isinstance(signature, str) or signature != _fingerprint(unsigned):
        raise AdditiveQuotePlanError(f"{field} mismatch")


def _index_selection(
    selection: dict[str, Any], *, expected_original_cases: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    _signed(selection, "selection_fingerprint")
    cases = selection.get("cases")
    coverage = selection.get("coverage")
    if (
        selection.get("contract") != SELECTION_CONTRACT
        or selection.get("status") != "OFFLINE_PIT_CONTRACT_IDENTITIES_ONLY"
        or selection.get("original_case_denominator") != expected_original_cases
        or selection.get("right_policy") != "both"
        or selection.get("original_right_memberships") != expected_original_cases * 2
        or not isinstance(cases, list)
        or selection.get("selected_case_right_memberships") != len(cases)
        or not isinstance(coverage, list)
        or len(coverage) != expected_original_cases * 2
        or selection.get("provider_requests") != 0
        or selection.get("historical_0935_option_bid_ask_verified") is not False
        or selection.get("verified_standard_deliverable_or_option_pnl") is not False
        or selection.get("2026_protected_outcomes_read") != 0
        or selection.get("strategy_authority") is not False
    ):
        raise AdditiveQuotePlanError("selection denominator or authority changed")
    by_case = {x["case_id"]: x for x in cases}
    by_slot = {
        f'{x["case_id"]}:{("C" if x["right"] == "call" else "P")}': x
        for x in coverage
    }
    if (
        len(by_case) != len(cases)
        or len(by_slot) != len(coverage)
        or set(by_case) - set(by_slot)
    ):
        raise AdditiveQuotePlanError("selection case/right identity duplicated or missing")
    return by_case, by_slot


def _validate_base_plan(
    plan: dict[str, Any], selected: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    _signed(plan, "plan_fingerprint")
    requests = plan.get("requests")
    memberships = plan.get("memberships")
    if (
        plan.get("contract") != QUOTE_CONTRACT
        or plan.get("status") != "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS"
        or not isinstance(requests, list)
        or not isinstance(memberships, list)
        or plan.get("requested_case_denominator") != len(selected)
        or plan.get("unique_physical_quote_queries") != len(requests)
        or len(memberships) != len(selected)
        or plan.get("provider_requests") != 0
        or plan.get("strategy_authority") is not False
    ):
        raise AdditiveQuotePlanError("base quote plan denominator or authority changed")
    by_req = {x["request_identity"]: x for x in requests}
    by_mem = {x["case_id"]: x for x in memberships}
    if (
        len(by_req) != len(requests)
        or len(by_mem) != len(memberships)
        or set(by_mem) != set(selected)
    ):
        raise AdditiveQuotePlanError("base quote request/membership identity changed")
    for identity, request in by_req.items():
        query = {
            "option_symbol": request["option_symbol"],
            "from_inclusive": request["from_inclusive"],
            "to_exclusive": request["to_exclusive"],
        }
        if (
            identity != _fingerprint({"contract": QUOTE_CONTRACT, "query": query})
            or sorted(request.get("member_case_ids", [])) != sorted(
                m["case_id"] for m in memberships
                if m["request_identity"] == identity
            )
        ):
            raise AdditiveQuotePlanError("base exact request fingerprint/membership changed")
    nonrequest_dispositions = {
        "ORIGINAL_DECISION_OUTSIDE_STARTER_FIVE_YEAR_WINDOW",
        "ORIGINAL_DECISION_AFTER_LAST_COMPLETED_SESSION",
        "NO_CLOSED_SOURCE_PERIOD",
    }
    for case_id, member in by_mem.items():
        chosen = selected[case_id]
        if (
            member.get("option_symbol") != chosen.get("option_symbol")
            or member.get("ticker") != chosen.get("ticker")
        ):
            raise AdditiveQuotePlanError("base selected contract/request mapping changed")
        disposition = member.get("disposition")
        identity = member.get("request_identity")
        if disposition == "SOURCE_DEMAND_READY":
            request = by_req.get(identity)
            if (
                request is None
                or request.get("option_symbol") != chosen.get("option_symbol")
                or case_id not in request.get("member_case_ids", [])
            ):
                raise AdditiveQuotePlanError(
                    "base selected contract/request mapping changed"
                )
        elif (
            disposition not in nonrequest_dispositions
            or identity is not None
        ):
            raise AdditiveQuotePlanError(
                "base selected source-gap disposition/request mapping changed"
            )
    return by_req, by_mem


_STABLE_CASE_FIELDS = (
    "case_id", "original_case_id", "ticker", "option_symbol", "right",
    "expiration", "decision_at_utc", "selected_at_utc",
    "accepted_stock_source_sha256", "frozen_native_raw_open",
    "frozen_structural_strike", "source_request_identity", "source_body_sha256",
    "prior_24h_news_count", "prior_7d_news_count", "source_selection_status",
    "not_an_option_fill_or_validated_deliverable",
)


def _validate_selection_extension(
    base_selection: dict[str, Any],
    expanded_selection: dict[str, Any],
    *,
    expected_original_cases: int,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    old, old_coverage = _index_selection(
        base_selection, expected_original_cases=expected_original_cases,
    )
    expanded, expanded_coverage = _index_selection(
        expanded_selection, expected_original_cases=expected_original_cases,
    )
    if set(old) - set(expanded):
        raise AdditiveQuotePlanError("previously selected PIT contract disappeared")
    if set(old_coverage) != set(expanded_coverage):
        raise AdditiveQuotePlanError("full case/right denominator changed")
    for case_id, prior in old.items():
        current = expanded[case_id]
        if any(prior.get(field) != current.get(field) for field in _STABLE_CASE_FIELDS):
            raise AdditiveQuotePlanError("previously selected PIT contract/source changed")
        before = old_coverage[case_id]
        after = expanded_coverage[case_id]
        if (
            before.get("option_symbol") != after.get("option_symbol")
            or before.get("right") != after.get("right")
            or before.get("status") != after.get("status")
        ):
            raise AdditiveQuotePlanError("previous selected coverage row changed")
    return old, old_coverage, expanded, expanded_coverage


def discover_additive_quote_lineage(
    settings: AtlasSettings,
    root_selection: dict[str, Any],
    root_plan: dict[str, Any],
    *,
    root_plan_path: Path | None = None,
    expected_original_cases: int = 14902,
) -> list[AdditiveLineageNode]:
    """Return the unique signed carry-forward chain rooted at the frozen base plan.

    Every child must extend the exact parent plan and the exact selection that parent
    represents. A fork, missing referenced selection, signature drift or broken parent
    link fails closed. Unrelated/orphan manifests are ignored.
    """
    settings.assert_external_storage_binding("options")
    root_selected, _ = _index_selection(
        root_selection, expected_original_cases=expected_original_cases,
    )
    _validate_base_plan(root_plan, root_selected)

    manifest_root = settings.resolved_path("data/options/manifests")
    if not manifest_root.is_dir():
        raise AdditiveQuotePlanError("options manifest directory is unavailable")

    plan_prefix = Path(PLAN_REL).name + "_"
    docs_by_fp: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(manifest_root.glob(plan_prefix + "*.json")):
        try:
            doc = _read_object(path)
        except (OSError, ValueError, TypeError):
            continue
        if doc.get("additive_contract") != CONTRACT:
            continue
        _signed(doc, "plan_fingerprint")
        fp = doc["plan_fingerprint"]
        if (
            doc.get("contract") != QUOTE_CONTRACT
            or doc.get("status") != "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS"
            or doc.get("provider_requests") != 0
            or doc.get("strategy_authority") is not False
            or doc.get("historical_fill_or_pnl_authority") is not False
            or doc.get("prior_selected_contracts_changed") != 0
            or doc.get("base_exact_windows_preserved") is not True
            or not isinstance(doc.get("base_quote_plan_fingerprint"), str)
            or not isinstance(doc.get("base_selection_fingerprint"), str)
            or not isinstance(doc.get("expanded_selection_fingerprint"), str)
        ):
            raise AdditiveQuotePlanError("additive plan authority/lineage changed")
        prior = docs_by_fp.get(fp)
        if prior is not None and prior[0] != path:
            raise AdditiveQuotePlanError("duplicate additive plan fingerprint files")
        docs_by_fp[fp] = (path, doc)

    lineage = [
        AdditiveLineageNode(
            plan_path=root_plan_path,
            plan=root_plan,
            selection_path=None,
            selection=root_selection,
        )
    ]
    current_plan = root_plan
    current_selection = root_selection
    seen = {root_plan["plan_fingerprint"]}
    previous_day: date | None = None

    while True:
        parent_fp = current_plan["plan_fingerprint"]
        children_all = [
            (path, doc)
            for path, doc in docs_by_fp.values()
            if doc.get("base_quote_plan_fingerprint") == parent_fp
        ]
        incompatible = [
            doc for _, doc in children_all
            if doc.get("base_selection_fingerprint")
                != current_selection["selection_fingerprint"]
        ]
        if incompatible:
            raise AdditiveQuotePlanError(
                "additive child references parent plan with a different base selection"
            )
        children = [
            (path, doc) for path, doc in children_all
            if doc.get("base_selection_fingerprint")
                == current_selection["selection_fingerprint"]
        ]
        if not children:
            break
        if len(children) != 1:
            raise AdditiveQuotePlanError(
                "ambiguous additive quote-plan lineage fork"
            )
        plan_path, child = children[0]
        child_fp = child["plan_fingerprint"]
        if child_fp in seen:
            raise AdditiveQuotePlanError("additive quote-plan lineage cycle")
        seen.add(child_fp)

        selection_fp = child["expanded_selection_fingerprint"]
        selection_path = settings.resolved_path(
            f"{SELECTION_OUTPUT_REL}_{selection_fp[:16]}.json"
        )
        if not selection_path.is_file():
            raise AdditiveQuotePlanError(
                "additive plan referenced selection artifact is missing"
            )
        selection = _read_object(selection_path)
        _signed(selection, "selection_fingerprint")
        if selection["selection_fingerprint"] != selection_fp:
            raise AdditiveQuotePlanError(
                "additive plan referenced selection fingerprint changed"
            )

        old, _, expanded, _ = _validate_selection_extension(
            current_selection,
            selection,
            expected_original_cases=expected_original_cases,
        )
        _validate_base_plan(child, expanded)
        if (
            child.get("preserved_selected_case_rights") != len(old)
            or child.get("newly_selected_case_rights")
                != len(expanded) - len(old)
            or child.get("base_physical_quote_queries")
                != current_plan.get("unique_physical_quote_queries")
            or child.get("requested_case_denominator") != len(expanded)
        ):
            raise AdditiveQuotePlanError("additive plan carry-forward counts changed")

        try:
            child_day = date.fromisoformat(str(child["additive_planning_day_et"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise AdditiveQuotePlanError("invalid additive planning day") from exc
        if previous_day is not None and child_day < previous_day:
            raise AdditiveQuotePlanError("additive planning day moved backward")
        previous_day = child_day

        lineage.append(
            AdditiveLineageNode(
                plan_path=plan_path,
                plan=child,
                selection_path=selection_path,
                selection=selection,
            )
        )
        current_plan = child
        current_selection = selection

    return lineage


def build_additive_quote_plan(
    base_selection: dict[str, Any],
    base_plan: dict[str, Any],
    expanded_selection: dict[str, Any],
    *,
    asof_utc: datetime,
    last_completed_session: date,
    expected_original_cases: int = 14902,
) -> dict[str, Any]:
    """Preserve every base exact query and add demand only for newly selected slots."""
    old, old_coverage, expanded, expanded_coverage = _validate_selection_extension(
        base_selection,
        expanded_selection,
        expected_original_cases=expected_original_cases,
    )
    base_requests, base_members = _validate_base_plan(base_plan, old)

    new_ids = sorted(set(expanded) - set(old))
    if not new_ids:
        # Quote demand is identical even if missing-chain coverage statuses improved.
        return deepcopy(base_plan)

    if not isinstance(asof_utc, datetime) or asof_utc.tzinfo is None:
        raise AdditiveQuotePlanError("aware additive planning as-of required")
    planning_day = asof_utc.astimezone(EASTERN).date()
    stable_asof = datetime.combine(
        planning_day, dt_time.min, tzinfo=EASTERN
    ).astimezone(UTC)
    fresh = freeze_quote_demand(
        [expanded[x] for x in new_ids],
        asof_utc=stable_asof,
        last_completed_session=last_completed_session,
    )
    fresh_members = {x["case_id"]: x for x in fresh["memberships"]}
    if set(fresh_members) != set(new_ids):
        raise AdditiveQuotePlanError("new selection/fresh demand membership changed")
    combined_requests = {k: deepcopy(v) for k, v in base_requests.items()}
    for request in fresh["requests"]:
        identity = request["request_identity"]
        existing = combined_requests.get(identity)
        if existing is None:
            combined_requests[identity] = deepcopy(request)
        else:
            for field in ("option_symbol", "from_inclusive", "to_exclusive"):
                if existing[field] != request[field]:
                    raise AdditiveQuotePlanError("same exact request identity changed query")
            existing["member_case_ids"] = sorted(set(
                existing["member_case_ids"] + request["member_case_ids"]
            ))

    memberships = [deepcopy(base_members[x]) for x in sorted(base_members)]
    memberships.extend(deepcopy(fresh_members[x]) for x in new_ids)
    requests = sorted(combined_requests.values(), key=lambda x: x["request_identity"])
    for request in requests:
        request["member_case_ids"] = sorted(set(request["member_case_ids"]))
    membership_by_request: dict[str, list[str]] = {}
    for member in memberships:
        identity = member.get("request_identity")
        if identity is None:
            if member.get("disposition") == "SOURCE_DEMAND_READY":
                raise AdditiveQuotePlanError("eligible membership lost exact request")
            continue
        if member.get("disposition") != "SOURCE_DEMAND_READY":
            raise AdditiveQuotePlanError("ineligible membership gained exact request")
        membership_by_request.setdefault(identity, []).append(member["case_id"])
    if any(
        sorted(request["member_case_ids"])
        != sorted(membership_by_request.get(request["request_identity"], []))
        for request in requests
    ):
        raise AdditiveQuotePlanError("combined physical request membership mismatch")

    result = {
        "contract": QUOTE_CONTRACT,
        "additive_contract": CONTRACT,
        "status": "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS",
        "asof_utc": fresh["asof_utc"],
        "additive_planning_day_et": planning_day.isoformat(),
        "rolling_five_year_floor": fresh["rolling_five_year_floor"],
        "last_completed_session": fresh["last_completed_session"],
        "requested_case_denominator": len(expanded),
        "unique_physical_quote_queries": len(requests),
        "memberships": sorted(memberships, key=lambda x: x["case_id"]),
        "requests": requests,
        "provider_requests": 0,
        "strategy_authority": False,
        "no_future_liquidity_contract_selection": True,
        "base_selection_fingerprint": base_selection["selection_fingerprint"],
        "expanded_selection_fingerprint": expanded_selection["selection_fingerprint"],
        "base_quote_plan_fingerprint": base_plan["plan_fingerprint"],
        "preserved_selected_case_rights": len(old),
        "newly_selected_case_rights": len(new_ids),
        "base_physical_quote_queries": len(base_requests),
        "added_physical_quote_queries": len(requests) - len(base_requests),
        "new_selected_outside_current_quote_window": sum(
            x.get("disposition") != "SOURCE_DEMAND_READY"
            for x in fresh["memberships"]
        ),
        "prior_selected_contracts_changed": 0,
        "base_exact_windows_preserved": True,
        "new_exact_windows_use_current_rolling_floor": True,
        "historical_fill_or_pnl_authority": False,
    }
    result["plan_fingerprint"] = _fingerprint(result)
    return result


def persist_additive_quote_plan(
    settings: AtlasSettings, report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _signed(report, "plan_fingerprint")
    if report.get("additive_contract") != CONTRACT:
        raise AdditiveQuotePlanError("not an additive quote plan")
    path = settings.resolved_path(
        f"{PLAN_REL}_{report['plan_fingerprint'][:16]}.json"
    )
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise AdditiveQuotePlanError("immutable additive quote plan changed")
        try:
            prior = _read_object(path)
        except (OSError, ValueError, TypeError) as exc:
            raise AdditiveQuotePlanError(
                "immutable additive quote plan unreadable or changed"
            ) from exc
        if prior != report:
            raise AdditiveQuotePlanError("immutable additive quote plan changed")
        return path, "REUSED_IDENTICAL_ADDITIVE_QUOTE_PLAN"
    _write_new(path, report)
    return path, "WRITTEN_IMMUTABLE_ADDITIVE_QUOTE_PLAN"
