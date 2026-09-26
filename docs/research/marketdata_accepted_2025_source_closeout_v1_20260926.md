# MarketData Accepted 2025 Candidate Source Closeout V1 — 2026-09-26

## Workstation observations and authority

Operator completion of the frozen 12-request source pilot: original recovered AGIO plus four first-batch verified chains and six subsequent verified chains. The first batch's original FSLY HTTP 404/`s=no_data` was separately proven as an exact-query, zero-credit source gap. The final six-request batch reported 6 new complete, 6 observed consumed credits, and 9989 last remaining. The final independent zero-provider-read preview reported **11 complete / 1 exact-query FSLY no-data / 0 pending**. The wrapper prints `status=PREVIEW` because the final object is its independently verifying read-only preview; that is not an incomplete acquisition.

Pilot credit accounting based on saved per-request provider headers: one original AGIO, four subsequent successful chains and six final successful chains = 11 observed consumed credits; original FSLY response reported zero consumed credits. This aggregate is subject to the exact original receipt re-verification at the next operator gate; no bill or subscription usage data is assumed beyond those headers.

Frozen plan fingerprint: `a830ab16e6ebce9b509ec88efad8b6c8e08e2951db8682aa8d5e34ffc96886e1`.
Accepted stock-source SHA-256: `e7d90ce3162475ecbfc442d35e0ffbca18fca38434e658b0ee8bd7633021362e`.
Original FSLY response body SHA-256: `54e3e162845e54a24f015e4faaff70531c0707baf1f492fcebd5c35922f5971a`.
FSLY no-data proof fingerprint: `6d2e3d17fbcb0f39d88af9ed025d71757c84e97ac00b75d130d189c6ac0f083f`.

These are operator-reported local observations. No private provider body or original private local manifest was uploaded or independently reproduced inside GitHub.

## Implementation: local source-level closeout, not contract selection

New `scripts/closeout_marketdata_candidate_2025_source_v1.py` is **offline by default**. It validates the exact accepted stock bundle and regenerated frozen plan; independently revalidates all twelve physical source receipts and the FSLY proof; decodes only the original already-verified local chain rows; and produces a deterministic metadata manifest summarizing each frozen request and opportunity. The manifest records identity hashes, observed call/put counts and opportunity-side coverage, not raw option quotes, fill prices, final contract selections, or source copies. An explicit `--write-local-closeout` creates a new fingerprinted manifest in the configured project-visible `data/options/manifests` location; existing different bytes block rather than overwrite. No provider call, credentials, token, or quotation history read.

Read-only preview:

~~~powershell
.\.venv\Scripts\python.exe scripts\closeout_marketdata_candidate_2025_source_v1.py
~~~

Only after verifying the output, explicit local closeout write:

~~~powershell
.\.venv\Scripts\python.exe scripts\closeout_marketdata_candidate_2025_source_v1.py --write-local-closeout
~~~

Expected counts: 11 verified complete, one exact-query gap, zero pending, 12 mapped stock opportunities, zero new provider calls/credits. Same-side row count is structural source evidence only; zero matching call rows in a complete chain is not proof of general historical option absence. The original raw, attempts, quarantine/recovery proofs and receipts remain unchanged. Do not commit local MarketData raw data or generated private candidate manifests to GitHub.

## Subsequent gates

Freeze an outcome-blind historical contract-selection contract using these source-verified snapshots, expected CALL side, exact PIT raw stock price and decision clock. Independently validate OCC identity, adjustment/deliverable and historical availability; treat ambiguous or unsupported contracts as abstentions. Only then cost selected-contract EOD quote horizons against shared date-wise chains; acquire price histories under a separate approved bounded, resumable provider contract. Do not use same-session EOD option fields at a preceding stock entry, zero-volume last as a traded price, synthetic intraday stop/target trajectories, or bid/ask as automatically executable fills. Source-only closeout changes no strategy evidence, simulator P&L, PAPER, LIVE or broker/order authority. Preserve provider-subscription licensing/retention policy.


**2026-09-26 PR #236 merged confirmation:** CI passed all ten GitHub checks, including Linux and Windows full suites (2,592 tests and four subtests on each), and source-only closeout was merged as `3fb8d50ffca9926e240a0a5e0c714817775527fc`. This is code/contract acceptance, not proof a local closeout manifest has been generated. Next operator command runs the exact frozen source/receipt preflight and independently verifies 11 complete, one FSLY source gap and zero pending with no provider calls, then creates only the D:-bound local metadata closeout through an explicit CLI flag. Original provider bytes and provenance remain private and immutable.
