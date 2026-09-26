# 2025 Selected CALL Historical EOD Quote Source V1 — 2026-09-26

## Distinct stage after the completed reference gate

Operator-reported reference acquisition completed 11/11 exact historical Massive GETs as HTTP 200 with structurally consistent 100-share, American and NOT_REPORTED additional-underlying fields. Frozen prior reference plan: 261812136e0ce8d947aece094ba60a45e69429db0093072e21f7457420361fd4. Accepted operator report: 773358a1afe429191671da5077ce98e1a03e6b991d3c5404c2297fd3bcb97ae9. No more Massive acquisition or prior source-pilot verification is needed.

The new source-only adapter consumes the accepted structural shortlist fingerprint e5a8347fa346934d908d925b9fdbf667d7a458d010bf51ce8e27324fbbc01268 and reuses original reference receipts as immutable lineage. Eleven actual CALL symbols are bound, FSLY is excluded. The original 09:35 ET raw-stock-opening decision, prior-session snapshot, as-traded symbol and shortlist quote horizon from decision date through expiration plus one day exclusive remain fixed. It does not rerank the contract from later price, Greeks, liquidity or outcome.

## Acquisition and preservation

One exact MarketData historical option quote-series GET per unique selected contract, maximum 11 NEW calls per authorized run. No broad option-universe download or automatic retries. A complete quote response is limited to 4 MiB and 500 observed rows, with exact symbol, date-range, schema, timestamp and nonnegative numeric checks. Historical EOD quote data is observations only, not a fill. Zero-volume last is not an executable price; historical OI is settled D-1, and bid/ask/last/underlyingPrice are EOD D. An exact 404 with s=no_data is a narrow exact-query source gap, not proof of absence of the contract; other errors quarantine. A durable exclusive intent precedes every GET, with exact raw body and SHA-bound receipt retained; partial/orphan evidence blocks re-request. No secrets or private raw provider responses are committed.

Before each call, enforce the existing research-storage quota with worst-case 4 MiB response reservation and the D: external binding. Check actual provider credit headers, stop further calls below 200 remaining or at 25 observed consumed in this run. Billing is per 1,000 returned historic quote rows and cannot be inferred from HTTP count. Active paid Starter access and private permitted workstation/IP are required. Subscription data must be deleted upon subscription termination unless written rights specify otherwise.

## Operator gate

One command performs local input binding, deterministic new quote plan, receipt reuse and authorized acquisition:

    .\.venv\Scripts\python.exe scripts\run_marketdata_candidate_2025_selected_quotes_v1.py --authorize-provider-reads --confirm-paid-starter --confirm-private-internal-use --max-new-requests 11

Default no flags means zero-provider-read preview, no new plan file. Authorized run creates only the new D:-bound plan, requests untouched quote series and prints per-contract safe row and credit status directly. Stop and preserve complete output on quarantine or uncertain transport; never blindly repeat.

## Authority boundary

All source outputs remain DEVELOPMENT source-only. No independent historical corporate-action deliverable resolution, executable bid/ask, intraday fill, option P&L, strategy promotion, PAPER, LIVE or broker authority follows from these historical EOD quote rows. Separately freeze EOD timing/cost assumptions and deliverable policy before option economics. Original 2025 source pilot, closeout, shortlist, reference evidence, and negative strategy evidence remain unchanged.

Source: https://www.marketdata.app/docs/api/options/quotes/ ; https://www.marketdata.app/terms/ ; docs/research/marketdata_eod_semantics_synthesis_v1_20260925.md.
