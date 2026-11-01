# ATLAS V101 original offline PIT news metadata CALL re-account replay.
# No paid options provider requests; no brokerage orders or holdout.
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py='.\.venv\Scripts\python.exe'
if (!(Test-Path $py)) { throw 'ATLAS virtual environment missing' }
if (@(git status --porcelain --untracked-files=no).Count -gt 0) {
    throw 'Tracked changes require review before V101 replay'
}
$stage=@(Get-ChildItem 'data/research' -Directory -Filter 'spy_v99_49_call_quote_cash_campaign_*' |
    Where-Object {
        (Test-Path (Join-Path $_.FullName 'summary.json')) -and
        (Test-Path (Join-Path $_.FullName 'eight_period_exploratory_matrix.json')) -and
        (Test-Path (Join-Path $_.FullName 'trial_archive_manifest.json')) -and
        (Test-Path (Join-Path $_.FullName 'journals'))
    })
if ($stage.Count -ne 1) {
    throw "Exactly one complete original V99 directory required; found $($stage.Count)"
}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$out="data/research/spy_v101_original_news_gate_quote_replay_$stamp"
try {
    Write-Host 'STAGE_START V101 source/test syntax compilation'
    $modules=@(
        'scripts/run_spy_v101_news_metadata_gate_quote_replay.py',
        'scripts/run_spy_v100_v99_independent_wfo_audit.py',
        'tests/test_spy_v101_news_metadata_gate_quote_replay.py',
        'tests/test_spy_v100_v99_independent_wfo_audit.py'
    )
    & $py -m py_compile @modules
    if ($LASTEXITCODE -ne 0) { throw 'V101 Python syntax gate failed' }
    Write-Host 'STAGE_START V101 as-of news, original signed sources and V90 account regression tests'
    $tmp=Join-Path $env:USERPROFILE ('at'+[guid]::NewGuid().ToString('N').Substring(0,8))
    & $py -m pytest -q --basetemp $tmp `
        tests/test_spy_v101_news_metadata_gate_quote_replay.py `
        tests/test_spy_v100_v99_independent_wfo_audit.py `
        tests/test_offline_multiyear_news_context_v1.py `
        tests/test_spy_v90_six_family_capital_ledger.py `
        tests/test_spy_v99_49_call_variant_quote_economics.py
    if ($LASTEXITCODE -ne 0) { throw 'V101 original source/news/account regressions failed' }
    Write-Host 'STAGE_START V101 reverify 630 source journals and 10800 prior ledgers; replay 21600 news-gated capital scenarios'
    & $py -m scripts.run_spy_v101_news_metadata_gate_quote_replay `
        --v99-dir $stage[0].FullName --output-dir $out
    if ($LASTEXITCODE -ne 0) { throw 'V101 replay stopped; preserve evidence' }
    $summary=Get-Content "$out/summary.json" -Raw | ConvertFrom-Json
    Write-Host "V101 COMPLETE gated_ledgers=$($summary.news_gated_50_x_24_x_3_x_6_replayed_accounts)"
    Write-Host "V101 fully_comparable_six_cohorts=$($summary.full_six_period_complete_configurations)"
    Write-Host "V101 positive_all_six=$($summary.positive_in_all_six_if_complete)"
    Write-Host 'V101 protected master holdout unread; no new provider GETs or broker orders'
}
finally {
    if (Test-Path $out) {
        $summaryZip="$($out)_summary_evidence.zip"
        $fullZip="$($out)_full_source_linked_evidence.zip"
        $roots=@(Get-ChildItem $out -File | Where-Object {
            $_.Name -eq 'summary.json' -or
            $_.Name -eq 'scenario_comparison.json' -or
            $_.Name -eq 'opportunity_news_gate_decisions.json.gz'
        } | Select-Object -ExpandProperty FullName)
        if ($roots.Count -gt 0 -and !(Test-Path $summaryZip)) {
            Compress-Archive -Path $roots -DestinationPath $summaryZip -CompressionLevel Optimal
            Write-Host "PRESERVED_V101_SUMMARY_EVIDENCE_ZIP: $summaryZip"
        }
        if (!(Test-Path $fullZip)) {
            Compress-Archive -Path "$out\*" -DestinationPath $fullZip -CompressionLevel Optimal
            Write-Host "PRESERVED_V101_FULL_EVIDENCE_ZIP: $fullZip"
        }
    }
}
