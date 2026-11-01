# V95 completed eight-cohort exploratory profitability evidence audit — 2026-11-01

## Verdict

**REJECT current common six-hypothesis one-slot portfolio for deployment.** The fixed `balanced_35_100` / 3-second action lag / 10-second original limit-rest / 2%-adverse exit BID quote reference was **negative in six of eight available historical cohorts**. Aggregate eight-period nominal *hypothetical, non-compounded* cash P&L: **−$6,915.76**, including **−$2,222.20 in full 2022** and **−$2,048.16 in full 2023**. The two positive combined periods are 2024 full +$378.26 and 2025 H2 +$461.48; 2026 January–April −$833.16. Across **163/168** fully comparable execution configurations **zero** were positive in every one of the eight cohorts. Five configurations have original 2024 cash/expiry uncertainty and remain censored. Original **2020** cohort is **not scored**, because three option source demands still lack qualified source outcomes. This is a historical quote model, not broker fill proof, live track record, or a statistically independent backtest.

**Sources:** user uploaded the complete console log fragment `Pasted text(20261101-165748).txt` (starts partway through 2022 and covers successful 2022/2023 and V95 summary), the complete immutable `spy_v95_eight_complete_regimes_2020_censored_matrix_20261101_113934.zip`, and the 2023 complete `spy_v95_v90_six_families_2023_full_20261101_113934.zip`. Other V95 2020 reconciliation, 2021 and 2022 original ZIPs were **not uploaded in this turn**. The matrix and 2023 ZIP passed independent verification described below. Earlier original 2018–2024 raw tapes, original signed 2021/2022 V89/V90 reports, and original 2020 read-only forensic receipts are represented through **SHA references inside V95 matrix**, not independently reopened in this particular audit. Do not claim their underlying option 1-second original bytes were independently rehashed here.

## Verified uploaded evidence integrity

- Both uploaded ZIPs pass full ZipFile CRC tests.
- V95 comparison `summary.json` SHA-256 compact canonical JSON + newline fingerprint **`19fb792356929289cd9c9771fb77366ca3509cd37aa391d14901fe40f78b40cf`**, signed `full_matrix.json` fingerprint **`4a4b0ccacc03e58a8e14634553adf5ea8b98ad9b0c361bb88503b015eaefe683`**, exact signed `summary.matrix_sha` parent link, and CSV byte SHA-256 **`40a4e50b21a696a2a42c148e421d45219a150ec014199104a99a794f231092a7`** all verified without mismatch.
- Exactly **1,344** matrix rows = 8 cohorts × 7 original capital scopes × 3 stop/target policies × 2 action delays × 4 original sell-limit resting windows. Cohort exact start/end, available stock source SHA roots, original V89/V90 report root fingerprints and all embedded capital ledger fingerprints are **reported** in matrix provenance, but every prior ZIP must be supplied to independently rehash those original contents. **163** variants complete in all eight, **5** censored in original 2024, **0** positive in all eight, **0** provider/broker calls during matrix. Original 2020 read-only forensic report hash **`c84c9f4cc3ff2b2d2755600482f87debac31129e7945ad61313cc543f432d4e4`** and original source census hash **`10f9096f18b93b0618a54cb81775501255c7c676b9df68702ba8c1f91cda890a`** linked in matrix; original 2020 quote-PnL null; **3** original 2020 source demands censored.
- Independent 2023 V90: top-level `summary.json` fingerprint **`f17b7a7006e6897bfae45688635c43366b90b73e097571203a491949e2542c59`**, `portfolio_ledgers.json` fingerprint **`913f1994b9929bd5fedc9082c46f4bd403227d700b0f17474a039d01154eb15f`**, **168/168** embedded capital-ledger fingerprints individually verified and **168/168** match V95 matrix original `portfolio_sha` fields. `trial_manifest.json` contains exactly **2,328** trials = 97 original exact option sources × 24 execution variants. **2,328/2,328** compressed file-byte SHA-256 and gzip size match manifest; each uncompressed journal fingerprint, embedded original V84 entry trial signature, V86 exit-recheck signature, trial parent link, source SHA, causal stock-decision/demand SHA, policy/lag/limit-rest identity, zero orders/providers checked. **Zero mismatches**.
- Independent full 2023 cash accounting across all **168** ledgers: SHA validation, count of original entry-reference events, rejected-entry events, capacity-conflict events, closed-exit events, sum of stressed quote exit P&L, original monthly/weekly cash subtotal, and $25,000 nominal starting-cash-to-ending-cash reconciliation **all passed**. Original full-resolution provider quote cache bytes live on the local workstation, not in evidence ZIP; no independent raw ThetaData byte rehash or live fills.
- Console excerpt confirms 2022: original 251 sessions, 1,506 six-family decisions, 152 exact option source requirements, **140 paid provider dispatches**, 3,648 source-linked quote journals, 168 portfolio scenarios, zero censored portfolios; 2023: 250 sessions, 1,500 decisions, 97 exact requirements, **92 paid provider dispatches**, 2,328 source-linked original quote journals, 168 scenarios, zero censored portfolios. No broker orders. Console reports completed eight-period matrix and original 2020 three unresolved demands. Console provided here **begins partway through 2022**, so prior 2021 and V95 forensic console details must be cross-checked against original separate ZIPs for complete independent evidence.

## Original fixed common-policy results — do not cherry-pick other settings

USD; all trade-counts are original **hypothetical accepted** quote entries, not brokerage executions. 2025 is Jul–Dec only; 2026 is Jan–Apr only. Across historical cohorts the research model resets nominal cash to $25,000; adding nominal dollars across unequal periods is **NOT a linked annual return or compounding simulation**.

| Family/scope | 2018 | 2019 | 2021 | 2022 | 2023 | 2024 | 2025 H2 | 2026 Jan–Apr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Combined, one-slot | −333.10 | −1,035.16 | −1,283.72 | **−2,222.20** | **−2,048.16** | +378.26 | +461.48 | −833.16 |
| Opening impulse | −30.62 | −203.40 | −659.74 | **−2,350.46** | **−1,634.42** | −526.12 | −117.06 | −904.72 |
| Acceleration | +0.20 | −209.28 | −146.94 | −280.78 | −3.92 | −581.74 | +23.16 | −114.40 |
| Early reversal | +191.70 | −148.80 | +155.12 | −30.54 | −72.42 | −48.40 | +67.66 | −8.88 |
| Pullback/resume | −225.50 | −276.88 | 0.00* | +0.88 | −21.52 | +18.80 | −179.70 | +68.72 |
| Gap followthrough | −597.62 | −274.40 | +44.04 | +469.32 | +107.24 | +405.72 | −184.42 | −139.90 |
| Range compression | +45.06 | −400.16 | −521.96 | −10.70 | **−1,383.76** | +1,183.70 | +240.44 | −341.32 |

\* Pullback 2021 $0.00 was **zero modeled accepted trades**, not a profitable/flat successful trading system.

Across these eight non-contiguous, differently sized periods, the original combined nominal quote-PnL sum is −$6,915.76. Six-family alternatives do not qualify either: opening impulse loses in **all eight** periods; the compression release family is negative in **2019, 2021, 2022, 2023, and 2026** despite its favorable 2024; the early reversal $105.44 total nominal sum comes from small and inconsistent opportunities, positive only **three of eight** periods and very sparse modeled trades. No evidence-driven automatic promotion to `runner_35_150` or 1s lag after seeing outcomes.

Original source demand census by cohort: 2018 60, 2019 51, 2021 53, 2022 152, 2023 97, 2024 87, 2025 H2 50, 2026 Jan-Apr 49; **599** option-source demands for the eight complete cohorts, 2020's 112 original attempts excluded.

### 2023 individual evidence mechanism — source-linked not ex-ante signal

Under original fixed policy, single-capital combined account had **97** original qualified option opportunities, **53** hypothetical entries closed, **27** rejected original entries and **17** capacity conflicts (97 = 53+27+17), **23** hypothetical quote winners vs **30** losers. Exact net **−$2,048.16**. Aggregate winning reference PnL **+$1,842.18**, losing **−$3,890.34**, quote-reference profit factor **0.4735**. The two largest favorable quote outcomes were +$440.52 and +$218.84; excluding them makes 2023 modeled PnL **−$2,707.52**.

Joined all **53** cash-ledger exit fingerprints back to the immutable 2023 compressed V86 recheck entries. All 53 matched. Original retrospective exit-reason decomposition:

| Exit reason known only after trade | Exit count | 2023 two-percent-stressed quote PnL |
|---|---:|---:|
| STOP_LOSS | 24 | **−$3,835.62** |
| CAUSAL_TRAIL | 28 | **+$1,346.94** |
| PROFIT_TARGET | 1 | **+$440.52** |
| **Total** | **53** | **−$2,048.16** |

**Do not use the observed stop-loss exit reason to invent an ex-ante entry filter**. It is a post-trade outcome. For original fixed-limit marketability, **29 of 53** V86 original action-time quotes classified `original_action_limit_marketable=True` (stressed net −$834.44); **24/53** were quote-unmarketable (stressed net −$1,213.72). Marketability is not an actual fill; missing queue position, order acknowledgement, fill ratios, and assignment/exercise remain important.

2023 combined month cash PnL: Jan −325.48; Feb −625.24; Mar +267.04; Apr +99.68; May −156.20; Jun +24.96; Jul −397.44; Aug +77.56; Sep −123.84; Oct +371.70; Nov −657.54; Dec −603.36. **7 negative vs 5 positive months**, November+December combined −$1,260.90. The 2023 original `compression_release_0940` loss was **−$1,383.76** over 16 modeled entries (6 favorable/10 unfavorable), and `impulse_0935` lost **−$1,634.42** over 31 modeled entries (12 favorable/19 unfavorable). In 2022 original opening impulse lost **−$2,350.46** over 53 modeled entries (23 favorable/30 unfavorable). This is strong failure of the already-frozen original hypothesis group, not a reason to delete those months.

## Audit limits and subsequent gate

- The eight original V89/V90 cohort reporting chain was validated by V95 workstation based on the console summary. This turn directly reverified **only** the two uploaded ZIPs: full eight-period matrix and full 2023 V90 journals. Request the other original 2021/2022 V89+V90 ZIPs, original V95 2020 reconciliation ZIP, and preferably 2018/2019 V90 ZIPs for independently checking every linked original source and ledger before a full-source-batch independent integrity PASS.
- **Research strategy status:** no frozen V89 family or combined portfolio is sufficiently robust to warrant trading. Historical source-linked quote model results are not brokerage earnings or proof of executable historical fills. Do not optimize 24 execution variants on these eight inspected historical periods to rehabilitate losses.
- Stop using the currently rejected six-family combined fixed policy as a candidate for live deployment; preserve all signed failures, not just winners, and maintain original dates/price-source fingerprints.
- Next useful research: a **different, pre-registered market mechanism**, with causal entry rules, sufficient trade sample, rigorous microstructure and quote marketability, plus out-of-sample chronological testing. Preliminary exploration of **bounded-risk option credit spreads** (requires two-leg contemporaneous available original source and realistic multi-leg fill/exit/assignment) or separately defined volatility-regime/mean-reversion hypotheses may be worthwhile, but are **NOT validated** here. Investigate market regimes for explanatory diagnostics without turning after-the-fact exit labels into a cherry-picked trade screen.
- Historical 2020 full-year PnL is **unknown** until source reconciliation; its three unresolved queries cannot be zeroed or automatically retried. The protected 2026-05-12..2026-08-11 master holdout remains sealed. No broker orders were placed.

**Conclusion:** V95 supplied matrix and 2023 V90 independent integrity PASS; eight-period historical robustness FAIL for original V89 strategies; incomplete source set for independently rehashing every other period.
