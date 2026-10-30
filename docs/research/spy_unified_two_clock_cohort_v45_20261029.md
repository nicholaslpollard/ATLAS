# V45 unified two-clock SPY source cohort — October 29, 2026

## Workstation V44 facts

Source report: `data/research/spy_v44_alternate_oi_20261029_212824.json`, SHA fingerprint `8dcd06e178fad25ebad6f88b9819dc2dc6479b5bc14fc1f57b694b01f271dbe5`. Uploaded full report independently inspected.

- V44 phase 1: **174/174** original OI-failing dates reviewed using **174 cache hits in 7 seconds**, **0 provider attempts, 0 errors**. Found **172** alternate 30–45 DTE call+put contracts with both OI >=100; **2** had no qualified alternate: 2021-01-04 and 2021-02-16.
- V44 phase 2: **688/688** requested original two-clock option quotes fetched and archived, no errors or explicit no-data (about 98 seconds). Each alternate has 09:59 predecision and 10:01 order-clock observations for call+put.
- **161** alternate pairs passed the two-clock quote/size/spread and OI requirements. **11** pairs failed one-second call/put timestamp skew: 8 failed the 09:59 pairing, 5 failed 10:01 (2 failed both). Do not loosen the skew threshold to chase trade counts.
- Year recovery counts: 2018=25, 2019=19, 2020=38, 2021=29, 2022=34, 2023=2, 2024=3, 2025=11.
- Original V43 had **178** source-quality-passing pairs, but its stored quote evidence was **10:01 only**. It does *not* prove the same original contracts had a valid 09:59 option quote for the 10:00 signal. Therefore **178+161=339 of 361** is a *maximum candidate cohort from different prior screens*, not yet a harmonized full two-clock qualified cohort.
- The V44 original source report includes two suspicious snapshots with equal call and put bid/ask prices despite distinct exact right source IDs: 2018-04-02 at 10:01 and 2021-06-21 at 09:59. These are diagnostic flags for source identity review; coincidence or provider reconstruction cannot be resolved from the report alone. Do not fabricate cause or identify them as fills.
- The 50 original weekly abstentions remain outside the selected 361; total 411 frozen weekly decision clocks.

## V45 implementation: last quote-coverage stage before PIT volatility

V45 is one combined workstation run:
1. Validate exact fingerprints of **original V43** and **alternate V44** reports and their mutual lineage; require the V44 count profile, unchanged frozen original identities, and disallow promoted trade outcomes.
2. For only the **178 original V43 source-quality-passing dates**, request the missing **two original options at 09:59**, 356 source uses total, through the same V39/V38 immutable dynamic cache. Previously archived exact sources are reused; missing ones are **automatically requested from ThetaData and archived**. Keep the V43 existing 10:01 quotes and decision-morning open interest; never rerequest or substitute a later 10:01 price for predecision.
3. Independently check exact right/expiration/strike, 09:59 call+put quote age <=30s, one-second pair skew, positive bid/ask/size, <=15% spread. Retain failures as unqualified original weeks.
4. Combine all **361 original selected dates** into mutually exclusive statuses: fully two-clock source-quality-passing ORIGINAL, fully two-clock source-quality-passing distinct ALT, or unqualified. The 50 original abstentions are not rewritten or represented as trades.
5. Preserve source SHA/query IDs, quote prices, OI, timestamps, original/alternate provenance and each quality reason. Separately flag equal call/put bid/ask snapshots on either clock without guessing the cause.
6. Print timestamped 10%-milestones of source acquisition. Save a SHA-fingerprinted JSON result. Preserve the original 411-week research cohort, no outcome data, no retroactive selection from entry/exit P&L.

V45 neither asserts independently proven historical quote publication nor computes real IV, strategy decisions, trades or P&L. The 09:59 underlying spot and old reconstructed 20-return retrospective variance also require **point-in-time feature provenance**. Next high-value integration is **PIT SOFR rate as of the decision, SPY discrete cash dividend publication/ex-date and OCC deliverable**, a correct 101-step American IV model with those actual inputs, and a causal trailing 20-return forecast before 10:00; then entry at 10:01, conditional exit-source acquisition, and true account-level replay.

## Single workstation command, after GitHub CI and merge

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }

    $v43 = 'data/research/spy_v43_quote_oi_quality_20261029_205927.json'
    $v44 = 'data/research/spy_v44_alternate_oi_20261029_212824.json'
    foreach ($p in @($v43, $v44)) {
        if (-not (Test-Path $p)) { throw "Required historical report missing: $p" }
    }

    $output = "data/research/spy_v45_two_clock_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    & '.\.venv\Scripts\python.exe' -m scripts.run_spy_unified_two_clock_cohort_v45 `
        --v43 $v43 `
        --v44 $v44 `
        --output $output

    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Some exact sources remain unresolved; successful archives are preserved.'
    }
    if (Test-Path $output) { Write-Host "V45 report saved: $output" -ForegroundColor Green }
}
```

The 356 source uses are **not a limit on future changed-strategy requirements**; they are the exact missing original 09:59 source scope for this frozen 178-case source-quality cohort. Further strategy changes can request additional provider sources automatically.
