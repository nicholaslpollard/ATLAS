# ATLAS V93–V94 | six frozen new-family yearly experiments 2018–2023.
# Preserve exact V89/V90/V91 rules already applied to 2024–2026.
# V93 pins the user's 72-month V92 signed original evidence and rehashes all
# original stock archives BEFORE any ThetaData option GET. Only cache-miss
# source-only historical option GETs are allowed; broker orders NEVER allowed.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py = '.\.venv\Scripts\python.exe'
$v92 = 'data/research/spy_v92_pre2024_original_stock_inventory_20261101_105004'
if (!(Test-Path $py)) { throw 'ATLAS virtualenv missing' }
if (!(Test-Path "$v92/summary.json")) {
    throw 'Frozen original V92 source inventory folder missing'
}
if ((git status --porcelain --untracked-files=no | Measure-Object).Count -gt 0) {
    throw 'Tracked local files were modified'
}

# Previously completed original and signed 2024–2026 V89/V90 evidence.
# These are READ ONLY; do not repeat source GETs for existing cohorts.
$old = @{
  '2024_full' = @(
    'data/research/spy_v89_six_new_families_2024_full_20261101_102938',
    'data/research/spy_v90_six_new_families_2024_full_20261101_102938'
  )
  '2025_h2' = @(
    'data/research/spy_v89_six_new_families_2025_h2_20261101_102938',
    'data/research/spy_v90_six_new_families_2025_h2_20261101_102938'
  )
  '2026_janapr' = @(
    'data/research/spy_v89_six_new_families_2026_janapr_20261101_102938',
    'data/research/spy_v90_six_new_families_2026_janapr_20261101_102938'
  )
}
foreach ($pair in $old.Values) {
    foreach ($dir in $pair) {
        if (!(Test-Path "$dir/summary.json")) {
            throw "Original signed historical cohort missing: $dir"
        }
    }
}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$created=[System.Collections.Generic.List[string]]::new()
$new=@{}
try {
    Write-Host 'STAGE_START V93-V94 compilation and no-provider regression tests'
    & $py -m py_compile `
        scripts/run_spy_v93_frozen_2018_2023_preflight.py `
        scripts/run_spy_v94_nine_cohort_original_source_matrix.py `
        scripts/run_spy_v89_six_family_source_batch.py `
        scripts/run_spy_v90_six_family_source_replay.py `
        packages/simulation/spy_v89_six_family_causal_registry.py `
        packages/simulation/spy_v90_six_family_capital_ledger.py
    if ($LASTEXITCODE -ne 0) { throw 'Source campaign not started: compilation failed' }

    $tmp=Join-Path $env:USERPROFILE (
        'at' + [guid]::NewGuid().ToString('N').Substring(0,8)
    )
    & $py -m pytest -q --basetemp "$tmp" `
        tests/test_spy_v93_frozen_2018_2023_preflight.py `
        tests/test_spy_v93_historical_spy_0dte_expiry_screen.py `
        tests/test_spy_v94_nine_cohort_original_source_matrix.py `
        tests/test_spy_v92_pre2024_original_minute_coverage.py `
        tests/test_spy_v89_six_family_causal_registry.py `
        tests/test_spy_v89_six_family_source_batch.py `
        tests/test_spy_v90_six_family_capital_ledger.py `
        tests/test_spy_v91_six_family_cross_period_evidence_matrix.py `
        tests/test_spy_v84_offline_three_family_economics.py `
        tests/test_spy_v85_shared_capital_quote_portfolios.py `
        tests/test_spy_v86_original_option_exit_recheck.py
    if ($LASTEXITCODE -ne 0) { throw 'No source acquisition: regression suite did not pass' }

    $gate="data/research/spy_v93_preflight_2018_2023_$stamp"
    $created.Add($gate)
    Write-Host 'STAGE_START V93 pinned V92 evidence + 72 monthly source-byte SHA verification'
    & $py -m scripts.run_spy_v93_frozen_2018_2023_preflight `
        --v92-source-dir $v92 --output-dir $gate
    if ($LASTEXITCODE -ne 0) { throw 'No provider acquisition: V93 original evidence preflight failed' }

    foreach ($year in @(2018,2019,2020,2021,2022,2023)) {
        $key="$($year)_full"
        $source="data/research/spy_v93_v89_six_families_$($key)_$stamp"
        $replay="data/research/spy_v93_v90_six_families_$($key)_$stamp"
        $created.Add($source)
        $new[$key]=@($source,$replay)

        Write-Host "STAGE_START original causal six-family 0DTE source acquisition year=$year"
        & $py -m scripts.run_spy_v89_six_family_source_batch `
            --start "$year-01-01" --end "$year-12-31" `
            --acquire-options --output-dir $source
        if ($LASTEXITCODE -ne 0) {
            throw "V89 $year stopped: retain source event journal, do not silently retry"
        }
        $pre=Get-Content "$source/summary.json" -Raw | ConvertFrom-Json
        if (!$pre.all_required_sources_archived -or
             $pre.source_resolution.status -ne 'ALL_REQUESTED_SOURCES_PRESENT') {
            throw "Original source receipt census incomplete year=$year"
        }
        Write-Host "SOURCE_PASS year=$year considered=$($pre.considered_decisions) exact_sources=$($pre.exact_source_requirements)"

        $created.Add($replay)
        Write-Host "STAGE_START V90 original SHA source-only 24 original-exit variants year=$year"
        & $py -m scripts.run_spy_v90_six_family_source_replay `
            --v89-source-dir $source --output-dir $replay
        if ($LASTEXITCODE -ne 0) { throw "V90 year $year failed: preserve original ZIPs" }
        $report=Get-Content "$replay/summary.json" -Raw | ConvertFrom-Json
        if ($report.portfolio_scenarios -ne 168 -or
            $report.signed_quote_trial_journals -ne 24 * $pre.exact_source_requirements) {
            throw "V90 year $year original outcome census mismatch"
        }
        Write-Host "REPLAY_PASS year=$year journals=$($report.signed_quote_trial_journals) ledgers=$($report.portfolio_scenarios) censored=$($report.portfolio_scenarios_with_unresolved_cash)"
    }

    $matrix="data/research/spy_v94_nine_period_six_family_matrix_$stamp"
    $created.Add($matrix)
    $options=@('--v93-preflight-dir',$gate)
    foreach ($year in @(2018,2019,2020,2021,2022,2023)) {
        $key="$($year)_full"
        $options+=@("--v89-$year-full",$new[$key][0],
                    "--v90-$year-full",$new[$key][1])
    }
    $options+=@(
        '--v89-2024-full',$old['2024_full'][0],
        '--v90-2024-full',$old['2024_full'][1],
        '--v89-2025-h2',$old['2025_h2'][0],
        '--v90-2025-h2',$old['2025_h2'][1],
        '--v89-2026-janapr',$old['2026_janapr'][0],
        '--v90-2026-janapr',$old['2026_janapr'][1],
        '--output-dir',$matrix
    )
    Write-Host 'STAGE_START V94 nine-period 1512-cell no-selection original portfolio SHA matrix'
    & $py -m scripts.run_spy_v94_nine_cohort_original_source_matrix @options
    if ($LASTEXITCODE -ne 0) { throw 'V94 matrix generation failed: preserve all original evidence' }

    $summary=Get-Content "$matrix/summary.json" -Raw | ConvertFrom-Json
    Write-Host 'ATLAS V93-V94 HISTORICAL EXTENSION COMPLETE'
    Write-Host "Historical cohorts: $($summary.distinct_historical_cohort_count)"
    Write-Host "Matrix comparisons: $($summary.total_comparison_rows)"
    Write-Host "Complete nine-cohort scenarios: $($summary.complete_nine_cohort_configurations)"
    Write-Host "Positive all nine periods, exploratory only: $($summary.diagnostic_positive_in_all_nine_cohorts)"
    Write-Host 'Provider calls in V94 comparison: 0'
    Write-Host 'Broker orders: 0'
    Write-Host 'Protected May-August 2026 master holdout: UNTOUCHED'
}
finally {
    foreach ($dir in $created) {
        if (Test-Path $dir) {
            $zip="$dir.zip"
            if (!(Test-Path $zip)) {
                Compress-Archive -Path $dir -DestinationPath $zip -CompressionLevel Optimal
            }
            Write-Host "PRESERVED_EVIDENCE_ZIP: $zip"
        }
    }
}
