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


## 2026-09-26 first bounded continuation — quarantined FSLY response

The authorized source-only continuation verified the exact exporter bundle at its original D:-junction-visible project path, reused the original 608-byte AGIO response, and durably completed four **new** chains (AMGN, ATRC, BANF, DAKT). Those four provider responses each reported one consumed credit, with the latest successful response reporting 9995 credits remaining. The following frozen FSLY request (2025-04-09 historical snapshot, 2025-05-16 expiry, strike 5.14–6.04) stopped the first ten-request batch with `provider chain quarantined with exact raw receipt: unexpected provider response status`. The failed request's HTTP status, provider payload status, billed credits and meaning **are not established by terminal output**. No second paid batch ran. The other six never-attempted requests stay pending. Original FSLY body, receipt and attempt marker must remain.

Read-only next operator step, from merged `main`:

~~~powershell
.\.venv\Scripts\python.exe scripts\inspect_marketdata_candidate_2025_pilot.py
~~~

This inspector directly verifies original stock source and saved plan SHA, reads only local bodies/attempts/receipts, verifies SHA and fingerprints, and reports the quarantined request's HTTP status, allowlisted payload `s`, recorded row count and provider numeric consumed/remaining headers. It never prints `errmsg`, `message`, raw JSON, tokens or headers other than those numeric credit fields. It also displays current physical receipt status independent of the latest historical run checkpoint. No provider reads, credit charges, writes, recovery, deletion, widened strikes or retry are permitted.

A 404 / `no_data` would be a candidate-source coverage observation, **not** a cache hit, a proven historical contract absence at all alternative expiries/strikes, or permission to replay a possibly charged request. A 401/403/429, unexpected provider schema, or unknown credit state requires different remediation. Do not make a versioned skip/continue or alternate-source decision until original saved response metadata and credit evidence are reviewed. Original aggregate strategy/exit evidence and PAPER/LIVE boundaries remain untouched.


## 2026-09-26 — Verified FSLY 404/no_data and separate source-gap disposition V1

Physical read-only inspection established that the frozen FSLY request `6886b1d35d7a1ea2e1a9f555cd0f778905ad1029175bec953fc52d5289a643d8` returned HTTP 404 with `s=no_data`, zero recorded rows, 47 exact HTTP body bytes (SHA-256 `54e3e162845e54a24f015e4faaff70531c0707baf1f492fcebd5c35922f5971a`), provider-reported zero consumed credits and 9995 remaining. Its original attempt and raw receipt passed fingerprint/integrity verification. The failed run-level checkpoint conservatively flags credit uncertainty, but the immutable request-specific headers resolve **this request's observed charge as zero**; the original checkpoint is not rewritten. Confirmed source totals before disposition: five complete chains (AGIO plus four), one preserved FSLY quarantine and six untouched requests.

Separate no-data proof V1 is explicitly opt-in and strictly exact-query scoped. It requires the original signed/quarantined 404/no_data response, unchanged SHA-verified raw bytes, a fingerprinted matching attempt on the same frozen plan, zero reported consumption, zero rows and no successful-recovery sidecar. The classification is written exclusively to a new `.no_data.json` sidecar with a fingerprint; the original body, receipt, attempt and plan remain immutable. Merely inspecting a 404 does NOT automatically authorize a skip. The cache treats the sidecar as a terminal *source-coverage observation* only after independent full-byte/proof/plan verification. It is **not** a complete chain and does not grant historical availability, quote-price, fills, option P&L or PAPER/LIVE authority.

Offline operator gate (default preview performs no writes and no provider reads):

~~~powershell
.\.venv\Scripts\python.exe scripts\classify_marketdata_candidate_2025_fsly_no_data_v1.py
~~~

After reviewing exact-proof metadata, explicit zero-provider-call classification:

~~~powershell
.\.venv\Scripts\python.exe scripts\classify_marketdata_candidate_2025_fsly_no_data_v1.py --authorize-exact-no-data-record
~~~

The offline classifying command must produce an independent result of exactly **5 complete / 1 exact-query no-data / 6 pending**, zero provider reads and no original evidence mutation. Later authorized pilot acquisition may issue up to six NEW requests; it must never replay FSLY, widen FSLY's original strike/expiry or falsely count its source gap as a completed chain. A successful remainder is **11 complete + 1 exact-query source gap + 0 pending**, explicitly `COMPLETE_WITH_SOURCE_GAPS`, not twelve complete. Any new abnormal provider response remains quarantined and stops the run. Do not automatically classify other 404s or infer that no alternative options existed for FSLY.


## 2026-09-26 workstation offline classification acceptance

Operator returned `RECORDED_VERIFIED_NO_DATA` for frozen FSLY, proof fingerprint `6d2e3d17fbcb0f39d88af9ed025d71757c84e97ac00b75d130d189c6ac0f083f`, original quarantine receipt fingerprint `afd9bc9135c575351f14f6bad3c769083d9331019c06dd7e0a1b1df0941f1748`, 404/no_data/0 rows/0 consumed credits/9995 last remaining. Independent physical preview confirmed **five complete, one exact-query no-data and six pending**. Original raw body, receipt, attempt and frozen plan unchanged; classification issued zero provider calls.

Next separately authorized, six-new-request maximum (not an automatic retry):

~~~powershell
.\.venv\Scripts\python.exe scripts\run_marketdata_candidate_2025_pilot.py --authorize-provider-reads --confirm-paid-starter --confirm-private-internal-use --max-total-new-requests 6
~~~

A new abnormal response must stop the run. Do not replay an attempted request; use immutable evidence diagnosis before any subsequent acquisition. Successful source-only terminal accounting is 11 complete, 1 exact-query FSLY no-data, 0 pending. No option quote/fill/P&L or promotion authority.
