# ATLAS Strategy Evidence Register

**V71 independent original-source findings (2026-10-31):** Original SPY June4 and June13 10:00:01 quote rejections are above the 15% spread quality limit; later qualified observations occur at 10:00:06 / 10:00:02 respectively. These are observation continuity facts, not actual fills or license to alter immutable prior P&L. Original candidate native 1-minute SPY month inventory 124; Jan/Feb/Apr/May blocked by XNYS calendar misclassification while March has 12 source archives, 1 explicit no-data, 6 closes, 5 unresolved. Partial closed P&L is NOT monthly performance. [Methodology](research/spy_v71_original_exit_clock_and_month_horizon_20261031.md).

**V70 evidence-based chronological ledger (2026-10-31):** The user completed V69 six-weekday 2025-06-23–30 source-first replay and supplied full signed archives. Four original contract acquisitions and four closed quote-reference trades were verified: June 23 +$488.10, June 25 −$204.90, June 27 +$496.20, June 30 −$249.20, alongside two Tue/Thu no-signals. This is +$530.20 of **standalone resolved** quote trades; V70 checks and links each source/strategy/fee/entry/exit before constructing a proposed chronological cash ledger starting $25k. The expected six-weekday settled end is $25,530.20 only if independently re-accepted by the V70 ledger gates. June 13 in the earlier interval remains unresolved; never stitch that blocked account forward or claim monthly/annual alpha. [V70 cash-account protocol](research/spy_v70_verified_chronological_quote_account_20261031.md).

**V68 execution sensitivity (2026-10-31, development only):** User-verified V67 originally acquired missing June 16/18/20 exact SPY quote tapes and reran ten weekdays. The complete June 9–20 reference outcome census is two closed ($−189.20 June 9, $+410.80 June 16), three 1% ask-drift no-entries (June 11 +3.053%, June 18 +1.25%, June 20 +1.515%), four Tue/Thu exclusions, and one **unresolved** June 13 quote exit. Two settled standalone P&L items total +$221.60 but MUST NOT be represented as a portfolio return because June 13 has no qualified close. V68 tests only existing V55 1s/3s and 0.5/1/2% execution policies as **post-hoc diagnostics**, with full saved quote event streams and original 1s/1% fingerprint reproduction. No historical fill or validated alpha. [V68 analysis](research/spy_v68_original_quote_execution_sensitivity_20261031.md).

**V66 exact missing June SPY tape recovery (2026-10-31):** User-verified V65 10/10 weekday offline inventory showed 6 frozen M/W/F signals, 3 previously archived exact-contract sources, and exactly **3 NOT_REGISTERED** source scopes: 2025-06-16 SPY 602 CALL from 09:42:01, 2025-06-18 SPY 599 CALL from 09:48:01, 2025-06-20 SPY 599 CALL from 09:38:01. V66 is a single-cohort source test, not an ATLAS-wide acquisition limit. It now continues other distinct source downloads despite a failed query, with each uncertain query left blocked for reconciliation. V66 pins the complete V65 evidence fingerprint, rechecks exact source query IDs in SQLite read-only before each call, persists an immutable dispatch intent BEFORE an individual on-demand ThetaData historical GET, uses verified V38 canonical/gzip SHA archives, and blocks all retry of FAILED_RETRYABLE or IN_FLIGHT requests. Continues with independently needed sources after ambiguity, without retrying the same query; broker trades=0, no P&L simulation or profitability claims. [Protocol](research/spy_v66_three_exact_missing_option_tapes_20261031.md).

**V65 full June 2025 offline source and simulator readiness (2026-10-31):** V64 found an independently measured $0.735 SPY midpoint rise in 1s during the June 13 $0.65 PUT 598 bid collapse; this does NOT prove a bad bid. Rather than continue one-date ThetaData requests, inventory each June 9–20 weekday using unchanged V55 closed-minute ORB policy and verified native SPY minute source, lookup exact V56 1s option-source scopes in V38 SQLite `mode=ro`, and replay already SHA-archived options only as isolated per-day quote reference. Log all signals, censor reasons, unknown/failed/never-cached sources, and avoid ANY new paid provider GETs, retries, broker fills or cumulative-account claims. [Protocol](research/spy_v65_full_june_offline_simulator_source_matrix_20261031.md).

**V64 safe post-timeout two-clock forensics (2026-10-31):** V63 passed 13 local tests but its first read-through ThetaData prior put-surface request stopped after ~179 seconds with `ThetaDataError` and no accepted source report. The isolated SDK worker has a 180s timeout; V38 marks any exception `FAILED_RETRYABLE`, which does **not** prove that the attempted provider dispatch was never received. Do **not** repeat this exact V63 query automatically. V64 independently audits the exact V38 SQLite registry state in `mode=ro`, the existing V56 SHA-verifiable SPY put 598 one-second option tape and original V62 1,467 stock quote rows, reporting prior/current bid/ask and underlying movements without any provider requests or fabricated IV/fills/profit. [Offline source and quote diagnosis](research/spy_v64_failed_prior_surface_two_clock_forensics_20261031.md).

**V63 independent prior option volatility input (2026-10-31):** The V62 workstation verified 1,467 original SIP stock quotes in one raw SHA page and a prior-to-10:00:01 SPY bid/ask of $598.63/$598.88. V63 verifies these original stock pages, selects a separate SPY reference at/before 09:59:59, then reuses/fetches exactly one 09:59:59 0DTE PUT quote surface through V38 immutable ThetaData source cache. The original SPY 598 put and future observation clocks are excluded from potential IV calibration. Captures original candidate counts/expiry/method/source SHA but **does not fabricate an IV band, historical carry inputs, fills or net profitability**. [Prior-option source protocol](research/spy_v63_independent_prior_iv_surface_20261031.md).

**V62 independent SPY spot quote source (2026-10-31):** Bounded historical Alpaca SIP quote GET for a 4-second June 13, 2025 window around 10:00:01; original page bytes plus SHA-256 archived before follow-on pages, nanosecond-strict no-future selection, up to 12 pages and no inferred completion if truncated. Bid/ask/size/condition/provenance recorded, but a stock quote alone cannot produce independent option IV or guarantee option fills. Original V61 09:59 SPY minute close $598.15 remains a **minute bar** not a one-second quote. [Source capture specification](research/spy_v62_narrow_spot_capture_20261031.md).

**V61 independent valuation input readiness (2026-10-31):** Audit the original V56 June 13 source and SHA journal, the accepted 2025 June SPY minute-bar checkpoint and only existing V38 option receipt metadata. It distinguishes already-verified SPY 1-minute OHLC from a point-in-time stock BID/ASK at 10:00:01 and reports candidate independent earlier option tapes without assuming they prove IV. Missing stock tick/IV/PIT rates/dividends means BSM action-side evaluation **ABSTAINS** rather than treating a historical suspect midpoint as fair. Read-only and zero provider or broker requests. [Specification](research/spy_v61_independent_reference_readiness_20261031.md).

**V60 action-side quote valuation (2026-10-31):** User-directed alternative to blanket spread rejection. For BUY evaluate the same option's ASK; for SELL evaluate BID; use independently timed SPY spot, independently calibrated earlier IV-band, historical rate/dividend and actual displayed side size. A wide spread because the *opposite* side is anomalous can make the acted side a further-execution-gates candidate. Never infer fair value from the same suspect option midpoint or use BSM to fabricate a broker fill. The June 13 SPY 598 PUT BID $1.05 / ASK $1.60 remains unapproved without a verified independent at-time spot and volatility band. [Research contract](research/spy_v60_independent_action_side_valuation_20261031.md).

**V59 read-only historical source diagnosis (2026-10-30):** V58 successfully verified the V56 June 9–13 report and one paired trade (+$64 modeled on June 9), but June 11 is NO_ENTRY and June 13 is an UNRESOLVED_POSITION that blocked the remaining five weekdays and independent cash finalization. Their exact causes have not been established from the console summary. V59 will verify original per-date SHA journals and exact archived V38 quote tape **without provider calls**, record the original censor code, rejection index, bid/ask spread and size, quote observation gaps and neighboring raw source observations before any replay rule is changed. [Source-forensics protocol](research/spy_v59_offline_quote_forensics_20261030.md).

**V58 offline matched-cohort adaptive portfolio (October 30, 2026):** An independent-cash shadow over V56's immutable per-day quote journals is under development. It recalculates V57's dollar risk stop from *adaptive* equity each session, reports per-day baseline/adaptive net outcomes, matched deltas, drawdown and weekly/monthly/annual counts, and blocks rather than fabricating P&L when a shadow exit needs quotes past the original fixed-exit close. No further ThetaData requests. Parameters remain post-June-9 chosen and performance **not validated**. [Technical specification](research/spy_v58_independent_adaptive_cohort_20261030.md).

**V57 dynamic exit candidate (October 30, 2026):** To avoid an untested fixed +100% profit target / -50% stop, introduced a **separate, retrospectively labeled in-sample** adaptive single-option quote-exit research shadow on V55/V56 immutable JSON+SHA event receipts, requiring no new provider data. It updates a 0.5%-of-account **desired** risk-loss budget (not guaranteed loss cap), original spread/size, prior quote movement, 20% profit activation, 10–20% non-loosening high-water trail, and a 15:00 exit for every observed quote. Never claim actual fills, future high prediction, or out-of-sample edge. A potential next-five-minute high *envelope* is an untrained logging heuristic only; next tests require real earlier-only model training and later independent fold evaluation. [Research specification](research/spy_v57_dynamic_risk_exit_20261030.md).

**ATLAS V55 accepted one-session quote simulation / V56 next cohort (Oct 30, 2026):** V55 original June 9, 2025 workstation: SPY 600C 0DTE at 10:33:02 ET, 4 theoretical contracts, entry $474.60 incl. fee, exit $285.40 incl. fee at 15:30, **net -$189.20**, terminal $24,810.80 from $25k; 17,820 original 1-second option quote rows and independently verified 17,825-record append-only SHA journal. This is **development quote-reference**, not original first-tick strategy, historical broker fill, PIT publication proof, or validated alpha. Broad checkpoint discovery consumed about 405 seconds. V56 narrows native checkpoint metadata to the requested month while still verifying both SHA-pinned original source files and extends identical V55 decisions across consecutive sessions, with cache-first new option sources, a chronological fee-aware cash account, fully retained per-session JSON/JSONL and weekly/monthly/annual reports. [V56 runbook](research/spy_v56_multi_session_quote_account_20261030.md).

**V55 first integrated development quote-reference simulation (Oct 30, 2026):** A separately registered SPY 0DTE **completed-minute CLOSE** breakout (NOT the external first-tick ORB) now connects SHA-verified existing SPY minute sources to dynamic cache-first exact one-day options 1s quotes, then a chronological single-long-option $25k quote account with $500 premium cap, 1s/3s latency variants, adverse action-price guard, +100%/-50%/15:30 exits, per-observation decisions, fee-aware cash and immutable hash-chained JSONL. Missing/incompatible quotes censor outcomes; historical publication, actual fills and profitability remain unverified. Pending workstation acceptance. [V55 runbook](research/spy_v55_closed_bar_0dte_quote_simulation_20261030.md).

**Mandatory ATLAS console observability for all workstation commands (updated October 30, 2026):** Every launcher, local source SHA verification, provider canary, acquisition and simulation must announce potentially blocking phases *before* they begin with ET timestamps and flushed console output. For measurable work, print 10%-completed milestones with completed/total, true elapsed time, throughput and approximate ETA; show source identity, cache/provider attempts and failures when relevant. A single provider GET with unknown internal progress must print START before the call and completion/error after it, never fabricate percentage or fill status. No repetitive time-based heartbeats or separate progress log. Never hand the user a potentially ten-minute-silent command. **Future ATLAS chats must apply [the authoritative living operating progress contract](architecture/atlas_living_operating_requirements_20261029.md#october-30-extension--required-observability-on-every-operator-launcher-including-v51v52) before writing a runnable command.**

## V49 operator run — independently verified original source decision audit (Oct 30, 2026)

Accepted full original JSON and event journal: 411 original frozen weeks, 361 detailed opportunity IDs, 50 earlier source-less abstentions, 106 hypothetical long signal cases, 206 hypothetical abstentions, 38 source-quality rejects, 7 scenario-dependent, 2 missing prior-volatility proxy and 2 identical call/put source reviews. The **all-363-event append-only journal's complete record-chain SHA validated independently** against the reported trace fingerprint `9dbfa6c1d69d06deab4a842db52bb52e5beea31a73a68973fb27d043363fb1fe`. Original 09:59 paired 1s skew passes **323/339**, diagnostic 3s **336/339**, while 10:01 passes **339/339** under either; 14 of 18 censored future exits would meet 3s **on skew alone**. Two-minute 09:59→10:01 combined ASK absolute drift <=0.5% in **326/339**, <=1% **336/339** and <=2% **338/339**; **not actual 1–3s order latency**. V49 generated zero new provider/broker calls and zero actual trades. No original 1s-gate revision or success promotion; original V47/V48 adverse quote-reference economics stand. [Full accepted V49 workstation audit and immutable receipt identifiers](research/spy_v49_workstation_audit_accepted_20261030.md).

**Original scientific consolidation 2026-10-12 at `64175780`; source-only continuation reviewed through merged PR #354 (`94807e2e`) on 2026-10-22. No new performance evidence opened.**

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

## Options-native pilot v1 — specified; exploratory exit-price evidence negative, no validated performance

On 2026-10-15 the user approved making options-native discovery a primary branch alongside independent stock research. The first code-registered specification is `options-native-spy-long-straddle-v1`: one SPY common-strike/expiry CALL+PUT pair, a fixed twenty-prior-return volatility estimator versus same-maturity ATM implied variance, daily thesis-based exit and five-session maximum hold. The [guide](roadmap.md#options-native-pilot-and-data-contract) describes scope/dependencies; the [contract](../packages/strategies/options_native_pilot_v1_contract.py) owns exact rules. Specification fingerprint: `e3ad55ad153ca61432bfde65aa0b5c54004766866a2919a567b6b5ade551efca`.

Budget: one strategy variant, qualified primary and predeclared spread/latency stress. The independent discovery plan has 411 weekly 2018-2025 CALL/PUT surfaces, including 2020, and excludes seven clocks by a predetermined maturity buffer. No historical prices/outcomes were read, provider calls made, historical trades simulated or workstation trial ledger appended. Synthetic feature and plan tests establish mechanics only. Source availability/clock models, broker fees and multi-leg execution/lifecycle remain unqualified. Append a matching draft to the existing trial ledger before any authorized outcome read. Earlier history is DEVELOPMENT, not untouched qualification; no consumed 2026 outcomes or post-result regime pruning are permitted. Status: SPECIFIED_NOT_PERFORMANCE_TESTED / NO_PROMOTION.

On 2026-10-16 the unchanged pilot gained synthetic exact-pair geometry, daily thesis/session/DTE exit requests and a separate two-leg receipt-driven account coordinator. Fixtures test lone-leg exposure, final unfilled cancellations, fee reserves, exact basis/P&L, unsettled proceeds, cash settlement and unknown valuation. They establish no historical fills, broker costs, exercise outcomes or strategy performance. No new variant, trial-ledger append, historical replay or promotion occurred in that engineering package.

The operator subsequently completed the raw-input packet and supplied its JSON. Independent inspection reconciles 21/21 SPY closes, the exact 2019-12-04..2020-01-03 prior window, its signature and two source-unit bindings. Report `92c4d71997ec3225d5040f00375fc4ad66d654be6ce4a6cb81136a87d75374dc`, raw-file SHA-256 `e02946c3390626bf8f1b1aee13081febfbc00ae100c8f1a8bf272e868a444459`. Economic returns, forecast and historical availability remain unqualified. The cached input follow-up subsequently completed on the workstation with 22/22 exact minute observations. The 411-week physical coverage review found 407 complete weeks and one missing closing-minute bar affecting four decisions; original State Street cash distributions reconciled 33/33 dates, with the archival 2018-06-15 omission retained. The 33-event publication demand maps 149 retrospective dividend-exposed, price-complete weeks but retains zero original as-of publication receipts. The PR #338 multi-underlying 09:35 CALL-only source census completed on 2026-10-17: **815 underlyings / 9,455 deduplicated source requests / 9,654 case memberships** across 2021-09-28..2025-12-24 (report fingerprint `713fae99a3e4a769829bfcf6ac43512ebdc8c25631cf1045632c474b0919c54c`). This is a retained plan/metadata receipt only: historical option series, original PIT issuer actions, CALL/PUT prices, OI, fills, P&L, and strategy evidence remain unqualified. The independent 411-week SPY 10:00 CALL+PUT pilot is not part of this demand count. No historical strategy outcome, fee change, new variant or performance authority is created. The guide owns downstream source prerequisites.

### October 30, 2026 V47/V48 development evidence (NO PROMOTION)

User-uploaded immutable V47 report fingerprint `9eea1abc12eca482d967cad172a9a2851b7c8cfc0879a7f97104d4bed01e855d` examined 106 **non-PIT, hypothetical** SPY long-straddle signals across 1–5 fixed-hold research horizons; **48** are frozen-original source pairs and **58** a separately versioned OI-selected alternate. Of 1,060 requested individual future CALL/PUT quotes, 1,058 were archived, 2 failed ThetaData Python worker ValueError on the same 2020-05-01 exit; among 530 historical option paired exits 510 qualified and 20 censored (18 cross-right quote timestamp skew, 1 excessive spread, 1 missing pair). Primary quote-reference conditional mean returns by hold: **-1.23, -1.24, -0.54, -0.60, +0.57%**; medians **-1.88, -2.38, -1.07, -3.78, -4.31%**; all five stressed means negative. The +0.57% five-day mean reverses to **about -0.57%** without one +114.38% observation. Only fully resolved $100K account is **frozen-original, one session**, 48 closures/16 winners, ending **$98,169.20** primary and **$96,861.20** with extra spread; **20/29 active months** negative. Other account variants block on censored positions, not zero-imputed.

**Disposition: CONDITIONAL NEGATIVE EXPLORATORY / NO PROMOTION / avoid hindsight exit optimization.** The 2018–2025 fixed-hold quote reference screen is development data conditioned on hypothetical rates/yields and non-PIT raw prior-return volatility, not the original registered American-IV daily dynamic-exit signal, point-in-time publication, executable multi-leg fills, or an independent profitability validation. Preserve frozen v1, alternate, and all unknown fills. Do not lower liquidity/skew gates to rescue P&L or reopen consumed 2026 holdout. Next: a reusable real sequential options fill/position simulator with causal sources and predeclared distinct research strategies, rather than trying to rescue straddle fixed-hold means. See [V48 detailed evidence](research/spy_v48_v47_development_evidence_20261030.md). No strategy is approved for live/paper execution by this entry.

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

ThetaData quote/OI/Greeks plans and direct Python-library worker preflight are implemented source preparation only. The operator's 2026-10-20 local setup verified the isolated Python 3.14.0 / ThetaData SDK 1.0.12 / python-dotenv 1.2.4 package environment and expected method signatures with zero provider requests; it reported `auth_material_present=False`. This is package/interface readiness, not authenticated or historical-source qualification. PR #347 (`3d0514aa`) now blocks legacy dollar-dividend binomial Greeks at the worker boundary until an explicitly unit-qualified successor contract is accepted; quote/OI are unaffected by that safeguard. The operator subsequently corrected local API-key discovery and, on 2026-10-20, completed zero-request full readiness: the pinned SDK passed, authentication material was detected via `THETADATA_API_KEY_ENV`, both signed source/enrichment plans were valid and linked, and `READY_FOR_BOUNDED_SOURCE_QUALIFICATION` was reported. This means offline package/plan/key-presence readiness only; no ThetaData auth response, subscription entitlement or historical quote/OI/Greeks request has been observed or accepted. The installed 1.0.12 SDK explicitly reported `sdk_greeks_dollar_dividend_keyword=KEYWORD_NOT_ACCEPTED`; the already-installed historical binomial Greeks guard remains mandatory. The combined quote/OI qualifier now reruns this zero-data preflight on every authorized execution, immediately before potential provider reads. No original source, plan, research result or protected outcome changed.

The first actual provider response on 2026-10-20 was limited to **two Free-tier EOD methods**, both successful: stock SPY 2026-10-16 returned 1 row/16 columns; SPY CALL expiration 2026-11-20 on that observation day returned 4 rows/20 columns. Operator-retained SDK-normalized JSON: `data/options/diagnostics/thetadata_free_eod_shape_probe_v1_10e5303150d1e72b.json`. It establishes authenticated Free EOD delivery and response shape only, **not** access to 09:35 historical option quotes, open interest or Greeks, nor existence of causal execution prices, broker fills, profitable strategies or retroactive EOD availability at intraday decision time. Sample option `created` and `last_trade` are after 16:00 ET. Preserve original raw market-source/provenance boundary: this is SDK-normalized dataframe evidence, not provider-native wire bytes. The independent local fingerprint audit is a no-provider-read source review, not a backtest.

No ThetaData quote/OI/Greeks response has been accepted. Frozen historical source manifests were not regenerated. Quote/OI qualification, full acquisition, contract selection, exact exit pricing, authoritative Greeks, historical fill/strategy/PAPER/LIVE authority remain downstream. No news-derived strategy has been validated. Source successes must not be counted as alpha.

## Retained closed research

Phases26-32 and later XBRL, beneficial ownership, FINRA short interest, SEC EPS, and Form13F branches remain accepted-negative/source-limited as originally recorded. They are not active tuning queues. Source defects, failed V1 validations, and later narrowly scoped repair acceptance retain separate verdicts. Refer to their immutable specs/closeouts and the baseline full register for exact lineage.

Future entries record strategy/version, contract/run/source identities, population/dates, prior-only training/test design, costs, support, gross/net results, drawdown/concentration/coverage, unresolved cases, multiplicity, disposition, limitations, and authority. Update this ledger in place; do not recreate acquisition diaries here.


## 2026-10-31 — V78 second-half 2025 pre-registered exit comparison (experimental; not promoted)

The original V77 H2 2025 study completed 128 actual XNYS market sessions using SHA-qualified original 1-minute SPY stock source and 77 new ThetaData exact option source requests, all archived with no source gaps; zero live broker orders. A separate standard-library V78 audit verified every one of the 31 compact signed JSON documents and its linked six-month daily exit summaries. V74 control 1s has -$407.70 closed-only across 60 exits and one July30 `INVALID_QUOTE_BLACKOUT_EXCEEDED`; the other four exit challengers have 61 closes. In 1s lag: defensive -$1,067.60, balanced -$160.60, fast -$970.60, runner +$492.40; 3s runner +$444.40. The runner's largest one-day winner +$670.80 exceeds its whole H2 net closed subset, meaning removal of one lucky winner yields -$178.40. Runner lost 2/6 months and 12/27 ISO weeks, maximum cumulative closed-only drawdown $934.60 (not account cash). Risk/reward and broker/venue execution are unverified; NO policy passes consistent net profitability gate. Keep original policy ledger and all rejected quotes/skip reasons. Do not count this as confirmed alpha, OOS strategy promotion, cash account or full multi-strategy simulator. See [V78 audit](research/spy_v78_original_quote_2025h2_independent_economics_20261031.md).


## 2026-10-31 — V79 original journal execution-price uncertainty / V80 diagnostic gate

Independent full original event audit validated 244 SHA-linked compressed V76 event files against six original monthly source manifests: 242 quoted sell-to-close action candidates, two unresolved original July30 control variants, zero broker orders/fills, 94 quote rejection observations and ten insufficient-quoted-size events. July30 runner modeled -$171.90 before control's later invalid quote blackout; August20 runner modeled +$670.80 at four-contract option action BID $2.79 with displayed bid size nine but **no venue ack/fill**. At 1% allowable additional adverse trigger-to-action BID drift, runner 1s has 39 original sell-limit marketable quotes, seven needing an unexecuted price update and 15 exceeding the 1% gate. Runner 3s is 36/5/20. 2% hypothetical additional exit BID haircut erases all runner H2 modeled net gains. Never label these quote action cases as realized P&L. V80 independent event-to-order price protection returns no credited cash or real filled state, and does not change original strategy/offer production broker access. [V79/V80 study](research/spy_v79_event_forensics_v80_execution_price_guard_20261031.md).

## 2026-10-31 — V81–V83 new SPY entry families (development only, no profitability claims)

Prior V79 archive reconciliation: 244 signed V76 option exit journals, 242 modeled quote-reference close candidates, two censored July30 V74 cases, zero actual broker orders/fills. Six-month H2 runner quoted P&L +$492.40 (1s) / +$444.40 (3s), 2% adverse additional exit-bid stress turns both negative; the August20 +$670.80 outlier dominates. V80 models original sell-limit action marketability without claiming execution. The prior SPY opening-range study and entire inspected 2025 H2 period are NOT held out; neither runner nor control has validated alpha.

New V82 candidate families: `orb_continuation_0940`, `failed_breakout_fade_0940`, `gap_fade_0935`, with original completed SPY stock-minute bars, prior XNYS close and explicit strict option-selection evidence clocks. V83 is a zero-provider stock-source screen by default. Its output is the number of considered sessions, signals, skipped/blocked cases and new exact option-source needs, **not** trade/economic returns. The V81 broker order lifecycle currently uses synthetic order fixtures and cannot prove any historical Webull or Alpaca fill. All new candidates have status `RESEARCH_SOURCE_SELECTION_REQUIRED / NO_PROMOTION`, and stock fallback remains unpriced/unexecuted. The required next gates are original listing/liquidity, cash/broker uncertainty, independently priced entry/exit, execution sensitivity, isolated strategies then shared-account risk, weekly/monthly/annual evaluation and prior-only out-of-sample testing. See [V81–V83 research](research/spy_v81_v82_v83_execution_and_three_entry_family_launch_20261031.md).

## 2026-10-31 — V83 original SPY three-family signal denominator (user-run; no trade P&L)

Original H2 2025 v1 signed ZIP independently reconciled: 128 XNYS trading sessions, 384 strategy decisions, 101 source-demand candidates, 283 no-signals, 97 days with any signal (four dual-family days), 0 missing stock sources, 0 broker orders, 0 ThetaData GETs. Breakdown: 09:40 ORB continuation 45 (22 CALL / 23 PUT), 09:40 failed breakout reversal 51 (22 CALL / 29 PUT), 09:35 previous-close gap fade 5 (1 CALL / 4 PUT). Candidate 0DTE contracts and original 2025 performance remain unproven; source demand does not equal an executable fill or capital-constrained position. The 2025 H2 months have already been inspected, so this is DEVELOPMENT / NO PROMOTION.

Three accepted early-close dates (2025-07-03, 2025-11-28, 2025-12-24) carried an invalid 15:30 ET original option-source end. Preserve original v1 signed report, use V83 v2's authoritative XNYS 13:00 close → 12:05 cutoff source derivative with new request identities. V39 source fetches and trade economics are still pending; no strategy has passed weekly/monthly/annual after-cost profitability, holdout, broker or shared-capital gates.

## 2026-10-31 — V83 ThetaData source acquisition completed; V84 quote research pending

V83 v2 original 2025 H2 source campaign from workstation: all 101 signed exact option-tape demands resolved, 96 provider fetches, five cache hits, no missing, no ambiguous current/prior dispatch, zero broker orders, 35 local regressions passed. The four-document signed ZIP was independently hash-checked and cross-linked, including all 101 demand/source identities and actual 12:05 ET half-day source scopes. Original 2025 H2 remains *in-sample*, no option P&L has yet been demonstrated. V84 now implements source-only read-only quote-reference replay for three fixed alternative exit policies and 1s/3s lags. P&L is a hypothetical BID/ASK reference, not guaranteed executions, and does not net unclosed positions or reconcile shared cash. Closed-only weekly/monthly/yearly totals and no-entry/censoring counts must be examined before any alpha promotion. Remain NOT PROMOTED.
