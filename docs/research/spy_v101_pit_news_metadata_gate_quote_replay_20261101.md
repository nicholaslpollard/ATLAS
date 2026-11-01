# ATLAS V101 — Source-linked PIT-news metadata filters and new CALL replay

Registered 2026-11-01 on research branch based on V100 commit `42ffdede447c1cf2483b42ffa1d8f8938ec7a44b`. **Implementation not yet workstation-verified. No historical profitability from V101 is claimed.**

## Why V101

The fully completed V99 quote-based experiment generated 630 original compressed trial journals and 10,800 one-slot cash-account scenarios. Across 1,114 source-complete eight-period settings, zero earned positive hypothetical P&L in every period; V100's prior-period-only selection rules also failed on aggregate. The original V99 explicitly did not join historical news. Another entry threshold adjustment is unlikely to establish a new edge.

V101 applies three **predeclared**, historically as-of SPY headline-activity filters to each original eligible 0DTE CALL opportunity and then **re-simulates** the unchanged V90 original one-slot $25,000 cash account using original V84/V86 signed option quotes. It does not filter already-known V99 winners after looking at their results.

## Fixed news activity gates, not sentiment

- `NEWS_24H_AT_LEAST_1`: at least one SPY-tagged original article effective at decision time in preceding 24 hours.
- `NEWS_7D_AT_LEAST_3`: at least three SPY-tagged original articles effective at decision time in preceding seven days.
- `NEWS_24H_ZERO`: source-verified no SPY articles in preceding 24 hours, as a news-quiet control (unknown coverage is NOT zero news).

An article's conservatively observable effective time is `max(created_at,updated_at)` from the accepted original normalized source. No future-revised article is backdated, no sentiment signal is inferred, and no post-entry P&L is used to decide the gate. Provider first-delivery time has not been independently established; this remains a point-in-time metadata proxy rather than fully proven contemporaneous publication.

## Historical coverage and source requirements

Only the six news-covered research cohorts 2021, 2022, 2023, 2024, 2025 H2 and 2026 Jan–Apr are eligible. The news scanner verifies original accepted source-integrity evidence and reads exactly 65 monthly original Parquet partitions from **December 2020 through April 2026**. It does not open May–August 2026 master-holdout partitions, nor does it treat 2018–2020 as zero-news periods.

All 630 original V99 option quote journals and all 10,800 original account scenarios are re-audited by V100 code before V101 uses them. Three gates × 50 portfolios (49 standalone CALL entry variants plus six-family frozen-baseline combined portfolio) × 24 original execution/exit variants × six cohorts = **21,600 additional historically quote-modeled account ledgers**. Each original source linked V84/V86 pair is reused unchanged; the 24 settings comprise three frozen exit policies, two action-lag choices, and four resting-limit durations. Each gated capital account is simulated again after excluding news-rejected entries and retains all accepted decisions, no-entry reasons, capacity conflicts, realized stressed weekly/monthly cash P&L, unresolved expiry, and original SHA references.

Original May 2020 ambiguous source, Jan 2022 explicit NO_DATA, and unknown 2024 settlement remain censored as relevant. In particular, **any original missing source remains censored even if a news filter might have rejected that unknown candidate**, because the missing trade cannot safely be scored; no missing or unpriced position is assigned a fictitious zero return. This may conservatively lower the number of six-period fully comparable scenarios.

## Outputs, controls, next inference

Runner: `scripts/run_spy_v101_news_metadata_gate_quote_replay_20261101.ps1`.

Source: `scripts/run_spy_v101_news_metadata_gate_quote_replay.py`. Tests: `tests/test_spy_v101_news_metadata_gate_quote_replay.py`.

The runner compiles source+test modules, runs relevant V101/V100/V99/news/V90 regressions, then runs the original V99 signed evidence audit and the **offline** news-filtered quote replay. Every 1,200-case cohort/gate account scenario set is a signed compressed JSON evidence file; signed opportunity decision events and the six-period comparison preserve each new result's V99 parent hashes. Summary manifest records SHA256 for all output evidence. The script preserves summary evidence and full evidence ZIPs, including partial evidence on failure. **Zero provider calls, zero broker orders, no source cache modifications, no true brokerage fill claims.**

This is **exploratory** because the historical cohorts and original 49 entry settings have already been examined. Do not claim this is independent OOS performance, a profitable strategy, or a restored protected holdout. After the run evaluate all three gate populations, by-period cash completeness, turnover, months/weeks, trade concentration and whether any advantage is stable rather than a few outsized winners. Separately advance V51 opening-range single-leg implementation when first breakout ticks and original 0DTE quote source coverage qualify; do not confuse the existing 0DTE ORB preview with trade-grade fills.

## V101 first workstation run and ledger correction — November 1, 2026

Pinned original branch head `eca385bf3dea5ff6da5c9957527ca82c6dc1ce00`: PowerShell source/test compilation passed; **54 regression tests passed** in 14.84s. The full 630 source journal/10,800 original account audit proceeded without source-integrity error. All three news-gated 1,200-ledger configurations completed for each of 2021, 2022 and 2023 (nine of eighteen cohorts-by-filter batches). The 2022 batches reported 1,128 cash-complete scenarios each, with the 72 original per-batch source-censored scenarios retained. The first 2024 gated ledger triggered `V101_GATED_CASH_ARITHMETIC_INVALID`. The original V101 partial evidence ZIP was preserved at `data/research/spy_v101_original_news_gate_quote_replay_20261101_164641_full_source_linked_evidence.zip`. No provider requests or broker orders; no V101 completed profitability comparison exists from that failed run.

**Root-cause code review:** V101 compared all accounts' terminal stressed cash delta to **closed-trade** stressed quote P&L, even when V90 correctly retained a non-flat, unpriced option position. V90 subtracts that open entry premium from cash while keeping unknown exercise/exit cash and terminal equity null. Therefore cash delta includes the open premium debit but closed P&L correctly does not. Earlier V99 full-ledger verification compared these quantities **only for cash-complete flat** accounts. V101 added an unconditional stronger check that was economically invalid for unresolved accounts. The specific 2024 trial that first triggered this has not been independently recovered from the console alone; this code defect is sufficient to explain the exception, not proof of the precise offending contract.

**Repair:** `audit_v90_cash()` still requires closed-trade P&L to equal both weekly and monthly sums in **all** account states. It independently totals every signed `ENTRY_ASK_REFERENCE_ONLY.debit_usd` and `MODELED_EXIT_QUOTE_CREDIT.two_pct_haircut_credit_usd` event and requires all cash movements to reconcile with ending minus starting cash. A **flat** ledger additionally requires closing cash change to equal closed P&L and final cash-equity to equal the known ending stressed cash. An **unresolved** ledger must have exactly one original unknown-expiry event, the original open entry premium must account for the entire difference between closed P&L and net cash, and terminal equity must stay null. Signed V101 filtered scenario evidence now also separately records `unresolved_open_entry_premium_usd` without assigning it an invented return.

New synthetic regressions assert complete-flat reconciliation, valid unresolved position with premium debit, failure for tampered event amounts/weekly totals/false terminal equity, and that the V101 wrapper **censors** unresolved quote P&L. Focused isolated source/tests were compiled and **16 local synthetic regression cases passed**; the complete Windows repository regression suite and corrected historical run remain pending workstation verification.

**No trading rule, entry candidate, option quote source, news cutoff, strategy threshold, or V84/V86/V90 economics changed.** A new timestamped V101 stage must rerun from the original signed V99 source evidence. Do not treat the original partial ZIP as a finished comparable campaign, do not retry original ambiguous paid sources, and do not open the protected 2026 May–August holdout.
