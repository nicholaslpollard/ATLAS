# SEC diluted-EPS earnings-innovation — PIT source audit

## Purpose

This gate is the source-only successor to the accepted diluted-EPS feasibility census. It determines whether the current SEC Company Facts history can be tied, without market outcomes, to the **original non-amendment periodic filing accession**, the official SEC acceptance timestamp, and a leakage-safe XNYS decision session.

It remains a prerequisite. It does **not** define an alpha hypothesis, direction, threshold, holding period, cost model, selection rule, or protected test.

## Frozen contract

- Contract: `alpha-gate-sec-earnings-innovation-pit-audit-v1-original-accession-acceptance-source-only-no-market-outcomes`
- Fingerprint: `423528f7518273f91432ee0cfaf0f43fec8cf33fa11a59f40af5523b4f9d6baa`
- Parent target head: `48720381a6cdf3963d75b023e3c1176ebbf674de`
- Parent feasibility fingerprint: `c32e4aa83b25cdc23476098ffc30bd48908123d047d75f18f0d45b2acaffcd0d`

The parent evidence is fixed at 300 successful Company Facts documents, 265 EPS-bearing documents, 204 issuers with at least 12 direct quarters, 170 with at least 16, 5,905 unique direct-quarter observations, calendar years 2013–2026, and zero same-accession context conflicts. The audit verifies the parent report and source-document hashes before using it.

## Original-accession rule

For each issuer and direct-quarter period end, ATLAS selects the earliest retained non-amendment `10-Q` or `10-K` Company Facts accession only when the earliest accession has an unambiguous direct-quarter context and value. Later comparative or restated values cannot overwrite that original observation.

`10-Q/A` and `10-K/A` are chronology evidence only and are never predictor-ready under this contract. If an original value cannot be proven from retained accession lineage, it is excluded rather than backdated.

## SEC chronology

Acceptance timing comes only from official SEC submissions metadata, either the issuer root submissions JSON or an SEC-declared historical submissions shard. The accession, form, and filing date must reconcile exactly.

The decision session is:

`FIRST_XNYS_REGULAR_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE`

This handles pre-open, intraday, after-hours, weekend, and exchange-holiday filings without a calendar-day shortcut.

This audit does not establish an earnings-announcement timestamp. The mechanism remains periodic-filing earnings innovation; it is not an earnings-announcement PEAD claim.

## Frozen acceptance gates

The audit requires all of the following:

- all 300 Company Facts documents match the hashes preserved by Gate0;
- Gate0 direct-quarter/history/SUE counts recompute exactly;
- at least 295 SEC submissions root documents succeed;
- at least 4,000 original-accession observations survive the complete PIT audit;
- at least 160 issuers retain 12 or more audited direct quarters;
- at least 130 issuers retain 16 or more audited direct quarters;
- at least 95% of original-accession candidates receive proven SEC acceptance chronology;
- at least eight calendar years remain represented;
- zero ambiguous earliest period contexts;
- zero accession/form/filing-date contradictions;
- zero acceptance timestamps on or before the reported period end;
- zero XNYS decision-session resolution errors.

These thresholds are frozen before the target audit is run.

## Forbidden reads and authority

Market prices, stock returns, SPY returns, target outcomes, protected returns, broker reads/writes, provider writes, orders, PAPER submissions, LIVE writes, automation writes, automatic broker failover, and Phase33 Signal-to-Trade authority remain disabled.

A passing audit still does not open market outcomes. The next prerequisite is PIT common-stock identity continuity; only after source chronology and identity are accepted may the earnings-innovation scientific hypothesis family be frozen.

## Artifacts

The target runner writes:

- `data/derived/strategy_evaluation/pre_phase33/sec_earnings_innovation_pit_audit_v1/pit_rows.jsonl`
- `data/derived/strategy_evaluation/pre_phase33/sec_earnings_innovation_pit_audit_v1/source_audit.json`

The accepted Gate0 report is never rewritten.
