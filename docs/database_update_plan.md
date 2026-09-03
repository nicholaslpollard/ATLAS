# ATLAS Database Update Plan

**Document type:** Frozen supporting design record; `README.md` and `docs/roadmap.md` are the only living handoff documents
**Status:** SUPERSEDED IN PART BY OPERATOR V1-DECOMMISSION DECISION / SAFETY ORCHESTRATION IN PROGRESS
**Last updated:** 2026-09-03  
**Primary objective:** Replace the active hybrid Alpaca/Massive historical market-data foundation with a clean, newly acquired Alpaca historical foundation. The operator subsequently chose precise local V1 historical-data decommissioning instead of a local archive; repository history, accepted results, and non-historical operational/research state remain preserved.

---

## 1. Why this document exists

ATLAS currently has a validated historical market-data foundation that combines Alpaca and Massive with a historical provider seam. The existing lake has passed substantial price, feature, identity, and seam validation and should not be treated as corrupted. However, the project is moving toward a cleaner long-term architecture for the following reasons:

- one historical provider is simpler to operate and reason about;
- one provider removes the permanent Alpaca/Massive volume-semantic seam;
- Alpaca historical SIP data is available without the recurring Massive historical-data subscription currently being paid;
- future rebuilds and reproducibility should be easier with one acquisition contract;
- the project wants a fresh source-built database rather than additional patches or compatibility layers on top of the current lake;
- the existing hybrid lake can be retained as strong independent validation evidence without becoming ancestry for the new database.

This file preserves the detailed sizing and design record. It is not a third living source of truth. Future continuation state and any changed decision are authoritative only in `README.md` and `docs/roadmap.md`.

---

## 2. Decision summary

### 2.1 New active historical source

The intended replacement historical source is **Alpaca SIP historical market data**, assuming the preflight confirms that Alpaca supplies the required breadth, history, granularities, and corporate-action/identity support needed by ATLAS.

### 2.2 Required base granularities

The replacement generation is not considered base-data complete until both of the following have been built from newly acquired Alpaca data:

1. **Native 1-Day historical bars**
2. **Native 1-Minute historical bars**

The migration may implement/download these internally in stages, but there must be **no manual approval gate between completion of the daily base and beginning of the minute base** once the full rebuild has been started.

The full rebuild runner must continue through both base granularities unless it encounters a real error that makes safe continuation impossible. It must be resumable from checkpoints so a network/API/process interruption does not require restarting the entire acquisition.

### 2.3 Base build before enrichment

The preferred order is:

1. construct the complete new 1-Day base;
2. construct the complete new 1-Minute base;
3. only after both bases exist, complete the additional information, derived datasets, and validation required for promotion.

This ordering is intentional. The initial long-running acquisition/build should not repeatedly stop for scientific review gates between individual data layers.

### 2.4 V1 decommissioning decision (supersedes the original local-archive plan)

The current Alpaca/Massive persisted historical database will be removed locally only through an exact inventory- and hash-bound decommission plan. This decision does not authorize deletion of the entire `data/` root. `data/live`, models, unrelated research state, source code, Git history, accepted-negative evidence, and protected-holdout records must remain intact. V1 market/feature files may not populate V2.

### 2.5 V2 must be source-built, not V1-derived

The replacement database must be constructed from fresh Alpaca provider responses and newly generated manifests/canonical files.

Do **not** populate it by:

- copying old canonical Parquet rows;
- copying old Massive rows;
- copying old feature tables;
- copying old intraday aggregates;
- copying old DuckDB derived state;
- silently carrying forward old provider-seam corrections;
- using V1 values to fill missing V2 values.

Existing ATLAS code may be reused when it is independently appropriate, but persisted V1 market/feature data is not ancestry for V2.

---

## 3. Storage policy and completed preflight

### 3.1 Measured workstation/V1 storage

The read-only storage inventory completed on 2026-09-03 reported:

- total disk: **476.29 GiB**;
- used: **251.23 GiB**;
- free with V1 local: **225.06-225.07 GiB**;
- complete ATLAS `data/` footprint: **148.80 GiB**;
- projected free space if the entire current V1 `data/` tree is moved off the primary disk: **373.87 GiB**.

Major existing V1 components were:

- `derived/features`: **41.00 GiB**;
- `provider/massive`: **29.41 GiB**;
- `canonical/stocks`: **25.89 GiB**;
- `raw/minute_aggs_v1`: **22.68 GiB**;
- `derived/historical_backfill`: **9.40 GiB**;
- `derived/bars`: **7.43 GiB**.

The earlier operator estimate of approximately 400 GB free after moving V1 was directionally close, but the measured result is approximately **373.9 GiB** unless additional non-ATLAS files are moved/removed.

### 3.2 Alpaca 1-Minute empirical sizing result

The bounded Alpaca SIP `1Min`, `adjustment=raw`, `asof=-` storage preflight completed on 2026-09-03 without modifying V1 or configuration files.

Sample evidence:

- daily weighting range: **2016-01-04 through 2026-08-21**;
- canonical daily rows used for weighting: **25,341,368**;
- sample years: **2016-2026**;
- liquidity strata: five buckets from `<$250K` through `$25M+` median daily dollar volume;
- sample per bucket/year: **6**;
- sample windows executed: **32**;
- Alpaca response pages: **120**;
- sampled minute rows: **1,046,094**;
- raw JSON sample: **98.19 MiB**;
- gzip raw-evidence sample: **17.72 MiB**;
- canonical-shape Zstd Parquet sample: **18.27 MiB**;
- gzip storage density: **17.76 bytes/minute-row**;
- Parquet storage density: **18.32 bytes/minute-row**.

Weighted estimate:

- projected native 1-minute rows: **3,781,281,073**;
- projected native 1-minute canonical Parquet: **64.51 GiB**;
- projected Alpaca raw 1-minute gzip evidence: **62.55 GiB**;
- native 1-day planning allowance: **755.93 MiB**;
- inferred native 1-minute canonical scale versus V1: **2.555x**.

### 3.3 Conservative full-package estimate

The intentionally non-optimized planning model, which scales normal ATLAS layers rather than making V2 artificially compact, produced:

- native/raw/daily/derived/features persistent planning: **270.07 GiB**;
- ancillary allowance (15%): **40.51 GiB**;
- transient build/validation reserve: **35.00 GiB**;
- estimated V2 migration peak: **345.58 GiB**;
- separate post-build free-space reserve: **30.00 GiB**;
- total free capacity required under this conservative policy: approximately **375.58 GiB**.

Disk verdicts:

- **V1 retained locally:** 225.07 GiB free -> **NO-GO**;
- **V1 moved externally:** 373.87 GiB free -> **NO-GO under the conservative full-package rule**.

The second NO-GO is extremely close: approximately **1.71 GiB short** of the modeled peak plus the 30 GiB safety reserve. This must not be rounded into a GO because the 3.78-billion-row result is an empirical estimate, not an exact final byte count. A margin of only ~1.7 GiB is operationally unsafe.

### 3.4 Important distinction: native base build versus complete post-base V2 package

The operator explicitly wants the long-running initial job to build both native bases completely first, and only then proceed with additional enrichment/validation work.

The measured native-base storage is much smaller than the conservative complete-package projection:

- projected native 1-minute canonical: **64.51 GiB**;
- projected raw 1-minute evidence: **62.55 GiB**;
- projected native 1-day allowance: **~0.74 GiB**;
- combined native base + raw evidence planning: approximately **127.8 GiB**, before small manifests/checkpoints and transient partition-building overhead.

Therefore:

- the complete native 1d + 1m source/canonical base is expected to fit after V1 is moved externally with substantial headroom;
- it may even fit in the current 225 GiB free space, but keeping V1 local is **not** the recommended launch configuration because it leaves much less failure/retry/temporary headroom and does not solve the later complete-package constraint;
- the safest current architecture is to move/seal V1 externally before launching the full native base rebuild;
- after both native bases are complete, derived bars/features/enrichment can be built in controlled post-base phases while exact V2 sizes replace the preflight estimates.

This staged execution does **not** weaken the final V2 requirement. V2 is not promoted until the complete required package and validation pass. It only respects the operator's requested order: build both authoritative native bases first, then add/validate the rest.

### 3.5 Storage decision going forward

The project should not launch the full final V2 package on the primary disk with only the measured 373.87 GiB free and assume it will fit. To meet the operator's requirement that V2 fit in totality without relying on space-efficiency tricks, one of the following must be true before the post-base full package is completed:

1. free additional primary-disk capacity beyond the 373.87 GiB projection (targeting a meaningful margin, not merely 1-2 GiB); or
2. use a larger/new primary data volume for V2; or
3. after the native bases are built and exact storage is known, re-run the full-package projection and demonstrate that actual storage is materially below the conservative estimate.

The operator has explicitly authorized precise V1 historical-data deletion as part of this clean rebuild. Deletion remains fail-closed: exact allowlisted targets, byte/file inventory, content fingerprints, path and symlink validation, a matching confirmation token, and a passing disk preflight are required. A broad recursive deletion of `data/` is prohibited.

---

## 4. Isolation requirements

The old and new generations must be physically and logically isolated.

Recommended conceptual layout:

```text
ATLAS data root
├── archive/
│   └── hybrid_alpaca_massive_<freeze-date>/
│       └── V1 files, read-only
│
└── v2_build/
    ├── source/
    ├── canonical/
    │   ├── daily/
    │   └── minute/
    ├── derived/
    ├── manifests/
    ├── checkpoints/
    └── validation/
```

Exact paths should be chosen to match the repository/config architecture, but the following invariants are mandatory:

- active V2 globs must never include V1 archive paths;
- V1 must not be writable by V2 migration tooling;
- V2 acquisition must not fall back to V1 on provider failures;
- comparison tooling must write results to a separate validation namespace;
- production promotion must be an explicit path/config switch after acceptance rather than a directory merge.

---

## 5. Historical data architecture

### 5.1 Native bases

Store two authoritative provider-native historical bases:

- Alpaca SIP native **1-Day**
- Alpaca SIP native **1-Minute**

Do not create the authoritative daily history by aggregating 1-Minute bars. The native 1-Day and native 1-Minute products should each be acquired from Alpaca under frozen request semantics.

### 5.2 Higher intraday timeframes

ATLAS historically uses intraday intervals such as 15-minute, 1-hour, and 4-hour bars. These should be deterministically derived from the canonical 1-Minute base under one explicitly documented aggregation/session policy.

The migration plan must decide which higher-timeframe datasets are materially persisted versus reproducibly generated/cached, but this decision must not alter the preflight requirement to determine whether the complete intended system fits under the normal straightforward design requested by the operator.

### 5.3 Corporate actions

The raw provider observations and analytical continuity requirements must be clearly separated.

The rebuilt system must have an explicit corporate-action representation sufficient to correctly handle at least:

- splits;
- reverse splits;
- stock dividends where relevant;
- cash dividends where required by a strategy/return definition;
- spin-offs where relevant;
- symbol changes;
- mergers/delistings/lifecycle events as available/required.

Raw execution prices must not be confused with research-adjusted continuous series.

### 5.4 Identity and ticker lifecycle

A one-provider rebuild does **not** eliminate the need for ATLAS instrument identity.

The existing audits demonstrated that ticker text alone does not prove company identity; ticker reuse and inactive/legacy assets remain real issues even when querying Alpaca.

The rebuild must preserve or re-establish correct point-in-time instrument identity without copying V1 market rows into V2.

---

## 6. Live/PAPER data separation

The historical rebuild is independent from the intended live/PAPER streaming path.

Current project direction is that **Webull is the primary PAPER/intended LIVE broker**, with real-time/current data intended to be obtained through the broker's supported streaming capability (WebSocket/MQTT or the final accepted Webull streaming integration).

Before implementation of the live path, re-check the latest accepted ATLAS broker/market-data architecture and current Webull API capability. Do not silently assume that the historical Alpaca source must also become the live streaming source.

The desired architectural separation is:

```text
Historical/research
Alpaca SIP -> canonical historical lake -> features/backtests

Current/PAPER/LIVE
Webull streaming -> live market state -> current features -> decisions/execution
```

Historical Alpaca and live Webull data should ultimately normalize into compatible ATLAS schemas, while retaining provider/source metadata so differences remain observable.

---

## 7. Rebuild execution contract

The full rebuild should eventually be launched by one operator command or one top-level orchestrator.

Once the operator starts the full build, the process should continue automatically through the complete base-data build:

```text
PRECHECK
  -> NEW ALPACA 1-DAY ACQUISITION
  -> 1-DAY CANONICAL BUILD
  -> NEW ALPACA 1-MINUTE ACQUISITION
  -> 1-MINUTE CANONICAL BUILD
  -> BASE DATA BUILD COMPLETE
```

There must be no normal conversational/manual gate between daily completion and minute acquisition.

### 7.1 Failure behavior

The long-running job must:

- checkpoint durable progress;
- use bounded retries/backoff for recoverable API/network failures;
- obey provider rate limits;
- be restart-safe;
- never overwrite accepted V1;
- never silently skip permanently failed symbols/periods;
- record unresolved failures explicitly;
- resume from completed partitions/pages rather than begin again where practical;
- fail safely if available disk approaches the reserved floor.

A failed run should leave a coherent resumable V2 candidate, not a partially promoted active database.

### 7.2 No premature promotion

Completing 1-Day and 1-Minute base construction does **not** automatically make V2 active production data.

Promotion occurs only after enrichment/validation and acceptance are complete.

---

## 8. Post-base enrichment and validation

After both native base granularities have been fully constructed, complete the additional work needed for acceptance.

Expected work includes, subject to final implementation design:

1. corporate-action acquisition/reconciliation;
2. point-in-time identity/lifecycle reconstruction;
3. exchange/session/calendar validation;
4. derivation of required 15m/1h/4h datasets;
5. regeneration of historical features from V2 source data;
6. regeneration of dependent regime/model/research state where required;
7. structural integrity tests;
8. price/volume sanity tests;
9. corporate-action sentinel tests;
10. inactive/delisted/ticker-reuse tests;
11. historical strategy/replay regressions needed to prove the new data path works;
12. explicit source/provenance manifests and final fingerprints.

Do not carry forward old derived feature values merely to avoid recomputation.

---

## 9. Use of V1 for validation

V1 is valuable as independent evidence and should be used only after V2 has been built from Alpaca.

Permitted direction:

```text
V1 read-only ----\
                  -> comparison validator -> reports only
V2 read-only ----/
```

Forbidden direction:

```text
V1 rows/features -> V2 population
```

Expected comparisons include:

### 9.1 Former Alpaca historical segment

For the period historically sourced from Alpaca, newly acquired Alpaca data should strongly reproduce the old Alpaca observations under equivalent request semantics, with differences investigated rather than silently reconciled.

### 9.2 Former Massive historical segment

For the period historically sourced from Massive:

- price-derived data should be expected to match very closely based on prior audits;
- volume need not match exactly because the completed provider-seam audits demonstrated systematic Alpaca/Massive volume-semantic differences;
- V2 should use Alpaca semantics consistently rather than attempting to make Alpaca volume imitate Massive.

### 9.3 Existing validation evidence to preserve

Prior audits established that the current hybrid lake itself is not known to be corrupt. Among the important historical findings to preserve in project history:

- ordinary overlap prices matched extremely closely;
- major split-window raw price behavior matched between Alpaca and Massive;
- a stratified 60-symbol provider-seam audit showed near-identical non-volume feature behavior and zero accepted-model argmax changes;
- provider volume differed systematically and is one reason a single-provider historical foundation is desirable;
- Alpaca returned historical bars for all tested legacy sentinels, while inactive-asset metadata was not sufficient by itself to prove identity/lifecycle;
- ticker reuse remains a real PIT identity concern.

The rebuild does not invalidate those findings.

---

## 10. Acceptance criteria framework

Exact thresholds must be frozen before final validation, but acceptance should require at minimum:

### Source/provenance

- V2 canonical historical bars contain only the intended Alpaca historical source.
- Request semantics, acquisition dates, provider/feed, adjustment mode, pagination, and manifests are durable and reproducible.
- No Massive rows are present in V2.

### Structural integrity

- zero duplicate canonical instrument/timestamp keys;
- valid OHLC geometry;
- valid timestamps/sessions;
- nonnegative/valid volume according to schema;
- malformed or missing partitions explicitly accounted for;
- no silent unresolved provider failures.

### Coverage

- full required history beginning at the accepted earliest Alpaca date;
- broad market universe coverage meeting the frozen ATLAS universe policy;
- inactive/legacy history appropriately represented where provider data exists;
- daily and minute coverage reports by year/session/symbol.

### Identity

- ticker reuse does not join unrelated issuers into one continuous instrument history;
- known legacy/symbol-change sentinels behave correctly;
- current ticker text is not treated as sufficient identity proof.

### Corporate actions

- known split/reverse-split sentinels reconcile correctly;
- raw versus adjusted analytical semantics are explicit;
- no false price crashes/jumps are introduced into research returns simply because of corporate actions.

### Derived data

- deterministic higher-timeframe aggregation is validated;
- historical features are rebuilt from V2;
- feature/replay regressions pass under the new source semantics or documented differences are scientifically explained and accepted.

### Isolation

- V1 remains unchanged;
- V2 fingerprint/manifests prove it was source-built;
- no V1 market/feature rows are included in V2.

---

## 11. Promotion and rollback

Only after complete acceptance:

1. freeze the accepted V2 fingerprint/manifests;
2. switch active configuration/path aliases to V2;
3. run exact-head acceptance/regression tests on the active configuration;
4. preserve a simple rollback pointer to V1 while V1 remains archived;
5. document the promotion in `docs/current_status.md` and the roadmap/status location used by the active ATLAS branch.

Do not merge V1 and V2 directories.

---

## 12. Superseded V1 retention alternatives

The following were considered before the operator selected precise local decommissioning:

Possible later outcomes:

- retain all V1 on the primary disk;
- move all V1 to external/archive storage;
- retain only canonical/source/manifests and remove reproducible derived V1 artifacts;
- delete selected V1 data only after explicit operator approval and only when validation/provenance needs are satisfied.

Current decision: the orchestrator may delete only its frozen allowlisted V1 historical targets after inventory drift, symlink/path, confirmation-token, and disk checks pass. It may never delete the complete `data/` root.

---

## 13. Immediate next implementation steps

Storage inventory and empirical 1-minute sizing are complete. The first orchestration safety slice is implemented. The operator explicitly accepted a database-only decommission mode to reclaim space before V2 acquisition exists, with the understood result that ATLAS will temporarily have no historical database. The combined delete-and-rebuild path remains locked until acquisition, canonicalization, identity/corporate-action, validation, and resume stages are implemented.

### Step A — COMPLETE: repository/current-state reconciliation

The migration plan, accepted historical backfill/audit code, and current data paths were reviewed before the preflight tooling was added.

### Step B — COMPLETE: read-only storage inventory

Measured V1 and disk footprint are recorded in Section 3.

### Step C — COMPLETE: Alpaca 1-Minute empirical scale sample

Measured provider row density and normal raw/Parquet storage are recorded in Section 3.

### Step D — COMPLETE: conservative peak-space projection

The native base is projected to fit comfortably with V1 external. The complete non-optimized V2 package misses the measured post-V1 internal capacity by approximately 1.71 GiB after the required 30 GiB reserve, so it is not accepted as a final whole-package GO yet.

### Step E — IN PROGRESS: implement/test resumable V2 base rebuild orchestrator

Requirements:

- entirely new V2 namespace — implemented;
- fresh Alpaca SIP source acquisition;
- native 1d acquisition/build followed automatically by native 1m acquisition/build;
- resumable/checkpointed partition units;
- bounded retry/backoff;
- permanent failure accounting;
- disk-floor monitoring — initial 30 GiB reserve guard implemented;
- no V1 writes or fallback — path/decommission foundation implemented;
- no manual gate between 1d and 1m;
- bounded end-to-end rehearsal before the real run.

### Step F — operator storage preparation and exact V1 decommission

Before the real base run, generate and review the exact hash-bound V1 historical decommission plan. Execution requires its derived confirmation token and a passing projected post-decommission base-space check. Preserve live/model/unrelated research state and never recursively delete `data/`.

### Step G — full operator base run

Provide one command that begins the complete base rebuild and automatically proceeds through both native 1-Day and native 1-Minute construction.

### Step H — exact post-base remeasurement and enrichment

After both bases are built:

1. measure actual raw/canonical V2 bytes and row counts;
2. replace the estimated 3.78B-row storage projection with exact measurements;
3. re-project the final derived/features/enrichment footprint;
4. confirm sufficient final-package space;
5. build corporate actions/PIT identity, derived bars, features, validations, and acceptance artifacts;
6. promote only after the full package passes.

---

## 14. Operating principle for future chats

Do not reopen the question of whether the current hybrid database is "corrupt" without new evidence. Existing audits indicate that it is scientifically usable and strongly validated.

The motivation for this rebuild is **architectural simplification and long-term source consistency**, not an attempt to erase failed evidence or claim the old lake was invalid.

Future work should optimize for:

**fresh source-built data -> one historical provider -> complete daily + minute bases -> explicit identity/corporate-action semantics -> rigorous validation -> one promoted active lake**

while keeping the research/product work moving and avoiding a return to indefinite data-source gates.

---

## 15. Decision log

### 2026-09-03

- Operator chose to proceed with planning for a clean Alpaca historical rebuild.
- Original decision was to archive the hybrid database; the later explicit operator decision supersedes this with precise local V1 historical decommissioning while preserving repository/evidence lineage and non-historical state.
- New generation must be built fresh from Alpaca; V1 is validation-only.
- New generation is expected to include both native 1-Day and native 1-Minute bases before base construction is considered complete.
- Full-run orchestration should not stop for a manual gate between daily and minute construction.
- Initial sizing must not depend on aggressive space-efficiency changes.
- Read-only inventory measured V1 at 148.80 GiB and primary-disk free space at 225.06-225.07 GiB.
- Moving the full V1 `data/` tree externally is projected to raise primary-disk free space to 373.87 GiB.
- Empirical Alpaca SIP 1-minute sampling measured 1,046,094 minute rows and estimated the full historical minute base at 3,781,281,073 rows.
- Estimated native 1-minute canonical storage is 64.51 GiB; raw gzip evidence is 62.55 GiB; native 1-day allowance is ~0.74 GiB.
- Conservative non-optimized full-package peak is 345.58 GiB plus a separate 30 GiB free-space reserve, requiring approximately 375.58 GiB.
- V1-local is a clear NO-GO for the complete package.
- V1-external at 373.87 GiB is also a formal NO-GO for the complete package because it is ~1.71 GiB below the conservative requirement and has effectively no estimation-error margin.
- The native 1d+1m base itself is expected to fit comfortably once V1 is moved externally, so the migration will honor the requested base-first execution order and remeasure exact storage before post-base enrichment.
- Post-base corporate actions, identity, higher timeframes, features, and final validation remain mandatory before promotion.
- Webull remains the intended primary PAPER/LIVE broker and live/current streaming path is kept architecturally separate from historical Alpaca acquisition, subject to final verification against the active broker/data architecture before implementation.
