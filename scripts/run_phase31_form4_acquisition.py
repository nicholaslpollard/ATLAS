from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase31_acquisition import Phase31AcquisitionError
from packages.backtesting.phase31_acquisition_v3 import Phase31Form4HistoricalAcquisitionV3
from packages.backtesting.phase31_policy import phase31_policy_fingerprint
from packages.backtesting.phase31_source_quality import Phase31SourceQualityError
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.phase31 import MassivePhase31Form4Client
from packages.providers.massive.rest import MassiveRESTClient


def main() -> int:
    print("ATLAS Phase 31 — Full Historical Form-4 Acquisition")
    print(f"Frozen scientific policy fingerprint: {phase31_policy_fingerprint()}")
    print("Scope: 2021-07-16 through 2026-08-11, monthly immutable shards")
    print("Provider mode: authenticated Massive read-only GET")
    print("Raw provider evidence: immutable / retained, including malformed source rows")
    print(
        "Source quality: fail-closed whole-accession global quarantine for impossible chronology "
        "or missing transaction classification"
    )
    print("Raw-shard resumability: existing v2 SHA-bound sidecars remain authoritative")
    print("Probe-window replay: must match the accepted target evidence exactly")
    print("Market outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Broker/order/PAPER/LIVE: DISABLED")
    print()

    settings = load_settings()
    client = MassivePhase31Form4Client(MassiveRESTClient(settings))
    acquisition = Phase31Form4HistoricalAcquisitionV3(settings, client)

    try:
        report = acquisition.run(progress=lambda message: print(f"  {message}"))
    except (Phase31AcquisitionError, Phase31SourceQualityError, ProviderError, OSError, ValueError) as exc:
        print()
        print("Phase 31 full historical Form-4 acquisition: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No market-outcome authority is granted. Do not weaken the frozen source/scientific policy.")
        return 2

    print()
    print("Phase 31 full historical Form-4 acquisition: PASS")
    print(f"Month shards: {report['month_shards']}")
    print(f"Fresh provider shards this run: {report['fresh_provider_shards_this_run']}")
    print(f"Reused raw shards this run: {report['reused_raw_shards_this_run']}")
    print(f"Successful provider pages this run: {report['successful_provider_pages_this_run']}")
    print(f"Raw rows: {report['raw_rows']}")
    print(f"Authoritative rows: {report['authoritative_rows']}")
    print(f"Quarantined rows: {report['quarantined_rows']}")
    print(f"Contaminated accessions: {report['contaminated_accessions']}")
    print(f"Chronology violation seed rows: {report['chronology_violation_seed_rows']}")
    print(f"Missing transaction_code seed rows: {report['missing_transaction_code_seed_rows']}")
    print("Probe reconciliation:")
    for item in report["probe_reconciliation"]:
        print(
            f"  {item['label']}: raw={item['raw_rows']} raw_exact={item['raw_exact']} "
            f"authoritative={item['authoritative_rows']} quarantined={item['quarantined_rows']} "
            f"authoritative_exact={item['authoritative_exact']}"
        )
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected candidate rows read: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print("Provider writes / broker reads-writes / orders / PAPER / LIVE / automation: 0")
    print(f"Report: {report['report_path']}")
    print(f"Pass: {report['pass']}")
    print()
    print("A PASS authorizes predictor-only Form-4 event construction under the frozen policy.")
    print("It does not accept Phase31, grant alpha support, or authorize protected return reads.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
