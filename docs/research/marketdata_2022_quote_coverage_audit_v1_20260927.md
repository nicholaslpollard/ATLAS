# Read-only 2022 historical CALL quote coverage audit V1 — 2026-09-27

## Why this gate follows the finished quote download

The source-only V2 operator run has completed 1,709 / 1,709 exact OCC histories from frozen 2022 additive shards 0–15. Original plan fingerprint \`3bde57ddc8c8675f48404a85d9c04d463f980abbb9db384c62ad663965381043\`; report \`a87b9e19b57a115d0293b1df816787c0470c4f88f509064840f65c3706022929\`. The 1,709 responses used 1,704 reported credits and stored 19,795,286 raw response bytes. Actual candidate-cache category 0.002 → 0.023 GiB. It is **not** necessary to reissue any of those provider requests because a new 16-worker downloader has been merged. Wider historical EOD observations are small on disk and may be sparse; making SSD usage rise is not the objective.

The next important information for a local-first simulator is **how many original dated option observations exist and what share has nonzero reported volume**, not the count of \`s=ok\` responses alone. The new read-only audit uses frozen \`data/options/manifests/marketdata_2022_broad_quote_plans_v2/through_shard_015.json\` and the same V1 exact-identity cache. It independently verifies plan fingerprint, V2 fixed window/expiry boundary, each original durable intent, body SHA, receipt SHA, exact symbol/date, raw byte count, and quote schema/session identity via the established receipt reader. It then sums original observed EOD rows, positive/zero reported volume rows, histories without positive-volume observations, first/last observed sessions, stored raw body bytes, original provider-reported charges, exact quote gaps and pending, and prints real D: free/cache figures.

No provider token, HTTP call, attempt creation, plan rewrite or receipt modification is performed. This is a **new quality/coverage gate** rather than redoing earlier source acquisition or original stock research. It does not assume missing sessions are no-trade days, that volume-null equals volume-zero, that a reported bid/ask is executable at 09:35, or that a quote row has verified historical standard deliverable. A complete source audit is still only EOD research authority.

Source-lineage accounting: original additive chain shards 0–15 included 601 complete physical exact chain sources and 39 strictly proven physical 404/no-data gaps. The V2 quote plan reports 40 source-gap/abstention ledger entries, not 40 physical 404s; original membership grouping and no eligible CALL cases may have different counting units. Do not overwrite or reinterpret original source status.

## Next single read-only workstation handoff after PR merge

\`\`\`powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\\.venv\\Scripts\\python.exe scripts\\audit_marketdata_2022_quote_coverage_v1.py --shards-through 15; if ($LASTEXITCODE -ne 0) { throw 'Local quote audit failed. Preserve original evidence; no provider requests or blind retries.' } }
\`\`\`

Review reported row/volume coverage and whether the full-year-to-expiration EOD data can support meaningful preregistered later-entry EOD simulation before authorizing another large paid 2022/other-year backfill. Once appropriate, acquire new 2022 chain source shards 16–25 via the original bounded source campaign, then the V2 \`--shards-through 25 --workers 16\` exact quote campaign, reusing every original exact 0–15 quote receipt. The V2 quote planner's default source preparation now checks the original 2022 prior cohort **once**, then individually SHA/binding/plan-verifies each already frozen additive source shard without redundantly repeating the 36-source original preview for every shard.

Do not mix this EOD dataset with 09:35 executable option quote/fill simulation; that requires separately sourced intraday market observations and a defined PIT fill rule.
