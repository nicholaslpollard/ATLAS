# ATLAS Strategy Evidence Register

**Consolidated 2026-10-12 against main `641757803b00bbebf75eb5c20c366b2668ee9707`. No new performance evidence opened.**

This register summarizes completed evidence and current research dispositions. The [project guide](roadmap.md) owns goals and work order. Code/contracts and original immutable artifacts own exact behavior/results; [the original full register](https://github.com/nicholaslpollard/ATLAS/blob/641757803b00bbebf75eb5c20c366b2668ee9707/docs/strategy_evidence_register.md) retains every earlier detailed entry and fingerprint. Consolidation does not alter prior verdicts or authorize reruns.

## Evidence rules

- Version every material strategy/selector/exit change; preserve failed versions and the append-only trial ledger.
- A favorable post-result slice is a hypothesis. It cannot independently validate the rule derived from it.
- Use prior-only walk-forward fitting; preserve purging/embargo, costs, independent-session support, uncertainty, multiplicity, and concentration.
- Abstention is valid. A supported negative specific cell cannot be rescued by a broader positive average.
- Keep standalone family lineage; confluence/ranking is separate. Correlated signals are not independent votes.
- Default research budget: structured diagnosis and at most three materially distinct successors per family per cycle, not dense threshold fishing.
- Dispositions such as KEEP, CONDITION-GATE, REDEFINE, or PARK are not authority promotions.
- Infrastructure/source acquisition is not strategy evidence. Record its current state in the guide and details in source receipts/closeouts.
- Historical supported modern alpha remains **0**; no strategy is HISTORICALLY_VALIDATED, PAPER_VALIDATED, LIVE_ELIGIBLE, or LIVE_AUTHORIZED by these entries.

The master `2026-05-12..2026-08-11` holdout was consumed once by frozen A33/B33 V2 on 2026-09-07 (93,380 protected return rows). It cannot qualify revisions. Earlier experiments' zero-protected-read statements remain true for their own scope. New prospective qualification is still necessary.

## Options-native pilot v1 — specified, no performance evidence

On 2026-10-15 the user approved making options-native discovery a primary branch alongside independent stock research. The first code-registered specification is `options-native-spy-long-straddle-v1`: one SPY common-strike/expiry CALL+PUT pair, a fixed twenty-prior-return volatility estimator versus same-maturity ATM implied variance, daily thesis-based exit and five-session maximum hold. The [guide](roadmap.md#options-native-pilot-and-data-contract) describes scope/dependencies; the [contract](../packages/strategies/options_native_pilot_v1_contract.py) owns exact rules. Specification fingerprint: `e3ad55ad153ca61432bfde65aa0b5c54004766866a2919a567b6b5ade551efca`.

Budget: one strategy variant, qualified primary and predeclared spread/latency stress. The independent discovery plan has 411 weekly 2018-2025 CALL/PUT surfaces, including 2020, and excludes seven clocks by a predetermined maturity buffer. No historical prices/outcomes were read, provider calls made, historical trades simulated or workstation trial ledger appended. Synthetic feature and plan tests establish mechanics only. Source availability/clock models, broker fees and multi-leg execution/lifecycle remain unqualified. Append a matching draft to the existing trial ledger before any authorized outcome read. Earlier history is DEVELOPMENT, not untouched qualification; no consumed 2026 outcomes or post-result regime pruning are permitted. Status: SPECIFIED_NOT_PERFORMANCE_TESTED / NO_PROMOTION.

On 2026-10-16 the unchanged pilot gained synthetic exact-pair geometry, daily thesis/session/DTE exit requests and a separate two-leg receipt-driven account coordinator. Fixtures test lone-leg exposure, final unfilled cancellations, fee reserves, exact basis/P&L, unsettled proceeds, cash settlement and unknown valuation. They establish no historical fills, broker costs, exercise outcomes or strategy performance. No new variant, trial-ledger append, historical replay or promotion occurred in that engineering package.

The operator subsequently completed the raw-input packet and supplied its JSON. Independent inspection reconciles 21/21 SPY closes, the exact 2019-12-04..2020-01-03 prior window, its signature and two source-unit bindings. Report `92c4d71997ec3225d5040f00375fc4ad66d654be6ce4a6cb81136a87d75374dc`, raw-file SHA-256 `e02946c3390626bf8f1b1aee13081febfbc00ae100c8f1a8bf272e868a444459`. Economic returns, forecast and historical availability remain unqualified. A pinned cached stock-input follow-up and synthetic split/cash-entitlement arithmetic are implemented; the follow-up has not run on the workstation. No historical strategy outcome, fee change, new variant or performance authority is created. The guide owns the next command and remaining source dependencies.

## A33/B33 and A34 reference account

Nine direction-specific policies / six families. Accepted V2 DEVELOPMENT: 161,347 opportunities, account return -17.912608%, maximum drawdown -20.803073%. Unchanged frozen walk-forward `2026-05-12..2026-09-03`: 14,081 opportunities, account return and maximum drawdown -8.372772%. The master slice ends 2026-08-11; later rows are post-protected continuation, not a new holdout. Some signal-level LONG means were positive; aggregate account results were negative, RSI support small, cash-distribution economics incomplete. All policies remain RESEARCH.

Original identities and authority are retained in the guide's compatibility appendix and `docs/a33_b33_phase_start_contract.md`.

## B35 intraday library and conditioning

Canonical DEVELOPMENT `2016-01-04..2026-04-30`: 482/482 groups, 59,768/59,768 units, 20,171,286 fired records. Frozen selector: 33 folds with 504 training / 63 test / 63 step / one-session embargo; minimum cells 60 opportunities / 30 sessions / 20 instruments. Selection score: 5th percentile of 1,000 XNYS-session-cluster bootstrap mean net-R samples at 50 bps, strictly positive or abstain.

17,030,985 test opportunities; 3,747 selected / 3,188 comparable; 99.978% abstention. Selected mean returns at 0/10/25/50/100 bps: +0.2984% / +0.1984% / +0.0485% / -0.2015% / -0.7014%. Small positive mean net-R at 50 bps did not produce positive mean percentage return. Prior market regime was unavailable; this did not test a meaningful bull/bear router.

| Strategy | Recorded result | Disposition |
| --- | --- | --- |
| `b34_gap_continuation_v1` | Unrestricted and selected cost-adjusted results negative; positive training cells temporally concentrated; delay/threshold neighbors did not rescue it | CONDITION-GATE / REDEFINE; preserved diagnostic mechanism |
| `b34_opening_range_breakout_15m_v1` | 3,489 selected / 2,935 comparable; selected mean at 50 bps about -0.2220%; 14/15/16-minute and 0/1/2-minute entry neighbors negative | CONDITION-GATE / CALIBRATE + execution audit; not a permanent low-liquidity filter |
| `b34_premarket_relvol_consolidation_v1` | 309,304 comparable; +0.0472% gross / -0.4529% at 50 bps; 32.80% positive, profit factor 0.290 on net-R; no selections | KEEP FOR R&D / cost-execution calibration; thin gross signal |
| `b34_highest_volume_day_style_v1` | 58 opportunities, below minimum 60; -0.3367% gross / -0.8359% at 50 bps | REDEFINE / insufficient evidence; do not lower support minimum |

Retained robustness over 2,079 sessions: 13 selected cell hypotheses, zero BH-FDR q=.05 rejections. All five 50-bps session profiles negative; Deflated-Sharpe probability 0.0. PBO/CSCV 0.01% is narrow ranking stability, not profitability. Exact 27 one-axis minute perturbations completed with canonical baseline equivalence; none rescued the four mechanisms. B35 v1 and simple parameter rescue are closed / NO PROMOTION.

| Artifact | Fingerprint |
| --- | --- |
| Replay | `8955a282453cb89a24d3bcdf819d80451bebfa3ec9752dc24c113efc668cffe6` |
| Conditioning analysis | `8369790cc019e84091d9ff431e0ba82678e8b23ec09f65f010cdfaca35d3254f` |
| Retained robustness | `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107` |
| Exact perturbation run | `dd3f6b94f9c669218512ed1eb014b33c0fd35e8ffe38484cc8967dc7a6e29f69` |

Detailed record: [B35 conditional evidence](b35_a36_preoutcome_conditional_evidence.md).

## Successor laboratory: standalone and conditioning v1

21 economic families / 28 routes (18 daily / 10 minute). Standalone DEVELOPMENT completed 546 groups (64 daily / 482 minute), 54,618,427 records. No confluence, protected/future outcomes, provider reads, or broker writes opened by this run.

Conditioning reused retained records: 504/1/63/63 chronological folds, minimum 60 opportunities / 30 sessions / 20 instruments. Of 45,516,323 test-eligible records, 36,259 were selected and 36,254 comparable. Mean primary/stress return -0.313660% / -0.466303%; 11/33 positive folds, 22 negative. Daily supplied 99.28% of selections. All 261 minute selections were `orb_15m_close_retest_v2`; both directions negative. Aggregate router FAILED / NO PROMOTION.

Post-result favorable slices below are specialist hypotheses, not validated strategies or a valid combined portfolio:

| Route / direction | Selected n | Primary / stress mean | Active folds, positive / negative | Disposition / limitation |
| --- | ---: | --- | --- | --- |
| `pract_bollinger_mean_reversion_v1` LONG | 5,516 | +0.4536% / +0.3032% | 21, 15 / 6 | Broadest specialist-development hypothesis; largest fold 21.9% |
| `donchian_breakout_20_volume_short_v1` SHORT | 379 | +0.6159% / +0.4664% | 15, 8 / 7 | Secondary candidate; largest fold 29.6%; short economics separate |
| `pract_adx_dmi_continuation_v1` LONG | 204 | +0.5269% / +0.3764% | 7, 3 / 4 | Exploratory; largest fold 38.7% |
| `pract_flag_pennant_v1` SHORT | 191 | +0.8811% / +0.7318% | 9, 7 / 2 | Exploratory; limited support; largest fold 38.7% |
| `rsi_recovery_14_trend_long_v1` LONG | 189 | +0.3706% / +0.2203% | 12, 6 / 6 | Exploratory; largest fold 31.7% |
| `pract_triangle_breakout_v1` LONG | 57 | +0.3271% / +0.1768% | 5, 2 / 3 | Insufficient/concentrated; 80.7% in one fold |

Many high-volume routes were negative, including EMA pullback LONG, MACD LONG/SHORT, relative-strength momentum LONG/SHORT, ATR-expansion LONG/SHORT, Bollinger SHORT, and multiple pattern/breakout directions. Selecting the six positive slices after outcomes would be post-selection.

Retained baseline daily MFE/MAE describes a 20-session excursion window; it cannot be reported as five-session excursion evidence. Separately computed selected five-session daily paths: 35,995 comparable cases, 143,980 threshold rows; entry next regular open, five instrument sessions; 1/2/3/5% favorable/adverse thresholds. Same-session collisions remain unordered. Many negative routes also reached 2-3% favorable excursion: timing, adverse path, and costs matter. Arithmetic mean of return/MFE is unstable near zero MFE and must not rank strategies; retained median and raw path distributions are the useful summaries. Underlying movement is not option P&L.

The 2026-10-12 review of the operator's uploaded retained artifacts reconciled the original 36,254 selected comparable cases, -0.313660% primary / -0.466303% stress means, and 11 positive / 22 negative folds without a source replay. Original full-summary snapshots and six matching aggregates support this selected-only review; the changed `route_summary.parquet` is excluded, so full DEVELOPMENT/test route means are not newly verified. For Bollinger mean reversion LONG, the five-session 2% favorable/adverse hit rates were 73.11% / 68.78%; favorable-first 43.49%, adverse-first 43.69%, and same-session unordered 10.88%. High favorable-hit frequency alone does not establish executable exit profit. This is existing evidence reconciliation; dispositions and trading authority are unchanged.

| Artifact | Fingerprint |
| --- | --- |
| Standalone scientific contract | `d962d72579996c26485a292469e6483132b413c484b90471aba74b209993cafb` |
| Standalone run | `c22bcb45b1a13dde11854f7ad166ae0abe1810fc0d6ab7371dbdd1165c1006e6` |
| Standalone artifact set | `4e5d66b8db1b37ac70dcff9e92fc4602bb729f90f18852db59f7e827de5a55d6` |
| Selected daily path analysis | `e89d1d61b7fe6875353816a11727f7ad4a0797917eac0ef4b2d437812a053e20` |

Detailed implementation: [successor laboratory](successor_practitioner_lab_preoutcome.md); historical diagnostic detail remains in the original register at the baseline commit.

## Literature-fidelity five-minute ORB v2

`orb_stocks_in_play_5m_literature_v2`: 40,606 top-20 selections; 33,773 entered / 23,412 comparable; 6,572 never entered / 10,361 same-minute entry-stop unordered. Comparable mean +0.12% gross / -0.38% at primary 50 bps / -0.88% at 100 bps. Both directions negative by 25 bps. Median hold 12 minutes; MFE/MAE 1.27% / 0.41%.

Entry-stop collisions are 30.68% of entered cases. Tight stop geometry is a diagnosis, not permission to retune v2. Preserve v2; do not sweep range, rank, relative volume, ATR stop, delay, or exit on the same DEVELOPMENT evidence. PARKED_COST_SENSITIVE / NO PROMOTION.

Analysis `cc6c34b18479aa76558e3c73cbc17ae75d85dd2c7b45d3806a8ac00d17b3a035`. [Immutable closeout](research/orb_stocks_in_play_literature_v2_development_closeout_20260916.md).

## Recurrent stock account and static exits

2025 outcome-replay diagnostic: $100,000 starting equity, 4,685 selected comparable / 3,650 supported LONG / 1,035 reported-only SHORT. 439 admitted/completed LONG positions; +1.6472% endpoint return and -20.9896% book drawdown. 3,211 rejected LONG opportunities reconcile; family cap dominated. This replay settles accepted terminal outcomes rather than testing new bar-level exits. Small positive endpoint is not a robust validated strategy.

Run `2096fe4bc3babdd80c667a0548ab24a861a586bd08f880237744f11b23378166`; contract `99c3b32b1905db3204646bac302a5b6836e843cbfe73d7647da9a84b8b879452`.

2025 daily exit sweep, 3,520 cases / 16 frozen pairs: 2% stop / 5% target +1.45% return, -9.20% marked drawdown, 649 completes; 3%/5% +0.46%, -13.11%, 575 completes. Other 14 pairs negative. The two positive candidates were frozen before later testing.

2026-01-01..2026-04-30 DEVELOPMENT confirmation, 1,831 cases: 2%/5% -6.38% return / -9.88% marked drawdown; 3%/5% -6.97% / -10.42%. Both FAILED forward confirmation. No retuning from that result.

Retrospective annual accounts with equal $100,000 starting equity:

| Year | 2%/5% return | 3%/5% return |
| --- | ---: | ---: |
| 2018 | -15.75% | -8.98% |
| 2019 | +6.60% | +6.64% |
| 2020 | -8.71% | -11.18% |
| 2021 | -21.19% | -18.76% |
| 2022 | -24.87% | -27.74% |
| 2023 | -9.79% | -9.24% |
| 2024 | -11.00% | -16.30% |

Only 2019 positive for both. STATIC_EXIT_UNIVERSAL_RULE_REJECTED / NO PROMOTION. This retrospective map cannot rescue failed confirmation.

| Artifact | Fingerprint |
| --- | --- |
| 2025 exit sweep | `2726c3a644ac22ed3238adf5b03e978152eaa50a5d0e91fc937716309f0db9f4` |
| 2026 confirmation | `bd8e1fd32d2c34e8699e6e243e851c936c475e0d5b16fc4f6047d5f02e40f210` |
| Static regime map | `60989a10985973bff48d3d2a82a633282b62e664f22f5c3fac4c35bfee380ede` |

## Dynamic Exit V1 and continuous V2

These experiments already occurred; neither is an accepted final dynamic-exit policy. V1 adapts the entry-bound choice among percentage pairs. V2 parameterizes continuous entry-bound levels. Neither establishes continuously moving in-position stops/targets.

V1 uses previous eight completed folds; six pairs (1%/2%, 1%/3%, 1%/5%, 2%/3%, 2%/5%, 3%/5%) plus ABSTAIN; fixed five-session horizon; minimum 60 cases / 30 sessions / 20 instruments. Prior session mean minus 1.645 standard errors must be positive, with positive mean trade return. Specific supported-negative cells cannot be rescued by broad fallback.

Stock V1: 22,604 usable cases / 32 folds; 535 selected (2.37%) / 22,069 abstained; 3,013 selected daily LONG cases lacked prior path support. Selected net mean -0.058%, median -2.099%, 41.31% positive. Actions: 49 at 2%/5%, 486 at 3%/5%. 2025 selected mean +0.147%; later 2026 Jan-Apr -0.468%. This is a selector diagnostic, not compounded account return. NO_GENERALIZATION / NO_PROMOTION.

The operator's 2026-10-12 read-only inspection of the original saved report reconciled all 22,069 abstentions: 3,951 (17.90%) `INSUFFICIENT_PRIOR_CONTEXT_SUPPORT`, and 18,118 (82.10%) `NO_SUPPORTED_ACTION_HAS_POSITIVE_ROBUST_LCB`. The latter label combines a nonpositive best-action confidence bound or nonpositive mean trade return; this summary cannot separate those causes or establish that every rejected action had negative mean return. Statistical support shortage is not proof that market files are missing. Of 535 selections, 520 used fallback level 1 and 15 level 4. Original report fingerprint: `6e526e6554413da41b9ddd7fc07bbe9ae1ae07c5a18e3f915bf8f4e8ac300ea7`. This is interpretation of existing evidence, not a new simulation or a threshold revision.

Contract `db538c8cc72189d4fcdb06b854ac8c8bf44e5b5b2798745dd0128f20b8f7cd9a`; run `560b35765e82b2ab5fb59f8b00cc641f28112232bf89a994fdb0637f069a2b5b`. [Original closeout](research/recurrent_successor_dynamic_exit_v1_acceptance_20260925.md).

EOD option V1: 354/14,733 target cases selected, all 2025, all 3%/5%. 93 source-ready pairs: mean premium return -11.56%, median -19.30%, 27.96% positive. Strict account 29 admitted / 26 completed / three unresolved; modeled realized P&L -$22,366.50, cash $58,622.05; equity/return NULL.

Continuous V2 used strictly-prior MAE/MFE and return quartiles, clipped stop 1-3%, target 2-5%, minimum target/stop 1.5x. Over 14,733 usable cases, stop mean 2.9986% (minimum 2.6853%, quartiles/median 3%); target exactly 5% in every case. It saturated rather than producing a broad dynamic surface.

2,055 source-ready pairs: mean premium return -14.06%, median -18.42%, 30.61% positive, mean -$75.01/contract. Every 2021-2025 annual paired mean negative. Strict account 84 admitted / 74 completed / ten unresolved; realized modeled P&L -$33,365.40, cash $24,997.70; equity/return NULL. 3,230 stock exits were not after the EOD option entry.

The 2026-10-14 operator retained-ledger review reconciled those original balances and memberships without replay or provider/source reads. All ten unresolved positions opened in 2021 and were labeled `STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP`: 226 contracts, $41,636.90 committed entry cash including fees, $146.90 reserved exit fees, $24,850.80 cash after reserve; terminal clock/equity/return remain unknown. Review fingerprint: `c06049ba1ca270f09fcb56d4927530ea78137fee6c0af8ceb23e1645ef51e474`. Original replay: `b525b49fabd0aead7f6fc5c8edf33e6f7c8d125de9253de6b7d9ecdf4c7516a7`; scenario: `03406fdf1def82332b8e01761213ab4cd4eb9e7a8cdb551ea37ad8c9d7bfcf5b`.

The uploaded review's complete self-signature and raw-file SHA `1197d49cb469f00bc91cbf617c24b2b2ac0d7738a81f37af3f41323a57ce5966` were verified on 2026-10-15. The subsequent operator exact-exit source audit completed that evening: all ten original sources / 226 contracts verified, no missing sources or classification disagreements; every snapshot matches its recorded stock exit clock. Nine legacy exits failed solely the positive-reported-volume check. CME failed solely the fixed 16:00 ET check, with its `2021-11-26T18:00:00+00:00` snapshot matching the early close. Four reported bids were smaller than their positions: OTTR 11/35, FOX 6/74, REYN 5/24, CME 10/13 contracts. A quote snapshot and its displayed size establish neither historical availability to an order nor a fill.

Operator-reported audit fingerprint: `81ef6487f0f0cd99431d33136a14c97294c6c704b270b88a21e75c459b0427f7`; saved report: `data/research/retained_option_exit_source_audit_v1/20261016T021014995089Z_f361ff14.json`. The saved JSON has not been independently inspected in this chat. This diagnoses the retained rejection rules; it does not resolve the account, revise V2 exits/costs or create profitability evidence. The separate synthetic partial-fill extension tests accounting only and creates no historical executions.

The original $0.65-per-contract entry/exit fees are generic model assumptions, not a qualified broker schedule; zero additional option slippage is also retained. This review verifies recorded arithmetic, not actual Webull/Alpaca charges, historical fills or settlement. Broker/account/date-specific costs remain an engineering dependency in the roadmap. Original costs, negative results and unknown equity remain unchanged; no fee-adjusted rerun or strategy promotion occurred.

EXIT_GEOMETRY_BRANCH_CLOSED / NO_V3_FROM_SAME_DEVELOPMENT_EVIDENCE / NO_PROMOTION. The closed branch does not prohibit all future dynamic-exit research; it prohibits rescuing this experiment by tuning its observed outcomes. [V2 closeout](research/continuous_dynamic_exit_v2_closeout_20261002.md).

## Option account and clock forensics

Initial EOD option plumbing replay used first later qualified liquid EOD exit, not stock STOP/TARGET/TIME. CALL modeled realized P&L -$99,108.00, $182.05 cash, two unresolved; PUT counterfactual -$99,443.90, $304.15 cash, three unresolved. These are plumbing diagnostics, not valid intended-strategy performance.

Static exact-session controls had 1,493 (2%/5%) and 2,055 (3%/5%) source-ready pairs. Strict accounts completed 58/74 positions with ten unresolved each; ending cash $26,147.70 / $24,997.70; realized P&L -$28,764.50 / -$33,365.40. Future exit-source availability conditions paired samples; they are not causal accounts.

Entry-clock forensics: 3,230/5,785 causal EOD CALL entries (55.83%) arrived after/not before stock exit; median lag 30.42 hours; median pre-entry absolute stock move 2.32%; 20.78% moved >=5%; 35.96% changed CALL moneyness. Late-entry share: STOP 75.36%, TARGET 57.55%, TIME 0.96%. Paired coverage is systematically biased toward surviving trades. Ten unresolved 2021 positions consumed all slots in strict replay; meaningful 2022-2025 account return was unavailable.

EOD_OPTION_PERFORMANCE_AS_ORIGINAL_STRATEGY_CLOSED / NO_PROMOTION. [Clock forensic record](research/eod_option_entry_clock_forensics_v1_20261002.md).

Offline minute clock: 9,667/9,974 option-expressible cases after 09:35; 304 already exited at/before 09:35; three minute-trigger gaps. Only 51 (0.5113%) changed daily STOP/TARGET ordering. No option provider/outcome read.

Causal 09:35 spot: 9,654/9,667 ready, 13 missing completed regular minute. Median absolute open-to-decision move 0.4660%, mean 0.6562%, P90 1.5422%; 22.81% moved >=1%. Old open-selected CALL was ATM in only 54 cases, median absolute strike distance 1.4266%. Old 18,921 single-contract requests superseded by 9,455 provider-agnostic candidate surfaces.

ThetaData quote/OI/Greeks plans and Terminal preflight are implemented source preparation only. Quote/OI qualification, full acquisition, contract selection, exact exit pricing, authoritative Greeks, historical fill/strategy/PAPER/LIVE authority remain downstream. No news-derived strategy has been validated. Source successes must not be counted as alpha.

## Retained closed research

Phases26-32 and later XBRL, beneficial ownership, FINRA short interest, SEC EPS, and Form13F branches remain accepted-negative/source-limited as originally recorded. They are not active tuning queues. Source defects, failed V1 validations, and later narrowly scoped repair acceptance retain separate verdicts. Refer to their immutable specs/closeouts and the baseline full register for exact lineage.

Future entries record strategy/version, contract/run/source identities, population/dates, prior-only training/test design, costs, support, gross/net results, drawdown/concentration/coverage, unresolved cases, multiplicity, disposition, limitations, and authority. Update this ledger in place; do not recreate acquisition diaries here.
