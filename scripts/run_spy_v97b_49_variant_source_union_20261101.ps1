# ATLAS V97B 49-variant CALL-only offline source-union forecast.
# Zero ThetaData requests, no broker orders, no V90 outcome/PnL access.
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py='.\.venv\Scripts\python.exe'
if (!(Test-Path $py)) { throw 'ATLAS Python environment missing' }
if ((git status --porcelain --untracked-files=no | Measure-Object).Count -gt 0) {
    throw 'Tracked changes require review before V97B'
}
$original=Get-ChildItem 'data/research' -Directory -Filter 'spy_v97a_call_only_original_source_capability_*' |
    Where-Object {
        (Test-Path (Join-Path $_.FullName 'summary.json')) -and
        (Test-Path (Join-Path $_.FullName 'original_call_source_considerations.json'))
    }
if (@($original).Count -ne 1) {
    throw 'Exactly one signed V97A original stage directory is required'
}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$out="data/research/spy_v97b_49_variant_call_only_source_union_$stamp"
try {
    Write-Host 'STAGE_START V97B Python compilation'
    & $py -m py_compile scripts/run_spy_v97b_49_variant_call_source_union_preview.py
    if ($LASTEXITCODE -ne 0) { throw 'V97B compilation failed' }
    Write-Host 'STAGE_START V97B original-source and causal-preview tests'
    $tmp=Join-Path $env:USERPROFILE ('at'+[guid]::NewGuid().ToString('N').Substring(0,8))
    & $py -m pytest -q --basetemp "$tmp" `
        tests/test_spy_v97b_49_variant_call_source_union_preview.py `
        tests/test_spy_v97a_call_only_original_source_capability.py `
        tests/test_spy_v89_six_family_source_batch.py `
        tests/test_spy_v90_six_family_capital_ledger.py
    if ($LASTEXITCODE -ne 0) { throw 'V97B regression failed; no output' }
    Write-Host 'STAGE_START V97B all 49 CALL-only entry variants original 2018-2026 prior-source census'
    & $py -m scripts.run_spy_v97b_49_variant_call_source_union_preview `
        --v97a-dir $original[0].FullName --output-dir $out
    if ($LASTEXITCODE -ne 0) { throw 'V97B original input or causal source union rejected' }
    $report=Get-Content "$out/summary.json" -Raw | ConvertFrom-Json
    Write-Host "V97B entry variants=$($report.preregistered_entry_variants)"
    Write-Host "V97B CALL-only candidate occurrences=$($report.candidate_variant_occurrences)"
    Write-Host "V97B cached distinct full source scopes=$($report.original_distinct_archived_exact_call_scopes)"
    Write-Host "V97B distinct missing candidate source scopes=$($report.new_exact_distinct_call_scopes_to_review)"
    Write-Host "V97B original unknown scopes=$($report.original_distinct_unknown_exact_call_scopes)"
    Write-Host 'V97B provider GET=0 broker orders=0 simulated returns=NOT RUN'
}
finally {
    if (Test-Path $out) {
        $zip="$out.zip"
        if (!(Test-Path $zip)) {
            Compress-Archive -Path $out -DestinationPath $zip -CompressionLevel Optimal
        }
        Write-Host "PRESERVED_V97B_EVIDENCE_ZIP: $zip"
    }
}
