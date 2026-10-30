# V48 — V47 user-run SPY exit-price evidence and negative-signal closeout

**Research date:** October 30, 2026. **Disposition:** DEVELOPMENT NEGATIVE / NO
PERFORMANCE PROMOTION / DEPRIORITIZE FROZEN LONG-STRADDLE ECONOMIC-INPUT
EXPANSION UNTIL A STRONGER PRE-REGISTERED HYPOTHESIS OR TRUE PIT VALIDATION
RATIONALE IS DOCUMENTED. This is not a claim of a failing or successful real
trading strategy. This closeout records the V47 hypothetical quote screen
without retrospectively changing its frozen signal, strike selection or exits.

## Immutable workstation source

The user completed `data/research/spy_v47_exits_20261030_123519.json`
(report fingerprint
`9eea1abc12eca482d967cad172a9a2851b7c8cfc0879a7f97104d4bed01e855d`).
It contains 106 V46 **hypothetical**, non-PIT LONG decisions: **48 frozen V43
original contracts and 58 V44 alternate-version contracts**. Exactly 1,060
CALL/PUT source uses were dispatched, 1,058 fetched and immutably cached, 0
already cached in this initial run, and **two provider-worker ValueError
requests failed** for the same **2020-05-01** alternate-position exit
(2020-04-27 entry, SPY May 29 2020 expiration, strike 286; session-4
CALL and PUT). The CLI wrote its fingerprinted report before exiting 2 to
flag unresolved source acquisition; this is **not** a full-sample model crash.
Do not infer the missing quotes were zero or that positions were closed.
An exact-cache-based rerun would reuse the 1,058 archives and retry the two,
but repairing this single exit is not prerequisite for the **negative
exploratory** research verdict.

Across 106 x 5 = **530** candidate exit-pair observations, **510 passed**
the contemporaneous quote validation. **20 were censored**: 18 cross-right
quote timestamp skews over one second, one observed spread exceeding the
unchanged 15% gate, and one missing quote pair caused by the two provider
errors. Original and alternate entry/exit price pairs are retained separately.

## Net quote-reference economics (percentage of original paired option debit)

The scenario uses one observed 10:01 entry CALL+PUT ASK and one later 10:01
paired exit BID, with $0.65 per contract per side plus a distinct
additional-full-spread stress. These are **NOT** broker executions.

| Next trading-session close | Quote-qualified / 106 | Primary mean | Primary median | Primary positive count | Stress mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 105 | -1.23% | -1.88% | 32/105 | -2.79% |
| 2 | 101 | -1.24% | -2.38% | 29/101 | -2.90% |
| 3 | 101 | -0.54% | -1.07% | 43/101 | -2.43% |
| 4 | 102 | -0.60% | -3.78% | 37/102 | -2.49% |
| 5 | 101 | **+0.57%** | **-4.31%** | 38/101 | **-1.31%** |

**Outlier sensitivity:** The five-session highest quote-reference winner,
entered 2025-03-31, returned **+114.38%**; removing that one observation
changes the five-session primary mean to approximately **-0.57%**. Removing
the largest five winners changes it to **-3.21%**. All five primary medians
are negative and all five stressed means are negative. No positive exit-hold
hypothesis survives this basic cost/outlier screen as evidence of a robust
profit. Do not select five sessions retroactively because the untrimmed mean
happened to exceed zero.

## Independent frozen-original vs separately versioned alternate cohort

All figures below are descriptive, conditional on the original V46
hypothetical signal and on accepted exit quotes. No multi-year OOS verdict
is implied.

| Source cohort | Exit sessions | Qualified quotes | Primary mean | Primary median | Positive |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen original (48) | 1 | 48 | -1.77% | -1.99% | 16/48 |
| Frozen original | 3 | 45 | +0.43% | -0.47% | 20/45 |
| Frozen original | 5 | 45 | +1.67% | -5.40% | 14/45 |
| Alternate (58) | 1 | 57 | -0.77% | -1.73% | 16/57 |
| Alternate | 3 | 56 | -1.31% | -1.75% | 23/56 |
| Alternate | 5 | 56 | -0.32% | -3.41% | 24/56 |

The original cohort's five-session average is positive but its typical
position loses money and the stressed mean is negative (~-0.23%).
The alternate has negative average five-session economics and a negative
stress mean (~-2.18%). Their union is a newly labeled hypothesis, not the
unchanged original strategy.

## Chronological $100,000 original-only one-day account

The **only** V47 cash-reference account to have no censored exit was the
**48-closed-pair frozen-original one-day exit**. Its original $100,000
reference account finishes at **$98,169.20** (loss **$1,830.80**); the
predeclared extra-spread scenario finishes at **$96,861.20** (loss
**$3,138.80**). Six of eight calendar years have negative realized
quote-reference cash differences; **20 of 29 months with a recorded closure**
are negative. The unqualified entry model, lack of actual fills, and cash
interest assumptions apply. The remainder of the 30 variant/hold/cost
account ledgers have unresolved exits and deliberately report *no valid
ending account equity*. Do not drop, impute, or call them complete.

## What changes in ATLAS research direction

1. **Stop treating collection speed as the main bottleneck.** The entire
   1,060-request V47 historical quote plan took ~2m29s, retained 1,058
   originals, and delivered a clear negative screen. Storage/provider
   acquisition is now sufficiently fast for targeted candidate research.
2. **No post-hoc strategy rescue.** Preserve unchanged frozen long straddle
   v1 and the separately recorded alternate. No DTE, expiry, strike,
   timing, hold-day or threshold optimization on these 2018–2025 outcomes
   can be called independent validation.
3. **Prioritize an actual trade-level simulation framework**: as-of
   publication/point-in-time returns, SOFR/dividends/OCC, original
   prescribed daily thesis-triggered exits, executable multi-leg fills and
   conservative censored-position accounting, weekly/monthly/yearly cash
   results and sequential drawdowns. Do this as reusable strategy-agnostic
   infrastructure. Do not open a broad 10-year full-universe options source
   download in advance.
4. **Explore genuinely distinct, pre-registered options strategies**
   individually using the same read-through source cache, focusing on
   risk-defined trades and realistic net economics. A favorable exploratory
   subcohort cannot qualify the new strategy; require independently
   prospective evidence before promotion.
5. **Do not block on May 1 2020 or relax the one-second quote-skew
   guard** merely to convert censored results to priced results. The two
   source retries can be attempted through existing V38/V39 exact-query
   retry behavior if a future strategy actually depends on that case.

V48 includes a zero-provider, version-pinned offline CLI,
`python -m scripts.run_spy_v48_v47_evidence_audit --v47 ... --output ...`,
for reproducible full-horizon, origin, year, outlier, and one-day
weekly/monthly/yearly development comparisons. It creates a new JSON result
without reading new source or outcome files.

The historical research/paper/live statuses remain **NOT VALIDATED**. The
original 2018–2025 data and outcomes are development-only; the consumed
2026 protected holdout cannot be reused as a fresh independent test.
