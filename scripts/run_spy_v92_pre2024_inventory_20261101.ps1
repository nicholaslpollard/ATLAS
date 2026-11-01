# V92: no ThetaData, no broker, no option tape access. Only locally held
# pre-2024 SPY original minute SHA checks. Preserves immutable signed evidence.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py = '.\.venv\Scripts\python.exe'
if (!(Test-Path $py)) { throw 'ATLAS Python virtual environment is missing' }
if ((git status --porcelain --untracked-files=no | Measure-Object).Count -gt 0) {
    throw 'Tracked repository changes require review'
}
$out = $null
try {
    Write-Host 'STAGE_START V92 standalone original stock source inventory compilation'
    & $py -m py_compile scripts/run_spy_v92_pre2024_original_minute_coverage.py
    if ($LASTEXITCODE -ne 0) { throw 'V92 compilation failed' }
    $tmp = Join-Path $env:USERPROFILE (
        'at' + [guid]::NewGuid().ToString('N').Substring(0,8)
    )
    & $py -m pytest -q --basetemp "$tmp" `
        tests/test_spy_v92_pre2024_original_minute_coverage.py
    if ($LASTEXITCODE -ne 0) { throw 'V92 synthetic no-provider tests failed' }

    $stamp = Get-Date -Format yyyyMMdd_HHmmss
    $out = "data/research/spy_v92_pre2024_original_stock_inventory_$stamp"
    Write-Host 'STAGE_START V92 inspect 2018–2023 original SPY monthly 1-minute sources'
    & $py -m scripts.run_spy_v92_pre2024_original_minute_coverage `
        --start-year 2018 --end-year 2023 --output-dir $out
    if ($LASTEXITCODE -ne 0) { throw 'V92 original source inventory stopped' }
    $summary = Get-Content "$out/summary.json" -Raw | ConvertFrom-Json
    Write-Host "V92 COMPLETE: SHA-verified SPY months=$($summary.available_original_spy_months_full_sha_verified)/$($summary.months_examined)"
    Write-Host 'Provider calls: 0'
    Write-Host 'Broker orders: 0'
}
finally {
    if ($out -and (Test-Path $out)) {
        Compress-Archive -Path $out -DestinationPath "$out.zip" `
            -CompressionLevel Optimal
        Write-Host "PRESERVED_V92_EVIDENCE_ZIP: $out.zip"
    }
}
