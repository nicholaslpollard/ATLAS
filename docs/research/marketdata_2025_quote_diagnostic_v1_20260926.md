# 2025 Selected CALL EOD Quote Offline Diagnostic V1 — 2026-09-26

## Accepted new operator evidence and why this is a different stage

Selected exact quote source acquisition completed without quarantine: eleven HTTP 203 series, eleven unique contracts, zero gaps/pending, 320 EOD rows including 190 positive-volume and 130 zero-volume observations, eleven observed credits, last reported remaining 9,978. Frozen selected quote plan b15feb274a00e911a233572856254c5b1bc77b5a8930832b94d76659a16d6589 and operator result 5912e0a4b9467a7dacf35044cfa4bc10791735e3ace3e7b50fa2ad3f38c743ea. No provider requests are required to inspect this already retained cohort.

The purpose of the new offline read-only diagnostic is a compact descriptive census of each original SHA-bound exact quote body/receipt/attempt, retaining PIT time separation, rather than repeating a paid source qualification or testing a post-selected strategy. It rebuilds the original frozen plan from the accepted shortlist and eleven historical reference receipts, binds the local saved quote plan and each of the eleven original quotes, and cross-checks exact source counts and credit reports. It creates at most one new immutable D:-bound local diagnostic under data/options/manifests. Existing raw provider bytes and original receipts are untouched. All metrics use original local raw bytes only, with zero provider/network calls.

## Original source coverage

| Underlying | EOD rows | Positive-volume rows | Zero-volume rows |
|---|---:|---:|---:|
| AGIO | 36 | 22 | 14 |
| AMGN | 31 | 31 | 0 |
| ATRC | 26 | 0 | 26 |
| BANF | 32 | 0 | 32 |
| DAKT | 38 | 3 | 35 |
| ISRG | 27 | 25 | 2 |
| LNT | 26 | 20 | 6 |
| OLLI | 21 | 17 | 4 |
| SRRK | 27 | 16 | 11 |
| TEM | 22 | 22 | 0 |
| TSLA | 34 | 34 | 0 |
| **Total** | **320** | **190** | **130** |

All-zero-volume ATRC and BANF cannot supply an observed same-session trade price from their positive historical last fields even if a two-sided EOD bid/ask field exists. A positive-volume row signals some same-session activity in provider EOD data, not a 09:35 or later executable option fill. OI remains D-1-settled; the EOD quote/last/underlying fields at D close cannot be used at D 09:35. Missing observed sessions are source coverage gaps, not independently proven zero activity. The new dossier records per-contract first positive-volume session, first later-than-original-decision-session positive-volume session, same-day EOD lookahead counts, EOD bid/ask geometric counts, and zero-volume positive-last rows as descriptive observations only. It does not infer a fill, option spread cost, return, or tradable asset from them.

## One workstation gate

After merged GitHub CI, execute one no-provider-read command that reads the private original evidence once and writes a new idempotent local report:

    .\.venv\Scripts\python.exe scripts\run_marketdata_candidate_2025_quote_diagnostic_v1.py --write-local-dossier

Output includes the new dossier fingerprint, per-underlying session/activity/geometry classification, aggregate and unchanged authority. Do not rerun the eleven paid MarketData series or Massive reference requests. The next science gate is a separately frozen corporate-action/deliverable policy and execution timing/cost *feasibility* assessment, not implied approval from source coverage. Existing stock DEVELOPMENT/holdout, news PIT and source retention restrictions remain unchanged.

**Authority:** DEVELOPMENT source-only. No historical deliverable certification, same-session trade price from zero volume, timestamped intraday option entry, executable bid/ask, option P&L, PAPER, LIVE, strategy promotion, broker or order rights.
