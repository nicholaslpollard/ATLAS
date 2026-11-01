# ATLAS V100 independent original V99 SHA source and prior-only model selection.
# Research-only; 0 ThetaData requests, 0 broker orders, no protected holdout.
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py='.\.venv\Scripts\python.exe'
if (!(Test-Path $py)) { throw 'ATLAS original Python environment missing' }
if ((git status --porcelain --untracked-files=no | Measure-Object).Count -gt 0) {
    throw 'Tracked changes require review before original source audit'
}
$source=@(Get-ChildItem 'data/research' -Directory -Filter 'spy_v99_49_call_quote_cash_campaign_*' |
    Where-Object {
        (Test-Path (Join-Path $_.FullName 'summary.json')) -and
        (Test-Path (Join-Path $_.FullName 'trial_archive_manifest.json')) -and
        (Test-Path (Join-Path $_.FullName 'eight_period_exploratory_matrix.json')) -and
        (Test-Path (Join-Path $_.FullName 'journals'))
    })
if ($source.Count -ne 1) {
    throw "Exactly one completed original V99 stage folder is required, found $($source.Count)"
}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$out="data/research/spy_v100_original_v99_rolling_audit_$stamp"
try {
    Write-Host 'STAGE_START V100 compile all new syntax and no-future regressions'
    $modules=@(
        'scripts/run_spy_v100_v99_independent_wfo_audit.py',
        'tests/test_spy_v100_v99_independent_wfo_audit.py'
    )
    & $py -m py_compile @modules
    if ($LASTEXITCODE -ne 0) {
        throw 'V100 source/test syntax invalid; no retrospective scoring started'
    }
    Write-Host 'STAGE_START V100 original SHA integrity, cash and causal selection regressions'
    $tmp=Join-Path $env:USERPROFILE ('at'+[guid]::NewGuid().ToString('N').Substring(0,8))
    $tests=@(
        'tests/test_spy_v100_v99_independent_wfo_audit.py',
        'tests/test_spy_v99_49_call_variant_quote_economics.py',
        'tests/test_spy_v90_six_family_capital_ledger.py'
    )
    & $py -m pytest -q --basetemp $tmp @tests
    if ($LASTEXITCODE -ne 0) {
        throw 'V100 original 630 journal, 10800 account or future-blind selector regressions failed'
    }
    Write-Host 'STAGE_START V100 independently SHA-audit all 630 original 1s trial journals and 10800 capital accounts'
    Write-Host 'STAGE_START V100 3 prior-only selectors across five chronological test cohorts'
    & $py -m scripts.run_spy_v100_v99_independent_wfo_audit --v99-dir $source[0].FullName --output-dir $out
    if ($LASTEXITCODE -ne 0) {
        throw 'V100 independent original signed source and cash audit rejected'
    }
    $result=Get-Content "$out/summary.json" -Raw | ConvertFrom-Json
    Write-Host "COMPLETE V100 original-account-ledgers=$($result.independent_source_and_cash_audit.account_scenarios_sha_verified)"
    Write-Host "V100 original-quote-SHA=$($result.independent_source_and_cash_audit.signed_source_archive_provenance.archive_sha_checked)"
    Write-Host "V100 fully-comparable=$($result.source_qualified_eightperiod_scenarios) robust-positive=$($result.positive_in_all_eight_scenarios)"
    Write-Host 'V100 no news leakage, no provider GET or broker orders'
}
finally {
    if (Test-Path $out) {
        $files=@(Get-ChildItem $out -File -Filter '*.json' | Select-Object -ExpandProperty FullName)
        if ($files.Count -gt 0) {
            $zip="$($out)_evidence.zip"
            if (!(Test-Path $zip)) {
                Compress-Archive -Path $files -DestinationPath $zip -CompressionLevel Optimal
            }
            Write-Host "PRESERVED_V100_SIGNED_AUDIT_AND_ROLLING_SELECTION_EVIDENCE: $zip"
        }
    }
}
