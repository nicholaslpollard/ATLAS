# V37 — Frozen SPY pre-trade feature bridge and next-source demand

## Objective

Move directly from V36 quote-based account stress to the **actual pre-trade volatility decision**. Preserve all 411 original first-session weekly clocks, the 361 V29 provisional SPY ATM option pair identities, and 50 original abstentions. Before making another paid ThetaData call, reuse the accepted V29 original spot/option plan, the already-recovered V32 original/exact quote tape and the existing full-period **retrospective** 20-return volatility report.

V36 completed on Oct 28, 2026 with report SHA `31e1ff2d7f1c6bb6ca7770e4c3c81778e49e5f5e0bfacfef89f6076518db5a0b` from `data/research/spy_v36_expiry_stress_20261028_181013.json`. All 40 zero-expiry stress outcomes were negative: **−88.9957% to −53.0843%**. Among pilot-capacity one-slot, one-contract-pair, 5%-available-cash scenarios, the least-negative was hold=2, fee=$0.65 per leg/side and zero extra slippage: **254 hypothetical entries, 227 matched-quote closes, 27 zero-credit expiry assumptions, $46,915.70 terminal hypothetical cash** from $100,000. This result **does not test the real volatility signal**. Zero expiry cash proceeds is **an unobserved pessimistic assumption**, not the actual settlement of a long straddle and not verified P&L.

## V37 evidence packet

The new V37 CLI validates the original V29 plan's one-stage fingerprint, the V32 quote-tape fingerprint including its historical nested SHA, and reconstructs the already programmed 411-window retrospective variance grid from **four pinned existing local research JSON files** (no new raw-bar scans or requests). It produces one exact-original pair-bound row for each of the **361** V29 selected entry dates, including:

- SPY physically observed historical 09:59 spot and source reference; no fabricated availability-time claim
- Original selected expiration, strike, source query fingerprint and two-leg 10:00 historical ask reference from V32; no claim of fill
- Annualized raw-close and retrospective dividend-conditioned variance's **volatility** (where the 20 prior returns are physically available). The grid has 407/411 price-complete windows, with known August–September 2019 gaps; V37 measures their actual intersection with the 361 selected pair dates.
- Explicit unfilled fields for *American-model call and put IV*, prior-session OI, PIT rate and dividend inputs, independently time-qualified stock/option sources, original deliverable, and 10:01 execution/exit/mark evidence. V37 **never** guesses these or substitutes entry premium for IV.
- A full selected-date/year source-to-feature work queue for the next integrated local and provider acquisition stage, without querying the provider in V37.

The retrospective dividend series was compiled later and is NOT a contemporaneously published historical signal. Even when the price-level evidence is complete, V37 reports **zero qualified true historical entry decisions, zero fills, zero simulations and zero claim of historical alpha**.

## Operator run after CI and merge

Use the existing **V29 and V32 JSON source reports** on your workstation. No big file upload or new ThetaData call is needed. Run this once and upload the resulting small V37 JSON report so that the next changes can target full-batch 361-pair actual decision inputs and start the real strategy signal.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }

    $py = '.\.venv\Scripts\python.exe'
    $output = "data/research/spy_v37_pretrade_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"

    & $py -m scripts.run_options_native_spy_pretrade_feature_bridge_v37 `
        --tape data/research/spy_quote_tape_post_v33_20261028_155608.json `
        --plan data/research/spy_one_pair_exact_exit_demand_v29.json `
        --expect-fingerprint a0bfbd1ae8db9d3b502ee21780db17a23d37d5284655611167078c5a870c365e `
        --output $output

    if ($LASTEXITCODE -ne 0) { throw 'V37 offline pretrade bridge failed' }
    Write-Host "V37 source packet: $output"
}
```

## After V37

The high-impact follow-on is **one consolidated acquisition + historical feature adapter**, not additional one-record canaries. Use the 361 dated exact identities and existing original source archives to source missing call/put OI, PIT rates/dividends and American-consistent IV, then qualify source availability at the 10:00 decision / 10:01 order clock and calculate the fixed signed variance signal (the 20-return realized variance-rate forecast exceeds average call/put implied variance). A source-unqualified decision abstains. Only then feed actual signal-selected entries, dynamic exits and qualified executed/marked positions into a chronological account simulator; keep missing exits visible. No 2026 protected-outcome reuse.

This work is the shortest scientific path from historical quotes to an ATLAS **actual pilot signal**. V37 itself is a source-binding stage, not a simulation or a performance result.
