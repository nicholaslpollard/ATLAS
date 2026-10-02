from __future__ import annotations

"""Run the zero-provider causal EOD standard-contract admission audit."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import (
    CONTRACT as EOD_PROBE_CONTRACT,
)
from packages.data.multiyear_marketdata_eod_standard_contract_admission_v1 import (
    build_eod_standard_contract_admission_audit,
    local_standard_chain_verifier,
    persist_eod_standard_contract_admission_audit,
)
from packages.data.multiyear_option_quote_bridge_v1 import (
    OUTPUT_REL as SELECTION_REL,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    OUTPUT_REL as HANDOFF_REL,
    _check_signature,
)


class StandardAdmissionRunnerError(ValueError):
    pass


def _artifact(settings, stem: str, fingerprint: str) -> tuple[Path, dict]:
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise StandardAdmissionRunnerError("artifact fingerprint is invalid")
    path = settings.resolved_path(f"{stem}_{fingerprint[:16]}.json")
    if path.is_symlink() or not path.is_file():
        raise StandardAdmissionRunnerError(
            f"required artifact is unavailable: {path}"
        )
    return path, _read_object(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit causal EOD entry readiness using verified MarketData "
            "standard-filter historical chain lineage"
        )
    )
    parser.add_argument(
        "--probe",
        type=Path,
        required=True,
        help=(
            "Exact multiyear_marketdata_eod_clock_liquidity_probe_v1 artifact "
            "from the accepted source run"
        ),
    )
    args = parser.parse_args(argv)

    print(
        "ATLAS MULTIYEAR MARKETDATA EOD STANDARD-CONTRACT ADMISSION AUDIT V1",
        flush=True,
    )
    print(
        "  ZERO provider GETs. Future exit liquidity is NOT used for entry admission.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")

        probe_path = (
            args.probe
            if args.probe.is_absolute()
            else settings.resolved_path(args.probe)
        )
        if probe_path.is_symlink() or not probe_path.is_file():
            raise StandardAdmissionRunnerError("probe artifact is unavailable")
        probe = _read_object(probe_path)
        _check_signature(probe, "probe_fingerprint")
        if probe.get("contract") != EOD_PROBE_CONTRACT:
            raise StandardAdmissionRunnerError("probe contract changed")

        handoff_path, handoff = _artifact(
            settings,
            HANDOFF_REL,
            probe["source_handoff_fingerprint"],
        )
        _check_signature(handoff, "handoff_fingerprint")
        selection_path, selection = _artifact(
            settings,
            SELECTION_REL,
            handoff["selection_fingerprint"],
        )
        _check_signature(selection, "selection_fingerprint")

        print(f"  probe={probe_path}", flush=True)
        print(f"  handoff={handoff_path}", flush=True)
        print(f"  selection={selection_path}", flush=True)

        report = build_eod_standard_contract_admission_audit(
            selection,
            handoff,
            probe,
            verify_standard_chain=local_standard_chain_verifier(settings),
        )
        output_path, action = persist_eod_standard_contract_admission_audit(
            settings, report
        )

        print(f"  audit={action} / {output_path}", flush=True)
        print(
            "  "
            f"dated_pair_work_items={report['dated_pair_work_items']} "
            f"unique_verified_selected_chain_requests="
            f"{report['unique_verified_selected_chain_requests']} "
            f"provider_standard_at_selection="
            f"{report['provider_standard_at_selection']} "
            f"entry_eod_clock_liquidity_source_shape="
            f"{report['entry_eod_clock_liquidity_source_shape']} "
            f"causal_entry_ready_model_source_shape="
            f"{report['causal_entry_ready_model_source_shape']} "
            f"later_exit_eod_clock_liquidity_source_shape="
            f"{report['later_exit_eod_clock_liquidity_source_shape']} "
            f"entry_and_later_exit_model_source_shape="
            f"{report['entry_and_later_exit_model_source_shape']}",
            flush=True,
        )
        for year, values in report["by_year"].items():
            print(f"  year={year} {values}", flush=True)
        print(
            "  COMPLETE provider_requests=0 future_exit_used_for_entry_admission=False "
            "historical_option_trades_admitted=0 historical_account_pnl=NULL "
            "independent_occ_deliverable_multiplier_verified=0",
            flush=True,
        )
        print(
            "  NOTE provider-standard 100-share treatment is a modeled EOD "
            "multiplier assumption, not independent OCC deliverable proof.",
            flush=True,
        )
        return 0
    except (
        OSError, ValueError, TypeError, KeyError, RuntimeError,
        StandardAdmissionRunnerError,
    ) as exc:
        print(
            f"EOD STANDARD ADMISSION AUDIT STOPPED: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            "  No provider fallback is authorized. Preserve all existing source receipts.",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
