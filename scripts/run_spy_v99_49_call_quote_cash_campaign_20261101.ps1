# V99 full offline 49 CALL entries x 24 V84/V86 execution-risk cases.
# Original V97B/V98 signed source roots; zero provider GET or broker orders.
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py='.\.venv\Scripts\python.exe'
if (!(Test-Path $py)) { throw 'ATLAS virtualenv Python missing' }
if ((git status --porcelain --untracked-files=no | Measure-Object).Count -gt 0) {
    throw 'Tracked repository files changed. Review before V99.'
}
$stage97=@(Get-ChildItem 'data/research' -Directory -Filter 'spy_v97b_49_variant_call_only_source_union_*' |
    Where-Object {
        (Test-Path (Join-Path $_.FullName 'summary.json')) -and
        (Test-Path (Join-Path $_.FullName 'call_only_candidate_source_coverage.json'))
    })
$stage98=@(Get-ChildItem 'data/research' -Directory -Filter 'spy_v98_safe_call_source_acquisition_*' |
    Where-Object {
        (Test-Path (Join-Path $_.FullName 'summary.json')) -and
        (Test-Path (Join-Path $_.FullName 'acquisition_results.json')) -and
        (Test-Path (Join-Path $_.FullName 'source_events.jsonl'))
    })
if ($stage97.Count -ne 1 -or $stage98.Count -ne 1) {
    throw "Expected exactly one original V97B and V98 stage folder. V97B=$($stage97.Count) V98=$($stage98.Count)"
}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$out="data/research/spy_v99_49_call_quote_cash_campaign_$stamp"
try {
    Write-Host 'STAGE_START V99 quote-cash source-linked module compilation'
    & $py -m py_compile scripts/run_spy_v99_49_call_variant_quote_economics.py
    if ($LASTEXITCODE -ne 0) { throw 'V99 compilation failed' }

    Write-Host 'STAGE_START V99 signed source/quote/capital regression tests'
    $tmp=Join-Path $env:USERPROFILE ('at'+[guid]::NewGuid().ToString('N').Substring(0,8))
    $tests=@(
        'tests/test_spy_v99_49_call_variant_quote_economics.py',
        'tests/test_spy_v98_historical_call_union_safe_acquisition.py',
        'tests/test_spy_v97b_49_variant_call_source_union_preview.py',
        'tests/test_spy_v97a_call_only_original_source_capability.py',
        'tests/test_spy_v89_six_family_source_batch.py',
        'tests/test_spy_v90_six_family_capital_ledger.py',
        'tests/test_options_on_demand_source_cache_v38.py',
        'tests/test_strategy_options_source_runtime_v39.py'
    )
    & $py -m py_compile @tests
    if ($LASTEXITCODE -ne 0) {
        throw 'V99 regression module syntax verification failed; no replay started'
    }
    & $py -m pytest -q --basetemp $tmp @tests
    if ($LASTEXITCODE -ne 0) {
        throw 'V99 regressions failed. No new quote-cash simulation started.'
    }

    Write-Host 'STAGE_START V99 original 1s CALL quote tapes, 49 entry thresholds x 24 exit scenarios'
    Write-Host 'V99 provider GET=0, broker orders=0, May-2020 uncertainty and Jan-2022 NO_DATA censored'
    & $py -m scripts.run_spy_v99_49_call_variant_quote_economics --v97b-dir $stage97[0].FullName --v98-dir $stage98[0].FullName --output-dir $out
    if ($LASTEXITCODE -ne 0) {
        throw 'V99 original quote/account run stopped. Preserve signed partial output; no PnL inference from it.'
    }
    $summary=Get-Content "$out/summary.json" -Raw | ConvertFrom-Json
    Write-Host "COMPLETE V99 historical cohorts=$(@($summary.cohorts).Count)"
    Write-Host "V99 source-family trial journals=$($summary.signed_source_family_quote_journals)"
    Write-Host "V99 signed capital-account scenarios=$($summary.total_standalone_and_combined_capital_scenarios)"
    Write-Host "V99 original qualified CALL scopes=$($summary.source_qualified_distinct_call_tapes)"
    Write-Host 'V99 news feature join NOT YET RUN; historical quote PnL NOT live broker fills'
}
finally {
    if (Test-Path $out) {
        # All detailed gzip 1s source-family quote journals stay on local disk.
        # Upload only signed summary, manifest and EVERY per-cohort cash ledger.
        $files=@(Get-ChildItem $out -File |
                 Where-Object { $_.Name -like '*.json' } |
                 Sort-Object Name |
                 Select-Object -ExpandProperty FullName)
        if ($files.Count -gt 0) {
            $zip="$($out)_summary_evidence.zip"
            if (!(Test-Path $zip)) {
                Compress-Archive -Path $files -DestinationPath $zip -CompressionLevel Optimal
            }
            Write-Host "PRESERVED_V99_ALL_CAPITAL_AND_SUMMARY_EVIDENCE_ZIP: $zip"
            Write-Host "PRESERVED_V99_ORIGINAL_SOURCE_JOURNALS_LOCAL: $out/journals"
        }
    }
}
