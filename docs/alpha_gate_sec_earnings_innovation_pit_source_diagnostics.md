# SEC diluted-EPS earnings-innovation — PIT failure source diagnostics

## Purpose

This package diagnoses the first frozen PIT source-audit failure without changing the audit contract, thresholds, chronology rule, source population, or scientific authority. The first failed PIT audit remains immutable evidence.

Diagnostic contract:

`alpha-gate-sec-earnings-innovation-pit-audit-diagnostics-v1-source-only-no-market-outcomes`

Diagnostic fingerprint:

`745c11fd29f752980404b128ec26d081e3e4df16342f0f6c66e32d201bcb52dd`

Parent PIT audit fingerprint:

`423528f7518273f91432ee0cfaf0f43fec8cf33fa11a59f40af5523b4f9d6baa`

The diagnostic runner requires the original local failed audit report to match SHA-256:

`3c299447e0ed8fd48d10c8cc792cf57396d87378cb21575e219b624c6a50566a`

The preserved failure had 5,902 original-accession candidates, three period-context ambiguities, six accession/form/filing-date contradictions, 5,896 audited observations, zero target-market outcome reads, zero protected-return reads, and an unconsumed protected holdout.

## Diagnostic scope

The source-only replay identifies the exact CIK, period end, accession, earliest Company Facts context rows, and official SEC submissions metadata behind:

- each ambiguous earliest direct-quarter period context;
- each accession/form/filing-date contradiction;
- any missing accession metadata or source replay failure, if present.

Results are written separately to:

`data/derived/strategy_evaluation/pre_phase33/sec_earnings_innovation_pit_audit_v1_diagnostics/source_diagnostics.json`

The original `sec_earnings_innovation_pit_audit_v1/source_audit.json` is read and hash-verified but never rewritten by this diagnostic runner.

## Scientific and authority boundary

This package changes no frozen gate and grants no alpha authority. Market prices, stock returns, SPY returns, target outcomes, protected returns, broker state, provider writes, orders, PAPER, LIVE, automation, automatic broker failover, and Phase33 Signal-to-Trade authority remain forbidden or disabled.

After the exact source rows are observed, only a demonstrated mechanical/source/provenance defect may be repaired under a separately fingerprinted repair contract. If the observed rows are genuinely ambiguous or contradictory source evidence rather than a mechanical interpretation defect, the frozen PIT audit remains failed and this mechanism must close or proceed only according to the existing preregistered governance rules.
