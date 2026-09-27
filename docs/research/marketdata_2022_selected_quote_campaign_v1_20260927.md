# 2022 PIT-selected exact CALL EOD quote campaign — 2026-09-27

## Why this is new data rather than another chain-only pass

Original eleven 2025 exact selected-CALL history series (320 EOD rows) were frozen and closed. The 2022 additive stock chain source is separately frozen into 71 source-disjoint shards. This implementation starts acquiring actual full historical EOD **quote series** for nearest-to-raw-open CALL and up to two distinct neighboring CALL strikes per accepted source opportunity. It does not filter/reselect on later quote volume, price, provider EOD moneyness or eventual stock return. Each original chain is from the previous session and underlying strike targeting comes from the original raw-as-traded entry OPEN. One shared OCC symbol from several accepted opportunities gets **one 2022-01-01 through expiration-inclusive quote request**, deduplicated across past/future 2022 shard ranges by exact symbol/date identity. All original member opportunity/chain source hashes remain in frozen D: plan metadata, separate from provider raw. The program does not ask MarketData for the same quote each day.

The first handoff after completion of concurrently running 2022 shards 6–15 targets the complete source shards **0–15**, plans all unique source-supported candidate CALL series, and then authorizes a bounded historical quote campaign. Existing source-only receipts and original exact 2025 historical selected quotes are unchanged. No previous exact 2022 quote request exists, so historical quote data is genuinely new on D:.

## Controls

- Max four simultaneous workers below provider concurrency 50; each original attempt persisted *before* request. One uncertain response/quarantine stops new batches, preserves all original intents/bodies/receipts and does not retry. Other in-flight requests from the same bounded batch finish and are preserved, even if one fails.
- Exact historical quote from/to query is keyed by immutable \`option_symbol\`, \`2022-01-01\`, \`expiry+1 exclusive\`, independent of source plan selection. Later overlapping 2022 shards reuse the same original raw body/receipt without changing original plan, enabling user to acquire earlier staged ranges without duplicate paid quote GETs.
- Uses original 4 MiB / 500 historical EOD quote row schema and timestamp checks, physical D: category quota and free-space floor, strict credit headers, 200-credit provider floor and user-supplied aggregate request/observed-credit targets. Actual cost is per 1,000 historical quote rows as documented, and a single response's provider-reported charge is authoritative.
- An original \`404/s=no_data\` is a stored exact-query source gap only if observed charge is zero; it does not prove a contract never existed or was never executable. Quarantined/nonzero-charge gaps fail closed.
- The source plan is immutable and can only be created once after all requested chain shards are complete. It retains the global accepted source fingerprint, all source-shard and chain SHA lineage, abstentions and all source-to-symbol memberships.
- **No historical adjusted 100-share deliverable, at-decision 09:35 bid/ask, fill, option P&L, protected holdout, promotion, PAPER/LIVE, broker or order authority.** 2022 full-year quote series include future observations for subsequent ex-post research only and cannot enter the historical intraday decision feature set.

## Intended first command (after the currently running 6–15 chain campaign and PR merge)

\`\`\`powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\\.venv\\Scripts\\python.exe scripts\\run_marketdata_2022_selected_quotes_v1.py --shards-through 15 --max-new-requests 2000 --max-observed-credits 2100 --workers 4 --authorize-provider-reads --confirm-paid-starter --confirm-private-internal-use; if ($LASTEXITCODE -ne 0) { throw 'Quote campaign stopped. Preserve source/receipts; do not blindly retry.' } }
\`\`\`

The script prints actual unique symbols, candidate memberships, complete/gap/pending series, raw body bytes and credit usage. If the unique quote count exceeds the explicit 2,000 request cap or a hard disk/credit limit is hit, it stops with a resumable partial result; never present partial source coverage as a complete priced sample. This is the first actual larger quote-history acquisition; expanding all 71 source shards, other years, new expiry horizons and intraday-price rights are separately bounded stages rather than promising unconditional total completion or permanent post-cancellation rights. MarketData Terms require deletion of raw licensed data when subscription terminates absent written exemption.


### 2026-09-27 — Accepted 2022 0–15 chain closeout and widened historical CALL price-source program

The additional 2022 chain campaign 6–15 completed: 372 exact successful chain sources, 28 strictly proven zero-credit 404 source gaps, zero pending, 400 new GETs/372 observed credits; last provider balance 9,275, report \`d358e3b4816cf7a588adc5f3f19e863f369e6d7d51f43eacd3fac59f0df77dbe\`. Additive 0–15 combined are 601 exact chain sources + 39 narrow gaps, no pending. Do not rerun any shard 0–15 source.

V1 historical CALL quote selection (nearest plus two strikes) is **superseded for the next broad acquisition** by \`scripts/run_marketdata_2022_broad_quotes_v2.py\`: every actual prior-session CALL returned within ±8% of individual raw entry OPEN in source shards 0–15, one full EOD quote history per distinct exact OCC symbol with immutable source membership and reuse of the existing V1 physical quote cache. This is a substantive data-stage expansion, not another chain-only 40-key campaign. The only available expiry in these original sources is the original 28–60-DTE monthly; alternate expiries, 2022 original pilot cohort, other years and remaining source shards still require separate real source acquisition. No 09:35 option fill/P&L or PAPER/LIVE authority. Full planning and handoff: \`docs/research/marketdata_2022_broad_quote_envelope_v2_20260927.md\`.


## Executor throughput update (shared exact-cache implementation) — 2026-09-27

Only the common exact quote-history executor's network concurrency and progress telemetry were changed. The original V1 three-strike source planning default and physical exact quote cache key remain immutable. Max concurrent network GETs is now 24; default is 16 for future calls. Batches remain evidence-preserving barriers, no retry after uncertain original requests. The currently running V2 \`--workers 4\` process is unaffected by a Git update and should finish normally. See \`docs/research/marketdata_2022_broad_quote_envelope_v2_20260927.md\`.
