from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from packages.core.settings import load_settings
from packages.validation.cumulative_acceptance import CumulativeFoundationIndependentValidator
from packages.validation.cumulative_foundation import CumulativeFoundationAuditError
from packages.validation.cumulative_policy import cumulative_policy_fingerprint
from packages.validation.cumulative_stage_lineage import CumulativeFoundationRetainedStageAuditor


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _print_component_summary(root: Path) -> None:
    daily = _load(root / "01_daily_canonical.json")
    if daily:
        print("  canonical daily integrity:")
        print(f"    rows:                         {int(daily.get('row_count', 0)):,}")
        print(f"    symbols:                      {int(daily.get('symbol_count', 0)):,}")
        print(f"    sessions:                     {int(daily.get('session_count', 0)):,}")
        print(f"    duplicate market keys:        {int(daily.get('duplicate_market_keys', 0)):,}")
        print(f"    invalid OHLC rows:             {int(daily.get('invalid_ohlc_rows', 0)):,}")
        print(f"    invalid volume rows:           {int(daily.get('invalid_volume_rows', 0)):,}")
        print(f"    missing exchange sessions:     {len(daily.get('missing_sessions', [])):,}")
        print(f"    partition-date mismatches:     {int(daily.get('partition_date_mismatch_rows', 0)):,}")
        print(f"    pass:                          {daily.get('pass')}")

    seam = _load(root / "02_provider_seam.json")
    if seam:
        print("  provider seam / authority:")
        print(f"    last Alpaca-era session:       {seam.get('last_pre_seam_session')}")
        print(f"    first Massive session:         {seam.get('first_massive_session')}")
        print(f"    exchange-calendar contiguous:  {seam.get('exchange_calendar_contiguous')}")
        print(f"    Gate 8 promotion checks:       {all(dict(seam.get('gate8_checks') or {}).values())}")
        print(f"    pass:                          {seam.get('pass')}")

    intraday = _load(root / "03_intraday_lineage.json")
    if intraday:
        print("  intraday lineage:")
        for tf in ("1m", "1h", "4h"):
            item = dict(intraday.get(tf) or {})
            print(
                f"    {tf}: partitions={int(item.get('partition_count', 0)):,} "
                f"first={item.get('first_partition_date')} pre-2021={int(item.get('pre_ticker_origin_partition_count', 0)):,} "
                f"pass={item.get('pass')}"
            )

    manifests = _load(root / "04_feature_manifests.json")
    if manifests:
        print("  feature manifest/hash lineage:")
        for tf in ("1d", "1h", "4h"):
            item = dict(manifests.get(tf) or {})
            extra = ""
            if tf == "1d":
                extra = (
                    f" lifecycle={int(item.get('lifecycle_event_session_count', 0)):,}"
                    f" state-transitions={int(item.get('adjacent_state_transition_count', 0)):,}"
                )
            print(
                f"    {tf}: checked={int(item.get('checked_manifest_count', 0)):,} "
                f"failures={int(item.get('failure_count', 0)):,} "
                f"pre-origin={int(item.get('forbidden_pre_origin_manifest_count', 0)):,}{extra} "
                f"pass={item.get('pass')}"
            )
            if item.get("failure_samples"):
                print(f"      first failure: {list(item['failure_samples'])[0]}")

    bars = _load(root / "05_intraday_reconciliation.json")
    if bars:
        print("  1m -> 1h/4h independent reconstruction:")
        print(f"    sampled sessions:              {int(bars.get('sample_session_count', 0)):,}")
        print(f"    checked derived bars:          {int(bars.get('checked_derived_bars', 0)):,}")
        print(f"    mismatches:                    {int(bars.get('mismatch_count', 0)):,}")
        print(f"    pass:                          {bars.get('pass')}")

    features = _load(root / "06_independent_feature_replay.json")
    if features:
        print("  independent 33-feature replay:")
        for tf in ("1d", "1h", "4h"):
            item = dict(features.get(tf) or {})
            print(
                f"    {tf}: symbols={int(item.get('sample_symbol_count', 0)):,} "
                f"comparisons={int(item.get('numeric_comparisons', 0)):,} "
                f"mismatches={int(item.get('mismatch_count', 0)):,} pass={item.get('pass')}"
            )

    regimes = _load(root / "07_regime_lineage.json")
    if regimes:
        print("  split-origin regime lineage:")
        print(f"    market/sector origin:           {regimes.get('market_sector_origin')}")
        print(f"    ticker origin:                  {regimes.get('ticker_origin')}")
        print(f"    manifest current:               {regimes.get('manifest_contract_current')}")
        print(f"    snapshot current:               {regimes.get('snapshot_contract_current')}")
        print(f"    split-origin provenance:        {regimes.get('split_origin_provenance_present')}")
        print(f"    pass:                           {regimes.get('pass')}")

    historical = _load(root / "08_accepted_historical_evidence.json")
    if historical:
        print("  historical identity / extension evidence:")
        identity_checks = dict(historical.get("identity_checks") or {})
        false_identity = [name for name, value in identity_checks.items() if not value]
        print(f"    identity rows:                  {int(historical.get('identity_rows', 0)):,}")
        print(f"    identity checks all pass:       {bool(identity_checks) and all(identity_checks.values())}")
        print(f"    identity failed checks:         {false_identity}")
        print(f"    extension accepted:             {historical.get('accepted')}")
        print(f"    Phase 10 authority preserved:   {historical.get('phase10_authority_reference_present')}")
        print(f"    pass:                           {historical.get('pass')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the read-only ATLAS 2016-current cumulative data and lineage integrity audit."
    )
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        default=None,
        help="Optional final canonical 1d session. Defaults to the latest local canonical daily partition.",
    )
    args = parser.parse_args()
    settings = load_settings()
    auditor = CumulativeFoundationRetainedStageAuditor(settings)

    print("ATLAS Cumulative Data & Lineage Integrity Audit v1")
    print(
        "  safety: read-only analytical audit; no canonical/feature/regime/model/broker writes; "
        "no external provider calls"
    )
    print(f"  preregistered policy fingerprint: {cumulative_policy_fingerprint()}")
    print("  audit coverage: Alpaca daily history -> identity -> provider seam -> Massive -> bars -> features -> regimes")

    try:
        acceptance = auditor.run(
            end_date=args.end_date,
            progress=lambda message: print(f"  {message}"),
        )
    except CumulativeFoundationAuditError as exc:
        print(f"  cumulative audit disposition: FAIL ({exc})")
        _print_component_summary(auditor.root)
        acceptance_path = auditor.root / "cumulative_foundation_acceptance.json"
        if acceptance_path.is_file():
            print(f"  acceptance report: {acceptance_path.resolve()}")
        raise SystemExit(1) from None

    print("  independent validator: rechecking component hashes, policy, authority, and zero-write guarantees")
    validation = CumulativeFoundationIndependentValidator(settings).run()
    _print_component_summary(auditor.root)
    print("  independent final checks:")
    for name, value in dict(validation["checks"]).items():
        print(f"    {name}: {value}")
    print("  final disposition:")
    print(f"    cumulative foundation accepted: {acceptance['pass']}")
    print(f"    history coverage:               {acceptance['history_start']} -> {acceptance['history_end']}")
    print(f"    foundation fingerprint:         {acceptance['source_fingerprint']}")
    print("    new post-hoc thresholds:        False")
    print("    execution authority changed:    False")
    print(f"  final acceptance report: {acceptance['acceptance_path']}")
    print(f"  independent validation report: {validation['report_path']}")
    print("  ATLAS Cumulative Data & Lineage Integrity: PASS")
    print("  Phase 15 Broker Execution and Outcome Learning: RESUME ONLY AFTER THIS ACCEPTANCE IS MERGED")


if __name__ == "__main__":
    main()
