# EOD Option Entry-Clock Forensics V1 — 2026-10-02

## Status

**DIAGNOSTIC COMPLETE / EOD OPTION PERFORMANCE INTERPRETATION CLOSED /
INTRADAY STOCK EXIT CLOCK NEXT**

This closeout joins the immutable Continuous Dynamic Exit V2 scenario, paired
option diagnostics, strict account replay, and EOD entry-clock closeout returned
from the workstation on 2026-10-02.

It does not promote a strategy or option expression. It identifies why the EOD
option replay is not a faithful representation of the original stock trade clock
and defines the next zero-provider diagnostic.

## Bound artifacts

- Continuous V2 scenario fingerprint:
  03406fdf1def82332b8e01761213ab4cd4eb9e7a8cdb551ea37ad8c9d7bfcf5b.
- Paired diagnostics fingerprint:
  c4c5ac96ae68b8a818cf34197e336d8618174e9f5cad034d8c15ecc77fb19d66.
- Strict account replay:
  multiyear_continuous_dynamic_exit_v2_option_replay_b525b49fabd0aead.json.
- Entry-clock closeout fingerprint:
  81ed6c657c07e05d0b8a5fb83d45e56c0f0834cd4424e51d8fc5b6979f102aa9.

## Continuous V2 is not a materially new exit surface

Across 14,733 policy cases:

- 14,383 / 14,733 = **97.6244%** of stops are exactly 3%;
- every target is exactly 5%;
- only 350 cases have a stop below 3%;
- 42 of those 350 are source-ready EOD option pairs;
- none of those sub-3% cases is admitted by the strict account before the account
  becomes capacity-blocked.

This explains why the V2 strict-account totals are exactly the same as the earlier
static 3%/5% account. The current exit-geometry branch remains closed.

## EOD entry creates a different economic clock

The entry-clock closeout found 5,785 causal EOD CALL entries.

- 3,230 / 5,785 = **55.8341%** had already reached the stock strategy exit by the
  time the EOD option entry was available.
- Median delay from the planned 09:35 option decision to EOD entry was one exchange
  session / **30.4167 hours**.
- Median absolute underlying movement before option entry was **2.3162%**.
- 76.37% moved at least 1%.
- 55.68% moved at least 2%.
- 39.60% moved at least 3%.
- 20.78% moved at least 5%.
- CALL moneyness classification changed in **35.96%** of cases.

The 2025 cohort was worse: 63.63% of causal EOD entries arrived after the stock
exit and median absolute pre-entry movement was 2.62%.

## The paired EOD option sample is mechanically survival-selected

Joining the 5,785 entry-clock rows to the stock exits shows:

| Stock exit | Causal EOD-entry cases | Exit before/not after EOD entry | Fraction |
| --- | ---: | ---: | ---: |
| STOP | 3,210 | 2,419 | **75.36%** |
| TARGET | 1,390 | 800 | **57.55%** |
| TIME | 1,144 | 11 | **0.96%** |

The 2,055 source-ready paired observations therefore overrepresent trades that
survive long enough for the next EOD option snapshot. Their stock exits are:

- STOP: 668;
- TARGET: 489;
- TIME: 898.

By contrast, the 3,230 cases eliminated because the stock exit was no later than
option EOD entry are:

- STOP: 2,419;
- TARGET: 800;
- TIME: 11.

Pre-entry movement makes the censoring even clearer:

| Absolute stock movement before EOD option entry | Cases | Already exited | Source-ready pair |
| --- | ---: | ---: | ---: |
| <1% | 1,367 | 314 (23.0%) | 859 (62.8%) |
| 1–2% | 1,197 | 396 (33.1%) | 635 (53.0%) |
| 2–3% | 930 | 463 (49.8%) | 386 (41.5%) |
| 3–5% | 1,089 | 863 (79.2%) | 175 (16.1%) |
| 5–10% | 946 | 942 (99.6%) | **0** |
| >=10% | 256 | 252 (98.4%) | **0** |

There are zero source-ready pairs once the underlying had moved at least 5% before
the delayed EOD entry. This is not random missingness. The EOD clock mechanically
removes many of the fastest winners and losers that define the STOP/TARGET strategy.

Therefore the paired -14.06% mean premium return remains a valid descriptive result
for the exact future-source-conditioned pairs, but it is not an unbiased estimate
of how the intended 09:35 option expression would have performed.

## What the paired option economics actually show

Conditioned on the 2,055 surviving exact-session pairs:

| Stock exit | Pairs | Mean option premium return | Median | P(positive) |
| --- | ---: | ---: | ---: | ---: |
| STOP | 668 | **-40.29%** | -40.36% | 3.14% |
| TARGET | 489 | **+22.01%** | +16.72% | 73.42% |
| TIME | 898 | **-14.19%** | -16.40% | 27.73% |

The option is broadly amplifying the stock outcome, while TIME exits lose on average.
This supports separating underlying signal quality from derivative expression. It
does not support another stop/target search.

At the policy level, the largest prior specialist is especially distorted by the
EOD clock:

- pract_bollinger_mean_reversion_v1: 1,529 causal EOD-entry cases,
  1,027 already exited before/not after EOD entry = **67.17%**;
- ema_pullback_20_50_long_v1: 50.75%;
- pract_relative_strength_momentum_v1: 52.06%;
- pract_atr_volatility_expansion_v1: 54.21%.

The EOD replay is therefore particularly unsuited to judging fast mean-reversion
behavior.

## Strict account is an execution-state diagnostic, not five-year performance

The strict account admitted 84 positions, completed 74, and accumulated ten unresolved
positions during 2021. Those ten positions then consume the full ten-position account
capacity, so 2022–2025 are dominated by MAX_CONCURRENT_POSITIONS_REACHED.

Inspection of the ten unresolved cases found:

- nine have a positive exact-session bid and bid size but fail the positive reported
  volume requirement;
- CME on 2021-11-26 has positive bid/size/volume at the official 13:00 ET
  Thanksgiving-Friday early close rather than the normal 16:00 ET clock;
- total modeled entry cost of those ten positions, including entry fees, was
  **$41,636.90**;
- valuing them only as a non-authoritative diagnostic at the observed exact-session
  bids less exit fees gives approximately **$33,073.10**, or **-$8,563.80** versus
  cost.

That diagnostic mark is not a historical-fill claim. It demonstrates that
"unresolved forever" is not an acceptable long-horizon account state. A later
execution model needs bounded exit attempts, exchange-calendar-aware close handling,
retry rules, and terminal expiration/settlement.

## Existing stock minute source changes the next step

ATLAS already has accepted Alpaca SIP raw one-minute source semantics and a frozen
2016-01-04 through 2026-04-30 DEVELOPMENT source plan. No second stock provider is
needed to determine the exit clock.

The next package, multiyear_intraday_stock_exit_clock_v1, therefore:

1. selects every pre-2026 Continuous V2 case that already has a continuous policy,
   stock exit, native raw stock open, and selected structural CALL;
2. uses only the accepted local Alpaca SIP raw 1-minute unit covering each
   STOP/TARGET exit session;
3. resolves the first boundary-touch minute and permits one-minute evidence to
   reorder a daily same-session collision;
4. treats a minute stamped T as causally actionable at T+1 minute;
5. uses the official exchange close for TIME exits, including early closes;
6. identifies stock exits that occurred at or before the planned 09:35 option
   decision and therefore could never have been expressed as an option at that clock;
7. emits deduplicated generic ENTRY/EXIT at-time CALL NBBO quote demands;
8. performs **zero provider requests**.

This is still a source/clock diagnostic. It creates no strategy, historical-fill,
PAPER, LIVE or option-P&L authority.

## Prospective option-source requirement

The later option source must be able to return historical NBBO at the exact requested
clock. MarketData historical option quotes are EOD-only and therefore cannot satisfy
this requirement.

ThetaData is a current candidate because its historical option at-time quote endpoint
returns the last OPRA NBBO at a specified millisecond, and its Options Value tier
documents one-minute option quote history beginning 2020. No ThetaData subscription
or provider read is authorized by this document. Provider qualification comes only
after the offline stock-exit clock demand plan is complete.

## Disposition

**EOD_OPTION_PERFORMANCE_AS_ORIGINAL_STRATEGY = CLOSED**

**CONTINUOUS_EXIT_V3 = NOT AUTHORIZED**

**NEXT = OFFLINE_INTRADAY_STOCK_EXIT_CLOCK_V1**

Underlying alpha remains the research bottleneck. Correct option clocks are necessary
to evaluate derivative expression, but they do not rescue a weak stock signal.
