# V40 — SPY 361-pair pretrade source acquisition, on demand

## Result of V37 from workstation

User completed the V37 411-week source-bound variance bridge on Oct 29, 2026:
- Source report: `data/research/spy_v37_pretrade_20261029_162223.json`
- Frozen report fingerprint: `61fe65551f6b9b9f1818c7eefa78bd3fa46f9814f0f80c2df35384c6412d17c8`
- **411** weekly entry clocks; **361** frozen first-pair selections; **50** original abstentions.
- **358/361** selected pairs have retrospective raw/retrospective-dividend volatility windows; 3 gap dates: **2019-08-19, 2019-09-03, 2019-09-09**.
- Call/put American IV, prior-session OI publication evidence, time-qualified execution, and actual volatility signal are **not** yet qualified. Do not confuse availability of retrospective 20-return estimates with historical PIT feature acceptance.
- No strategy account P&L was produced.

## V40 work: acquire all source requirements and persist once

Build the exact entry/initial risk source demand from all V37 selected contracts and process through the V39 source resolver backed by V38's immutable compressed ThetaData source archive.

Per selected SPY entry session, generate:
1. **Decision-date morning OI publication** representing the previous XNYS trading session's end-of-day open interest, both rights, with historical scope DTE up to 75 and all eligible strikes; the selected expiration is ~30–45 DTE at the entry session. ThetaData documents publication at approximately 06:30 ET; the actual OPRA timestamp and source availability by 10:01 ET remain unverified until the returned historical evidence is qualified. Querying the previous session date would normally return OI for the session before that.
2. Exact selected expiration/strike call quote at **10:01:00 ET**, using `option_at_time_quote`.
3. Identical exact selected expiration/strike put quote at **10:01:00 ET**.

For the original 361-pair sample, the fully expanded source-demand stream contains **1,083 exact source uses**. This is the *expected input count*, NOT a fixed provider-call ceiling or a requirement to issue 1,083 new paid GETs. Each exact query is checked against the indexed persistent archive first. Provider calls are made automatically for missing sources and original responses are losslessly compressed, SHA-indexed and reused in other strategy versions. A user changing strategies may generate more or fewer candidates and any number of new requests; the general generator has no 361-entry cap and accepts new contract identities.

The original 10:00 quotes remain retained; the 10:01 requests are separate event evidence. Even if the at-time provider returns the exact contract, the quote is NOT a broker fill. Quoted bid/ask size, availability, crossed quotes, required pair skew and independent historical source publishing times still need validation. The open interest response must be matched by original expiration/strike/right; any option chain filters that fail to restrict results cannot be assumed successful. V40 captures matching-identity observations as diagnostics only. No American-model IV or signal is computed yet; no rate, dividend or OI is given a fabricated zero. An unavailable source stays explicitly unresolved.

## Run on the workstation after PR is tested and merged

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }

    $py = '.\.venv\Scripts\python.exe'
    $file = 'data/research/spy_v37_pretrade_20261029_162223.json'
    $out = "data/research/spy_v40_source_acquisition_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    & $py -m scripts.run_options_native_spy_dynamic_source_acquisition_v40 `
        --v37 $file `
        --output $out
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'V40 has unresolved sources or an execution error; retained successful sources remain indexed for restart'
    }
    Write-Host "V40 status report: $out"
}
```

The command processes the whole candidate set and normally performs provider calls on cache misses. It records actual provider attempts, newly archived sources, verified cache hits, source-only exact-contract observations and unresolved cases. A second run reuses previously archived sources and retries failures; no previously acquired data needs to be discarded. If the command ends before writing a report, the persistent cache still retains completed source receipts.

**Next sprint:** source-qualified OI field extraction/publication, bid/ask clock and pair-skew checks, PIT rates/dividends/corporate actions, independent 101-step American IV and the fixed training-free realized-variance-vs-IV entry decision. Then dynamic exit data demand must be emitted by the same runtime. Distinguish genuine missing provider data and data time-availability uncertainty from a model abstention.

## V42 runtime progress and timing

Long V40 runs now print ET timestamped **START**, **FIRST_SOURCE**, **PROGRESS** and **HEARTBEAT** records every 15 seconds during active provider calls and at least every 25 completed source requirements, plus immediate source-error events. The status shows completed/1,083, percentage, newly fetched receipts, reused cache, actual provider dispatch attempts, no-data/errors, elapsed, observed requirement throughput, rough remaining time, current active source and its request age. A flushed `.progress.log` is saved beside the requested final JSON report and remains available even if the run is interrupted; successful archived source receipts are already independently durable in V38.

Run the latest merged `main` script with `--heartbeat-seconds 15 --progress-every 25` (these are the defaults). Do not interpret an ETA printed during mostly cached initial requests as a guaranteed wall-clock completion date; provider response time and large open-interest surfaces may vary. Planning-only calculation if all 1,083 requirements need new GETs: 1s each ~18 minutes, 3s ~54 minutes, 5s ~90 minutes, plus SDK/authentication, caching and error recovery; the true runtime can be much shorter or hours longer. This is **not** a measured benchmark or a provider-call cap. Every newly discovered strategy/exit requirement may require further API requests and a newly saved source.

[ATLAS operating requirements](../architecture/atlas_living_operating_requirements_20261029.md) contains the permanent monitoring, caching, causal simulator and profitability objectives.
