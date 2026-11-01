# V88 completed full-year 2024 signed quote-reference audit and cross-cohort robustness decision

**Audit date:** 2026-11-01. **Result:** V88 simulation complete, original 2024 historical source campaign intact, preregistered strategy **negative**. This is a historical regime challenge, **not** untouched forward validation, not a backtest trading account, and not the 2026 master holdout.

## Archived immutable evidence

User ran original V88 at commit `611a480f4406539d3bc4c85eba278ea333e42b8f`. Local regression/compile passed: **33 tests**, 16.25 seconds. V88 output `data/research/spy_v88_regime_2024_20261101_092829.zip` supplied in chat for independent signed audit.

**Original campaign:** source ZIP `spy_v83_source_first_2024_full_20261101_081710.zip` independently checked: 252 original XNYS sessions, 756 original decision cases, 549 NO_SIGNAL, 207 original causal exact-option-source requests, all 207 `FETCHED_AND_ARCHIVED`, 0 broker orders. Full four source report SHA roots are pinned in original V88 runner: entry `f24ecbcc9c7a7c3f22200048b33a8631daeb2121b6ec0b3bc9283b997818f32e`, plan `6d81364b40587d69361241fb1c6b955a0ed19e578e1dd88c6c23e88909dfaf41`, receipts `fdf9ebfc10583febb53b9199fd7b257a2e5615140d80b26fa66e473511f04db3`, summary `c08008c476cdd90eb8fee33749af2c3b64780e4ce4c1098f3bd317caa967d1d9`.

**Completed V88 ZIP independently verified:**
- ZIP CRC test passed, 6,221 archive members, 11/11 top-level report SHA-256 document signatures valid. All top-level V88 → V84/V85/V86 report fingerprints matched.
- **1,242/1,242** V84 compressed original 1s source quote trial journals: stored gzip-byte size and SHA-256, extracted journal document SHA-256, original trial fingerprint and original session/family/policy/lag metadata all matched. 1,014 CLOSED_QUOTE_REFERENCE variants and 228 NO_ENTRY variants (counts across 3 policies × 2 action delays, not independent trades).
- **4,968/4,968** V86 independently signed recheck journals: gzip bytes/SHA-256 and embedded fingerprint plus original trial session/policy/lag binding all matched. 48/48 V85 embedded signed quote-only cash ledgers and 92/92 complete V86 embedded signed quote-only cash ledgers verified. The remaining **four** V86 alternate execution scenarios were correctly marked unresolved/censored with no complete cash ledger; **the preregistered primary had zero unresolved positions**.
- All 96 V86 portfolio scenario comparisons were present; 92 scenarios with complete original cash ledgers had matching source-linked ledger fingerprints. No provider GETs and no broker orders during replay; original exact source **bytes** were verified by local V84/V86 cache routines, but are not included in the ZIPs for independent byte-level source rehashing.
- V88 signed top-level fingerprint: `119bc58dcf3e3af528c7a97fb81f0e46c9f45cde1a13aa7f26288e2102df2b05`. Parent V84 `8787bae7af03ab5e653e9ff18666a031aed6ee107378fc85895090cd3bf22ee6`, V85 `f2dce884df7a9563b106158806fb1123888d2c89f722accaa26d99e05f722b4a`, V86 `7a303932d55d2e668cb761ebff6d720d271a482c92b17ef902c8531c0299e24d`.

## Preregistered full-year 2024 primary: FROZEN / FAILED robustness

**Exactly frozen before observing this 2024 quote P&L**: `failed_breakout_fade_0940`, `balanced_35_100` (−35% stop/+100% target, 20% trail arm/15% trail, 120-minute maximum), **3-second** action delay, original fixed sell-limit **10-second rest**, **2% adverse exit BID haircut**, unchanged same-day SPY 0DTE strike, 1–4 contracts, <=$500 debit, $0.65 per-contract per-side commissions, nominal starting cash $25,000, one open position. Original observations and broker execution remain distinct.

- 90 causal entry signal opportunities, 15 original no-entry rejections, **75** accepted *hypothetical* ASK references / 75 complete BID exit references, 0 portfolio capacity conflicts, 0 unresolved primary outcomes, **zero actual historical fills**.
- **2%-haircut stressed quote-reference P&L −$1,149.96**, or **−4.59984%** of nominal $25,000 initial cash in a full year, with modeled terminal flat cash reference $23,850.04.
- Unstressed BID quote-reference P&L **−$542.80**. The 2% stress reduced hypothetical P&L by **$607.16**, but **unprofitable even without any adverse exit BID haircut**.
- Positive exits 39, negative exits 36, observed quote win rate **52.0%**. Positive gross P&L +$3,073.68; negative gross P&L −$4,223.64; profit factor **0.728**; mean winner **+$78.81**, mean loser **−$117.32**. With the recorded average payoff sizes, break-even win rate would be ~**59.8%**. This is a *win/loss payoff asymmetry* failure, not merely low hit rate.
- **6 positive months, 6 negative months**, loss dominated by **May −$604.98** and **August −$623.68** (combined −$1,228.66). Completed-position cash-curve max flat-to-flat drawdown $1,413.70 in source-ledger metric (not full mark-to-market risk).
- Original limit quote-marketability at action: 44 accepted exits; observed fixed-limit later marketability within 10s: 16; **15** modeled cancel/repriced-BID exit quote references. These are not verified historical order fills.

### Full year 2024 monthly original stressed P&L

| Month | Modeled exits | Winning | Losing | 2%-stressed quote P&L |
| --- | ---: | ---: | ---: | ---: |
| Jan | 7 | 4 | 3 | +$154.20 |
| Feb | 7 | 4 | 3 | +$5.30 |
| Mar | 9 | 5 | 4 | +$90.00 |
| Apr | 8 | 4 | 4 | −$310.88 |
| May | 9 | 3 | 6 | −$604.98 |
| Jun | 2 | 2 | 0 | +$37.46 |
| Jul | 5 | 3 | 2 | −$8.30 |
| Aug | 8 | 3 | 5 | −$623.68 |
| Sep | 5 | 4 | 1 | −$53.50 |
| Oct | 3 | 3 | 0 | +$245.24 |
| Nov | 3 | 1 | 2 | −$140.08 |
| Dec | 9 | 3 | 6 | +$59.26 |
| **2024 total** | **75** | **39** | **36** | **−$1,149.96** |

Winning/loss counts and USD sum independently reconstructed from 75 signed V86 primary cash-ledger exit events. Largest positive trade references: Mar 14 +$428.96; Jan 11 +$364.92. Top two winners sum +$793.88, meaning excluding them worsens already-negative P&L to **−$1,943.84**; removing winners is **diagnostic only** and not an entry/exit rule. Extreme losses around −$170–$188 occur repeatedly, while winners average smaller positive amounts.

## All three original entry families under SAME frozen balanced/3s/10s/2% conditions

| Scope | 2024 full year | 2025 H2 development | 2026 Jan–Apr later validation |
| --- | ---: | ---: | ---: |
| Failed-breakout fade **PRIMARY** | **−$1,149.96** (75 quotes/90 signals) | +$971.68 (39 quotes/51 signals) | +$883.70 (17 quotes/30 signals) |
| Opening-range continuation | **−$1,047.84** (70/94) | −$63.74 | −$674.10 |
| Gap fade | **−$543.46** (12/23) | −$141.40 | −$478.96 |
| Three-family one-slot combined | **−$2,805.64** (153 accepted/207 signals, 4 capacity blocks) | +$778.14 | −$325.82 |

The combined capital account is NOT the arithmetic sum of independently simulated families because signals conflict and only one position may be held concurrently. All three period results use originally frozen historical quote execution rules, NOT actual trades. 2024 is earlier historical regime testing, not an untouched future holdout; earlier research may have inspected stock data within it.

**Additional multiple-variant diagnostic, without reselecting a winner:** independently compared all **96** existing V86 scope × policy × latency × original rest configurations across all three signed 2024/2025/2026 reports. **92** configurations had complete modeled ledgers in all three periods; **NONE** was positive in all three periods. For the failed-breakout scope specifically, **0/24** configurations were positive in 2024, **24/24** positive in 2025 H2, **24/24** positive in 2026 Jan–Apr. These tests are **not independent trials of 24 strategies**, share the same source dates/candidate entries, and cannot be used to make a multiple-testing-corrected discovery claim. They show that adjusting the previously considered exit limit, delay or policy is not a credible cure for the 2024 robustness gap.

## Decision and next useful work

**FAIL: historical regime robustness** for all three original families and the combined account. Earlier favorable 2025/2026 quote outputs **remain valid as source-linked observations** but do not establish portable profit. Do **NOT** promote `failed_breakout_fade_0940`, the other two original families, or the all-family mixed strategy to live trading or label them profitable. Replacing 3-second action delay with the best backtested delay, excluding May/Aug 2024 after seeing losses, treating hypothetical BID as guaranteed fills, or cherry-picking a policy is NOT valid forward validation.

ATLAS next should stop investing further paid source acquisition into *this exact three-family unchanged system* until a genuinely new ex-ante hypothesis exists. Reuse already archived sources for **diagnostic** research: identify underlying stock/option market differences, signed rejection causes, and exit-order price sensitivity without changing prior reported outcomes. Develop a substantively distinct strategy in a separately labeled **development** cohort, predefine execution and risk assumptions, then reserve a genuinely new period for prospective validation. Protected master holdout **2026-05-12 through 2026-08-11 remains sealed**; do not open for an already failed candidate.
