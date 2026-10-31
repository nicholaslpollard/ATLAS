# V73 + V74 — real exchange sessions, dynamic options sell-to-close, broker rule comparison

Status: new independent source-first experiment and immutable original quote-reference exit challenger. **Do not promote to LIVE/PAPER options execution, claim actual fills, or overwrite original V55/V69/V70 receipts.**

## Verified workstation input evidence
The user ran V71 27/27 regression tests, full source clock diagnostic for both June 4/13 invalid 10:00:01 quotes, then attempted source-first option acquisition for January–May 2025. V71 identified 124 native stock months with original-file presence candidates. January, February, April, May passed full SHA verification of stock source but V69's legacy weekday list treated Jan1/Jan20, Feb17, Apr18 and May26 NYSE holidays as missing eligible 09:30 bars. This blocked **all** option requests for those four months. March acquired 12/13 original quotes and one explicit NO_DATA; source-qualified original V65 results had 6 closes, 5 unresolved positions, and two NO_ENTRY, source-aware V69 correctly censored one absent quote source. June 4 and June 13 both rejected an original 10:00:01 option quote >15% spread; first later quality-eligible observations occurred respectively 10:00:06 and 10:00:02, not evidence of original executed sale.

## V73 XNYS source-first calendar repair
ATLAS already depends on `exchange_calendars` and has `packages.core.market_calendar.get_market_calendar('XNYS')`. V73 uses its true trading sessions (including historical holidays and early closes) to build V69 cohorts **and** calls V65 with the identical filtered sessions. Original V65/V69 weekday functions remain the default to keep original signed report expectations and tests stable. V73's calendar must be monotonic, unique, within requested bounds, and cannot invent data on real eligible sessions with missing original bars. Every nonholiday eligible session still requires full original stock SHA verification **before** V39 automatic exact options source acquisition. Original missing/ambiguous provider attempts retain their V38 receipts; no blind retry.

The user's original January/February/April/May blocked folders are immutable; V73 MUST use new output directory names. March original signed V69 receipts remain available for offline dynamic-exit comparisons even with the explicit no-data. The preflight/replay source archive resolver may discover different contracts on new strategy revisions; original source cache first, automatically acquire all distinct exact options requirements for eligible sessions.

## Official broker expiration and options-order details, 2026-10-31

**Webull primary** ([exercise FAQ](https://www.webull.com/help/faq/659), [expiry risk FAQ](https://www.webull.com/help/faq/10614), [OpenAPI options orders](https://developer.webull.com/apis/docs/trade-api/options/), [specific API FAQ](https://developer.webull.com/apis/docs/trade-api/faq/)):
- A long SPY equity/ETF option that finishes at least $0.01 ITM normally automatically exercises into underlying shares, unless contrary DNE instruction applies; broker can risk-liquidate beforehand if not enough buying power. There is no unconditional cash settlement or guaranteed sellout.
- Webull's options REST interface supports `OPTION` contract legs and sell-to-close intent; supported LIMIT/STOP_LOSS/STOP_LOSS_LIMIT. **No native option trailing stop**; broker FAQ explicitly says **no market option orders**, and option sell-side is DAY time-in-force. The generic options page is less strict/inconsistent; use the stricter API FAQ until demonstrated otherwise.
- 0DTE single-leg *opening* cutoff is 15:40 ET and multileg opening cutoff 15:00 ET, which must **not** be confused with a guaranteed forced-close time.

**Alpaca manually selected fallback** ([Options Trading Overview](https://docs.alpaca.markets/us/docs/options-trading-overview), [Options Trading](https://docs.alpaca.markets/us/docs/options-trading), [support expiration](https://alpaca.markets/support/what-is-option-expiration)):
- Long options at least $0.01 ITM are typically exercised unless directed otherwise; physical SPY shares and actual buying power apply, no cash payout guarantee. Alpaca's expiration-day automatic risk checks start **15:30 ET**; it may liquidate positions that cannot safely exercise, but a sale cannot be guaranteed.
- Alpaca supports API option symbols, DAY limit and market orders and order cancel/replace; option approval required. Documentation on Alpaca DNE API vs manual contact varies by product/service and should be checked for the actual account before any broker-side DNE implementation. No DNE action is authorized by this research.
- Accepted ATLAS Phase15 adapter and schema still only trade EQUITY in PAPER; these official APIs show a future integration route, NOT proof ATLAS has operational option submit/reconcile or LIVE approval.

Both brokers' exchange-traded SPY options are **physically settled**. Protective liquidation begins under the ATLAS risk plan, never after assuming net intrinsic payout. No automatic cross-broker retry/failover.

## V74 independent quote reference dynamic exit
New `packages/simulation/spy_v74_dynamic_sell_to_close_shadow.py` and `scripts/run_spy_v74_original_dynamic_exit_cohort.py`:
- Independently revalidate original signed V69 preflight/after/source/chunk/root and V55 signed entry and 1s/1% *entry* quote-reference policy; source cache is accessed by V59 original SHA/index verifier in SQLite `mode=ro`. No provider GET or broker mutation.
- One predeclared experimental exit policy per broker label: original stop -50%, target +100%, profit protection armed at +20% option BID and a nonloosening 15% BID high-water trail, maximum hold 180 minutes, proactive exit intent at 15:00 ET (ATLAS **research** time, NOT published broker forced-close time), last chance 15:05 ET. Decision quote separated from actionable quote by **1 second**. Experimentally compare a 3s action-lag version only as a separately registered later sensitivity.
- The path audits **every later source quote**: invalid spreads and sizes are recorded and skipped only as *observations*, with max invalid-quote blackout 30 seconds or max gap 60 seconds. Quotes after an exit intent are reviewed and never silently assumed equivalent to the earlier indicated price. When later qualified displayed BID size is insufficient for all contracts, note partial-liquidity possibility but **do not invent partial execution**; keep the whole exit pending. An allowed current quote with full size becomes a **quote-reference potential close** with fee-aware action-side bid, not an actual traded fill. If no qualified action before deadline, leave account/position censored.
- All original NO_SIGNAL/NO_ENTRY positions preserve their entry disposition; explicit SOURCE_NO_DATA remains source-unresolved, not no-trade. Save signed per-date/per-broker full event decision trees, reason codes and quote-reference fee P&L.
- Cash is chained only chronologically until first unresolved source/position or frozen-sized trade above available cash. Profit and account return are not inferred past a censored exposure. These exits are explicitly retrospective development alternatives **not historical alpha validation**, and cannot justify parameter selection until properly prior-fold trained and later held-out.
- Broker labels make separate evidence surfaces for eventual broker-specific fill and expiry policies; **currently they share the same early conservative research cutoff** because historic broker-specific 0DTE fill and intervention clocks are not independently proved.

## Combined workstation procedure

1. Run V73 for **January, February, April and May 2025** in new `data/research` folders. The 2025 March original 12 archived tapes remain reusable; do not repeat an already terminal explicit-no-data exact March31 query.
2. Run V74 against each new signed V73 folder, the prior March V69 folder and original June2–30 V69 folder. Provide each signed parent fingerprint **from its actual `summary.json`**; never change or overwrite the parent.
3. Compare by day: original baseline vs dynamic Webull/Alpaca research quote dispositions, source qualification, score of originally unresolved trades with a later qualified quote, modeled option premium and costs, prior-only timestamp/exit events, censored daily account. A positive quote replay does not establish market order fills. Review adverse quote action drift and need for partial order fill adapter before paper options.
4. After identifying gaps, use the source-ready 124-month catalog to select **more non-holdout months** in parallel source-first folds. Ultimately fit exit thresholds only on earlier windows and certify later independent per-week/per-month/per-year performance before strategy promotion.

### Running V74 for one previously accepted original month (zero paid calls)
```powershell
& '.\.venv\Scripts\python.exe' -m scripts.run_spy_v74_original_dynamic_exit_cohort `
  --v69-folder 'data/research/spy_v69_full_june_20261031_134145' `
  --expected-v69-fingerprint '0b8379ee99238bfde3c4230e74f7d8c9412c3fece899f3f0e1e3b3c75a18d7dd' `
  --output-dir "data/research/spy_v74_original_june_$(Get-Date -Format yyyyMMdd_HHmmss)"
```
Source acquisition: ZERO. Broker calls: ZERO. Immutable baseline unchanged. The newly generated source-only research report is a **separate** experimental comparison.
