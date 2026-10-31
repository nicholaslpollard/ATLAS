# V64 — failed V63 historical surface and two-clock quote forensics (2026-10-31)

The user ran V63 at 10:12:05 to 10:15:04 ET. Local tests passed (13), the previously accepted Alpaca source pages passed original SHA re-verification, and the attempt for the exact ThetaData `option_at_time_quote_surface` (`SPY`, `2025-06-13`, `09:59:59.000`, `right=put`, `max_dte=1`, `strike_range=3`) stopped with `ThetaDataError`. **No V63 accepted options surface report was created.** The request may or may not have reached the provider.

The historical ThetaData worker (`packages/providers/thetadata/client.py`) has a 180-second response timeout. The observed failure interval is consistent with that timeout but the console log preserves only the exception class, **not proof of the precise cause**. V38 cache presently translates *any* provider exception into `FAILED_RETRYABLE`. That SQLite status does **not** establish safe repeatability for an earlier ambiguous dispatch. Rerunning V63 as written could dispatch the same request again. **Do not rerun V63 until a separate trusted dispatch/receipt audit resolves that ambiguity.**

## V64 alternative — proceed without any new provider calls

`scripts/run_spy_v64_offline_two_clock_forensics.py` is a read-only original-source audit, using V61/V62 signed reports and the preexisting V56 0DTE exact-contract put 598 archive in V38. It:

1. Constructs the **exact** V63 source requirement, including normalized keyword defaults, then finds its stable query fingerprint and original status in V38's SQLite source index opened with `?mode=ro`. For `FAILED_RETRYABLE`, `IN_FLIGHT`, or no receipt, records **provider outcome unknown and no same-query retry**. For `ARCHIVED`, re-verifies original compressed source bytes through the V38 verifier. Does not alter cache state.
2. Re-verifies V61, V62 original signed reports and V62 Alpaca raw-page SHA/row counts. Retains the original 1,467 stock quotes in the existing source files. Reads original V56 exact-contract option source through V59's offline cached reader, validating V38 original SHA and the original V61-reported source SHA. No paid requests.
3. Builds *as-of* snapshots at 09:59:59, 10:00:00, 10:00:01 and 10:00:02 ET, separately for the PUT 598 original bid/ask and SPY underlying bid/ask. Stock timestamps preserve nanoseconds; a quote at 10:00:01.000000001 is **not** valid for an action at 10:00:01. The 10:00:02 snapshots are labelled future diagnostic-only, never used to approve a 10:00:01 action.
4. Independently records bid-size/ask-size, original quote rejection code, spread and option bid/ask change between 10:00:00 and 10:00:01, alongside stock mid move over the same interval. The paired changes help localize a suspect bid-versus-ask issue, but **cannot isolate IV, validate a model-fair price, guarantee an executable exit, or establish historical alpha**.
5. Persists a SHA-fingerprinted immutable JSON summary and no new provider request or broker operation.

### Scientific caveat

On the user-verified V59 tape, the SPY PUT 598 BID dropped from $1.70 at 10:00:00 to $1.05 at 10:00:01, while ASK fell from $1.81 to $1.60. The sell BID was thus notably more volatile than ASK. This is a descriptive observation, not proof of a wrong quote: true volatility, liquidity, or an exchange-book change could explain it. The contemporaneous SPY underlying mid will allow causal context; **do not** interpret the following 10:00:02 put bid as available at 10:00:01.

Only after this and independent earlier strike volatility is available can ATLAS apply V60 action-side model valuation. The retrospective June 13 event remains development-only, not a virgin holdout. No invented trade, mark, broker fills or recovered cash.

### Operating command

```powershell
$stamp=Get-Date -Format yyyyMMdd_HHmmss
& .\.venv\Scripts\python.exe -m scripts.run_spy_v64_offline_two_clock_forensics `
  --v61-report 'data/research/spy_v61_source_readiness_20261031_094733.json' `
  --v62-summary 'data/research/spy_v62_spot_quote_20261031_100317/summary.json' `
  --output "data/research/spy_v64_no_retry_two_clock_$stamp.json"
```

No provider SDK client creation, no ThetaData GET, no Alpaca GET, and no broker orders. The model outcome remains unresolved until new independent IV provenance can be established.
