# 2022 additive historical chain multi-shard campaign V1 — 2026-09-27

## Accepted first shard and frozen lineage

Operator's original additive 2022 shard zero is complete: 39 HTTP source-complete exact historical chains, one independently proven original zero-credit exact-query 404/no_data gap, zero pending; 40 new attempts, 39 observed credits, provider last remaining 9,836. Shard plan `9df6a0c6db48c9617a99d1decab35b84ceffd5677090516cb7a8b31095512fd8`, original source SHA `438418f9e50f58ba66501e5935d3a857cedadddc2c668dd6ea69baf119c89030`, report `64bfde3f86876e457dcee6f582b065000eee6558f46b638253a49b567468b1e9`. Do not reacquire shard zero, any original 2022 monthly cohort, or the 2025 pilot.

The original accepted 2022 additive census is 2,812 distinct physical historical query keys over 71 deterministic 40-key shards, with separate recorded 20 missing-in-28-to-60-day monthly-expiry source exclusions. Original opportunity selection and entire old `(ticker, previous-session snapshot, expiration)` physical query-group exclusion remain fixed and outcome-independent. The SSD is storage budget, not an instruction to blindly fill it. Data is source-only with no 09:35 option fill, deliverable, option P&L or execution/PAPER/LIVE authority.

## New implementation

`scripts/run_marketdata_additive_2022_campaign_v1.py` composes the **unchanged** per-shard `prepare_additive_shard` and `run_expansion` under a single user-chosen multi-shard budget. It first reuses original immutable shard zero as source-census anchor and confirms the requested index range is within its original total and matches the frozen full-key fingerprint. Every new shard reuses the full 2022 accepted source loader **once per command**, rather than reloading 546 source parts for each shard. Each shard still SHA-binds its own raw native 1D opens and immutable source/plan/receipt lineage; no license data enters GitHub.

Before any billable call it checks the new shard's original source/plan and the exact physical query keys against previously processed shards. Existing complete shard zero gets zero provider requests; existing partial shards reuse original complete receipts and narrowly proven zero-credit 404 sidecars. Provider calls remain sequential via the existing 10-per-batch cache with durable intents, no retries, D: physical minimum/category quota guards, and observed credit-header checks. A timeout, quarantine, schema/identity/source mismatch or unproved no-data response stops the entire command. An explicit opt-in authorizes offline sidecar only for a fully proven original zero-credit `404/s=no_data`.

A bounded campaign supports at most 10 consecutive shards, 400 *new* requests and an observed-credit stopping target at most 500. Credit accounting is observed after provider responses; no pre-response promise of a mathematically exact billing ceiling is made. The requested range never silently advances into 2023/2024 or 2025 and stops at a shard boundary on depleted budget. No new large cohort returns or option strategy statistics are computed.

## First live campaign command

Use from clean main after merge. It starts with already-complete shard zero (reused, zero new GETs), then acquires consecutive shards 1–5 subject to a **200-new-request / 250-observed-credit** budget. A single invocation prints per-shard status and shared cumulative accounting. It may return a partial result if the budget or storage/credit floor is reached; this is recoverable from intact receipts:

```powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\.venv\Scripts\python.exe scripts\run_marketdata_additive_2022_campaign_v1.py --start-shard 0 --max-shards 6 --duckdb-threads 4 --max-total-new-requests 200 --max-observed-credits 250 --authorize-provider-reads --confirm-paid-starter --confirm-private-internal-use --classify-exact-no-data; if ($LASTEXITCODE -ne 0) { throw 'Multi-shard campaign stopped. Preserve original evidence; do not blindly retry.' } }
```

Follow actual output before authorizing the following bounded range (e.g. shards 6–10). Do not automatically loop over all 71 shards or assume a historical chain establishes a priced selected CALL. Selected-contract EOD quote histories and independent historical deliverable/entry-timing feasibility remain subsequent acquisition/simulator stages. Source retention is governed by provider license terms.
