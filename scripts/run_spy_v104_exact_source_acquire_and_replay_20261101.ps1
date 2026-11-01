# ATLAS V104 original-source acquisition and original V55/V65 full replay.
# This may issue new historical ThetaData reads for the 45 original exact scopes.
# No broker orders, no retry of ambiguous exact source query, no master holdout.
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py='.\.venv\Scripts\python.exe'
if (!(Test-Path $py)) { throw 'ATLAS Python virtual environment missing' }
if (@(git status --porcelain --untracked-files=no).Count -gt 0) {
    throw 'Tracked changes require review'
}
$original='data/research/spy_v103_multimonth_original_orb_20261101_182528_full_source_linked_evidence.zip'
if (!(Test-Path $original)) { throw 'Original signed V103 full evidence ZIP required' }
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$acquisition="data/research/spy_v104_exact_orb_source_recovery_$stamp"
$replay="data/research/spy_v104_refreshed_orb_$stamp"
try {
    Write-Host 'STAGE_START V104 compile and signed source/account regressions; NO provider calls yet'
    $modules=@(
       'scripts/run_spy_v104_original_orb_source_recovery.py',
       'scripts/run_spy_v104_compare_refreshed_orb.py',
       'scripts/run_spy_v103_multimonth_original_closedbar_orb.py',
       'tests/test_spy_v104_original_orb_source_recovery.py',
       'tests/test_spy_v103_multimonth_original_closedbar_orb.py'
    )
    & $py -m py_compile @modules
    if ($LASTEXITCODE -ne 0) { throw 'V104 compilation failed' }
    $temp=Join-Path $env:USERPROFILE ('v104test'+[guid]::NewGuid().ToString('N').Substring(0,8))
    $testargs=@('-m','pytest','-q','--basetemp', $temp,
       'tests/test_spy_v104_original_orb_source_recovery.py',
       'tests/test_spy_v103_multimonth_original_closedbar_orb.py',
       'tests/test_strategy_options_source_runtime_v39.py',
       'tests/test_options_on_demand_source_cache_v38.py',
       'tests/test_spy_v65_full_june_offline_simulator_readiness.py',
       'tests/test_spy_v56_multi_session_quote_replay.py')
    & $py @testargs
    if ($LASTEXITCODE -ne 0) { throw 'V104 source/cache/account regressions failed' }

    Write-Host 'STAGE_START V104 signed original V103 verification + guarded V39 exact acquisition'
    & $py -m scripts.run_spy_v104_original_orb_source_recovery --original-v103-full-zip $original --output-dir $acquisition --acquire
    if ($LASTEXITCODE -ne 0) { throw 'V104 source audit/acquisition stopped; preserve dispatch journal' }
    $sourceSummary=Get-Content (Join-Path $acquisition 'summary.json') -Raw | ConvertFrom-Json
    Write-Host "V104 SOURCE_RESULT missing=$($sourceSummary.original_missing_source_queries)"
    Write-Host "V104 SOURCE_RESULT attempts=$($sourceSummary.provider_result.provider_dispatch_attempts)"
    Write-Host "V104 SOURCE_RESULT resolved=$($sourceSummary.provider_result.source_uses_resolved)"

    Write-Host 'STAGE_START V104 full 11-month V55/V65 source-only replay; NO additional provider calls'
    & $py -m scripts.run_spy_v103_multimonth_original_closedbar_orb --start 2025-06-01 --end 2026-04-30 --output-dir $replay
    if ($LASTEXITCODE -ne 0) { throw 'V104 refreshed V103 failed; original source receipts retained' }

    Write-Host 'STAGE_START V104 verify 227 historical signal fingerprints and original parents'
    & $py -m scripts.run_spy_v104_compare_refreshed_orb --original-v103-full-zip $original --refreshed-v103-dir $replay --output (Join-Path $acquisition 'verified_refreshed_source_comparison.json')
    if ($LASTEXITCODE -ne 0) { throw 'V104 source comparison stopped; both evidence directories retained' }
    $fresh=Get-Content (Join-Path $replay 'summary.json') -Raw | ConvertFrom-Json
    Write-Host "V104 COMPLETE acquired_sources=$($sourceSummary.provider_result.source_uses_resolved)"
    Write-Host "V104 COMPLETE continuous_cash_known=$($fresh.continuous_cash_known)"
    Write-Host 'V104 master holdout unread; broker orders=0; no fictional expiry cash'
}
finally {
    if (Test-Path $acquisition) {
        $sourceZip="$($acquisition)_evidence.zip"
        if (!(Test-Path $sourceZip)) {
            Compress-Archive -Path "$acquisition\*" -DestinationPath $sourceZip -CompressionLevel Optimal
            Write-Host "PRESERVED_V104_SOURCE_EVIDENCE_ZIP: $sourceZip"
        }
    }
    if (Test-Path $replay) {
        $roots=@(Get-ChildItem $replay -File | Where-Object {
            $_.Name -in @('summary.json','chronological_account.json')
        } | Select-Object -ExpandProperty FullName)
        if ($roots.Count -gt 0) {
            $summaryZip="$($replay)_summary_evidence.zip"
            if (!(Test-Path $summaryZip)) {
                Compress-Archive -Path $roots -DestinationPath $summaryZip -CompressionLevel Optimal
                Write-Host "PRESERVED_V104_REFRESHED_SUMMARY_ZIP: $summaryZip"
            }
        }
        $fullZip="$($replay)_full_source_linked_evidence.zip"
        if (!(Test-Path $fullZip)) {
            Compress-Archive -Path "$replay\*" -DestinationPath $fullZip -CompressionLevel Optimal
            Write-Host "PRESERVED_V104_REFRESHED_FULL_ZIP: $fullZip"
        }
    }
}
