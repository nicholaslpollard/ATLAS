# V68 — SPY original-source latency and adverse-ask sensitivity

## Evidence and fixed cohort
The immutable [V67 completed joint run](v67_unskipped_source_demands_and_june_cohort_joint_run_20261031.md) proved 6/6 exact selected option quote tapes from June 9–20, 2025 archived and verified, with 33/33 targeted workstation tests. New V66 source reads archived June 16 (20,880 rows), June 18 (20,520) and June 20 (21,120). The original unchanged V65 re-audit has ten weekdays: four weekday-filter exclusions, three entry rejects due to >1% price drift at one second, two closed reference trades, and June 13 still unqualified after an original quote spread >15%.

| Session | Original quote-reference outcome | Causal observation at order to action |
|---|---|---|
| June 9 | $-189.20 closed | no adverse ask move, 1.18 → 1.18 |
| June 11 | NO_ENTRY | 1.31 → 1.35, **+3.0534%** |
| June 13 | UNRESOLVED_POSITION | entry 1.72, rejected exit at 10:00:01; do not impute a close |
| June 16 | **+$410.80** closed at +100% quote take-profit | entry ask 1.04, exit bid 2.08, 4 contracts, fees included |
| June 18 | NO_ENTRY | 1.60 → 1.62, **+1.25%** |
| June 20 | NO_ENTRY | 1.32 → 1.34, **+1.5152%** |

Total **+$221.60 across only the two resolved independent $25k reference-trade replays** is NOT a valid cumulative portfolio return, because June 13 is unresolved and none of the quote executions is a broker fill or first-publication-clock validated.

## Purpose and scope
V55 already accepts exactly six distinct simulated execution policies: delay **1 or 3 seconds**, combined with maximum adverse ask drift **0.5%, 1%, or 2%**. V68 tests all six without modifying V55's frozen signal, expiration, strike, quote qualification, premium cap, 100% TP, -50% SL, 15:30 exit or per-side fees. **This is a post-hoc in-sample sensitivity exercise, not trading optimization or an out-of-sample win.** All six scenarios reuse *only original V38 SHA-verified local quotes*. No new source scope is needed; provider requests must equal zero. If any of the six required sources has disappeared or fails verification, the program explicitly refuses the run with `V68_SOURCE_ACQUISITION_REQUIRED_OR_SHA_INVALID` instead of counting a no-trade, silently changing to another provider or retransmitting an uncertain query. Separate V39/V68 source acquisition planning must resolve that requirement first.

The script checks the full SHA-signature of the original V67 summary and original refreshed V65 report, all ten per-day signed original reports, every exact query ID and archive SHA. It replays ten days for six policies (60 session evaluations). The **original 1-second/1-percent result must reproduce every original per-day replay fingerprint exactly**, otherwise abort. It saves every scenario's original per-quote `EXIT_REVIEW`, `EXIT_SOURCE_REJECTION`, decision/no-trade reason, timing, premium, fees, cash balance and quote-reference event sequence in independently SHA-manifested compressed JSON. The summary provides counts by outcome/rejection and resolved standalone trade P&L, explicitly not cumulative profitability. A separate file is written per policy, original reports are never modified or replaced, and the output folder is immutable.

## One-call Windows workstation command (read-only original archives)
Run **once** after the branch/PR has passed CI and is merged, with the V67 output present at the exact folder indicated. A new source requirement elsewhere must still be fetched by the provider-aware runtime; this offline what-if does not authorize ignoring future data.

```powershell
Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
$py = '.\.venv\Scripts\python.exe'
& $py -m pytest -q --basetemp (Join-Path $env:USERPROFILE ('at' + [guid]::NewGuid().ToString('N').Substring(0,4))) tests/test_spy_v68_original_source_execution_sensitivity.py tests/test_spy_v67_acquire_then_offline_reaudit.py tests/test_strategy_options_source_runtime_v39.py
if ($LASTEXITCODE -ne 0) { throw 'V68 regression failure; source archive unchanged' }
$stamp = Get-Date -Format yyyyMMdd_HHmmss
& $py -m scripts.run_spy_v68_original_source_execution_sensitivity `
 --v67-summary 'data/research/spy_v67_joint_20261031_130037/summary.json' `
 --refreshed-v65 'data/research/spy_v67_joint_20261031_130037/refreshed_v65.json' `
 --output-dir "data/research/spy_v68_execution_matrix_$stamp"
if ($LASTEXITCODE -ne 0) { throw 'V68 blocked; retain original sources and inspect reason' }
```

## After result
Review original and alternate outcomes in parallel, particularly June 18/20 at 2%, June 11 even above 2%, and June 13's unresolved exit. Do not choose a winning policy by these six historical sessions. Pre-register a candidate policy using prior training periods, then evaluate separate unseen historical folds, source-acquiring any missing quote/OI/Greek/spot/volatility inputs through the full source runtime. A one-session quote profit cannot establish weekly, monthly or annual alpha. No broker orders are placed.
