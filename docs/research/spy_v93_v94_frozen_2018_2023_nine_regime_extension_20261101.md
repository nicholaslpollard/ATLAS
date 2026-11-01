# V93–V94 registered six-year SPY historical options regime extension

**Registered 2026-11-01 BEFORE opening any 2018–2023 V89/V90 source-linked option result.**

## Original verified trigger and immutable source ancestry

User completed V92 offline, `spy_v92_pre2024_original_stock_inventory_20261101_105004.zip`, 2 passed and 1 Windows symlink test skipped (no symlink privileges), 72/72 local SPY monthly 1-minute canonical+raw pairs SHA-verified from January 2018 to December 2023, **no options provider or broker calls**. Independent ZIP integrity CRC passed and both signed compact-JSON SHA-256 roots match exactly:
- `original_month_inventory.json`: `e19d03c45847e48b536d6eab16331aa752ae296b525484693cc210e63528f0e9`
- `summary.json`: `96d819a0b31d6c1ee436eeda7644871e9e425a6513a719e18b05084218f180c4`
- Signed summary's `inventory_sha` matches signed inventory; all 72 monthly YYYY-MM keys unique, 72 `ORIGINAL_FULL_SHA_VERIFIED`, zero unavailable/invalid, all bounded 2018–2023. Source names, monthly original SHA values are recorded inside V92, not recopied to this document.

V93 **requires** those exact original root fingerprints, 72 complete months and full local rehash of both canonical and raw stock file bytes across all 72 original monthly SPY source units, before any paid ThetaData option data GET. Every month must match V92 original canonical/raw SHA and exact unit ID. If anything differs, **FAIL before provider access**. A monthly SHA pass is not proof all session minute bars exist: V89 still performs original per-session semantic validations, logging no-signal, prior-source-unqualified and other failure dispositions.

## Six complete annual cohorts, original registered hypotheses unchanged

Six *separate* annual original XNYS calendars, never combined in data selection or peeking across folds:
- 2018-01-01 through 2018-12-31 (full calendar year)
- 2019-01-01 through 2019-12-31
- 2020-01-01 through 2020-12-31
- 2021-01-01 through 2021-12-31
- 2022-01-01 through 2022-12-31
- 2023-01-01 through 2023-12-31

Every session is evaluated for **all six original V89 registered causal price hypotheses** at their unchanged 09:35:01/09:40:01 clocks: `impulse_0935`, `acceleration_0940`, `early_reversal_0940`, `pullback_resume_0940`, `gap_followthrough_0940`, `compression_release_0940`. Feature thresholds, option strike whole-dollar rounding, original entry ASK/1% adverse drift rejection, one-position nominal $25k account, <=4 contracts, <=$500 debit, same V84 3 stop/target policies, V86 1s/3s action delay and 0/3/10/30s resting original sell limit, $0.65/contract/side and 2% adverse exit BID haircut all stay **exactly unchanged**. Prior session close must come from independently verified original earlier bars, not today's future values; first January session may need prior December even if previous year is outside the P&L cohort. If inaccessible, V89 must preserve the gap-family no-source rejection without silently fabricating a prior close.

The exploratory comparison policy, registered before any new-period outcomes, remains **`balanced_35_100` / lag 3s / original rest 10s / 2% exit BID haircut**. V94 may compare all 24 correlated execution settings, but no post-observation winner selection is authorized. Do not derive new exception dates from outcomes. Earlier 2024–2026 batches already examined and are **NOT** independent validation of these hypotheses. Extra 2018–2023 periods are also retrospective research and may have appeared in ATLAS's historical development; claim historical regime coverage, not untouched forward validation.

## Execution and complete preserved evidence

1. Run local regression first (new V93/V94 plus existing V89/V90/V91 and V84–V86). Fail before any original options source if tests fail.
2. V93 freeze exact original V92 roots, reverify 72 monthly canonical/raw stocks; sign `preflight.json` in an immutable new directory. Zero providers or brokerage.
3. For each full year 2018..2023, **one original V89 stock-source scan for all six hypotheses**, log every no-signal and rejection. Cache-first V39→V38 provider GETs are **serialized**, no concurrent SQLite writes; original 1s exact option source receipts, SHA-chained fsynced append-only source events and immutable `entry_screen.json`/`exact_option_source_plan.json`/`source_receipts.json`/`summary.json`. New GETs allowed for fully-qualified exact source query misses; do not retry uncertain already-dispatched originals.
4. Only if year original source statuses are `ALL_REQUESTED_SOURCES_PRESENT`, run V90 source-cache-only offline original option replay: **24** original signed journals per source, gzip SHA for every journal, **168** complete-or-explicitly-censored signed quote-only cash portfolios per annual cohort. No option or broker calls in this step. Preserve all candidate traces, original exits, rejections, shared-cash capacity conflicts, unresolved exercise/expiry, monthly/weekly P&L, top-two-winner concentration, and one-slot chronological action time. Save immutable fresh output directories and ZIP evidence after every year, including partial evidence if stopped.
5. V94 ingest six original annual V89/V90 directories plus the already-completed **2024-full, 2025-H2, 2026-Jan–Apr** V89/V90 sets. Verify every V89 source and V90 outcome SHA, all 168 original ledgers per cohort, exact dates and registry, and **72 2018–2023 monthly original source-unit SHAs matching V93**. The original V89 prior December source can be recorded as an additional causal feature month but never selected as in-period trade outcomes. Produce **168 execution-capital configurations × 9 periods = 1,512 signed JSON comparison rows**, immutable CSV SHA, signed summary, and report explicit unknown/censored cells. No provider/broker calls.
6. Audit year-level and monthly quote P&L, quote winning/losing trade count, largest two positive trades, drawdown, 2% adverse bid marketability, and source quality. **Report every full-year failure** and every candidate/exit mismatch; do not hide absent whole-year source observations. Time periods are not all equal (2025 H2 is six months, 2026 Jan–Apr four months); positive across 9 periods is a descriptive count, not a proof of alpha or annualized claim.

## Guardrails

- May 12–August 11, 2026 **protected master holdout remains completely sealed**; no 2026 May–August stock partition or option tape is read.
- Never call a live broker, never train on future data or calculate entry signals from future option quote P&L.
- **Signed BID reference does not verify an actual executable fill**, queue priority, bid size sufficient for quantity, market-order impact, order cancel acknowledgement, assignment/exercise, or paper fills.
- 24 correlated execution configurations per entry family do **not** count as 24 independent strategies. Prior tiny early-reversal seven quote-winning observations across the 2024/2025/2026 cohorts insufficient for live deployment.
- If source acquisition fails for any year, stop without converting missing into 0 P&L, without silently auto-retrying ambiguous provider calls, and preserve original event/ZIP evidence. Everything remains on local user workstation until explicit uploaded result.

**Status at preregistration:** V92 source verification passed, but **no V93–V94 six-year original option outcomes observed**. New code and tests committed; awaiting workstation compile/test and source run.

## Critical historically known SPY expiration-listing screen (added before any V93 paid GET)

**As-of original listing schedule, not post-trade price filtering:** Cboe's authoritative public product FAQ states Monday SPY weekly options were first listed February 16, 2018 (first expected Monday expiry February 26, 2018), Wednesday options in 2016, Tuesday weekly SPY listings began November 14, 2022 and Thursday listings November 16, 2022. Cboe's original November 2022 notice identifies first Tuesday expiration **November 22, 2022** and first Thursday weekday-regular expiration **December 1, 2022** (November 24 was Thanksgiving market holiday). Original sources:
- https://datashop.cboe.com/faqs
- https://cdn.cboe.com/resources/product_update/2022/Cboe-Options-to-List-SPY-and-QQQ-Tuesday-and-Thursday-Expiring-Weekly-Options.pdf

V93 adds a conservative explicit base-schedule **no-trade** classification `OPTION_0DTE_BASE_SCHEDULE_UNQUALIFIED_NO_TRADE` for original qualifying stock signals on ordinary days when a listed same-day SPY expiry cannot be expected from the standard historical schedule. Known base pattern: Wednesday/Friday throughout; Monday on or after 2018-02-26; Tuesday on or after 2022-11-22; Thursday on or after 2022-12-01. Normal 2023–2026 dates remain eligible as in the completed signed V89 campaigns. This screen does **not** change causal stock hypothesis thresholds or existing options exit policies: it marks a predicted entry as untradable due to instrument availability and retains it in the denominator with its original SHA-signed signal. It prevents requesting nonsensical 0DTE contracts on most pre-November-2022 Tuesdays and Thursdays. An exchange-holiday shifted expiration is **not independently proven by this base schedule**; any affected excluded session is separately documented as conservative unqualified, not as certain unlisted date, and must NOT be relabeled after observing later option P&L. A normal-schedule eligible date is *still not proof* an exact requested strike was listed or liquid; the signed original tape/quote gate remains authoritative. Tests cover 2018 Monday introduction, 2022 Tuesday/Thursday expansion, 2023+ preservation, and weekends.

Earlier V89 2024–2026 signed outputs are immutable and unchanged; V93 new code applies only to earlier historical campaigns, without rewriting original reports.
