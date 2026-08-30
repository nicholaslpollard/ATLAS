from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_xbrl_pit_audit import XBRL_PIT_REPORT_RELATIVE
from packages.core.settings import load_settings


def _load_report() -> tuple[Path, dict]:
    settings = load_settings()
    derived_root = settings.resolved_path(settings.data.paths.derived)
    path = derived_root / XBRL_PIT_REPORT_RELATIVE
    if not path.is_file():
        raise FileNotFoundError(f"PIT audit report not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"PIT audit report root is not an object: {path}")
    return path, value


def main() -> int:
    try:
        path, report = _load_report()
    except (OSError, ValueError) as exc:
        print(f"PIT identity diagnostic: NOT AVAILABLE — {exc}")
        return 2

    status_counts: Counter[str] = Counter()
    no_eligible_reason_counts: Counter[str] = Counter()
    ambiguous_security_types: Counter[str] = Counter()
    ambiguous_candidate_counts: Counter[int] = Counter()
    low_issuers: list[dict] = []

    for issuer in report.get("issuer_reports") or []:
        if not isinstance(issuer, dict):
            continue
        per_issuer_status: Counter[str] = Counter()
        ambiguous_examples: list[str] = []
        for filing in issuer.get("filings") or []:
            if not isinstance(filing, dict):
                continue
            identity = filing.get("identity")
            if not isinstance(identity, dict):
                continue
            status = str(identity.get("status") or "UNKNOWN")
            status_counts[status] += 1
            per_issuer_status[status] += 1
            if status == "NO_ELIGIBLE_PIT_INSTRUMENT":
                for item in identity.get("mapping_evidence") or []:
                    if isinstance(item, dict):
                        no_eligible_reason_counts[str(item.get("status") or "UNKNOWN")] += 1
            elif status == "AMBIGUOUS_MULTIPLE_PIT_INSTRUMENTS":
                instruments = [item for item in identity.get("instruments") or [] if isinstance(item, dict)]
                ambiguous_candidate_counts[len(instruments)] += 1
                parts: list[str] = []
                for item in instruments:
                    security_type = str(item.get("security_type") or "<missing>")
                    ticker = str(item.get("ticker") or "?")
                    ambiguous_security_types[security_type] += 1
                    parts.append(f"{ticker}:{security_type}")
                if parts and len(ambiguous_examples) < 3:
                    ambiguous_examples.append(
                        f"{filing.get('decision_session')}=" + ",".join(parts)
                    )

        mapping_count = int(issuer.get("unambiguous_mapping_count") or 0)
        if mapping_count < 3:
            low_issuers.append(
                {
                    "issuer_cik": str(issuer.get("issuer_cik") or ""),
                    "entity_name": str(issuer.get("entity_name") or ""),
                    "mapping_count": mapping_count,
                    "statuses": dict(sorted(per_issuer_status.items())),
                    "ambiguous_examples": ambiguous_examples,
                }
            )

    print("ATLAS XBRL PIT identity failure diagnostic")
    print(f"Report: {path}")
    print(f"Audit status: {report.get('status')}")
    print(f"Unambiguous mappings: {report.get('unambiguous_identity_mappings')}")
    print(f"Issuers with >=3 mappings: {report.get('issuers_with_3_unambiguous_mappings')}")
    print(f"Identity status counts: {dict(sorted(status_counts.items()))}")
    print(f"No-eligible evidence reasons: {dict(sorted(no_eligible_reason_counts.items()))}")
    print(f"Ambiguous candidate-count distribution: {dict(sorted(ambiguous_candidate_counts.items()))}")
    print(f"Ambiguous security-type counts: {dict(sorted(ambiguous_security_types.items()))}")
    print()
    print(f"Issuers below frozen >=3 mapping requirement: {len(low_issuers)}")
    for issuer in sorted(low_issuers, key=lambda row: (row["mapping_count"], row["issuer_cik"])):
        print(
            f"- CIK {issuer['issuer_cik']} | mappings={issuer['mapping_count']} | "
            f"{issuer['entity_name']} | statuses={issuer['statuses']}"
        )
        for example in issuer["ambiguous_examples"]:
            print(f"    ambiguous: {example}")

    print()
    print("This diagnostic reads only the existing source-only audit report; it performs no provider, market-outcome, protected-return, broker, or trading reads/writes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
