from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_identity import AlpacaBackfillIdentityBuilder


def main() -> None:
    settings = load_settings()
    report = AlpacaBackfillIdentityBuilder(settings).run()

    print("ATLAS Historical Backfill Gate 4 Identity Evidence Materialization")
    print("  safety: retained raw evidence only; no provider fetch; canonical history untouched")
    print(f"  retained corporate-action pages: {report.retained_corporate_action_pages:,}")
    print(f"  corporate-action events:         {report.corporate_action_events:,}")
    print(f"  identity relationship rows:      {report.identity_relationship_rows:,}")
    print(f"  structural/distribution events:  {report.structural_event_rows:,}")
    print(f"  duplicate provider event ids:    {report.duplicate_provider_event_ids:,}")
    print(f"  unknown event types:              {len(report.unknown_event_types):,}")
    if report.unknown_event_types:
        print(f"    {report.unknown_event_types}")
    print("  rename continuity triage:")
    print(f"    candidates:                     {report.rename_continuity_candidates:,}")
    print(f"    safe stitch candidates:         {report.safe_stitch_candidates:,}")
    print(f"    evidence only:                  {report.continuity_evidence_only:,}")
    print(f"    review required:                {report.rename_review_required:,}")
    print(f"    Gate 3 casefold-sensitive:      {report.gate3_casefold_sensitive_candidates:,}")
    print("  event type counts:")
    for event_type, count in sorted(report.event_type_counts.items()):
        print(f"    {event_type:30s} {count:,}")
    print(f"  event ledger:                     {report.event_ledger_path}")
    print(f"  relationships:                    {report.relationship_path}")
    print(f"  rename candidates:                {report.rename_candidate_path}")
    print(f"  report:                           {report.report_path}")
    print("  canonical data modified:          False")
    print("  Historical Backfill Gate 4 corporate action / identity segmentation: CURRENT")


if __name__ == "__main__":
    main()
