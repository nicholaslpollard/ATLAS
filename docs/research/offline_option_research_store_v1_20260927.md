# Offline 2022 accepted CALL EOD read adapter V1 — 2026-09-27

## Purpose and authority

Start the reusable local source layer for the integrated stock/news/options strategy laboratory. This is **source retrieval only**, not a simulation, claim of historic executability, 09:35 option pricing, actual cash P&L or strategy qualification.

`packages/data/offline_option_history_v1.py` indexes the already frozen 2022 broad CALL quote plan by exact OCC symbol. It uses only the existing `AtlasSettings` D:-bound `data/options` namespace and original on-disk receipts/bodies. It has **no API transport, no provider fallback, no paid requests, no writes, and no alternate-strike selection**. Initializing verifies the complete accepted plan identity and its 6,398 unique source keys; requesting a particular symbol reuses the preexisting exact-quote integrity verification and checks original body SHA before decoding. It does **not** perform another full 6,398-body audit.

`inspect_retrospective_history(symbol)` explicitly returns complete *retrospective* EOD observations. It is not a feature feed; same-day and later rows may be included. `predecision_history(symbol, decision_utc=...)` requires an aware timestamp and excludes all EOD source rows for the decision's ET session and later, as well as original provider `updated` timestamps later than the cutoff. This is a conservative chronology filter, **not proof that the provider originally published every remaining row by that time**. A timestamp, two-sided quote or positive reported volume is not a proven executable fill or historical deliverable. Rows retain exact per-share bid/ask and observed timestamp, without multiplier assumptions or imputed absent observations.

Missing, altered or mismatched source evidence fails closed. A 2022 CALL outside the frozen original plan is unavailable; this adapter never silently chooses another option. The next independent year/PUT/expiry sources will each require their own accepted, fingerprint-bound index rather than treating a 2022 CALL source as all-options coverage.

## Zero-credit local inspection

After the PR is green and merged, run on a *correctly bound* workstation:

```powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\.venv\Scripts\python.exe scripts\inspect_offline_option_history_v1.py; if ($LASTEXITCODE -ne 0) { throw 'Offline options library inspection stopped; do not acquire or retry sources.' } }
```

The output prints both the project-relative C: alias and real D: external root, accepted plan fingerprint, and indexed source count. It does not query the provider or reread all 6,398 quote bodies. For one exact symbol, pass `--symbol <EXACT_OCC_SYMBOL>`; add `--decision-utc <AWARE_ISO8601>` for the conservative predecision view.

## Simulator handoff

1. Complete the already authored zero-credit rank-zero later-EOD reference on the workstation. It is a descriptive pair of strictly later source references and **not** the original 09:35 trade.
2. Bind local stock opportunities to this source adapter and to separately verified historical news through a common, explicitly chosen simulation clock. Keep stock, option and abstain outcomes on the *same decision and entry schedule*, with missing-source cases in the denominator. Do not retune against already consumed protected labels.
3. Introduce documented option contract/deliverable, fee, spread, expiration and mark/exit evidence before capital/account P&L. Report per-share descriptive EOD references separately from fill-derived returns.
4. Expand accepted year/expiry/PUT cohorts through the existing resumable acquisition mechanism only when missing coverage demands it and with explicit credits/concurrency bounds. Do not start another acquisition from this adapter.

The downloaded dataset is offline-usable under applicable active-license terms; a local cache does not confer indefinite post-cancellation retention rights.
