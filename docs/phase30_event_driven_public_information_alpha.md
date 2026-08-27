# Phase 30 — Event-Driven Public-Information Alpha

**Status:** ACTIVE — historical-news feasibility/provenance contract frozen; alpha hypotheses are **NOT YET FROZEN**.

**Source foundation:** Phase29 merge `87c9450e1b21606b83489f16ff326235ae92eb2b` (`ACCEPTED_NEGATIVE`).

## Plain-English purpose

ATLAS has correctly rejected four modern price-derived alpha families under frozen standards. Phase30 changes the information source rather than retuning those failures. It asks whether timestamped public company information—initially financial news—contains repeatable directional value after realistic costs.

The first Phase30 work package is deliberately not a backtest. Before ATLAS is allowed to define or test news alpha, it must prove that the historical news evidence is actually available, timestamped, ticker-linked, replayable, and point-in-time defensible. A data source that cannot pass that provenance test cannot be used to claim edge.

## Entry condition

Satisfied:

- Phase29 full closeout PASS / `ACCEPTED_NEGATIVE`;
- Phase29 supported candidates = 0;
- protected candidate rows read = 0;
- protected return rows read = 0;
- inherited `2026-05-12` through `2026-08-11` holdout remains outcome-unopened;
- post-merge Phase29 `main` workflow `33124971664` passed Ubuntu and Windows.

## Current contract boundary

### Frozen now — feasibility/provenance only

The following are frozen before any Phase30 target outcome is inspected:

- source provider path: accepted `MassiveRESTClient` -> `/v2/reference/news`;
- all-ticker historical query; no current-universe ticker list is projected backward;
- sort = `published_utc`, order = ascending;
- page limit = 1000;
- provider `next_url` pagination must remain on the configured Massive REST host through the accepted REST adapter;
- exact UTC/RFC3339 publication timestamps are required;
- provider-native ticker text/case is preserved;
- article IDs are the deduplication key; conflicting duplicate IDs fail closed;
- raw provider article objects, including optional provider `insights`, are retained as provenance;
- provider `insights` have **NO ALPHA AUTHORITY** during feasibility and may not become historical alpha features unless their point-in-time model/vintage semantics are separately proven before the scientific hypothesis freeze;
- no market outcomes, future closes, directional returns, forward returns, candidate performance, protected outcomes, or alpha rankings may be read during feasibility;
- no broker reads/writes, order writes, PAPER submits, LIVE writes, automation writes, or automatic broker failover.

### Exact non-performance probe windows

These windows are tied mechanically to already-frozen research boundaries rather than chosen from price outcomes:

1. `research_start`: `2021-08-16T00:00:00Z` through `2021-08-16T23:59:59Z`;
2. `development_end`: `2026-05-06T00:00:00Z` through `2026-05-06T23:59:59Z`;
3. `protected_start`: `2026-05-12T00:00:00Z` through `2026-05-12T23:59:59Z`;
4. `protected_end`: `2026-08-11T00:00:00Z` through `2026-08-11T23:59:59Z`.

The probe asks only whether usable contemporaneous news evidence exists and whether its provider contract is internally consistent. Counts are coverage facts, not alpha evidence.

## Feasibility acceptance criteria

The historical-news feasibility work package passes only if all of the following hold on the authorized target machine/account:

1. every exact probe window can be read successfully through the accepted Massive REST adapter;
2. every probe window returns at least one article and at least one ticker-linked article;
3. every retained article has a nonblank provider ID, nonblank title, parseable timezone-aware `published_utc`, and a ticker array;
4. every publication timestamp lies within the exact requested window;
5. provider-native ticker strings are preserved without uppercasing/remapping;
6. repeated article IDs are identical or fail closed as conflicting evidence;
7. pagination completes deterministically and request IDs/page counts are recorded;
8. raw article evidence is written deterministically and hashed;
9. repeated runs over unchanged provider evidence produce the same content hashes;
10. target outcomes/protected returns remain unread;
11. external mutation authority remains zero.

An empty/denied 2021 boundary is a legitimate feasibility failure. ATLAS will not fabricate history, substitute current news, or silently shrink the research interval merely to continue.

## Evidence artifacts

Provider evidence:

`data/provider/massive/phase30_news_feasibility/v1/<window>.jsonl`

Feasibility report:

`data/derived/strategy_evaluation/phase30/v1/phase30_news_feasibility.json`

The report records the feasibility fingerprint, exact windows, article/page counts, timestamp range, ticker-linked counts, evidence SHA-256 hashes, request IDs, and zero outcome/mutation authority.

## What is explicitly NOT frozen yet

**ALPHA HYPOTHESES: NOT YET FROZEN.**

No Phase30 signal family, text transform, event aggregation window, tail/threshold, outcome horizon, cost assumption, bootstrap setting, multiplicity rule, winner rule, or support threshold is defined by this feasibility contract.

That is intentional. Historical field availability and PIT semantics must be established first. Once feasibility passes, Phase30 will freeze a finite scientific contract **before** reading development or protected performance.

Potential fields/ideas mentioned in literature or provider documentation are hypotheses only and carry no authority.

## Post-feasibility scientific freeze

If feasibility passes, the next internal Phase30 work package must freeze, before performance inspection:

- exact article fields allowed for historical features;
- deterministic local text/metadata transforms;
- duplicate/staleness/freshness semantics if used;
- article-to-market-session timing rule using the accepted exchange calendar;
- finite LONG/SHORT hypothesis family;
- exact development/internal/protected chronology and purge/embargo;
- outcome horizon(s);
- realistic costs;
- dependence-aware statistical method;
- multiplicity/selection-bias correction;
- sample/year/regime/concentration/liquidity robustness;
- winner/finalist cardinality and no-runner-up rule;
- independent blindness audit;
- immutable finalist-only protected read plan;
- independent reconstruction and full Phase30 closeout.

Only then may target performance be read.

## Authority

Current Phase30 authority:

- bounded historical Massive news **reads** for feasibility/provenance: ALLOWED;
- local immutable evidence/provenance writes: ALLOWED;
- target outcome reads: FORBIDDEN;
- protected outcome reads: FORBIDDEN;
- provider writes: 0;
- broker reads/writes: 0;
- order writes: 0;
- PAPER submits: 0;
- LIVE writes: 0;
- automation writes: 0;
- automatic broker failover: disabled;
- frontend trading authority: none.

A future positive Phase30 closeout may grant historical analytical `SUPPORTED` authority only and unlock Phase31. It cannot grant PAPER/LIVE authority.
