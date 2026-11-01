# V89–V91 completed six-new-family three-cohort original-source audit (2026-11-01)

## Result and scope

**Status:** user workstation V89–V91 completed; uploaded **seven evidence ZIPs** and original console log. This independent analysis reviewed the entire uploaded corpus, not just V91's summary. **No strategy qualifies for live trading.** Eight positive 3-cohort variants belong to **one early-reversal entry hypothesis** and reuse the same handful of trades; the frozen common balanced/3-second/10-second policy shows losses or mixed signs for every individual family in at least one cohort. The combined six-family portfolio is essentially breakeven across noncontemporaneous cohorts and negative in 2026. The protected 2026-05-12..08-11 master holdout remains sealed according to signed campaign date boundaries.

**Registered sources:** `docs/research/spy_v89_v91_parallel_exploratory_strategy_campaign_20261101.md`; immutable exploratory entry registry `packages/simulation/spy_v89_six_family_causal_registry.py`. User checked out and executed commit `fc3b2685db9805d177338f88fe9004b01d15ddfe` after local fixture fix. V89 exact stock-derived source decisions and contract selection are not equivalent to a proven executable options trade. V84/V86 quote-based exits are not broker fills.

### Seven uploaded ZIPs audited

- `spy_v89_six_new_families_2024_full_20261101_102938.zip`
- `spy_v90_six_new_families_2024_full_20261101_102938.zip`
- `spy_v89_six_new_families_2025_h2_20261101_102938.zip`
- `spy_v90_six_new_families_2025_h2_20261101_102938.zip`
- `spy_v89_six_new_families_2026_janapr_20261101_102938.zip`
- `spy_v90_six_new_families_2026_janapr_20261101_102938.zip`
- `spy_v91_six_new_family_three_cohort_matrix_20261101_102938.zip`

ZIP CRC passed for all seven. **All 23 signed JSON report roots** valid (V89 four per cohort; V90 three per cohort; V91 two JSON documents = 23). Verified canonical sorted compact JSON/newline SHA-256 fingerprints, all source report parent links, **465** source SHA-chain events (216+128+121), their terminal event fingerprints/sequence/parent links, **186/186** original signed causal option source demands and **186/186** provider/archive receipts with request identities, **4,464/4,464** complete gzip-byte SHA-256 journals (2,088/1,200/1,176), all nested V84 + V86 trial fingerprints and parent-trial/session/strategy SHA links, **504/504** embedded signed V90 portfolio ledgers, V91's 504 signed matrix rows and exact embedded ledger fingerprints, and CSV byte SHA-256. **Zero audit mismatches**. Independently recomputed every of the 504 portfolio ledgers' closed event P&L, original entry count, monthly sums, and flat terminal cash against its signed recorded totals: zero mismatches.

Note: the original 1-second ThetaData quote *bytes* are stored in original workstation V38 external cache and were checked by V90's local SHA-source audit, but **are not included in the uploaded ZIP files**, so independent raw quote-source byte rehash from these ZIPs alone is not possible. The audit establishes the internally intact **signed derived evidence**, not actual fills or raw source tape reconstruction. User log reported regression passed before acquisition and no broker orders.

| Cohort | Original sessions | All 6 causal decisions | New option demands | Original FETCHED_AND_ARCHIVED | V38 CACHE_HIT | V90 journal trials | Cash ledgers / unresolved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 full | 252 | 1,512 | 87 | 42 | 45 | 2,088 | 168 / 5 |
| 2025 H2 | 128 | 768 | 50 | 28 | 22 | 1,200 | 168 / 0 |
| 2026 Jan–Apr | 82 | 492 | 49 | 23 | 26 | 1,176 | 168 / 0 |
| **Total** | **462** | **2,772** | **186** | **93** | **93** | **4,464** | **504 / 5** |

The five V90 2024 terminal cash outcomes with unknown exercise/expiry are **censored**, not assumed to be flat; V91 therefore classifies **163/168** configurations as having complete three-cohort cash ledgers. There are 7 capital scopes × 24 correlated execution configurations × 3 cohorts = 504 report rows.

## Original fixed-settings comparator (avoid retrospective policy selection)

The common comparison policy previously used for V83–V88 is `balanced_35_100`, action lag **3 seconds**, original fixed limit resting **10 seconds**, adverse exit BID haircut **2%**, plus existing transaction fees and one-position $25k nominal account. Same rule applied to all three cohorts.

| Individual/combined six-family scope | 2024 full-year quote P&L | 2025 H2 quote P&L | 2026 Jan–Apr quote P&L |
| --- | ---: | ---: | ---: |
| `impulse_0935` | **−$526.12** | −$117.06 | **−$904.72** |
| `acceleration_0940` | −$581.74 | +$23.16 | −$114.40 |
| `early_reversal_0940` | −$48.40 | +$67.66 | −$8.88 |
| `pullback_resume_0940` | +$18.80 | −$179.70 | +$68.72 |
| `gap_followthrough_0940` | +$405.72 | −$184.42 | −$139.90 |
| `compression_release_0940` | **+$1,183.70** | +$240.44 | −$341.32 |
| **All six one-slot cash** | +$378.26 | +$461.48 | **−$833.16** |

All figures are nominal quote-shadow profits/losses for different-length historical windows, NOT equal annual return periods and NOT real execution. Because of simultaneous candidates/one-position constraint, combined-account gains are not arithmetic sums of solo strategies.

**Combined +$6.58 net across three distinct periods** (+378.26 +461.48 −833.16) before additional real fill frictions. 2024 combined modeled accepted quote entries 49 (29 quote-positive/20 quote-negative), 33 rejected before entry, five concurrent position conflicts, peak-to-valley completed-trade cash drawdown $442.72; 2025 H2 26 accepted (16 positive/10 negative), 16 rejected, eight conflicts, drawdown $520.78; 2026 Jan–Apr 26 accepted (13/13), 14 rejected, nine conflicts, drawdown $1,361.88. 2026 March combined month was **−$973.64**. Five V90 configurations censored are **not** this common comparator.

### Why eight configurations all positive are NOT eight discoveries

Exactly **8 of 163 complete** configurations show strictly positive nominal quote P&L in all three cohorts, and **all eight** are `early_reversal_0940 + runner_35_150`: lag 1s/3s × original limit rest 0/3/10/30s. These eight are strongly correlated alternatives using the **same original 4/2/2 signal opportunities**, not independent trading experiments.

One illustrative variant: lag 1s, 10s resting limit:

| Cohort | Quote-modeled accepted entries | Positive/negative exits | 2%-stressed nominal P&L | P&L with two largest winning quotes removed |
| --- | ---: | --- | ---: | ---: |
| 2024 | 3 | 3 / 0 | **+$76.94** | +$13.44 |
| 2025 H2 | 2 | 2 / 0 | **+$84.86** | $0.00 |
| 2026 Jan–Apr | 2 | 2 / 0 | **+$53.86** | $0.00 |
| **Total** | **7** | **7 / 0** | **+$215.66** | **+$13.44** |

These are **seven source-linked hypothetical wins** in 462 historical market sessions, not enough independent observations to establish a profit edge. The 3-second/10-second runner variant has 4/2/1 accepted entries with +$37.84 / +$108.82 / +$42.08; the 2024 variant becomes −$71.18 if its two best trades are removed. **NO PROMOTION**, no selection of runner post hoc as the new primary.

`compression_release_0940` with original common balanced policy is a more frequently triggered **diagnostic lead**, but only 14, 8 and 6 accepted quote entries across cohorts, returns +1,183.70/+240.44/**−341.32**. The **2025 H2 net falls to −$69.80 after excluding its two largest positive quotes**, and 2026 declines; it does not qualify as a regime-invariant edge. The impulse family has 20/16/13 accepted hypothetical entries and negative P&L in **all three** periods at the common settings.

## Retrospective execution sensitivity, not new selected policy

Independently recomputed original **2% signed portfolio credit at the cent** from per-exit actual reference BID credit, then applied additional hypothetical exit-BID haircuts by adjusting only each original ledger's exit cash credit. Entry events, hours, order-action timing, option contract, quantity, original exit decision and marketability classification left unchanged; no future trade filtering. Table below is **post hoc execution sensitivity**, not an optimized strategy:

| All six, shared cash account | 2024 | 2025 H2 | 2026 Jan–Apr |
| --- | ---: | ---: | ---: |
| 2% original | +$378.26 | +$461.48 | −$833.16 |
| 4% | +$2.02 | +$242.76 | −$1,037.42 |
| 6% | −$374.22 | +$24.04 | −$1,241.68 |
| 8% | −$750.46 | −$194.68 | −$1,445.94 |
| 10% | −$1,126.70 | −$413.40 | −$1,650.20 |

For the compression-release common variant at 2/4/6/8/10% haircuts: 2024 +1183.70/+1052.20/+920.70/+789.20/+657.70; 2025 H2 +240.44/+164.58/+88.72/+12.86/−63.00; 2026 Jan–Apr −341.32/−387.84/−434.36/−480.88/−527.40. The negative 2026 sign cannot be repaired by a more aggressive adverse haircut assumption.

## Evidence-backed promotion / next research gate

1. **FAIL common combined portfolio:** 2026 loss more than offset earlier reference gains, and exit price stress erodes even earlier positive cohorts. Do not promote live or claim forward profits.
2. **NO proven individual family:** early reversal's runner policy is 7 modeled winning quotes across 21 months of covered history and only an exploratory small-sample hypothesis; compression release has a negative last cohort; all six families are unproven.
3. **Do not silently pick one of eight configurations:** multiple-testing/variant correlation, hindsight and historically inspected three cohorts destroy untouched validation status.
4. Preserve original immutable V89/V90/V91 ZIPs and original V38 cache; do not rewrite reports to label them favorable. Every rejected/no-signal candidate and 5 censored portfolios must remain counted.
5. **Most useful next work is more independent observations**, preferably new untouched 2023-or-earlier regime if original stock months exist, using an explicit new pre-scored research plan. Do not assume local 2023 source coverage exists; inventory it offline before any ThetaData GET. Parallelize **offline original-source auditing, clock causality, quote-size/bid marketability risk and retrospective regime-feature diagnostics**, but avoid multiple concurrent writes to the same original V38 SQLite cache. Avoid continuing to scan 24 post-hoc exit settings for a winner.
6. Before considering any live execution, require an independently time-separated forward trial, stronger sample size, realistic option assignment/expiry/partial fill and quote-size constraints, and verified paper-order versus source BID outcomes.
7. Protected master holdout **2026-05-12..2026-08-11 remains untouched**; do not open it to rescue these exploratory outcomes.

**Research conclusion: V89–V91 evidence integrity PASS; statistically and operationally robust strategy profitability NOT demonstrated.**
