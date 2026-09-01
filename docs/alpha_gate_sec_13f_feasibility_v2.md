# Pre-Phase33 SEC Form 13F Institutional Positioning — Gate0 V2 Audit-Aligned Bounded Probe

## Status

`FROZEN_BEFORE_PROVIDER_READ`

Feasibility contract:

`alpha-gate-sec-13f-feasibility-v2-official-bulk-probe-only-no-market-outcomes`

Policy fingerprint:

`4f41f7b1ca93bb76d559134d8ef74505ffd6a598e96676011ef515026d491696`

Audited source-main lineage:

`938747804e05357981faed79d696875cd7649f19`

Preserved pre-audit v1 head:

`4f40b25d0a19d1485ef990e465ab064080c8cc06`

Economic mechanism candidate:

`PIT_SEC_FORM13F_INSTITUTIONAL_POSITIONING_CHANGE_AND_CONSENSUS_ACCUMULATION`

No v1 SEC archive or market outcome had been read before PR #42 introduced the prospective research-gate audit. V1 therefore remains preserved as preregistration history, while v2 prospectively adopts the new audit safeguards before any provider read.

## What this gate can establish

This gate is explicitly `PROBE_ONLY`.

It uses the same four frozen official SEC bulk-data anchors as v1: `2016Q1`, `2020Q2`, `2023Q1`, and `2025MAM`. The newest anchor ends on 2025-05-31, before the master protected outcome window.

A `PROBE_FEASIBILITY_PASS` means only that these bounded anchors satisfy the preregistered structural/source-quality checks and demonstrate enough apparent source richness to justify a complete capacity census. It does **not** mean the complete natural-event source has been enumerated, scientific sample minima are attainable, or an alpha hypothesis may be frozen.

The report must retain `feasibility_scope = PROBE_ONLY`, `capacity_evidence_kind = BOUNDED_ANCHOR_PROBE`, `capacity_evidence_complete = false`, `complete_source_scope_proven = false`, and `scientific_freeze_allowed = false`.

## Structural probe checks

Every anchor must contain `SUBMISSION.tsv`, `COVERPAGE.tsv`, and `INFOTABLE.tsv`. The bounded-anchor checks remain at least 500 original `13F-HR` submissions, 50,000 original-HR holdings rows, 500 manager CIKs, 99.5% valid CUSIPs, zero key/orphan/chronology defects, only documented 13F submission types, and at least ten inclusive calendar years across the four anchors. These are **probe thresholds**, not future scientific row/session/instrument floors.

## PR #42 prospective research-freeze boundary

PR #42 merged `research-gate-freeze-v1-reachability-population-power-before-outcomes`. V2 records the four-anchor population using `PopulationScope.PROBE_ONLY`; therefore `source_scope_proven` must remain false even if every structural probe check passes.

No 13F scientific contract may be frozen until later source-only work establishes complete source capacity, original-EDGAR reconciliation and filing chronology, PIT CUSIP-to-ATLAS identity, a source-to-signal funnel, mechanism-appropriate effective-sample minima, costs and positive after-cost effect target, reachable multiplicity arithmetic, at least eight positive-path power trials meeting the preregistered detection target, and zero protected outcome reads.

## Identity, timing, and immutability

Form 13F is CUSIP-based. Gate0 grants no CUSIP-to-ticker or CUSIP-to-ATLAS identity authority and performs no fuzzy issuer matching. Quarter-end holdings are not decision timestamps; later science must use authoritative public filing availability/acceptance chronology.

V2 evidence uses separate `feasibility_v2` canonical and derived paths and cannot overwrite v1. After the first report exists, accepted ZIP hashes are immutable; missing or changed accepted evidence fails closed rather than silently refetching.

Market prices, development outcomes, protected returns, holdout consumption, full-history acquisition, hypothesis freezing, provider writes, broker reads/writes, orders, PAPER/LIVE submission, automatic broker failover, and Phase33 authority are forbidden.

If the bounded probe passes, the next step is a complete source-capacity and PIT provenance/identity stage—not performance testing.
