# Phase 32 — SEC 8-K Material Corporate-Event Alpha

**Status:** ACTIVE — SOURCE FEASIBILITY / PROVENANCE ONLY. Alpha hypotheses remain unfrozen, zero market outcomes are authorized, and Phase33 signal-to-trade remains blocked.

**Source foundation:** Phase31 PR #35 merge `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4` (`ACCEPTED_NEGATIVE`) with zero protected-return reads.

## Feasibility V2 contract

Contract version:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Frozen V2 feasibility fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

V1 archive-header feasibility remains retained as failed source-history evidence. V2 does not reinterpret any V1 result and does not authorize market outcomes.

## Source boundary

Massive discovery remains unchanged:

`MassiveRESTClient -> GET /stocks/filings/vX/index`

with the frozen query:

- `form_type=8-K`
- frozen `filing_date.gte/lte` probe windows
- `sort=filing_date.asc`
- `limit=10000`
- deterministic `next_url` pagination.

Current Massive subscription declaration remains **Stocks Starter**.

Authoritative SEC metadata source for V2:

`official SEC EDGAR -> https://data.sec.gov/submissions/CIK##########.json`

For an older accession not present in the root `filings.recent` arrays, ATLAS may follow only SEC-declared `filings.files` archive JSON whose `filingFrom..filingTo` range contains the requested Massive filing date. At most two matching archive shards may be read for one lookup.

For every sampled Massive original 8-K, SEC metadata must independently confirm:

- exact `accessionNumber` equality;
- exact original form `8-K` — not `8-K/A`;
- SEC `filingDate` equal to Massive `filing_date`;
- nonempty `acceptanceDateTime`;
- structured SEC `items` codes;
- issuer CIK provenance and primary-document metadata when supplied.

SEC `acceptanceDateTime` is parsed as an offset-aware timestamp and converted to `America/New_York` for the unchanged timing rule. ATLAS does not infer accession, filing date, form, acceptance time, or item codes from the requested URL.

Because the root SEC company-submissions JSON legitimately changes as new filings arrive, V2 does not make the entire live company JSON an immutable artifact. Instead, ATLAS preserves an exact canonical JSON record containing only the sampled filing's authoritative SEC metadata plus its source URL. Historical changes to that filing record therefore still produce immutable-evidence drift without unrelated future filings invalidating the artifact.

## Conservative public-availability rule

The feasibility timing boundary remains exactly:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

An intraday SEC acceptance still cannot authorize same-session entry. A later scientific contract may be more conservative but may not choose an earlier entry after inspecting returns.

## Frozen feasibility windows and sampling

The four probe windows remain unchanged:

1. research boundary `2021-08-16..2021-08-20`
2. mid-history `2023-08-14..2023-08-18`
3. development boundary `2026-05-04..2026-05-08`
4. protected boundary `2026-08-07..2026-08-11`.

For each window, ATLAS preserves the complete Massive index frame and samples at most 12 unique accessions: all when there are 12 or fewer, otherwise the first six and last six by filing date/accession.

V2 evidence is namespaced separately under `data/provider/phase32_sec_8k_feasibility/v2/`, with its report under `data/derived/strategy_evaluation/phase32/v2/`.

## Feasibility acceptance criteria

The target run must prove, without market outcomes:

- all four windows contain original Massive 8-K rows;
- every window has provider-native ticker linkage;
- Massive pagination/request provenance is retained;
- every sampled accession is independently found in official SEC submissions metadata;
- SEC accession, original `8-K` form, and filing date reconcile exactly to Massive;
- every sampled filing has an exact SEC acceptance timestamp;
- every probe window has at least some structured SEC item-code evidence;
- immutable Massive frames and canonical sampled SEC records reproduce exactly;
- SEC reads remain read-only on `data.sec.gov/submissions/`, identify ATLAS using the local contact, support gzip/deflate, and run at one request per second;
- alpha hypotheses remain unfrozen;
- target/protected market outcomes remain zero;
- provider writes, broker reads/writes, orders, PAPER, LIVE, automation, and automatic broker failover remain zero/disabled.

## What remains unfrozen

No Phase32 alpha candidate exists yet. Event ideas such as bankruptcy/receivership, defaults or accelerated obligations, material impairments, listing deficiencies, financial-statement non-reliance/restatements, and unregistered equity issuance/dilution remain ideas only.

Do not inspect returns, assign directions, select horizons, rank item codes, or choose thresholds until V2 feasibility is accepted and a finite scientific hypothesis family is frozen.

## Post-feasibility sequence

If V2 feasibility passes, ATLAS will freeze the finite SEC-item-code hypothesis family, event-unit and amendment rules, exact PIT identity, decision session, horizons, benchmark, costs, sample/concentration/robustness gates, multiplicity, development/internal/protected chronology, purge, finalist-only protected reads, and no-runner-up rule before any governed performance read. Predictor-only event construction follows before development outcomes.

If feasibility fails, diagnose the source/provenance defect generically. Do not inspect market outcomes or weaken chronology/identity rules to rescue the source.

## Authority boundary

Allowed during V2 feasibility: bounded read-only Massive 8-K discovery, bounded read-only official SEC submissions metadata, and immutable local source/report writes.

Forbidden: stock/SPY/options outcomes, protected candidate/return reads, provider mutations, broker/account reads or writes, orders, PAPER submits, LIVE writes, frontend trading authority, automation writes, and automatic broker failover.

A feasibility PASS means only that the source is suitable for a scientific test. It does not establish alpha, does not satisfy Phase33 entry, and grants no trading authority.
