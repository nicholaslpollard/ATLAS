# V62 — exact-time SPY stock NBBO historical source capture (Alpaca SIP)

## Objective

V61 confirmed the original SPY 598 PUT quote at 2025-06-13 10:00:01 ET cannot be evaluated by BSM from the existing records: original quote/option source SHA valid, last completed SPY minute close **598.15**, but no verified stock quote at the target second, no independent prior implied-volatility band or independently published rate/dividend evidence. V60 asks for independent fair value to classify whether the bid or ask side of the *acted* PUT SELL is abnormal. The quote spread alone is insufficient.

## Source plan

ATLAS already has an Alpaca client for historical minute bars and a credential profile. The new `AlpacaMarketDataClient.historical_stock_quote_page` uses Alpaca's documented read-only historical stock quote route `GET /v2/stocks/SPY/quotes`. The request is only **09:59:58 through 10:00:02 ET, June 13, 2025**, with `feed=sip`, ascending timestamps, at most 12 pages of 10,000 records. `feed=iex` is an explicit alternative and must never silently replace SIP or be called unless the user chooses it. Any permission error is real; do not assert entitlement until the actual credentials respond.

The `run_spy_v62_historical_spot_capture` script:
- Requires the exact V61 immutable signed report and its 10:00:01 target. Re-running requires a new output directory.
- Writes **each original provider raw JSON page verbatim** to a new archival path with SHA-256 digest and row count before issuing the next page.
- Preserves original nanosecond timestamps; parses up to 9 decimal digits without truncating a quote at 10:00:01.000000001 into an apparently causal 10:00:01 reference.
- Never considers any stock quote published after **10:00:01.000000000 ET** for that decision, or over two seconds earlier; chooses the most recent past-only valid positive, noncrossed SPY bid/ask with positive sizes and captures original exchange/condition flags.
- Requires complete pagination. If the source needs more than 12 pages, writes `CENSORED_TOO_MANY_HISTORICAL_PAGES` and **does not** select any spot quote from an incomplete window.
- Persists the entire provenance summary, valid/rejected candidate counts, latest selected raw quote timestamp, age, bid/ask/size/spread and raw-page digest. Does not overwrite the V55/V56/V57/V58/V59/V60/V61 original evidence.
- Treats the underlying stock quote as a *candidate independent spot reference*, not a guaranteed executable stock or options quote. Stock quote condition codes and quote receipt first-publication timing remain to be fully validated.
- Does **not** estimate IV, BSM theoretical put value, salvage historical trade fills or compute cash P&L. Until independent earlier option IV, rates and dividends are established, V60 model gate continues abstaining.

All API calls in this script are Alpaca stock market-data GETs; no ThetaData GETs or broker orders. Local synthetic tests make zero provider requests.

## User-facing run

Test before source acquisition:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_spy_v62_historical_spot_capture.py tests/test_spy_v61_independent_source_readiness.py
```

Then acquire:

```powershell
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
& .\.venv\Scripts\python.exe -m scripts.run_spy_v62_historical_spot_capture `
    --v61-report 'data/research/spy_v61_source_readiness_20261031_094733.json' `
    --output-dir "data/research/spy_v62_spot_quote_$stamp" `
    --feed sip
```

A 401/403/permission error is not an absence of historical market quotes and must not be handled by fabricated quotes or silent IEX switching.

Alpaca documentation: https://docs.alpaca.markets/us/reference/stockquotesingle-1 (timestamp, ask/bid, sizes, conditions), https://docs.alpaca.markets/us/reference/stockquotes-1 (time bounds, pagination, feed).

## Remaining work

1. Verify the actual SIP quote/time/depth/conditions and market-data entitlement; if unavailable assess explicit IEX historical reference as a different, weaker feed with clear provenance.
2. Source one or more *other options contracts* as of **before** 10:00:01 to independently estimate an IV interval. The current V38 June 13 cache has only the acted-on put 598, so current-midpoint IV would be circular.
3. Verify historical rates, dividends, American exercise/carry approximations, model uncertainty and sensitivity to IV/spot changes.
4. Apply V60 bid-side valuation rule, quote size, latency, and original stop-loss checks. The reviewed day remains developmental; do not publish profitability from post-outcome quote recovery.
5. Once independent inputs established, run identical quote-side rules across a larger later date cohort, complete each trade journal, retain all no-trades/reasons, and validate after-fee net returns by weekly/monthly/annual windows.
