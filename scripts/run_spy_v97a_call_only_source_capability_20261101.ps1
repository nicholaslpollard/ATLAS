# ATLAS V97A — complete nine-cohort signed CALL-only historical source census.
# No options provider GET, raw V38 cache write, brokerage order or PnL tuning.
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py='.\.venv\Scripts\python.exe'
if (!(Test-Path $py)) { throw 'ATLAS Python environment not found' }
if ((git status --porcelain --untracked-files=no | Measure-Object).Count -gt 0) {
    throw 'Tracked original repository changes require review'
}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$out="data/research/spy_v97a_call_only_original_source_capability_$stamp"
try {
    Write-Host 'STAGE_START V97A compilation'
    & $py -m py_compile scripts/run_spy_v97a_call_only_original_source_capability.py
    if ($LASTEXITCODE -ne 0) { throw 'V97A compilation failure' }
    $tmp=Join-Path $env:USERPROFILE ('at'+[guid]::NewGuid().ToString('N').Substring(0,8))
    Write-Host 'STAGE_START V97A source-only synthetic regressions'
    & $py -m pytest -q --basetemp "$tmp" `
        tests/test_spy_v97a_call_only_original_source_capability.py `
        tests/test_spy_v96_research_evidence_upload_packets.py `
        tests/test_spy_v89_six_family_source_batch.py `
        tests/test_spy_v90_six_family_capital_ledger.py
    if ($LASTEXITCODE -ne 0) {
        throw 'V97A regression failure; no research evidence produced'
    }
    Write-Host 'STAGE_START V97A all-nine-original-year CALL-only source and feature roster'
    & $py -m scripts.run_spy_v97a_call_only_original_source_capability `
        --output-dir $out
    if ($LASTEXITCODE -ne 0) { throw 'V97A original source SHA/census mismatch' }
    $summary=Get-Content "$out/summary.json" -Raw | ConvertFrom-Json
    Write-Host "V97A_READY: CALL archived=$($summary.original_CALL_sources_archived) CALL unresolved=$($summary.original_CALL_sources_unresolved) PUT excluded=$($summary.original_PUT_sources_not_eligible_for_CALL_only)"
    Write-Host "V97A historical original considerations=$($summary.original_six_family_considerations)"
    Write-Host "V97A source-complete cohorts=$($summary.historical_complete_source_cohorts)/$($summary.historical_original_cohort_count)"
    Write-Host 'Historical source GETs=0 broker orders=0'
}
finally {
    if (Test-Path $out) {
        Compress-Archive -Path $out -DestinationPath "$out.zip" `
            -CompressionLevel Optimal
        Write-Host "PRESERVED_V97A_SHA_EVIDENCE_ZIP: $out.zip"
    }
}
