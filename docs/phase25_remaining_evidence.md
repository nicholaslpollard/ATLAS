# Phase 25 — Cumulative Remaining Evidence Gates 8–11

**Status: ACCEPTED — NO SUPPORT REPLACEMENT**

Exact target-tested head: `302bf6db5d807884f3b74cda049fc95864c5a194`.

Exact-head CI run `32981080421`: Ubuntu and Windows SUCCESS; every validator through Phase25 Gate11 and the full regression suite passed.

## Accepted Gate7 boundary

Gate7 established the route-fidelity population before any incumbent rule-return study:

- WARM/HOT directional rows: 23,177;
- exact PIT ticker intervals: 9,609;
- market-compatible candidates: 17,285;
- fully route-eligible candidates: 15,283;
- eligible route decisions: 61,132;
- total route decisions: 185,416;
- provider/broker/execution/support activity: zero;
- independent validation: PASS.

## Cumulative workflow

Gates8–11 were implemented and preregistered together before target performance was inspected:

`Gate8 development attribution -> Gate9 robustness/internal validation -> Gate10 frozen-finalist protected confirmation -> Gate11 cumulative closeout`

Valid zero-selection/zero-finalist outcomes were required to continue rather than fail the software path.

## Gate8 — development-only incumbent attribution

The eight incumbent v1 rules and accepted three-session directional-return outcome were unchanged.

Target result:

- route rows matched to accepted legacy research source: **43,456 / 57,160**;
- exact legacy-source route coverage: **76.0252%**;
- development rule-fired signal rows: **24,753**;
- candidates with >=1 incumbent fire: **10,521**;
- protected evidence reads: **0**;
- independent validation: PASS.

10 bps means:

| Strategy | Broad comparator | Production path | Delta |
|---|---:|---:|---:|
| breakdown_short_v1 | -0.004272 | -0.011314 | -0.007042 |
| breakout_long_v1 | -0.000684 | -0.017605 | -0.016921 |
| momentum_long_v1 | -0.000537 | -0.015455 | -0.014918 |
| momentum_short_v1 | -0.002665 | -0.012069 | -0.009404 |
| pullback_long_v1 | -0.000207 | no production fires | n/a |
| pullback_short_v1 | -0.001467 | no production fires | n/a |
| trend_following_long_v1 | -0.000424 | -0.013482 | -0.013058 |
| trend_following_short_v1 | -0.002891 | -0.011394 | -0.008502 |

Every non-empty production-path incumbent was materially worse than its broad comparator and negative after the primary 10 bps cost.

The 76% legacy-source join is a comparator limitation and is preserved as evidence. It is not authority to impute missing rows. Future strategy research should derive observations directly from accepted PIT production-path lineage instead of relying on this legacy source as primary input.

## Gate9 — preregistered robustness and internal validation

Gate9 inherited the accepted Phase24 robustness machinery and strengthened multiplicity to one global Holm-Bonferroni family across the eight fixed incumbents.

Selected after development + global Holm: **[]**.

Finalists after internal validation: **[]**.

Failure counts:

- `positive_folds`: 8/8;
- `primary_mean_positive`: 8/8;
- `primary_median_positive`: 8/8;
- `positive_rate_half`: 8/8;
- `primary_lcb_positive`: 8/8;
- `stress_mean_positive`: 8/8;
- `year_robustness`: 8/8;
- `regime_robustness`: 8/8;
- `min_raw_rows`: 2/8;
- `min_signal_sessions`: 2/8;
- `session_concentration`: 2/8.

No losing strategy was substituted after selection/internal failure. Independent validation: PASS.

## Gate10 — frozen-finalist protected confirmation

Because Gate9 produced zero finalists:

- disposition: `SKIPPED_ZERO_FINALISTS`;
- protected evidence reads: 0;
- confirmed strategies: [];
- independent validation: PASS.

The existing protected interval remained unread for this Phase25 path.

## Gate11 — cumulative diagnostic closeout

Final verdict:

`NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED`

Next boundary:

`TARGET_DEVELOPMENT_FAILURE_MODES_OR_NEW_STRATEGY_ARCHITECTURES`

Phase11 support map unchanged: true.

Provider reads/writes by Gates8–11: 0 / 0.

Broker/order/PAPER/LIVE writes: 0 / 0 / 0 / 0.

Phase11 support writes: 0.

Independent validation: PASS. Cumulative status: COMPLETE / PASS.

## Decision

Phase25 is complete. Route fidelity did not reveal hidden robust edge in the incumbent v1 strategies. No support replacement is justified.

The next phase must investigate materially different architectures rather than weaken gates or continue threshold tightening of trend/momentum/breakout/pullback mirrors. Candidate examples include relative strength, mean reversion, gap/event, volatility-normalized structures, multi-timeframe logic, and composite signals. Short-side research must not be a mechanical mirror of long-side rules.
