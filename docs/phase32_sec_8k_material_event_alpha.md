# Phase 32 — SEC 8-K Material Corporate-Event Alpha

**Status:** ACTIVE — V2 core source feasibility accepted; semantic 8-K source qualification is now active. Alpha hypotheses remain unfrozen, zero market outcomes are authorized, and Phase33 signal-to-trade remains blocked.

**Source foundation:** Phase31 PR #35 merge `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4` (`ACCEPTED_NEGATIVE`) with zero protected-return reads.

## Phase32 source progression

V1 archive/header acquisition remains retained as failed source-history evidence. Six attempts failed without reading market outcomes. Those failures were not bypassed silently: ATLAS diagnosed the presentation/archive path and then formally versioned the source contract before changing to official structured SEC submissions metadata.

V2 contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Frozen V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine V2 result: **PASS**.

Retained V2 totals:

- Massive original 8-K index rows: **6,048**
- ticker-linked rows: **5,272**
- sampled SEC records: **48**
- sampled SEC item codes: **94**
- successful Massive pages: **4**
- SEC filing-date mismatches versus Massive: **0**
- target/protected outcome reads: **0 / 0**
- provider/broker/order/PAPER/LIVE writes: **0**

The two acceptance-local-date versus filing-date differences are informational only. Exact SEC filing dates reconciled in all 48 samples; exact SEC acceptance timestamps remain the authoritative timing input.

## Accepted core source boundary

Massive discovery:

`MassiveRESTClient -> GET /stocks/filings/vX/index`

with original `8-K`, filing-date windows, `filing_date.asc`, limit 10000, and deterministic pagination.

Authoritative SEC metadata:

`https://data.sec.gov/submissions/CIK##########.json`

For older filings absent from `filings.recent`, ATLAS may follow only SEC-declared `filings.files` historical JSON shards whose `filingFrom..filingTo` range contains the requested Massive filing date, bounded to at most two candidate shards per lookup.

Every sampled filing must reconcile exact accession, exact original `8-K` form, SEC filing date equal to Massive filing date, nonempty `acceptanceDateTime`, structured SEC item codes, issuer CIK provenance, and primary-document metadata when supplied.

Conservative public-availability rule remains:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

Same-session entry remains forbidden even for intraday acceptance.

## Active semantic source qualification

SEC item codes are legal filing categories and may combine economically different events. Before freezing Phase32 hypotheses, ATLAS is now qualifying Massive's semantic sources:

- `/stocks/filings/8-K/vX/disclosures`
- `/stocks/filings/8-K/vX/text`
- `/stocks/taxonomies/vX/disclosures`

Massive's formal endpoint documentation says Plan History is not applicable, while its July 22, 2026 provider article states disclosure coverage begins in January 2022. ATLAS therefore verifies history empirically and freezes a conservative semantic-study start of `2022-01-03`; it does not infer older authority from provider marketing or later backfills.

Semantic contract:

`phase32-semantic-feasibility-v1-massive-8k-disclosures-text-no-market-outcomes`

Frozen semantic fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

The five source-only probe windows are 2021 research boundary, January 2022 published-history boundary, 2023 mid-history, 2026 development boundary, and 2026 protected boundary. Covered windows sample at most six exact original-8-K accessions.

The gate requires taxonomy membership, provider-native ticker alignment, exact original-8-K overlap, supporting-text grounding in parsed 8-K Item text, exact SEC accession/form/filing-date/acceptance reconciliation, immutable evidence, and zero target/protected outcome reads.

Full contract: `docs/phase32_semantic_source_qualification.md`.

Runner: `scripts/run_phase32_semantic_feasibility.py`.

## What remains unfrozen

No Phase32 alpha candidate exists yet. No event direction, horizon, threshold, ranking, or return-based selection is authorized.

If semantic source qualification passes, ATLAS will use only the accepted source/taxonomy evidence to freeze a finite economically coherent hypothesis family plus event aggregation/contradiction/amendment rules, exact PIT identity, decision session, horizons, benchmark, costs, sample/concentration gates, dependence-aware inference, multiplicity, robustness, development/internal/protected chronology and purge, winner/finalist rules, and finalist-only protected reads before any governed performance read.

If the semantic gate fails, Phase32 stops. Diagnose and repair the actual source/provenance cause first; do not weaken validation or substitute a workaround. A different source method is considered only after the intended method is shown infeasible.

## Authority boundary

Allowed now: bounded read-only Massive index/disclosure/text/taxonomy calls, bounded official SEC submissions reads, and immutable local source/report writes.

Forbidden: stock/SPY/options outcomes, protected candidate/return reads, provider mutations, broker/account reads or writes, orders, PAPER submits, LIVE writes, frontend trading authority, automation writes, and automatic broker failover.

A source PASS establishes only scientific-source suitability. It does not establish alpha, satisfy Phase33 entry, or grant trading authority.
