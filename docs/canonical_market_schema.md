# Canonical Stock-Bar Contract

Canonical ATLAS bars represent normalized provider facts.

## Timestamp rules

- All canonical timestamps are timezone-aware UTC datetimes.
- Naive datetimes are rejected.
- `session_date` is the corresponding market-local trading date, not simply the UTC calendar date.
- Market-local calculations use `America/New_York`.

## Initial canonical fields

- symbol
- timestamp_utc
- session_date
- timeframe
- session_segment
- open
- high
- low
- close
- volume
- provider VWAP when available
- transaction count when available
- provider
- dataset
- source identifier
- adjustment flag when known

## Canonical timeframes

Initial persistent canonical stock bars are `1m` and `1d`.

`15m`, `1h`, and `4h` are derived/materialized bars. `1w` and `1mo` are initially derived on demand.

## OHLC contract

For every valid bar:

- `high >= open`
- `high >= close`
- `high >= low`
- `low <= open`
- `low <= close`
- volume is non-negative
- values must be finite

## What does not belong in canonical bars

- RSI / MACD / EMA / ATR
- support/resistance
- regime labels
- ML probabilities
- strategy signals
- analogue/simulation results
- OpenAI judgments
- trade plans

Those are derived or operational state.
