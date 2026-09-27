# Integrated 2022 stock + news + CALL source casebook V1 — 2026-09-27

## Accepted user-observed input, no reacquisition

The workstation produced and accepted the zero-provider local reference on D:, not a pending source-gate: frozen 2022 quote plan 017805741349c5bd93eead00123282cee8a3980fcf9d3c368147b0ed4bbe6786, 6,398 indexed exact CALL histories, structural rank-zero 2,643 representatives/2,227 original selected histories. The derived immutable reference fingerprint is 15901045e456335638714e1f0259f5dc5ada519a168801f3676eb8582a3e7598. Its original observed first-later ask → next-later bid price-change median is −0.322751 **among the 2,629 opportunities with both reference dates**; five have no later two-sided row, nine have only the first row. 1,298 have reported positive entry-reference volume and 1,281 have reported positive next-reference volume. These source references are neither executable trades, 09:35 quotes, adjusted contract P&L nor stock-versus-option strategy returns. D: free was 225.58 GiB after the local build.

## New independent step

\`scripts/build_integrated_2022_casebook_v1.py\` is a bounded, entirely local join that combines:

- the exact new SHA/fingerprint-bound immutable 2022 later-EOD source reference on D:, preserving **all 2,643 original structural representative memberships** and all unavailable statuses;
- only the previously accepted original 71 **DEVELOPMENT** stock source-shard bindings, including original timestamp and raw stock open as identity/context, never an invented matched later-session stock fill, protected outcomes, or a new candidate selection;
- exact normalized SHA/receipt-bound 2022 Alpaca monthly news Parquets from the accepted V2 chronology closeout, containing the conservative \`MAX(created_at, updated_at)\` availability rule. The final retrieved text is never backdated. It computes prior 24-hour and seven-day **article-count context** by ticker and original 09:35 decision UTC, not news sentiment or a novel alpha result.

It reads no provider, broker, protected return or historical article API. The 12 news normalized partition hashes are checked against their existing receipts (not a second full raw-news re-audit), and only four metadata columns are streamed using DuckDB. The 71 stock bindings reuse original source SHAs/plan identities without rerunning stock candidate selection or quote acquisition. Missing or tampered evidence fails closed. The new immutable compact output is placed under D:-bound \`data/research/evidence/\`. The local-original source corpus remains unchanged.

All original EOD bid/ask evidence remains **descriptive**. Neither original raw stock 09:30 entry open nor next-session option EOD price can act as a matched common-clock fill. Article ID counts are not a point-in-time historical revision archive. No same-clock P&L, option contract multiplier, deliverable/corporate action, stock later-session mark, 09:35 option bid/ask, PAPER, LIVE or promotion authority is added.

## One-line operator handoff after green merge

\`\`\`powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\.venv\Scripts\python.exe scripts\build_integrated_2022_casebook_v1.py --news-threads 4; if ($LASTEXITCODE -ne 0) { throw 'Offline stock/news/options casebook stopped. Preserve existing sources; no provider retry.' } }
\`\`\`

This is not a recommendation to start broad paid source acquisition. The remaining MarketData allowance today is below 2,000, and the command has **zero paid requests**. It prints accepted D: evidence, provenance and full original denominator.

## Immediate next implementation after this casebook

Use its joined case identities for the common-clock simulator: obtain *local native raw stock marks at the option reference's actual later sessions*, align exact observed timestamps or explicitly label date-level approximation, verify option contract deliverables/multipliers and conservative fees/mark rules, preserve no-quote/abstain statuses, and run the same entry/exit schedule for stock-vs-CALL-vs-abstain. The original 09:35 strategy is a **separate** future intraday-quote gate. Tune on DEVELOPMENT, not already-consumed protected outcomes. Keep offline mode network-inert.
