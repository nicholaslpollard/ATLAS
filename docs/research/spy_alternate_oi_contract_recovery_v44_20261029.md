# V44 — Recover alternate SPY options from predecision open-interest surfaces

## Baseline: actual workstation V43 finished successfully on Oct 29, 2026

Full user report: `data/research/spy_v43_quote_oi_quality_20261029_205927.json` (SHA fingerprint `d974e1510717b20a69fe4cb26121bf03be55f7ea4016dcdd49c166b8c59feecc`).

- 1,083/1,083 exact provider source requirements reused from V40 cache in 34 seconds; **0 new provider requests, 0 failed/no-data sources**.
- Of 361 frozen first-selected SPY call/put pairs, **178** passed contemporaneous-source microstructure + original-call/put OI and **183** did not.
- **174** distinct original pairs had an OI source/threshold failure; **17** quote pairs exceeded a 1-second call/put source time skew (overlapping categories). The individual leg bid/ask freshness, spreads, sizes passed in all 361 cases.
- OI-specific failure cases: put OI <100 in **132**, call OI <100 in **117** (overlapping), morning-report time issue both rights in **6**, and exact contract not unique/missing both rights in **5**. Four dates had no exact matching OI on at least one leg, one had a duplicate. No claim that each OI result was independently proven published at its timestamp.
- Strong year differences (passed/total): 2018 20/50; 2019 17/44; 2020 6/44; 2021 8/41; 2022 13/48; 2023 46/49; 2024 43/48; 2025 25/37. Do not infer alpha or adjust strategy performance from this source-quality trend.

## V44: new source-only research strategy variant

**Goal:** keep the frozen original V37/V43 results immutable while adding a *new* strategy-version candidate selector based on historical decision-morning open interest and the previously observed 09:59 SPY physical spot.

Phase 1 revisits only the **174 OI-unqualified original dates** and reads their original archived decision-morning OI surfaces through the V39/V38 immutable read-through cache. The code selects a different contract with:
- SPY underlying, dual original right records, integer **call OI>=100 and put OI>=100**, each timestamped on the decision date no later than **10:00 ET**.
- **30–45 DTE**, not the current or original contract if it failed liquidity. Rank the candidate strike **nearest the original 09:59 SPY spot**, prefer original expiration on equal proximity, then closer original DTE and greater weaker-side OI. Sort deterministically; do not inspect 10:01 quote or any post-entry P&L when selecting.
- If none is available, report **NO_ALTERNATE** without inventing data or relaxing minimum OI. If one is available, emit a new independent candidate identity; do not modify the original's trade identity or results.

Phase 2 automatically makes and persists exactly the source demands for **both rights at 09:59** (pre-10:00 option quote) and **both rights at 10:01** (post-decision, hypothetical order observation). These are independent source identities, with cache-first reuse. No artificial call limit is imposed. Required provider calls are dynamically determined by actual candidates and cache state. The 09:59 original timestamp must be no later than 09:59 and within 30 seconds; 10:01 source checks use V43's 30-second age, positive bid/ask/size and <=15% spread rules. Each call/put pair source timestamps must be within 1 second for that clock.

V44 prints user-requested timestamped milestones at 10% completed *per phase*, with completed/total, actual cache/provider/error counts and observed throughput. The run saves a narrow JSON report with every recovered contract's source identities and reasons if unable to qualify. Original compressed OI surfaces remain in V38; no duplicate full OI archive is written.

**Important causal distinction:** This is a changed-strategy *source-quality selection*, not real trade authorization, verified PIT OPRA distribution, an American IV solution, a live broker fill or out-of-sample P&L. The 10:01 quote is never used for the 10:00 entry signal. The 09:59 quote allows a pre-decision IV calculation only after historically published SOFR, dividend/corporate actions, OCC deliverable, source provenance and exact American 101-step IV gates are validated.

A successful alternate still requires full entry/exit source-qualified historical simulation. The large OI gap in 2018–2022 is measured evidence, not a reason to reduce the OI threshold below 100.

## Run on workstation after CI and GitHub merge

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\\Users\\cyberdyne\\Desktop\\ATLAS'
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
    $v43 = 'data/research/spy_v43_quote_oi_quality_20261029_205927.json'
    if (-not (Test-Path $v43)) { throw "Missing V43 input: $v43" }
    $report = "data/research/spy_v44_alternate_oi_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    & '.\\.venv\\Scripts\\python.exe' -m scripts.run_spy_alternate_oi_contract_recovery_v44 `
       --v43 $v43 `
       --output $report
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Unresolved sources; completed original and alternate archives remain persisted' }
    if (Test-Path $report) { Write-Host "V44 report: $report" -ForegroundColor Green }
}
```

This run can incur newly required ThetaData calls for **changed-strategy** selected contracts. It must not be presented as guaranteed read-only or as a promise of a fixed number of GETs. Source receipts persist and are replay-safe. Next: integrate historical PIT rate/issuer dividend/discrete exercise and 101-step IV with the 09:59 pre-decision quote, then conditionally request dynamic exit sources for genuinely qualifying candidates and evaluate realized option strategy P&L with weekly/monthly/annual held-out windows.
