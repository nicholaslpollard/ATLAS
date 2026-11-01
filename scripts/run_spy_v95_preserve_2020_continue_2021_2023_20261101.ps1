# ATLAS V95: preserve failed 2020 source census; continue untouched years.
# DO NOT rerun 2018, 2019 or the original 2020 paid V89 campaign.
# No ThetaData calls for 2020. New cache-first provider requests are permitted
# ONLY for independently qualified 2021–2023 original option requirements.
# Read-only V95 2020 forensics; 2020 PnL stays CENSORED if unresolved.
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py='.\.venv\Scripts\python.exe'
$prior='20261101_111155'
$priorLast='20261101_102938'
$gate="data/research/spy_v93_preflight_2018_2023_$prior"
$source2020="data/research/spy_v93_v89_six_families_2020_full_$prior"
$old=@{
  '2018_full'=@(
    "data/research/spy_v93_v89_six_families_2018_full_$prior",
    "data/research/spy_v93_v90_six_families_2018_full_$prior")
  '2019_full'=@(
    "data/research/spy_v93_v89_six_families_2019_full_$prior",
    "data/research/spy_v93_v90_six_families_2019_full_$prior")
  '2024_full'=@(
    "data/research/spy_v89_six_new_families_2024_full_$priorLast",
    "data/research/spy_v90_six_new_families_2024_full_$priorLast")
  '2025_h2'=@(
    "data/research/spy_v89_six_new_families_2025_h2_$priorLast",
    "data/research/spy_v90_six_new_families_2025_h2_$priorLast")
  '2026_janapr'=@(
    "data/research/spy_v89_six_new_families_2026_janapr_$priorLast",
    "data/research/spy_v90_six_new_families_2026_janapr_$priorLast")
}
if (!(Test-Path $py)) { throw 'ATLAS Python virtual environment missing' }
if (!(Test-Path "$gate/preflight.json")) {
    throw 'Original SHA-verified V93 source preflight missing'
}
foreach ($p in @(
    "$source2020/entry_screen.json",
    "$source2020/exact_option_source_plan.json",
    "$source2020/source_receipts.json",
    "$source2020/source_events.jsonl",
    "$source2020/summary.json")) {
    if (!(Test-Path $p)) { throw "Original 2020 signed source evidence missing: $p" }
}
foreach ($pair in $old.Values) {
    foreach ($dir in $pair) {
        if (!(Test-Path "$dir/summary.json")) {
            throw "Previous immutable original source or replay directory missing: $dir"
        }
    }
}
if ((git status --porcelain --untracked-files=no | Measure-Object).Count -gt 0) {
    throw 'Tracked source tree is not clean; stop without provider requests'
}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$created=[System.Collections.Generic.List[string]]::new()
$new=@{}
try {
    Write-Host 'STAGE_START V95 source reconciliation and historical continuation compilations'
    & $py -m py_compile `
        scripts/run_spy_v95_2020_read_only_source_reconciliation.py `
        scripts/run_spy_v95_eight_complete_cohort_2020_censored_matrix.py `
        scripts/run_spy_v89_six_family_source_batch.py `
        scripts/run_spy_v90_six_family_source_replay.py
    if ($LASTEXITCODE -ne 0) { throw 'V95 compilation failed; no provider work' }

    Write-Host 'STAGE_START V95 synthetic no-provider source reconciliation and matrix regressions'
    $tmp=Join-Path $env:USERPROFILE (
        'at' + [guid]::NewGuid().ToString('N').Substring(0,8))
    & $py -m pytest -q --basetemp "$tmp" `
        tests/test_spy_v95_2020_read_only_source_reconciliation.py `
        tests/test_spy_v95_eight_complete_cohort_2020_censored_matrix.py `
        tests/test_spy_v93_frozen_2018_2023_preflight.py `
        tests/test_spy_v93_historical_spy_0dte_expiry_screen.py `
        tests/test_spy_v94_nine_cohort_original_source_matrix.py `
        tests/test_spy_v89_six_family_causal_registry.py `
        tests/test_spy_v89_six_family_source_batch.py `
        tests/test_spy_v90_six_family_capital_ledger.py `
        tests/test_spy_v84_offline_three_family_economics.py `
        tests/test_spy_v86_original_option_exit_recheck.py
    if ($LASTEXITCODE -ne 0) {
        throw 'V95 regression failure; no further historical provider acquisition'
    }

    $reconciliation="data/research/spy_v95_original_2020_read_only_reconciliation_$stamp"
    $created.Add($reconciliation)
    Write-Host 'STAGE_START V95 original signed 2020 May-01 source-forensics READ-ONLY'
    & $py -m scripts.run_spy_v95_2020_read_only_source_reconciliation `
        --original-2020-v89-dir $source2020 `
        --output-dir $reconciliation
    if ($LASTEXITCODE -ne 0) { throw 'Original 2020 SHA evidence reconciliation failed' }
    $forensic=Get-Content "$reconciliation/summary.json" -Raw | ConvertFrom-Json
    Write-Host "2020_FORENSIC requirements=$($forensic.original_source_requirements) original_complete=$($forensic.original_signed_complete_receipts) verified_new_cached=$($forensic.extra_original_source_requirements_read_only_archived) still_unknown=$($forensic.unresolved_2020_source_requirements)"
    Write-Host '2020 historical provider requests made by V95: 0'

    foreach ($year in @(2021,2022,2023)) {
        $key="$($year)_full"
        $src="data/research/spy_v95_v89_six_families_$($key)_$stamp"
        $sim="data/research/spy_v95_v90_six_families_$($key)_$stamp"
        $created.Add($src)
        $new[$key]=@($src,$sim)
        Write-Host "STAGE_START V95 original causal six-family stock/source year=$year"
        & $py -m scripts.run_spy_v89_six_family_source_batch `
            --start "$year-01-01" --end "$year-12-31" `
            --acquire-options --output-dir $src
        if ($LASTEXITCODE -ne 0) {
            throw "V95 $year original acquisition stopped; preserve ZIP and do not retry uncertain scope"
        }
        $v89=Get-Content "$src/summary.json" -Raw | ConvertFrom-Json
        Write-Host "V95_ORIGINAL_SOURCE year=$year cases=$($v89.considered_decisions) exact_sources=$($v89.exact_source_requirements) complete=$($v89.all_required_sources_archived)"
        if ($v89.all_required_sources_archived -ne $true -or
            $v89.source_resolution.status -ne 'ALL_REQUESTED_SOURCES_PRESENT') {
            throw "V95 source coverage incomplete in $year; do not simulate missing-option PnL"
        }
        $created.Add($sim)
        Write-Host "STAGE_START V95 24 source-linked original-exit scenarios year=$year"
        & $py -m scripts.run_spy_v90_six_family_source_replay `
            --v89-source-dir $src --output-dir $sim
        if ($LASTEXITCODE -ne 0) {
            throw "V95 $year original-source replay stopped; preserve original evidence"
        }
        $v90=Get-Content "$sim/summary.json" -Raw | ConvertFrom-Json
        if ($v90.portfolio_scenarios -ne 168 -or
            $v90.signed_quote_trial_journals -ne 24 * $v89.exact_source_requirements) {
            throw "V95 $year original outcome census drift"
        }
        Write-Host "V95_REPLAY_PASS year=$year journals=$($v90.signed_quote_trial_journals) ledgers=$($v90.portfolio_scenarios) censored=$($v90.portfolio_scenarios_with_unresolved_cash)"
    }

    # If 2020 is now fully cache-verifiable we still DO NOT rewrite its
    # earlier signed original V89 source records or silently re-run a GET.
    # That case needs a separate signed offline recovery overlay, not false
    # historical cash values in this eight-complete-cohort matrix.
    if ($forensic.unresolved_2020_source_requirements -eq 0) {
        Write-Host 'V95_2020_CACHE_ALL_VERIFIED: original source overlay needed; no nine-year PnL promoted'
        return
    }

    $matrix="data/research/spy_v95_eight_complete_regimes_2020_censored_matrix_$stamp"
    $created.Add($matrix)
    $args=@(
        '--v93-preflight-dir',$gate,
        '--v95-2020-reconciliation-dir',$reconciliation)
    foreach ($year in @(2018,2019,2021,2022,2023)) {
        $key="$($year)_full"
        $pair=if ($old.ContainsKey($key)) { $old[$key] } else { $new[$key] }
        $args+=@("--v89-$year-full",$pair[0],"--v90-$year-full",$pair[1])
    }
    $args+=@(
        '--v89-2024-full',$old['2024_full'][0],
        '--v90-2024-full',$old['2024_full'][1],
        '--v89-2025-h2',$old['2025_h2'][0],
        '--v90-2025-h2',$old['2025_h2'][1],
        '--v89-2026-janapr',$old['2026_janapr'][0],
        '--v90-2026-janapr',$old['2026_janapr'][1],
        '--output-dir',$matrix)
    Write-Host 'STAGE_START V95 eight complete historical regimes; 2020 PnL explicitly censored'
    & $py -m scripts.run_spy_v95_eight_complete_cohort_2020_censored_matrix @args
    if ($LASTEXITCODE -ne 0) {
        throw 'Eight-cohort SHA matrix failed; preserve all original evidence'
    }
    $report=Get-Content "$matrix/summary.json" -Raw | ConvertFrom-Json
    Write-Host 'COMPLETE V95 ORIGINAL SOURCE-HISTORICAL EXTENSION'
    Write-Host "Completed historical cohorts: $($report.distinct_historical_cohort_count)"
    Write-Host "Signed comparison rows: $($report.total_comparison_rows)"
    Write-Host "Fully comparable eight-cohort configurations: $($report.complete_eight_cohort_configurations)"
    Write-Host "Positive all eight original periods (diagnostic only): $($report.diagnostic_positive_in_all_eight_cohorts)"
    Write-Host "Original 2020 censored exact sources: $($report.PSObject.Properties['2020_missing_query_count'].Value)"
    Write-Host 'Historical broker orders: 0'
    Write-Host 'Protected May-Aug 2026 master holdout: UNTOUCHED'
}
finally {
    foreach ($dir in $created) {
        if (Test-Path $dir) {
            $zip="$dir.zip"
            if (!(Test-Path $zip)) {
                Compress-Archive -Path $dir -DestinationPath $zip -CompressionLevel Optimal
            }
            Write-Host "PRESERVED_V95_EVIDENCE_ZIP: $zip"
        }
    }
}
