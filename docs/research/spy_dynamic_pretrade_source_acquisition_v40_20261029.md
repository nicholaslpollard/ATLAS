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

Long V40 runs now print ET timestamped **START** and **PROGRESS_10PCT** through **PROGRESS_100PCT** messages. Milestones are determined by the known source requirement total: one update per **10% completed**, so 10 of 100, 100 of 1,000, and one per completed requirement when the total is 10. For V40's 1,083-source initial cohort, the first completion milestone is 109/1,083; the final is 1,083/1,083. Individual failures also print immediately.

Every milestone includes completed/total, percentage, newly fetched receipts, cache hits, actual provider attempts, no-data/error counts, elapsed time, throughput, a rough observed ETA and the last processed source identity. The tool does **not** print 15-second heartbeats or create a separate progress log. Original source receipts and strategy lineage remain stored independently in the durable V38/V39 cache, including when the command ends before a final JSON report.

Run the latest merged `main` V40 script with its default progress settings. A slow single request will not produce a new line until a source completes or fails; absence of a line during that interval is not proof of a crash. A partial-cached initial sample can give an optimistic ETA that changes when slower provider requests begin. The total 1,083 refers to source *requirements*, not a required or capped provider call count.

The completed user-run V40 on October 29 acquired **1,083/1,083** original source requirements, made **1,083 provider calls**, archived **1,083** source responses, saw **0 cache hits / 0 failures / 0 explicit no-data**. It found exact call and put identities for all 361 original pairs, and archived decision-morning OI sources for 361 dates. The result is `data/research/spy_v40_source_acquisition_20261029_173628.json`. Do not re-download these original exact sources merely to demonstrate a new progress display. Future changed-strategy source requirements are dynamically fetched and retained. Historical PIT publication, validated American IV and actual fills are still open gates.

[ATLAS operating requirements](../architecture/atlas_living_operating_requirements_20261029.md) contains the permanent monitoring, caching, causal simulator and profitability objectives.
