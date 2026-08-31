# SEC diluted-EPS earnings-innovation — PIT failure source diagnostics

## Purpose

This package diagnoses the first frozen PIT source-audit failure without changing the audit contract, thresholds, chronology rule, source population, or scientific authority. The first failed PIT audit remains immutable evidence.

The first diagnostic implementation, V1, stopped safely before any provider replay because its immutability guard compared the known SHA-256 `3c299447e0ed8fd48d10c8cc792cf57396d87378cb21575e219b624c6a50566a` against the wrong artifact. That SHA was printed by the PIT audit as **Parent report SHA-256** and belongs to the accepted Gate0 feasibility report, not to the PIT `source_audit.json` bytes. The V1 diagnostic stop is preserved as a mechanical diagnostic-guard failure and is not reused.

Corrected diagnostic contract:

`alpha-gate-sec-earnings-innovation-pit-audit-diagnostics-v2-source-only-no-market-outcomes`

Corrected diagnostic fingerprint:

`399e7d0bece8088e63c4835566d276b51375a5031d81f4db4781675351a87961`

Parent PIT audit fingerprint:

`423528f7518273f91432ee0cfaf0f43fec8cf33fa11a59f40af5523b4f9d6baa`

V2 uses the guard:

`STRUCTURAL_EXACT_FAILED_AUDIT_PLUS_PARENT_REPORT_SHA256`

The guard requires the failed PIT report to retain the original contract/fingerprint, exact observed counts, exact gate vector, zero market/protected reads, disabled trading authority, and `parent_report_sha256` equal to the accepted feasibility-parent hash above. V2 also independently hash-checks the feasibility parent itself. Once those checks pass, V2 records the failed PIT report's actual current byte SHA-256 in the separate diagnostic artifact for future immutability checks.

The preserved PIT failure had 5,902 original-accession candidates, three period-context ambiguities, six accession/form/filing-date contradictions, 5,896 audited observations, zero target-market outcome reads, zero protected-return reads, and an unconsumed protected holdout.

## Diagnostic scope

The source-only replay identifies the exact CIK, period end, accession, earliest Company Facts context rows, and official SEC submissions metadata behind:

- each ambiguous earliest direct-quarter period context;
- each accession/form/filing-date contradiction;
- any missing accession metadata or source replay failure, if present.

V2 results are written separately to:

`data/derived/strategy_evaluation/pre_phase33/sec_earnings_innovation_pit_audit_v2_diagnostics/source_diagnostics.json`

The original `sec_earnings_innovation_pit_audit_v1/source_audit.json` is read-only and is never rewritten by the diagnostic runner.

## Scientific and authority boundary

This package changes no frozen gate and grants no alpha authority. Market prices, stock returns, SPY returns, target outcomes, protected returns, broker state, provider writes, orders, PAPER, LIVE, automation, automatic broker failover, and Phase33 Signal-to-Trade authority remain forbidden or disabled.

After the exact source rows are observed, only a demonstrated mechanical/source/provenance defect may be repaired under a separately fingerprinted repair contract. If the observed rows are genuinely ambiguous or contradictory source evidence rather than a mechanical interpretation defect, the frozen PIT audit remains failed and this mechanism must close or proceed only according to the existing preregistered governance rules.
