# V43 — Original SPY 10:01 source quality and morning open-interest admission

## Workstation acquisition achieved (2026-10-29)

The user completed V40 against the original 361 SPY weekly call/put candidate pairs. The signed report `spy_v40_source_acquisition_20261029_173628.json` has fingerprint `7e5b088af272ec8f32af038480d28204156f5e16246985ff6bedded69dacf05e`, and confirms:

- **1,083/1,083 source requirements resolved**, all via actual new ThetaData calls, with no cache hits, source errors or explicit provider no-data.
- **361 historical exact call 10:01 quotes, 361 exact put 10:01 quotes, 361 decision-morning open-interest surfaces**, retained in immutable compressed V38 source archives and SQLite. Exact requested option identity matched on all **722** call/put request scopes.
- **1,612,682 total OI rows** across those morning surfaces. This is a *raw universe source-row count*, not proof that all 361 selected pairs have two qualifying OI observations.
- No historically qualified volatility entry signal, American IV, rate/dividend PIT features, executable fills or strategy P&L was produced.

Avoid downloading the same V40 data again. New strategy changes still generate new source requirements and the V39 resolver automatically fetches and archives missing exact queries when needed.

## V43: use the archived evidence to decide what actually qualifies

The V43 CLI checks the frozen V37/V40 content and fingerprints before opening provider/cache sources. It then streams the existing **1,083 exact acquisition needs** through the V38/V39 source resolver, which reuses original cached SHA-verified gzip archives and may fetch an absent source automatically. There is **no** fixed zero-provider-call assumption or total-request restriction.

For each of the 361 original entry identities it computes:

1. Exact original call and put row identity (expiration, strike, right, underlying), with missing/duplicate original contract evidence explicitly identified.
2. **10:01 quote quality:** observed local Eastern timestamp must have an explicit timezone, match session date and be no later than 10:01. Quote age at most **30 seconds**, positive two-sided bid/ask, displayed positive bid/ask sizes, and spread relative to midpoint at most **15%**.
3. **Pair synchronization:** selected call and put timestamps within **1 second**.
4. **Decision-morning OI quality:** find the original strike/expiry for BOTH rights within the raw OI surface; require exactly one observation for each, integer OI of at least **100 per leg**, and timestamp on the decision date **no later than 10:00**. This is morning publication of the previous session's state, not the OI of the current session.
5. **A narrow evidence report:** original 361-date source identities and SHA refs, exact premium/size/quote timestamps and filtered OI values, per-year pass/fail counts, explicit reasons for failures; no need to write all 1.6 million raw OI rows again.
6. Timestamped console **10%-completion** milestones and actual API/cached/error counters. No periodic heartbeat or extra progress-log file.

**A source-quality PASS is not a legitimate 10:00 entry signal or real 10:01 execution.** The 10:01 quote must not be used as an input available at the earlier 10:00 decision. The 09:59 SPY physical spot, historical rate, dividends, OCC deliverables, quote-source publication qualification, 101-step Leisen–Reimer IV and strictly prior corporate-action-qualified economic return inputs need their own causal gates before the real SPY signal can be computed. This study measures source matching and market microstructure; **not broker fills or trading profitability**.

## Next workstation command after CI merge

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }

    $py = '.\.venv\Scripts\python.exe'
    $v37 = 'data/research/spy_v37_pretrade_20261029_162223.json'
    $v40 = 'data/research/spy_v40_source_acquisition_20261029_173628.json'
    foreach ($file in @($v37, $v40)) {
        if (-not (Test-Path $file)) { throw "Missing retained input: $file" }
    }
    $report = "data/research/spy_v43_quote_oi_quality_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    & $py -m scripts.run_options_native_spy_source_admission_v43 `
        --v37 $v37 `
        --v40 $v40 `
        --output $report
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Some V43 sources or evidence were unresolved; previous original archives remain persisted'
    }
    if (Test-Path $report) { Write-Host "V43 quality report: $report" -ForegroundColor Green }
}
```

This **reads already archived records**, unless a required exact source is missing; then the resolver may make and persist a new provider call. No manually set call limit or typed authorization. Upload the V43 JSON and send console output. Next focus is PIT rates/dividends and American model IV + frozen prior-variance entry decision, using only genuinely available decision-clock evidence. Source-quality failures must not be interpreted as negative strategy returns.
