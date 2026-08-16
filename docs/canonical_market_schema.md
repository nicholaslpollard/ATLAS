# ATLAS Canonical Market Schema

Canonical market data stores provider/source facts only.

## Canonical stock bar fields

| Field | Meaning |
|---|---|
| `symbol` | provider-native security symbol; case is preserved because Massive uses lowercase `p` in preferred-share tickers |
| `timestamp_utc` | semantic bar start in UTC |
| `session_date` | exchange trading-session date |
| `timeframe` | `1m` or `1d` in canonical storage |
| `session_segment` | premarket, regular, after-hours, or closed |
| `open/high/low/close` | provider OHLC |
| `volume` | provider aggregate volume |
| `vwap` | provider VWAP when supplied; otherwise null |
| `transaction_count` | provider aggregate transaction count when supplied |
| `provider` | source provider, initially `massive` |
| `dataset` | provider dataset identity |
| `source_id` | deterministic provenance key for the source object |
| `is_adjusted` | provider adjustment state when known |
| `provider_timestamp_utc` | optional original provider timestamp when semantic timestamp differs |

The Massive flat-file aggregates currently used by ATLAS do not supply a VWAP
column, so Phase 03 deliberately stores `vwap = null`; it does not invent one.

## Symbol case contract

Massive follows SIP ticker formatting and uses a lowercase `p` to identify
preferred-share symbols. Therefore ATLAS treats ticker case as semantically
significant and preserves it exactly apart from surrounding whitespace. For
example, `TPC` and `TpC` are different securities and must never be folded into
the same canonical symbol.

Downstream exact-symbol queries are also case-sensitive. User-facing search can
later provide aliases or suggestions, but canonical storage and joins always use
the provider-native symbol.

## Canonical daily timestamp

For 1d bars, `timestamp_utc` is the official regular-session open, which gives
ATLAS a stable trading-session semantic timestamp. Massive's original daily
`window_start` is retained as `provider_timestamp_utc`.

## Derived bars

15m, 1h and 4h are not provider facts and therefore live under `data/derived`.
They include the standard OHLCV fields plus:

- `bar_end_utc`
- `input_bar_count`
- internal derived provenance

1w and 1mo remain on-demand until later benchmarking demonstrates that permanent
materialization is worthwhile.
