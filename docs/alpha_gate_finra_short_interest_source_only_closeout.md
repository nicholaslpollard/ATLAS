# FINRA Consolidated Short Interest — Accepted-Negative Source-Only Closeout

Status: **CLOSED `ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`; DEVELOPMENT AND PROTECTED MARKET OUTCOMES UNREAD**

Frozen scientific fingerprint:

`0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f`

Accepted source-reconstruction target head:

`d312ec95752ab49a6fcbec18973faacb96d4aa89`

Accepted persisted-artifact probe head:

`5ceac74ad67c8f3539b03192cf1946d51d476434`

Closeout contract:

`alpha-gate-finra-short-interest-closeout-v1-protected-source-insufficient-no-market-outcomes`

Accepted source-probe evidence fingerprint:

`c624da82b45fb8d530c2400262598f266ec6309e614a0dcd135b38d9ba5518ce`

Accepted closeout evidence fingerprint:

`bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565`

## Accepted target evidence

The complete frozen reconstruction successfully processed all **116 official FINRA settlement files** and **232 Massive point-in-time reference snapshots**. It produced **19,343** source-only predictor rows:

- DEVELOPMENT: **14,841**
- PROTECTED: **4,502**

Frozen candidate totals:

- `rapid_short_build_crowded_short`: **2,036**
- `rapid_short_build_non_crowded_short`: **8,025**
- `rapid_short_cover_crowded_long`: **1,257**
- `rapid_short_cover_non_crowded_long`: **8,025**

Exact accepted artifact hashes:

- predictor report SHA-256: `56479707945a59752aeb2056f3cfbcfd2df1e4a87ada31c9e8e6d3ed93f314cd`
- predictor rows SHA-256: `21c7dd2e44013ba0f1d290019db70f7b0f23b0603c5e965cbd8b441128190e48`

## Single frozen gate failure

All development source-count gates passed for all four hypotheses. Every protected source-count gate also passed except one:

`rapid_short_cover_crowded_long -> protected_min_rows`

Its exact protected source population was:

- event rows: **257** versus frozen minimum **300**
- signal sessions: **26** versus frozen minimum **16**
- unique instruments: **211** versus frozen minimum **200**

Therefore this is not a broad FINRA acquisition failure, identity collapse, or performance failure. It is a specific preregistered protected sample-size insufficiency for one member of the frozen global four-hypothesis family.

## Scientific disposition

The contract froze exactly four hypotheses and global `HOLM_BONFERRONI_GLOBAL_4` multiplicity before outcomes. Because one frozen hypothesis could not meet its protected 300-row floor, the source-only stage correctly returned `SOURCE_ONLY_PREDICTOR_FAIL` and stopped before any development performance was opened.

The exact scientific disposition is:

`ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`

Development market outcomes were never opened. Target/development outcome rows read = **0**. Protected return rows read = **0**. Protected holdout consumed = **false**. Phase33 signal-to-trade authority = **false**.

No return, profitability, benchmark-relative, win-rate, or alpha-performance claim may be inferred from this FINRA v1 result because no governed market outcomes were read.

## Permanent anti-retuning boundary

This exact FINRA v1 family is permanently closed. It may not be rescued after the observed source result by:

- removing `rapid_short_cover_crowded_long` and testing only three hypotheses;
- lowering the protected **300-row** requirement;
- changing the 10% change-tail or 80% crowding thresholds;
- changing the deterministic sampling cap;
- changing chronology, costs, horizon, fold rules, dependence treatment, or multiplicity;
- substituting another bucket or direction;
- opening protected returns merely to inspect an inadmissible result.

A future FINRA/short-interest study would have to be preregistered as a genuinely new scientific version before outcomes and may not present a post-result change as continuation of this v1 experiment.

## Downstream authority

Historical supported alpha remains **0**. Phase33 Signal-to-Trade Construction remains blocked. Provider writes, broker reads/writes, orders, PAPER, LIVE, automation, and automatic broker failover remain disabled for this research family.

The next authorized alpha research program must use a **materially different economic/information mechanism** rather than retuning this accepted-negative FINRA formulation.
