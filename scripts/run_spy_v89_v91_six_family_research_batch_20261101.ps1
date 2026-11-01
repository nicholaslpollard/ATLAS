# ATLAS V89-V91 — 2024 / 2025 H2 / 2026 Jan-Apr; six new families.
# Source-only historical provider GETs permitted when original exact cache
# misses; broker orders are NEVER permitted. Three cohorts are fixed.
# Invoke ONLY from the repository's pinned research revision.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py = '.\.venv\Scripts\python.exe'
if (!(Test-Path $py)) { throw 'Local ATLAS Python virtualenv not found' }
if ((git status --porcelain --untracked-files=no | Measure-Object).Count -gt 0) {
    throw 'Tracked checkout files changed; stop before acquisition'
}

$cohorts = @(
    @{ Label='2024_full'; Start='2024-01-01'; End='2024-12-31' },
    @{ Label='2025_h2'; Start='2025-07-01'; End='2025-12-31' },
    @{ Label='2026_janapr'; Start='2026-01-01'; End='2026-04-30' }
)
$stamp = Get-Date -Format yyyyMMdd_HHmmss
$dirs = [System.Collections.Generic.List[string]]::new()
$sources = @{}
$replays = @{}
$matrix = $null
try {
    Write-Host 'STAGE_START V89-V91 original-source and executable regression compilation'
    & $py -m py_compile `
        packages/simulation/spy_v89_six_family_causal_registry.py `
        packages/simulation/spy_v90_six_family_capital_ledger.py `
        scripts/run_spy_v89_six_family_source_batch.py `
        scripts/run_spy_v90_six_family_source_replay.py `
        scripts/run_spy_v91_six_family_cross_period_evidence_matrix.py
    if ($LASTEXITCODE -ne 0) { throw 'Research code compilation failed; no source acquisition' }

    $tmp = Join-Path $env:USERPROFILE (
        'at' + [guid]::NewGuid().ToString('N').Substring(0,8)
    )
    Write-Host 'STAGE_START V89-V91 synthetic no-provider regression and existing execution tests'
    & $py -m pytest -q --basetemp "$tmp" `
        tests/test_spy_v89_six_family_causal_registry.py `
        tests/test_spy_v89_six_family_source_batch.py `
        tests/test_spy_v90_six_family_capital_ledger.py `
        tests/test_spy_v91_six_family_cross_period_evidence_matrix.py `
        tests/test_spy_v84_offline_three_family_economics.py `
        tests/test_spy_v85_shared_capital_quote_portfolios.py `
        tests/test_spy_v86_original_option_exit_recheck.py
    if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed; no historical source acquisition' }
    Write-Host 'PASS: regression tests; registered strategy rules and quote simulation code frozen'

    foreach ($c in $cohorts) {
        $label = $c.Label
        $source = "data/research/spy_v89_six_new_families_$($label)_$stamp"
        $replay = "data/research/spy_v90_six_new_families_$($label)_$stamp"
        $dirs.Add($source)
        $sources[$label] = $source

        Write-Host "STAGE_START V89 causal six-family stock screen + exact source acquisition $label"
        & $py -m scripts.run_spy_v89_six_family_source_batch `
            --start $c.Start --end $c.End `
            --acquire-options --output-dir $source
        if ($LASTEXITCODE -ne 0) {
            throw "V89 acquisition stopped for $label; preserve original event journal"
        }
        $pre = Get-Content "$source/summary.json" -Raw | ConvertFrom-Json
        Write-Host "SOURCE_CENSUS cohort=$label decisions=$($pre.considered_decisions) sources=$($pre.exact_source_requirements) fully_archived=$($pre.all_required_sources_archived)"
        if (!$pre.all_required_sources_archived -or $pre.source_resolution.status -ne 'ALL_REQUESTED_SOURCES_PRESENT') {
            throw "V89 source data incomplete for $label; stop before trading economics"
        }
        $dirs.Add($replay)
        $replays[$label] = $replay
        Write-Host "STAGE_START V90 original source-only 24-exit experiments and 168 signed capital ledgers $label"
        & $py -m scripts.run_spy_v90_six_family_source_replay `
            --v89-source-dir $source --output-dir $replay
        if ($LASTEXITCODE -ne 0) {
            throw "V90 offline quote replay stopped for $label; preserve partial trial journals"
        }
        $post = Get-Content "$replay/summary.json" -Raw | ConvertFrom-Json
        Write-Host "REPLAY_CENSUS cohort=$label signed_journals=$($post.signed_quote_trial_journals) account_scenarios=$($post.portfolio_scenarios) unresolved_account_scenarios=$($post.portfolio_scenarios_with_unresolved_cash)"
        if ($post.portfolio_scenarios -ne 168 -or
                $post.signed_quote_trial_journals -ne 24 * $pre.exact_source_requirements) {
            throw "V90 signed outcome census incomplete for $label"
        }
    }

    $matrix = "data/research/spy_v91_six_new_family_three_cohort_matrix_$stamp"
    $dirs.Add($matrix)
    Write-Host 'STAGE_START V91 504-row full-period causal option evidence matrix'
    & $py -m scripts.run_spy_v91_six_family_cross_period_evidence_matrix `
        --v89-2024 $sources['2024_full'] --v90-2024 $replays['2024_full'] `
        --v89-2025h2 $sources['2025_h2'] --v90-2025h2 $replays['2025_h2'] `
        --v89-2026janapr $sources['2026_janapr'] --v90-2026janapr $replays['2026_janapr'] `
        --output-dir $matrix
    if ($LASTEXITCODE -ne 0) { throw 'V91 evidence matrix stopped; retain all signed sources and ledgers' }

    $summary = Get-Content "$matrix/summary.json" -Raw | ConvertFrom-Json
    Write-Host 'ATLAS SIX-FAMILY MULTI-COHORT RESEARCH COMPLETE'
    Write-Host "Registered distinct hypotheses: $($summary.hypothesis_families.Count)"
    Write-Host "Total signed matrix rows: $($summary.total_comparison_rows)"
    Write-Host "Complete three-cohort configurations: $($summary.complete_three_cohort_configurations)"
    Write-Host "Positive across all three (exploratory only): $($summary.diagnostic_positive_in_all_three_cohorts)"
    Write-Host 'Broker orders: 0'
    Write-Host 'Protected May-Aug 2026 holdout: NOT TOUCHED'
}
finally {
    foreach ($d in $dirs) {
        if (Test-Path $d) {
            $zip = "$d.zip"
            if (!(Test-Path $zip)) {
                Compress-Archive -Path $d -DestinationPath $zip -CompressionLevel Optimal
            }
            Write-Host "PRESERVED_EVIDENCE_ZIP: $zip"
        }
    }
}
