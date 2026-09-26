# MarketData 2025 PIT Structural CALL Shortlist V1 — 2026-09-26

## Purpose and frozen scientific choice

Build a new, outcome-blind, offline structural CALL shortlist from the **already closed** 11-chain-plus-FSLY-gap pilot. This is actual next-stage candidate work, not a repeat closeout. The existing local source closeout fingerprint is `98b47179a2e563fb9d97ed16fec02d9a962f8f8788e88952f64c022f34a49daa`; plan fingerprint remains `a830ab16e6ebce9b509ec88efad8b6c8e08e2951db8682aa8d5e34ffc96886e1`. Original raw responses and prior manifests are preserved. No MarketData API calls or credits.

Precommitted structural ranking: among actually returned CALL rows at each **previous-session EOD** snapshot and exact frozen expiration/strike window, sort by absolute strike distance from the accepted **as-traded next-session stock OPEN known at the 09:35 ET decision**. Equal distance favors the OTM CALL (strike >= raw stock OPEN), then smaller strike and OCC symbol. This is ATM structural discovery, not an ex-post optimal option, trade selection or comparison of realized returns. Same-day option quote/last/volume, provider underlyingPrice and inTheMoney, Greeks, news, future stock outcomes and dynamic terminal option prices never inform ranking. For FSLY, preserve `EXACT_QUERY_NO_DATA` and abstain without widening the original query.

The private derived output includes every ranked observed CALL symbol and strike (no raw provider quote columns), provisional first structural symbol, PIT raw OPEN, exact request/receipt hashes, observed count, and a *planning-only* quote horizon. It never names that symbol a final executable contract and never treats a quote series as acquired. The potential quote horizon `from` is the local stock decision day and `to` is the day after expiration, exclusive; these date bounds are candidate acquisition scope only. A same-day 16:00 EOD quote could not have supplied a 09:35 fill.

## Adjusted deliverables and source limitations

An OCC-formatted symbol, returned chain row and the provider's default nonstandard filter do not independently prove a standard 100-share historical deliverable, contract multiplier or preserved corporate-action terms. MarketData's current chain documentation states that a missing `nonstandard` request parameter defaults false, but the frozen request omitted an explicit setting and does not include a complete adjusted-deliverable audit. Accordingly every provisional row has `standard_deliverable_independently_validated=false` and every opportunity remains `final_executable_option_contract_selected=false`. The independent historical identity/adjustment gate is next and can abstain on any ambiguous contract; no implicit standard-contract inference.

Source: https://www.marketdata.app/docs/api/options/chain/ (historical dates/fields and nonstandard filter); https://www.marketdata.app/docs/api/options/quotes/ (`to` is exclusive; historical Greeks null). Source semantics from `docs/research/marketdata_eod_semantics_synthesis_v1_20260925.md` and the immutable selected stock cohort take precedence.

## CLI and permission boundary

New `scripts/select_marketdata_candidate_2025_structural_calls_v1.py` reads the accepted local closeout manifest *once*, verifies its frozen fingerprint, opens the original immutable chain bodies strictly for new structural extraction and applies the fixed ranking. It does **not** rerun the source closeout experiment or touch the provider. Default is no-write preview; a single explicit `--write-local-shortlist` stores a deterministic, idempotent private metadata artifact under the D:-junction-visible `data/options/manifests` path. No raw private options response is committed to GitHub.

~~~powershell
.\.venv\Scripts\python.exe scripts\select_marketdata_candidate_2025_structural_calls_v1.py --write-local-shortlist
~~~

Expected cohort-level observation is eleven provisional symbols and one FSLY abstention if all eleven completed chains contain at least one CALL (source closeout recorded positive CALL counts for all eleven). That is NOT eleven executable contracts. The workstation artifact reports actual ranked symbols/strikes and a new fingerprint; GitHub tests use synthetic fixtures, not the private source. Stop on any mismatch rather than regenerate the pilot.

Next decision: freeze historical deliverable identity and contract availability using independent reference where possible, then budget selected-contract EOD quote series and model conservative next-available execution. No option fill/P&L, predictor/strategy evidence, PAPER, LIVE, broker/order, or promotion authority is granted.
