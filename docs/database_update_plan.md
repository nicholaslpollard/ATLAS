# ATLAS Database Update Plan

**Document type:** Living implementation and handoff plan  
**Status:** PLANNING / PRE-MIGRATION  
**Last updated:** 2026-09-03  
**Primary objective:** Replace the active hybrid Alpaca/Massive historical market-data foundation with a clean, newly acquired Alpaca historical foundation, while retaining the current database as an isolated read-only archive until the replacement is fully accepted.

---

## 1. Why this document exists

ATLAS currently has a validated historical market-data foundation that combines Alpaca and Massive with a historical provider seam. The existing lake has passed substantial price, feature, identity, and seam validation and should not be treated as corrupted. However, the project is moving toward a cleaner long-term architecture for the following reasons:

- one historical provider is simpler to operate and reason about;
- one provider removes the permanent Alpaca/Massive volume-semantic seam;
- Alpaca historical SIP data is available without the recurring Massive historical-data subscription currently being paid;
- future rebuilds and reproducibility should be easier with one acquisition contract;
- the project wants a fresh source-built database rather than additional patches or compatibility layers on top of the current lake;
- the existing hybrid lake can be retained as strong independent validation evidence without becoming ancestry for the new database.

This file is the authoritative living handoff for the database migration. Future ATLAS chats should read this file before changing the migration design or executing database-rebuild work.

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

### 2.4 V1 preservation

The current Alpaca/Massive database generation will be retained initially as a **sealed read-only archive**.

It may be read by comparison/validation tools after the new base is built, but it must never be used as a source for populating the replacement database.

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

## 3. Storage policy and preflight requirement

### 3.1 Current operator storage

At planning time the workstation has approximately:

- **476 GB total disk capacity**
- **225 GB currently free**

If the archived current database is moved to external storage, the operator expects approximately **400 GB free** on the primary disk.

These values are planning inputs only and must be re-measured immediately before migration.

### 3.2 Full-size estimate required before starting the rebuild

Before the long-running rebuild command is authorized, ATLAS must estimate whether the **entire intended replacement generation fits**, including 1-Day and 1-Minute data, without relying on later space optimizations to make the plan work.

The preflight should conservatively account for peak simultaneous usage from:

- archived V1 data remaining on the primary disk;
- new raw/staging acquisition files if retained by the acquisition design;
- new canonical native 1-Day data;
- new canonical native 1-Minute data;
- manifests/checkpoints;
- temporary build artifacts;
- corporate-action/identity artifacts required after base acquisition;
- derived higher timeframes required by ATLAS;
- regenerated features/state required for acceptance;
- validation/comparison outputs;
- a free-space safety reserve.

The first estimate should reflect the intended straightforward storage design. Do not make the project appear to fit only by introducing aggressive compression, pruning, data-type reduction, selective-universe reduction, or deletion of required data.

### 3.3 Empirical minute-data sizing

Because full-universe 1-Minute history can be orders of magnitude larger than daily history, do not extrapolate from daily row counts alone.

Before the full build, use a representative Alpaca 1-Minute sample to measure at minimum:

- rows returned;
- compressed bytes written using the intended normal Parquet/schema implementation;
- bytes per row;
- symbol/session coverage;
- expected historical universe size by period;
- estimated final canonical 1-Minute size;
- estimated peak migration footprint.

The estimate must be written to a durable preflight report.

### 3.4 Storage decision

Use the following decision policy:

- If the complete replacement plus V1 archive and safety reserve fit comfortably with the current free space, keep V1 on the primary disk during migration.
- If the complete replacement does not fit comfortably while V1 remains local, move the sealed V1 archive to external storage **before** starting the full rebuild.
- If approximately 400 GB free still cannot safely accommodate the projected peak footprint, stop before the full rebuild and revise the physical-storage plan. Do not begin a job expected to exhaust the disk.

No V1 deletion is authorized merely to make the first estimate look better. Deletion of old data is a post-promotion decision unless the operator explicitly approves another action after reviewing the storage evidence.

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

## 12. Post-promotion V1 retention/deletion policy

After V2 has been accepted and operated successfully, review the actual value of continuing to retain V1 locally.

Possible later outcomes:

- retain all V1 on the primary disk;
- move all V1 to external/archive storage;
- retain only canonical/source/manifests and remove reproducible derived V1 artifacts;
- delete selected V1 data only after explicit operator approval and only when validation/provenance needs are satisfied.

No automatic deletion is part of the migration.

---

## 13. Immediate next implementation steps

The next database-migration work should be limited to preflight and orchestration preparation. Do not start the full historical download until the size estimate is accepted.

### Step A — Repository/current-state reconciliation

Before coding, re-read:

- this document;
- `docs/current_status.md`;
- `docs/roadmap.md`;
- current README/data-provider documentation;
- accepted historical backfill/audit scripts and evidence;
- current active Review/Product branch changes that may affect data paths.

### Step B — Read-only storage inventory

Create/run a read-only tool that reports exact bytes by major V1 category and current disk free space.

At minimum report:

- raw/source market data;
- canonical daily;
- canonical minute/intraday;
- derived timeframes;
- features;
- DuckDB/state databases;
- research/audit caches;
- total V1 footprint;
- current free bytes.

### Step C — Alpaca 1-Minute empirical scale sample

Create/run a bounded read-only/sample acquisition that does not modify V1. Write to an isolated temporary V2/preflight location and measure normal on-disk size using the intended schema/Parquet implementation.

### Step D — Peak-space projection

Produce a durable report estimating:

- new daily size;
- new minute size;
- additional required V2 artifacts;
- expected temporary peak;
- required safety reserve;
- peak with V1 retained locally;
- peak with V1 moved externally;
- GO/NO-GO recommendation.

### Step E — Only after storage GO

Implement/test the resumable top-level V2 rebuild orchestrator and a small end-to-end bounded sample.

### Step F — Full operator run

Provide the operator one command that begins the complete base rebuild and automatically proceeds through both native 1-Day and native 1-Minute construction.

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
- Current hybrid Alpaca/Massive database will be archived initially rather than deleted.
- New generation must be built fresh from Alpaca; V1 is validation-only.
- New generation is expected to include both native 1-Day and native 1-Minute bases before base construction is considered complete.
- Full-run orchestration should not stop for a manual gate between daily and minute construction.
- Full projected storage footprint must be determined before the full rebuild starts.
- Initial sizing should not depend on aggressive space-efficiency changes.
- Current planning free space is ~225 GB; moving V1 externally is expected to increase free space to ~400 GB if needed.
- Post-base corporate actions, identity, higher timeframes, features, and final validation may be completed after both native bases have been constructed.
- Webull remains the intended primary PAPER/LIVE broker and live/current streaming path is kept architecturally separate from historical Alpaca acquisition, subject to final verification against the active broker/data architecture before implementation.
