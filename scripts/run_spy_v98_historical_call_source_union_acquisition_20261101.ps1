# V98 source-only cache-first historical CALL acquisition.
# Tests run BEFORE any provider GET; exact original V97B scope SHA verified.
# No broker orders, no historical PnL, protected 2026 holdout untouched.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py = '.\.venv\Scripts\python.exe'
if (!(Test-Path $py)) { throw 'Python venv not available' }
if ((git status --porcelain --untracked-files=no | Measure-Object).Count -gt 0) {
    throw 'Tracked files changed; stop before source acquisition'
}
$found = @(Get-ChildItem 'data/research' -Directory -Filter 'spy_v97b_49_variant_call_only_source_union_*' |
    Where-Object {
        (Test-Path (Join-Path $_.FullName 'summary.json')) -and
        (Test-Path (Join-Path $_.FullName 'call_only_candidate_source_coverage.json')) -and
        (Test-Path (Join-Path $_.FullName 'new_exact_call_source_union_preview.json'))
    })
if ($found.Count -ne 1) {
    throw "Expected exactly one original V97B workstation source directory; found $($found.Count)"
}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$out="data/research/spy_v98_safe_call_source_acquisition_$stamp"
try {
    Write-Host 'STAGE_START V98 exact-source reconstruction compilation'
    & $py -m py_compile scripts/run_spy_v98_historical_call_union_safe_acquisition.py
    if ($LASTEXITCODE -ne 0) { throw 'V98 compilation failure; zero provider calls' }

    Write-Host 'STAGE_START V98 tests: original CALL qid, early closes, SQLite RO and no-retry coordinator'
    $tmp=Join-Path $env:USERPROFILE ('at'+[guid]::NewGuid().ToString('N').Substring(0,8))
    & $py -m pytest -q --basetemp "$tmp" `
        tests/test_spy_v98_historical_call_union_safe_acquisition.py `
        tests/test_spy_v97b_49_variant_call_source_union_preview.py `
        tests/test_spy_v97a_call_only_original_source_capability.py `
        tests/test_spy_v89_six_family_source_batch.py `
        tests/test_spy_v90_six_family_capital_ledger.py `
        tests/test_options_on_demand_source_cache_v38.py `
        tests/test_strategy_options_source_runtime_v39.py
    if ($LASTEXITCODE -ne 0) {
        throw 'V98 regression failed; zero paid source dispatches'
    }

    Write-Host 'STAGE_START V98 signed V97B exact source identity and V38 READ-ONLY preflight'
    Write-Host 'V98 will fetch each missing, never-before-attempted exact CALL source at most once'
    Write-Host 'V98 unresolved previous-provider-query state will NEVER be auto-retried'
    & $py -m scripts.run_spy_v98_historical_call_union_safe_acquisition `
        --v97b-dir $found[0].FullName `
        --output-dir $out `
        --acquire-new
    if ($LASTEXITCODE -ne 0) {
        throw 'V98 original/source cache acquire stopped; preserve all existing evidence'
    }
    $result=Get-Content "$out/summary.json" -Raw | ConvertFrom-Json
    Write-Host "COMPLETE V98 source_mode=$($result.mode)"
    Write-Host "V98 first-time source candidates=$($result.fresh_first_dispatched_source_candidates)"
    Write-Host "V98 actual provider dispatch attempts=$($result.provider_dispatch_attempts)"
    Write-Host "V98 source resolutions=$($result.source_uses_resolved)"
    Write-Host "V98 explicit no data=$($result.source_uses_explicit_no_data)"
    Write-Host "V98 source ambiguous/failed=$($result.source_uses_failed_or_unresolved)"
    Write-Host 'V98 quote PnL NOT RUN; BROKER ORDERS 0'
}
finally {
    if (Test-Path $out) {
        $zip="$out.zip"
        if (!(Test-Path $zip)) {
            Compress-Archive -Path $out -DestinationPath $zip -CompressionLevel Optimal
        }
        Write-Host "PRESERVED_V98_ORIGINAL_SOURCE_EVIDENCE_ZIP: $zip"
    }
}
