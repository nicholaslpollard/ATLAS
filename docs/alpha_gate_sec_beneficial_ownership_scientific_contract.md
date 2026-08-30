# Pre-Phase33 SEC Schedule 13D/13G Beneficial Ownership — Frozen Scientific Contract

**Status: FROZEN BEFORE MARKET OUTCOMES.** The original source-only v1 failure remains preserved. The targeted v2 source repair passed with all 43 quarterly indexes, 200/200 submissions parsed, 195 unique authoritative `SUBJECT COMPANY` CIKs, 142 unambiguous PIT active common-stock mappings, zero target outcomes, zero protected returns, and zero trading authority.

## Contract identity

Scientific contract:

`alpha-gate-beneficial-ownership-scientific-v1-four-initial-ownership-intent-buckets`

Scientific fingerprint:

`4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c`

Entry source-repair fingerprint:

`78bf3f18368114a5a6073e8a4d66a0c13ee29a5da78b8adeb1d71b1f10c6f78c`

Mechanism:

`PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`

The mechanism is motivated by the economic distinction between Schedule 13D control/active intent and Schedule 13G passive/qualified ownership, plus the size of the disclosed block. Prior activism literature is motivation only; no published return estimate is used as ATLAS performance evidence.

## Point-in-time source semantics

Only **initial** Schedule 13D and Schedule 13G filings are performance eligible. Amendments remain useful source evidence but are excluded from this finite performance family. This prevents post-result amendment-chain interpretation or ownership-change tuning.

Accepted initial aliases are `SC 13D`, `SCHEDULE 13D`, `SC 13G`, and `SCHEDULE 13G`.

The authoritative security issuer is the exact `SUBJECT COMPANY` CIK extracted from the official SEC complete-submission header. The master-index CIK remains filing/index provenance only. The decision session is the first XNYS regular-session open strictly after SEC acceptance. Security identity is exact header subject-CIK + decision date + `active=true` + `type=CS`, requiring exactly one STRONG/MEDIUM instrument. Ambiguous or missing identity fails closed.

## Ownership percentage rule

ATLAS extracts the cover-page percent-of-class values reported by the filing persons. Structured Schedule 13D uses `percentOfClass`; structured Schedule 13G may use the corresponding structured class-percent field. Historical HTML/text is parsed only from the cover-page label `Percent of class represented by amount in Row (...)` followed by an explicit percentage.

The filing-level predictor is the **maximum finite cover-page percent-of-class value across reporting persons**. Percentages are never summed across affiliated reporting persons because that can double-count the same block. Only `0 < percent <= 100` is accepted. A filing without a valid percentage emits no signal.

## Four finite hypotheses

Exactly four non-overlapping LONG hypotheses are frozen:

1. `initial_13d_5_to_10_long`: initial Schedule 13D, `5 <= percent < 10`.
2. `initial_13d_10_plus_long`: initial Schedule 13D, `percent >= 10`.
3. `initial_13g_5_to_10_long`: initial Schedule 13G, `5 <= percent < 10`.
4. `initial_13g_10_plus_long`: initial Schedule 13G, `percent >= 10`.

No amendment hypothesis, short hypothesis, ownership threshold, purpose-text taxonomy, reporting-person type filter, or filer-class filter may be added after outcomes are observed.

## Source-only scientific sample

The development predictor acquisition deterministically hash-ranks initial filings independently of market outcomes and selects at most **2,000 initial 13D plus 2,000 initial 13G** filings from the development filing-date window. The protected predictor acquisition selects at most **600 initial 13D plus 600 initial 13G** filings from the protected filing-date window.

Hash input is accession + frozen scientific contract + stage + form family. Market prices, returns, issuer performance, and candidate returns do not participate in source sampling.

Final stage attribution is based on the SEC acceptance-derived decision session. A filing whose decision session crosses a frozen stage boundary is censored rather than reassigned to manufacture sample size.

## Chronology

- predictor source window: `2016-01-01..2026-08-11`;
- governed performance signal start: `2021-08-16`;
- development last signal: `2024-12-31`;
- outer embargo: `2025-01-02..2025-04-03`;
- protected first signal: `2025-04-04`;
- protected last signal: `2026-05-11`;
- protected outcome end: `2026-08-11`.

Entry is the decision-session open. Primary exit is the close 63 XNYS sessions after the decision. The 21- and 126-session paths are diagnostic only and cannot replace the primary horizon.

## Outcome and friction contract

Primary performance is stock open-to-63-session-close return minus same-window SPY return minus **10 bps** total LONG cost. Positive after-cost unhedged stock return is independently required. Stress cost is **25 bps**.

The system is testing tradeable post-publication return from the first eligible market open, not the inaccessible price reaction before that entry.

## Development, dependence, multiplicity and robustness

Development sessions are split chronologically 70/30 with a 63-session internal purge. Selection uses four time folds; internal validation uses three. Overlapping 63-session returns use a 63-session block bootstrap with 2,000 replicates and seed `133013`.

Selection confidence is 95%; internal validation 90%; protected confirmation 80%.

Selection hard minimums: 200 event rows, 100 signal sessions, 50 unique instruments, and at least 3/4 positive folds.

Internal hard minimums: 60 event rows, 30 signal sessions, 20 unique instruments, and at least 2/3 positive folds.

Protected source-only minimums: 60 predictor rows, 25 signal sessions, and 25 unique instruments. Protected confirmation later requires at least 2/4 positive folds if a finalist exists.

At applicable performance stages, after-cost SPY-relative mean, its required lower bootstrap bound, stress-cost mean, and unhedged after-cost mean must all be positive. At least 60% of years with at least 15 signal sessions must have positive primary mean. A single decision session may contribute no more than 8% of rows and one instrument no more than 4%.

The February 5, 2024 Schedule 13D deadline regime change is a diagnostic split and cannot rescue a failed hard gate.

Multiplicity is global `HOLM_BONFERRONI_GLOBAL_4` at alpha 0.05. At most **one** selection winner exists across the four candidates, ranked only by selection-tranche primary lower confidence bound then candidate ID. Internal validation only confirms/rejects that winner. At most one finalist may reach protected returns. Runner-up substitution is forbidden.

A deflated-performance diagnostic is required but cannot rescue a hard-gate failure.

## Protected evidence

Protected predictors may be reconstructed before a finalist exists solely for source-count sufficiency. Protected returns remain forbidden until one fixed finalist independently passes development and its source-only protected precheck.

Any non-empty protected return read consumes this mechanism's protected holdout. A failed finalist cannot be replaced by another candidate after that read.

## Pre-outcome development transport repair

The optimized target run reached `3500/5200` in the source-only predictor walk and then stopped because one official SEC complete-submission archive exceeded ATLAS's historical 20 MB submission-response cap. The failure occurred **before** `Source-only predictor reconstruction: PASS`, so development stock/SPY outcomes and protected returns remained unread.

The accepted source-feasibility replay retains its historical/default **20 MB** complete-submission cap. The scientific acquisition runner now explicitly opts into a separate bounded **256 MB** complete-submission ceiling for legitimate large SEC archive submissions while keeping the existing 64 MB quarterly-index cap and 5 calls/second fair-access pacing.

This repair changes no source sample, filing parser, `SUBJECT COMPANY` identity rule, decision-session chronology, ownership threshold, hypothesis, horizon, cost, split policy, bootstrap, multiplicity rule, robustness gate, finalist rule, or protected-return boundary. The scientific fingerprint remains `4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c`, and the statistical development implementation fingerprint remains `0e90a65e6e2f6a7d7206296901054de3a2c97aaa204c80927a963c298c81060d`.

The bounded acquisition repair is independently frozen as:

`a4db8419364895c6861c4becbe3abf9b32ec044ceb4aff5cf14a7c9244368bdb`

## Authority boundary

The scientific-policy and predictor stages read zero stock returns, zero SPY returns, and zero protected returns. Provider writes, broker reads/writes, orders, PAPER submission, LIVE writes, automation writes, and automatic broker failover remain disabled. Phase33 remains blocked until a strategy independently earns accepted historical `SUPPORTED` authority.
