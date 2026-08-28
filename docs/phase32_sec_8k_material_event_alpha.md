# Phase 32 — SEC 8-K Material Corporate-Event Alpha

**Status:** ACTIVE — SOURCE FEASIBILITY / PROVENANCE ONLY. Alpha hypotheses are not frozen; zero market outcomes are authorized; Phase33 signal-to-trade remains blocked.

**Source foundation:** Phase31 PR #35 merge `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4` (`ACCEPTED_NEGATIVE`) with zero protected-return reads.

## Plain-English phase start

ATLAS has now tested six materially different modern alpha mechanisms and none earned support. Phase32 changes the information mechanism again: structured SEC 8-K material corporate-event disclosures.

An 8-K is the issuer's regulatory disclosure of specified material events. The research question is whether particular structured event classes create robust post-disclosure repricing/drift after the filing is publicly accepted by the SEC. This is different from Phase30's metadata-only news-arrival shock and Phase31's insider transactions.

The phase is allowed to fail. Nothing may be tuned into a positive result after performance is observed.

## Entry condition

Phase31 closed `ACCEPTED_NEGATIVE` with `PASS_NEGATIVE_MANDATORY_SAMPLE_GATE_PROOF`, zero supported candidates, zero protected candidate rows, zero protected returns, and an unconsumed master holdout. Entry satisfied by merge `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.

## Feasibility source boundary

Massive discovery source:

`MassiveRESTClient -> GET /stocks/filings/vX/index`

Frozen feasibility query:

- `form_type=8-K`
- `filing_date.gte/lte` by frozen probe window
- `sort=filing_date.asc`
- `limit=10000`
- deterministic pagination through `next_url`.

Current Massive subscription declaration: **Stocks Starter**. Actual credential access must be proven by the target run; documentation or prior endpoint access does not substitute for that evidence.

Authoritative timestamp/item source:

`official SEC EDGAR -> https://www.sec.gov/Archives/edgar/data/<CIK>/<accession-no-dashes>/<accession>.hdr.sgml`

The official raw SGML filing-header artifact is used only for source provenance:

- `ACCESSION NUMBER`
- `<ACCEPTANCE-DATETIME>`
- `ITEM INFORMATION` labels
- exact bounded raw filing-header evidence.

The raw header URL is derived generically from Massive CIK + accession. No accession-specific URL override is allowed. ATLAS does not request the complete submission `.txt` or the HTML `-index-headers.html` presentation during feasibility.

## Conservative public-availability rule

Feasibility timing boundary:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

`<ACCEPTANCE-DATETIME>` is interpreted in `America/New_York`. Filing date alone cannot move the signal earlier. Even an intraday SEC acceptance cannot authorize same-session entry under this feasibility boundary.

A later frozen scientific contract may be more conservative but cannot choose an earlier decision time after inspecting returns.

## Frozen feasibility windows

1. research boundary `2021-08-16..2021-08-20`
2. mid-history `2023-08-14..2023-08-18`
3. development boundary `2026-05-04..2026-05-08`
4. protected boundary `2026-08-07..2026-08-11`.

For each window ATLAS will preserve the complete returned Massive 8-K index frame and fetch a deterministic bounded SEC sample of at most 12 unique accessions (all when <=12; otherwise first six + last six by filing date/accession).

## Feasibility acceptance criteria

The target run must prove, without market outcomes:

- all four windows return original 8-K rows;
- all windows have provider-native ticker linkage;
- Massive pagination/request provenance is retained;
- all sampled SEC filings have exact acceptance timestamps from official raw filing headers;
- sampled SEC accessions reconcile exactly to Massive accessions;
- all windows demonstrate populated `ITEM INFORMATION` evidence;
- immutable Massive index and SEC-header evidence reproduces exactly on rerun;
- SEC reads stay on official `www.sec.gov/Archives/edgar/` paths, identify ATLAS with a local contact, target only `.hdr.sgml`, advertise gzip/deflate support, and are limited to one request/second;
- alpha hypotheses remain unfrozen;
- target/protected market outcomes remain zero;
- provider writes, broker reads/writes, orders, PAPER, LIVE, automation, and automatic broker failover remain zero/disabled.

A mismatch between SEC acceptance local date and Massive `filing_date` is a diagnostic to preserve, not automatically a source failure. Exact acceptance time is the authoritative timing input for later scientific design.

## What is not frozen yet

No Phase32 alpha candidate exists yet. Potential event ideas—including bankruptcy/receivership, default or accelerated financial obligations, material impairment, delisting/listing deficiency, financial-statement non-reliance/restatement, or unregistered equity issuance/dilution—are **ideas only** during feasibility.

Do not inspect returns, rank item labels, choose a direction, pick a horizon, or select thresholds until feasibility is accepted and a finite scientific contract is frozen.

## Post-feasibility sequence

If feasibility passes:

1. freeze a finite original-8-K item-defined hypothesis family;
2. freeze event-unit/contradiction/amendment rules and exact PIT identity;
3. freeze decision session, horizon(s), benchmark, costs, dependence/multiplicity, robustness and concentration gates;
4. freeze development/internal/protected chronology and no-runner-up rules;
5. build predictor-only event frames before outcomes;
6. only then read development performance;
7. protected returns remain finalist-only after independent blindness/lineage audit;
8. independently reconstruct and close Phase32.

If feasibility fails, diagnose source/provenance root cause generically. Do not inspect market outcomes or change the information family merely to manufacture a PASS.

## Authority boundary

Allowed in feasibility:

- bounded read-only Massive SEC-index calls;
- bounded read-only official SEC EDGAR raw filing-header calls;
- immutable local source evidence and feasibility report writes.

Forbidden:

- stock/SPY/option target outcomes;
- protected candidate/return reads;
- provider writes;
- broker/account reads or writes;
- orders, PAPER submits, LIVE writes;
- frontend trading authority;
- automation writes;
- automatic broker failover.

## Success semantics

A feasibility PASS means the structured 8-K source is suitable to define a scientific test. It does **not** establish alpha, does not satisfy Phase33 entry, and creates no trading authority.

A later positive Phase32 closeout requires at least one fully confirmed candidate to earn historical analytical `SUPPORTED` authority. A legitimate negative result will close `ACCEPTED_NEGATIVE` and keep Phase33 blocked.
