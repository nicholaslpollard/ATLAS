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
