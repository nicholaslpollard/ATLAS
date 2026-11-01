# ATLAS V103 read-only multimonth ORIGINAL V55/V65 closed-minute ORB campaign.
# Use pinned detached research checkout; no ThetaData GET, brokerage order or holdout.
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$python='.\.venv\Scripts\python.exe'
if (!(Test-Path $python)) { throw 'ATLAS Python venv is unavailable' }
if (@(git status --porcelain --untracked-files=no).Count -gt 0) {
    throw 'Tracked changes require review'
}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$out="data/research/spy_v103_multimonth_original_orb_$stamp"
try {
    Write-Host 'STAGE_START V103 compile new source, calendar, original quote account and tests'
    $modules=@(
      'packages/simulation/spy_v103_offline_orb_causal_account.py',
      'scripts/run_spy_v103_multimonth_original_closedbar_orb.py',
      'tests/test_spy_v103_multimonth_original_closedbar_orb.py',
      'scripts/run_spy_v65_full_june_offline_simulator_readiness.py',
      'packages/simulation/spy_v55_closed_bar_option_replay.py'
    )
    & $python -m py_compile @modules
    if ($LASTEXITCODE -ne 0) { throw 'V103 syntax gate stopped' }

    Write-Host 'STAGE_START V103 signed V55/V65 and multimonth source/account regressions'
    $temp=Join-Path $env:USERPROFILE ('v103test'+[guid]::NewGuid().ToString('N').Substring(0,8))
    & $python -m pytest -q --basetemp $temp `
      tests/test_spy_v103_multimonth_original_closedbar_orb.py `
      tests/test_spy_v65_full_june_offline_simulator_readiness.py `
      tests/test_spy_v51_native_minute_orb_inventory.py `
      tests/test_spy_v56_multi_session_quote_replay.py
    if ($LASTEXITCODE -ne 0) { throw 'V103 signed regressions failed' }

    Write-Host 'STAGE_START V103 eleven historical month source census + offline quote account'
    & $python -m scripts.run_spy_v103_multimonth_original_closedbar_orb `
       --start 2025-06-01 --end 2026-04-30 --output-dir $out
    if ($LASTEXITCODE -ne 0) { throw 'V103 source or account gate stopped; evidence retained' }

    $summary=Get-Content (Join-Path $out 'summary.json') -Raw | ConvertFrom-Json
    Write-Host "V103 COMPLETE months=$($summary.months) sessions=$($summary.exchange_sessions)"
    Write-Host "V103 cash_chain_complete=$($summary.continuous_cash_known)"
    Write-Host "V103 continuous_quote_pnl_if_known=$($summary.total_contiguous_quote_pnl_if_qualified)"
    Write-Host 'V103 offline source-only, no option provider GET, broker orders or holdout'
}
finally {
    if (Test-Path $out) {
        $root=Get-ChildItem $out -File | Where-Object {
            $_.Name -eq 'summary.json' -or $_.Name -eq 'chronological_account.json'
        }
        if ($root.Count -gt 0) {
            $summaryZip="$($out)_summary_evidence.zip"
            if (!(Test-Path $summaryZip)) {
                Compress-Archive -LiteralPath $root.FullName -DestinationPath $summaryZip -CompressionLevel Optimal
                Write-Host "PRESERVED_V103_SUMMARY_EVIDENCE_ZIP: $summaryZip"
            }
        }
        $fullZip="$($out)_full_source_linked_evidence.zip"
        if (!(Test-Path $fullZip)) {
            Compress-Archive -Path "$out\*" -DestinationPath $fullZip -CompressionLevel Optimal
            Write-Host "PRESERVED_V103_FULL_EVIDENCE_ZIP: $fullZip"
        }
    }
}
