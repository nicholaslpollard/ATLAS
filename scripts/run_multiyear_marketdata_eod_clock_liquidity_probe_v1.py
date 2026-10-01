from __future__ import annotations

"""Run the zero-provider MarketData EOD clock/liquidity evidence probe."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import PLAN_REL
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import (
    build_marketdata_eod_clock_liquidity_probe,
    persist_marketdata_eod_clock_liquidity_probe,
)
from packages.data.multiyear_observed_option_quote_timeline_v1 import (
    local_verified_quote_body_reader,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    OUTPUT_REL as HANDOFF_REL, _check_signature,
)
from packages.data.multiyear_verified_stock_option_source_casebook_v1 import (
    OUTPUT_REL as CASEBOOK_REL,
)
from packages.simulation.multiyear_historical_execution_requirements_v1 import (
    CONTRACT as PROOF_CONTRACT,
)


class ClockProbeRunnerError(ValueError):
    pass


def _artifact(settings, stem: str, fingerprint: str) -> tuple[Path, dict]:
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise ClockProbeRunnerError("artifact fingerprint is invalid")
    path = settings.resolved_path(f"{stem}_{fingerprint[:16]}.json")
    if path.is_symlink() or not path.is_file():
        raise ClockProbeRunnerError(f"required artifact is unavailable: {path}")
    return path, _read_object(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Probe accepted MarketData EOD bodies for documented same-row "
            "stock/option clock, quote-side liquidity and pre-expiry exit evidence"
        )
    )
    parser.add_argument(
        "--proof-demand",
        type=Path,
        required=True,
        help="Exact multiyear_historical_execution_proof_demand_v1 artifact from the accepted run",
    )
    args = parser.parse_args(argv)

    print("ATLAS MULTIYEAR MARKETDATA EOD CLOCK + LIQUIDITY PROBE V1", flush=True)
    print("  ZERO provider GETs. No historical trade/P&L authority.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")

        proof_path = (
            args.proof_demand
            if args.proof_demand.is_absolute()
            else settings.resolved_path(args.proof_demand)
        )
        if proof_path.is_symlink() or not proof_path.is_file():
            raise ClockProbeRunnerError("proof-demand artifact is unavailable")
        proof = _read_object(proof_path)
        _check_signature(proof, "proof_demand_fingerprint")
        if proof.get("contract") != PROOF_CONTRACT:
            raise ClockProbeRunnerError("proof-demand contract changed")

        casebook_path, casebook = _artifact(
            settings, CASEBOOK_REL, proof["casebook_fingerprint"]
        )
        _check_signature(casebook, "casebook_fingerprint")
        handoff_path, handoff = _artifact(
            settings, HANDOFF_REL, casebook["handoff_fingerprint"]
        )
        _check_signature(handoff, "handoff_fingerprint")
        plan_path, plan = _artifact(
            settings, PLAN_REL, handoff["quote_plan_fingerprint"]
        )
        _check_signature(plan, "plan_fingerprint")

        print(f"  proof_demand={proof_path}", flush=True)
        print(f"  casebook={casebook_path}", flush=True)
        print(f"  handoff={handoff_path}", flush=True)
        print(f"  quote_plan={plan_path}", flush=True)

        body_reader = local_verified_quote_body_reader(settings, plan)
        report = build_marketdata_eod_clock_liquidity_probe(
            plan,
            handoff,
            casebook,
            proof,
            read_verified_body=body_reader,
        )
        output_path, action = persist_marketdata_eod_clock_liquidity_probe(
            settings, report
        )

        print(f"  probe={action} / {output_path}", flush=True)
        print(
            "  "
            f"dated_pair_work_items={report['dated_pair_work_items']} "
            f"unique_histories_decoded={report['unique_verified_physical_histories_decoded']} "
            f"same_row_clock_candidates={report['documented_same_row_clock_candidates']} "
            f"positive_size_and_volume_candidates="
            f"{report['entry_exit_positive_size_and_volume_candidates']} "
            f"forced_pre_expiry_exit_candidates="
            f"{report['forced_pre_expiry_exit_candidates']} "
            f"non_deliverable_gates_candidate_pass="
            f"{report['non_deliverable_gates_candidate_pass']} "
            f"clock_liquidity_or_exit_gap="
            f"{report['eod_clock_or_liquidity_or_exit_policy_gap']}",
            flush=True,
        )
        for year, values in report["by_year"].items():
            print(f"  year={year} {values}", flush=True)
        print(
            "  COMPLETE provider_requests=0 historical_option_trades_admitted=0 "
            "historical_account_pnl=NULL deliverable_multiplier_verified=0",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"CLOCK + LIQUIDITY PROBE STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
