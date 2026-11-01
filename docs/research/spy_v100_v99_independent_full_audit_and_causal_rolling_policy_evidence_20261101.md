# V99 independent full original-source audit and V100 causal rolling policy selection — 2026-11-01

## Original V99 workstation campaign COMPLETE

Original workstation user output pinned GitHub V99 `bd2f11b39aebd5d5be1c406ae0fe4f57516c68ab`: **63 regressions PASS**, all nine source-scoped chronological 2018–2026 historical cohorts simulated with exactly **630 full original source-family option-trial journals**, **10,800** one-slot capital scenarios (1,200 per cohort), **576 distinct original SHA-backed CALL quote query scopes** referenced by the replay, and full 1,200-scenario eight-source-complete-period comparison. No new ThetaData calls, broker orders or PIT news features. Original May 2020 ambiguous CALL source and Jan 2022 explicit no-data CALL source remained missing, not zero PnL.

User uploaded TWO artifacts, `spy_v99_49_call_quote_cash_campaign_20261101_153603_summary_evidence.zip` (12 original signed JSON root artifacts: nine cohorts, summary, full matrix, original trial manifest) and `spy_v99_49_call_quote_cash_campaign_20261101_153603.zip` (entire V99 stage, 12 signed JSON roots + **all 630 original gzip trial-journal payloads**). Independent reviewer verified both ZIP CRCs, every signed summary member exactly equals its full-stage ZIP copy, summary SHA **`fdd191f035c188dc5125df5c83802729f9597ea5273b39410e2f268bbfe4fb75`**, original source-journal manifest SHA **`adc181d09d3ff0f42b319261bee26f7868f30b3d29648d7de09c04aa0e850cba`**, and eight-period comparison SHA **`dd6b52581c4a66472f0e4b59a6720ecb7207741f410115efeb8721ddd47729b7`** with every original SHA parent link.

The independent reviewer then inspected **all 630 actual compressed quote-journal bytes, gzip SHA-256 and raw decompressed length, each SHA-signed original six embedded V84 trials (3,780), all four nested V86 exit rechecks for each trial (15,120), source query+SHA, derived CALL decision/demand SHA, option right, no provider/broker calls**, and all **10,800 SHA-signed original V99 scenario and nested V90 account ledgers**, checking every complete account's cash start/end difference equals stressed closed PnL equals sum of weekly and monthly stressed quote amounts, and comparing every crossperiod matrix row to its nine original source-ledger parents. **All checks PASS.** This is a verified audit of derived source-linked replay journals. The original full raw V38 ThetaData 1-second exchange feed bytes remain on workstation and were **not independently byte-rehashed from these ZIPs**; journal source SHA and V99 original cache were checked at creation.

### Historical source completeness

| Cohort | Original signed capital scenarios | Qualified+flat | Incomplete |
|---|---:|---:|---:|
| 2018 | 1,200 | 1,200 | 0 |
| 2019 | 1,200 | 1,200 | 0 |
| 2020, source-partial | 1,200 | 1,104 | 96 |
| 2021 | 1,200 | 1,200 | 0 |
| 2022 | 1,200 | 1,128 | 72 |
| 2023 | 1,200 | 1,200 | 0 |
| 2024 | 1,200 | 1,186 | 14 |
| 2025 H2 | 1,200 | 1,200 | 0 |
| 2026 Jan–Apr | 1,200 | 1,200 | 0 |

2020 excluded from all eight-period robustness gates even where individual 2020 scenario cash resolved. The 2024 missing/uncertain cash is not falsely flattened. Of 1,200 fixed scenario identities, **1,114** have eight eligible development cohorts completely source-qualified and terminal-cash-resolved; **zero** were positive in all eight; **90** had a positive nominal **sum** of the eight separate initial-$25,000 account period PnLs, not an annual compounded return. Among all fully comparable settings, positive-period counts: 0→143, 1→229, 2→258, 3→293, 4→100, 5→42, 6→49, 7→0, 8→0.

The strongest retrospective nominal eight-period quote PnL was V97B `gap_followthrough_0940-04`, V84 `control_50_100` (−50% stop/+100% target), 1-second modeled action lag, 0-second original sell-limit rest: **+$736.20**, **five profitable, three losing periods**, 51 closed hypothetical positions and 17 rejected entries in those eight periods. This rule is not a live-proven winner and was NOT selected before the evaluation data. Its historical 2018=−$481.84, 2019=+$127.78, 2021=+$217.60, 2022=+$337.04, 2023=−$43.94, 2024=+$527.62, 2025H2=+$82.68, 2026 Jan-Apr=−$30.74. The fixed combined six-family CALL account's best eight-period nominal quote PnL is **−$2,641.46** with only two profitable periods. Original V84/V86 quote references are not guaranteed exchange fills or demonstrable alpha.

## V100 actual prior-only chronological selection

The independent reviewer ran three **predeclared selection rules against the uploaded, signed 1,200-case V99 matrix**, never accessing a test period while selecting its policy: initial prior history 2018+2019+2021, next period 2022; then append each successive period, testing 2023, 2024, 2025 H2, and 2026 Jan-Apr. Exclude original 2020 incomplete cohort entirely. Eligibility: original prior source and position cash fully resolved for every prior period, minimum **10 previously modeled closed positions** across training years, and no selection based on future PnL. Rules rank by prior total stressed PnL, prior count of profitable periods (tie-break by PnL), or best worst prior period. Deterministic tie-break via registered source scenario ID; no future changes of hypothesis/fees.

| Prior-only rule | 2022 | 2023 | 2024 | 2025 H2 | 2026 Jan–Apr | Five-period sum |
|---|---:|---:|---:|---:|---:|---:|
| Highest prior nominal PnL | −670.80 | −129.36 | −4.20 | +82.68 | −30.74 | **−752.42** |
| Most positive prior periods | −670.80 | −454.96 | −4.20 | +82.68 | −30.74 | **−1,078.02** |
| Best minimum prior period PnL | −257.10 | −141.44 | 0.00 | +63.92 | +13.64 | **−320.98** |

All five next-period quote results for each selector were cash-resolved; none were profitable on the 5-period observed total. The local independently reviewed JSON source-of-evidence is `atlas_v100_rolling_preview_from_uploaded_v99_20261101.json` (SHA `ae79482dd0f5528bbf8fc17cd369c47341172840743d5a06bdcd8ff76d7b67b6`), available in the ChatGPT conversation files, not a GitHub stored future result. **These earlier historical periods have been researched before and are NOT a fresh genuinely untouched holdout or paper trading**. Simple prior-only rank selection did not rescue the six-hypothesis CALL grid. The first test 2022 was especially negative under profit maximizing selectors.

## Committed reproducible V100 code and next research priorities

`scripts/run_spy_v100_v99_independent_wfo_audit.py`: original local V99 SHA audit on full 630 compressed journal files, 3,780 V84, 15,120 V86, 10,800 nested account ledgers and complete original eight-period matrix; then exactly three prior-only rolling selectors with a guaranteed closed-period boundary, min three prior periods and min 10 prior trades. Produces SHA-signed `prior_only_rolling_selection.json` and `summary.json`. No original cache writes, no provider calls, no broker orders, no news sources, no original 2026 protected master holdout. Paired `tests/test_spy_v100_v99_independent_wfo_audit.py` rejects tampered SHA, prior-unknown source, insufficient sample and future PnL leakage, and when the original stage is present performs an entire 630-journal+10,800-ledger integration pass. Windows runner `scripts/run_spy_v100_original_source_and_rolling_audit_20261101.ps1` syntax-checks source and tests then runs pytest, then independent audit and signed ZIP.

**The V100 GitHub code is committed but has NOT YET been executed on the user's Windows workstation.** Its original audit method was separately executed independently against the uploaded full original ZIP and produced the results above; the original physical on-workstation run provides reproducibility.

**Research decision:** Do **not** claim that the best retrospectively tuned gap-followthrough CALL rule is durable or promote it to live trading; V99 data contradict robust eight-period profitability, and V100 naive causal selection did not succeed. Profitability priority now favors (a) implementing truly different executable CALL-only entry families rather than tweaking 49 correlated thresholds, (b) verifying 2021+ as-of historical Alpaca news metadata and testing independently motivated regime/news filters, (c) shadow paper execution and real spread/fill feasibility, (d) preserving protected later holdout, and (e) avoiding redundant ThetaData GETs when archived source already qualifies. Optimizing further only within already negative V89 thresholds risks multi-hypothesis overfit.

ATLAS is still an original-source-linked **hypothetical quote** simulator, not a verified brokerage historical fill emulator. No source PnL can be represented as actual investor account returns or a proven profitable options strategy.
