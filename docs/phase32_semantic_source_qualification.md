# Phase 32 — Semantic 8-K Source Qualification

**Status:** ACTIVE — SOURCE/PREDICTOR PROVENANCE ONLY. No alpha hypothesis is frozen and no market outcome is authorized.

## Why this gate exists

The accepted Phase32 V2 feasibility run proved that Massive can discover original 8-K filings and official SEC `data.sec.gov/submissions` metadata can independently reconcile exact accession, original form, filing date, acceptance timestamp, and item codes without reading market outcomes.

That source is scientifically usable, but SEC item codes are legal filing categories rather than precise economic-event labels. Before freezing the finite Phase32 hypothesis family, ATLAS is therefore qualifying Massive's semantic 8-K sources:

- `/stocks/filings/8-K/vX/disclosures`
- `/stocks/filings/8-K/vX/text`
- `/stocks/taxonomies/vX/disclosures`

The disclosure endpoint provides a three-tier event taxonomy plus `supporting_text`; the text endpoint provides parsed 8-K Item text used to verify that supporting evidence is actually present in the filing text.

## Accepted V2 feasibility evidence

Frozen V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine result: **PASS**.

Retained totals:

- Massive original 8-K index rows: **6,048**
- ticker-linked rows: **5,272**
- sampled official SEC records: **48**
- sampled SEC item codes: **94**
- successful Massive pages: **4**
- SEC filing-date mismatches versus Massive: **0**
- target outcome rows read: **0**
- protected candidate rows read: **0**
- protected return rows read: **0**
- provider/broker/order/PAPER/LIVE writes: **0**

The two observed acceptance-local-date versus filing-date differences are informational only; official SEC filing dates reconciled exactly, and exact SEC acceptance timestamps remain authoritative.

## Provider history evidence and conservative boundary

Massive's formal endpoint documentation currently says **Plan History: Not applicable to this endpoint**. Separately, Massive's July 22, 2026 provider article for the 8-K disclosure product states that disclosure coverage starts in **January 2022**.

ATLAS does not treat either statement as sufficient by itself. The semantic gate empirically probes the source and freezes a conservative usable semantic-history start of:

`2022-01-03`

The 2021 Phase32 research-boundary window is still queried and preserved as source evidence, but semantic rows before the frozen safe start are not authorized for the later study even if the provider has subsequently backfilled them.

## Frozen semantic-source contract

Contract version:

`phase32-semantic-feasibility-v1-massive-8k-disclosures-text-no-market-outcomes`

Frozen fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Frozen probe windows:

1. prepublished boundary: `2021-08-16..2021-08-20` — observation only;
2. published-history boundary: `2022-01-03..2022-01-07`;
3. mid-history: `2023-08-14..2023-08-18`;
4. development boundary: `2026-05-04..2026-05-08`;
5. protected boundary: `2026-08-07..2026-08-11`.

For each covered window, ATLAS deterministically samples at most six unique disclosure-bearing accessions after exact overlap with the original-8-K Massive index.

## Required source checks

The target run must prove, without any return read:

- the disclosure taxonomy is nonempty and versioned;
- every covered window contains disclosure rows;
- covered disclosure rows overlap exact original `8-K` accessions from the Massive index;
- sampled disclosure categories exist in the frozen taxonomy;
- provider-native ticker linkage aligns between disclosure and index records without case normalization;
- every sampled accession has exactly one matching original-8-K row from Massive 8-K Text;
- every sampled disclosure `supporting_text` is grounded in that filing's parsed `items_text` after punctuation/whitespace normalization only;
- official SEC submissions metadata independently reconciles exact accession, original `8-K`, filing date, and nonempty acceptance timestamp;
- raw taxonomy/index/disclosure/text/SEC source evidence is immutable and drift-detecting;
- target/protected market outcomes remain unread;
- provider writes, broker reads/writes, orders, PAPER, LIVE, automation writes, and automatic broker failover remain disabled.

## Failure rule

Any failure stops Phase32 progression. Diagnose and repair the actual source/provenance defect first. Do not weaken grounding, ticker, accession, SEC, chronology, or immutability checks. Only if the intended semantic source is ultimately proven infeasible may ATLAS define a different source method before returns are opened.

## What this gate does not do

A PASS does **not** establish alpha and does not authorize Phase33. It only establishes whether the semantic event data is sufficiently grounded and historically available to use when defining the finite Phase32 hypothesis family.

Only after this source gate passes may ATLAS freeze the full scientific contract: finite event hypotheses, directions, aggregation/contradiction/amendment rules, PIT identity, decision session, horizons, benchmark, costs, sample/concentration gates, dependence-aware inference, multiplicity, robustness, chronology/purge, winner/finalist rules, and finalist-only protected read.

## Exact target

Runner:

`scripts/run_phase32_semantic_feasibility.py`

Expected frozen fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`
