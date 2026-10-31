# V61 — real historical reference source readiness for side-aware Black–Scholes valuation

V60's synthetic tests verify buy ASK and sell BID as independent action-side pricing candidates. A wide quote does **not** establish that the acted side is wrong. However, a V60 model-consistent price is meaningful only when the independent benchmark itself is point-in-time credible.

## This development checkpoint

The actual original 2025-06-13 SPY put 598 from V59 showed 10:00:01 ET BID 1.05 (size 2), ASK 1.60 (size 5). One second prior bid was 1.70. The correct target is the **sell BID**; no Black–Scholes mark can create an executable bid. June 11 put 602 did not enter due to 1% adverse ASK drift, a distinct action-latency rejection.

The repo has an accepted SHA-verified Alpaca historical SPY **one-minute stock-bar** pipeline (V2). Those are historical OHLC, *not* certified spot best bid and ask at the action second. A minute bar from 09:59 to 10:00 is complete by 10:00 but its publication lag, any market price change in the next second, and whether the minute close equals underlying executable quote are not established.

The V38 original exact-option source cache has a SQLite receipt index, potentially including alternative strikes, rights and quote-clock scopes. Mere receipt existence does not establish independent implied volatility: the source needs independently timed SPY spot, historical rate/dividend as-of, clean prior historical option quotes, conditional expiry and quote-quality checks. It is invalid to compute the candidate's IV from its *own suspicious midpoint*.

## V61 preflight script

Run `python -m scripts.run_spy_v61_independent_source_readiness` with the original V56 cohort folder and a new output path. The script:

1. Verifies V56 summary fingerprint, June 13 original immutable report, and SHA-linked event journal tip.
2. Retains original signal, selected option contract, entry's action BID/ASK and adverse ASK drift metadata.
3. Resolves only the original SPY June 2025 month-scoped native minute checkpoint, verifies **both** canonical and raw bundle SHA-256, and checks full session minute OHLC geometry.
4. Selects the latest **completed** SPY minute bar known by the decision second. Reports bar open/high/low/close, bar completion time, and the parent monthly source SHA. Explicitly marks *exact second-level stock quote absent* and *bar-close publication timing not proven*.
5. Reads V38 SQLite source index in URI `mode=ro` only, lists any original or alternative SPY option-source receipts for that date, preserving query ID, method, contract, SHA and state. Does not open their payloads, infer IV or ask any provider.
6. Persists a new immutable fingerprinted report with missing independent stock quote, prior IV, historical rate/dividend provenance; explicitly `ABSTAIN_MISSING_INDEPENDENT_MODEL_INPUTS`; zero provider and broker calls.

This program is a **source-inventory diagnostic**, not an attempt at BSM repricing or source acquisition. Do not interpret the previous minute close as a 1s SPY spot quotation.

## Credible next source options

Alpaca documents historical stock BID/ASK `GET /v2/stocks/{symbol}/quotes`, including SIP or IEX feeds, timestamp and depth (actual account entitlements unverified): https://docs.alpaca.markets/us/reference/stockquotesingle-1 . ThetaData documents 1-second/tick `stock_history_quote()` for accounts with the relevant stock entitlements, which is **not established by the current Options Standard subscription alone**: https://docs.thetadata.us/operations_python/stock_history_quote.html .

Only after an entitlement check and one narrowly scoped immutable historical source acquisition, derive an independent SPY spot BID/ASK as of June 13 10:00:01; separately construct an earlier-only volatility interval from qualified other option quotes, with prior rates and dividend as-of data. Reprice via V60 model using both volatility bounds, and keep a no-independent-reference verdict if any prerequisite fails.

The June 13 reviewed example is already in-sample. Report eventual earlier vs later untouched cohort profitability separately; never claim this result demonstrates alpha or a historical fill.
