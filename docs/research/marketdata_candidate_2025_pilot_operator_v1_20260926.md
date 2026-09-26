# Accepted 2025 MarketData Candidate Pilot — Junction-Safe Operator Gate (2026-09-26)

## Status and authoritative state

This is an operational wrapper around the already accepted source-only chain cache; it
does not change scientific source, query selection, MarketData transport, storage
budget, credit guards, durable attempt/receipt handling, or option-price authority.

The physical stock bundle was emitted by the accepted exporter at the stable
project-visible path
`data/research/evidence/marketdata_candidate_stock_v1/d6c924cf5006d295.json`.
The options plan is under `data/options/manifests`. These logical directories
are Windows junctions into `D:/ATLAS_DATA` on the current workstation, an
internal Samsung 860 EVO SSD; a recursive PowerShell scan starting at `.\data`
may skip junction descendants and is not reliable evidence that this file is missing.
The prior recursive scan was an operator-command defect. Do not copy, re-export,
move or overwrite the original artifact merely because that scan returned nothing.

The exact source bundle SHA-256 is
`e7d90ce3162475ecbfc442d35e0ffbca18fca38434e658b0ee8bd7633021362e`;
the exact plan-file SHA-256 is
`fe7b85272212d9ba5584b4e964d7e46e3ac128cf449604786bdee7e9441e149e`,
and reconstructed plan fingerprint is
`a830ab16e6ebce9b509ec88efad8b6c8e08e2951db8682aa8d5e34ffc96886e1`.
The original AGIO HTTP 203 two-row raw body and quarantine receipt remain
immutable; separately fingerprinted offline recovery is verified. Latest
zero-network operator preview: 1 reused receipt, 608 bytes, 11 pending,
0 provider reads, no additional credits. The prior FAILED_REVIEW_REQUIRED
checkpoint from the initial AGIO request is a historical record, not a
current cache verdict.

## Default preflight (read-only)

```powershell
.\.venv\Scripts\python.exe scripts\run_marketdata_candidate_2025_pilot.py
```

The wrapper resolves the exact logical exporter path directly, validates the
source and plan bytes, source cohort IDs, regenerated plan and AGIO canary,
then runs the existing receipt-verifying zero-network preview. It never scans
`.\data` recursively and does not trust a historical latest-run checkpoint
as proof of current completeness. A missing or mismatched input stops with
the exact expected path; no automatic substitute or re-export occurs.
The default performs no API calls, cache writes or provider charges.

## Bounded operator-authorized source reads

Only after merging CI-validated code and review of the read-only preflight:

```powershell
.\.venv\Scripts\python.exe scripts\run_marketdata_candidate_2025_pilot.py --authorize-provider-reads --confirm-paid-starter --confirm-private-internal-use --max-total-new-requests 11
```

A single operator invocation reuses AGIO and permits at most ten *new*
requests in the first existing cache invocation, independently previews
exact receipt reuse, then at most one more request, then independently
previews the final cache. These are two separately gated provider batches,
not an attempt to bypass the ten-request cache cap. A failing, quarantined,
credit/storage-blocked or ambiguous first batch stops without a second.
The existing per-attempt durable marker, exclusive lock, no automatic
provider retry, required rate-limit accounting, 200-credit floor and
storage quota checks remain in force.

Expected complete pilot: 12 independently verified receipts and zero
pending. In case of failure, preserve all original raw bodies, recovery
records, attempts, receipts and run reports; inspect before any retry.
A successful pilot proves bounded historical EOD chain source availability
only. It is not historical contract selection, quote history, executed
option price, simulated P&L, PAPER or LIVE authority.

## Longer-term provider and storage separation

D: remains secondary research storage; the core source/runtime and accepted
Alpaca SIP V2 stock data stay on C:. News, options, qualification records,
research evidence, fundamentals and archives use configured secondary
bindings. The provider-license registry must distinguish MarketData
subscription-scoped raw/normalized data and copies from independent
research outputs and other providers' separately governed datasets.

MarketData's current published terms require subscription-period downloaded
data to be deleted when the subscription ends. Do not treat an SSD archive
as a cancellation workaround; seek written provider clarification of
permitted retention and derived-data treatment before designing a
subscription-exit process: https://www.marketdata.app/terms/ .

After the pilot, freeze candidate contract identities, corporate-action
and historical deliverable validation, and separate selected-contract
historical EOD quote horizons and conservative EOD timing/cost modeling.
Preserve news chronology as max(created_at, updated_at). Only then compare
stock-only, news-context and option-economics recurrent DEVELOPMENT
replays. No alpha or PAPER/LIVE promotion is authorized.
