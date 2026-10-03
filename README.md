# ATLAS

**Autonomous Trading, Learning, and Analysis System**

**Current as of 2026-09-27 (UTC). The root README, `docs/roadmap.md`, and
`docs/strategy_evidence_register.md` are the three living project documents. Every
continuation chat must read all three in full before making recommendations or changes.**

ATLAS is the greenfield successor to Chart Monitor. Its purpose is to become a
usable quantitative trading platform that can discover and compare opportunities,
run faithful historical replays, construct risk-controlled trades, operate end to
end with PAPER money, record outcomes, show the operator what is happening, and
improve its strategy library without hindsight or silent self-modification.

Profit is an objective, never a guarantee. Activity, alerts, attractive charts, and
profitable backtests are not substitutes for positive expected value after costs,
controlled risk, prospective evidence, and reliable operation.

### Active MarketData accepted 2025 source pilot — COMPLETED 2026-09-26

PRs #229–#235 are merged. Twelve outcome-blind accepted 2025 DEVELOPMENT daily LONG stock opportunities were bound to twelve immutable, prior-session EOD historical chain queries. Stock source SHA-256 `e7d90ce3162475ecbfc442d35e0ffbca18fca38434e658b0ee8bd7633021362e`; frozen plan fingerprint `a830ab16e6ebce9b509ec88efad8b6c8e08e2951db8682aa8d5e34ffc96886e1`. The data/options and research/evidence directories resolve through verified junctions to the D: secondary SSD; ATLAS runtime and accepted Alpaca SIP V2 stock corpus remain on C:.

Original AGIO raw evidence was recovered offline and four subsequent chains completed. FSLY's original 2025-04-09 / 2025-05-16 / $5.14–$6.04 request returned HTTP 404, provider `s=no_data`, zero rows and provider-reported zero consumed credits; its raw body, original quarantine receipt and attempt remain immutable. Separately verified FSLY proof fingerprint `6d2e3d17fbcb0f39d88af9ed025d71757c84e97ac00b75d130d189c6ac0f083f` classifies this *exact query* as source noncoverage, not broader option absence. The final six untouched requests then completed in one bounded batch, reporting six additional consumed credits and last remaining 9989.

**Current independently verified physical status: 11 complete chain source receipts / 1 exact-query FSLY no-data / 0 pending.** Terminal CLI `status=PREVIEW` is the independent zero-provider-read receipt reconciliation after completion, not a pending acquisition. The original failed-run checkpoint remains historical evidence, not current receipt status. The frozen pilot is closed; do not re-request FSLY or attempt further pilot calls.

**Source closeout accepted; next point-in-time structural CALL shortlist:** the local, read-only-first source closeout independently revalidates original receipts/proof and computes observed CALL/PUT structural counts for each request, without copying provider raw bodies or selecting an executable contract. Later contract identity/deliverable and quote-history acquisition are separate preregistered and provider-authorized work. No historical option fill/P&L, strategy, PAPER, LIVE, broker/order or promotion authority is granted. Provider-specific licensing and retention limits still apply.

### Retained Czar28 historical-options challenger (not simulator critical path)

The broad Massive Historical Option Reference V7 contract remains preserved, but its
current Basic-tier provider continuation is operationally paused after a resumed run
issued 477 request starts at the enforced 5 requests/minute budget over roughly
1.5–2 hours while all first five provider partitions remained incomplete. This is a
throughput finding, not a scientific rejection of V7 or its preserved evidence.

The active source gate is now the separately frozen
`atlas-czar28-historical-option-source-qualification-v1`. It uses the user's free
Czar28/PublicOptions key only through read-only documented endpoints and may consume
up to the full 1,000-request monthly Free allowance under an explicit second CLI
gate. The deterministic matrix covers 30 durable US option roots across June monthly
expirations for every anchor year 2016..2026, representative 90-day EOD contract
histories, bounded one-day intraday quotes and trades, intentional repeatability
checks, and useful March/September fill probes if quota remains. Every completed
probe is preserved with a hash-bound receipt and is reusable after restart. Local
pacing is capped at 55 requests/minute and provider remaining-quota headers stop the
run at zero. Czar28 remains candidate-only until workstation evidence and later
cross-provider price validation pass. The documented Czar28 EOD schema does not
supply open interest; OI remains a separately versioned future overlay study.

The first workstation execution stopped after its first logical chain probe because
Czar28 returned HTTP 502 `upstream_error`; no chain/EOD coverage conclusion was
opened from that run. Czar documents 5xx responses as uncached and safe to retry with
the same idempotency key. The client now retries HTTP 500/502/503/504 and transient
URL transport failures with bounded exponential backoff while preserving the same
logical probe/idempotency key. Retry attempts are reported separately from logical
qualification calls. The frozen qualification contract and authority boundary are
unchanged.


A separate operational preflight now runs before any further full-quota attempt. It
checks the documented Czar health endpoint, a current SPY monthly chain, a recent
expired SPY monthly chain, the 2016 SPY monthly chain, and a direct 2016 SPY $200C
EOD query. This distinguishes a
provider-wide outage from a deep-history-only failure before ATLAS spends the
remaining monthly quota. The full qualifier also now prints phase transitions,
10-call live heartbeats, current probe identity, rows returned, elapsed time,
remaining quota, recovered retry events, and correct physical HTTP-attempt counts
including failed probes.

### Czar28 provider-health evidence and recovery gate — 2026-09-23

The user's Czar28 dashboard showed the Free plan active, one active read-only key,
and seven requests counted, confirming that ATLAS requests reached Czar's service.

Direct health checks on the apex service returned a structured degraded payload with
`status=degraded`, `upstream.mdds_status=UNDETERMINED`, and upstream message
`ERROR CODE: 1033`. This is operational evidence that the options-history upstream
was degraded at the time of testing; it is **not** evidence that the required
2016..2026 historical option corpus is absent.

Czar28's current official surfaces disagree on the global Production host: OpenAPI
1.2.0 declares `https://czar28.com`, while the human Servers table identifies
`https://api.czar28.com/v1` for live authenticated traffic. The health operation is
public in OpenAPI and the human health example also uses the apex host without an
Authorization header.

ATLAS therefore freezes role-specific routing rather than claiming either source
globally supersedes the other: authenticated chain/EOD/intraday/trade requests use
`https://api.czar28.com/v1`, while public health uses
`https://czar28.com/v1/options/health`. The qualification remains fail-closed unless
public health is explicitly `status=ok` **and**
`upstream.mdds_status=CONNECTED`. A degraded, disconnected, undetermined, malformed,
or unreachable health response blocks all quota-consuming qualification calls.

Once health recovers, the required next step remains the bounded five-probe preflight:
health -> current SPY chain -> recent expired SPY chain -> 2016 SPY chain -> direct
2016 SPY $200C EOD. The 1,000-call qualification remains blocked until that corrected
preflight succeeds or yields a bounded deep-EOD/chain-limitation result.

A quota-free public health watcher is available while the provider is degraded:

~~~powershell
.\.venv\Scripts\python.exe scripts\watch_czar28_health_v1.py
~~~

It checks at 60-second intervals by default, prints state changes plus periodic
heartbeats, consumes no Czar API-key quota, and exits only when public health is
explicitly `status=ok` and `mdds_status=CONNECTED`. The next action after that
exit is the existing five-probe preflight, not the 1,000-call qualification.


### Active unblocking path — MarketData.app five-year options V1

ATLAS will no longer let ten-year option-source perfection block simulator
development. The active paid challenger is
`atlas-marketdata-five-year-historical-options-v1`, targeting the MarketData.app
Starter plan at $30 month-to-month.

The current documented Starter entitlement provides 10,000 API credits/day and a
rolling five-year historical window. Historical option-chain requests with a date
parameter are billed at one credit per 1,000 returned contracts; historical
single-contract quote series are billed at one credit per 1,000 quote rows. The
provider exposes historical bid/ask/mid/last, volume, open interest, underlying
price, OCC symbol, strike/expiration/side and timestamps. Historical IV/Greeks are
not stored and are expected null.

This source is intended to unlock **five-year EOD option economics plus OI** for
candidate-first simulation. It is not a whole-market bulk-download authorization.
ATLAS will query only PIT stock opportunities already produced by the research
pipeline, restrict DTE/strike range server-side, select contracts under a separately
frozen rule, and download short EOD quote paths only for selected contracts.

Point-in-time semantics remain explicit: historical OI on date D is the value
settled from D-1 and available before D opens; bid/ask/last/underlyingPrice and
volume are EOD-D observations. Full-session D volume is therefore unavailable to an
intraday-D decision. Provider data is as-traded and not corporate-action adjusted;
corporate-action-sensitive/non-standard cases remain fail-closed unless separately
resolved.

Massive Historical Option Reference V7 remains preserved but its 5-calls/minute
Basic-tier continuation is **not on the simulator critical path**. Czar28 remains
the low-cost ten-year challenger/backfill path after its upstream health recovers.

The first MarketData qualification is intentionally small: six anchors from
2021-10-01 through 2026-09-01 across SPY/AAPL/MSFT/NVDA/QQQ, each using a restricted
historical chain and a ten-day quote series for one selected contract. Passing that
gate creates challenger-source evidence only; cross-provider validation and a
separate simulator adapter remain required.

The original **Starter Trial** was used before paid activation. Trial mode
(`--starter-trial`) exploits the documented full-history AAPL exception for
a 2021-10-01 deep probe and uses SPY/MSFT/NVDA/QQQ anchors inside the trial's normal
one-year limit. This can prove endpoint/schema/OI/quote-series mechanics without
spending $30, but it cannot prove broad five-year entitlement for non-AAPL symbols.
The paid six-anchor gate was separately executed and accepted on 2026-09-25.

The workstation Starter Trial qualification has now **PASSED** under run id
`20260923T203419Z` / evidence fingerprint
`facd9289fc56279a14294c442f8a1f256388cfd152662be1bc06f600d1bf914a`.
All five anchors returned non-empty chains and quote histories, OI, usable bid/ask,
required schema and the expected historical-Greeks-null behavior. It consumed only
8 observed API credits and ended at 9,992 remaining. This accepts MarketData as a
**qualified Starter-Trial capability source**, not as five-year historical-price
authority.

The paid **Starter five-year qualification has now PASSED on its first workstation
run**, `20260925T182731Z` / evidence fingerprint
`f7a0c78e6812e59bf1b7efd243ce9c66c0325aa7241fd5a46868b3fc2224747a`.
All six frozen anchors from 2021-10-01 SPY through 2026-09-01 SPY returned
nonempty restricted chains and selected-contract quote series (96 chain rows,
50 quote rows total). Required schema, OI, usable bid/ask and expected null
historical Greeks passed; the oldest non-AAPL SPY history was available.
Observed consumption was 10 credits, with 9,990 remaining at the last header;
there was no terminal error. The original workstation report/raw SHA receipts
are retained under
`data/research/provider_qualification/marketdata_app/historical_options_v1/20260925T182731Z/`.

This **closes the sampled paid-plan entitlement/source gate**, not exhaustive
contract coverage and not intraday/execution/option-P&L authority. With the
external-storage architecture merged and the secondary SSD bindings READY, the next
engineering package is a bounded **candidate-first acquisition and cache
adapter** driven by PIT stock opportunities. No whole-universe options download
is authorized. Earlier source-validation failure verdicts remain immutable;
sparse-activity V2 is frozen and still has no workstation result.

Accepted run record:
`docs/research/marketdata_paid_starter_acceptance_v1_20260925.md`.

The first independent overlap calibration is now complete under run id
`20260923T205206Z` / evidence fingerprint
`b10d6d8eb2f3bfcb9fa9dad5623d1eb56297bec5222922b2b8f2302fe5324f3a`.
All four 2026 contracts produced full date overlap: 31 overlapping sessions total,
77.419355% exact MarketData-last / Massive-close matches, zero aggregate median
absolute last-close difference, and 100% of MarketData historical last values inside
Massive's independent daily low/high range. Aggregate median relative volume
difference was 0.065284%; the maximum observed session relative volume difference was
14.213836%. No terminal error occurred.

That calibration does not itself grant price authority. Its purpose was to learn the
cross-vendor semantics before freezing a decision rule.

The preregistered disjoint validation has now **FAILED** under run
`20260923T211759Z` / evidence fingerprint
`2ab5dc3012bdbda388e6d2648403814999c54aa9ac0d4184295c595072eea145`.
IWM, AMZN and META passed every frozen anchor criterion. DIA failed only the overlap
requirements: MarketData returned 9 EOD rows while Massive returned 4 daily aggregate
bars, producing 4/9 overlap. On those four overlapping DIA sessions, last/close
median disagreement was 0%, volume median disagreement was 0%, and MarketData last
was inside Massive's daily low/high 100% of the time. The aggregate price/volume
median checks also passed, but V1 required all four anchors and therefore remains a
real failed validation. Its thresholds will not be widened and V1 will not be rerun.

Failure closeout:
`docs/research/marketdata_massive_disjoint_validation_v1_closeout_20260923.md`.

Massive's current aggregate semantics allow a daily interval to be absent when no
qualifying trade exists, so the active next gate is a separately versioned **DIA
aggregate-gap diagnostic**, not a retroactive reinterpretation of V1. It reuses the
accepted local raw evidence, makes zero MarketData calls, and checks Massive raw
trades plus option trade-condition update rules for each DIA date missing a daily
bar. The original V1 remains failed regardless of the diagnostic outcome.

Diagnostic contract:
`docs/research/marketdata_massive_dia_gap_diagnostic_v1_20260923.md`.

The first workstation execution of that raw-trade diagnostic is preserved as
**DIAGNOSTIC_INCOMPLETE**, run `20260923T222933Z` / evidence fingerprint
`48d58cecf4d084f241f8b6b008454427389be609c18d42ffcdcb318a12be4e6a`.
The condition-metadata request succeeded with 33 rows, but the first historical
raw-options-trades request for 2026-08-06 returned HTTP 403. Current Massive plan
documentation confirms that `/v3/trades/{optionsTicker}` is not included in Options
Basic or Starter and begins at Options Developer. The V1 diagnostic is therefore
closed as entitlement-blocked rather than retried or silently changed.

The next separately frozen gate is
`atlas-marketdata-massive-dia-aggregate-surface-diagnostic-v1`. It uses **0
MarketData calls** and nine Options-Basic-accessible Massive 1-minute aggregate
queries: one for each DIA EOD date in the frozen window. The four dates with known
Massive daily bars act as controls and the five missing dates are the target set.
This can determine whether daily-bar presence/absence is consistent with Massive's
minute aggregate surface. It cannot determine whether an empty aggregate surface was
caused by no raw trades or by raw trades whose conditions made them ineligible.

Aggregate-surface contract:
`docs/research/marketdata_massive_dia_aggregate_surface_v1_20260923.md`.

The aggregate-surface workstation gate has now **PASSED its diagnostic
hypothesis** under run `20260923T225713Z` / evidence fingerprint
`dadc60d4eb1bf4f33d123cdd1b8b09d92222f8e53b4fdb3a9a28c48b1d5b1487`.
All four dates with Massive daily bars also had one-minute aggregates, and all five
daily-missing dates had no one-minute aggregates. More importantly, MarketData
volume was positive on exactly the four Massive-present dates (3, 6, 41 and 1
contracts) and zero on all five Massive-absent dates; summed Massive minute volume
exactly matched MarketData volume on every present date.

This supports a new **activity-aware** cross-provider hypothesis without changing the
failed V1 verdict. MarketData can emit an EOD row with a `last` value on a
zero-volume session, while Massive emits no aggregate bar when its qualifying-trade
surface is empty. The zero-volume MarketData `last` therefore remains unvalidated
and cannot be treated as an independently confirmed trade price.

The next gate is preregistered as
`atlas-marketdata-massive-disjoint-validation-v2` on six new roots and six new dates
with no root/date reuse from prior cross-provider calibration or V1. V2 freezes the
same contract selector, 10-calendar-day quote window, price/range and volume
thresholds. The only semantic change is activity-aware coverage: MarketData
`volume > 0` requires a Massive daily bar, while MarketData `volume == 0` requires
that the Massive daily bar be absent. Price/volume thresholding uses only
positive-volume sessions. Every anchor still requires at least five positive-volume
sessions, and the complete sample must include at least one zero-volume session so
the sparse-case rule is actually exercised.

V2 contract:
`docs/research/marketdata_massive_disjoint_validation_v2_20260923.md`.

The first V2 workstation result is preserved as **VALIDATION_FAILED** under run
`20260924T023405Z` / evidence fingerprint
`7461146a5c3f3f021384fea54cdfae1c4f62b509ed64f55f8a61b1b0d8d13dad`.
All six anchors passed every anchor-level criterion and contributed **53
positive-volume comparisons**. Across those sessions, MarketData `last` equaled
Massive close on 100% of comparisons, MarketData `last` was inside Massive
low/high on 100%, aggregate median relative price difference was 0%, aggregate
median relative volume difference was 0%, and the maximum observed volume-relative
difference was approximately 0.30%. The only failed preregistered check was
`sparse_case_observed`: the six selected contracts produced **0 zero-volume
MarketData sessions**. V2 therefore remains failed and will not be rerun or have its
thresholds weakened.

The next gate is a separate targeted sparse-activity confirmation,
`atlas-marketdata-massive-sparse-activity-confirmation-v1`. It does not repeat the
positive-volume price validation. Instead it freezes 12 new roots/dates and a
deterministic **farthest-OTM call** selector based only on chain strike and underlying
price, specifically to stress low-activity option paths without using quote-series
volume to choose contracts. Every observed session counts. A pass requires at least
10 zero-volume sessions across at least 3 anchors, at least 20 positive-volume
control sessions across at least 3 anchors, and 100% activity concordance:
MarketData volume 0 -> no Massive daily bar; MarketData volume >0 -> Massive daily
bar present. This gate cannot validate zero-volume `last` or create price,
execution, simulator, PAPER or LIVE authority.

Sparse confirmation contract:
`docs/research/marketdata_massive_sparse_activity_v1_20260924.md`.

The first sparse-activity workstation result is preserved as
**SPARSE_ACTIVITY_CONFIRMATION_FAILED** under run `20260924T033435Z` / evidence
fingerprint `d7ce4d184d175b6f60233f2a4470e8e4e67a27691ac8a45a082b805b9e3cce6d`.
Across 105 MarketData sessions, 87 were zero-volume and 18 were positive-volume.
All 105 sessions were activity-concordant with Massive: every zero-volume session
lacked a Massive daily aggregate, every positive-volume session had one, no invalid
volume occurred, and Massive supplied no extra dates. Zero-volume sessions appeared
across all 12 anchors; positive-volume controls appeared across 6 anchors.

The gate still failed because the preregistered positive-control floor was 20 and
only 18 were observed. That threshold is not reduced, V1 is not rerun, and its
selector is not altered after observation.

The next gate is separately preregistered as
`atlas-marketdata-massive-sparse-activity-confirmation-v2`. It uses 12 new roots
and dates and retains the exact V1 support thresholds, but changes the selector
prospectively to the **third-farthest OTM call** from the same restricted chain.
The selector still uses only strike, underlying price and symbol; quote-series
volume and Massive data remain unavailable at selection time. This is intended to
produce a less-extreme mix of sparse and positive-control sessions without changing
the activity hypothesis or support requirements.

Sparse V2 contract:
`docs/research/marketdata_massive_sparse_activity_v2_20260924.md`.

**Sparse-activity V2 has now PASSED on its first workstation execution**:
`SPARSE_ACTIVITY_CONCORDANCE_CONFIRMED`, run `20260925T184421Z`,
evidence `398ca760a7e05126e18008c6e7c09fc2f9d03e8a07b5a9a95e0282891d4c2d69`.
All 12 anchors completed: 106 MarketData sessions, 38 zero-volume across 8
anchors and 68 positive-volume across 11 anchors. Every activity-state
comparison matched Massive aggregate absence/presence. No mismatches, invalid
volumes, extra Massive dates or terminal errors. All frozen checks passed; 24
MarketData credits consumed and 9,966 remained at the last reported header.

The resulting *source-semantics synthesis* keeps the earlier failed validation
verdicts unchanged. The separate failed disjoint V2 nevertheless observed
53 positive-volume sessions with 100% MarketData-last/Massive-close agreement
and zero aggregate median price/volume discrepancy; fresh sparse V2 independently
confirms activity-state behavior. These are **different samples and hypotheses**,
not one joint price validation. Zero-volume last remains unvalidated, and bid/ask
is quote context rather than executable-fill authority.

The repeated source activity mini-campaign is now closed. Proceed to a
PIT-safe, candidate-first historical EOD acquisition/cache adapter, using
shared chain snapshots where possible, without whole-market downloading.

First-run acceptance:
`docs/research/marketdata_sparse_activity_v2_acceptance_20260925.md`.
Evidence synthesis:
`docs/research/marketdata_eod_semantics_synthesis_v1_20260925.md`.

Historical executable option prices, intraday paths, option P&L, strategy,
PAPER and LIVE authority remain closed.


MarketData daily credit reset is 09:30 America/New_York. Runtime budget control uses
the provider's `X-Api-Ratelimit-*` headers, and future acquisition must stay below
the documented 50-request concurrency ceiling. Trial qualification is sequential and
records observed credit consumption/remaining balance. HTTP 203 is accepted as normal
success; 429 fails closed rather than being blindly retried.

MarketData authenticated reads are workstation-only during this research phase because
the self-service account permits one public IP at a time. CI/cloud runners must not
use the token. MarketData-derived data also remains private/internal under the
self-service license; public or multi-user redistribution requires a separate
licensing gate.


**EOD-only scientific boundary:** MarketData historical option chains and quote
series are EOD snapshots. The qualification's nearest-ATM contract selection is only
an endpoint-linkage probe. A future simulator may not use EOD-D
`underlyingPrice`/moneyness to select a contract for an earlier open/intraday-D
decision. Strike bounds must come from ATLAS's PIT opportunity-time underlying price.
MarketData alone also cannot reconstruct option open/intraday STOP/TARGET paths; an
intraday-faithful option replay requires a separately qualified intraday source or a
separately preregistered EOD-only option experiment.

Full design:
`docs/research/marketdata_five_year_historical_options_v1_20260923.md`.


### Official Czar host/auth documentation discrepancy — 2026-09-23

A later complete documentation capture exposed an official-surface inconsistency that
ATLAS must preserve rather than silently resolve:

- the human `/docs` Servers table and quickstart name
  `https://api.czar28.com/v1` as the Production base for authenticated data;
- the same human documentation's endpoint examples, including the health example,
  use `https://czar28.com/v1`;
- the current OpenAPI 3.1 / API version 1.2.0 document declares
  `https://czar28.com` as its Production server;
- the human authentication section says every request requires Bearer auth, while
  the OpenAPI health operation explicitly overrides global auth with `security: []`
  and the human health example supplies no Authorization header.

ATLAS therefore no longer claims that either official surface globally supersedes the
other. Role-specific defaults are frozen instead: authenticated chain/EOD/intraday/
trade requests use the human-doc Production data host
`https://api.czar28.com/v1`; the quota-free public health watcher uses
`https://czar28.com/v1/options/health`, which is supported by both the endpoint
example and the machine-readable no-auth health contract.

This is a transport-contract reconciliation only. Historical depth remains unproven
while the upstream is degraded, and no provider, historical-price, strategy, PAPER,
LIVE, broker or order authority changes.

### MarketData license boundary for local caches — 2026-09-26

The current published MarketData Terms of Service license downloaded data only
for the subscription term and require deletion when the subscription ends.
The local exact-raw chain cache reduces repeat API reads while licensed; filling
the secondary SSD is NOT authority for indefinite use after cancellation.
Provider documentation confirms Starter's five-year historical access and
10,000 daily credits, and historical chain charges of one credit per 1,000
returned option symbols. Before any broad source-acquisition campaign, confirm
current provider retention terms in writing, maintain provider-specific
license lineage for raw/normalized/cache copies and backups, and distinguish
independently licensed durable data from subscription-bound data. Do not
treat a free-tier downgrade as grandfathered rights to paid-download archives.
Current source-only 12-case canary authorization does not authorize a
whole-universe campaign. Provider terms:
https://www.marketdata.app/terms/ ;
https://www.marketdata.app/docs/api/options/chain/ .

### External secondary-data storage V1 — 2026-09-24

ATLAS now has an explicit external-storage boundary for large secondary datasets.
The core repository and existing primary stock-data layout remain internal and
unchanged, including `data/provider`, `data/canonical` (the accepted Alpaca SIP V2
stock corpus), `data/duckdb`, and `data/checkpoints`.

The external-eligible bindings are `data/options`, `data/news`,
`data/research/provider_qualification`, `data/research/evidence`,
`data/fundamentals`, and `data/archives`. On Windows these remain visible at their
stable project-relative paths through directory junctions while their bytes live
under the configured external root. This preserves legacy path/receipt compatibility
and prevents drive-letter changes from becoming scientific-identity changes.

The external root is configured with `ATLAS_EXTERNAL_DATA_ROOT` only after
`scripts/configure_external_storage.py` reaches `READY`. The bootstrap can migrate
existing secondary files with an explicit `--migrate-existing` gate; it never moves
the primary stock paths. Once configured, research acquisition uses the external
volume's free-space/quota profile and fails closed if the root/bindings are not ready
rather than silently spilling large options/news data back onto the internal drive.

The 2026-09-26 workstation activation uses the internal Samsung 860 EVO SATA
SSD at `D:/ATLAS_DATA`, rather than the unrecognized external NVMe enclosure.
All six junction bindings reached READY, and 2,122 migrated files (2.521 GiB)
passed SHA-256 verification through the logical project paths. The existing
secondary profile reserves at least 25 GiB free and caps total acquisition at
190 GiB, including a 120 GiB candidate-options cache. The runtime
research-storage preflight subsequently passed: D: had 227.07 GiB free,
status SAFE, 190.00 GiB budget / 187.62 GiB remaining, and 25/40 GiB
minimum/warning thresholds. The pre-existing local profile remains 40 GiB total with a
50 GiB minimum-free-space floor when no external root is configured.

Full storage contract:
`docs/external_secondary_storage_v1_20260924.md`.

### Candidate-first MarketData historical-chain batching V1 — offline planner

The next product package now includes an **offline, zero-provider-call batch
planner** under `atlas-marketdata-candidate-chain-batch-plan-v1`.
`packages/data/marketdata_candidate_batch_plan_v1.py` and
`scripts/plan_marketdata_candidate_batches_v1.py` turn accepted stock
opportunity inputs into bounded shared historical-chain requests.

The planner uses the stock opportunity's own raw/PIT price, requires a source
SHA-256 and a decision date strictly after the EOD chain snapshot, and groups
overlapping explicit-strike windows by underlying, snapshot date and expiration.
Calls and puts may share one returned chain. Fifty same-root/date/expiration
opportunities with nearby prices can therefore yield **one planned historical
chain request**, not fifty duplicate requests. Different roots, dates, expirations
or disjoint strike windows stay separate. Nominal credit estimates are not
guaranteed; actual provider credits and returned symbols remain authoritative.

This is **planning only**: zero API reads, zero option quote-history requests,
no option selection/fill/P&L authority, and no stock-storage relocation.
The provider acquisition/cache executor remains a subsequent separately gated
package; it must verify external storage, paid license, quota/concurrency,
SHA-bound restart reuse, and the zero-volume and EOD/PIT restrictions already
recorded in the source-semantics synthesis.

Contract and operator input format:
`docs/research/marketdata_candidate_batch_plan_v1_20260925.md`.

## Read this first

1. Read this entire README for the current handoff.
2. Read [`docs/roadmap.md`](docs/roadmap.md) for the complete mission, testing
   design, gates, and ordered work.
3. Read [`docs/strategy_evidence_register.md`](docs/strategy_evidence_register.md)
   for strategy/version evidence, condition specialties, dispositions, robustness
   state, and successor hypotheses.
4. Inspect code, tests, immutable phase evidence, and Git history only as needed to
   perform the active roadmap package. Those materials support the three living
   documents; they do not compete with them as current plans.
5. If the three living documents conflict, stop and reconcile them in the same
   package before proceeding.
6. Every repository-changing implementation package must update this README and
   `docs/roadmap.md` before acceptance. Any package that opens, changes, interprets,
   closes, calibrates, or promotes strategy evidence must update the Strategy
   Evidence Register in the same package. A future chat must be able to reconstruct
   current product state, research direction, and strategy evidence without a prior
   conversation window.

All earlier README/roadmap versions were archived verbatim under
`docs/archive/2026-09-02-pre-product-rebaseline/`. The old `current_status`,
`phase_flow`, and plain-English files are frozen compatibility snapshots, not
living handoffs. Historical incident, closeout, policy, evidence, and research
documents are immutable records and must not be rewritten to make a later result
look like an original pass.

## Direction established by ATLAS Review Chat 3

The prior roadmap let unsuccessful alpha research block product construction. That
dependency is retired.

ATLAS now advances on two parallel tracks:

- **Track A — Product:** finish the end-to-end operating system using clearly
  labeled reference/baseline strategies in historical replay and operational
  PAPER. Product completion does not imply alpha validation or LIVE eligibility.
- **Track B — Strategy & Research Lab:** catalog practitioner setups, implement
  faithful finite strategy specifications, backtest them without parameter fishing,
  learn where each works or fails, and later add higher-prior academic mechanisms
  and advanced alpha research.

The immediate research priority is practitioner strategies built from observable
price, volume, volatility, trend, momentum, gap, opening, and premarket signals.
They are useful reference mechanisms and product test loads. A Reddit post, book,
charting site, or popular indicator is an **idea source**, not proof of edge.
Academic and replication evidence receives a higher prior evidence weight, but all
strategies must earn ATLAS historical and prospective evidence.

ATLAS is a strategy-selection system, not a single-strategy bot. It will eventually
rank eligible opportunities using frozen, walk-forward estimates of probability,
net expectancy, downside, execution cost, confidence, correlation, concentration,
and current conditions. It must not search indicators live until something agrees
with a desired trade.


## Historical News V1 acquisition — 2026-09-20

The first bounded historical-data acquisition package is now frozen as
`atlas-historical-news-v1`.

Scope: `2015-01-01..2026-09-19`, covering 141 calendar-month source-query
partitions from Alpaca's historical news endpoint. The package requests article
content and preserves every returned provider record in deterministic gzip JSONL.
A normalized ZSTD Parquet representation is produced beside the raw source.

Every completed month has an independent receipt binding the acquisition contract,
query window, page count, raw/unique article counts, byte sizes and SHA-256 hashes.
Restart/resume reuses a month only when the receipt is COMPLETE, belongs to the exact
contract fingerprint and both raw and normalized files still hash to the recorded
values. Missing or damaged months are reacquired independently.

The normalized layer deduplicates only by provider article ID, retaining the latest
returned `updated_at` version while leaving the raw provider records untouched.
Because Alpaca exposes creation/update timestamps but not a full historical revision
stream, retrieved headline/summary/content is conservatively assigned
`pit_available_at = updated_at`. The final retrieved body is never backdated to
`created_at`.

Acquisition is globally rate-limited across concurrent monthly fetch workers and is
bound to the existing 4 GiB news category quota plus the 50 GiB workstation
free-space floor. Normalization uses the existing DuckDB runtime; no new dependency
is introduced.

This package is source acquisition only. It does not derive sentiment, materiality,
event classes, novelty, or any other predictor yet and cannot access strategy outcomes
or grant PAPER/LIVE authority.

The authorized target-workstation acquisition completed on 2026-09-20 under
contract fingerprint `c977c5fd379deb6fda8f6733d7066d4d3a2179ec3dd1e9896cc9d5d288189c51`
and run fingerprint
`8076044e7f7c233f98b990dc5595bc4171d1788c143c8391bf173f827ed12c2f`.
All **141/141** monthly partitions were acquired in the run, producing
**2,211,606** raw provider records and **2,211,606** month-normalized article
records. The news lake occupied **1.931 GiB** of the 4 GiB category quota and the
workstation retained **116.81 GiB** free after completion.

Acquisition completion is not source-integrity acceptance. Before any Historical
News V1 sentiment, novelty, materiality, event-class or other predictor work may
begin, ATLAS must pass the separate
`atlas-historical-news-v1-source-integrity-closeout-v1` gate, frozen under
fingerprint
`99b3b76cadbfff7a7975ce1c9c5b4f2103b2d9e8ec77acae46bba51f80fa8df0`.
That gate independently re-hashes every raw/normalized month, recomputes receipt
and summary fingerprints, reconstructs the normalized record selected from raw
provider records, checks timestamp/PIT/JSON/schema invariants, tests article-ID
uniqueness across all 141 partitions, reconciles the exact global counts, and
derives a machine-path-independent corpus fingerprint. It deliberately does not
invent undocumented provider partition semantics. Predictor/strategy/PAPER/LIVE
authority remains false until this source-integrity gate passes and later scientific
contracts separately authorize research.

The first target-workstation closeout execution exposed a validator-only false
negative: DuckDB auto-detected the normalized file paths
`year=YYYY/month=MM/articles.parquet` as Hive partitions and injected virtual
`year`/`month` columns into `DESCRIBE SELECT *`, causing the exact-schema
check to fail for all 141 otherwise readable partitions. The observed corpus still
reconciled at **2,211,606** raw records, **2,211,606** normalized rows,
**2,211,606** distinct article IDs and **0** cross-month duplicate article-ID rows.
The closeout reader now explicitly disables Hive partition inference when validating
the physical Parquet payload, and a regression test covers the production directory
layout. This correction changes validator implementation only; the frozen closeout
contract and its scientific authority boundary are unchanged.

The corrected target-workstation closeout then reduced the failure surface to
**2/141** partitions: `2015-07` and `2026-08`. The follow-up read-only chronology
diagnostic proved exactly **4 provider-source timestamp inversions**: **three** in
July 2015 and **one** in August 2026. Their `updated_at` values precede
`created_at` by exactly **1, 16, 18 and 29 seconds**. Every anomalous normalized
row binds to its immutable raw provider record by SHA-256, both timestamps remain
inside the acquired monthly query window, and the stored V1
`pit_available_at == updated_at` for all four. Corpus-wide structural evidence
continues to reconcile at **2,211,606** raw records, **2,211,606** normalized rows,
**2,211,606** globally distinct article IDs and **0** cross-month duplicate IDs.
The machine-path-independent corpus fingerprint remains
`a5a26ed8b0093db16060c03d5ecb883a03322e61d7fe7217549b678dc1b3a1b0`.

V1 closeout remains a truthful **FAIL** and is not rewritten. A successor
`atlas-historical-news-v1-source-integrity-closeout-v2` contract is frozen under
fingerprint
`2a2039ba8ca495f1ea04a7ffd0719ccb95021d48917098899c4d93e5599df632`.
It accepts only the exact four diagnosed article-ID/SHA-256/timestamp tuples; there
is **no generic timestamp tolerance**, and any additional or changed anomaly fails
closed. Raw and normalized provider fields remain unchanged. Downstream effective
text availability is conservatively defined as
`max(created_at, updated_at)`, ensuring final retrieved text is never available
before either provider timestamp. For the other **2,211,602** rows this is identical
to V1; only the four diagnosed rows move forward by 1/16/18/29 seconds. The V2
package is source-integrity acceptance only and still grants no predictor,
strategy-outcome, PAPER or LIVE authority.

The target-workstation V2 acceptance **PASSED** on 2026-09-20 with acceptance
fingerprint
`279c13b37eb0a793a3ba821172e8ee226315109a52bca55040bbb3e1dd0a1532`.
The accepted corpus fingerprint remained
`a5a26ed8b0093db16060c03d5ecb883a03322e61d7fe7217549b678dc1b3a1b0`,
with **2,211,606** raw records, **2,211,606** normalized rows,
**2,211,606** distinct article IDs and **0** cross-month duplicate IDs. Strict V1
still records its two failed partitions; V2 accepted exactly the four hash-bound
provider chronology anomalies and no others. Historical News V1 source integrity is
therefore closed under the conservative V2 PIT policy, while news-derived predictor
evidence remains unopened.

### Historical source preservation and recovery doctrine — 2026-09-22

News and option-source anomalies are treated as source-semantics/reconstruction
problems to understand, not as reasons to weaken an acceptance rule until a run
passes. A failed or quarantined source record remains preserved evidence.

For historical news, option reference and later option market-data layers, ATLAS
uses the following recovery order:

1. **Preserve first.** Keep immutable raw provider rows, receipts, hashes and prior
   failed-version evidence. Never delete or rewrite the original source merely
   because a later interpretation becomes available.
2. **Diagnose the exact anomaly.** Determine whether the problem is provider
   correction/versioning, symbol identity, corporate action, adjusted deliverable,
   timestamp chronology, pagination, entitlement, schema, missing history or another
   reproducible source behavior.
3. **Repair narrowly when possible.** If authoritative evidence exists for only a
   small set of records/partitions, reacquire or supplement only those records and
   bind the replacement/supplement to explicit provenance and hashes. Do not
   redownload an entire corpus merely to repair a bounded defect.
4. **Use corroborating sources when needed.** A second qualified provider, supported
   historical endpoint, corporate-action/deliverable source or other authoritative
   evidence may resolve an ambiguity that the original source cannot. The original
   provider data remains preserved alongside the corroborating evidence.
5. **Rebuild derived layers freely when justified.** Normalized/reference/derived
   databases may be regenerated from preserved source lineage under a separately
   versioned contract when the data model or resolver improves. A rebuild must not
   silently reinterpret historical raw data without recorded provenance.
6. **Full reacquisition is permitted for systemic defects.** If evidence shows that
   an acquisition/source model is broadly inadequate, ATLAS may redownload and
   rebuild the affected corpus from the same or a better source. Storage/time
   efficiency is important, but it does not override source correctness.
7. **Quarantine is reversible authority withholding, not data disposal.** A
   quarantined record remains retained and auditable. It is excluded only from
   authoritative normalized/research use until sufficient evidence supports a
   deterministic resolution. The preferred outcome is eventual evidence-backed
   recovery whenever feasible.

A later contract may change behavior only after the root cause is documented and the
successor rule is frozen before reopening the broader run. The old failure remains
truthful historical evidence. Successor rules must be scoped to the diagnosed source
class and must not contain a generic tolerance or exception whose purpose is merely
to make the previously failing corpus pass.

This doctrine applies equally to news chronology/revision issues, historical option
identity/correction/deliverable conflicts, future quote/trade reconstruction and
similar source-integrity work. It changes no strategy evidence and grants no
predictor, PAPER or LIVE authority.

Before the next bulk source acquisition, ATLAS now uses a reusable provider
source-qualification framework covering identity/cardinality, chronology,
duplicate/version semantics, pagination, provider metadata versus observed data,
PIT availability, schema/nullability, entitlement boundaries, raw-to-normalized
reconciliation, corruption/hash receipts and unknown-anomaly fail-closed behavior.
Historical option reference is the first package using that framework. Its frozen
qualification contract fingerprint is
`17a3736f9317f7e403ea08c123aac35fabad0a8b2682bca7450373b797e9d260`.
The qualification is read-only and bounded; it does not authorize bulk acquisition
or grant historical candidate-availability, dynamic-deliverable, strategy, PAPER or
LIVE authority.

The target-workstation qualification completed **PASS_WITH_LIMITATIONS** under
evidence fingerprint
`120f141089420dcfaf86e1d30203a1517f27815bf1e6b3587976ccb74f4025e3`.
Identity/cardinality, schema/nullability, historical/recent entitlement, sampled
pagination and repeat-page integrity all passed. The retained limitations are
intentional: the source has no first-listed timestamp, may expose later
correction/deliverable state, and is not market-activity evidence.

Historical Option Reference V1 acquisition is therefore frozen as a structural
reference corpus only under contract fingerprint
`95eb5048336e411cb31c912e2cf8569915aedd42fc9e9f0fd0917f3fb3fe3f23`.
The corpus is anchored to provider `as_of=2026-09-19` and split into **212**
expiration-month partitions: expired contracts from 2014-06-02 through the replay
cutoff plus active-at-cutoff contracts through an exclusive 2032-01-01 hard
boundary. A pre-acquisition boundary probe must prove zero active contracts beyond
that bound or the run fails closed. Acquisition uses 1,000-row pages, exact
ticker-identity checks, streaming raw gzip JSONL, normalized ZSTD Parquet,
raw-to-normalized 1:1 reconciliation, SHA-256 receipts, partition restart/reuse,
four concurrent workers by default and continuous 4 GiB reference-quota / disk-floor
enforcement. No acquired reference row gains historical availability, dynamic
deliverable, price, predictor, strategy, PAPER or LIVE authority.

The first target-workstation V1 acquisition attempt failed closed in
`expired-2014-08` when Massive returned the same option ticker
`O:AAL140816C00020000` more than once. No V1 completion claim is made. Massive's
current endpoint documentation explicitly defines `correction` as the correction
number for an option contract, so ticker identity is not sufficient to assume a
single provider row.

V1 remains frozen as failed evidence. Historical Option Reference V2 is preregistered
under fingerprint
`6d0af0b58a66b77c445d7e561d759dfd947e348e994045a1f7cfc16aeb9ccb41`.
V2 preserves every provider row in immutable raw storage and resolves normalized
structural reference by ticker using the highest explicit numeric correction number;
a missing correction ranks below any explicit correction. Exact duplicate rows at the
same selected correction are deduplicated but counted and hash-recorded. Conflicting
payloads at the same highest correction fail closed. Every discarded version hash,
observed correction rank, version count and exact-duplicate count is carried into
normalized lineage and partition receipts. The original 212-partition/date/storage/
authority boundaries are unchanged.

V2 also treats the failed V1 run as reusable source lineage rather than wasted I/O.
Any V1 partition is reused only when its COMPLETE receipt, V1 contract fingerprint,
receipt fingerprint, query bounds, zero-duplicate V1 condition and raw SHA-256 all
verify exactly. V2 then rebuilds only the normalized Parquet/lineage layer while
referencing the original immutable V1 raw gzip, so the raw source is neither
redownloaded nor duplicated on disk. Partitions without verified V1 raw are acquired
from Massive normally. Work submission is bounded to the configured worker count
instead of pre-queuing all 212 partitions; after any failure no new partitions are
launched and only already-running workers are allowed to finish.

The first V2 target-workstation retry used five workers. It found **63** verified V1
raw partitions, rebuilt all 63 locally into V2 structural reference, and left **149**
partitions requiring provider acquisition. The 2032 active hard-boundary probe again
passed. After the local rebuild phase, V2 failed closed in the first historical
provider month, `expired-2014-06`, because ticker
`O:AAL140621C00020000` had conflicting provider payloads with the same highest
correction rank of `-1` (no explicit correction on either selected version).
Reference usage remained only about **0.136 GiB** with about **116.48 GiB** free.
No V2 completion claim is made and the same-correction conflict rule is not relaxed.

A targeted read-only successor diagnostic is frozen under fingerprint
`f544bb78cb6d61cbd69aa5fd266ee20349b3a977b39cb85e79a0a6a5ec0f9678`.
It makes two repeated supported structural-list requests and two repeated single-contract
overview requests at both the frozen current `as_of=2026-09-19` and a
pre-expiration historical `as_of=2014-06-20`. It records every returned row/hash,
field-level differences, request stability and whether the overview endpoint matches
one of the list rows. The diagnostic has no bulk-acquisition, source-mutation,
predictor, strategy, PAPER or LIVE authority and authorizes no conflict-resolution
rule by itself.

The repaired target-workstation diagnostic is now complete under evidence fingerprint
`20f255cab7b19e1d27902a76ed386e94156393c019434fbff4623b6d269a1722`.
All repeated requests were stable. At current `as_of=2026-09-19`, the structural
list returned two rows for `O:AAL140621C00020000` plus adjusted series
`O:AAL2140621C00020000`; the two target rows differed only in
`primary_exchange` (`BATO` versus `XMIO`). Exact current Contract Overview
returned stable HTTP 404 / `NOT_FOUND`. At pre-expiration
`as_of=2014-06-20`, the structural list returned exactly one target row and exact
Contract Overview returned one stable row that matched the historical list row.

Historical Option Reference V3 is therefore separately frozen under fingerprint
`7a9dab85c57bbc6cd93dee2472a9244d86e8c1776f986cd97036b9963bc4c48e`.
V3 retains V2 correction ranking, exact-duplicate handling, 212 monthly partitions,
the 2032 hard-end/storage guards, bounded worker scheduling and verified V2/V1 raw
reuse. Its only new resolver is deliberately narrow: an expired same-highest conflict
may proceed only when all rows are unversioned, differ only in `primary_exchange`,
and two stable exact Contract Overview requests at
`expiration_date - 1 calendar day` return a payload that exactly matches one of the
current conflicting raw rows. Anything else still fails closed. Before bulk work,
the observed AAL conflict itself must pass this rule as a dedicated pre-acquisition
probe. The immutable diagnostic closeout is
`docs/research/historical_option_reference_v2_conflict_diagnostic_closeout_20260921.md`.

V3 remains structural-reference acquisition only. It does not establish historical
contract availability, dynamic deliverables, market prices, predictor validity,
strategy evidence, promotion, PAPER or LIVE authority.

The first V3 target-workstation acquisition attempt used five workers. Its hard-end
probe passed and the mandatory AAL pre-acquisition resolver probe passed, selecting
the `BATO` raw payload at historical `as_of=2014-06-20`. The run discovered
**63 verified V2 raw partitions**, rebuilt all 63 locally under V3, and identified
**149 provider-pending partitions**. After the local rebuild phase, V3 failed closed
in `expired-2014-06` on `O:ACHI140621C00001000`: the unversioned same-ticker
rows differed in `underlying_ticker`, which is outside V3's deliberately frozen
`primary_exchange`-only resolver. Reference usage was about **0.198 GiB** and
reported free space about **116.40 GiB** at the end of the reusable rebuild phase.
No V3 completion claim is made.

The read-only ACHI diagnostic completed under evidence fingerprint
`b655282ff5f1da7bd3c2d7ac931a34b37650ffaa57354c6ac47efdfe746f81d1`.
All repeated requests were stable. At current `as_of=2026-09-19`, the provider
returned two `O:ACHI140621C00001000` rows differing only in
`underlying_ticker` (`ACHI` versus `AH`) and exact current Contract Overview
returned stable HTTP 404 / `NOT_FOUND`. At pre-expiration
`as_of=2014-06-20`, the provider returned exactly one target row with
`underlying_ticker=ACHI`; exact Contract Overview returned one stable HTTP-200 row,
matched that historical list row, and matched exactly one of the current conflicting
raw payloads.

Supplemental Massive Stocks reference returned no 2014 `ACHI` row but did return
inactive `AH` under CIK `0001472595`. This does not contradict the options result:
Massive documents OTC stock history as beginning on 2021-12-31. SEC EDGAR for the same
CIK independently states that Accretive Health traded on NYSE as `AH` through
2014-03-14 and began OTC trading as `ACHI` on 2014-03-17, before the target option's
2014-06-21 expiration. That SEC evidence is corroboration only; ATLAS does not stitch
symbols or use SEC at runtime.

Historical Option Reference V4 is therefore frozen under fingerprint
`2ddeb58d5f552ff0edb87a2244f130b813cf49600f5f82b1f50d8e1ee047a57d`.
V4 retains correction ranking and exact-duplicate semantics. Its successor fallback is
restricted to expired unversioned same-ticker conflicts whose only differing fields
are `primary_exchange`, `underlying_ticker`, or both. Two repeated pre-expiration
structural-list requests without an underlying filter must yield one stable target row;
two repeated exact Contract Overview requests must yield the same payload; and that
provider-native historical payload must exactly match one and only one current raw
conflicting row. Otherwise V4 fails closed. Both observed AAL and ACHI cases are
mandatory pre-acquisition probes.

The immutable ACHI diagnostic closeout is
`docs/research/historical_option_reference_v3_achi_diagnostic_closeout_20260921.md`.
V4 remains structural-reference acquisition only and opens no historical availability,
dynamic-deliverable, market-price, predictor, strategy, promotion, PAPER or LIVE
authority.

The first target-workstation V4 acquisition attempt used five workers. The active
hard-end probe passed, both mandatory known-conflict probes passed, and all **63**
verified V3 raw partitions were rebuilt locally under V4. At that point the reference
lake occupied about **0.260 GiB** and the workstation reported about **116.22 GiB**
free. Provider acquisition then failed closed in `expired-2014-07` on
`O:ACT2140719C00045000`: the same-highest-rank conflict reached V4's narrow
fallback with an **explicit correction present**, while V4 intentionally authorizes
that historical exact-match fallback only for unversioned rows. This is a new
source-semantics boundary, not a runtime defect, and no V4 completion claim is made.

The read-only ACT2 diagnostic completed on the target workstation under evidence
fingerprint
`283f736a73a742704c7d005b9c0c48aee2b11cf2dd1eccc8bf44fd52a443e1e3`.
All repeated requests were stable. At current `as_of=2026-09-19`, Massive
returned two `O:ACT2140719C00045000` rows carrying the same explicit correction
value **2**. The rows differed only in `additional_underlyings`: both were USD cash
deliverables, with observed amounts **2604** and **2617.04**. Exact current Contract
Overview returned stable HTTP 404 / `NOT_FOUND`. At pre-expiration
`as_of=2014-07-18`, the structural list returned exactly one target row with
correction **2**, and exact Contract Overview returned one stable HTTP-200 row that
matched the historical list row and exactly one current conflicting raw payload.

Historical Option Reference V5 is therefore frozen under contract fingerprint
`4a9775c90414d8a454654d5f0928d79b68dec785b16b493e197ea34471aef1ea`.
V5 preserves V4's unversioned AAL/ACHI branch unchanged: expired rows must have
missing correction and may differ only in `primary_exchange`,
`underlying_ticker`, or both before the repeated pre-expiration exact-match rule may
run. V5 adds a separate branch for **expired explicit same-correction conflicts**.
That branch requires all conflicting current rows to share one nonnegative highest
correction rank, permits only `additional_underlyings` to differ, requires the
pre-expiration structural-list and Contract Overview payloads to be stable and
identical, requires the historical correction rank to equal the current highest
rank, and requires that historical payload to match exactly one current conflicting
raw row. Anything else remains fail-closed.

AAL, ACHI and ACT2 are all mandatory pre-acquisition probes. V5 inventories verified
V5 receipts first, then verified V4/V3/V2/V1 raw lineage and re-normalizes reusable
raw locally without copying it. Five workers remain the default with at most five
partitions in flight. V5 remains structural-reference acquisition only; choosing the
provider-native pre-expiration ACT2 row creates **no historical dynamic-deliverable
authority** and grants no historical candidate-availability, market-price, predictor,
strategy, promotion, PAPER or LIVE authority.

The immutable ACT2 diagnostic closeout is
`docs/research/historical_option_reference_v4_act2_correction_conflict_closeout_20260921.md`.

The first target-workstation V5 acquisition passed the hard-end probe and all three
mandatory AAL/ACHI/ACT2 probes. Startup inventory was **212** monthly partitions:
0 verified V5 reusable, **63 verified V4 raw reusable**, and **149 provider
pending**. All 63 verified V4 raw partitions were successfully re-normalized under
V5. Displayed option-reference usage reached about **0.322 GiB** with about
**135.45 GiB** free. Provider-side continuation then failed closed in
`expired-2014-08` on `O:ACIW140816C00040000`: the frozen unversioned
resolver requested its required pre-expiration `as_of=2014-08-15` structural
view and received **zero** target rows instead of exactly one.

The ACIW diagnostic completed on the target workstation under evidence
fingerprint
`9c04eba3dd7fce45bbd3e35366e93191acb92493c3e4ed34001e0ad4ef31c777`.
The fully paginated current view returned two stable unversioned ACIW rows with the
same underlying ticker and differing only in `primary_exchange`
(`GMNI` versus `XCBO`). The historical boundary matrix was stable: no target
row existed on 2014-08-14 or the required pre-expiration 2014-08-15 view; the target
remained absent for `expired=false` on/after expiration; `expired=true` exposed
both rows beginning on 2014-08-16. Exact Contract Overview was absent throughout the
tested 2014-08-14 through 2014-08-18 boundary. No provider-native historical payload
identified exactly one current row.

Historical Option Reference V6 is therefore frozen under contract fingerprint
`f40edc7bc0dd872dfa944297571545a8e4ab14c112af1ea35ddd806bf2c30342`. V6 preserves all V5 AAL/ACHI/ACT2 resolution semantics
unchanged and adds a separate **no-guess ambiguity quarantine**. Quarantine is
eligible only for expired, unversioned same-ticker conflicts whose sole differing
field is `primary_exchange`, whose underlying ticker is identical across current
rows, and whose required pre-expiration structural target is repeatably absent.
Eligible conflicts select **no provider row**: all raw rows are preserved, a
fingerprinted partition quarantine artifact is written, and the ticker is excluded
from normalized authoritative option reference. Other unresolved ambiguity classes
remain fail-closed.

V6 reconciliation is explicitly
`raw rows = normalized selected + discarded version rows + quarantined raw rows`.
Verified V6 receipts require raw, normalized and quarantine hashes. V6 inventories
verified V5 raw lineage before V4/V3/V2/V1, so the 63 V5 partitions already completed
during the first attempt—and any provider partitions that atomically completed before
worker cancellation—can be re-normalized locally without refetching. Five bounded
workers remain the default.

The immutable ACIW diagnostic closeout is
`docs/research/historical_option_reference_v5_aciw_historical_gap_closeout_20260922.md`.
V6 quarantine is source-quality exclusion only and creates no historical
candidate-availability, dynamic-deliverable, market-price, predictor, strategy,
promotion, PAPER or LIVE authority.

The first target-workstation V6 acquisition passed the 2032 hard-end boundary probe,
all three AAL/ACHI/ACT2 resolution probes and the ACIW quarantine probe. Startup
inventory was **0 verified V6 reusable / 63 verified V5 raw reusable / 149 provider
pending**, and all **63/63** verified V5 raw partitions were re-normalized locally
under V6. Bounded scheduling remained five workers / five in flight. At the end of
the reusable rebuild phase, displayed option-reference usage was about **0.384 GiB**
with about **103.35 GiB** free.

Provider-side continuation then failed closed in `expired-2014-07` on
`O:ARTC140719C00025000`. The current unversioned same-rank rows differ in both
`additional_underlyings` and `cfi`, which exceeds V6's deliberately frozen
unversioned allowance of `primary_exchange` and `underlying_ticker`. The conflict
is also outside the ACIW quarantine, whose sole allowed differing field is
`primary_exchange`. No V6 completion claim is made and neither resolver nor
quarantine semantics are broadened from the observed result.

A read-only ARTC source-conflict diagnostic is therefore frozen as
`atlas-historical-option-reference-v6-artc-deliverable-cfi-conflict-diagnostic-v1`
under contract fingerprint
`af4cae21c4d8307a37346098449b37ebc04e6e9a5ab25ef4414d5820f71853df`.
It fully paginates and repeats the current structural list, records exact
`additional_underlyings` and `cfi` values, probes the immediate expiration
boundary, repeats exact Contract Overview, and tests whether any stable historical
provider payload matches exactly one current conflicting row. It grants no
conflict-resolution, quarantine, predictor, strategy, PAPER or LIVE authority.

The immutable failure/diagnostic contract is
`docs/research/historical_option_reference_v6_artc_deliverable_cfi_conflict_20260922.md`.
The next authorized workstation action is this ARTC diagnostic after the package is
accepted on `main`. V6 must not be rerun until that evidence is reviewed and any
successor rule is separately frozen. After a future reference acquisition completes
all **212** partitions, ATLAS must independently close
raw/version/normalized/quarantine/hash/cardinality and all
conflict-resolution/quarantine lineage before broad option daily history.

### ARTC diagnostic closeout and Historical Option Reference V7 — 2026-09-22

The target-workstation ARTC diagnostic completed under evidence fingerprint
`c7c52de6fb807957ecdb0fe5c6c9c2efb65baa739831fe7f25a64a2a5d77b48c`.
The current `as_of=2026-09-19` view contains two stable, unversioned rows for
`O:ARTC140719C00025000`, differing exactly in `additional_underlyings` and
`cfi`: one row carries a **$4,825 USD** cash additional-underlying with CFI
`OCASCN`, while the other has no additional underlying and CFI `OCASPS`.

The expiration-boundary evidence resolves the historical structural state without
guessing. On both 2014-07-17 and 2014-07-18 with `expired=false`, repeated
structural-list requests return exactly one ARTC row; repeated Contract Overview is
present and stable; list and overview agree exactly; and that payload matches exactly
one current conflicting row. The selected historical/current payload hash is
`6f1274868c60e6d23c42c96e4698a08724b3ff1014dd6ecf5b3a992f9794d3d8`,
the `OCASCN` + $4,825 cash-deliverable row. Beginning at expiration under
`expired=true`, both current variants appear and exact overview becomes unavailable.

Independent corporate-action evidence corroborates, but does not drive, the runtime
resolver: ArthroCare's 2014 acquisition converted each common share into **$48.25
cash**; 100 shares per contract therefore imply exactly **$4,825**. CFI documentation
also supports the cash/non-standardized versus physical/standardized classification
difference. The provider-native PIT list/overview evidence remains the resolver
authority; external sources are retained only as root-cause corroboration.

Historical Option Reference V7 is separately frozen from this evidence. It does
**not** simply add `additional_underlyings` and `cfi` to V6's generic allowance.
Its new unversioned cash-deliverable/classification branch requires an expired,
correction-null conflict differing **exactly** in those two fields; exactly two rows;
identical underlying/exchange/shares and immutable option economics; exactly one
positive USD cash additional-underlying row and one no-deliverable row; two distinct
non-empty CFI values; and stable repeated pre-expiration list + Contract Overview
evidence whose identical payload matches exactly one current row and itself carries
the USD cash deliverable. Anything outside that complete class still fails closed.

ARTC becomes a mandatory V7 pre-acquisition probe with the exact expected selected
row hash, `OCASCN` classification and $4,825 cash deliverable. Known-conflict
preflight now fully paginates the current structural result because the ARTC target
was found inside a three-page candidate set. The ACIW quarantine semantics remain
unchanged; its raw data remains preserved for later evidence-backed recovery.

V7 reuses verified V7 receipts first, then verified V6/V5/V4/V3/V2/V1 raw lineage,
re-normalizing reusable raw locally without copying it. Only partitions lacking
verified reusable raw require provider reacquisition. Five bounded workers remain
the default.

V7 remains structural-reference acquisition only. It creates no historical candidate
availability, dynamic-deliverable, market-price, predictor, strategy, PAPER or LIVE
authority. The Strategy Evidence Register remains unchanged. Full evidence and
preregistration are recorded in
`docs/research/historical_option_reference_v6_artc_conflict_closeout_v7_20260922.md`.

After V7 is accepted on `main`, the next workstation gate is:

```powershell
git checkout main; git pull; .\.venv\Scripts\python.exe scripts\run_historical_option_reference_v7.py --authorize-source-acquisition --workers 5
```

If V7 encounters another new source-semantic class, preserve completed/reusable work
and stop for another bounded diagnostic rather than widening V7 after the result.

### Historical Option Reference V7 provider-throttle hotfix — 2026-09-22

The first target-workstation V7 run successfully rebuilt all **63/63** verified V6 raw
partitions under V7, then entered the 149-partition provider-acquisition phase. The
provider phase exposed an operational defect: V7's direct-`urllib` request path did
not consume the existing Massive reference budget of **5 requests/minute**. Five
partition workers could therefore burst account-level requests and trigger HTTP 429
even though `config/massive.yaml` already required approximately 12 seconds between
reference request starts.

The observed stop was transport throttling, not a new source-semantic conflict. No
V7 resolver rule or scientific/source policy changes.

V7 now uses one shared request coordinator across boundary probes, known-conflict/
quarantine probes, provider pagination, historical exact-match list requests and
Contract Overview calls. At the configured five requests/minute, request starts are
globally paced at approximately 12-second intervals across all worker threads. HTTP
429 imposes a shared provider cooldown; `Retry-After` is honored when present and a
full 60-second cooldown is used when it is absent. The existing bounded retry count
remains authoritative.

Fatal worker/provider errors now trigger cooperative cancellation before executor
shutdown. Queued work is cancelled, workers waiting in pacing/backoff wake immediately,
and any active network request remains bounded by the configured request timeout. The
CLI reports expected failures as `STOPPED_RESUMABLE` instead of dumping an uncaught
traceback; Ctrl+C reports `INTERRUPTED_RESUMABLE`. Completed V7 receipts remain
restart-reusable in both cases.

Provider acquisition also emits an explicit phase-transition line and one-minute
heartbeats with completed partitions, in-flight partitions, request starts and
throttle-event count. A healthy rate-limited run therefore no longer appears frozen
while a monthly partition is still paging.

The 63 completed V7 rebuild receipts from the interrupted workstation run remain
reusable; any provider partition that atomically completed a receipt before the peer
failure is likewise discovered on restart. Full root-cause and operational details:
`docs/research/historical_option_reference_v7_massive_throttle_hotfix_20260922.md`.

This is transport/reliability hardening only. The Strategy Evidence Register remains
unchanged and no historical availability/deliverable/price, predictor, strategy,
PAPER or LIVE authority is created.

## News + options historical-data foundation — 2026-09-20

ATLAS now has a bounded local-data foundation for bringing historical news and
option economics into the deterministic simulator without repeating the stock-lake
bulk-build mistake.

The initial storage policy is intentionally conservative for the current workstation:

- minimum free-space floor: **50 GiB**;
- warning threshold: **65 GiB** free;
- initial new research-data budget: **40 GiB**;
- news quota: **4 GiB**;
- option-reference quota: **4 GiB**;
- broad option-daily quota: **8 GiB**;
- selective candidate option cache: **20 GiB**;
- derived IV/Greeks quota: **4 GiB**.

The planned local lake is partitioned under `data/news/` and `data/options/`.
News retains immutable raw articles plus normalized/versioned derived features.
Options retain broad contract reference and daily data plus a selective permanent
candidate cache for chains, minute bars, quotes and trades actually needed by
historical replay. Derived implied-volatility and Greek records are separate from
observed provider prices.

The source roles are frozen at this stage:

- Alpaca historical news is the intended broad historical-news source and documents
  history beginning in 2015;
- Alpaca historical option market data is recent-only for this research purpose,
  beginning in February 2024;
- Massive option day/minute/trade history documents coverage back to June 2014,
  subject to the account's actual plan entitlement;
- Massive historical option quotes document coverage beginning March 7, 2022;
  therefore 2016-2021 exact historical top-of-book execution is not assumed and
  requires a later explicit execution-fidelity policy.

The source/storage preflight completed successfully on the target workstation under
fingerprint `8fa4fe13856c3e93973867e4503765be4c240c64d73df08ab11ed654985bb134`.
It observed **119.01 GiB free**, status `SAFE`, the full **40.00 GiB** research-data
budget still available, and zero existing usage in all new categories. Read-only
provider probes confirmed access to Alpaca historical news in the 2015 window,
Massive 2016 option reference, and Massive option day/minute flat-file prefixes for
both 2016 and 2025. No bulk downloads occurred.

PR #172 merged the bounded news/options data foundation as
`551e2a88a13cec74e8ff4cef6147d742b5c1b659`. PR #173 then merged the resumable
Historical News V1 acquisition package as
`a7b1a12db1e9403372d6b499ef332de95730d655`. The target-workstation Historical
News V1 acquisition is now complete: **141/141** monthly partitions,
**2,211,606** raw provider records, **2,211,606** month-normalized articles,
**1.931 GiB** news storage and **116.81 GiB** free after the run. The completed
run fingerprint is
`8076044e7f7c233f98b990dc5595bc4171d1788c143c8391bf173f827ed12c2f`.
A separate source-integrity closeout must PASS before predictor development; no
strategy evidence or trading authority is created by the acquisition itself.

## Full deterministic decision envelope and AI boundary — 2026-09-20

The target ATLAS simulator and production decision object must be materially richer
than the current recurrent stock-equivalent research slices. The deterministic core
must be able to make, replay, explain, and score the complete trade decision **without
AI participation**. The required information envelope is:

### Underlying forecast

- expected direction and calibrated direction probability;
- expected return/move distribution, not only one point estimate;
- expected horizon and time-to-move distribution;
- MFE/MAE distributions and expected path shape;
- probability and timing of reaching favorable/adverse thresholds;
- realized/implied volatility state, volatility trend and regime;
- market, sector, industry and ticker regime/alignment;
- relative strength, momentum, trend, gap and participation context;
- liquidity, spread, slippage and execution-quality expectations;
- downside/tail scenarios, uncertainty/confidence and evidence support;
- exact strategy/economic-family/version lineage and point-in-time provenance.

### Catalyst and context

- news sentiment, direction and source provenance;
- novelty, materiality, relevance and duplication/echo handling;
- event type and event-time certainty;
- earnings date/proximity, surprise/guidance context and post-event state;
- SEC/regulatory/corporate-action evidence when available;
- analyst/reference/fundamental context when under an accepted source contract;
- macro/calendar risk and scheduled-event proximity;
- sector/industry/peer context and correlated catalyst exposure;
- short-interest, ownership or other approved predictor context when separately
  accepted;
- data freshness, availability and contradiction/conflict state.

### Trade gate

- TAKE / ABSTAIN;
- calibrated confidence and expected probability of profit;
- expected gross and net edge after spread, fees, slippage and expected decay;
- downside/tail estimate and expected risk-adjusted value;
- support/sample size, stability, walk-forward robustness and regime applicability;
- strategy/confluence agreement and conflict evidence without double-counting
  correlated signals;
- data-quality/freshness/tradability checks;
- portfolio capacity and authority state;
- ranked opportunity priority and explicit abstention reason.

### Option construction

When options are economically preferable to stock, the deterministic constructor
must model the option rather than multiply the underlying return by a leverage
factor. Required fields include:

- call/put and strategy structure;
- expiration/DTE and strike/moneyness;
- bid, ask, midpoint, spread and executable-price assumption;
- premium and contract multiplier;
- delta, gamma, theta, vega and rho where available/material;
- implied volatility, IV percentile/rank when supportable, term structure and skew;
- open interest, volume, quote age and contract liquidity;
- underlying/option synchronization and quote provenance;
- earnings/event exposure through expiration;
- expected contract P&L distribution under underlying-path and IV scenarios;
- breakeven, maximum premium at risk and scenario/tail loss;
- expected return on premium/capital and expected value after option-specific costs;
- stock-versus-option economic comparison and reason for chosen instrument;
- contract-roll/expiration handling where relevant.

### Risk and portfolio construction

- position size and account-risk dollars/percentage;
- stop-distance-aware or scenario-loss-aware risk normalization;
- maximum premium/notional/account risk;
- available cash, buying power and capital reservation;
- current portfolio gross/net exposure;
- ticker, family, sector, industry and factor concentration;
- pairwise/cluster correlation and overlapping catalyst exposure;
- portfolio beta and directional exposure;
- aggregate option Greeks and volatility exposure when options are used;
- liquidity/exit-capacity constraints;
- drawdown state, daily/weekly loss limits and risk-of-ruin controls;
- stress/scenario loss including gap and volatility shocks;
- competing-opportunity priority and opportunity-cost/capital-allocation evidence.

### Position-management plan

Before entry, every admitted trade must also bind a deterministic management plan:

- entry method and acceptable price/slippage bounds;
- stop, target and time-exit policy;
- whether exits are fixed, volatility-scaled or otherwise versioned;
- trailing/breakeven/partial-exit behavior when explicitly supported by that version;
- option-specific IV/theta/event invalidation conditions;
- thesis invalidation conditions;
- mark/freshness requirements and degraded-data behavior;
- exit precedence for simultaneous or conflicting triggers.

### Outcome and learning record

Every taken and abstained opportunity must retain the immutable decision-time
features plus later outcomes required for learning:

- realized stock and option P&L after all modeled costs;
- MFE/MAE, threshold touches, time-to-touch and path diagnostics;
- realized slippage/spread/fees and option Greek/IV evolution when available;
- reason for entry, abstention, rejection and exit;
- contribution by strategy, regime, catalyst, contract and portfolio constraint;
- marked-equity and book-equity effect;
- calibration error and forecast-vs-realized diagnostics;
- complete fingerprints/provenance so future research can reproduce the decision.

The full-system simulator should ultimately compare **stock and option economics on
the same underlying opportunity and path**, then admit the economically justified
instrument under the portfolio constraints. A favorable underlying move is not
assumed to imply a profitable option trade.

### AI is a late, independent verification layer

AI is intentionally outside the quantitative decision stack. Signal generation,
feature construction, news/catalyst extraction used by the deterministic models,
trade gating, option construction, sizing, portfolio admission and exit-plan
construction must all function and be testable without an AI reviewer.

Only after ATLAS has produced an immutable deterministic trade case may an optional
AI reviewer inspect that case plus the same authorized point-in-time evidence. Its
role is independent challenge/verification: approve, caution, reject, or flag an
evidence inconsistency. It may not silently rewrite direction, strike, expiration,
position size, entry, stop, target, horizon, probabilities, expected value or
portfolio state. If AI identifies a material problem or proposes an alternative, the
original deterministic case remains immutable and any alternative must return through
a new deterministic evaluation path under a new record.

AI output is separately fingerprinted and its incremental value must eventually be
measured against the identical deterministic system with AI disabled. AI is not
allowed to become hidden alpha, a substitute for weak quantitative evidence, or a
training input that contaminates the independent baseline.

## Current repository truth

- **B35 canonical DEVELOPMENT replay is CLOSED / ACCEPTED.** The frozen `2016-01-04..2026-04-30` trial completed exactly **482/482 groups, 59,768/59,768 source units, and 482 validated receipt ids**, producing **20,171,286** compact fired opportunity/context/outcome records. Run fingerprint = `8955a282453cb89a24d3bcdf819d80451bebfa3ec9752dc24c113efc668cffe6`; B35/source/split/authorization identities remained exactly frozen. Consumed-master rows read `0`; future-blind rows read `0`; provider calls `0`; broker reads/writes `0/0`; PAPER/LIVE authority `false/false`; strategy/selector promotion `false/false`; no permanent minute feature lake was created. The accepted continuation reused 82 validated groups and computed the remaining 400 groups / 49,600 units in **11:40:46 at 4,246.7 units/hour**, about **6.43x** the original serial restart and **44.3% faster** than the final isolated exact-equivalent benchmark.
- **B35 strategy x condition / frozen walk-forward selector analysis is COMPLETE / PROFILE-ONLY.** PR #76 merged as `cceccdc23569f6d48395a52322a83f59ba555b23`. Analysis fingerprint `8369790cc019e84091d9ff431e0ba82678e8b23ec09f65f010cdfaca35d3254f` normalized all 20,171,286 accepted compact opportunities and built 33 complete-XNYS 504/63/63/1 folds. The frozen selector evaluated 17,030,985 test opportunities, selected 3,747 (3,188 comparable), and abstained on 99.978%. Selected mean return was +0.2984% / +0.1984% / +0.0485% / -0.2015% / -0.7014% at 0/10/25/50/100 bps. No strategy or selector is promoted. The material research interpretation and per-strategy dispositions are maintained in `docs/strategy_evidence_register.md`.
- **B35 retained-artifact robustness is COMPLETE / NO PROMOTION.** PR #78 merged as `83d09c424a02883f7d3529a39c62294dcbaf6bc2`; workstation robustness fingerprint = `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107` across 2,079 complete XNYS test sessions. At 50 bps every declared standalone/selector profile has negative mean session return and Deflated-Sharpe probability `0.0`; 13 selected fold/cell hypotheses produced **0 BH-FDR q=.05 rejections**. The frozen selector remains positive at 0/10/25 bps but is negative at 50/100 bps; its 10,000-draw bootstrap assigns 24.21% probability to positive mean 50-bps session return. PBO/CSCV is 0.01%, retained only as a narrow ranking-stability diagnostic and not profitability evidence. No strategy/selector promotion occurred; consumed-master/future/provider/broker reads remain zero and PAPER/LIVE authority remains false.
- **B35 exact targeted minute perturbations are COMPLETE / NO PROMOTION.** The frozen DEVELOPMENT-only pass completed **482/482 groups and 59,768/59,768 source units**, evaluated all **27 one-axis-at-a-time profiles**, and returned run fingerprint `dd3f6b94f9c669218512ed1eb014b33c0fd35e8ffe38484cc8967dc7a6e29f69`. Baseline equivalence is `PASS_EXACT_CANONICAL_OUTCOME_REUSE_ALL_GROUPS`; targeted fingerprint `078bdc84a18bd6e5ff401ca0a21d4feed61f7b21770a86610a42ee0fdd16374d`. Consumed-master/future-blind rows read `0/0`; provider calls `0`; broker reads/writes `0/0`; canonical replay rewrite and selector refit `false`; PAPER/LIVE/promotion authority `false/false/false`. No neighboring parameter variant rescued the four B34/B35 strategies after costs: gap delay/threshold variants remained deeply negative; ORB 14/15/16-minute and 0/1/2-minute delays were economically indistinguishable and negative; premarket rel-vol retained only a roughly 4.9-bps best gross mean that was already negative at 10 bps; HVD remained 55-59 signals and negative. B35 v1 is therefore scientifically closed; simple parameter rescue is closed as well.
- **Successor source verification is ACCEPTED; PR #84 implements the separately gated DEVELOPMENT outcome runner without opening broad successor performance during repository acceptance.** PR #82 merged as `26ddd08952454c9b1251df15fe5bfcc8ccdad16a`, implementing the frozen **21 economic families = 10 retained + 11 new**, four bounded B35 mechanism-level challengers, shared PIT context, and deterministic no-lookahead evaluators. PR #83 merged as `5bcc80d72d1203394525c69ba21f07193b4d6272` and froze all **28 concrete routes = 18 daily + 10 minute**, accepted V2 DEVELOPMENT source identities, profile-independent grouping, standalone-before-conditioning/confluence artifact order, and the `0/10/25/50/100` bps diagnostic contract. The workstation hash-only preflight then completed **493/493 groups and 59,768 minute units** under runner-contract fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c` and source-verification fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`, using 8 workers x 1 DuckDB thread while opening zero strategy outcomes, protected/future rows, provider calls, or broker access. PR #84 adds exact accepted-preflight validation, one shared daily feature pass, exact retained-reference signal masks, a common daily executable-universe disposition, exact B35-native grouping for all ten minute routes, SPY benchmark reconstruction from the already accepted native minute source, next-open 1/5/20-session daily diagnostics, conservative structural-stop/fixed-2R intraday diagnostics, atomic standalone artifacts, hash-validated restart/reuse, and an optional 4x1/6x1/8x1 exact-equivalence performance diagnostic. The accepted source begins on `2016-01-04`; earlier history is never invented. The full 493-group run still requires a second explicit CLI gate, but the workstation benchmark is now an optional performance diagnostic rather than a scientific prerequisite. The first benchmark attempt on 2026-09-13 stopped during input preparation before any benchmark profile ran because the accepted minute source lacks SPY's exact scheduled final regular minute on 2019-08-12. This is now treated as a source-coverage edge case rather than fabricated data: the repaired preregistered SPY benchmark uses the last observed regular SPY bar from the same session only when it is at most 5 minutes stale, records every fallback session/staleness value, forbids cross-session fill and provider fetches, and still fails closed beyond that bound. No successor benchmark performance was opened by that failed attempt. A second preparation attempt then proved the gap is material rather than a one-minute edge case: SPY's last accepted minute on 2019-08-12 is 15:31 ET, 28 minutes before the scheduled final minute. The minute-only repair is therefore retired. The next gate is a separate source-only SPY audit: accepted B35 minute data remains primary; an exact same-session raw canonical V2 daily close may repair an unusable minute session only through 2025; 2026 native-daily partitions are forbidden so the consumed May-August 2026 master cannot be opened indirectly. The source-only audit is now ACCEPTED under contract fingerprint `912bf7b0ed12a0e4fd7c0382244138573564472e618586677e78c154f7e3cc33` and scientific fingerprint `c575d5df1b7f0d0a7734efc3833329f57f73c953b7b67ccb4ea54d33abb4555c`. It resolves all **2,596** DEVELOPMENT XNYS sessions: **2,595** use the accepted minute-primary close and exactly **one** (`2019-08-12`) uses the preregistered `NATIVE_RAW_DAILY` same-session repair because the last accepted minute is `19:31:00Z`, 28.0 minutes stale. Benchmark artifact SHA-256 = `29d7ea9d6a322b4b55af872f7d2e5097777738b209727a487cfd0dcf1306790d`; native-acceptance fingerprint = `6e3e78f181183f0ee92517fd6fabf2f0bd5b33c1a6eea14a87f0894ce2bd6664`. PR #87 merged as `1e5c399752be690cc1b4a33e915f922e5503d956`, removing optional pandas Parquet-engine dependencies from both the source audit and successor DEVELOPMENT runner without changing scientific contracts. Consumed-master/future-blind/provider/broker reads remain `0`; PAPER/LIVE/promotion authority remains false. The next permitted evidence action is the separately authorized full 546-work-group standalone DEVELOPMENT run (64 daily buckets + 482 minute groups); the earlier 493 count is the source-verification grouping, not the outcome-run denominator; the 4x1/6x1/8x1 benchmark remains available only as an optional performance diagnostic. The first authorized full standalone attempt then opened the DEVELOPMENT-only runner at 8 workers under run fingerprint `22a2ace77c4c578c30964ba2a645b822738ef667617f0ef6bffb3192f75582ae` and stopped on a real sparse/flat prior-session geometry edge before a complete standalone result existed. The failed-break/reclaim route had passed a flat prior high/low into its strict evaluator and raised instead of treating that route as unavailable. The successor engine is now versioned so finite positive non-flat prior geometry is a readiness prerequisite; invalid/flat prior geometry fails closed for that route only. No geometry is fabricated. Console progress now reports completed/total groups, reused/new counts, active/queued work, elapsed time, new-group throughput and ETA at least every 30 seconds or five new completions.

- **B34 intraday source readiness and the opening/premarket pack are CLOSED / ACCEPTED.** The enhanced 2026-09-08 workstation audit returned `ACCEPTED` under contract `atlas-b34-intraday-source-readiness-v2-ohlcv-pack-frozen` with evidence SHA-256 `415c46c714b80f5cff4950320443088b8b89ed761c9f51d071fccf3e60baefd0`. It preserves the earlier semantic/source-readiness evidence SHA-256 `aad355e57c089a7aaea84a3f941091dec69d89ce87235972f13472a308550237`, accepted all five deterministic OHLCV samples, represented premarket/regular/after-hours bars, opened zero partitions overlapping the consumed `2026-05-12..2026-08-11` master interval, and made zero provider calls, broker reads, or broker writes. The frozen RESEARCH-only pack fingerprint is `6f7239fcda11ac6c890d2635980d431ec49e346707d9cc549f111bd50daaa4bf` for `b34_gap_continuation_v1`, `b34_opening_range_breakout_15m_v1`, `b34_premarket_relvol_consolidation_v1`, and `b34_highest_volume_day_style_v1`. B34 opened no outcomes and grants no promotion, PAPER, LIVE, broker-mutation, or broad/full minute-materialization authority.
- Accepted numbered foundation: **through Phase32**, merged on `main`.
- Phases26–32 are scientifically valid `ACCEPTED_NEGATIVE` results.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is
  `ACCEPTED_NEGATIVE` as well.
- Later XBRL, beneficial-ownership, FINRA short-interest, diluted-EPS, and Form 13F
  branches are also closed accepted-negative/source-limited results.
- Retained beneficial-ownership source-gate lineage: source-only feasibility
  mechanism `PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`; frozen
  feasibility fingerprint
  `f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`.
  These are historical source-feasibility identifiers, distinct from the later
  frozen scientific mechanism and preserved for accepted-validator compatibility.
- Historical supported modern alpha remains **0**. No existing strategy is
  historically validated, paper validated, live eligible, or live authorized.
- The retained master protected outcome window `2026-05-12..2026-08-11` was
  **consumed exactly once on 2026-09-07** by the frozen A33/B33 V2 walk-forward.
  The completed receipt/accounting reports **93,380 master-protected return rows
  read**. The frozen version then continued unchanged through the accepted V2
  source cutoff `2026-09-03`; rows after `2026-08-11` are separately tracked as
  post-protected continuation, not a redefinition of the master holdout. This is
  historical out-of-sample evidence, not prospective PAPER.
- V2 split-reconciliation validator repair: provider-native split-adjusted volume
  is no longer required to equal the inverse OHLC split factor. That relationship
  is retained as deterministic audit evidence, while OHLC factor agreement,
  provider/source provenance, schema, finite/nonnegative volume, and other
  raw/adjusted integrity gates remain fail-closed. Focused regressions cover both
  accepted volume divergence and rejected price-factor corruption. At repair
  acceptance this changed no source bytes, strategy/portfolio policy, trading
  authority, or protected-return state; the later frozen replay described below
  subsequently consumed the master holdout exactly once.
- V2 split-price quantization repair: the real completed V2 source showed that the
  former absolute `1e-5` OHLC-factor equality was also too strict for provider-rounded
  split-adjusted prices. The retained quantization diagnostic covered 2,825,114 paired
  eligible rows: maximum adjusted-price residual was `$0.05841364` and maximum
  relative factor error was `0.000994532`. Reconciliation now fails closed unless each
  open/high/low value is within `$0.10` adjusted-price residual **and** `0.001` relative
  factor error of the close-derived split factor. A new regression accepts bounded
  provider rounding while the existing corruption regression still rejects a material
  price-factor mismatch. At repair acceptance it changed no source bytes,
  strategy/portfolio policy, holdout receipt, protected-return state, PAPER
  authority, or LIVE authority; the later frozen replay subsequently consumed the
  master holdout exactly once.
- LIVE trading and automatic broker failover remain disabled.
- The former operator pause is satisfied and superseded by the explicit Review
  direction encoded here. Product and practitioner-library work may resume; it
  grants no trading authority by itself.
- The unmerged Review research lineage remains preserved: LIT-01 Heston-Sadka
  calendar-seasonality work is source-inconclusive; LIT-02 terminal-repair work is
  deferred/incomplete. Neither grants alpha support or changes `main` authority.
- The former statement `Phase33 signal-to-trade remains blocked` is retained only
  as historical roadmap provenance. Product signal-to-trade work is now unblocked
  for historical replay and operational PAPER baselines. LIVE remains blocked.
- Product/strategy rebaseline: PR #44 merged to `main` as
  `6b972c4d26dfa350580e269d8010038fe526cf4f`, based on the accepted PR #43 Form
  13F closeout.
- A33/B33 phase-start contracts: PR #45 merged as
  `bc105be4958cce808dbbeb306f0ec58f23b13a6d`. Its six pre-outcome seed
  specifications, broader research taxonomy, authority transition rules, and
  shared opportunity-event contract remain preserved.
- A33/B33 foundation implementation is complete and protected by its exact-head
  acceptance workflow. Historical performance has now been opened only for the
  frozen V2 DEVELOPMENT and one-time walk-forward versions described below; strategy
  authority did not change and provider/broker/PAPER/LIVE mutations remain zero.
- A33/B33 compatibility validation now treats living-document protected state as a
  monotonic lifecycle: before outcome access it requires the original zero-read
  boundary; after an accepted one-time consumption it requires the current
  consumption statement and protected-row accounting instead. Frozen policy,
  authority, and feature fingerprints remain mandatory. This prevents current
  evidence from being rewritten backward merely to satisfy a historical handoff
  token.
- The trusted-lake adapters are implemented. The retained Massive path remains
  reproducibility-only; the isolated Alpaca SIP V2 adapter produced the completed
  frozen DEVELOPMENT and walk-forward evidence described below.
- The adapter package was accepted in PR #47 and merged as
  `646db6e6e44ccd2355c7c2263221f35cd01d5da8`; its post-merge Windows and Ubuntu
  full-suite jobs passed.
- The first A34 RESEARCH account-replay vertical slice is implemented: deterministic
  candidate admission, cash/position accounting, simulated orders, outcomes, equity
  curve, read-only API, and visible browser state. Empirical V2 DEVELOPMENT and
  frozen walk-forward account replays now exist and are negative at the aggregate
  account level; no strategy was promoted. The slice was accepted in PR #48 and
  merged as
  `147b95810936a0b10b24eb08e51cd4d83c16c85b`; its post-merge Windows and Ubuntu
  full-suite jobs passed.
- The accepted Phase19 operator-path correction is merged in PR #49 as
  `cc0ecc6995ad977ca6eeb5fc00983ba2926317a0`; its post-merge Windows and Ubuntu
  full-suite jobs passed. The current stacked dashboard, not the legacy Phase16
  shell, is the authoritative local GUI entry point.
- The hash-verified A34 operator drilldown was accepted in PR #50 and merged as
  `f0a45cbff2662e26f4f1f55e8a16c0c356c9266c`; its post-merge Windows and Ubuntu
  full-suite jobs passed. The dashboard now verifies and displays account metrics,
  decisions, rejection reasons, simulated orders, outcomes, and equity/exposure.
- Exact point-in-time market-regime context was accepted in PR #51 and merged as
  `e2dd741b4cdd3f5b729c4ec1cb510451887c748c`; its post-merge `main` test workflow
  passed. Daily close-derived signals now carry the exact XNYS-close availability
  clock and the replay consumes only the hash-bound same-close market regime that
  was knowable before next-open entry. Ticker/sector regime remain unavailable.
- Alpaca SIP V2 daily source/replay preparation and the finite B34 minute/intraday semantics audit are complete and accepted. Empirical sizing
  estimates 3.781B native minute rows, 64.51 GiB canonical minute Parquet, 62.55
  GiB compressed raw evidence, and a conservative 375.58 GiB peak-plus-reserve
  requirement. The operator chose precise local V1 historical-data decommissioning,
  not a local V1 archive. The first rebuild-safety package provides a generation-
  isolated `data/v2_build/alpaca_sip_v2` layout, atomic run state, a 30 GiB reserve
  guard, and an allowlisted content-hash-bound V1 decommission plan. It deliberately
  preserves live, model, unrelated research, repository, and accepted evidence
  state. The explicit `--decommission-v1-only` run completed successfully on the
  operator workstation on 2026-09-03 local time: **8 targets / 38,034 files /
  147,206,406,678 bytes (137.10 GiB)** were deleted after the exact generated token
  was confirmed. The retained receipt is
  `data/checkpoints/alpaca_v2_migration/v1_decommission_receipt.json`. ATLAS now has
  no accepted historical market database. The read-only post-decommission inventory
  then identified database-generation remnants that were outside the first eight
  targets: `raw/day_aggs_v1`, legacy `provider/alpaca`, old ML training data,
  discovery/universe/regime/quality/reference products, and their ingestion/manifests.
  Accepted strategy-evaluation evidence, SEC/regulatory source evidence, live state,
  models, source code, and Git history remain outside the expanded cleanup boundary.
- The fresh-source native V2 package was accepted in PR #57 and its first operator
  acquisition completed on 2026-09-07. `scripts/run_alpaca_v2_rebuild.py --build-v2`
  first
  inventories and asks for
  exact hash-bound confirmation of only the remaining database-derived targets; it
  writes a new plan-hash-specific receipt and never overwrites the original receipt.
  It then freezes the last completed XNYS session, captures fresh active and inactive
  Alpaca assets plus complete-quality corporate actions, builds an exact-literal
  acquisition universe, and runs native `1Day` units before native `1Min` units.
  The source contract is Alpaca SIP, raw adjustments, `asof=-`, 10,000 total bars per
  page, opaque pagination until the token is null, and New York local-midnight
  windows with the inclusive API end moved back one microsecond. Every page is an
  atomic restart boundary; exact response bytes, checksums, request metadata,
  normalized page shards, unit Parquet, quarantine records, and run/plan manifests
  live only beneath `data/v2_build/alpaca_sip_v2`. Provider-rejected or anomalous
  literals are quarantined without substitution. The runner reserves 30 GiB and
  pauses safely when capacity is insufficient. The estimated 3.781B minute rows mean
  one overnight run was not assumed; rerunning the identical command resumed rather
  than restarted. The final operator report is `COMPLETE`: **67,480 / 67,480 units**,
  including **5,302 / 5,302 daily** and **62,178 / 62,178 minute** units,
  **3,897,688,734 canonical rows**, and **1,757,288 quarantined rows**. This is a
  complete isolated native candidate base, not production promotion. The quarantine
  is retained evidence and was carried into the post-build gate rather than
  discarded or assumed harmless. Historical V2 RESEARCH results now exist only for
  the frozen versions described below; PAPER authority and LIVE authority remain
  absent.
- The V2 post-build package was accepted in PR #58 and merged as
  `8e5abf21fe1ca138cd90125005b8c305a598dd44`; its post-merge `main` workflow passed
  on Windows and Ubuntu. It has now run successfully against the completed operator
  V2 source: native validation passed **67,480 / 67,480 units**, the provider-native
  split source reused **5,302 / 5,302 complete units**, and the reconciled research
  view materialized **2,706,154 rows across 1,582 symbols**. Its single resume-safe
  post-build
  coordinator hash-verifies every native unit; fully scans native daily schema,
  provenance, dates, sessions, duplicates, and OHLCV; builds conservative direct-
  Alpaca-asset identity/lifecycle evidence; acquires a separate provider-native SIP
  `adjustment=split` daily source; reconciles raw and adjusted bars; and materializes
  a hash-bound V2 daily research view. Name changes, mergers, reorganizations,
  spin-offs/rights, stock distributions, termination/redemption events, ticker reuse,
  uncertain security type, source anomalies, and internally gapped streams are
  excluded rather than silently stitched until a separate segment and cash-flow
  policy exists. Native raw prices remain separate. The research view carries
  unadjusted same-session close for the PIT `$5` universe floor so a future split
  cannot rewrite historical eligibility. Although source capture continues through
  its frozen current cutoff, the strategy-input Parquet ends physically at the
  **2026-05-11 DEVELOPMENT boundary** and materializes zero protected-window return
  rows. It does not promote a production database or grant historical, PAPER, or
  LIVE authority. Compile-all and the complete local
  suite pass at **1,546 tests**; all ten PR #58 exact-head workflow groups and the
  post-merge `main` workflow passed.
- The frozen walk-forward package is implemented and tested in PR #61 after native
  completion and before any operator V2 performance read. The default DEVELOPMENT
  manifest and adapter still end
  physically at `2026-05-11` and reject every later row. A separate
  `walk_forward_daily.json` generation can be created only after an immutable,
  self-hash-bound authorization records the exact native/split source plus frozen
  strategy, feature, and portfolio fingerprints. Its signal interval begins exactly
  `2026-05-12`; earlier rows are indicator warm-up only, and its end must equal the
  latest validated V2 source session. The trials ledger, strategy replay, account
  replay, post-build manifest, and permanent consumption receipt all account for the
  protected rows. A failed attempt after opening remains consumed. No parameter
  revision, historical-to-PAPER relabeling, strategy promotion, or external write is
  permitted by this path. The restart repair preserves each superseded consumption
  receipt as a content-addressed snapshot, verifies the complete history before
  continuation, retains known protected-row counts across attempts, and reuses a
  completed replay only after its operator artifact verification passes. Missing or
  inconsistent current/history receipts fail closed; source-only reruns cannot erase
  prior consumption. The GUI shows the attempt and known/pending row accounting and
  never describes an incomplete run as unopened. The materialization-cutoff failure
  path also preserves an observed protected-row count in both the receipt and
  post-build summary. Three additional pytest cases cover that failure and successful
  retries after cutoff and replay failures. The complete implementation revision
  `0879bbed7f22c53108f58db0b790f58c61a04987` passed all **ten PR #61 workflow
  groups**, including the locked Windows and Ubuntu full suites at **1,581 tests
  plus 4 subtests per platform** and all three retained A33/A34 validators. Local
  checks also passed 10 isolated standard-library receipt tests, 13 isolated
  coordinator checks, Python compilation, JavaScript syntax, dependency-lock
  validation, and secret hygiene. Local isolation was necessary because application
  dependencies were absent; the full application evidence comes from locked CI.
  The implementation closeout changed only the two living documents after the code
  package. The authorized workstation run has now completed. DEVELOPMENT produced
  **161,347 opportunities**, account replay **-17.912608%** return and
  **-20.803073%** max drawdown. The frozen walk-forward evaluated signals
  `2026-05-12..2026-09-03`, produced **14,081 opportunities**, consumed the retained
  master holdout exactly once with **93,380 protected return rows read**, and ended
  with account replay **-8.372772%** return and **-8.372772%** max drawdown. Signal-
  level mean net return was positive for Bollinger-long, EMA-pullback-long,
  MACD-long, and RSI-recovery-long, but the aggregate account evidence is negative,
  the RSI sample is small, cash-distribution economics remain incomplete, and
  **authority promotion is none**. All nine policies remain RESEARCH; PAPER/LIVE
  authority remains absent.
- **A34.5 operator live observability is now implemented in PR #60.** Its
  accepted merge closes the observability prerequisite before A35; A35 itself remains
  a separate PAPER/broker-authority package and has not begun. No PAPER broker
  mutation is authorized by A34.5.
- The former Phase39 LIVE numbering is retained: **Phase39** remains Controlled
  LIVE Activation and is still protected by all preceding evidence and authority
  gates.

## What exists now

The accepted foundation already includes provider ingestion, PIT identity/history,
Parquet/DuckDB analytical storage, deterministic features, universe/discovery,
market/sector/ticker regime context, ML evidence, strategy routing, instrument and
trade geometry, portfolio risk planning, AI review boundaries, broker-neutral
SHADOW/PAPER primitives, Webull-primary and manual-Alpaca-secondary controls,
restart-safe orchestration, API/browser primitives, and historical production-path
reconstruction.

Important limitations:

- The accepted Phase11 strategy registry still contains eight simplified daily
  rule variants. A33/B33 adds a separate, versioned reference-strategy catalog so
  accepted behavior is not silently changed.
- The accepted PR #45 six-specification seed catalog remains an immutable
  pre-outcome compatibility layer. The nine direction-specific policies resolve
  its declared implementation blockers without rewriting that accepted lineage.
- The first six practitioner families now have nine direction-specific, complete
  research policies covering universe, signal, side, timing, stop, target, exit,
  sizing, costs, and authority.
- A separate daily reference-feature overlay supplies the exact indicator
  transitions needed by those policies without changing the accepted 33-feature
  core. B34 supplies accepted minute/session semantics and the initial
  opening/premarket evaluators. The successor pre-outcome implementation now adds the
  shared daily PIT overlay, objective confirmed-pivot/chart-pattern geometry, ADX/DMI
  and SPY-relative-strength context, closed-minute VWAP/failed-break evaluators, and
  exact implementations for all eleven new families plus the four bounded B35
  challengers. No successor historical performance is opened by that implementation.
- The existing router applies fixed regime compatibility; it does not yet learn
  conditional, walk-forward strategy performance or calibrated probability.
- A provider-free independent-strategy runner, condition-sliced opportunity/outcome
  records, append-only strategy-trials ledger, and read-only catalog API now exist.
  A read-only trusted-lake adapter now supplies its exact input contract. The first
  fixed, non-learned account replay and browser view now exist; learned selection,
  qualifying PAPER, strategy-management controls, and the complete operator product
  remain unfinished.
- A34.5 now supplies the accepted read-only near-live Operational PAPER dashboard
  contract over engine-owned evidence: no second GUI trading truth, no independent
  trade decisions, bounded automatic refresh, and visible fail-closed degraded/
  invalid state. A35 broker mutation remains a separate authority package.
- PostgreSQL and the root Docker deployment remain historical scaffolds, not an
  accepted operational database or deployment.

The decommissioned V1 daily lake used Alpaca SIP through `2021-08-13` and
Massive from `2021-08-16`. That boundary is retained historical provenance, not the
current data path. The fresh V2 candidate base is Alpaca SIP throughout its frozen
acquisition interval. No V1 row, derived indicator, regime, or identity product may
be silently reused as V2 input. Earlier source limitations do not authorize invented intraday history; V2 minute semantics are now accepted by B34, and missing minute history remains preserved as absence rather than synthesized.

## 2026-09-16 — Live market-data provider and transport policy

ATLAS now separates its durable analytical lake from its live market interface. The
canonical Parquet/DuckDB V2 lake remains the broad historical/research source used for
large-universe discovery and replay. **Alpaca is the primary live/current market-data
provider; Webull is the secondary live/current fallback where its API entitlement and
feed quality are sufficient.** Execution remains a separate concern: Webull is the
planned primary PAPER/LIVE execution broker and Alpaca remains the explicitly selected
manual execution fallback. Automatic broker failover remains prohibited.

Massive is no longer a required forward runtime dependency. Any retained Massive free
access is diagnostic/research-only and carries no trading authority; historical Massive
source provenance and reproducibility paths remain immutable evidence and are not
rewritten. Unofficial Yahoo/yfinance feeds are not part of the supported
operating-provider chain. Tradier is **not yet** in that chain either; as of
2026-09-22 it is a separately qualified candidate current-market-data source only.
Its availability and credentials do not change the accepted Alpaca-primary /
Webull-secondary policy until REST, streaming, freshness, coverage and cross-provider
quality evidence are independently accepted.

Live transport is intentionally selective rather than market-wide. Broad discovery
runs locally first; REST/API snapshots refresh the narrowed candidate set and obtain
option-chain/contract evidence; WebSocket subscriptions are then allocated where
seconds matter economically: final candidate validation before entry, pending orders,
open positions, and exits. REST remains the normal overflow and recovery path when a
candidate does not receive a streaming slot or a stream is degraded. One provider
connection may multiplex many symbol/contract subscriptions; subscription capacity,
not one-connection-per-candidate, is the managed resource.

Streaming priority is: **open positions and pending orders first; entry-ready finalists
second; strong near-finalists third; lower-ranked candidates by REST; broad discovery
from the local lake.** A central market-data coordinator must own the stream/REST budget,
share one underlying subscription across related option candidates, apply hysteresis or
minimum residency so nearly tied candidates do not thrash subscriptions, and dynamically
promote/demote candidates as ranking changes. A WebSocket failure degrades first to a
fresh same-provider REST snapshot, then to the accepted secondary provider when
available, and finally to `DATA_UNAVAILABLE`/abstention rather than invented market
state.

Every live observation must retain provider, feed, transport, market timestamp,
receive timestamp, freshness/age, and quality/provenance. Current Alpaca Basic limits
verified on 2026-09-16 are **30 equity WebSocket symbols** on the real-time IEX stock
feed and **200 option quote subscriptions** on the indicative option feed, with REST
rate capacity treated as a separate budget. These are operational entitlements, not
scientific constants: the coordinator must configure/discover current provider limits
rather than hard-code them permanently. The then-current paid Alpaca plan raises stock
streaming to unlimited symbols and option quote streaming to 1,000 with consolidated
U.S. equities/OPRA-quality access; ATLAS does not require that paid plan until the
system's economics justify supporting its own data subscription.

For options, the intended sequence is `underlying shortlist -> REST option-chain
snapshot/Greeks/liquidity -> small contract finalist set -> underlying + finalist
WebSockets -> entry -> held-contract/underlying streams through exit`. If finalists
exceed streaming capacity, the coordinator streams the highest-priority subset and
keeps the remainder current through rate-aware REST polling. Provider transport choice
must not alter strategy authority, economics, portfolio-risk gates, or execution truth.

### Tradier candidate source qualification — 2026-09-22

The operator now has a production Tradier Brokerage API token stored only in the local
`TRADIER_API_KEY` environment variable. Official Tradier documentation describes
production U.S. equity/options market data as real-time consolidated data, production
`/markets` resources as 120 requests/minute per access token, POST
`/v1/markets/quotes` as the larger-symbol-list quote surface, and one market-data
stream session with practical support beyond several hundred symbols but no published
hard symbol cap.

ATLAS does not accept those provider claims as an operating-policy change. The frozen
first-stage diagnostic
`atlas-tradier-production-market-data-source-qualification-v1`
has contract fingerprint
`3a14be911be351d465ad3a99ab6dc7d47e985fbd17005af0bb6faa9c7613305d`.
It uses read-only production POST quote requests staged at
`1, 10, 100, 250, 500, 1000` symbols from the latest local Phase 7
discovery-eligible universe. It records returned cardinality, exact coverage,
missing/unexpected symbols, duplicate rows, provider/request latency, response bytes,
payload fingerprint, non-null schema fields and returned `X-Ratelimit-*` headers.
Actual quote values are not persisted by the diagnostic.

Streaming is deliberately **not** qualified in V1. Tradier publishes no hard stream
symbol limit and explicitly discourages exchange-wide subscriptions, so a separate
stream contract will be designed from the accepted REST evidence using bounded
candidate-style symbol sets. Until both REST and streaming/freshness/feed-quality
evidence are accepted, Tradier has no current-data authority and the existing
Alpaca-primary/Webull-secondary live transport policy remains unchanged. The source
contract is documented in
`docs/research/tradier_market_data_source_qualification_v1_20260922.md`.

The first target-workstation Tradier REST qualification attempt on 2026-09-22
stopped **before any Tradier request** because the previously accepted Phase 7
universe snapshot was no longer present locally. Recovery then confirmed that the
2026-08-14 Phase 4 reference manifest and reference Parquet were also absent. An exact
historical reference reacquisition through the accepted Phase 4 path reached Massive
HTTP 429 before the snapshot could complete.

That failure exposed an old operational gap in the Phase 4 Massive REST adapter:
retryable 429 responses were recognized, but successful pagination was not paced to a
configured request budget and four exponential retries could still be exhausted
inside the provider's rate-limit window. The reference client is now explicitly
rate-aware. `massive.reference.requests_per_minute` is configurable and set to **5**
for the retained free reference-access profile; every reference request, including
pagination and retry attempts, is paced to that budget, and numeric `Retry-After`
headers are honored in addition to bounded exponential backoff.

This is transport hardening only. It does not alter Phase 4 identity semantics,
Phase 7 eligibility, the frozen Tradier qualification population, any provider-policy
authority, or strategy/PAPER/LIVE authority. After this hardening is accepted on
`main`, reacquire the exact 2026-08-14 reference snapshot, rebuild Phase 7, require
the original **12,066** discovery-eligible count and universe fingerprint
`98e72372e2a4725b2e90b3f6bf797e085f6ed64e2190454892b5ffa42c240124`, and only then
rerun the frozen Tradier REST qualification.

A separate current-asset stress diagnostic was then run against the surviving
Alpaca SIP V2 asset snapshot
(SHA-256 `43a5645d4366e7f7294e14f60596c5e753db6158c394a62262fdd283bbab151a`).
The staged 1,000-symbol sample returned **962 / 1,000 (96.2%)** in **0.544 s**.
A same-session full-universe benchmark then requested all **13,412** active/tradable
US-equity symbols. Tradier accepted the entire population in one POST and returned
**12,775 / 13,412 (95.251%)** in **2.009 s wall time** (**1.983 s provider latency**,
approximately 5.853 MiB). Equivalent 1,000/2,000/5,000-symbol batching returned the
exact same 12,775-symbol set, ruling out request-size truncation through the tested
13,412-symbol request. This materially supports broad REST snapshot -> local narrowing
-> selective streaming as a candidate live-data architecture, but does not freeze a
polling cadence. Follow-up symbol probes also showed that the documented dot-to-slash
notation recovered only 4/30 dotted misses, so no blanket normalization rule is
accepted. This is supplemental engineering evidence only: it does not replace the
frozen Phase 7 V1 population, change provider policy, or grant PAPER/LIVE authority.
Full evidence is preserved in
`docs/research/tradier_current_asset_rest_stress_20260922.md`.


### Tradier whole-universe cadence diagnostic V1 — 2026-09-23

The next current-data question is no longer POST cardinality; it is **how often broad
current discovery should refresh and how much a bounded retry of stale/missing symbols
actually recovers**. The prior 13,412-symbol stress work established roughly two-second
full-universe acquisition and a stable 95.251% raw-return cardinality, but the
near-close quality snapshot was not representative of the whole session and explicitly
left polling cadence unfrozen.

ATLAS now freezes
`atlas-tradier-whole-universe-cadence-diagnostic-v1` as a read-only mid-morning
diagnostic. It performs 20 broad current-universe quote snapshots at 30-second starts
and, ten seconds after each broad pass, re-requests only symbols that were missing,
had invalid quote geometry, had unknown quote freshness, had quote age above 30
seconds, or carried a future-timestamp anomaly. The maximum provider-read count is 40
over about ten minutes, far below the observed 120 requests/minute entitlement.

The source population is pinned to the exact 2026-09-22 Alpaca SIP V2 comparison source: SHA-256 `43a5645d4366e7f7294e14f60596c5e753db6158c394a62262fdd283bbab151a` and exactly 13,412 active/tradable/us-equity symbols. Any change fails closed before the first provider read. When the exact local Phase 7 discovery snapshot is available,
its 12,066-symbol population is analyzed as a subset of the same broad responses
without consuming additional provider calls.

V1 preserves raw gzip responses, hash-bound receipts, missing/unresolved-set
fingerprints, retry recovery, quote/trade freshness, spread/liquidity sensitivity and
descriptive 30/60/120/300-second cadence views. Non-positive provider timestamps are
explicitly UNKNOWN rather than epoch-aged. All freshness/spread thresholds remain
diagnostic sensitivity only: this package does **not** freeze production cadence,
provider policy, strategy evidence, PAPER/LIVE or execution authority.

Workstation command after merge:

~~~powershell
git checkout main; git pull
.\.venv\Scripts\python.exe scripts\diagnose_tradier_whole_universe_cadence_v1.py --authorize-provider-reads --run-live-cadence-diagnostic
~~~

Full design:
`docs/research/tradier_whole_universe_cadence_v1_20260923.md`.


Accepted workstation evidence now covers both **mid-morning** and **midday** under
the same frozen 13,412-symbol / 12,066-symbol comparison populations. Both runs
completed 20 broad + 20 unresolved-retry cycles with no terminal errors. Raw broad
coverage was identically 12,775/13,412 (95.251%) on every snapshot; the same 637
symbols were persistently absent, and neither later broad passes nor +10-second
retries recovered any missing symbol. That gap is now treated as a separate
identity/provider-coverage problem rather than a polling-cadence problem.

Freshness weakened across the three observed regular-session regimes. Mean quote-age
<=30s counts were 5,805.2 mid-morning, 4,768.6 midday and 4,608.3 in the power hour;
mean diagnostic-usable counts were 5,598.4 / 4,660.6 / 4,515.55; and mean unresolved
counts were 7,607.15 / 8,643.4 / 8,803.7. The final power-hour run completed under
evidence fingerprint
`6ba17e5fcca3c2890d6ad38a41ca56953afaf4d978f97e6ed14e2977a634fd01`.
It again returned exactly 12,775/13,412 symbols with the same 637 persistent/ever
missing and zero missing-symbol recovery.

The three-regime cadence diagnostic is **COMPLETE**. +10-second retries are retained
for freshness only. **120 seconds is frozen as the subsequent Tradier broad-REST
qualification/engineering baseline** because it is the shortest tested interval with
>60% quote-timestamp advancement in all three observed regimes (68.253% / 61.174% /
60.942%). This does not freeze production trading cadence or freshness/liquidity
policy and does not grant Tradier current-data, PAPER or LIVE authority.

### Tradier REST qualification V1 closeout — 2026-09-22

The exact 2026-08-14 Phase 7 universe was successfully reproduced before rerunning
the frozen Tradier REST qualification: **36,417** reference rows, **35,226** stable
instruments, **12,066** discovery-eligible symbols and accepted universe fingerprint
`98e72372e2a4725b2e90b3f6bf797e085f6ed64e2190454892b5ffa42c240124`.

The production read-only V1 rerun completed all six frozen POST quote stages with no
terminal provider/request error, no unexpected symbols and no duplicate symbol rows.
Observed coverage/latency was: 1/1 at 0.317 s; 10/10 at 0.182 s; 98/100 at 0.260 s;
238/250 at 0.332 s; 477/500 at 0.392 s; and 952/1,000 at 0.439 s. Evidence fingerprint:
`e78e5bfa26039d6895b2b25ebe377d0242f83a2943fe9854f3f1bd1518310a29`.

The frozen >=98% completeness rule is satisfied through the 100-symbol stage but not
at 250/500/1,000, so V1 closes exactly as
`DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS`. The limitation is cross-provider
symbol/coverage behavior rather than request-cardinality failure. In the 1,000-symbol
sample, 38/48 misses use the Phase-7 lowercase-`p` preferred/class notation, three
are dotted classes and seven are otherwise plain literals; no generic ticker rewrite
is authorized.

V1 therefore accepts the observed REST transport/batch capability as useful evidence
but creates **no current-data authority**. Streaming, timestamp/freshness,
provider-symbol resolution and fallback behavior remain separately versioned work.
The selected future routing target remains Tradier -> Alpaca -> Webull ->
DATA_UNAVAILABLE/abstain. Full closeout:
`docs/research/tradier_market_data_source_qualification_v1_closeout_20260922.md`.

With the REST V1 evidence closed, the active historical data-foundation thread returns
to the already frozen Historical Option Reference V6 ARTC diagnostic; V6 itself must
not be rerun and no V7 rule may be invented before that diagnostic evidence is
reviewed.

### Selected live-data routing and execution-broker migration direction — 2026-09-22

The operator has selected the target current-market-data routing order for future
runtime implementation:

1. **Tradier — primary discovery/current ingest.** The target uses Tradier's
   production consolidated current-data surface for broad REST snapshots and later
   selective streaming after the remaining formal qualification gates pass.
2. **Alpaca — first fallback.** Under the operator's current no-paid-data-plan
   assumption, Alpaca remains a useful real-time fallback with its available
   entitlement even though the free stock feed is narrower than consolidated SIP.
3. **Webull — second fallback.** Webull remains a capable current-data source when
   production OpenAPI access and the required account/entitlement state are available.
4. **No qualified source — fail closed.** ATLAS must publish data unavailable/degraded
   state and abstain from new entries rather than silently substitute delayed,
   stale, unqualified or differently entitled data.

This order is a **product-routing decision**, not a claim that all three providers
currently possess equal accepted runtime authority. The frozen Tradier V1 source
qualification and later freshness/streaming work must still complete before the
runtime may promote Tradier to primary. Data-source failover may be automated only
when the fallback source independently satisfies its frozen entitlement, freshness,
identity and quality contract. Provider identity must remain explicit in every
current-data observation.

Execution-broker selection is intentionally independent from market-data routing.
Using the same company for data and execution earns no preference by itself. The
current execution candidates, before a common broker-execution qualification, are:

- **Webull — leading execution candidate** because the existing ATLAS adapter and
  provider-specific safety work are the most mature, the API supplies strong order
  lifecycle controls and deterministic client-order identifiers, and ordinary
  stock/equity-option commission economics are attractive.
- **Alpaca — close execution challenger** because its automation semantics,
  client-order-id recovery, fractional stock support, paper/live workflow and existing
  ATLAS adapter are strong.
- **Tradier — execution challenger** because its trading API and options support are
  viable, but whole-share equity sizing and the need to prove uncertain-submit /
  idempotent-reconciliation behavior leave more execution work before selection.

The eventual execution primary must be chosen from common ATLAS evidence covering
fees, spread/slippage, decision-to-ack/fill latency, partial fills, cancel/replace,
unknown-submit recovery, order-event consistency, option lifecycle behavior and
operational reliability. Market-data-provider rank must not influence that score.

The target operator model is **one normal ACTIVE_EXECUTION broker at a time** with
other qualified brokers allowed to remain connected as standby. ATLAS must never
automatically fail over order placement to another broker. The front end must expose
an explicit Trade Management Broker selector backed by a controlled migration
workflow rather than a raw configuration toggle.

Before activating a target broker, ATLAS must perform read-only preflight and
reconciliation of credentials/connectivity, account identity, funding/buying power,
required trading permissions, current positions, current open orders and any
unresolved provider-mutation state. An unfunded or otherwise unready broker may remain
connected but cannot become ACTIVE_EXECUTION.

If the current broker is flat and reconciled, an explicitly confirmed switch may
move new-trade authority to the target broker. If the current broker has positions or
working orders, the operator must be shown the exposure and choose explicitly among:

- cancel the broker change;
- close/cancel and reconcile the current broker to flat, then switch; or
- keep existing exposure at the old broker while moving **new-trade** authority to
  the target broker.

When existing exposure is retained and the old broker API remains available, the old
broker enters **MANAGE_EXISTING_ONLY**: ATLAS may monitor, reconcile, amend or exit
only the already-existing positions/orders there and may not originate new entries.
The target broker becomes ACTIVE_EXECUTION for new positions. Once the old broker is
proven flat, it returns to CONNECTED_STANDBY.

If the operator switches because access to the old broker API has been lost while
exposure may remain, ATLAS must not discard that exposure or pretend it can still
control it. The broker enters **BROKER_CONTROL_LOST** and the affected positions enter
a local/shadow-management state. ATLAS must preserve the last verified broker
quantity, entry, strategy lineage, intended exit policy and last broker-confirmed
protective SL/TP state; continue valuation and exit analysis from independent
qualified market data; and continue counting the last verified exposure in portfolio,
ticker/family and risk limits. Any broker-side SL/TP is recorded only as **last
confirmed protection**, not asserted to remain active while broker truth is
unavailable.

For a locally managed/unverified position, ATLAS may continue to tell the operator
when its accepted exit logic recommends leaving the trade, but it must clearly state
that it cannot submit or verify the exit at the inaccessible broker. Manual closure
through the broker's own app/site remains available to the operator. After manual
action, the position remains closure-pending until later broker reconciliation or an
explicit, audited manual-resolution workflow establishes the terminal state.

The intended broker/runtime states are therefore distinct:

- `ACTIVE_EXECUTION` — may accept new entries and manage existing exposure;
- `CONNECTED_STANDBY` — connected/readable but has no new-order authority;
- `MANAGE_EXISTING_ONLY` — may manage only exposure already held there;
- `SWITCH_PENDING` — migration/preflight is incomplete;
- `DEGRADED` — broker connection/reconciliation is incomplete but not fully lost;
- `BROKER_CONTROL_LOST` — broker-side exposure may exist but current broker truth
  and mutation authority are unavailable;
- `NOT_READY` — connection may exist but funding/permissions/other activation
  requirements are insufficient;
- `DISCONNECTED` — no usable broker connection.

The corresponding position-management states must distinguish broker-managed exposure
from locally/shadow-managed unverified exposure, manual-action-required exposure,
closure-pending verification and reconciled closed positions.

This direction **supersedes the old product assumption that future switching must
always require both brokers to be flat**, but it does not rewrite the already accepted
Phase 15/16 flat-only PAPER switch contract or promote LIVE broker switching today.
The richer migration model requires a separately versioned successor implementation,
front-end confirmation flow, tests and acceptance evidence before it gains PAPER/LIVE
authority. Automatic execution-broker failover remains prohibited.

## 2026-09-19 — Recurrent successor historical outcome replay bridge

ATLAS now stages **atlas-recurrent-successor-outcome-replay-v1-walk-forward-selector-long-only** as the first historical campaign bridge from accepted successor research artifacts into the current recurrent account lifecycle.

This package reuses the accepted successor conditioning output rather than recomputing strategy rules. Admission remains the frozen 504-session training / 1-session embargo / 63-session test walk-forward selector. For every selected test opportunity, the product-side move/return forecast is rebuilt only from the matching fold's prior training cell; the test opportunity's realized return is not used in its forecast, selection, sizing or reservation.

Frozen v1 mechanics:

1. signal scope remains inside DEVELOPMENT `2016-01-04..2026-04-30`; consumed-master and future-blind rows are forbidden;
2. only `research_eligible AND comparable` conditioning rows enter the candidate stream;
3. the portfolio uses 10% of current book equity per position, at most 10 active/reserved positions, at most 3 per economic family, and one active/reserved position per ticker;
4. current recurrent funding supports LONG stock only. Selected SHORT opportunities are counted and reported but remain unsimulated until a separately versioned short borrow/collateral model exists;
5. admitted opportunities produce genuine training-only `UnderlyingMoveTimeForecast -> SimulationDecisionRecord` evidence and then use the current recurrent RESERVE -> ENTRY -> CLOSE ledger transitions;
6. accepted outcomes are mapped to a normalized $100 entry-price basis so percentage economics and the frozen cost convention are reproduced exactly without pretending to reconstruct historical share quantities;
7. daily rows use the frozen five-session / 10-bps primary outcome and intraday rows use accepted entry/exit timestamps with the 50-bps primary cost convention;
8. recurrent entry/exit costs are split exactly across the two fills; every completed trade must reproduce the accepted primary net return or the run fails closed;
9. outputs include portfolio decisions/rejections, canonical recurrent closed trades, realized book-equity history, finite-cash competition, peak active/reserved slots and policy/family P&L attribution;
10. this is explicitly **OUTCOME_REPLAY_DIAGNOSTIC**. It is not yet the stricter bar-level campaign where historical bars drive decision-bound STOP/TARGET/TIME exits directly;
11. all inputs remain local/hash-bound and provider calls, broker reads/writes, order actions, PAPER, LIVE, promotion and confluence authority remain zero/false.

Operator entry point:

`python scripts/run_recurrent_successor_outcome_replay.py --authorize-development-replay --initial-equity 100000 [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--policy-id POLICY]`

This historical replay does not require the market to be open. PR #161's current-Webull workstation acceptance remains a separate regular-market-hours operational-runtime gate.

## 2026-09-22 — Recurrent workstation market-hours entry-schedule repair

The first target-workstation regular-session acceptance attempt reached the Webull
sandbox L1 SPY quote capture successfully under run id `20260922T133439Z`, then
failed closed before RESERVE admission because the acceptance harness scheduled the
ENTRY cycle at the later quote-bundle capture timestamp while building RESERVE
evidence at the earlier local quote-receipt timestamp.

The durable RESERVE rule `built_at_utc >= scheduled_for_utc` remains unchanged and
correct. The first repair moved ENTRY scheduling to
`quote.received_at_utc`—the first ATLAS-observable time for that evidence.

A second isolated run, `20260922T140229Z`, again captured SPY successfully but exposed
the remaining fixture defect: the recurrent cycle was created at the later bundle
capture timestamp and RESERVE was then applied using the earlier quote receipt time.
The durable cycle invariant correctly rejected the update as preceding cycle creation.

The final fixture chronology is now explicit and monotonic:

`provider <= receipt = schedule = reserve-build <= bundle-capture = cycle-begin = CLOSE/RESERVE-apply`.

ENTRY acceptance artifacts retain schedule, quote-receipt, bundle-capture and
cycle-action timestamps. Regression coverage now protects both the RESERVE evidence
schedule invariant and the cycle-update-after-creation invariant. No production
recurrent or evidence contract was weakened.

The third isolated regular-session run, `20260922T142213Z`, completed the
full acceptance path successfully. ENTRY passed, restart/MARK passed, the immutable
one-minute horizon was respected, TIME CLOSE passed, and the exact persisted CLOSE
bundle replayed idempotently after a second restart. The final closed-trade count
remained exactly 1 and cycle health reported `OPEN_CYCLE`.

Accepted receipt fingerprint:

`d0f880a85d5f07c0ddc68c7d3017a0ae0e3bacc04d5e0bb6473da3f601340c4a`

This closes the frozen PR #161 current-Webull regular-market-hours operational-runtime
acceptance gate for `atlas-recurrent-workstation-acceptance-v1`. The accepted run
used exactly three explicit read-only Webull sandbox L1 captures; provider writes,
broker reads/writes, order creation, PAPER, LIVE, promotion and confluence authority
all remained zero/false. This is a product/runtime acceptance proof, not strategy
evidence and not trading authorization.

The immutable chronology incident remains
`docs/research/recurrent_workstation_acceptance_entry_schedule_incident_20260922.md`.
The accepted closeout is
`docs/research/recurrent_workstation_acceptance_closeout_20260922.md`.

## 2026-09-19 — First recurrent successor workstation portfolio replay

The first workstation historical portfolio replay completed successfully for signal scope
`2025-01-01..2025-12-31` under recurrent successor outcome-replay contract
`99c3b32b1905db3204646bac302a5b6836e843cbfe73d7647da9a84b8b879452`.
Run fingerprint: `2096fe4bc3babdd80c667a0548ab24a861a586bd08f880237744f11b23378166`.

Observed portfolio/account result:

- 4,685 selected comparable opportunities;
- 3,650 LONG supported by current recurrent cash-stock funding;
- 1,035 SHORT retained as reported-only because short borrow/collateral remains unsupported;
- 439 positions admitted and completed = about 12.0% of supported LONG selections;
- starting book equity $100,000.00;
- ending book equity $101,647.15;
- total return +1.6472%;
- maximum realized/book-equity drawdown -20.9896%;
- peak active/reserved slots = 10;
- rejections: 2,429 max-per-family, 458 max-open-position, 262 insufficient-capital, 62 ticker-already-active/reserved.

The rejection counts reconcile exactly to the 3,211 supported LONG opportunities that
were not admitted. The dominant constraint was the frozen three-position-per-family
cap, which rejected roughly two-thirds of all supported LONG selections and roughly
three-quarters of all rejected LONG opportunities. The account therefore demonstrated
real portfolio competition rather than simply summing independent trade outcomes.

This result is **diagnostic, not validation**. It is positive at the endpoint but carries
a large realized/book-equity drawdown relative to the return, omits selected SHORT
trades, and replays already accepted outcomes rather than allowing bar-driven
STOP/TARGET/TIME mechanics to determine exits. No strategy, selector, family, or
portfolio rule is promoted or retuned from this result.

Immediate simulation continuation is the separately versioned bar-level historical
campaign. It must preserve training/test chronology, reread only accepted DEVELOPMENT
bars, keep the recurrent account as the single portfolio truth, and let frozen
decision-bound STOP/TARGET/TIME policies determine exits directly. Any later changes
to sizing, family caps, entry/exit policy, or short funding must be new explicit
versions rather than silent reinterpretations of this run.

## 2026-09-20 — Static daily exits rejected across regimes; Dynamic Exit V1 frozen

The unchanged 2%/5% and 3%/5% static daily exit candidates completed the
retrospective 2018–2024 DEVELOPMENT regime map.

Run fingerprint:
`60989a10985973bff48d3d2a82a633282b62e664f22f5c3fac4c35bfee380ede`.

Across seven annual regimes, each static geometry was positive in only one year:

| Year | 2% STOP / 5% TARGET | 3% STOP / 5% TARGET |
| --- | ---: | ---: |
| 2018 | -15.75% | -8.98% |
| 2019 | +6.60% | +6.64% |
| 2020 | -8.71% | -11.18% |
| 2021 | -21.19% | -18.76% |
| 2022 | -24.87% | -27.74% |
| 2023 | -9.79% | -9.24% |
| 2024 | -11.00% | -16.30% |

The 2%/5% median annual return was -11.00% with worst marked drawdown -25.32%.
The 3%/5% median annual return was -11.18% with worst marked drawdown -28.38%.
Combined with the failed Jan–Apr 2026 forward confirmation, this closes the
hypothesis that either fixed geometry is a robust universal exit rule.

Dynamic Exit V1 is now preregistered as a separate DEVELOPMENT research package.
It does not fit arbitrary percentages. It chooses from six frozen geometries:
1%/2%, 1%/3%, 1%/5%, 2%/3%, 2%/5%, and 3%/5%, plus an explicit ABSTAIN action.
Every trade retains a fixed five-session horizon in V1.

Selection uses only completed prior walk-forward folds from approximately the last
two years (eight folds). The current fold and current trade future path are forbidden.
Supported cells require at least 60 prior cases, 30 sessions, and 20 instruments.
Context fallback is based on strategy policy, market volatility state, higher-timeframe
ticker trend, realized-volatility bucket, and market-direction alignment.

Each candidate exit action is scored from prior realized net returns after the frozen
10-bps split entry/exit cost. The selector uses an equal-weight session-mean return and
a one-sided 95% lower-confidence bound. If no supported action has a positive robust
lower bound and positive mean trade return, ATLAS abstains rather than forcing a trade.

Dynamic Exit V1 first produces selector diagnostics only. Portfolio competition,
position admission, recurrent account compounding, and account return are deliberately
deferred until the selector passes this anti-lookahead gate.

### Dynamic Exit V1 first-run closeout — 2026-09-25

The frozen DEVELOPMENT-only Dynamic Exit V1 completed its original run under
`560b35765e82b2ab5fb59f8b00cc641f28112232bf89a994fdb0637f069a2b5b`.
It verified all 546 source parts and evaluated 22,604 usable daily LONG cases
over 32 folds. It selected 535 cases (2.37%), abstained 22,069, and chose
only STOP 2%/TARGET 5% (49) or STOP 3%/TARGET 5% (486). The selected-case
realized net mean was -0.058%, median -2.099%, P(positive) 41.31%.
The 2025 selected mean was +0.147% across 354 cases, but the later Jan–Apr
2026 mean was -0.468% across 176 cases. These are trade diagnostics, not
account returns, and do not support dynamic-exit promotion or modification
of prior failed exit decisions.

The read-only command below shows the stored breakdown of insufficient
training-context support versus supported cells with no positive robust LCB.
It validates the first-run summary without repeating the large source scan
or consuming provider credits:

~~~powershell
git checkout main; git pull
.\.venv\Scripts\python.exe scripts\inspect_recurrent_successor_dynamic_exit_v1.py
~~~

Original retained report:
`data/research/recurrent_successor_dynamic_exit_v1/db538c8cc72189d4/560b35765e82b2ab/dynamic_exit_v1_summary.json`.
Record and disposition:
`docs/research/recurrent_successor_dynamic_exit_v1_acceptance_20260925.md`.
This does not block a separately preregistered news/options challenger; it
does prevent treating V1 as an accepted exit policy.

## 2026-09-19 — 2026 forward exit confirmation failed; regime map frozen

The chronologically forward DEVELOPMENT confirmation for the two frozen 2025
daily-exit candidates completed over `2026-01-01..2026-04-30`.

Run fingerprint:
`bd8e1fd32d2c34e8699e6e243e851c936c475e0d5b16fc4f6047d5f02e40f210`.

The confirmation contained 1,831 usable selected daily LONG cases:

- 2% STOP / 5% TARGET: -6.38% endpoint return, -9.88% maximum marked-equity
  drawdown, -9.93% book-equity drawdown, 282 completed positions,
  190 STOP / 66 TARGET / 26 TIME exits;
- 3% STOP / 5% TARGET: -6.97% endpoint return, -10.42% maximum marked-equity
  drawdown, -10.45% book-equity drawdown, 236 completed positions,
  130 STOP / 62 TARGET / 44 TIME exits.

Both candidates therefore failed the first chronologically later confirmation window.
Neither static geometry is promoted. The result is preserved rather than retuned around:
the candidate set remains unchanged for retrospective robustness mapping.

ATLAS now freezes annual DEVELOPMENT regime checks for 2018 through 2024 under
`atlas-recurrent-successor-daily-exit-regime-robustness-v1`. Each calendar regime
resets to the same starting equity and runs both unchanged candidates through the same
recurrent account, source, costs, compounding-within-regime, sizing/cap constraints,
collision/gap semantics and five-session TIME exit.

This backward regime map cannot rescue the failed 2026 confirmation. Its purpose is to
identify whether static exit performance is regime-dependent and to provide evidence
for the next research package: Dynamic Exit V1, where STOP/TARGET/TIME selection will
use only point-in-time regime, volatility and prior path/forecast evidence.

## 2026-09-19 — 2025 recurrent daily exit sweep result and forward confirmation freeze

The first bar-driven recurrent daily exit sweep completed for
`2025-01-01..2025-12-31`.

Run fingerprint:
`2726c3a644ac22ed3238adf5b03e978152eaa50a5d0e91fc937716309f0db9f4`.

The sweep had 3,520 usable selected daily LONG cases and compared the preregistered
16 STOP/TARGET combinations. Only two policies finished the 2025 window positive:

- 2% STOP / 5% TARGET: +1.45% endpoint return, -9.20% maximum marked-equity
  drawdown, -9.06% book-equity drawdown, 649 completed positions, with
  397 STOP / 160 TARGET / 92 TIME exits;
- 3% STOP / 5% TARGET: +0.46% endpoint return, -13.11% maximum marked-equity
  drawdown, -13.26% book-equity drawdown, 575 completed positions, with
  286 STOP / 169 TARGET / 120 TIME exits.

All other frozen policies were negative in this tuning window. Narrower targets were
especially weak: every 1% target policy lost at least 29%, while 2% and 3% targets were
also negative across all tested stops.

This does **not** promote 2%/5% or 3%/5%. The result is post-result DEVELOPMENT tuning
evidence only. It also is not a direct apples-to-apples replacement for the earlier
outcome replay because the population and exit mechanics differ. The useful product
finding is that bar-driven exits materially change capital recycling, admission and
drawdown behavior inside the recurrent account.

Before inspecting any later result, ATLAS now freezes exactly those two positive 2025
policies as confirmation candidates under
`atlas-recurrent-successor-daily-exit-candidate-confirmation-v1`.

Primary confirmation is chronologically forward within DEVELOPMENT:
`2026-01-01..2026-04-30`. Candidate membership cannot change from that result.
The 2026 confirmation remains DEVELOPMENT-only and grants no promotion, PAPER or LIVE
authority. Earlier-regime robustness checks follow afterward with the same candidates
unchanged.

## 2026-09-19 — Recurrent daily exit-policy sweep preregistration

ATLAS now stages a bounded post-result DEVELOPMENT exit-policy research package under
`atlas-recurrent-successor-daily-exit-policy-sweep-v1`.

The package keeps the accepted successor selector and recurrent portfolio mechanics
fixed, then compares exactly 16 daily LONG exit policies: STOP and TARGET each drawn
from the already frozen 1%, 2%, 3%, and 5% move thresholds. Position sizing remains
10% of current book equity with compounding, at most 10 active/reserved positions,
at most 3 per economic family, and one active/reserved position per ticker.

Execution uses only the hash-bound Alpaca SIP V2 DEVELOPMENT daily lake for selected
instruments. Entry is the next regular-session open. STOP/TARGET are evaluated from
actual daily OHLC. Same-session STOP+TARGET ambiguity resolves conservatively to STOP.
An adverse gap through the stop fills at the worse session open. A favorable gap
through the target receives no positive slippage beyond the target. If neither trigger
occurs, TIME closes at the fifth entry-session regular close. Entry/exit costs retain
the accepted 10-bps daily round-trip convention.

The current fold's outcome is forbidden from its forecast. Return-distribution
evidence remains training-cell-only; 1/2/3/5% path probabilities and timing are bound
from strictly earlier selected folds with at least 30 prior cases. The recurrent
decision record, decision-bound exit plan, five-session horizon clock, actual fill,
daily historical replay marks, closeout and account ledger remain the canonical
simulation lineage.

This is DEVELOPMENT tuning research only. The sweep does not automatically promote
the highest-return policy. Any candidate emerging from the 2025 diagnostic must be
tested across other DEVELOPMENT regimes and later untouched/prospective evidence.
SHORT simulation remains excluded until a separate accepted short funding/collateral
model exists. Consumed-master/future/provider/broker/order/PAPER/LIVE/promotion/
confluence authority remains zero/false.

## 2026-09-16 — Explicit simulation funding/collateral terms

Track A now freezes the funding boundary under contract `f76d77ebbf138924a22813773ad27276b0fa71691ddff1d21040171c7b6d3821`
(`atlas-simulation-funding-collateral-terms-v1`). It consumes only the exact accepted
simulation account-state v2 snapshot and exact broker-neutral entry-fill evidence. The
terms object is descriptive evidence only: it does not mutate the account, release a
reservation, create a position, borrow funds, create an order, mark to market, realize
P&L, read/write a broker/provider, or grant PAPER/LIVE/promotion/confluence authority.

V1 permits a **fully cash-funded bullish stock long only**. Required cash is exact
filled gross notional plus explicit entry fees. The existing stock reservation is
credited toward that requirement and any remaining amount must be proven available in
the account's currently unreserved cash pool. Insufficient supplemental cash fails
closed. Borrowing, margin, leverage, collateral and short-sale proceeds remain exactly
zero and are never inferred from the accepted economic-capital/gross-notional gap.
Bearish stock/short position conversion therefore remains unsupported until a separate
versioned short-collateral/proceeds model is accepted.

Long options reuse the already-resolved debit from accepted fill evidence. Required
cash equals the exact filled premium debit plus accepted entry fees, supplemental cash
is zero, and any unspent option reservation remains explicit for the later atomic
position transition. Option delta-equivalent exposure remains separate from stock
gross notional and is not reinterpreted as funding or collateral.

That funding boundary is now consumed by the deterministic open-position entry-book
account state described below. Mark-to-market, unrealized/realized P&L, exits/closeout,
broker mutation and PAPER/LIVE authority remain later gates. The Strategy Evidence
Register is intentionally unchanged because these packages change product simulation
architecture only.

## 2026-09-16 — Deterministic open-position entry-book account state

Track A now adds `atlas-simulation-open-position-account-state-v1` under contract
`c15c03400d61bf9e025f836118bf431178caadbdfc7c9a62826ec03796a0ee37`. It consumes one immutable accepted reservation-account snapshot plus
exact simulated entry-fill and funding/collateral evidence, then converts reservations
into deterministic **entry-book-value open positions**. The source reservation batch is
never rewritten: every fill and funding record remains bound to the exact account-state
fingerprint against which it was created, while the position layer tracks which source
reservations remain unconverted.

Each transition releases exactly one matching reservation and updates cash as
`current cash + released reservation - accepted required cash`. Cash is rechecked at
the moment of transition, so multiple fills that were individually affordable against
the same original unreserved-cash pool cannot spend those dollars twice. Same-fill
reapplication is idempotent; a different fill for an already-open decision fails
closed. Batch application is deterministic by `(filled_utc, fill_fingerprint)`, and
state/event/ledger fingerprints support exact replay verification and tamper detection.

Entry fees are expenses immediately: `entry book equity = initial equity - cumulative
entry fees`, while `cash + remaining reservations + open entry book value` must equal
that entry-book equity. Stock gross exposure transfers exactly from the reservation to
the cash-funded bullish stock position. Long-option premium paid becomes option entry
book value/premium at risk; the reservation's signed/absolute delta-equivalent exposure
is retained only as an **entry reference**, not a current Greek or mark. Stock shorts
remain unsupported because no accepted collateral/proceeds model exists.

The open-position package deliberately stops before market valuation. The source-bound
market-mark evidence layer described below now supplies exact valuation provenance, but
mark-to-market, unrealized/realized P&L, exits/closeout, broker mutation and PAPER/LIVE
authority remain separate gates. The Strategy Evidence Register remains unchanged
because these packages change product/account-simulation architecture only.

## 2026-09-16 — Source-bound market-mark evidence

Track A now freezes `atlas-simulation-market-mark-evidence-v1` under contract
`1219f600e447f90718213ce0f974314f6480e90e13f46487770785e45c87c154`. The package binds one immutable mark record to one exact accepted
open-position fingerprint and requires explicit source id/SHA-256, provider, feed,
transport, feed-quality, market timestamp, receive timestamp, and valuation timestamp.
It is evidence-only: the accounting layer still performs no provider or broker read.

For the currently supported long stock and long-option positions, v1 selects the
**executable bid** as the conservative valuation candidate. Midpoint and last may be
retained descriptively but are never treated as liquidation truth. Stock requires a
positive bid; a long option may legitimately carry a zero bid, preserving a possible
zero liquidation value rather than inventing one. Crossed quotes fail closed.

Freshness is frozen at a maximum **60 seconds** from market timestamp to valuation
time. `market_timestamp <= received_timestamp <= valuation_timestamp` is mandatory.
A stale observation is retained for audit but is explicitly
`valuation_eligible = false`; it cannot create or carry forward P&L. The 60-second
limit is a versioned simulation policy rather than a permanent provider constant.

The market-mark package itself remains evidence-only and grants no account mutation,
realized P&L, exit/closeout, provider/broker, order, PAPER, LIVE, promotion or
confluence authority. The deterministic marked-account layer described below now
consumes those fresh marks for simulation valuation and unrealized P&L. The Strategy
Evidence Register remains unchanged because these packages change
product/account-simulation architecture only.

## 2026-09-16 — Deterministic marked account and unrealized P&L

Track A now adds `atlas-simulation-marked-account-state-v1` under contract
`f09a1ead48e86ae82442785f281c0e57d242db3773537a3ba64a44bb2519c082`. It consumes the exact accepted open-position account snapshot plus
one exact fresh, valuation-eligible market-mark record for **every** active position at
one common valuation timestamp. Missing, stale, duplicate, mismatched, or extra marks
fail closed; ATLAS does not publish an authoritative account-level marked-equity value
for an incomplete valuation snapshot.

For each active position, marked value is `quantity * selected bid mark * multiplier`.
Unrealized P&L is marked value minus immutable entry book value, and unrealized return
uses entry book value as its denominator. Account unrealized P&L is the sum of the
position values, while marked equity is `entry_book_equity + aggregate_unrealized_P&L`
and independently reconciles to `cash + remaining reservations + marked open-position
value`. Entry fees were already expensed when the position opened and are therefore
never subtracted a second time in unrealized P&L.

A long option with a valid fresh zero bid may mark to zero and therefore to a full loss
of its entry book value. Option delta-equivalent exposure remains the immutable
**entry reference** only; this package does not infer a current Greek from price marks.
All marked positions share the requested valuation timestamp, and a mark whose market
timestamp predates the position open is rejected. Empty accounts produce a complete
zero-position valuation deterministically.

This is deterministic simulation valuation only. It does not mutate the open-position
state and grants no realized-P&L, exit/closeout, provider/broker, order, PAPER, LIVE,
promotion or confluence authority. The next bounded Track A work is broker-neutral
simulated exit-fill evidence followed by deterministic closeout/realized-P&L accounting
with lifetime trade-P&L and account-equity semantics kept explicit so entry fees cannot
be double counted. The Strategy Evidence Register remains unchanged because this is
product/account-simulation architecture only.

## 2026-09-17 — Broker-neutral simulated exit-fill evidence

Track A now adds `atlas-simulated-exit-fill-evidence-v1` under contract
`d823bdf481f6ae6266be0a7e87d36702e1687d5a84f97da105e64cfc7e8f77c0`.
It consumes the exact accepted open-position account state, requires one exact active
open-position fingerprint, and binds a complete exit fill to an explicit source id,
source SHA-256, timezone-aware exit timestamp, exit price, and explicit exit fees.

V1 is deliberately **full-close only**. Quantity, quantity unit, instrument identity,
position lineage, and contract multiplier are inherited exactly from the active open
position; callers cannot silently resize or partially close a position. Gross exit
proceeds are `quantity * exit_price * multiplier`, and net exit proceeds are gross
proceeds less explicit exit fees. Exit price may be zero so a long stock/option
complete-loss case remains representable; exit fees may not exceed gross proceeds.

This object is descriptive broker-neutral fill evidence only. It does not remove the
position, mutate account cash, compute realized P&L, read/write a provider or broker,
create an order, assert a broker fill, or grant PAPER/LIVE/promotion/confluence
authority. The deterministic closeout layer described below now consumes this
evidence. The Strategy Evidence Register remains unchanged because this package
changes product/account-simulation architecture only.

## 2026-09-17 — Deterministic closeout and realized-P&L accounting

Track A now adds `atlas-simulation-closeout-account-state-v1` under contract
`d8363e6a0dba68ad8894691a308eff6231770e59ccea909a38fd95af317aa599`.
It consumes the exact accepted open-position account snapshot plus exact accepted
broker-neutral exit-fill evidence. Only the matched active position is removed;
unrelated positions and all remaining reservations are preserved exactly, while exact
net exit proceeds are returned to simulation cash.

The accounting boundary deliberately distinguishes two realized-P&L meanings. The
**account-state realized-P&L delta** is `net_exit_proceeds - entry_book_value`
because entry fees were already expensed when the position opened. The **lifetime
trade net P&L** is `gross_exit_proceeds - entry_book_value - entry_fees - exit_fees`.
For every closed trade, lifetime net P&L therefore equals account realized-P&L delta
less the already-expensed entry fee. Account book equity is
`initial_equity - cumulative_entry_fees + cumulative_account_realized_pnl` and
independently reconciles to cash plus remaining reserved capital plus remaining open
entry-book value.

Closeout transitions are chronological, fingerprint chained, and deterministic.
Reapplying the identical exit-fill fingerprint is idempotent; a different second
exit against an already closed position fails closed. Batch application is ordered by
exit timestamp/fingerprint and the full state/ledger can be reconstructed and
fingerprint-verified by deterministic replay. Closed-trade evidence retains entry and
exit economics, both fee layers, holding duration, instrument/strategy lineage, and
the two P&L views.

This remains simulation-only lifecycle accounting. It grants no provider/broker
read/write, order, PAPER, LIVE, promotion, or confluence authority. The post-close
valuation layer described below closes the remaining current-marked-equity gap before
browser integration. The Strategy Evidence Register remains unchanged because this
package changes product/account-simulation architecture only.

## 2026-09-17 — Post-close lifecycle marked-account state

Track A now adds `atlas-simulation-lifecycle-marked-account-state-v1` under contract
`4cc4fb35c5a95cb48603f581a48127fe188c844c44e445394ad3d662e07a5346`.
This closes the valuation gap that appears after one or more positions have been
deterministically closed: the closeout account remains the current book/realized-P&L
truth, while fresh mark evidence remains bound to each surviving immutable position.

The lifecycle valuation consumes the exact closeout-account fingerprint plus exactly
one fresh, valuation-eligible mark for every **currently open** position at one common
valuation timestamp. Missing, duplicate, stale, closed-position, or other extra marks
fail closed. Closed trades are never revalued. Current marked position value and
unrealized P&L are computed only for surviving positions, while cumulative entry fees,
exit fees, account-realized P&L, and lifetime trade net P&L are carried forward
unchanged from the accepted closeout state.

Marked equity is `account_book_equity + aggregate_unrealized_pnl` and independently
reconciles to cash + remaining reserved capital + current marked open-position value.
An account with no surviving positions has complete zero-mark coverage and marked
equity equal to closeout book equity. Option delta-equivalent exposure remains an
immutable entry reference only; current Greeks are not inferred from price marks.

This layer performs simulation valuation only. It grants no account mutation, new
realized P&L, exit/closeout, provider/broker read/write, order, PAPER, LIVE, promotion,
or confluence authority. The read-only operator projection described below now
consumes this current post-close truth. The Strategy Evidence Register remains
unchanged because this is product/account-simulation architecture only.

## 2026-09-17 — Engine-owned simulation lifecycle observability

Track A now adds a read-only lifecycle projection to the existing loopback
control-plane/browser surface. `SimulationLifecycleDashboardService` accepts only an
injected pair of accepted engine objects: the deterministic closeout account and the
post-close lifecycle marked-account state. It independently revalidates closeout
state/ledger fingerprints, the marked-state fingerprint, exact source-state binding,
carried accounting fields, and current open-position/mark lineage before exposing any
payload.

The new local endpoint is `/api/v1/ops/simulation-lifecycle`. It never initializes a
provider, broker, order adapter, or legacy execution-artifact fallback. With no
injected engine source it returns explicit `NOT_CONNECTED`; an invalid injected
source returns `INVALID`. Only a fingerprint-valid engine-owned source is rendered
as `AVAILABLE`.

The browser adds a Track A simulation-lifecycle panel showing current marked/book
equity, cash, realized and unrealized P&L, fee layers, currently open marked
positions, deterministic closed trades, and source fingerprints. It uses the existing
`atlas:observability-refreshed` event, adds no independent timer, performs GET only,
and carries zero browser/provider/broker/order mutation authority. The synthetic
preview server exposes the same response shape for UI development while remaining
explicitly synthetic and read-only.

This closes the projection/UI seam. The single-cycle coordinator described below now
supplies the accepted atomic engine-owned source, while post-close re-entry remains a
separate next lifecycle boundary. The Strategy Evidence Register remains unchanged.

## 2026-09-17 — Atomic single-cycle simulation lifecycle coordinator

Track A now implements the first production-facing lifecycle owner in the previously
empty `packages/simulation/engine.py` seam under contract
`atlas-simulation-lifecycle-coordinator-v1`
(`696254240971db5a9a7ae2a0307c2c847b376d360d5cfe1f8b5f30ec80a93a9b`).

`SimulationLifecycleCoordinatorV1` starts from one exact accepted
`OpenPositionAccountStateV1`, deterministically initializes the accepted closeout
account, and then owns that cycle's current closeout book state plus an optional
post-close marked state. It performs no provider, broker, order, or filesystem I/O;
exit fills and market marks must already exist as accepted evidence before they are
supplied.

The coordinator uses one re-entrant lock and immutable state replacement so readers
can obtain an atomic book+valuation pair. A real closeout event advances the logical
revision and invalidates any prior marked state. Reapplying an identical idempotent
exit does not mutate state, advance the revision, or destroy a still-current
valuation. Mark publication requires the accepted complete/fresh current-position
coverage contract; an identical mark snapshot is idempotent. Revision advancement is
defined by actual new closeout ledger events plus new valuation publications, so
sequential and batch application converge to the same logical revision and replay
fingerprint.

The control-plane adapter now converts only `current_dashboard_pair()` into the
read-only lifecycle projection. Until current marks exist—or immediately after a
closeout invalidates them—the browser remains `NOT_CONNECTED` rather than displaying
stale valuation. `create_phase19_status_server` may accept either an explicitly built
lifecycle dashboard service or a lifecycle coordinator, never both.

This is deliberately a **single-cycle** coordinator. It does not create new
reservations, accept new entries after the immutable source snapshot, or support
re-entry. Those capabilities remain outside v1 so current-state ownership can be
accepted independently before the account model is extended across subsequent
decision/entry cycles. No provider/broker/order/PAPER/LIVE/promotion/confluence
authority is created.

The lifecycle-native reservation layer described below now begins that post-close
re-entry path without conflating reservation with a filled position. The Strategy
Evidence Register remains unchanged.

## 2026-09-17 — Lifecycle-native post-close re-entry reservations

Track A now adds `atlas-simulation-lifecycle-reservation-account-v1` under contract
`b4b825cca77a59f2d65064c9644d513714968f4ae7b8cea03f0738411d3459bb`.
This is the first re-entry/account-continuation layer that operates against a
**current lifecycle book** rather than restarting the old reservation-only account
model after positions or realized P&L already exist.

The state is initialized from one exact accepted `CloseoutAccountV1` and carries
forward, unchanged, the closeout state/ledger fingerprints, current open positions,
closed trades, cumulative entry/exit fees, account-realized P&L, lifetime trade net
P&L, cash, book equity, and any still-active reservations. New decision records may
then reserve stock capital or long-option capital from **current unreserved cash**.
Reservations reduce cash and increase their dedicated reserved-capital/exposure
buckets while account book equity remains unchanged and continues to reconcile as
`cash + stock reservations + option reservations + open entry-book value`.

Reserved stock gross notional remains separate from existing open-stock exposure.
Reserved option signed/absolute delta-equivalent notional, max-loss cash, and premium
at risk remain separate from the immutable entry-reference exposure of already-open
options. Long-option reserved max loss remains equal to reserved option capital.
Abstentions, missing option terms, and insufficient-current-cash decisions are
fingerprint-chained ledger events with zero capital mutation. Duplicate decisions are
idempotent; conflicting option terms fail closed; chronological batch replay
reconstructs exact state and ledger fingerprints.

This package intentionally creates **no entry fill or new position**. Existing open
and closed histories are immutable across reservation transitions, and one decision
cannot exist simultaneously in an active reservation/open bucket and the closed
history. No mark, closeout, provider/broker/order, PAPER/LIVE, promotion, or
confluence authority is created.

The lifecycle-native fill/funding evidence layer described below is required first
because the earlier accepted evidence contracts are explicitly bound to the legacy
reservation-only account contract. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Lifecycle-native re-entry fill and funding evidence

Track A now adds two descriptive lifecycle-native evidence contracts required before a
post-close reservation can become a new open position:

- `atlas-simulation-lifecycle-entry-fill-evidence-v1`
  (`a2bcaddbfba19370af070217cd2c4b911b121797abb76348747e575e17aa3b3c`);
- `atlas-simulation-lifecycle-funding-terms-v1`
  (`26266be782240511baadeb73d11aef393aaa6a52f12883b30cd3aab025f54870`).

This versioning is necessary rather than cosmetic. The earlier accepted
`atlas-simulated-entry-fill-evidence-v1` and
`atlas-simulation-funding-collateral-terms-v1` explicitly require
`atlas-simulation-account-state-v2-stock-option-reservations` as their account input.
After deterministic closeout, the authoritative reservation account is instead
`atlas-simulation-lifecycle-reservation-account-v1`, whose fingerprint also carries
open/closed history and realized accounting. Reusing the old evidence contracts would
therefore misstate provenance.

The lifecycle-native fill evidence binds one exact current lifecycle reservation-state
fingerprint, decision fingerprint, active reservation fingerprint, economic candidate,
explicit fill source id/SHA-256, timestamp, price, and entry fees. Stock quantity is
derived from the exact reserved economic notional and executable fill price; stock
funding remains unresolved at the fill-evidence layer. Long-option fills reuse the exact
accepted reservation terms, require the reserved contract count/multiplier, cap premium
debit and fees at the accepted reservation buckets, and record exact unspent reserve.

The lifecycle funding object then proves funding against the same current lifecycle
reservation state. Bullish stock longs remain cash-only: reserved capital is credited
first and any remaining required cash must come from **current unreserved lifecycle
cash**. Long options reuse the exact resolved reserved debit and may not require
supplemental cash. Prior realized P&L and prior fee history are not recomputed. Both
objects remain descriptive only and create no reservation release, account mutation,
position, provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

The atomic reservation-to-position layer described below now consumes this evidence.
The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Lifecycle-native reservation-to-position account state

Track A now adds `atlas-simulation-lifecycle-position-account-v1` under contract
`7c5f2a82a8583b9f7b2e90f994f7d6ca4c682888448b97ad287e79e6dad82f29`.
It consumes one exact accepted lifecycle reservation snapshot plus lifecycle-native
entry-fill and funding evidence and performs the first post-close **re-entry position
mutation**.

Initialization carries the exact lifecycle reservation state/ledger fingerprints,
current cash, active reservations, pre-existing open positions, closed trades, fee
history, account-realized P&L, lifetime trade net P&L, and book equity forward. Each
entry must bind the immutable source reservation snapshot and an exact reservation
that is still active in the current mutation state. Only that matched reservation is
removed and one exact new `SimulatedOpenPositionV1` is created.

Entry accounting remains explicit. Stock cash becomes current cash minus supplemental
cash plus any unspent reserve; long-option cash adds only the exact unspent reserved
debit. The new entry fee is added to cumulative entry fees **once**, while prior
realized P&L and exit fees remain unchanged. Account book equity remains
`initial_equity - cumulative_entry_fees + cumulative_account_realized_pnl` and must
also reconcile to current cash + remaining stock reservations + remaining option
reservations + total open entry-book value.

A critical competition rule is enforced at mutation time. Multiple fill/funding
objects may each have been individually fundable against the same immutable source
reservation snapshot, but deterministic application is ordered by fill timestamp then
fill fingerprint and each new entry must still have enough **current remaining cash**.
Thus stale per-fill source projections cannot overspend the account. Identical duplicate
fill/funding application is idempotent; a different second fill for an already-open
decision fails closed; state and ledger replay are exact.

This v1 creates positions only. It does not create new reservations after the source
snapshot, close positions, mark to market, read/write providers or brokers, create
orders, or grant PAPER/LIVE/promotion/confluence authority.

The lifecycle post-reentry valuation layer described below now binds current marks to
this position state. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Lifecycle post-reentry marked-account state

Track A now adds `atlas-simulation-lifecycle-position-marked-account-v1` under
contract
`ba944922450d570ac15b6b28794cfe0cb2c7894cba0e62d09e0957df35c92863`.
It provides the account-level current valuation required after lifecycle-native
re-entry creates new positions.

Individual `SimulatedMarketMarkEvidence` objects remain reusable because they are
bound to immutable position fingerprints rather than to the older account contract.
The account-level valuation is versioned, however, because the accepted source is now
`LifecyclePositionAccountStateV1`, not the pre-reentry closeout snapshot.

The builder requires exactly one fresh, valuation-eligible mark for every currently
open lifecycle position at one common valuation timestamp. Missing, duplicate, stale,
or extra marks fail closed. Closed trades are never revalued. Current marked value and
unrealized P&L are computed for all surviving pre-existing and newly re-entered
positions while cumulative entry/exit fees, realized P&L, lifetime trade net P&L,
cash, remaining reservations, and book equity are carried forward unchanged.

Marked equity remains `account_book_equity + aggregate_unrealized_pnl` and must
independently reconcile to current cash + stock reservations + option reservations +
marked open-position value. This package performs valuation only and grants no account
mutation, new realized P&L, exit/closeout, provider/broker/order, PAPER/LIVE,
promotion, or confluence authority.

The lifecycle-native exit-evidence layer described below now supplies the exact
post-reentry exit provenance. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Lifecycle-native post-reentry exit-fill evidence

Track A now adds `atlas-simulation-lifecycle-exit-fill-evidence-v1` under contract
`f3a952f971d693dbc0ca098d9eb5ff912d54443b9dcf2580409bb5558285df74`.
This is the descriptive exit boundary for positions held by
`LifecyclePositionAccountStateV1`.

A new exit-evidence version is required because the earlier accepted
`atlas-simulated-exit-fill-evidence-v1` explicitly consumes the pre-reentry
`atlas-simulation-open-position-account-state-v1` snapshot. Newly re-entered
positions and their current account history now live under the lifecycle position
contract, so reusing the old account-level source fingerprint would lose provenance.

The builder requires one exact lifecycle position-account state fingerprint and one
exact active position fingerprint. Quantity, quantity unit, instrument/option identity,
entry-fill/funding/reservation lineage, and contract multiplier are inherited from
that position. Exit evidence binds an explicit source id/SHA-256, timezone-aware exit
timestamp, nonnegative exit price, and explicit nonnegative exit fees. Gross proceeds
are `quantity * exit_price * multiplier`; net proceeds are gross less exit fees.
Zero-price complete-loss exits remain representable, while fees may never exceed gross
proceeds. V1 is full-close only.

This object remains descriptive broker-neutral evidence. It does not remove the
position, mutate account cash, compute realized P&L, read/write providers or brokers,
assert a broker fill, create an order, or grant PAPER/LIVE/promotion/confluence
authority.

The deterministic lifecycle closeout layer described below now consumes this evidence.
The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Lifecycle-native post-reentry deterministic closeout

Track A now adds `atlas-simulation-lifecycle-closeout-account-v1` under contract
`9588c3ac326a78103803371071655f0133608beaf0fb10ee7932b3cf0cbace1b`.
It consumes one exact lifecycle position-account state plus exact lifecycle exit-fill
evidence and performs deterministic realized-P&L closeout after re-entry.

The source lifecycle position state/ledger fingerprints are frozen at initialization.
Each accepted exit must still match one currently open position exactly and reproduce
its decision, reservation, entry-fill, funding, instrument, quantity, multiplier, and
option lineage. Only the matched position is removed; remaining reservations and
unrelated positions are unchanged. Exact net exit proceeds return to cash.

The closeout keeps two historical record classes deliberately separate. Closed trades
that predate lifecycle re-entry remain immutable `ClosedTradeV1` records with their
original open-position source semantics. New post-reentry exits append
`LifecycleClosedTradeV1` records whose source fingerprint explicitly names the
lifecycle position-account snapshot. This avoids relabeling old provenance merely to
make the collections uniform.

For every new lifecycle closed trade, account realized-P&L delta remains
`net_exit_proceeds - entry_book_value`; lifetime trade net P&L remains that delta
minus the already-expensed entry fee. Cumulative entry fees never change at closeout,
while cumulative exit fees, account realized P&L, and lifetime trade net P&L add only
the new closeout contribution. Book equity remains
`initial_equity - cumulative_entry_fees + cumulative_account_realized_pnl` and must
also equal cash + remaining reservations + remaining open entry-book value.

Identical exit-fill reapplication is idempotent, conflicting second closes fail
closed, batch order is exit timestamp then exit-fill fingerprint, and exact state and
ledger replay is required. No provider/broker/order/PAPER/LIVE/promotion/confluence
authority is created.

The stable recurrent-account foundation described below now performs that
consolidation without erasing source provenance. The Strategy Evidence Register
remains unchanged.

## 2026-09-18 — Stable recurrent lifecycle account foundation

Track A now introduces the consolidation target
`atlas-simulation-recurrent-lifecycle-account-v1` under contract
`9a22ebdb75a85c7d602851f48ae19a4262b0ab5a28441fc80f26b22a96781299`.
This is intentionally a **stable multi-cycle account contract**, not another numbered
copy of the reservation → position → closeout bridge.

The bootstrap consumes one exact accepted lifecycle-closeout state/ledger pair and
carries forward current cash, active reservations, open positions, fee totals,
realized P&L, lifetime trade net P&L, and book equity. Historical closed trades are
canonicalized into `RecurrentClosedTradeV1` records without erasing provenance.
Each canonical record retains:

- whether it originated from the original closeout path or the lifecycle closeout path;
- the exact source-state contract fingerprint;
- the exact source-state fingerprint;
- the exact original closed-trade record fingerprint; and
- the full immutable trade economics/fee/P&L lineage.

This removes the need to pretend that a lifecycle-native closed trade came from the
original open-position contract merely to combine histories. The recurrent state then
uses one chronological closed-trade collection for accounting while the source record
remains independently verifiable.

The recurrent account also freezes one append-only event-ledger schema broad enough
for reservation, entry, and closeout state transitions. The bootstrap ledger begins
empty at the exact recurrent initial-state fingerprint; later accepted mutation
packages will append fingerprint-chained events rather than replace the account
contract again. Current marks remain a read-only projection and are not ledger
mutations.

The recurrent state grants no provider/broker/order/PAPER/LIVE/promotion/confluence
authority. The recurrent reservation transitions described below now begin mutating
this stable account directly. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle reservation transitions

Track A now extends the stable recurrent account with
`atlas-simulation-recurrent-reservation-transitions-v1` under contract
`8e7cb6b4cf3d64bcafc8f0af9443bde8022df92c5b200aec67f4611fbedae796`.
Unlike the bounded bridge, these transitions mutate
`RecurrentLifecycleAccountV1` directly and append to its existing recurrent ledger;
no new reservation-account contract is created for each cycle.

Every decision is evaluated against current recurrent unreserved cash while existing
open positions and canonical closed history remain unchanged. Bullish stock
reservations retain separate reserved capital and economic gross notional. Long-option
reservations require the exact accepted reservation terms and maintain reserved
capital, max-loss, premium-at-risk, signed delta-equivalent, and absolute
delta-equivalent exposure separately from already-open option exposure.

The recurrent ledger now retains decision, reservation, reservation-terms, option
economics, candidate, option-contract, instrument, ticker, direction, state-chain, and
monetary/exposure deltas. Abstentions and rejected decisions advance deterministic
account time through zero-money ledger events. Duplicate decisions are idempotent;
supplying conflicting option reservation terms for an already-applied option decision
fails closed. Batch competition is ordered by decision timestamp then decision-record
fingerprint.

This package still creates reservations only. It grants no entry-fill, new-position,
exit/closeout, provider/broker/order, PAPER/LIVE, promotion, or confluence authority.
The recurrent entry/funding evidence layer described below now binds fills directly to
the same stable recurrent state. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle entry-fill and funding evidence

Track A now adds two descriptive operation contracts against the stable recurrent
account:

- `atlas-simulation-recurrent-entry-fill-evidence-v1` —
  `6802682c78dac10921afd49a023bab774dded6d5c8415e53f17ac92f852bf15a`;
- `atlas-simulation-recurrent-funding-terms-v1` —
  `4340cbe3d39b1026663db416094093814dab691ef611e7fca8a8a93e5023b6fc`.

Both objects bind one exact **current recurrent-state fingerprint** and one exact active
reservation fingerprint. They therefore cannot be reused after unrelated recurrent
state mutation. Stock fill evidence preserves the reserved economic gross notional and
derives complete share quantity from the explicit fill price while leaving funding
semantics unresolved. Long-option fill evidence reuses the exact accepted option
reservation terms, contract count/multiplier, premium/fee reserve, and records any
unspent reserved capital.

Funding evidence then proves the same fill against the same recurrent snapshot.
Bullish stock longs remain cash-only: existing reserved capital is credited and any
remaining requirement must be available in current recurrent unreserved cash. Long
options reuse the exact reserved debit and require zero supplemental cash. Neither
evidence object changes cash, releases a reservation, creates a position, recomputes
historical fees/P&L, or grants provider/broker/order/PAPER/LIVE authority.

The recurrent reservation→position transition described below now consumes that
evidence on the same stable account and append-only ledger. The Strategy Evidence
Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle reservation-to-position transitions

Track A now adds `atlas-simulation-recurrent-position-transition-v1` under contract
`998b3c505aaabd429b5009cb1c9cfebe864810f2d6e871d60450f4ccc2d7e084`.
This operation consumes and returns `RecurrentLifecycleAccountV1`; it does not create
a new position-account generation.

A transition requires recurrent entry-fill and funding evidence from one accepted
recurrent source snapshot and the exact reservation must still be active when the
mutation is applied. Only that reservation is consumed. The new
`SimulatedOpenPositionV1` preserves decision/candidate/reservation/fill/funding and
option lineage, the new entry fee is expensed once, canonical closed history remains
unchanged, and one fingerprint-chained `OPEN_POSITION` event is appended.

Single-entry application requires evidence to bind the exact current state. Batches may
pre-materialize several fills/funding objects against one common source snapshot, but
application is deterministic by fill time/fingerprint and each transition rechecks the
current remaining cash and reservation. Thus separately valid evidence cannot spend the
same supplemental cash twice. Exact duplicate fill/funding reuse is idempotent and a
conflicting second fill for an already-applied decision fails closed.

The operation grants no exit/closeout, mark-to-market, provider/broker/order,
PAPER/LIVE, promotion, or confluence authority. The read-only recurrent marked-account
projection described below now supplies current valuation without mutating the
recurrent ledger. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle marked-account projection

Track A now adds `atlas-simulation-recurrent-marked-account-v1` under contract
`6f473d2480167efa77e7826c994661d12141621122e99b644cb58cc39bbf5532`.
It consumes one exact recurrent account state plus accepted position-bound market-mark
evidence and produces current unrealized-P&L/equity state without appending a recurrent
ledger event.

Exactly one fresh, valuation-eligible mark is required for every current open
position at one common valuation timestamp. Missing, duplicate, stale, or extra marks
fail closed. Both inherited positions and newly recurrent-opened positions are valued
through their immutable position fingerprints; canonical closed history is never
revalued.

Marked position value is quantity × selected mark × multiplier. Aggregate unrealized
P&L is the sum of marked value less entry-book value for current open positions.
Marked equity is `account_book_equity + aggregate_unrealized_pnl` and must
independently reconcile to cash + stock reservations + option reservations + marked
open-position value. Cash, reservations, entry/exit fees, realized P&L, lifetime trade
net P&L, book equity, and the recurrent ledger remain unchanged.

This projection grants no account mutation, new realized-P&L, exit/closeout,
provider/broker/order, PAPER/LIVE, promotion, or confluence authority. The
source-bound recurrent exit-evidence layer described below now supplies that boundary.
The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle exit-fill evidence

Track A now adds `atlas-simulation-recurrent-exit-fill-evidence-v1` under contract
`61135bbede1416c852d7c84fa2914876c056508be9fdad1a87b834cb71f659ad`.

The evidence binds two distinct account identities deliberately: the exact **current
recurrent-state fingerprint** from which the active position is selected, and the
position's immutable **entry-source account-state fingerprint** retained from when that
position was created. These may not be collapsed or substituted for one another.

The builder requires one exact active position fingerprint, explicit source id/SHA-256,
timezone-aware exit time, nonnegative exit price, and explicit nonnegative exit fees.
Quantity, multiplier, instrument/option identity, decision/candidate lineage,
reservation, entry-fill, and funding lineage are inherited from the position. Gross
proceeds are quantity × exit price × multiplier and net proceeds are gross less fees.
Zero-price complete-loss exits are representable; exit fees may not exceed gross
proceeds. V1 is full-close only.

This package remains descriptive broker-neutral evidence. It does not remove the
position, alter cash, compute realized P&L, append a recurrent ledger event, read/write
providers or brokers, create an order, or grant PAPER/LIVE/promotion/confluence
authority. The recurrent `CLOSE_POSITION` transition described below now consumes
this evidence on the same stable account and append-only ledger. The Strategy Evidence
Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle close-position transitions

Track A now adds `atlas-simulation-recurrent-close-position-transition-v1` under
contract
`9f2f32d8905c19bfb377184abd1fa3f9842eb979829ce5ca03c3a44068e17e39`.

The operation consumes and returns `RecurrentLifecycleAccountV1`. Each close requires
exact recurrent exit evidence and the matched position must still be open. Only that
position is removed; active reservations and unrelated positions remain unchanged.
Exact net proceeds return to cash and one fingerprint-chained `CLOSE_POSITION` event
is appended to the recurrent ledger.

New closes append `RecurrentClosedTradeV1` records directly to the existing canonical
closed history using native origin `RECURRENT_ACCOUNT_V1`. The source-state contract
and recurrent-state fingerprint are preserved, while the exact recurrent exit-fill
fingerprint is retained as the native source record. Decision/candidate,
reservation, entry-fill, funding, and option lineage remain attached to the canonical
trade.

Account realized-P&L delta is `net_exit_proceeds - entry_book_value`. Lifetime trade
net P&L subtracts the entry fee that was already expensed when the position opened.
Cumulative entry fees therefore do not change at close, exit fees are added once, and
book equity continues to reconcile from both fee/realized history and cash +
reservations + remaining open entry-book value.

Single-close application requires evidence from the exact current state. Batches may
use multiple exits materialized against one common starting snapshot and apply them in
exit-time/fingerprint order. Identical exit-fill reuse is idempotent; a different
second close for the same position fails closed. No provider/broker/order/PAPER/LIVE,
promotion, or confluence authority is granted.

This completes the recurrent simulation loop on one stable account contract:
**reserve → entry evidence/funding → open → mark → exit evidence → close → reserve
again**. The recurrent coordinator described below now becomes the atomic runtime owner.
The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle coordinator

Track A now adds `atlas-simulation-recurrent-lifecycle-coordinator-v1` under contract
`0cadfd2c89c09c26731b8895ca70893dde3855c3eded4773c4455bce94b8e882`.
It is a new runtime owner rather than a mutation of the earlier single-cycle
coordinator, which remains intact for compatibility.

`RecurrentLifecycleCoordinatorV1` owns one accepted
`RecurrentLifecycleAccountV1` behind a single `RLock` and delegates only to the
accepted recurrent reservation, entry, mark, and close operations. It performs no
provider, broker, order, filesystem, or network I/O. The initial logical revision is
the current recurrent ledger-event count; every newly appended ledger event advances
the revision, including zero-money abstention/rejection events. Each unique mark
publication advances revision once but does not alter the recurrent ledger.

Any real account mutation invalidates the previously published marked state because its
source-state fingerprint is no longer current. Exact idempotent reservation/entry/close
reuse does not change account state, does not advance revision, and does not destroy a
still-current valuation. Republishing an identical complete mark snapshot is likewise
idempotent. `current_dashboard_pair()` returns an atomic recurrent account + marked
state only when their fingerprints match exactly.

The recurrent lifecycle observability layer described below now adapts this atomic pair
into the existing loopback/browser surface while retaining one engine-owned source of
truth. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Recurrent lifecycle observability

Track A now projects the recurrent coordinator through the existing
`GET /api/v1/ops/simulation-lifecycle` browser surface without adding a second
polling loop or browser mutation path.

`RecurrentLifecycleDashboardService` accepts only an injected atomic
`RecurrentLifecycleAccountV1 + RecurrentMarkedAccountStateV1` pair. It independently
revalidates account/ledger fingerprints, the marked-state fingerprint, exact
source-state binding, carried accounting values, and complete open-position mark
lineage. With no current marked pair it returns explicit `NOT_CONNECTED`; invalid
lineage returns `INVALID`.

The payload preserves the existing operator metrics while naming provenance correctly:
`account_state_fingerprint`, `account_ledger_fingerprint`, and
`source_kind=RECURRENT_LIFECYCLE_ACCOUNT`. Canonical closed trades additionally expose
their provenance origin/source fingerprints. The browser accepts both these recurrent
fields and the older closeout fields so the migration remains backward compatible.

`create_phase19_status_server` can receive an explicit lifecycle dashboard service,
the earlier single-cycle coordinator, or the recurrent coordinator—but never more than
one source. Recurrent injection performs no provider/broker initialization. The
browser still uses the existing `atlas:observability-refreshed` event, GET only, with
zero provider/broker/order/browser mutation authority.

This closes the recurrent engine→operator-view seam. The durable checkpoint/restore
layer described below now provides the production restart boundary. The Strategy
Evidence Register remains unchanged.

## 2026-09-18 — Durable recurrent lifecycle checkpoint and restore

Track A now adds `atlas-simulation-recurrent-lifecycle-checkpoint-v1` under contract
`53d34c03bf23157bb447cdf4ddb8902cd56ac008403efb8dd8145e596c45c2fa`.

The checkpoint is a durable envelope around one exact
`RecurrentLifecycleCoordinatorSnapshotV1`. It records the coordinator revision,
snapshot fingerprint, recurrent account state/ledger fingerprints, optional current
marked-state fingerprint, persisted timestamp, and the full validated snapshot payload.
The checkpoint carries its own SHA-256 and every superseded current checkpoint is
preserved in a content-addressed `history/<checkpoint_sha256>.json` file before the
current projection changes.

Writes use ATLAS's same-directory atomic temp/replace primitive with `fsync=True`.
A successor checkpoint may not move revision backward, may not change a snapshot at
the same revision, may not shrink or rewrite prior recurrent ledger events, and may
not change bootstrap lineage. An exact duplicate snapshot is idempotent and does not
grow checkpoint history. Callers may bind an expected previous checkpoint SHA to
reject stale writers.

Restore reconstructs the full nested dataclass graph from explicit JSON types and then
re-runs the accepted recurrent coordinator/account/ledger/mark contracts and
fingerprints. The coordinator's restored revision and current marked state are
preserved exactly; revision may exceed ledger length because unique mark publications
are versioned even though they do not mutate the recurrent ledger.

The production Phase 19 startup path now looks only for
`data/live/simulation/recurrent_lifecycle/current.json`. If no checkpoint exists,
recurrent lifecycle remains explicitly unconnected. If a checkpoint exists but fails
contract, self-hash, history-chain, state/ledger, marked-state, or lineage validation,
startup fails closed rather than reconstructing current trading truth from research or
legacy artifacts.

The durable runtime transaction layer described below now binds every accepted
recurrent mutation/mark publication to checkpoint commit or explicit fail-closed
recovery. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Durable recurrent runtime transaction boundary

Track A now adds `atlas-simulation-recurrent-durable-runtime-v1` under contract
`2959ba43c8279fd28cedeeca6df24f6f56edb6714a72cfc47999ea7e2bb3f891`.

`DurableRecurrentLifecycleRuntimeV1` wraps the accepted recurrent coordinator without
moving filesystem I/O into the deterministic engine. Every reservation, entry,
close-position, or unique mark-publication operation executes behind one runtime
`RLock`, captures the exact pre-operation coordinator snapshot, and then commits the
exact post-operation snapshot through the recurrent checkpoint contract using the
expected previous checkpoint SHA.

An idempotent operation whose coordinator snapshot does not change performs no
checkpoint write and therefore creates no history noise. For a real state change, the
operation is not considered durably resolved until the checkpoint can be classified.

Persistence failure has three explicit outcomes:

1. if durable readback is still the exact pre-operation snapshot, the in-memory
   coordinator is restored to that snapshot and the operation fails as rolled back;
2. if durable readback is the exact post-operation snapshot, the commit is accepted
   even if the writer surfaced an error after the atomic replace; and
3. if durable state cannot be read or matches neither pre nor post state, the runtime
   enters `UNCERTAIN` and blocks account, mark, dashboard, and mutation access until
   an explicit verified checkpoint reload succeeds.

Production Phase 19 startup now restores this durable wrapper rather than a naked
recurrent coordinator. The browser therefore sees recurrent state only through an
engine owner that is tied to one verified durable checkpoint. Runtime status exposes
the checkpoint SHA, logical revision, snapshot fingerprint, and uncertainty flag but
grants no provider/broker/order/PAPER/LIVE/promotion/confluence authority.

This closes the mutation↔checkpoint atomicity boundary for a single process. The
controlled one-time genesis package described below now creates the first authoritative
recurrent checkpoint without inventing a hidden account source. The Strategy Evidence
Register remains unchanged.

## 2026-09-18 — One-time recurrent genesis bootstrap

Track A now adds `atlas-simulation-recurrent-genesis-bootstrap-v1` under contract
`2784da99747760b50ff5cab35ae6f761d9ec8a77378ce767e603960571130b2a`.

The bootstrap creates the **first** authoritative recurrent simulation account without
reading a broker account, provider, research result, or legacy runtime artifact. It
requires an explicit positive starting simulation equity and a timezone-aware bootstrap
timestamp, then deterministically walks the accepted empty account contracts in order:
simulation account v2 → open-position account → closeout account → lifecycle
reservation account → lifecycle position account → lifecycle closeout account →
recurrent lifecycle account.

Every intermediate ledger must be empty and every reservation/open-position/closed-
trade collection must be empty. The resulting recurrent account must have cash and book
equity exactly equal to the explicit starting equity, with zero fees, realized P&L,
reservations, exposure, open positions, and closed history. Every intermediate state
fingerprint is retained in the bootstrap result for audit.

The bootstrap is one-time and fail closed. It refuses to overwrite an existing
`data/live/simulation/recurrent_lifecycle/current.json` and also refuses to run if
content-addressed checkpoint history exists without the current projection. Successful
bootstrap immediately creates the first checkpoint through
`DurableRecurrentLifecycleRuntimeV1.bootstrap()`; it never writes an unprotected
standalone current account first.

The operator CLI is `scripts/bootstrap_recurrent_lifecycle.py`. It requires
`--initial-equity` and optionally accepts `--as-of-utc`; no default dollar balance
is embedded in ATLAS. The command performs zero provider/broker reads or writes and
grants no order/PAPER/LIVE/promotion/confluence authority.

The durable recurrent simulation-cycle orchestrator described below now provides the
stage ordering and restart-safe receipt boundary. The Strategy Evidence Register
remains unchanged.

## 2026-09-18 — Durable recurrent simulation-cycle orchestration

Track A now adds `atlas-simulation-recurrent-cycle-receipt-v1`. The orchestrator
does not acquire provider or broker evidence itself; it consumes already accepted,
fingerprint-bound evidence and sequences it through the durable recurrent runtime in
one frozen order:

`CLOSE → RESERVE → ENTRY → MARK → COMPLETE`.

Every cycle has an explicit operator/system cycle id, deterministic cycle fingerprint,
source checkpoint SHA-256, source runtime-snapshot fingerprint, current checkpoint and
snapshot fingerprints, logical revision, and one content-addressed receipt under the
recurrent checkpoint's sibling `cycles/` directory. Each stage records the exact
sorted action fingerprints consumed plus before/after checkpoint and snapshot
fingerprints. RESERVE action identity binds the decision-record fingerprint together
with the exact long-option reservation-terms fingerprint, or explicit absence of terms,
so conflicting option capital terms cannot masquerade as an idempotent restart. Receipt writes use the existing atomic write + fsync path and are
self-hash verified on readback.

The stage contract is restart-safe. Repeating an exactly recorded stage is idempotent;
attempting to reuse a stage with different evidence fails closed. If the durable runtime
commit succeeded but execution stopped before the matching cycle receipt was written,
the orchestrator can prove that the exact actions are already present in the recurrent
ledger/marked state and record the missing receipt without applying them twice. An
unexplained checkpoint advance, broken stage order, tampered receipt, or uncertain
durable runtime fails closed.

Empty stages are explicit and still receive receipt records so a completed cycle proves
that each stage was evaluated. The mark stage binds the exact valuation timestamp in
addition to mark fingerprints. Completion is allowed only after all four stages and
only if runtime checkpoint/snapshot state still equals the recorded MARK result.

The cycle layer grants no provider/broker/order/PAPER/LIVE/promotion/confluence
authority. A deliberately narrow operator smoke CLI,
`scripts/run_recurrent_empty_cycle.py`, is included for the first post-genesis
workstation validation. It refuses any account with active reservations or open
positions and runs only a zero-evidence CLOSE/RESERVE/ENTRY/MARK cycle, proving durable
checkpoint + receipt + empty marked-state behavior without provider/broker reads.

The next product boundary is the production cycle runner/evidence-admission surface:
schedule and identify cycles, acquire current accepted evidence outside this
orchestrator, feed the immutable inputs into these stages, expose cycle health/receipts,
and prove workstation restart/resume behavior before any qualifying PAPER program. The
Strategy Evidence Register remains unchanged.

## 2026-09-18 — Deterministic recurrent cycle runner admission

Track A now adds `atlas-simulation-recurrent-cycle-runner-v1` under frozen contract
`2de1540cddf58f0c724efbbd25378800143de586c7d0f159fefa2e4af0ac5e0d`.
It derives each cycle id deterministically from an explicit schedule id plus an
explicit timezone-aware scheduled slot normalized to UTC; it does not decide when a
scheduler should fire.

Before any CLOSE, RESERVE, ENTRY, or MARK mutation reaches the durable cycle
orchestrator, the runner persists a self-hash-verified, fsync-backed stage-admission
record. That admission binds the cycle/stage, exact pre-stage durable checkpoint and
runtime snapshot, explicit evidence-source id/SHA-256, normalized evidence
fingerprint/count, and stage context. Exact admission reuse is idempotent; a different
source, evidence set, checkpoint lineage, or context for an already admitted stage
fails closed.

The runner restores only the authoritative recurrent checkpoint and delegates actual
mutation/restart reconciliation to the accepted recurrent cycle orchestrator. Evidence
is admitted stage by stage because later entry/mark evidence depends on state produced
by earlier stages; ATLAS does not precompute later-stage evidence against stale account
state. Provider/broker acquisition and scheduler triggering remain outside this layer,
and provider/broker/order/PAPER/LIVE/promotion/confluence authority remains false.

The next bounded Track A work is the current-evidence acquisition adapter plus
read-only cycle-health projection. Those surfaces must bind real provisional/current
market evidence into these admissions without allowing provider reads or browser
actions to bypass the runner. Workstation restart/resume and market-hours validation
remain required before any qualifying PAPER program. The Strategy Evidence Register
remains unchanged.

## 2026-09-18 — Current live evidence adapter and recurrent cycle health

Track A now freezes `atlas-simulation-current-live-evidence-v1` under contract
`6502f8b9a4644705ec819bf7ecfcc3ee8b65742f4016454e497b0da8aca5deb0`
and adds a read-only recurrent cycle-health projection.

The current-evidence adapter reads only the already-persisted
`data/live/market_state/current.json` artifact. It performs zero provider or broker
network calls, hashes the exact raw bytes, validates the accepted
`LiveStateSnapshot` schema, rejects future-dated snapshots, duplicate exact-case
symbols, and per-event feed/delay/symbol lineage mismatches, then exposes a normalized
evidence fingerprint and feed/session/freshness counts. Minute aggregates remain minute
aggregates: **ATLAS does not fabricate bid/ask quotes from OHLC bars.** A delayed
`AM.*` snapshot can therefore be valid current evidence while still having zero quote
coverage.

The cycle-health service restores the authoritative recurrent checkpoint read-only,
validates recent durable cycle receipts and stage-admission records, reports current
runtime revision/reservation/open-position counts, identifies the next lifecycle action
(including the post-MARK `COMPLETE` action), and includes the locally captured current
evidence summary. Corrupt receipts/admissions degrade health explicitly; missing
checkpoint/evidence remains explicit instead of being synthesized. Phase 19 exposes
this through `GET /api/v1/ops/recurrent-cycle-health` with zero browser mutation,
provider refresh, broker, order, PAPER, or LIVE authority.

The next bounded Track A work is stage-specific production evidence construction:
derive accepted RESERVE decisions from the frozen product forecast/economics path and
build CLOSE/ENTRY/MARK evidence from real current execution-quality sources without
bypassing the runner. Because the current Massive Starter path supplies delayed minute
aggregates rather than executable quotes, real mark/entry/exit evidence must continue to
fail closed until the accepted broker/finalist quote source is connected. Workstation
restart/resume and market-hours validation remain required before any qualifying PAPER
program. The Strategy Evidence Register remains unchanged.

## 2026-09-18 — Realtime current-stock mark adapter

Track A now freezes `atlas-simulation-current-stock-mark-adapter-v1` under contract
`2ff8bfc7afff4b072b37e364a46aa565d40d4d91a29a799de0aece13bb2ac4c0`.
It consumes only the accepted local current-live evidence object plus exact accepted
open stock positions and produces ordinary accepted `SimulatedMarketMarkEvidence`
records; it performs no provider or broker call itself.

V1 is intentionally strict. The enclosing live snapshot must be subscribed, real-time,
zero expected delay, and free of an open transport gap. Every open position must be a
stock position with an exact-case symbol match and a fresh quote. The quote must
postdate the position open, satisfy the frozen market-mark timestamp ordering, and
remain within the accepted 60-second valuation age. Missing quotes, delayed feeds,
minute-only state, stale marks, or any option position fail closed. Minute OHLC is never
turned into a synthetic spread.

The returned batch is deterministic by decision fingerprint and binds the exact
current-live evidence fingerprint, raw source SHA-256, valuation timestamp, and
individual accepted mark fingerprints. It grants no provider/broker/order/PAPER/LIVE,
promotion, or confluence authority.

The next bounded product work is equivalent execution-quality evidence for ENTRY and
CLOSE plus the RESERVE decision-production adapter. Those paths require explicit fee,
fill and option-quote semantics rather than inferring them from stock minute data.
Real-machine quote/provider acceptance remains required before this adapter can produce
non-empty production marks on the current deployment.

## 2026-09-18 — Current Webull L1 quote bundle and stock-mark adapter

Track A now adds a product-grade read-only quote path for the current deployment.
`atlas-execution-current-webull-stock-quote-bundle-v1` is frozen under contract
`5c2df876e2d9814434d6823f04c2cd0e6bfcdbe9b071cf291213abb634f2d26d`.

The capture command `scripts/capture_current_webull_quotes.py` accepts an explicit
comma-separated stock list, performs exactly one Webull **sandbox** L1 market-data read
per exact-case symbol. Starting a capture invalidates the prior current bundle first,
so a failed attempt cannot leave a previous still-fresh artifact masquerading as the
new capture. Nothing new is persisted unless every requested symbol returns a valid,
positive, uncrossed, regular-session quote inside the accepted execution age cap. The resulting bundle is sorted, complete, self-fingerprinted, atomically written
with fsync, and carries explicit provider-read counts. Capture performs no account read,
provider write, broker write, order creation, PAPER, or LIVE action.

The paired `atlas-simulation-current-webull-stock-mark-adapter-v1` contract is frozen
at `586b58a791e14cc21a3bb02f8d556a35785deae335a4153cee5bd37d30f33148`.
It consumes the already-captured bundle and exact recurrent stock positions with zero
network calls, requires exact-case complete quote coverage, preserves the stricter
30-second execution quote age cap, and converts each quote through the existing accepted
market-mark evidence contract. Option positions fail closed rather than borrowing an
underlying stock price, and mark construction grants no trading authority.

This closes the current-deployment stock MARK source gap without upgrading Massive or
fabricating quote data from delayed minute bars. The remaining production evidence
boundaries are RESERVE decision production plus execution-quality ENTRY/CLOSE evidence
with explicit fill/fee semantics. A real market-hours Webull sandbox capture on the
target workstation is still required before non-empty recurrent MARK acceptance. The
Strategy Evidence Register remains unchanged.

## 2026-09-18 — Durable recurrent RESERVE evidence bundle

Track A now freezes `atlas-simulation-recurrent-reserve-evidence-bundle-v1` under
contract `e410ab31187b4b35cd5c036ba02073f63de41dd35269f33af4b9ff10357de875`.

This package closes the missing restart-safe RESERVE input boundary. One bundle is bound
to one deterministic recurrent cycle id/fingerprint and contains the exact accepted
`SimulationDecisionRecord` objects plus option reservation terms only where the
decision actually selected an option. Stock and abstain records explicitly forbid
option terms; selected options require exact decision, chosen-candidate, forecast,
underlying, direction and reservation-term lineage.

The artifact is deterministically ordered by decision time then record fingerprint,
rejects duplicate/future decisions, self-fingerprints its complete typed payload, and is
written atomically with fsync at
`data/live/simulation/recurrent_reserve/current.json`. On restore, ATLAS does not trust
stored derived selection fields: it reconstructs the decision from the persisted
forecast, explicit stock-economics inputs, actionability policy, expression mode and
option candidates through the accepted deterministic decision builder, then requires
the rebuilt full record to equal the stored payload. This prevents a modified selection
or reason/economics lineage from becoming accepted merely by recomputing the outer
bundle hash.

The bundle exposes a direct recurrent-runner admission helper using its fixed source id
and bundle fingerprint. It performs no provider/broker calls and grants no order,
PAPER/LIVE, promotion or confluence authority. The recurrent account engine remains the
only authority that can actually record abstention, reject insufficient capital, or
create a stock/option reservation after stage admission.

Immediate continuation is durable ENTRY/CLOSE evidence production from execution-quality
quotes/fills with explicit fee semantics, followed by a full workstation cycle
restart/resume proof using real market-hours Webull sandbox L1 evidence. The Strategy
Evidence Register remains unchanged.

## 2026-09-18 — Current Webull stock ENTRY evidence

Track A now freezes `atlas-simulation-current-webull-stock-entry-evidence-bundle-v1`
under contract `2a5635ce3cffff6eadeda16a2857a6b71acfb6daa267f786caa9e2aa803d070d`.

The adapter consumes the accepted post-RESERVE recurrent account, the exact durable
RESERVE evidence bundle, one accepted current Webull sandbox L1 quote bundle, and an
explicit fee source with a fee amount for every active stock decision. It performs no
network call itself. Stock entry uses the exact current **ask** as the complete simulated
fill price; quantity remains derived from the already-reserved economic gross notional,
not from a new sizing decision.

V1 preserves fail-closed lifecycle semantics:

1. abstentions and explicit insufficient-capital RESERVE rejections create no ENTRY;
2. every active recurrent reservation must be represented by the current RESERVE
   evidence bundle;
3. active option reservations fail closed because the current Webull bundle is stock-L1
   only;
4. exact-case quote coverage is required for each active stock decision;
5. the quote must be regular-session, received after the post-RESERVE recurrent state,
   and inside the accepted 30-second execution age cap;
6. entry fees must be explicitly supplied from one named/fingerprinted source with exact
   coverage—no silent zero-fee assumption;
7. the accepted recurrent fill builder binds the active reservation and uses ask price
   plus explicit fees;
8. the accepted recurrent funding builder proves cash-only long-stock funding; and
9. the entire proposed entry batch is dry-run through the accepted recurrent batch
   transition before the evidence bundle is accepted, so competing supplemental fees
   cannot overdraw remaining cash.

The complete fill/funding pairs are deterministically ordered, self-fingerprinted and
persisted atomically with fsync at
`data/live/simulation/recurrent_entry/current.json`, with a direct runner ENTRY
admission helper. The artifact grants no provider/broker/fill/order/PAPER/LIVE,
promotion or confluence authority.

That original continuation direction is superseded by the 2026-09-19 lineage audit
below. Recurrent exit planning now consumes the accepted product-side
UnderlyingMoveTimeForecast / SimulationDecisionRecord lineage directly; Phase 13
reference geometry is not a recurrent exit dependency. The Strategy Evidence Register
remains unchanged.

## 2026-09-19 — Decision-bound recurrent stock exit-plan book

A pre-merge architecture audit caught and retired one green-but-wrong branch before it
entered `main`. PR #150 had 20/20 exact-head checks green, but it attempted to make
legacy-compatible Phase 13 reference geometry a required recurrent exit dependency.
That contradicted the accepted Track A product sequence, which deliberately created the
separately versioned
`UnderlyingMoveTimeForecast -> SimulationDecisionRecord -> RESERVE -> ENTRY` path
without modifying `Phase13CaseFile`. PR #150 was therefore closed unmerged. No Phase 13
exit-plan code or living-document text from that PR entered `main`.

The replacement freezes
`atlas-simulation-recurrent-decision-stock-exit-plan-v1` under contract
`445d820b0d4268f10d66b842e3ed341ccadd94363418edf2f4ff30f755e44754`.
It consumes only accepted product-side decision/forecast evidence plus the exact
recurrent open position.

V1 requires an explicit fingerprinted stock-exit policy. The policy supplies separate
stop and target threshold fractions, but **each fraction must already exist as an exact
threshold in the original accepted `UnderlyingMoveTimeForecast`**. ATLAS does not pick
a favorable threshold after seeing the position or invent one from Phase 13. For a
bullish stock long, the plan binds those accepted fractions to the actual simulated
entry fill:

- stop = actual entry × (1 − explicit stop-threshold fraction);
- target = actual entry × (1 + explicit target-threshold fraction).

Stop and target thresholds may differ. The original forecast threshold records,
probabilities, path-order evidence, horizon unit/value, full immutable
`SimulationDecisionRecord`, selected candidate fingerprint, explicit exit policy, and
actual fill are all retained in the plan. The forecast horizon is preserved for later
clock-policy work, but v1 grants no time-exit or price-trigger authority.

The durable artifact is an **open-position exit-plan book**, not a rolling one-cycle
decision file. Existing open-position plans are carried forward unchanged across
cycles. A newly opened position must be joined to its full decision record from the
current durable RESERVE bundle plus exact explicit policy coverage. Positions no longer
present in authoritative recurrent state are pruned on the next rebuild. This prevents
the original decision evidence from disappearing when
`recurrent_reserve/current.json` advances to a later cycle. The book is deterministic,
self-fingerprinted, atomically fsync-persisted at
`data/live/simulation/recurrent_decision_stock_exit_plan/current.json`, and requires
exact coverage of all open bullish stock positions; open option positions fail closed
in v1.

The package also moves persisted `SimulationDecisionRecord` reconstruction into one
canonical verified decoder in `decision_record.py`; RESERVE reuses that decoder rather
than maintaining duplicate reconstruction logic.

Immediate continuation is a fresh Webull L1 stock CLOSE adapter that consumes this
book, requires exact current-position/plan/quote coverage, records STOP/TARGET versus
NO_TRIGGER explicitly, uses the executable bid for bullish stock exits, requires
explicit exit-fee evidence only for triggered positions, and dry-runs the accepted
recurrent close batch before runner admission. Time-based exits remain a separate
clock-policy boundary. The Strategy Evidence Register remains unchanged.

## 2026-09-19 — Current Webull decision-bound stock CLOSE evidence

Track A now freezes **atlas-simulation-current-webull-decision-stock-close-evidence-bundle-v1** under
contract **3834abe2212b794a04ce70b5595d992de38cea77ac82185e6daaf6134bd6db96**.

This package consumes only the accepted recurrent account, exact decision-bound
open-position exit-plan book, and current Webull sandbox L1 evidence. It does not
reintroduce Phase 13, infer a different exit policy, or add broker authority.

For every open bullish stock position, the exact current plan and exact-case current
quote are required. Webull quotes must remain zero-delay/realtime, regular-session,
postdate the current recurrent state, and satisfy the accepted 30-second execution age
cap. The bundle's own capture timestamp may not postdate CLOSE evidence construction.

Long-stock price-trigger semantics are explicit and deterministic:

- **STOP** when executable bid is at or below the accepted actual-fill stop;
- **TARGET** when executable bid is at or above the accepted actual-fill target;
- **NO_TRIGGER** only when bid remains strictly between stop and target.

NO_TRIGGER is retained as explicit evidence and carries neither fee evidence nor an
exit fill. STOP/TARGET require exact explicit exit-fee coverage and one fingerprinted
fee source. The accepted recurrent exit-fill builder then uses the exact Webull **bid**
as the full-close price and binds the full current position quantity/multiplier. Before
the bundle is accepted, all triggered fills are dry-run together through the accepted
pure recurrent close-batch transition.

The evidence bundle retains the full exit-plan book and full Webull quote bundle rather
than only external fingerprints, allowing readback to revalidate plan/quote/trigger/fill
lineage. Triggered fill-source fingerprints bind the CLOSE contract, exit-plan-book
fingerprint, quote-bundle fingerprint, fee-source identity, exact plan, exact quote,
trigger disposition and explicit fee. The artifact is deterministic,
self-fingerprinted and atomically fsync-persisted at
data/live/simulation/recurrent_decision_stock_close/current.json.

A cycle with **zero open positions** is provider-inert: it requires no quote bundle, no
fee source and no exit fees. A cycle with open positions but no trigger requires quote
evidence but no fee source. Time-based exit remains deliberately unevaluated in v1.
The package grants no provider/broker write, broker-fill, order, PAPER/LIVE, promotion
or confluence authority.

Immediate continuation is production orchestration of the accepted plan-book refresh
after ENTRY so the next cycle's CLOSE always begins with exact durable plan coverage,
followed by the separately versioned time-exit clock policy and the target-workstation
market-hours/restart-resume acceptance proof. The Strategy Evidence Register remains
unchanged.

## 2026-09-19 — Restart-safe post-ENTRY exit-plan refresh

Track A now freezes **atlas-simulation-recurrent-exit-plan-refresh-v1** under contract
**7cf394ab6ba2fd3dc7e506a7718acb9f90ff647a55ed7b68c0a6a5f4eade2abc**.

This is a sidecar orchestration boundary, not a fifth recurrent mutation stage. The
accepted generic cycle order remains CLOSE → RESERVE → ENTRY → MARK. Refresh is only
eligible while the cycle is OPEN with exactly CLOSE, RESERVE and ENTRY recorded and
before MARK.

The refresh proves that the durable runtime still matches the post-ENTRY cycle receipt
checkpoint, snapshot and revision. Its receipt binds the immutable ENTRY stage-record
fingerprint plus the independently persisted ENTRY stage-admission SHA, so that lineage
remains verifiable after MARK/COMPLETE rewrites the cycle receipt file. When a current
RESERVE bundle is supplied, it must also match the actual admitted RESERVE evidence
source for that cycle. Exit policies are fingerprinted and bound to decision-record
fingerprints in deterministic order.

The current open-position plan book is then refreshed using the accepted decision-bound
builder. Existing valid plans are carried forward, new open positions require their
current-cycle full RESERVE decision evidence plus exact explicit policy coverage, and
closed positions are pruned. The effective refresh time is the deterministic ENTRY
stage recorded timestamp rather than a retry-dependent wall clock.

Both outputs are durable: the canonical plan book is atomic/fsync-written first, then a
self-fingerprinted per-cycle refresh receipt is atomic/fsync-written beside the
recurrent checkpoint. Exact retries reuse the receipt and book. Conflicting retries
fail closed. If a crash occurs after the plan book is committed but before the refresh
receipt, recovery accepts the book only when it already binds the current recurrent
state and the supplied policies exactly match its plans, then writes the missing
receipt.

This package deliberately does not change the frozen generic runner contract or stage
order. The production-cycle facade below now enforces ENTRY → refresh → MARK while the
existing zero-evidence smoke runner remains backward-compatible.

Time-based exits remain gated. The accepted move/time forecast schema identifies
horizons as MINUTES or SESSIONS but does not yet define whether MINUTES means wall-clock
or regular-session trading time, nor the exact exchange-session counting rule for
SESSIONS. No clock-trigger behavior will be inferred until that separately versioned
policy is explicit.

The refresh performs zero provider/broker reads or writes and grants no order,
PAPER/LIVE, promotion or confluence authority. The Strategy Evidence Register remains
unchanged.

## 2026-09-19 — Plan-aware recurrent production-cycle facade

Track A now freezes **atlas-simulation-recurrent-production-cycle-v1** under contract
**c03e6e299076618a537e8ab2d7ebd575b33f22924f25fc1f0ba655f10e7412ca**.

This facade composes the accepted recurrent runner and evidence packages without
changing the generic CLOSE → RESERVE → ENTRY → MARK mutation order. Its contract
also freezes the exact accepted fingerprints for the generic runner, RESERVE bundle,
Webull stock ENTRY, post-ENTRY exit-plan refresh, decision-bound exit-plan book,
Webull decision-bound CLOSE, and Webull stock MARK adapter.

On first application, CLOSE must bind the current recurrent state. RESERVE delegates
to the accepted durable reserve bundle. ENTRY must bind the current recurrent state
and the exact RESERVE bundle already admitted for the cycle. Exact retries after a
stage is durable rely on the existing stage-admission receipts rather than incorrectly
revalidating against a later post-mutation account state.

MARK is plan-aware. Before any MARK can be admitted, the facade runs or idempotently
reuses the accepted post-ENTRY refresh. It then re-verifies the durable refresh receipt,
immutable ENTRY stage-record fingerprint, ENTRY admission SHA, ENTRY result checkpoint/
snapshot/revision, current account-state fingerprint, exact RESERVE bundle, explicit
policy bindings, and the current durable exit-plan book. Missing, stale, or conflicting
refresh lineage fails closed.

Open stock positions require an accepted current Webull stock-mark batch with exact
position coverage and matching valuation time. Zero-position MARK is provider-inert and
uses no quote batch. A recorded MARK retry verifies the persisted MARK admission and
returns idempotently, including after the cycle is COMPLETE; it does not reopen runtime
mutation. COMPLETE still delegates to the accepted generic runner.

The facade can be restored directly from the durable recurrent checkpoint after a
process restart. It performs no provider or broker acquisition itself and grants no
broker write, order, PAPER/LIVE, promotion, scheduler-trigger, or confluence authority.

The separately versioned forecast-horizon clock contract below now resolves the
MINUTES/SESSIONS deadline ambiguity without granting expiry-disposition or CLOSE
authority. Immediate continuation is a durable open-position horizon-clock book so the selected timing
policy cannot change between cycles, followed by TIME_EXPIRED/NOT_EXPIRED disposition,
explicit STOP/TARGET/TIME precedence, and the target-workstation market-hours Webull
sandbox/restart-resume proof.

The Strategy Evidence Register remains unchanged because this package composes accepted
product/runtime evidence and does not change strategy research evidence.

## 2026-09-19 — Descriptive forecast-horizon exchange clock

Track A now freezes **atlas-simulation-forecast-horizon-clock-v1** under contract
**5efb0fb3b6bd37ba718ced50d1ebcbd589843cc895aba33426aa6235c643a56a**.

This package resolves the timing ambiguity that remained after the decision-bound
exit-plan and production-cycle work while preserving a strict separation between
**deadline calculation** and **expiry disposition**. It consumes the exact accepted
decision-bound recurrent exit plan and emits one deterministic descriptive horizon
deadline. It does not accept an evaluation time, does not emit an `expired` boolean,
does not create a CLOSE fill, and does not mutate recurrent account state.

V1 is deliberately limited to the accepted **XNYS** exchange calendar because current
recurrent position/forecast lineage does not carry an authoritative exchange identity
that would justify caller-selected calendars.

For **MINUTES** horizons, one forecast minute means one elapsed minute of the official
regular session from the actual simulated position-open timestamp. Premarket,
after-hours, closed time, overnight, weekends and exchange holidays contribute zero.
Official early closes are respected, and remaining minutes carry into later sessions.
The evidence retains the ordered sessions traversed to the deadline.

For **SESSIONS** horizons, the original move/time forecast did not encode whether the
entry session counts. V1 therefore refuses to guess. The caller must provide one
fingerprinted policy:

- **ENTRY_SESSION_INCLUDED** — horizon 1 ends at the official close of the entry
  session; or
- **FULL_SESSIONS_AFTER_ENTRY** — horizon 1 ends at the official close of the first
  complete exchange session after entry.

MINUTES rejects a session-counting policy; SESSIONS requires one. The clock retains
exact exit-plan, forecast, decision, position and policy fingerprints together with
entry session, horizon unit/value, deadline UTC, deadline session and counted-session
trace. The builder requires the real typed accepted exit-plan object and re-verifies
its plan/forecast lineage before calculating a deadline.

This clock remains descriptive evidence only: time-expiry disposition, price-trigger
authority, CLOSE-fill authority, account mutation, provider/broker reads or writes,
orders, PAPER/LIVE, promotion and confluence authority are all disabled.

The durable **open-position horizon-clock book** below now retains this exact
clock/policy for the life of each open simulated position and prevents session-policy
drift between cycles. Immediate continuation is therefore a separately versioned
**TIME_EXPIRED / NOT_EXPIRED** disposition over the immutable deadline plus explicit
evaluation UTC. Only after that evidence is accepted should a later CLOSE integration
freeze deterministic precedence among STOP, TARGET and TIME. The Strategy Evidence
Register remains unchanged.

## 2026-09-19 — Durable open-position forecast-horizon clock book

Track A now freezes **atlas-simulation-forecast-horizon-clock-book-v1** under contract
**b6badd42b77c47f5994db08f5c419991831c232041857f968bde80efd3514017**.

This package persists the accepted descriptive forecast-horizon clock for every open
decision-bound stock exit plan. The artifact retains the complete typed exit-plan book,
not only its fingerprint, so readback can re-prove every plan → clock relationship.

Clock policy is explicit at first persistence. Every newly unclocked position must
supply one ForecastHorizonClockPolicyV1; MINUTES therefore still requires the caller
to explicitly submit the XNYS/no-session-counting policy object, while SESSIONS requires
one of the two accepted explicit counting modes. Once a position has a clock, later
cycles carry that exact clock forward and reject any attempt to resupply or switch its
policy. If the exit-plan fingerprint for the same position changes, reuse fails closed.

The clock-book builder requires exact coverage of the current open exit-plan book,
orders clocks deterministically by position fingerprint, prunes clocks whose positions
are no longer open, and uses the source exit-plan-book timestamp as its own deterministic
effective time. It never injects a retry-dependent wall clock.

The complete clock book is self-fingerprinted and atomically fsync-persisted at
`data/live/simulation/forecast_horizon_clock_book/current.json`. Typed readback restores
the nested exit-plan book and each clock, then revalidates exact decision, forecast,
position, horizon and policy lineage.

The book remains descriptive evidence only: it carries no evaluation UTC, expired
boolean, time-exit disposition, price-trigger authority, CLOSE-fill authority, account
mutation, provider/broker access, order, PAPER/LIVE, promotion or confluence authority.

The separately versioned `TIME_EXPIRED / NOT_EXPIRED` disposition below now consumes
this immutable clock book plus explicit evaluation UTC without granting CLOSE authority.
Immediate continuation is therefore the later CLOSE precedence package that must freeze
STOP/TARGET/TIME ordering before time expiry can create a simulated exit fill. The
Strategy Evidence Register remains unchanged.

## 2026-09-19 — Explicit forecast-horizon time disposition

Track A now freezes **atlas-simulation-forecast-horizon-time-disposition-v1** under
contract **eda75ce9e816942b46e9c215c429da0b568cd2d2012bba2b09c43fe0672a049b**.

This package performs the first explicit evaluation of the durable immutable horizon
clock, while remaining separate from price triggers and CLOSE execution. It consumes
the complete typed forecast-horizon clock book plus one caller-supplied timezone-aware
evaluation UTC and retains the complete clock book inside its durable evidence.

For every current open-position clock, v1 emits exactly one disposition:

- **NOT_EXPIRED** when evaluation UTC is strictly before the immutable deadline;
- **TIME_EXPIRED** when evaluation UTC is equal to or later than the immutable deadline.

Deadline equality is therefore explicitly expired. Evaluation before the position-open
time fails closed. Every disposition retains the exact clock fingerprint, position,
instrument/ticker, position-open UTC, immutable deadline UTC and shared evaluation UTC.
The bundle requires exact deterministic clock coverage and re-derives every disposition
from its retained source clock during typed validation/readback.

The complete bundle is self-fingerprinted and atomically fsync-persisted at
`data/live/simulation/forecast_horizon_time_disposition/current.json`. Empty clock books
produce an empty disposition set while still binding the explicit evaluation UTC.

This evidence grants no price-trigger or STOP/TARGET comparison authority, no
STOP/TARGET/TIME precedence authority, no CLOSE fill, account mutation, provider/broker
access, order, PAPER/LIVE, promotion or confluence authority.

The price-first time-aware Webull CLOSE package below now consumes current price-trigger
evidence plus this time-disposition evidence and freezes deterministic STOP/TARGET/TIME
precedence. Immediate continuation is production-cycle facade integration of that final
CLOSE evidence, followed by target-workstation market-hours Webull sandbox and
restart/resume acceptance. The Strategy Evidence Register remains unchanged.

## 2026-09-19 — Price-first time-aware Webull stock CLOSE

Track A now freezes **atlas-simulation-current-webull-time-aware-stock-close-v1** under
contract **7b3a9f25959002ea070eca4611a16ce57f73771430d7075f855cd924ca7cac45**.

This package composes the already accepted current Webull STOP/TARGET/NO_TRIGGER evidence
with the explicit forecast-horizon time disposition. It retains both full typed source
bundles and requires their exact exit-plan book to match. The shared time-evaluation UTC
must equal the price-CLOSE build timestamp.

V1 freezes **price-first precedence**:

- an accepted **STOP** remains STOP even if the horizon is also TIME_EXPIRED;
- an accepted **TARGET** remains TARGET even if the horizon is also TIME_EXPIRED;
- price **NO_TRIGGER + NOT_EXPIRED** remains NO_TRIGGER;
- price **NO_TRIGGER + TIME_EXPIRED** becomes **TIME**.

STOP/TARGET reuse their already accepted price-CLOSE fills unchanged. TIME may create a
new recurrent exit fill only from a price NO_TRIGGER row. That TIME fill uses the same
retained Webull executable bid, requires the quote itself to have been received at or
after the immutable horizon deadline, and requires exact explicit time-exit fee coverage
from one fingerprinted fee source. This prevents a post-deadline evaluation from
retroactively closing at a quote that was actually sampled before the deadline.

All final STOP/TARGET/TIME fills are dry-run together through the accepted pure recurrent
close-batch transition before the final bundle is accepted. The complete nested evidence
and final rows are self-fingerprinted and atomically fsync-persisted at
`data/live/simulation/recurrent_time_aware_stock_close/current.json`. A canonical decoder
for the accepted price-CLOSE bundle is also exposed so nested readback reuses one typed
serialization contract rather than duplicating it.

The package performs no provider or broker calls itself and grants no broker-fill, order,
PAPER/LIVE, promotion or confluence authority. It only produces simulation CLOSE evidence
for the already accepted recurrent runner.

Immediate continuation is a small production-cycle facade update so first-stage CLOSE
consumes this final price/time evidence rather than price-only evidence, while preserving
the generic CLOSE → RESERVE → ENTRY → MARK order. After that exact-head gate, the next
meaningful boundary is target-workstation market-hours Webull sandbox and restart/resume
acceptance. The Strategy Evidence Register remains unchanged.

## 2026-09-19 — Time-aware recurrent production-cycle extension

Track A now freezes **atlas-simulation-recurrent-time-aware-production-cycle-v1** under
contract **c16ce1d4b9923d857673a92e6a4378a76699d6413ccf3ee8dbed9b138a894e84**.

This is a backward-compatible extension of the accepted
**atlas-simulation-recurrent-production-cycle-v1** contract
(**c03e6e299076618a537e8ab2d7ebd575b33f22924f25fc1f0ba655f10e7412ca**).
The base production cycle is not modified.

The extension inherits accepted BEGIN, RESERVE, ENTRY, post-ENTRY exit-plan refresh,
MARK, COMPLETE and restart/restore behavior unchanged. It overrides only first-stage
CLOSE so the production facade admits the accepted
**atlas-simulation-current-webull-time-aware-stock-close-v1** bundle
(**7b3a9f25959002ea070eca4611a16ce57f73771430d7075f855cd924ca7cac45**)
instead of the earlier price-only CLOSE bundle.

First CLOSE application must still bind the exact current recurrent-state fingerprint.
After CLOSE mutates the account, an exact retry delegates to the existing immutable
stage-admission receipt and cannot double-close a position. Inherited restore uses
the subclass through the base class's `cls(...)` construction, so the same exact bundle
remains idempotent after process restart.

The extension does not reacquire quotes, recompute clocks, reinterpret time
dispositions, or alter STOP/TARGET/TIME precedence. Those semantics remain owned by
the accepted time-aware CLOSE evidence package. The generic recurrent mutation order
remains CLOSE → RESERVE → ENTRY → MARK, and the base production v1 continues to reject
the time-aware CLOSE contract rather than silently changing behavior.

The package performs zero provider/broker reads or writes and grants no order,
PAPER/LIVE, promotion or confluence authority. The Strategy Evidence Register remains
unchanged.

Immediate continuation after acceptance is the target-workstation acceptance proof:
use real market-hours Webull sandbox L1 evidence through the accepted production
facade, prove durable restart/resume across the recurrent lifecycle, verify browser/
control-plane observability stays bound to the same authoritative state, and capture
the resulting acceptance evidence before any PAPER authority is considered.

## 2026-09-19 — Isolated target-workstation recurrent acceptance harness

Track A now freezes **atlas-recurrent-workstation-acceptance-v1** under contract
**5d450f115c03cfef389845ba594402f34a62ed7491f263dc7e33f8b5bb38af50**.

This is the operational proof harness for the accepted time-aware recurrent production
stack. It is not a strategy and does not grant PAPER or LIVE authority.

The parent command creates a unique isolated live-data root under
`data/acceptance/recurrent_workstation/<run-id>/live`. The configured normal `data/live`
root is explicitly rejected. The existing Webull sandbox L1 capture CLI now supports an
optional `--live-root` argument so the acceptance run can reuse the accepted read-only
provider capture without overwriting normal operator evidence.

The acceptance fixture is explicitly labeled product plumbing rather than strategy
evidence. It uses one operator-selected stock ticker, one regular-session minute
horizon, and a fixed ±20% stop/target threshold that is frozen before any exit quote is
observed. The wide band exists to exercise the TIME path. If the current bid somehow
crosses that fixed band, acceptance fails closed rather than retuning the fixture.

One parent command performs three read-only Webull sandbox quote captures and launches
fresh child Python processes across the lifecycle:

1. bootstrap an isolated recurrent account from the operator-supplied initial equity,
   admit empty CLOSE, deterministic RESERVE and ask-based ENTRY, then exit the process;
2. capture a fresh quote, restore in a new process, run Webull MARK through the
   production facade (which must create/verify post-ENTRY plan refresh), complete the
   first cycle, persist the explicit horizon clock book, and prove the recurrent
   dashboard reports the same authoritative marked state;
3. wait for the immutable one-regular-session-minute deadline, capture a fresh quote,
   restore again, require price NO_TRIGGER + TIME_EXPIRED, and admit a TIME close using
   the exact current bid plus the operator-supplied exit fee;
4. restore in one more process and submit the exact same CLOSE bundle again, proving
   the stage-admission receipt prevents a double close; then require clean read-only
   cycle-health lineage.

The final acceptance receipt is self-fingerprinted and requires exactly one closed
trade, three provider reads, zero provider writes, zero broker reads/writes, no order
authority, dashboard status `AVAILABLE`, and cycle-health status `OPEN_CYCLE` after the
exact CLOSE retry.

Operator command after this package is accepted:

`python scripts/run_recurrent_workstation_acceptance.py --ticker SPY --initial-equity 100000 --entry-fee 0 --exit-fee 0`

The command must be run while XNYS is in the regular session and with the existing
Webull sandbox/paper API credentials available. It normally waits about one minute for
the immutable horizon before the final quote capture. No broker/order endpoint is used.

The Strategy Evidence Register remains unchanged. A successful workstation receipt is
product operational evidence only; PAPER authority remains separately gated.

## A33/B33 reference foundation

The **A33/B33 — Practitioner Strategy Laboratory and Product Rebaseline**
foundation implements:

1. a stable, versioned reference catalog alongside the accepted registry;
2. separate indicators, setup signals, complete trade policies, routing, and
   authority;
3. the missing daily features required by the first six reference families;
4. the first finite daily reference library;
5. a reusable, PIT-safe historical runner and opportunity/outcome
   ledger that records fired, rejected, routed, and counterfactual strategies;
6. report structures by time, market/sector/ticker regime, volatility, liquidity,
   and direction without mining sparse condition combinations;
7. a read-only product/control-plane catalog view and append-only trials ledger;
8. proof that these research baselines cannot become PAPER or LIVE
   authority accidentally; and
9. a read-only adapter from accepted Massive canonical daily partitions and
   retained identity/split evidence into the frozen runner input contract.

The first six families contain nine direction-specific policy versions:

1. 50/200 moving-average trend cross;
2. 20/50 EMA pullback continuation;
3. MACD momentum shift;
4. RSI trend-filtered mean reversion;
5. 20-session Donchian high-volume breakout;
6. Bollinger compression breakout.

Gap/opening-range and premarket relative-volume consolidation breakouts follow only
after trusted minute/premarket coverage and exact session semantics pass a
source-only readiness gate. The Reddit “Highest Volume Day” setup belongs in that
later intraday pack as a quantitatively defined, unverified practitioner hypothesis;
its reported statistics are not ATLAS evidence.

No historical performance is opened until each implemented strategy version has a
frozen universe, signal, direction, timing, exit, risk, cost, and evaluation
contract. One canonical version per genuinely different family comes before
variants.

Frozen A33/B33 contracts:

- reference strategy-policy fingerprint:
  `26a6aae124b1a5d2b14b8a11a72671b06ac34d3cf94eb7ac47f16d2cfb94a8b3`;
- strategy-authority fingerprint:
  `a23ec27367ae540b869abc428d118241e84436719a8a543cbdbc3f3b678c69c5`;
- daily reference-feature fingerprint:
  `ee7e09b680b64b65280dea88c01d402bd9576a04cc70bc7748d8e3048ff57159`.
  This pre-outcome correction binds the PIT `$5` price floor to the unadjusted
  same-session close while indicators and returns remain split-adjusted.
- retained legacy trusted-lake adapter contract:
  `reference-lake-adapter-v1-massive-development-split-free-identity-exact`.
- isolated V2 adapter contract:
  `reference-v2-lake-adapter-v2-alpaca-sip-hash-bound-explicit-evaluation-scopes`.

All nine policies remain `RESEARCH` authority and are permitted only in
`RESEARCH_REPLAY`. The runner accepts caller-supplied split-adjusted daily bars,
rejects every post-DEVELOPMENT row by default, creates signals only at finalized
closes, and enters no earlier than the next session open. Its distinct one-time
walk-forward mode requires explicit master-holdout authorization, uses earlier rows
only for indicator warm-up, filters signal generation to `2026-05-12` onward, and
counts the protected rows it reads.
It retains fired, rejected, selected-independent, and overlap-suppressed
counterfactual opportunities across the `0/5/10/25/50` bps grid. Empirical V2
DEVELOPMENT and frozen walk-forward account replays now exist. The retained master
holdout was consumed exactly once; **93,380** master-protected return rows were
read. The frozen walk-forward continued unchanged through `2026-09-03`; no
parameter revision or strategy promotion occurred. Broker writes: **0**; PAPER
submits: **0**; LIVE writes: **0**.

The retained adapter is deliberately narrower than the accepted complete daily history. V1
uses Massive only from `2021-08-16` through at most `2026-05-11`, requires every
requested XNYS partition, resolves exact identity without current active/delisted
filters, rejects internal stream gaps, and excludes an entire identity if any of its
observed tickers has a documented split in scope. Because retained canonical prices
are unadjusted, only these factor-1-equivalent streams may be labeled
`SPLIT_ADJUSTED`; no factor is guessed. This costs coverage but prevents false
signals and returns. Alpaca pre-seam and split-affected streams remain deferred to a
separately validated adjustment-capable V2. The new V2 adapter accepts only
`data/v2_build/alpaca_sip_v2/manifests/research_daily.json` and its exact partition
hashes; arbitrary paths and legacy fallback are forbidden. It validates Alpaca SIP,
split-adjusted, regular-session, identity-clear common-stock provenance and the
regular-open/source versus regular-close/signal clocks before returning a row.
A separate `ReferenceV2WalkForwardLakeAdapter` accepts only
`walk_forward_daily.json`, verifies its immutable authorization self-hash and frozen
strategy/feature/portfolio fingerprints, requires a permanent consumption receipt,
requires the exact authorized warm-up start plus the complete protected interval,
and requires the requested end to equal the source cutoff. It is never an automatic
fallback.

The replay input now has two separate clocks. The canonical daily
`timestamp_utc` remains the provider's regular-open stamp for source provenance;
`signal_available_at_utc` is derived from the XNYS regular close under contract
`reference-signal-availability-v1-xnys-regular-close-next-open`. Close-derived
signals are recorded at that availability time and still cannot enter before the
next regular-session open. This corrects evidence labeling without changing the
previous next-open return simulation or claiming that any empirical result exists.

The retained read-only regime adapter contract
`reference-regime-context-v1-exact-asof-hash-bound-same-close-market-only` attaches
the accepted same-session finalized market regime to a next-open decision. It
requires the split-origin manifest whose `as_of_date` exactly equals the replay end,
verifies the bound snapshot and `market_effective.parquet` SHA-256 values, rejects
future, duplicate, blank, or missing-session state, and writes no production state.
No accepted PIT instrument-to-sector mapping or reference ticker-state join exists,
so ticker and sector regime fields remain `UNAVAILABLE` rather than inferred.
No accepted V2 PIT regime generation exists yet. V2 replay therefore labels market,
sector, and ticker regime `UNAVAILABLE` and reads zero retained V1 regime rows rather
than importing the decommissioned generation or guessing a label.

The native V2 acquisition, post-build, DEVELOPMENT replay, and frozen one-time
walk-forward have all completed on the operator workstation. The browser read model
prefers the hash-valid completed walk-forward and fails closed rather than silently
falling back to legacy or DEVELOPMENT evidence when protected-state artifacts are
invalid. DEVELOPMENT account replay returned **-17.912608%** with
**-20.803073%** max drawdown. The frozen walk-forward through `2026-09-03` returned
**-8.372772%** with **-8.372772%** max drawdown and read **93,380** rows from the
retained master protected interval. Performance is now opened for these frozen
versions; no strategy was promoted.

The local command first runs the adapter, binds its source fingerprint,
and registers the frozen trial before calculating any strategy outcome. It can stop
after source validation or continue through the independent-strategy replay:

```powershell
.\.venv\Scripts\python.exe scripts\run_a33_b33_reference_development.py --data-source v2 --source-only
.\.venv\Scripts\python.exe scripts\run_a33_b33_reference_development.py --data-source v2
```

The full command writes its lake-adapter and regime-context reports, independent
opportunity ledger, account admission decisions, simulated orders, position
outcomes, equity curve, summaries, and append-only trial records beneath the V2
generation; it does not write to a provider, broker, PAPER account, or LIVE account
and cannot promote authority. `--source-only` validates V2 input and explicit
unavailable regime context and stops before any performance outcome is opened.
`--data-source legacy` preserves the former Massive-only evidence path for
reproducibility; it is never an automatic fallback.

The first V2 analytical stream is provider-native **split-adjusted price return**.
It does not yet credit or debit cash distributions in position P&L. Any optional
first replay is therefore a product/research diagnostic, not qualifying historical
evidence; dividend and spin-off cash-flow economics must be added or conservatively
bounded before a strategy can earn historical authority.

## A34 RESEARCH account replay

The first A34 product vertical slice has frozen portfolio-policy fingerprint
`c6528b5619a0058131347715dae771474a7b37babda282856f5f53a430f792fa`.
It processes each session in this order: opening exits, opening candidate admission,
intraday daily-bar exits, then closing valuation. The fixed baseline begins with
`$100,000`, risks at most `0.25%` of current equity per admitted position, caps one
position at `10%` of equity, gross exposure at `100%`, open positions at `10`, and
active positions from one strategy family at `3`. Same-session candidates are
balanced by current family load and then stable identifiers; realized returns are
never used to rank them.

This is a **RESEARCH account replay**, not qualifying historical validation. V1 is
long-only: short signals and their independent counterfactual results are retained,
but account admission rejects them until short borrow, locate fees, recalls, and
asymmetric execution are modeled. Correlation and sector controls also remain
explicitly unavailable rather than guessed. A conservative `10` bps round-trip cost
is charged as `5` bps on entry and `5` bps on exit. Candidates without a resolved
historical exit are rejected so the V1 account finishes cash-reconciled and flat.

The local control plane exposes the latest result read-only at
`/api/v1/research/reference-replay`. The browser shows all nine frozen policies,
RESEARCH authority, per-strategy account statistics, replay
return/drawdown/costs, recent completed positions, admission decisions, simulated
order events, and a closing-equity/exposure curve. Before displaying an available
run, the read model verifies the recorded SHA-256 binding and schema of every
decision, order, outcome, and equity artifact; drift fails closed as `INVALID`. It
shows `NOT_RUN` honestly until the trusted-lake command produces artifacts. After
the one-time walk-forward completes, it prefers that separately labeled result,
verifies the completed consumption receipt and protected-row count, and labels the
GUI `WALK-FORWARD`; an incomplete/failed consumption never falls back to a seemingly
clean DEVELOPMENT display. Policy
promotion: **false**; master-protected return rows read: **93,380**; holdout
consumed: **true exactly once**; provider writes: **0**; broker writes: **0**; PAPER
submits: **0**; LIVE writes: **0**.

The current operator entry point is the stacked Phase19 dashboard, not the older
Phase16 shell. Start it from the repository root with
`python scripts/run_phase19_control_plane.py` (or
`.\.venv\Scripts\python.exe scripts\run_phase19_control_plane.py` on Windows), then
open `http://127.0.0.1:8765`. Its A33/A34 Strategy Laboratory panel reads the
catalog and latest replay through the two local GET endpoints; loading or refreshing
the panel does not call a market-data provider or broker.

Market-regime condition slices now use the hash-bound same-session finalized market
regime that was knowable at the signal close and before the next-open entry. Ticker
and sector condition slices remain explicitly `UNAVAILABLE`; they must not be used
for conditional performance claims until their separate PIT joins are accepted.

## A34.5 operator live observability gate

PR #60 (`a34-5-frontend-operator-dashboard`) completes the A34.5 read-only
operator-observability gate when this closeout is accepted and merged.
`PaperDashboardService` reads accepted local Phase15 execution evidence plus
Phase5 persisted marks, verifies artifact path/hash/schema before display, and
never initializes a provider or broker merely to refresh the browser. Fresh LONG
positions mark conservatively at bid and SHORT positions at ask; stale marks cannot
create P&L, provider uncertainty is visibly `DEGRADED`, and invalid evidence is
`INVALID`. Strategy provenance and realized net P&L remain explicitly unavailable
where the accepted upstream evidence does not bind them.

The production surface is GET-only at `/api/v1/ops/paper-dashboard` on the existing
loopback-only Phase19 server. The operator console uses bounded 5/15/30-second
polling and organizes Overview, Market, Research, Portfolio, Execution, Brokers &
Data, Operations, and Controls without maintaining a second trading truth. A
separate synthetic Codespaces preview never loads `.env`, never initializes real
providers/brokers, disables mutation controls, and rejects POST. A34.5 grants no
PAPER strategy authority or broker-write authority; it only satisfies the
observability prerequisite so A35 can begin under its own explicit authority gate.

This is a product-readiness gate, not a strategy-evidence promotion.
The accepted dashboard must make it easy to see, as the PAPER system operates:

- account equity, cash/buying power, exposure, realized P&L, unrealized P&L, and
  relevant daily/session totals;
- every open position with ticker, strategy/version, side, quantity, entry/current
  price, stop/target/invalidation state, risk, and unrealized dollar/percent P&L;
- the decision stream: what setup fired, relevant market/condition context, concise
  deterministic selection/rejection reasoning, sizing/risk reasoning, authority,
  and AI audit/review state when applicable;
- planned/submitted/accepted/partially-filled/filled/canceled/rejected order events
  and reconciliation state;
- exits/sales with exit reason, price, realized dollar/percent P&L, costs, and hold
  duration;
- searchable/reviewable closed-trade and decision history plus strategy-level and
  account-level statistics; and
- market-data/provider/broker freshness and health, last successful update,
  orchestration state, authority mode, and kill/emergency-control visibility.

The UI must update through an accepted event-driven or short-polling mechanism
without requiring the operator to manually refresh the page. It must read the same
engine-owned decision/order/position/account records used for execution and
reconciliation; it may format or aggregate them but must not maintain a separate
trading truth or recompute trading decisions independently. Unknown or stale state
must be obvious and fail closed. A34.5 completion grants no PAPER authority by
itself; it removes the observability prerequisite so A35 can begin under its own
centralized PAPER authority gate.

## Strategy authority and PAPER/LIVE boundary

Every strategy carries two separate labels:

- **Evidence source:** `PRACTITIONER_BASELINE`, `LITERATURE_ANCHORED`, or
  `INTERNAL_CHALLENGER`.
- **Authority:** `RESEARCH` → `CANDIDATE` → `HISTORICALLY_VALIDATED` →
  `PAPER_VALIDATED` → `LIVE_ELIGIBLE`.

Authority controls what a strategy may do. Ranking controls which eligible
opportunity ATLAS prefers. A high score cannot bypass an authority gate.

Two PAPER modes are required:

- **Operational PAPER** exercises the product with baselines. Results are useful
  for debugging and learning, but cannot qualify a strategy for LIVE. Operational
  PAPER is additionally blocked until the A34.5 operator live-observability gate is
  accepted.
- **Qualifying PAPER** begins only after a version is historically validated and
  the prospective policy is frozen. It is the strongest empirical gate to LIVE,
  but still must pass profitability, sample, risk, drawdown, stability, execution,
  concentration, and operational checks.

`PAPER P&L > 0` alone is never enough. LIVE also requires `LIVE_ELIGIBLE` status,
system-level readiness, explicit operator authorization, small initial exposure,
hard loss limits, reconciliation, a kill control, and no automatic broker failover.

## Non-negotiable safeguards

- Preserve point-in-time identity, provider-native symbols, chronology, corporate
  actions, delistings, and session semantics; fail closed on ambiguity.
- Do not silently weaken transaction-cost, slippage, spread, borrow, capacity,
  liquidity, or market-impact assumptions.
- Use the retained `0/5/10/25/50` bps diagnostic grid where comparable, with
  10 bps primary and 25 bps stress for signal-level daily screening; executable
  replay must replace generic costs with instrument-, side-, liquidity-, volatility-,
  and order-aware costs.
- Signals computed at a bar close enter no earlier than the next executable event.
  Same-bar high/low cannot fill an order created from that bar's close.
- Treat overlapping trades, shared sessions, tickers, sectors, and market moves as
  dependent observations.
- Keep a trials ledger and apply family-level multiple-testing controls. A hundred
  indicator parameterizations are not a hundred independent discoveries.
- Use chronological walk-forward selection, purging/embargo where labels overlap,
  frozen challengers, and untouched qualifying periods.
- Use the master protected window only once for the already-frozen practitioner
  walk-forward evaluation. Never use its results to select parameters and then call
  the same interval validation; any revision becomes a new version whose evidence
  starts after the revision.
- No production self-modification. A learned selector or strategy revision is a new
  version that must be frozen, replayed, PAPER qualified, and explicitly promoted.
- Zero trades or negative results are valid. Stop a branch when expected information
  gain no longer justifies its infrastructure or source-repair cost.
- Prefer trusted existing market data. Novel difficult sources must beat simpler
  available experiments on expected research value before receiving priority.

## Data repair and V2 policy

When historical data becomes materially questionable:

1. investigate root cause and reconcile local files, transformations, provider
   semantics, and authoritative sources;
2. repair V1 only when the economic meaning remains trustworthy;
3. otherwise preserve V1 results/provenance and either freeze the persisted V1 lake
   or, when explicitly authorized as here, decommission only its exact historical
   namespaces through a reviewed hash-bound plan;
4. build a separately versioned V2 with authoritative sources and explicit
   canonical rules;
5. never substitute V2 underneath an observed experiment or describe it as the
   same experiment; and
6. preserve provenance and old results for audit.

Repeated authoritative-source contradictions do not justify purge/refetch loops
whose only purpose is to make evidence disappear.

The current Alpaca V2 rebuild is started or resumed from PowerShell with:

```powershell
.\.venv\Scripts\python.exe scripts\run_alpaca_v2_rebuild.py --build-v2
```

The first invocation may display a small residual cleanup plan and require its exact
generated token. Later invocations reuse the frozen cutoff/source/plan and verify
completed artifacts before continuing. Do not delete the V2 checkpoint tree or vary
`--start-date` between resumes. `Ctrl+C`, a time limit, a network failure, or the disk
floor leaves a resumable checkpoint; none grants production-data or trading authority.

After that command returns `NATIVE V2 ACQUISITION COMPLETE`, do not delete or move
its generation. Pull the accepted post-build package and run one of these:

```powershell
# Source validation, identity/lifecycle, split-adjusted daily acquisition, and V2 research view.
.\.venv\Scripts\python.exe scripts\run_alpaca_v2_postbuild.py

# The same fail-closed chain, then the frozen DEVELOPMENT strategy/account replay.
.\.venv\Scripts\python.exe scripts\run_alpaca_v2_postbuild.py --through-reference-replay

# Recommended authorized chain: DEVELOPMENT through May 11, then one-time
# walk-forward from May 12 through the exact validated V2 cutoff.
.\.venv\Scripts\python.exe scripts\run_alpaca_v2_postbuild.py --through-walk-forward-replay --authorize-master-holdout-consumption
```

The post-build command is resumable at split-adjusted daily unit boundaries.
`--max-hours` can create a graceful checkpoint and the identical command continues
it. `--validate-only` performs no provider request. `--through-reference-replay`
opens DEVELOPMENT outcomes only and cannot read beyond `2026-05-11`.
`--through-walk-forward-replay` first completes that same DEVELOPMENT run, then
requires `--authorize-master-holdout-consumption`. Before any protected performance
read it writes an immutable self-hash-bound authorization tied to the exact source
and frozen policy fingerprints. After DEVELOPMENT succeeds and before protected
materialization starts, it writes the permanent consumption receipt; a materialization
or replay failure therefore remains consumed and cannot reset the holdout. Before
each receipt update, its previous state is preserved under
`manifests/master_holdout_consumption_history/`; the current self-hash and every
prior snapshot are verified on reads and retries. Known protected-row counts cannot
be cleared or changed. A verified completed run is reused without repeating either
replay; a missing or damaged completed result stops for repair. It then
creates a separate analytical manifest, starts signals on `2026-05-12`, and advances
chronologically through the exact source cutoff. Earlier rows in that input are
warm-up only. Neither replay may promote a strategy or submit a PAPER/LIVE order.
The DEVELOPMENT files remain physically capped at May 11; the authorized walk-forward
files and results remain separately labeled.
Provider rejections and malformed split-source rows remain evidence: when their
literal symbol is attributable, that symbol is excluded globally and the clean
remainder may proceed; an unattributed anomaly or unit-level validation failure
blocks materialization rather than poisoning or discarding the full database.
If source preparation passes but replay fails, the valid V2 daily foundation remains
recorded while the replay failure is explicit. Do not start this command in the same
working tree while the native acquisition process is still running.

Daily indicators are calculated by the frozen reference engine from the promoted V2
research view when a replay runs; a second giant feature lake is not created merely
to duplicate them. News acquisition is not part of this database acceptance chain:
it neither validates price history nor has a frozen provider/PIT contract, so it is
deferred to its own finite research package. Native minute evidence, extended-hours semantics, and initial intraday strategy readiness are accepted by B34. **B35 DEVELOPMENT replay and all preregistered B35 robustness/targeted diagnostics are CLOSED / ACCEPTED-NO-PROMOTION (2026-09-13).** The frozen `2016-01-04..2026-04-30` replay completed all **482/482 groups** and **59,768/59,768 source units**, with **482 validated receipt ids**, **20,171,286 fired opportunity/context/outcome records**, and run fingerprint `8955a282453cb89a24d3bcdf819d80451bebfa3ec9752dc24c113efc668cffe6`. The authoritative summary confirms consumed-master rows read `0`, future-blind rows read `0`, provider calls `0`, broker reads/writes `0/0`, PAPER/LIVE authority `false/false`, and strategy/selector promotion `false/false`. The canonical replay, condition/selector analysis, retained-artifact robustness, and exact targeted perturbations are all complete. Track B has moved to the frozen successor practitioner laboratory: PR #82 merged the exact 21-family rule/feature implementation, and PR #83 is the source/runner-contract plus hash-only source-verification gate. B35 v1 will not be replayed or parameter-tuned again.

## Planned practitioner strategy library and confluence architecture

ATLAS already contains more practitioner work than the current four-strategy B35
pack. The accepted A33/B33 reference library has **six daily practitioner families
with nine direction-specific policies**, and B34/B35 adds **four intraday/opening
families**. Those ten existing families are retained; the successor package adds
**eleven genuinely new mechanisms** for a planned **21-family practitioner library**.
Do not duplicate an existing mechanism under a new name merely because a later chat
rediscovers it.

The completed B35 DEVELOPMENT experiment remains frozen around its four B34
strategies and is now immutable historical evidence. It must not be rewritten or
replayed to rescue a disappointing result. The broader library is successor work
under a new preregistered fingerprint.

### Existing practitioner families to retain

1. **50/200 moving-average trend cross / Golden Cross** —
   `ma_trend_cross_50_200_long_v1`. The accepted policy uses the standard 50-session
   SMA crossing above the 200-session SMA, 201 sessions minimum history, ATR-based
   risk, and reverse-cross/maximum-hold exit logic. This is already ATLAS's Golden
   Cross implementation; do not create a duplicate `golden_cross` strategy.
2. **20/50 EMA pullback continuation** — `ema_pullback_20_50_long_v1`. Established
   EMA uptrend, bounded pullback into the 20/50 trend zone, objective recovery,
   ATR/pullback-low risk geometry and finite holding horizon.
3. **12/26/9 MACD momentum shift** — `macd_shift_12_26_9_long_v1` and
   `macd_shift_12_26_9_short_v1`. Long requires an upside signal cross below zero;
   short mirrors it above zero. The short profile remains research-only for account
   admission until borrow/locate/recall economics exist.
4. **RSI trend-filtered recovery / mean reversion** —
   `rsi_recovery_14_trend_long_v1`. RSI(14) recovery through the frozen level inside
   the accepted long-trend filter; strong-trend behavior is measured rather than
   assumed to mean-revert.
5. **20-session Donchian high-volume breakout** —
   `donchian_breakout_20_volume_long_v1` and
   `donchian_breakout_20_volume_short_v1`. Prior rolling-channel escape, aligned
   trend and relative-volume evidence, with the decision bar excluded from the prior
   boundary. Short remains research-only for account admission.
6. **20-session Bollinger squeeze breakout** —
   `bollinger_squeeze_breakout_20_long_v1` and
   `bollinger_squeeze_breakout_20_short_v1`. Prior-session compression followed by a
   directional band escape, relative-volume evidence, ATR risk and finite hold.
7. **Gap continuation** — `b34_gap_continuation_v1`. Material overnight gap followed
   by the frozen continuation trigger; prior regular close anchors the B34/B35 risk
   rule.
8. **15-minute opening-range breakout** —
   `b34_opening_range_breakout_15m_v1`. Uses the completed 09:30-09:44 ET opening
   range and only acts after the range is information-safe; the opposite boundary
   anchors risk.
9. **Premarket relative-volume consolidation breakout** —
   `b34_premarket_relvol_consolidation_v1`. Requires unusual premarket participation,
   an objective premarket consolidation and the frozen post-open breakout.
10. **Highest-volume-day style** — `b34_highest_volume_day_style_v1`. Tests the
    practitioner thesis that exceptional current premarket participation versus
    prior high-volume sessions, combined with the frozen price-structure trigger,
    can identify continuation.

### Eleven new successor families

The successor package adds only mechanisms that materially broaden the library. Exact
lookbacks, tolerances, bar authority, stops, targets and exits are frozen before any
new performance is opened.

11. **Bollinger-band mean reversion — `pract_bollinger_mean_reversion_v1`.** Detect a
    price excursion to/outside a frozen Bollinger envelope and require objective
    rejection/re-entry toward the band structure. A band touch alone is not a trade.
    Band width, trend regime, volume and volatility remain explicit conditional
    evidence so ATLAS can learn where mean reversion does or does not work.
12. **ATR volatility-expansion / consolidation breakout —
    `pract_atr_volatility_expansion_v1`.** Identify a normalized low-ATR/range
    contraction, then require directional price/range expansion beyond a frozen
    boundary. ATR measures volatility and supplies adaptive risk geometry; it does
    not choose direction by itself.
13. **VWAP reclaim / reject — `pract_vwap_reclaim_reject_v1`.** Intraday session-VWAP
    setup. Long research signal requires trading below VWAP followed by a
    deterministic reclaim-and-hold; the mirrored reject is the short research
    profile. Closed bars and an explicit confirmation rule are required; a single
    touch/cross is insufficient.
14. **Pivot support/resistance breakout — `pract_pivot_sr_breakout_v1`.** Build
    information-safe structural support/resistance from prior deterministic pivots
    or accepted ranges, then fire only on a confirmed boundary break. Relative
    volume, OBV and breakout distance are recorded as corroborating evidence rather
    than made hidden mandatory filters. This differs from Donchian by using
    structural pivot levels instead of a simple rolling extreme.
15. **Head-and-Shoulders / inverse Head-and-Shoulders —
    `pract_head_shoulders_v1`.** A shared deterministic pivot engine must identify
    the five alternating pivots that form left shoulder, head, right shoulder and
    the two neckline points. Freeze shoulder-similarity, head-prominence, spacing,
    neckline-slope and prior-trend rules. The setup is incomplete until an
    information-safe neckline break. Classic H&S is research-only short; inverse H&S
    is the long counterpart. Volume and formation duration are confirmation features.
16. **Double top / double bottom — `pract_double_top_bottom_v1`.** Require two
    separated tests of approximately the same resistance/support region, a material
    intervening reversal, and a break of the intervening neckline/support/resistance
    before firing. Double bottom is the long counterpart; double top is research-only
    short until short admission is available.
17. **Flag / pennant continuation — `pract_flag_pennant_v1`.** Require an objective
    impulse leg followed by a bounded, short consolidation with frozen retracement
    and contraction geometry, then a breakout in the original direction. Impulse
    strength, consolidation tightness, volume and breakout quality are retained as
    separate evidence.
18. **Triangle breakout — `pract_triangle_breakout_v1`.** Fit deterministic converging
    support/resistance boundaries from repeated prior pivots, classify ascending,
    descending or symmetrical geometry, and fire only on an information-safe
    boundary breakout. Breakout direction controls the signal; the visual pattern
    name alone never does.
19. **ADX/DMI continuation/filter — `pract_adx_dmi_continuation_v1`.** Use DMI for objective directional state and ADX for trend-strength state under one frozen rule. ADX alone never chooses direction. Test whether established directional strength improves continuation expectancy rather than assuming all high-ADX conditions are favorable.
20. **Relative-strength momentum — `pract_relative_strength_momentum_v1`.** Measure PIT ticker out/underperformance versus SPY over a small frozen horizon set and test continuation as its own family. The same relative-strength features may also be shared context for other strategies; sector-relative strength waits for an accepted PIT sector map.
21. **Session-level failed-break/reclaim — `pract_session_failed_break_reclaim_v1`.** Test breach and bounded reclaim of objective previous-day high/low and premarket high/low levels with normalized breach depth, explicit reclaim confirmation, sweep-extreme invalidation and one coherent exit hierarchy. This is observable failed-break/reversal research, not a claim about hidden institutional liquidity.

Cup-and-handle, candlestick-only patterns, stochastic-only systems and other popular
setups remain backlog candidates. Add them later only if they introduce a genuinely
new mechanism or evidence source rather than another correlated restatement of an
existing family.

### Confluence / evidence-strength layer

ATLAS will **not** turn simultaneous strategy alerts into a naive confidence vote.
Every strategy fires independently and keeps its own lineage, outcome history and
standalone statistics. A separate confluence layer asks whether *independent*
corroborating evidence improves conditional probability, net expectancy, downside or
capital efficiency.

Evidence is grouped into at least seven families: **trend**, **momentum**,
**volume/participation**, **price structure**, **volatility**, **chart pattern**, and
**context** (market/sector regime, liquidity, price band, time of day and other
point-in-time state). Raw same-direction strategy count is recorded, but correlated
signals inside one family are capped/regularized so several moving-average-derived
signals cannot masquerade as several independent confirmations. Distinct-family
agreement is measured separately. Opposing/conflicting evidence is preserved as a
negative feature; it is never silently removed.

This is why ATLAS should not initially create a new hard-coded "EMA + MACD" strategy:
the existing EMA-pullback and MACD families remain independently testable, and the
confluence layer can directly measure whether their same-direction agreement adds
value beyond either signal alone.

Research compares three systems: **A) standalone strategies**, **B) explicit
confirmation-filter variants**, and **C) confluence-ranked candidates**. First report
conditional outcome tables without invented manual point weights. If sample size and
stability justify it, a later interpretable conventional probability/expectancy model
may learn weights from training-only walk-forward data. Any displayed 0-100 strength
or confidence must map to a documented calibrated probability, percentile or frozen
score; it cannot be an arbitrary sum of indicators.

Confluence inputs may include primary strategy, distinct evidence-family agreement,
opposing signals, regime, trend, momentum, volume, volatility, structure, liquidity,
estimated cost, signal age and time-of-day. Same-session/future outcomes are forbidden
inputs. Confluence itself is a hypothesis and must beat standalone baselines out of
sample before it can affect qualification or capital priority.

### Controlled calibration and refinement

A losing v1 is evidence, not an instruction either to discard the mechanism
immediately or to tune it until green. After each frozen v1 evaluation, perform one
structured diagnostic review covering regime, liquidity, price band, time, volatility,
setup intensity, entry delay, MFE/MAE, stop/target path, cost drag, unresolved/no-entry
rate, loss concentration, losing streaks and confluence/conflict state.

Per strategy family and research cycle, create **no more than three materially
distinct v2 candidates by default**. Each requires a ledgered failure/opportunity
rationale, practitioner/statistical basis, exact rule change, declared trial count and
untouched evaluation source before performance is opened. Dense threshold sweeps,
tiny parameter stepping and repeated same-sample optimization are prohibited.
Original v1 results remain permanently ledgered. Data used to propose v2 is
training/diagnostic evidence only; v2 promotion requires a fresh walk-forward or other
untouched evaluation under a new fingerprint. Consumed master evidence is never
recycled, and an existing blind window is never reassigned after results are known.

### Implementation order and efficiency

B35 canonical replay, condition/selector analysis, retained-artifact robustness, and exact targeted minute perturbations are complete. The successor **21-family / eleven-new-family** PRE-OUTCOME contract is frozen in `packages/strategies/successor_practitioner_lab.py` and `docs/successor_practitioner_lab_preoutcome.md`; PR #82 merged the exact family/challenger evaluators and shared PIT feature layer without opening successor performance. PR #83 now freezes the portable source/runner contract and restart-safe hash-only source-verification gate under `atlas-successor-development-runner-contract-v2-project-relative-source-binding-preoutcome-no-authority`. It binds the 28 concrete routes to the accepted DEVELOPMENT sources, freezes profile-independent grouping and preregistered outcome/artifact semantics, and keeps project-root/runtime-profile details outside scientific identity. The preflight hashes exact source bytes and opens no bar rows, signals, returns, or outcomes. After PR #83 acceptance, run the workstation hash-only preflight to bind actual V2 source fingerprints; then implement the separate outcome-opening broad evaluator/output runner, prove golden-output/restart/authority behavior, benchmark exact-equivalent worker shapes, and only then open permitted DEVELOPMENT performance. Reuse the six accepted daily families and four B34 intraday families rather than reimplementing them. Shared point-in-time feature extraction, canonical bars, indicator primitives, deterministic pivots, market/relative-strength context, and the validated parallel execution pattern should be reused where exact-equivalent, while every strategy evaluator remains independently testable and deterministic.

The destination is not one universal strategy. It is a library of versioned
mechanisms whose standalone evidence, condition profile, confluence value, costs and
correlation are known well enough for ATLAS to rank good opportunities, abstain when
evidence is weak, and explain why one candidate outranks another.


### Successor selected-path evidence — COMPLETE / NO PROMOTION (2026-09-15)

**Exact-minute execution repair (2026-09-15).** The first exact-minute invocation stopped before any minute source read because the compact `eligibility_assignments.parquet` selector artifact intentionally does not persist `gross_return`, MFE/MAE, or entry/exit timestamps. The minute diagnostic now re-joins those selected assignments to the already SHA-validated normalized opportunity artifacts on the same unique conditioning key used by the accepted option-worthiness analysis (`policy_id`, `native_timeframe`, `instrument_key`, `session_date`, `direction`). Return/comparability bindings are checked before path construction. No minute result was opened by the failed invocation and all research/trading authority remains unchanged.

The retained option-worthiness pass showed that 20-session MFE is too broad to answer whether a signal moves fast and cleanly enough for stock/option construction: even losing routes frequently reached 1-5% favorable excursion eventually. ATLAS therefore froze a separate five-session path diagnostic before opening those results. The completed selected-daily run is bound by contract fingerprint `14d3598599e21a8603f95933368c9bdfaf6480577a51064d6110706a9682d1ca` and analysis fingerprint `e89d1d61b7fe6875353816a11727f7ad4a0797917eac0ef4b2d437812a053e20`. It covered exactly **35,995** already-selected comparable daily DEVELOPMENT opportunities, entered at the next regular-session open and measured favorable/adverse path through five instrument trading sessions at frozen 1/2/3/5% thresholds. Same-session two-sided daily touches remain unordered; no intraday ordering is inferred from daily bars.

The path result reinforces specialization rather than promotion. The broadest positive diagnostic remains `pract_bollinger_mean_reversion_v1` LONG (n=5,516; mean five-session gross +0.55%; MFE5 5.19%; adverse excursion 4.93%; favorable-before-adverse 43.49% at 2% and 43.65% at 3%). `pract_flag_pennant_v1` SHORT is cleaner but much smaller (n=191; +0.98%; favorable-before-adverse 54.45% at 2% and 50.79% at 3%). `donchian_breakout_20_volume_short_v1` SHORT (+0.72%, n=379), `pract_adx_dmi_continuation_v1` LONG (+0.63%, n=204), and `rsi_recovery_14_trend_long_v1` LONG (+0.47%, n=189) remain bounded specialist hypotheses. Triangle LONG is positive but only n=57 and highly concentrated. These are post-result DEVELOPMENT diagnostics, not a new valid portfolio or historical qualification result.

The important system-level finding is **path quality**: many routes reach 2-3% favorable excursion within five sessions while favorable-before-adverse rates are only about 30-50%. Expected endpoint return alone is therefore insufficient for options. Trade construction must model move magnitude, speed, adverse path, and then contract-specific delta/gamma/theta/vega, IV/skew/term structure, DTE/strike, spread/liquidity and scenario P&L before an option can pass the universal actionability gate. A stock candidate may remain valid when the option expression fails in modes that permit stock fallback.

The arithmetic mean of per-opportunity `five_session_return / MFE` is denominator-unstable when MFE is near zero and produced misleading aggregate values; it is **not** route evidence. Operator output now uses the retained median capture statistic and explicitly labels the mean as unsuitable for comparison. Underlying path/MFE/MAE/threshold artifacts remain unchanged.

The **259** selected comparable intraday opportunities are deliberately separate. They are all `orb_15m_close_retest_v2` and now have a preregistered exact-minute diagnostic: retained actual entry through retained actual exit, frozen 1/2/3/5% favorable/adverse thresholds, exact minute-bar first-touch time, same-minute collisions unordered, and no use of exit-bar high/low extremes after the strategy may already have exited. The accepted serialized native-unit bindings are reused; only selected symbol/month units are SHA-verified and selected symbol/session paths are queried. This is DEVELOPMENT diagnosis only and grants no consumed-master, future-blind, provider, broker, confluence, promotion, PAPER/LIVE or option-trading authority.

After this minute-path closeout, Track B proceeds through failure-specific external research and at most a small bounded set of versioned specialist hypotheses. Track A account simulation/control-plane work remains free to advance using clearly labeled baseline evidence; alpha research does not block product construction.

## How progress is reported

### Reusable validated performance-optimization protocol

The B35 replay established the default ATLAS pattern for expensive deterministic or research workloads. Apply the same pattern, adapted to the workload's own correctness contract, to historical replays, data builds, validation passes, simulations, feature generation, large audits, and other batch work where runtime becomes material:

1. **Instrument before optimizing.** Establish a real baseline on the target workstation: completed work unit, elapsed time, throughput, ETA, worker/thread shape, and restart state. Do not optimize from intuition alone.
2. **Make the job restartable first.** Preserve atomic checkpoints, self-hash receipts, immutable input fingerprints, and validated completed work so experiments or interruptions never require discarding good canonical progress.
3. **Separate science/correctness from execution.** Frozen strategy rules, source scope, validators, outcome mechanics, authority, and final scientific fingerprints must not change merely to improve speed. Runtime metadata and completion order are non-authoritative.
4. **Profile the actual bottleneck.** Test concurrency, I/O shape, Python/object overhead, reusable process-local resources, and data-layout costs independently. More threads or fewer scans are not assumed faster; B35 demonstrated both diminishing concurrency returns and a major single-scan regression.
5. **Use isolated golden-output probes.** Recompute already completed canonical work in a temporary location and require the strongest available equivalence evidence—preferably byte-identical output hashes plus receipt/scientific-field parity—before an optimization may touch the canonical continuation path.
6. **Change one execution layer at a time.** Keep experiments narrow enough that gains or regressions have an attributable cause and can be cleanly reverted.
7. **Tune the real hardware empirically.** Benchmark worker x library-thread combinations on the actual host while reserving enough CPU/RAM/I/O headroom for the OS, remote administration, and coordinator. Keep the fastest scientifically equivalent measured shape, not the configuration that merely looks most parallel.
8. **Reuse infrastructure, not evidence shortcuts.** Safe examples include process-local database connections, immutable calendars, compiled/read-only helpers, and bounded non-scientific caches. Do not bypass source hashes, validators, checkpoint verification, protected-data boundaries, or required model/schema validation solely for speed.
9. **Reject regressions explicitly.** Preserve benchmark evidence for failed ideas so future work does not repeat them. Exact equivalence is necessary but not sufficient: a slower equivalent implementation is rejected unless it solves another material operational problem.
10. **Stop optimizing when execution is tractable.** Among accepted candidates, use the fastest measured scientifically equivalent implementation. Continue searching only when the projected time saved reasonably exceeds the engineering and revalidation cost or a clearly larger safe gain is available.
11. **Resume; do not restart.** Once the execution path is accepted, continue the canonical job from all validated receipts/checkpoints. Benchmark recomputes remain isolated and never advance or erase canonical progress.
12. **Close the loop with real-run evidence.** After the canonical workload completes, record final elapsed time, sustained throughput, interruptions/restarts, resource shape, and any difference from benchmark projections. Use that case history to size and design future long-running ATLAS work.

For B35 specifically, the measured path moved from about **660.6 units/hour** in the serial restart to a final isolated exact-equivalent benchmark of **2,942.2 units/hour** at 10 x 1, while preserving **10/10 byte-identical sampled outputs** and all scientific/authority boundaries. The accepted canonical continuation then reused 82 validated groups and computed the remaining **400 groups / 49,600 units in 11:40:46 at 4,246.7 units/hour**. That sustained real-run rate was about **6.43x the original serial rate** and **44.3% faster than the accepted isolated benchmark**, saving about **63.4 hours** versus serial processing for the remaining 49,600 units. At that sustained rate the equivalent full 59,768-unit workload is about **14.1 hours** instead of roughly **90.5 hours** serial. This completed case is the reference example for the reusable ATLAS efficiency protocol.

**Mandatory long-running runtime observability.** Any ATLAS command expected to run materially longer than an interactive task must expose operator-visible progress without changing scientific authority. At minimum it reports a start timestamp and PID, frozen scope and execution profile, completed/total groups or units and percentage, elapsed time, restart-reused work, throughput, a timestamped heartbeat at least once every 60 seconds even while one work item is long, and an ETA once enough new work exists (otherwise explicitly unavailable). Completion, failure, and interruption report their timestamp and elapsed duration. Terminal output is flushed promptly, and an atomic machine-readable status artifact is maintained for second-terminal and future GUI inspection. Runtime progress/status is **NON_AUTHORITATIVE**: wall-clock fields, worker order, heartbeats, throughput, ETA, and the status artifact never enter scientific identities, source/group fingerprints, receipt hashes, trial identity, strategy decisions, or final result fingerprints. Validated receipts and final scientific summaries remain the completion authority.

Every accepted package reports both scientific control and functioning product
progress. Examples include:

- strategy specified and implemented;
- historical replay completed;
- candidate generated and routed;
- trade and portfolio constructed;
- operational PAPER order planned or submitted under explicit authority;
- position managed and outcome recorded;
- strategy statistics and calibration updated;
- replay/dashboard/GUI control functioning;
- PIT audit, cost policy, protected reads, trial count, fingerprints, and authority
  state preserved.

Implementation uses the largest safe coherent package. Each package begins and
ends with a short plain-English account of its goal, capability change, result,
remaining risk, authority change, and next work. Root causes are repaired at the
owning layer; validators and scientific rules are never weakened to manufacture a
pass.

Documentation is part of acceptance, not cleanup. Every repository-changing
package must update this README and `docs/roadmap.md` together before merge with the
exact current capability, test/CI state when known, safety/authority effect,
unresolved limitations, and next action. Strategy-evidence-changing packages must
also update `docs/strategy_evidence_register.md`. If implementation or strategy
evidence changes but the applicable living documents do not, the package is
incomplete and must not be treated as the new handoff.

## Historical evidence that remains binding

The complete ledger is in the roadmap and immutable closeout documents. Key facts:

- Phase32 is `ACCEPTED_NEGATIVE`; frozen finalist `solvency_distress_short` had
  **46 event rows / 33 signal sessions / 40 unique instruments** versus
  **50 / 20 / 20**; protected stock/SPY returns remained unread.
- Phase32 scientific policy fingerprint:
  `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`;
  protected return rows read = 0; holdout consumed = false.
- Phase31 SEC Form 4 insider-transaction alpha is `ACCEPTED_NEGATIVE`; it produced
  zero survivors, winners, finalists, support, and protected reads.
- XBRL quality/accrual: 200 documents, 170 accrual-ready and 92 profitability-ready
  issuers; zero development passers; protected reads zero.
- XBRL protected return rows read = **0**.
- XBRL retained lineage: Phase32 merge `69f8aa81289934b71f2652482c747391917c15a3`;
  contract `alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`;
  `FEASIBILITY_PASS`; feasibility fingerprint
  `6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`;
  accepted evidence fingerprint
  `33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`;
  PIT audit fingerprint
  `50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`.
- Schedule 13D/13G: 3,652 predictors and 2,412 usable development outcomes; zero
  passers; protected reads zero; closeout fingerprint
  `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`.
- FINRA: 19,343 predictors; `rapid_short_cover_crowded_long` had 257 protected rows
  versus 300 required; no outcomes opened; closeout fingerprint
  `bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565`.
- Diluted EPS: three ambiguous contexts and six metadata contradictions reproduced
  by clean authoritative replay; no outcomes opened; closeout fingerprint
  `29e72b427aa63c6ae2e0c25917fad0c9c948f2a2cd97c0d51f390ecd343baacc`.
- Form 13F: 10,431 malformed CUSIPs across 374 accessions reproduced exactly in
  original EDGAR XML; no outcomes opened; closeout fingerprint
  `0375d5567e0547c151f9fb140309aa568d17528246e611a68fa5984a1c481acd`.

These results may inform future work but may not be retuned into positive findings.
The retained master holdout was subsequently consumed exactly once by the frozen
A33/B33 V2 walk-forward on 2026-09-07; that consumption does not rewrite the
separate earlier branch statements below, which correctly record zero protected
return reads for those experiments. LIVE and automatic broker failover remain
disabled.

### Retained exact historical validator statements

The following literals are retained as **historical evidence**, not as the current
product dependency. They allow accepted phase validators to continue recognizing
the facts they were written to certify:

- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is `ACCEPTED_NEGATIVE` as well.
- Phase32 policy fingerprint: `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`.
- Phase32 frozen source evidence: 46 event rows / 33 signal sessions / 40 unique instruments.
- Phase33 signal-to-trade remains blocked was the superseded roadmap rule; its LIVE-authority conclusion remains binding, while baseline Product construction is now allowed.
- XBRL protected return rows read = **0**; closeout fingerprint `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`.
- LIVE and automatic broker failover remain disabled.

## Successor Strategy Lab direction — 21 families

The accepted B35 targeted perturbation diagnostic is closed. Track B now proceeds under a new preregistered successor research package rather than modifying B35 v1. The next broad historical experiment targets **21 economic strategy families** plus a bounded set of explicitly versioned challengers. The ten retained families remain immutable baselines; eleven distinct additions are planned: Bollinger mean reversion, ATR/range expansion, VWAP reclaim/reject, pivot support/resistance breakout, ADX/DMI continuation/filter, relative-strength momentum versus market/sector, deterministic head-and-shoulders/inverse, double-top/bottom, flag/pennant continuation, triangle breakout, and objective session-level failed-break/reclaim. Nearby parameterizations remain members of one economic family for multiplicity and confluence.

The Opening Range family receives two high-priority successor policies, not two new independent families: a **Stocks-in-Play 5-minute ORB/opening-momentum** policy using abnormal same-time opening participation and executable liquidity/volatility controls, and a **15-minute ORB close + bounded retest confirmation** challenger designed to test false-break reduction. The failed-break/reclaim family uses only observable PIT levels (initially previous-day high/low and premarket high/low) and makes no hidden-liquidity or ICT/SMC claim.

The successor experiment also adds a shared PIT context layer before confluence/ranking: broad-market alignment, ticker relative strength/weakness versus SPY, bounded higher-timeframe trend, trend maturity/extension, participation/relative volume, overnight gap, signal time, price band, realized volatility, and liquidity/execution quality. Sector-relative strength waits for an accepted PIT sector map. Context is measured first for incremental value and is not automatically a hard filter. Confluence remains separate from standalone strategy firing and counts independent evidence families rather than correlated indicators. Portfolio loss limits, simultaneous-position competition, concentration, and capital allocation remain account/PAPER-layer questions; fixed arbitrary stops/targets, human psychology rules, small discretionary watchlists, and reopened failed SEC hypotheses are not part of this successor strategy package.

The large successor run must report standalone v1 baselines, each frozen challenger, condition coverage, win rate, payoff ratio, net expectancy/net-R, cost decay, MFE/MAE, drawdown, concentration, fold stability, and abstention. The objective is broader **economically viable condition coverage**, not maximizing win rate or forcing every strategy to trade broadly. Candidate context interactions are frozen before performance, tested incrementally with multiplicity control, and any favorable condition-gated successor requires new untouched/prospective evidence before authority promotion.


## 2026-09-15 strategy-development and trade-expression direction

The successor DEVELOPMENT standalone and conditioning work has now moved ATLAS from broad strategy implementation into a repeatable **Strategy Development Cycle**. Existing strategy versions are not discarded when a broad or conditioned result is weak. Their observed v1 evidence remains immutable, and ATLAS uses the result to diagnose where the mechanism works, where it fails, and whether one or more bounded versioned revisions are justified. Operationally the cycle is:

`baseline -> diagnose -> targeted external research -> bounded revision -> retest -> specialize or park -> move on`

A strategy can improve in two economically useful ways: **higher edge per qualified opportunity** or **more quality opportunities without destroying edge/risk quality**. After each baseline, diagnose direction, regime, relative strength, trend/extension, volatility, liquidity, price band, participation, signal time, entry/confirmation, exit behavior, MFE/MAE, stop/target path, cost drag, false-signal rate, concentration, fold/year stability, move magnitude/speed, and option-worthiness. Then research the observed failure/opportunity mechanism using credible academic literature, original indicator/strategy sources, exchange/broker/quant research, books, respected practitioner material, and community experience. External popularity is never proof; it is evidence for a bounded candidate change. By default no more than three materially distinct revisions per family per research cycle are admitted, dense parameter sweeps remain prohibited, and the data that motivates a revision cannot independently validate it. Parked strategies remain versioned research assets and may be revisited when new data, research, market behavior, or option-source capability justifies it.

ATLAS is also explicitly an **options-capable and options-oriented** trading system, while preserving stock trading as a valid expression. The operator-facing product should support four trade-expression modes: `OPTIONS_ONLY`, `STOCKS_ONLY`, `OPTIONS_PREFERRED`, and `STOCKS_PREFERRED`. These are preferences/permissions, not commands to force a trade. Every signal must pass a universal **economic actionability gate** before capital is committed. If expected profit is too small relative to costs, spread, slippage, uncertainty, capital consumption, downside, liquidity, or portfolio risk, ATLAS abstains regardless of mode.

The strategy/forecast layer must estimate the underlying move before choosing the instrument: direction, expected move magnitude, expected holding/time-to-move window, uncertainty/distribution, and useful thresholds such as probabilities of positive, 1%, 2%, 3%, 5%, 1-ATR and 2-ATR moves, together with MFE/MAE and path/speed information. The trade-construction layer then evaluates whether available option contracts can profit from that projected move within the projected timeframe. A good underlying opportunity may therefore remain a stock candidate even when every option contract is rejected; in `OPTIONS_ONLY` mode the same case abstains.

Option construction must account for strike/expiration/moneyness, delta, gamma, theta/time decay, vega, implied-volatility level and plausible change, skew/smile and term structure when available, interest rates, dividends/early-exercise effects for American-style equity options, bid/ask spread, volume/open interest/liquidity, known events such as earnings, expected option P&L, probability of profit, downside/loss probabilities, and expected value per dollar of capital/risk. Black-Scholes-Merton and related pricing/Greek models are reference/scenario tools, not historical option-P&L truth. Apparent cheapness is **model-relative undervaluation evidence** that must be checked against the observed option surface and executable liquidity. Historical option qualification ultimately requires real point-in-time option-chain/quote/IV evidence rather than synthetic stock-return translation.

Efficiency remains a design constraint. Broad market/strategy discovery stays cheap; detailed option-chain retrieval and scenario pricing occur only after a stock candidate clears strategy/forecast/actionability gates. Cheap option filters narrow the chain before detailed scenario valuation, and vectorized/cached pricing should keep compute cost small relative to market-data acquisition. The intended flow is:

`broad discovery -> strategy/condition evidence -> underlying move/time distribution -> actionability -> permitted instrument modes -> option-chain filter/scenario economics -> stock/option/abstain -> portfolio risk`

This direction does not grant historical, PAPER, LIVE, strategy, selector, or option-trading authority. It defines the product and research requirements that subsequent implementation must satisfy.

### Successor option-worthiness diagnostic package — PRE-RUN

ATLAS now has a separately authorized DEVELOPMENT-only diagnostic package that derives option-relevant **underlying** move evidence from the already accepted successor conditioning artifacts without rereading the raw market lake. It compares all comparable DEVELOPMENT opportunities, the walk-forward test population, and the frozen conditioning-v1 selected population; reports route/direction MFE/MAE distributions, 1/2/3/5% favorable/adverse excursion frequencies, daily 1/5/20-session behavior, intraday holding-time behavior, selected-fold stability, and an exact 28-route / 21-family implementation inventory. Daily retained MFE/MAE covers the full 20-session diagnostic window, while intraday MFE/MAE covers entry-to-actual-exit; the report labels this explicitly and does not reinterpret daily threshold hits as five-session hits. It creates no new selector, ranking score, confluence rule, or strategy authority.

The retained artifacts do **not** preserve exact threshold-crossing timestamps, entry ATR magnitude, complete MFE/MAE path ordering, hold-period realized-volatility paths, or historical option chains. Therefore this package explicitly refuses to claim exact time-to-1/2/3/5% moves, 1ATR/2ATR hit frequencies, path ordering, historical option P&L, or contract-level Greeks/IV/skew/term-structure evidence. Those require separate future source/path packages. Repository acceptance opens no new empirical diagnostics; the workstation command remains separately gated.

### Successor selected-path timing diagnostic (2026-09-15)

The retained-artifact option-worthiness diagnostic completed successfully with analysis fingerprint `6f82ac0e55be43b8cf95fc362c7f292cb592b41c15ff897b24665470e95410f3`. It confirmed 28 replayed routes / 21 economic families and 36,254 walk-forward-selected comparable opportunities. The retained daily MFE/MAE fields span **through 20 sessions**, so their high 1%/2%/3%/5% favorable-excursion rates must not be interpreted as five-session or option-speed evidence. Losing routes also frequently reached large favorable excursions somewhere in that long window.

The next frozen diagnostic is therefore `successor_selected_daily_path_v1`: it reads only the already-selected comparable **daily** opportunities (35,995; about 99.3% of selections) against the accepted DEVELOPMENT daily lake, enters at the same next-session open, and measures five-session MFE/adverse excursion, first 1%/2%/3%/5% favorable/adverse touch session, session-level first-touch ordering, exit capture versus available MFE, and peak give-back. Same-session high/low collisions remain explicitly unordered because daily bars cannot reveal intraday ordering. This is post-result DEVELOPMENT diagnosis only; it creates no strategy, selector, confluence, PAPER, LIVE, promotion, or option-trading authority. The 259 selected ORB minute opportunities remain deferred to a separate minute-path diagnostic rather than mixing minute and daily path semantics.

## Exact-minute ORB closeout and literature-fidelity v2 freeze — 2026-09-15

The selected-minute diagnostic is complete under analysis fingerprint `a58c06b19b499082190110c227ddd4617826bb33e733d07bd17d849d73b099d8`. It reopened only the 259 already-selected/comparable DEVELOPMENT `orb_15m_close_retest_v2` opportunities, verified 218 bound native minute units by exact path and SHA-256, and read 55,581 entry-to-exit minute bars. The consumed master and future blind remained closed.

The exact path result diagnoses a **direction/order failure, not a lack-of-movement failure**. LONG (`n=157`) finished at -0.71% gross / -1.20% primary / -1.70% stress with 8.82% MFE and 7.78% MAE; favorable-first frequency fell from 48.41% at 1% to 40.76% at 5%. SHORT (`n=102`) finished at -0.01% gross / -0.51% primary / -1.01% stress with 3.85% MFE and 3.88% MAE; favorable-first frequency fell from 42.16% at 1% to 29.41% at 5%. Large moves occur, but the retained directional retest entry does not order those moves favorably often enough to justify leverage or an option-expression rescue. Historical option P&L remains unclaimed.

The next opening-range revision is therefore **not** another 15-minute retest parameter tweak. ATLAS preserves `orb_stocks_in_play_5m_v1` unchanged and preregisters a separate `orb_stocks_in_play_5m_literature_v2`, anchored to Zarattini, Barbon & Aziz, *A Profitable Day Trading Strategy For The U.S. Equity Market* (Swiss Finance Institute Research Paper 24-98 / SSRN 4729284). The v2 freezes: first-five-minute range; price > $5; prior-14-session average share volume >= 1,000,000; prior ATR14 > $0.50; first-five-minute relative volume versus the prior 14-session average >= 1.0; top-20 daily relative-volume rank; first-candle direction with doji abstention; direction-specific stop entry at the opening-range boundary; 10% ATR14 stop; and end-of-day exit. ATLAS retains its stricter 0/10/25/50/100-bps cost grid with 50/100 bps primary/stress diagnostics.

The frozen pre-outcome contract fingerprint is `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb`. This is a DEVELOPMENT-only, B35/opening-range-motivated challenger. Because both the internal diagnosis and the published study overlap DEVELOPMENT-era evidence, DEVELOPMENT can diagnose this v2 but cannot self-validate or promote it. Master/future/provider/broker/PAPER/LIVE/confluence/option-trading authority remains zero/false.

## 2026-09-15 — literature-fidelity 5-minute ORB v2 DEVELOPMENT runner

The retained `orb_15m_close_retest_v2` exact-minute path diagnostic is closed with analysis fingerprint `a58c06b19b499082190110c227ddd4617826bb33e733d07bd17d849d73b099d8`: 259 selected/comparable cases across 208 symbols and 218 SHA-verified native units showed substantial move magnitude but unfavorable path ordering. LONG averaged -0.71% gross / -1.20% at the 50-bps primary cost assumption with 8.82% path MFE and 7.78% path MAE; SHORT averaged -0.01% gross / -0.51% primary. Favorable-first frequency was below 50% at every measured 1/2/3/5% threshold in both directions. The diagnostic therefore motivates a direction/selection redesign rather than leverage or another 15-minute retest parameter sweep.

A separate `orb_stocks_in_play_5m_literature_v2` is preserved under base strategy contract `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb`. Its DEVELOPMENT analysis contract is frozen at `87ee4ff703f8040d88c22147444aa992d196ab49be91dc749e3035e3c15e739b`. Before any v2 historical outcome was opened, the runner was corrected to honor the accepted V2 source semantics: raw daily OHLC is reconstructed only for ATR14 using the accepted unadjusted-close price factor, while the one-million-share prior-volume gate consumes Alpaca's provider-native split-adjusted daily volume exactly as supplied; no inverse-price-factor volume transform is permitted. First-five-minute relative volume requires the exact previous 14 XNYS sessions to each contain a complete 09:30-09:34 ET five-bar snapshot, so missing opening sessions cannot be bridged with older observations.

Execution uses a two-stage efficiency funnel. Stage 1 SHA-verifies the accepted DEVELOPMENT minute units and reads only the exact five opening regular-minute bars across the 482 accepted symbol groups, computes the frozen filters and deterministic top-20 relative-volume cross-section, and lets a doji consume its rank slot while abstaining. Stage 2 opens full-session minute paths only for the selected directional candidates, applies the frozen stop-entry/gap-through/0.10xATR14/EOD mechanics, treats same-minute entry-stop collisions as unordered/noncomparable, and reports the 0/10/25/50/100-bps cost grid plus 1/2/3/5% move timing. Per-group SHA-bound receipts make both stages restart-safe; runtime worker count is operational and excluded from scientific identity.

**Outcome status remains UNOPENED at this repository state.** The next permitted evidence action is the explicitly gated DEVELOPMENT workstation run after this runner package is accepted. That run cannot self-validate or promote the revision because the hypothesis was motivated with DEVELOPMENT evidence and the external study overlaps the DEVELOPMENT era. Consumed master and future blind remain closed; provider/broker reads and writes, PAPER, LIVE, promotion, confluence, historical option-P&L, and option-trading authority all remain zero/false.


## 2026-09-16 — ORB v2 DEVELOPMENT closeout and trade-expression foundation

The frozen `orb_stocks_in_play_5m_literature_v2` DEVELOPMENT diagnostic is complete under analysis fingerprint `cc6c34b18479aa76558e3c73cbc17ae75d85dd2c7b45d3806a8ac00d17b3a035`. It produced 4,957,662 five-minute opening snapshots, 62,516 eligible rank-pool rows, 40,606 top-20 selections, 40,345 directional candidates, 33,773 entries and 23,412 comparable outcomes. Aggregate comparable mean was **+0.12% gross, -0.38% at the frozen 50-bps primary cost and -0.88% at 100 bps**, with 1.27% mean MFE and 0.41% mean adverse excursion. LONG and SHORT were economically similar. The setup is therefore preserved as a cost-sensitive research reference but is **not promoted**. The exact immutable closeout is `docs/research/orb_stocks_in_play_literature_v2_development_closeout_20260916.md`.

A material execution-path diagnostic is retained rather than optimized away: 10,361 entries, about 30.68% of entered cases, had entry and the frozen 0.10xATR14 stop touched in the same minute and remain unordered/noncomparable. Changing that stop, relative-volume gate, top-20 rank, range length, entry timing or exit after seeing this result would create a new version and would require a newly frozen hypothesis plus untouched/prospective evidence. Historical option P&L remains unclaimed; the 1/2/3/5% path statistics are underlying option-worthiness evidence only.

Track A now has a pure product-side trade-expression foundation under contract `a9341b7c0e6399165403cfa3d2f33e9f3b2749194ce39d41044a260dbd5fef4c`. It implements `OPTIONS_ONLY`, `STOCKS_ONLY`, `OPTIONS_PREFERRED` and `STOCKS_PREFERRED` as permission/preference modes behind a universal economic actionability gate. There are deliberately no hidden production thresholds: expected value, return on capital, probability of profit, loss/gain, execution-cost burden, liquidity and material-superiority thresholds must be supplied explicitly by policy. Options additionally require complete contract, Greeks, IV, liquidity and event context. Model-relative undervaluation is evidence only and can never independently make an option actionable. Preferred modes may use a materially superior alternate expression; no mode can force an uneconomic trade. This layer creates no broker read/write, PAPER, LIVE or strategy-promotion authority.

## 2026-09-16 — underlying move/time forecast foundation

Track A now has a versioned, broker-neutral underlying move/time forecast contract: `93525886fb2f0e8af3821caba8c87854ab1d732d5619dc02838df0ef98d931e1`. This object sits **before instrument selection** and carries the distribution evidence needed by the economic actionability layer: signed-return mean/median and p10/p25/p75/p90, probability of a positive underlying return, MFE/MAE, forecast horizon, source/sample lineage, uncertainty, and direction-relative move-threshold timing/path probabilities.

Directional forecasts may carry one or more unique move thresholds such as 1/2/3/5%; larger thresholds cannot report a higher touch probability than smaller thresholds. Favorable-first, adverse-first and same-interval-collision probabilities are validated for internal consistency, and favorable timing must fit inside the forecast horizon. Neutral forecasts intentionally carry no favorable/adverse threshold table. Unavailable forecasts remain first-class objects but may not carry a partial distribution.

The schema enforces PIT ordering (`evidence_cutoff_utc <= forecast_created_utc`), timezone-aware timestamps, finite numerics and a SHA-256 source fingerprint. It is explicitly underlying-only: historical option P&L, instrument-selection authority, broker reads/writes, PAPER, LIVE and strategy-promotion authority are all forbidden. The existing Phase 13 equity-only case-file contract and Phase 15 equity execution path are unchanged; later simulator integration will use a separately versioned product path rather than mutating those accepted contracts.

## 2026-09-16 — Stock economics adapter foundation

Track A now has a deterministic underlying-forecast-to-stock-economics adapter under frozen contract `68f4b7ca0e4f86f07bf20afa1c7e6e5aa9708c081db44cc3c18f8123e711f924` (`atlas-stock-economics-adapter-v1`). It consumes the accepted `atlas-underlying-move-time-forecast-v1` object and produces the `STOCK` `EconomicCandidate` already consumed by the universal trade-expression/actionability gate. Unavailable or neutral forecasts do not create a stock candidate.

The adapter deliberately keeps every economic assumption explicit. Position notional and capital reserved are separate inputs; no leverage, margin or collateral rule is inferred. Entry/exit slippage, round-trip commissions/fees, horizon borrow cost and horizon financing cost are supplied as explicit nonnegative inputs. Expected gross P&L is the direction-adjusted mean signed underlying return times position notional; expected net value subtracts all-in expression cost; expected return on capital divides net value by explicitly reserved capital. Forecast MFE/MAE scale expected gain/loss evidence. Net probability of profit is an explicit post-cost scenario input and cannot exceed the forecast's gross directional sign probability. The candidate preference score is expected return on capital, so negative economics remain negative rather than being clamped or rescued.

Bearish stock construction also carries an explicit shortability input. If the stock is not shortable, the economic candidate is preserved with `executable=false` so the downstream gate can explain the rejection. The adapter performs no provider/broker reads or writes, chooses no order quantity, creates no order, and grants no PAPER, LIVE, option-trading, confluence or promotion authority.

## 2026-09-16 — Deterministic simulation decision record

Track A now composes the accepted product-side decision layers into one immutable simulation record under frozen contract `62dceacde38687828e610c096d8c0a39479d5bc65b26b56aed2bf4164d8c8af8` (`atlas-simulation-decision-record-v1`). The record binds the full underlying move/time forecast, original stock-economics assumptions, calculated stock economics, exact universal `ActionabilityPolicy`, selected trade-expression mode, normalized option economic candidates when supplied, gate evaluations, final stock/option/abstain decision and reason-code lineage. It records the forecast instance fingerprint plus the accepted forecast, stock-economics and trade-expression contract fingerprints so a simulator result can be traced to the exact decision inputs that produced it.

Decision time is an explicit timezone-aware input and cannot precede forecast creation. Option candidate input order is normalized before evaluation and fingerprinting, making replay independent of caller ordering. Ignored instruments are not erased: for example, `OPTIONS_ONLY` retains the stock economics but explicitly records that the stock gate was not evaluated by mode, while `STOCKS_ONLY` retains supplied option candidates with equivalent not-evaluated lineage. The final record fingerprint changes when evidence, stock assumptions, actionability policy, mode, option candidates or decision timestamp changes.

This record is a simulation/control-plane artifact only. It performs no provider or broker access, creates no order, and grants no PAPER, LIVE, promotion or confluence authority. Option candidates can now be produced by the separately versioned `atlas-option-scenario-economics-adapter-v1` and supplied to this unchanged decision-record contract. Historical option P&L remains unclaimed.

## 2026-09-16 — Deterministic simulation account-state foundation

Track A now has the first explicit product-side account state under frozen contract
`2460956a47dfa3f73c157b5e2f60aa710b10dabb0c1a7115309056d06c1a588b`
(`atlas-simulation-account-state-v1`). It consumes accepted
`atlas-simulation-decision-record-v1` objects and models stock-only capital
reservation and opportunity competition without pretending that a reservation is an
execution fill.

The v1 state tracks account equity, currently unreserved cash, reserved capital,
gross stock exposure, and active stock reservations keyed to the originating
decision-record fingerprint. A selected stock decision reserves the exact capital
preserved by the accepted stock-economics adapter; its explicit stock position
notional becomes gross exposure. Release returns that same capital and removes that
same exposure. Because this layer has no fill, mark-to-market, or realized-P&L
authority, equity is invariant in v1 and `cash + reserved_capital == equity` is a
fail-closed accounting invariant.

Every decision path remains auditable. ABSTAIN, insufficient-capital rejection, and
a selected option whose account capital/risk semantics are not yet accepted all
create deterministic ledger events without changing account amounts. Duplicate
decision application and duplicate release are idempotent. Multiple decisions
compete deterministically in decision-time order with the decision-record fingerprint
as the stable tie-breaker. Every event binds before/after state fingerprints, and
ledger replay must reproduce the exact final state or fail closed on altered lineage.

This package deliberately does not infer margin, leverage, option collateral,
position quantity, fills, P&L, mark-to-market, broker behavior, or account-level risk
rules that are not already accepted upstream. Provider/broker reads and writes,
order creation, fill simulation, PAPER, LIVE, promotion, and confluence authority
all remain false. Phase 13 remains the separate broker-neutral risk/planning gate;
the A34 research account replay remains historical research evidence rather than the
product simulation truth.

The separately versioned option scenario-economics adapter is now implemented
under frozen contract `798b05ab3867058865301c35a52491ee9a8cde82c6f1b019b8d27bae34e88178` (`atlas-option-scenario-economics-adapter-v1`). It may
produce option decision-support candidates, but option capital/risk semantics still
fail closed in the account simulator. The next Track A package is therefore an
explicit option capital/risk reservation contract; it must not reuse stock notional,
margin, or collateral assumptions. The Strategy Evidence Register remains unchanged
because this is product architecture rather than strategy evidence.


## 2026-09-16 — Option scenario-economics adapter foundation

Track A now has a separately versioned option scenario-economics adapter under
frozen contract `798b05ab3867058865301c35a52491ee9a8cde82c6f1b019b8d27bae34e88178` (`atlas-option-scenario-economics-adapter-v1`). It consumes
the accepted underlying move/time forecast plus `OptionCandidateEvidence` and emits
the same `OPTION` `EconomicCandidate` consumed by the universal actionability and
trade-expression layer. V1 is intentionally bounded to long, single-leg,
direction-aligned calls for bullish forecasts and puts for bearish forecasts;
unavailable/neutral forecasts and direction-mismatched contracts do not create a
candidate.

The adapter does not manufacture an option-return distribution from sparse Greeks.
Expected, favorable, and adverse terminal option premiums plus model probability of
profit are explicit outputs of a separately identified and SHA-256-fingerprinted
scenario model, and that model must bind the exact underlying-forecast instance
fingerprint. The full `OptionCandidateEvidence` snapshot is also SHA-256-fingerprinted
and bound into the economics result and candidate identity, so changes to delta, IV,
open interest, volume, eligibility or quote evidence cannot silently reuse an older
candidate. Scenario prices must satisfy `adverse <= expected <= favorable` and the
holding period cannot exceed contract DTE. Current midpoint is the valuation
reference; entry executes economically at the ask, so the entry half-spread is
explicit. Exit slippage, commissions, and fees are explicit nonnegative costs.
Expected gross P&L is `(expected_terminal_premium - current_mid) * multiplier *
contracts`; all-in expression cost adds entry spread plus explicit exit/cash costs;
net value and return on capital remain signed and are never clamped positive.

Completeness is separately auditable across option contract evidence, delta/gamma/
theta/vega, current IV plus percentile/skew/term context, quote/open-interest/volume
liquidity, event context, and rates/dividends. Incomplete context can remain visible
as an economic candidate but fails the existing universal option gate. Upstream
option-screen rejection, unacceptable in-horizon event risk, executability failure,
and risk-budget rejection also remain explicit. A supplied reference-model premium
above the executable ask marks only `MODEL_RELATIVE_UNDERVALUE_EVIDENCE_ONLY`; it is
not historical option-P&L truth or independent trading authority.

The option `capital_required_dollars` value is the economic denominator used to
compare return on capital, but for a long option it may never be below the explicit
ask-debit cash requirement (`ask * contract_multiplier * contracts`). This prevents
artificial ROC inflation before account admission. The value still grants **no
simulator option reservation/collateral semantics**. It also performs zero provider/broker reads or
writes, creates no order, claims no historical option P&L, and grants no PAPER,
LIVE, promotion, or confluence authority. Historical option qualification still
requires accepted point-in-time option-chain/quote/IV evidence rather than synthetic
translation from stock returns.

Immediate Track A continuation is the separately versioned option capital/risk
reservation layer. It must define long-option debit/max-loss cash reservation and
option-specific exposure/accounting without mapping stock gross-notional semantics
onto options. Fill/mark-to-market/outcome authority remains a later package. The
Strategy Evidence Register is intentionally unchanged by this product-only work.

## 2026-09-16 — Long-option capital/risk reservation terms

Track A now has a separately versioned broker-neutral long-option reservation-terms
contract under frozen fingerprint
`26835cbab3e551f0f7514e8537d823cb23d5db1f440362d20b1ba7493ff6aa64`
(`atlas-long-option-capital-risk-reservation-v1`). It binds an accepted selected
OPTION decision to the exact simulation-decision fingerprint, exact accepted option
economics result, exact full `OptionCandidateEvidence` fingerprint, exact underlying
forecast fingerprint, and selected candidate fingerprint. Quote-only similarity is
not enough: changing non-price evidence such as open interest invalidates the
reservation lineage.

V1 supports only long single-leg, direction-aligned calls and puts. Entry premium at
risk is the accepted executable ask debit (`ask * multiplier * contracts`). Reserved
capital is that debit plus an explicit nonnegative cash-fee reserve, max-loss cash is
exactly the reserved capital, and the already-selected option economic capital must
cover the entire reservation. Delta-equivalent underlying notional is recorded as a
separate signed/absolute option exposure measure and never mutates or reinterprets
the stock account state's gross-notional field.

This package creates immutable reservation **terms only**. It does not mutate
account state, reserve cash, create orders/fills, mark to market, realize P&L, read or
write a provider/broker, or grant PAPER, LIVE, promotion, or confluence authority.
The next Track A package is the separately versioned option-aware simulation
account-state extension: deterministic admission/reservation/release and replayable
ledger lineage using these exact terms while keeping stock gross exposure and option
delta-equivalent exposure separate. Fill, mark-to-market, realized-P&L, and broker
authority remain later packages. The Strategy Evidence Register is intentionally
unchanged because this is product architecture, not strategy evidence.

## 2026-09-16 — Stock-option simulation account-state v2

Track A now has a broker-neutral reservation-only account model for both stock and
accepted long-option expressions under frozen contract fingerprint
`1e9da000571d02eb8fe4d317d770fdef25fb35a527ad177d1a87a6794c9592e5`
(`atlas-simulation-account-state-v2-stock-option-reservations`). The accepted v1
stock-accounting arithmetic is preserved, while v2 strengthens stock lineage by
requiring the exact chosen-candidate fingerprint. Option admission additionally
requires the separately accepted long-option reservation terms and their exact
decision, candidate, forecast, economics, and option-evidence lineage.

The state uses one unreserved-cash pool but never conflates instrument economics.
Stock reserved capital and stock gross notional remain separate from option reserved
capital, signed/absolute option delta-equivalent notional, option max-loss cash, and
option premium at risk. Reservation-only equity remains invariant and every state
must satisfy `cash + stock_reserved_capital + option_reserved_capital == equity`.
Missing option terms and insufficient unreserved cash fail closed. Releasing a stock
or option reservation restores exactly the reserved cash and exposure fields; it does
not invent a fill, gain/loss, mark, margin, collateral, or leverage event.

The mixed stock/option ledger is deterministic, chronological, idempotent,
fingerprint-linked, and replayable. Reservation and release events preserve exact
decision and, for options, reservation-terms/economics lineage. Stock gross notional
never includes option exposure, and option delta-equivalent exposure is never
reinterpreted as stock notional. No provider/broker reads or writes, order creation,
fill simulation, mark-to-market, realized P&L, PAPER, LIVE, promotion, or confluence
authority is granted.

## 2026-09-16 — Broker-neutral simulated entry-fill evidence

Track A now has a deterministic complete-entry fill-evidence boundary under contract
fingerprint `e271ba5c66fe9bc41b7f81945a1ef8152a2eeae091b27f6efd4859bacd2d8668`
(`atlas-simulated-entry-fill-evidence-v1`). It consumes an exact active account-state
v2 reservation, the exact simulation decision record and explicit source-bound fill
price/timestamp/fee evidence. The package records evidence only: it does not release a
reservation, mutate the account, create an open position, mark to market, realize P&L,
read/write a provider or broker, create an order, or grant PAPER/LIVE/promotion/
confluence authority.

Stock fills preserve the reservation's accepted economic gross notional and derive
complete simulated share quantity from explicit fill price; fractional simulation
quantity is allowed. Stock cash funding, margin, collateral, leverage and short-sale
proceeds remain deliberately unresolved because accepted stock economic capital can
differ from gross notional. Option fills require the exact accepted long-option
reservation terms: contract count and multiplier remain frozen; premium debit cannot
exceed the reserved ask debit; entry fees cannot exceed the separate fee reserve;
total cash debit cannot exceed reserved capital; and any unspent reserve is explicit.

Explicit funding/collateral semantics are now frozen under contract `f76d77ebbf138924a22813773ad27276b0fa71691ddff1d21040171c7b6d3821`
before any fill may become an open position. Fully cash-funded bullish stock longs may
use their existing reservation plus proven unreserved cash; stock shorts remain
unsupported until a separate short-collateral/proceeds model is accepted. Long-option
debit funding reuses the exact accepted fill evidence. The next bounded Track A package
is deterministic reservation/fill/funding -> open-position and cost-basis account
state. The Strategy Evidence Register is intentionally unchanged because this package
changes product simulation architecture only.
Deep chain discovery and deep EOD pricing are evaluated independently. If the deep chain endpoint fails but the direct 2016 EOD contract succeeds, ATLAS classifies that as `DEEP_EOD_AVAILABLE_CHAIN_LIMITATION` rather than rejecting the provider outright. That preserves the possibility of using Czar28 for prices while sourcing historical contract identity separately.


### MarketData Starter dashboard observation — 2026-09-25

The operator privately retained an authenticated Starter dashboard screenshot,
SHA-256 `1357a70a9c154f9171eac1ec976abaa647834d613a6f88b8129e4e3f266775bd`.
It displays verified Starter, IEX real-time stocks ENTITLED, UTP consolidated
candles ENTITLED, OPRA real-time options NOT ENTITLED, and 34/10,000 used credits.
The 34 usage is consistent with the independent 10+24 observed credit receipts.
The screenshot remains outside the public repo; its custody and bounded reading
are recorded in `docs/research/marketdata_starter_dashboard_evidence_20260925.md`.
This changes neither the separately accepted five-year historical EOD options
qualification nor any historical fill, simulator, PAPER or LIVE authority.


### Candidate-first MarketData exact-raw chain cache V1 — 2026-09-25

The first separately bounded provider executor after the offline batch planner
is now implemented in packages/data/marketdata_candidate_chain_cache_v1.py
with CLI scripts/run_marketdata_candidate_chain_cache_v1.py. **First real
workstation acquisition is pending.** The default run is an offline preview.
It rebuilds the PIT plan from source bindings, verifies exact claimed source
SHA values against explicitly supplied physical DEVELOPMENT stock artifacts
before any authorized provider call, and executes at most ten new bounded
shared historical-chain reads per run only under paid/private/explicit-read
flags. C: research-budget and READY-external storage policies are enforced.
The authenticated client captures bounded exact HTTP body bytes, and atomic
SHA-256 receipts are verified before reuse. Anomalies are preserved as
quarantined evidence rather than overwritten or treated as accepted rows.
No whole-market acquisition, quote-series calls, contract selection, historical
option fill/P&L, provider mutation, broker action or PAPER/LIVE authority exists.
Document: docs/research/marketdata_candidate_chain_cache_v1_20260925.md.

The historical news/options preflight console now says *that invocation*
performed zero bulk downloads; it no longer implies the previously acquired
2,211,606-article news corpus is absent.


### Accepted stock candidate export V1 — 2026-09-25

The source-only bridge to the chain planner is implemented as
packages/data/marketdata_accepted_stock_candidate_export_v1.py and
scripts/export_marketdata_accepted_stock_candidates_v1.py. Its first
source-only workstation export succeeded as detailed above. Default 2025
one-case-per-month sampling
takes only accepted walk-forward-selected comparable daily LONG stock
opportunities, ranks by a fixed SHA-256 of original ID (not by realized
outcome or option/news data), verifies existing normalized DEVELOPMENT
lineage and raw V2 entry open, and produces an immutable evidence bundle,
source manifest and PIT-safe bounded shared-chain plan. The plan binds
every claimed stock SHA to the exact physical evidence bundle required
by the gated cache. All work is offline and leaves the consumed master,
future-blind periods, Dynamic Exit V1, option price/P&L and PAPER/LIVE
authority untouched. First command and scientific limitations:
docs/research/marketdata_accepted_stock_candidate_export_v1_20260925.md.


### MarketData run tracking and bounded efficiency — 2026-09-25

Historical chain cache V1 now records an atomic per-run checkpoint and a
stable per-plan latest report, including UTC run ID, stage/status,
planned/processed/reused/new/pending requests, SHA-verified reused bytes,
new raw bytes, observed provider-credit use/remaining, initial/current
research headroom, elapsed time, throughput and approximate ETA. A fsynced
per-request attempt marker is written **before** each billable call,
and an exclusive plan lock prevents parallel duplicate paid acquisition.
An ambiguous attempt is never blindly replayed; completed SHA receipts
are reused, and free cache hits are checkpointed in groups of ten to
avoid filesystem churn. Offline preview skips the full disk quota census.
All provider calls remain serial, capped at ten and single-attempt, and
fail closed on credit/storage or source-identity anomalies. This remains
strictly source acquisition, not option pricing or trading authority.


Accepted stock-candidate export also writes a separate SHA-bound, per-invocation
stage ledger under data/options/manifests/md_stock_runs.
It reports accepted selected-source loading, the frozen cohort, native raw
source verification **unit by unit**, output-plan construction, immutable
artifact reuse, timings and terminal errors without changing source/plan
fingerprints. The default source pass uses four DuckDB threads and only
the bounded 2025 eligible cohort. No API call is made by export.


### MarketData candidate-chain recovery and next acquisition — 2026-09-26

Operator-reported Windows regression on PR #232 branch `fix/marketdata-chain-expiration-recovery-20260926`: 22/22 targeted tests passed. The first paid AGIO historical chain response (HTTP 203, two contract rows) had been quarantined because its numeric epoch expiration was compared with an ISO date. Offline recovery verified the original immutable body SHA-256 `ff8ec7b9a4b0e49dcadce4c2c3f9cd110dd5efa7419cce0a2fcd06a0f406b254`, original receipt fingerprint and plan/request identity, and wrote separate recovery evidence without provider calls or additional credits. The subsequent zero-network cache preview recognized one reusable receipt (608 raw bytes), eleven pending chains, zero reads and `EXTERNAL_SECONDARY` storage. This is operator-reported local evidence; PR #232 is not represented here as merged.

The physical accepted stock source bundle was subsequently supplied for independent inspection: SHA-256 `e7d90ce3162475ecbfc442d35e0ffbca18fca38434e658b0ee8bd7633021362e`, twelve 2025 source rows, matching all twelve plan source bindings; plan fingerprint `a830ab16e6ebce9b509ec88efad8b6c8e08e2951db8682aa8d5e34ffc96886e1`. Workstation project root example: `C:\\Users\\cyberdyne\\Desktop\\ATLAS`; the actual secondary-data root is resolved through settings, not assumed to be this project-local path. The cache's hard limit is ten **new** requests per invocation: the remaining eleven require a bounded 10+1 continuation with the exact SHA-bound stock-source file, explicit paid/private/read flags, and no blind replay. Do not launch simultaneous processes or bypass the plan lock. No option quote-series, fill/P&L, PAPER or LIVE authority is granted.


**2026-09-26 merge confirmation:** PR #232 was squash-merged into `main` at commit `f95b639a4f78d8d4d8c78d3b87ad33546f77ec4b` after its ten recorded GitHub workflow runs completed successfully. The offline recovery remains the sole accepted AGIO source; paid continuation requires the exact stock bundle and per-run bounded authorization. This updates the earlier pre-merge wording without rewriting the retained chronology.


### 2026-09-26 — Junction-safe accepted 2025 option-chain pilot

The project-visible `data/research/evidence` and `data/options` paths are Windows junctions to the verified internal D: secondary SSD. A previous operator command recursively searched `.\data` with PowerShell and incorrectly interpreted its failure to descend through junctions as a missing stock-source bundle. Test the exact exporter file directly at `data/research/evidence/marketdata_candidate_stock_v1/d6c924cf5006d295.json`; its SHA-256 and the plan SHA/fingerprint are frozen. The latest read-only preview verified one offline-recovered AGIO receipt (608 bytes), eleven pending and zero API calls. Do not delete or overwrite original raw, attempt, quarantine, recovery or receipt evidence.

`scripts/run_marketdata_candidate_2025_pilot.py` provides a zero-network default preflight and an explicitly authorized sequential 10+1 source-only acquisition, with direct junction-safe source resolution and independent post-batch receipt previews rather than stale-checkpoint assumptions. All existing credit, storage and fail-closed guards remain. See `docs/research/marketdata_candidate_2025_pilot_operator_v1_20260926.md`. No historical option pricing/fill/P&L, strategy, PAPER or LIVE promotion.

MarketData's published subscription terms require deleting downloaded data after subscription termination. D: capacity does not imply perpetual post-cancellation data rights; track provider-license provenance and seek written clarification before any retention plan. PR #231 documenting the actual D: Samsung 860 EVO and six READY junctions was merged.


**2026-09-26 validation/merge confirmation:** Junction-safe operator pilot PR #233 passed all ten recorded GitHub workflow runs, including complete Linux and Windows ATLAS tests, and was squash-merged into `main` at `0ac607d6ed47e8ed8810ef6bee82f09428618724`. This is a source-acquisition workflow fix only. The current workstation gate is the exact-path, zero-network-first wrapper; original AGIO evidence remains immutable and 11 pending chains have not yet been represented as acquired.


### 2026-09-26 — First authorized chain batch stopped on FSLY quarantine

After verified original source/plan and reused offline-recovered AGIO (608 bytes), the bounded 10-new-request batch saved four new complete responses (AMGN, ATRC, BANF, DAKT), each reporting one consumed credit; last observed successful remaining was 9995. The next request, FSLY on the frozen 2025-04-09 snapshot/2025-05-16 expiry/5.14–6.04 strikes, was preserved as QUARANTINED due to unexpected provider response status. The terminal output does not establish the failed response's HTTP status, payload `s` or charged credits. No second batch ran. This is **not** an accepted missing-contract inference, a complete chain or a reason to retry/delete the original.

Read-only next action: run `scripts/inspect_marketdata_candidate_2025_pilot.py` after its CI-validated merge. It validates physical source/plan lineage and original saved body/receipt/attempt fingerprints, and prints only sanitized status/credit metadata. No API requests, data edits, retry, option fills/P&L or strategy authority. See the pilot operator research contract.


**2026-09-26 PR #234 merge confirmation:** All ten recorded GitHub workflows succeeded, including full Linux and Windows ATLAS test suites. The metadata-only offline pilot quarantine inspector is merged into `main` at commit `e898af60850ef907b6f372db064e05e21f494eb1`. Workstation next gate is a zero-provider-read run of `scripts/inspect_marketdata_candidate_2025_pilot.py`, not another acquisition. HTTP/payload status and possible billing of the preserved FSLY response remain unresolved until that inspection. No original raw bytes or receipts were modified by the GitHub change.


### 2026-09-26 — Exact-query FSLY no-data coverage, independently classified

The offline receipt inspection confirmed the original FSLY 2025-04-09 / 2025-05-16 / $5.14–$6.04 request returned HTTP 404, provider `s=no_data`, zero rows, an intact 47-byte raw body, zero credits consumed **in that response's headers** and 9995 remaining. The original attempt, raw response, quarantine receipt, and original FAILED_REVIEW_REQUIRED run checkpoint remain unchanged. The other six requests were never attempted. This is exact-query noncoverage, not a determination that FSLY had no eligible options at alternative strikes/expiries.

An explicit, offline, separately SHA-bound source-gap proof can now be recorded with `scripts/classify_marketdata_candidate_2025_fsly_no_data_v1.py --authorize-exact-no-data-record`. It is NOT created merely by a read-only preview or HTTP 404. The cache verifies the original response, attempt, proof and exact plan before treating FSLY as a terminal source gap, never a successful chain. The pilot then allows acquisition of only six pending untouched queries through the original bounded credit/storage/attempt/lock guards. Target coverage is 11 complete, one exact-query no-data, zero pending; this is `COMPLETE_WITH_SOURCE_GAPS`, not twelve completed options chains. No broader contract-absence, option pricing/fill/P&L, strategy, PAPER or LIVE authority.


**2026-09-26 PR #235 merge confirmation:** The exact-query FSLY no-data/source-gap proof and six-only continuation were validated by all ten GitHub checks (including full Linux and Windows test suites) and squash-merged into `main` at `6ee3fbeca84d9c938ba2d82a5623f7ff96554599`. This does not mean a local FSLY sidecar has been written. The operator's next step is the explicit *offline* exact-FSLY disposition CLI with zero MarketData calls/credits; inspect its independent 5-complete/1-gap/6-pending result before any separately authorized paid continuation. All original FSLY raw/receipt/attempt and old failed-run checkpoint remain immutable.


**2026-09-26 operator acceptance of PR #235:** The user ran the explicit offline classifier successfully. It recorded FSLY proof fingerprint `6d2e3d17fbcb0f39d88af9ed025d71757c84e97ac00b75d130d189c6ac0f083f` bound to original raw SHA-256 `54e3e162845e54a24f015e4faaff70531c0707baf1f492fcebd5c35922f5971a` and original receipt fingerprint `afd9bc9135c575351f14f6bad3c769083d9331019c06dd7e0a1b1df0941f1748`. Independent read-only preview: **5 complete / 1 exact-query FSLY no-data / 6 pending**, 0 provider requests and 0 credits for classification. The prior run's original evidence remains unchanged. Next separately authorized workstation gate is `scripts/run_marketdata_candidate_2025_pilot.py` with `--max-total-new-requests 6` and the existing three paid-use confirmation flags. It must never replay FSLY. A complete remainder means 11 complete / 1 narrow source gap / 0 pending, not 12 executable chains.


**2026-09-26 completed 2025 MarketData source pilot:** Operator's final six untouched chain reads succeeded: 11 physical verified complete source receipts, one exact FSLY 404/no_data proof, zero pending; the provider reported six new credits consumed and 9989 remaining. The wrapper's terminal `status=PREVIEW` is the zero-network independent final verification, not incomplete acquisition. A new offline, read-only-first source closeout validates all original physical receipts and records per-request structural coverage only; see `docs/research/marketdata_accepted_2025_source_closeout_v1_20260926.md`. No final contract, historical quote/fill/P&L, strategy/PAPER/LIVE authority follows.


**2026-09-26 PR #236 merged confirmation:** CI passed all ten GitHub checks, including Linux and Windows full suites (2,592 tests and four subtests on each), and source-only closeout was merged as `3fb8d50ffca9926e240a0a5e0c714817775527fc`. This is code/contract acceptance, not proof a local closeout manifest has been generated. Next operator command runs the exact frozen source/receipt preflight and independently verifies 11 complete, one FSLY source gap and zero pending with no provider calls, then creates only the D:-bound local metadata closeout through an explicit CLI flag. Original provider bytes and provenance remain private and immutable.


### 2026-09-26 — 2025 source closeout accepted; structural CALL shortlist

The operator reported `COMPLETE_WITH_SOURCE_GAPS`, 11 complete original chains, one FSLY exact-query no-data, zero pending, 11 reported credits across complete receipts, and `WRITTEN_AND_REVERIFIED` for the private source closeout fingerprint `98b47179a2e563fb9d97ed16fec02d9a962f8f8788e88952f64c022f34a49daa`. The underlying stock/option source is closed; no further source-pilot runs are needed.

New `scripts/select_marketdata_candidate_2025_structural_calls_v1.py` uses that *existing manifest* plus original historical chain identities for an outcome-blind nearest-ATM CALL shortlist at the accepted 09:35 ET decision, ranked from the PIT raw stock OPEN (equal-distance tie favors OTM). FSLY remains an abstention. It does not rank by historical quote/last, OI, volume, Greeks, future returns or news; all symbols are provisional with independent standard-deliverable and historical pricing still unverified. Output is private under D:-bound options manifests; no new provider reads/credits or final option P&L/PAPER/LIVE authority. See `docs/research/marketdata_2025_pit_structural_call_shortlist_v1_20260926.md`.


**2026-09-26 PR #237 merge/next operator gate:** The outcome-blind structural CALL shortlist was CI-validated (all ten workflows; 2,600 tests plus four subtests on both Linux and Windows) and squash-merged at `9cc16d5de6ffaca439c92212193b441a9b4d2c38`. The accepted source closeout is already written; do not rerun it. Next local action is **one new computation**: `scripts/select_marketdata_candidate_2025_structural_calls_v1.py --write-local-shortlist`. It reads the frozen private closeout/chain receipts and produces the new provisional CALL shortlist on D:, with zero provider reads/credits. This GitHub merge is not a claim about actual provisional symbols until the workstation returns the new local artifact. Historical deliverable, executable quote and option P&L authority remain withheld.


### 2026-09-26 — Frozen 11 CALL symbols enter independent historical reference stage

The operator produced and saved a *new* PIT structural CALL shortlist (fingerprint `e5a8347fa346934d908d925b9fdbf667d7a458d010bf51ce8e27324fbbc01268`): 65 historical CALL rows examined, 11 provisional symbols and one unchanged FSLY abstention, without provider reads. The source pilot/11+1 closeout is closed and must not be repeated.

`scripts/run_marketdata_candidate_2025_exact_reference_v1.py` is the next new DEVELOPMENT source stage: freeze those exact eleven symbols and query Massive's contract overview at the original historical snapshot/as-of date, not the present-day contract record. A new D:-bound private reference plan and separate immutable raw/receipt/attempt cache are created; authorized GETs are sequential with >=13s pacing and no automatic replay. Identity, shares, exercise style, extra underlying and CFI evidence are recorded. A matching reference alone never establishes a dynamically correct historical 100-share deliverable or execution price. No option fill/P&L, PAPER/LIVE, broker or promotion authority. See `docs/research/marketdata_2025_exact_historical_reference_v1_20260926.md`.


**2026-09-26 PR #238 merge acceptance:** All ten GitHub checks passed, including full Linux and Windows suites (2,609 tests plus four subtests on each). Exact PIT reference dossiers were squash-merged at `438b3df794f1b382dbee54bb396e3d1fbffbc336`. Operator's accepted prior CALL shortlist remains fingerprint `e5a8347fa346934d908d925b9fdbf667d7a458d010bf51ce8e27324fbbc01268`. The new next workstation gate is a *single new, explicitly authorized* eleven-symbol historical reference acquisition, not another source/closeout/shortlist verification; the CLI first binds and prints the exact local new plan, then starts at most eleven new Massive GETs, one worker, >=13 seconds between starts, preserving raw/receipts/attempts and stopping on any quarantine. It prints HTTP status and safe structural terms on completion. No original MarketData pilot requests are repeated, and no execution-price/P&L authority follows.


### 2026-09-26 — Accepted 11/11 historical reference source; selected EOD quote acquisition

Operator completed all eleven frozen prior-session-dated Massive reference GETs with HTTP 200, 100-share/American source terms and additional underlyings NOT_REPORTED. Reference plan fingerprint `261812136e0ce8d947aece094ba60a45e69429db0093072e21f7457420361fd4`; original source-only run fingerprint `773358a1afe429191671da5077ce98e1a03e6b991d3c5404c2297fd3bcb97ae9`. **Do not rerun the 11-request reference gate or completed chain/shortlist closeouts.** No independent historical adjusted-deliverable proof, option fill or P&L follows.

New source-only V1 reads the existing reference receipts once, freezes eleven exact selected CALL EOD quote-series queries from the original 09:35 ET decision date through expiry + one day exclusive, and excludes FSLY. The operator entry point `scripts/run_marketdata_candidate_2025_selected_quotes_v1.py` performs one-command binding, bounded paid acquisition, immutable raw/intent/receipt caching, deduplicated restart reuse, storage and provider credit guards, and direct safe per-contract output. It never automatically retries an uncertain request; 404/no_data remains a narrowly scoped exact-query source gap. See `docs/research/marketdata_2025_selected_quote_source_v1_20260926.md`. This is not a return, execution-price, strategy, PAPER/LIVE or broker gate.


### 2026-09-26 — Selected 2025 CALL EOD quote source complete; offline source diagnostic next

The operator completed PR #239's selected exact quote acquisition on the first authorized run: all 11 actual CALL series returned HTTP 203; 320 historical EOD rows comprised 190 positive-volume and 130 zero-volume rows; zero source gaps or pending, 11 observed MarketData credits and 9,978 remaining. Accepted source quote plan `b15feb274a00e911a233572856254c5b1bc77b5a8930832b94d76659a16d6589`, operator source result `5912e0a4b9467a7dacf35044cfa4bc10791735e3ace3e7b50fa2ad3f38c743ea`. ATRC had 0/26 positive-volume days, BANF 0/32; these EOD last values are not evidence of same-session trading. FSLY remains an unrelated prior exact-query chain source gap. **No repeat MarketData quote acquisition or Massive reference queries.**

Distinct next offline stage: `scripts/run_marketdata_candidate_2025_quote_diagnostic_v1.py --write-local-dossier` consumes only the already saved eleven immutable local quote bodies/receipts and the accepted source binding, writes a separate D:-bound idempotent diagnostic, and prints per-contract historical observed activity, same-decision-day EOD lookahead, later activity, zero-volume positive-last and bid/ask geometric coverage. Zero provider calls, no selector change, no implied executable bid/ask/fill, historical deliverable or P&L authority. See `docs/research/marketdata_2025_quote_diagnostic_v1_20260926.md`. Independent adjusted-deliverable and preregistered EOD cost/timing policy remain subsequent gates.

 
### 2026-09-26 — Secondary-SSD options acquisition resumes beyond eleven-series pilot

Operator completed the frozen offline quote census (fingerprint `7cb463b255f57325af5b1be861250f2e16f43423fe6a19b9a266ba0b7ce183fe`): 11 original EOD quote receipts, 320 source rows, 190 positive-volume, 130 zero-volume, 273 two-sided EOD quote-geometric observations and 85 zero-volume-positive-last observations; no new provider calls. ATRC and BANF had no positive-volume day. The intended next task is **materially larger historical options acquisition on the activated D: SSD**, not more repetitions of this pilot.

The new `scripts/run_marketdata_candidate_expansion_v1.py` is a one-command **new historical chain acquisition** driver for source-supported 2022–2024 accepted daily LONG stock candidate cohorts, up to three outcome-blind monthly opportunities and 36 shared chain groups/year. It exports/validates the original native raw stock bundle once and reuses its immutable D:-bound binding later, then invokes the existing ten-attempt immutable MarketData chain cache in bounded sequential batches. Explicit new request/observed credit caps, D: 120 GiB category guard, exact original raw/intent/receipt, no retries, and optional *only* fully verified 404/no_data zero-credit offline sidecars. The first 2024 run is up to 30 new GETs; it does not replay the accepted 2025 source/quote requests. After actual acquisition, expand collision-safe full accepted source coverage and selected quote paths. Source-only, no option-fill/P&L or PAPER/LIVE promotion. See `docs/research/marketdata_candidate_expansion_v1_20260926.md`.


### 2026-09-26 — 2024 chain expansion accepted, bounded multi-year D: campaign next

The operator's 2024 three/month source acquisition (frozen plan `16a9946fdb78af8eb046e55ecfc743ff14543fbb83f53b6f1a6e84b0738d78b9`) returned **29 completed historical EOD chains, one exact zero-credit 404/no_data sidecar, five pending**, 30 new attempts and 29 observed credits (9,949 remaining). The original source export selected 36 native-raw DEVELOPMENT opportunities into 35 shared chain requests. The exact-query gap does not prove broader absence, and the accepted 2025 pilot is not repeated.

The new `scripts/run_marketdata_chain_campaign_v1.py` composes the existing source exporter and immutable receipt-based cache under one 60-request/80-observed-credit campaign, **finishing 2024's five pending requests before 2023 and 2022**. It reuses frozen source/receipt outputs, exports each new year once, applies external secondary storage and credit gates, and stops on uncertainties. It does not create false intraday fill or option P&L authority. Further all-selected DEVELOPMENT sharding and option quote histories follow this bounded acquisition. See `docs/research/marketdata_chain_campaign_v1_20260926.md`.


### 2026-09-27 — Multi-year 2024/2023 chains closed; additive 2022 sharding after original completion

Original PR #242 operator campaign `e3b18a9d32758f6016e38e29cb7696bd1bb6a0ff545c7033d896b78cb0e4572e`: **2024 34 complete + 1 exact-query gap, 0 pending; 2023 36 complete, 0 gaps/pending; 2022 16 complete + 3 independently verified exact zero-credit 404/no_data, 17 pending**. It issued 60 new GETs, consumed 57 observed credits, and retained immutable raw/attempt/receipt evidence on D:. The original 2022 cohort source fingerprint/plan remain frozen.

Next operator gate first completes **2022's 17 original outstanding query identities**, then begins `scripts/run_marketdata_additive_2022_shard_v1.py`, which adds the first entire-key-disjoint shard beyond the existing three/month sampler. That new exporter loads the 2022 accepted daily LONG source only once for an immutable shard, applies accepted raw daily OPEN PIT validation, excludes previously covered `(ticker, source snapshot, expiry)` groups even if strike query boundaries would differ, fingerprints fixed 40-group shards, and invokes the existing bounded, resumable SHA-receipted cache. Existing evidence and original 2025 are untouched; later 2023–2025 additive shards and quote-history/simulator integration are separate. See `docs/research/marketdata_additive_2022_shards_v1_20260927.md`. No option execution price/P&L or PAPER/LIVE authority.


### 2026-09-27 additive 2022 expiry-window source repair

Original 2022 sample completion is **accepted**: 33 exact chains, three proved 404/no-data, zero pending; the original campaign has no further billable work. The first additive 2022 source scan stopped *before any provider GET* on a valid calendar gap in the frozen 28..60-day exchange monthly-expiry rule. The corrected exporter explicitly records per-opportunity out-of-window omissions (SHA-bound count/ledger) rather than expanding the strategy expiry window; it also stores all same-key accepted members while reading one unique native raw opening pair per physical chain key. Next operator command runs **only additive shard 0** with 40 new request / 80 observed credit limits. See `docs/research/marketdata_additive_2022_shards_v1_20260927.md`. Original raw receipts and scientific judgments unchanged.

### 2026-09-27 additive 2022 frozen 40-key shard

Source census found 2,897 eligible cases, 20 documented monthly-expiry exclusions, 2,812 new physical keys and 71 shards. Shard 0 source SHA `438418f9e50f58ba66501e5935d3a857cedadddc2c668dd6ea69baf119c89030` and plan `9df6a0c6db48c9617a99d1decab35b84ceffd5677090516cb7a8b31095512fd8` were frozen before any new provider GET. Generic executor's old 36-group pilot limit is repaired to the already validated 250-group planner maximum; the first 40-group shard is revalidated/reused without source regeneration. Original monthly selection remains capped at 36; ten-call physical batches and 50 new GET/request budget remain intact. No trading authority. See `docs/research/marketdata_additive_2022_shards_v1_20260927.md`.


### 2026-09-27 — 2022 additive shard zero closed; first bounded multi-shard acquisition

Operator completed shard zero with 39 exact EOD chains, one separately proven zero-credit 404/no_data gap, zero pending, 40 new attempts and 39 observed credits, last remaining 9,836. Original source SHA \`438418f9e50f58ba66501e5935d3a857cedadddc2c668dd6ea69baf119c89030\`, unchanged plan \`9df6a0c6db48c9617a99d1decab35b84ceffd5677090516cb7a8b31095512fd8\`, source result \`64bfde3f86876e457dcee6f582b065000eee6558f46b638253a49b567468b1e9\`. The original 2022 three/month cohort and 2025 pilot remain fully accepted and must not be rerun.

The next distinct acquisition tool, \`scripts/run_marketdata_additive_2022_campaign_v1.py\`, reuses complete shard zero, preserves the frozen 2,812-key / 71-shard census and runs consecutive 40-key shards with a single bounded command. Accepted 2022 source material is loaded once per invocation for *new* shards, not once per shard; per-shard native raw opens, SHA lineage and immutable original receipts remain individually validated. At most ten new GETs per existing internal batch, and the user chooses a campaign cap (first: five new shards, 200 GETs and 250 observed-credit stopping target). Source data stays on D:, stock DB and simulator stay on C:. Subsequent expansion to 2023/2024/2025 and selected quote paths is separate and must remain noncolliding. See \`docs/research/marketdata_additive_2022_campaign_v1_20260927.md\`. Historical option fills, P&L, protected-holdout promotion, PAPER/LIVE and broker authority are still absent.


### 2026-09-27 — 2022 additive historical chain campaign shards 0–5 complete

The first multi-shard operator campaign completed all six requested frozen shards. **Shard zero was reused with zero new provider requests**; new shards 1–5 issued 200 total new GETs, consumed 189 observed MarketData credits and finished with 9,647 credits last reported remaining. Across the six shard plans: **229 exact historical EOD chain sources, 11 independently verified narrow 404/no_data exact-query gaps, zero pending** (shards 0/1/2/3 = 39 sources + 1 gap each; shard 4 = 35 + 5; shard 5 = 38 + 2). Campaign report fingerprint \`85ef3deb1f72a8161669b6df2f3e48d02e0544df5cff084e87a578d6b64ac892\`; frozen global key census \`dabca20038131947b5ee4cb586e7fe6c1fa9e376d4666c01967f30e88866410c\`. The accepted 2022 source was loaded once across these new shards; original source/plan/receipts remain immutable. These are **source acquisition counts only, not executable option positions or returns**.

Next distinct paid acquisition: existing \`scripts/run_marketdata_additive_2022_campaign_v1.py --start-shard 6 --max-shards 10 --duckdb-threads 4 --max-total-new-requests 400 --max-observed-credits 450 --authorize-provider-reads --confirm-paid-starter --confirm-private-internal-use --classify-exact-no-data\`. This targets shards 6–15 only, bounded by the original 71-shard census and shared budget. It is not an instruction to reissue any completed shard 0–5 request; no new code or provider pilot is required. Continue selected historical CALL quote histories and 2023/2024 additive source expansion separately; no 09:35 option fill/P&L, deliverable, PAPER/LIVE or broker authority. See \`docs/research/marketdata_additive_2022_campaign_v1_20260927.md\`.


### 2026-09-27 — Acquisition reset: chain count is not historical options pricing coverage

Operator reports that D: storage has barely grown while chain requests consume credits. The 2022 0–5 closeout remains 229 complete chain sources, 11 narrow exact no-data gaps, and zero pending; 6–15 currently runs under its original authorization. This is expected to be compact EOD **snapshot** data. Do not launch more repetitive chain-only campaigns as an end in themselves. Implement a single source-bound, resumable, credit+storage-aware pipeline spanning accepted chain coverage **and exact selected-contract historical from/to EOD quote series**, deduplicated across repeated OCC symbols and bounded by actual reported billing and physical D: quota. Preserve existing original receipts, plans and no-lookahead rules. MarketData's published Terms require deletion of downloaded licensed data when the subscription ends absent separately obtained rights; do not represent the SSD as a perpetual raw-data license. See \`docs/research/marketdata_bulk_acquisition_reset_20260927.md\`. EOD cannot prove 09:35 fills.


### 2026-09-27 — Operator subscription and simulation scope clarified

The operator explicitly confirmed this historical options dataset is for **private ATLAS simulator/research use**, and the paid MarketData subscription will remain active for as long as needed to run those strategies. The intended workflow is reusable local D: historical chain plus selected-contract EOD quote source, not immediate subscription cancellation. The existing terms-of-service requirement for eventual termination still applies; this is not a perpetual offline-license assumption. Prioritize complete source coverage needed by scenario design, deduplication of paid requests, actual receipt bytes and credit-ledger observability. Chain-only snapshots must not masquerade as priced options simulations. Do not start an overlapping provider job while the previously authorized 2022 shard 6–15 campaign is active.


### 2026-09-27 — Accepted 2022 0–15 chain closeout and widened historical CALL price-source program

The additional 2022 chain campaign 6–15 completed: 372 exact successful chain sources, 28 strictly proven zero-credit 404 source gaps, zero pending, 400 new GETs/372 observed credits; last provider balance 9,275, report \`d358e3b4816cf7a588adc5f3f19e863f369e6d7d51f43eacd3fac59f0df77dbe\`. Additive 0–15 combined are 601 exact chain sources + 39 narrow gaps, no pending. Do not rerun any shard 0–15 source.

V1 historical CALL quote selection (nearest plus two strikes) is **superseded for the next broad acquisition** by \`scripts/run_marketdata_2022_broad_quotes_v2.py\`: every actual prior-session CALL returned within ±8% of individual raw entry OPEN in source shards 0–15, one full EOD quote history per distinct exact OCC symbol with immutable source membership and reuse of the existing V1 physical quote cache. This is a substantive data-stage expansion, not another chain-only 40-key campaign. The only available expiry in these original sources is the original 28–60-DTE monthly; alternate expiries, 2022 original pilot cohort, other years and remaining source shards still require separate real source acquisition. No 09:35 option fill/P&L or PAPER/LIVE authority. Full planning and handoff: \`docs/research/marketdata_2022_broad_quote_envelope_v2_20260927.md\`.


**Historical options bulk performance (2026-09-27):** 2022 V2 selected CALL quote histories are network-bound, not CPU/SSD-bound. Original first command \`--workers 4\` remains valid while already running. Future bounded exact-cache runs default to 16 concurrent GETs, support 1–24, and report actual GETs/s, without changing source/quote identities, re-requesting completed receipts, or weakening D:/credit/no-retry checks. See \`docs/research/marketdata_2022_broad_quote_envelope_v2_20260927.md\`.


### 2026-09-27 — Accepted 2022 PIT-wide exact CALL EOD quote closeout

Operator's initial four-worker campaign for additive shards 0–15 completed **all 1,709 selected exact OCC full-to-expiration EOD quote histories**, with zero quote no-data gaps and zero pending. The local frozen plan is \`through_shard_015.json\` (fingerprint \`3bde57ddc8c8675f48404a85d9c04d463f980abbb9db384c62ad663965381043\`); 1,835 opportunity/contract memberships deduplicate to 1,709 physical exact series. Invocation: 1,709 new GETs, 1,704 observed credits, final MarketData remaining 8,296, 19,795,286 original raw quote body bytes, report fingerprint \`a87b9e19b57a115d0293b1df816787c0470c4f88f509064840f65c3706022929\`. Physical D: candidate_cache changed 0.002 → 0.023 GiB (before/after storage snapshot); D: free changed 226.911 → 226.679 GiB across the run; do not attribute the entire free-space delta to just quote raw bytes. All 1,709 exact quote requests are *completed*; no rerun just to exercise the newly merged 16-worker performance change.

**Source abstention accounting:** The prior 2022 additive chain acquisition closed with 39 physical exact-query 404 gaps among 640 acquired physical keys. The wider quote plan reports **40 source-gap ledger entries**, a per-source/member abstention count (may include a completed chain without eligible CALLs); do not relabel it 40 provider 404s. No zero-quote histories were recorded. Current evidence does not yet aggregate quote-day counts, positive versus zero reported volume, or last observed sessions; source \`s=ok\` alone does not establish usable entry/exit pricing or liquidity.

**New next gate is offline coverage audit before additional paid reads:** \`scripts/audit_marketdata_2022_quote_coverage_v1.py --shards-through 15\`. This verifies original plan+receipt+body SHA and sums actually observed EOD rows, positive/zero reported volume, histories without any positive-volume rows, observed session extrema, aggregate original bytes/charges, exact gaps and pending. It makes **zero provider requests** and writes no provider data or new receipts. If the audit reveals materially sparse/zero-volume series, revise next acquisition/price scenario before charging the next historical cohort. Only then authorize new 2022 source shards 16+ and reuse all 1,709 exact histories in the wider plan. EOD remains source-only with no 09:35 executable fill/P&L or PAPER/LIVE authority.


### 2026-09-27 — Local 2022 EOD coverage acceptance and coordinated new-source/new-history campaign

Accepted read-only audit \`70e2e5ba9bd2c97322066de2c82ba8fbc581949569412dfc34e46c04e55bf88a\` verified all 1,709 exact saved historical CALL histories from 0–15, zero quote gaps/pending, 128,625 dated EOD rows (47,985 positive reported volume; 80,640 zero reported volume), and 100 histories without a single positive-volume observation. Original response bytes 19,795,286; original report charges 1,704; D: remaining 226.679 GiB. No quote results establish executable 09:35 fills or model P&L. Rather than repeat this audit or replay paid 0–15 series, proceed with the new \`scripts/run_marketdata_2022_coordinated_chain_quotes_v1.py\`: strict source-stage completion of shards 16–25 (up to 400 new exact chain GETs), then one frozen V2 PIT CALL quote plan through 25 with reuse of all original exact 0–15 histories and up to 3,000 genuine missing full EOD series (16 bounded network workers), under a combined observed-credit stopping target 3,500. No quotes if a source is partial/uncertain, and no blind retries. See \`docs/research/marketdata_2022_coordinated_chain_quote_v1_20260927.md\`.


### 2026-09-27 — Accepted coordinated 2022 16–25 closeout; transition to one 2022 bulk command

New operator result \`01bc9b6e3187161d6cc296cabe54e1ca5c993b89cdbfde962ef5cfc63876163b\`: 400 new physical chain GETs, 378 original complete, 22 exact proved gaps, 0 pending, 377 chain credits. Total additive physical source 0–25 is 979 complete / 61 exact 404 gaps across 1040 keys (separate original 36-source pilot not included). Exact EOD CALL histories 2,725 complete/0 gaps/0 pending, including 1,709 prior reused + 1,016 new, quote credits 1,010. Aggregate credits1,387; last observed6,909. Quote throughput 2.84 GET/s with16 workers, original chain stage serial. Source/quote data on D:; 31,361,769 verified raw quote bytes, candidate cache 0.023→0.036 GiB.

The successor \`scripts/run_marketdata_2022_complete_bulk_v1.py\` is one explicit 2022 remaining-shards26–70 campaign: original prior verification once, one accepted native stock load, independent source-plan waves starting8 network workers and adapting to max24, strict all-source-complete barrier, then 24-worker original exact quote cache through70, up to6500 new requests within aggregate observed-credit target6400 and protected provider/D: floors. Every paid response is persisted with original attempt/receipt; source/QC complete later. It automatically reuses all 2725 original saved quote histories and 1040 physical source keys, does not acquire non-monthly expiries/other years, and cannot infer 09:35 fills. Detailed runbook \`docs/research/marketdata_2022_complete_bulk_v1_20260927.md\`.


**2026-09-27 accepted entire frozen 2022 selected CALL source closeout:** all 71 original additive source shards / 2,812 physical chain keys reached terminal original source status; 45 new shards 26–70 added 1,772 physical GETs / 1,661 observed credits. Frozen quote plan 8,518 memberships → 6,398 unique exact OCC EOD CALL histories, all 6,398 complete, zero exact quote gaps/pending; 3,673 newly downloaded histories and 2,725 original reused, 3,647 quote credits. Whole run 5,308 credits, last provider1,601, 73,016,761 verified quote-body bytes, D: options candidate cache0.085/120GiB, free225.589GiB; 0 paid receipts replayed. Approx43.7min single-run elapsed. Report \`e0958bd4321b80919262fe38caee61d435d995517fcdceb33a0d2d508fc0c2a0\`, plan \`017805741349c5bd93eead00123282cee8a3980fcf9d3c368147b0ed4bbe6786\`. No repeat GET. **Not** a full options market, alternate expiry/PUT, adjusted deliverable, 09:35 option fill or P&L result. Next distinct research source work: accepted DEVELOPMENT 2023–25 complete physical source census/campaign (not invented from 2022 counts); later all-corpus local audit and EOD scenario with clear timing/cost assumptions. See \`docs/research/marketdata_2022_complete_closeout_v1_20260927.md\`.


### 2026-09-27 — Entire 2022 local quote audit accepted; new rank-zero scenario-readiness gate

Operator's completed read-only full-2022 audit \`f1adec38fbffa2fa2612dda0e3f68cac128c39434cc99651b6a30cddcd8b5298\` confirms 6,398/6,398 source histories, zero quote gaps/pending, 473,683 observed EOD quote rows, 170,861 positive reported volume, 302,822 zero reported volume and 421 histories without positive reported volume; 73,016,761 original raw bytes; 6,361 original provider charges summed across all historical receipts; zero new API calls. This closes the same-source quality audit. The new \`scripts/assess_marketdata_2022_ranked_eod_readiness_v1.py\` is **not another coverage audit**: it joins structural rank-zero CALLs to original signal/decision dates, excludes same-day EOD for 09:35 entries, and counts later dated/two-sided/positive-volume EOD context without assigning fills, deliverable multipliers, returns or strategy authority. All 2022 original paid receipts stay untouched. See \`docs/research/marketdata_2022_ranked_eod_readiness_v1_20260927.md\`. Separately design 2023–25 source/quote plans under fresh exact year-specific census before another paid request.


### 2026-09-27 — Accepted rank-zero readiness and EOD reference-value successor

Operator's offline rank-zero readiness result \`8f561664c6ee0bc11aed44bfe4a84606701e93a9aa8a3cbd7f4b53a102452efc\` joins 2,643 original stock opportunities to 2,227 preferred CALL histories, 0 lacking later EOD rows, 5 lacking later two-sided context, 2,638 with later two-sided context, 2,629 with at least two later two-sided dates and 2,435 with some later positive-volume row; zero new paid reads. That gate is accepted and must not be repeated simply for reconfirmation. Next distinct zero-credit artifact is a *hypothetical price reference only*: first strictly-later dated valid two-sided observed ask versus next strictly-later dated valid bid, with original updated timestamp, availability/volume and fully reported original denominator, no future-dependent contract selection or cash P&L. See \`docs/research/marketdata_2022_rank0_later_eod_reference_v1_20260927.md\`. The C: project options namespace is a verified junction to D: physical options; never duplicate raw data on C:.


### 2026-09-27 — Accepted cross-year stock/news/native data bridge; original option gap census implemented

The workstation completed \`scripts/build_multiyear_stock_news_source_v1.py\` on the accepted 2021–2025 DEVELOPMENT source: 14,902 selected daily LONG stock cases, broken out as 5,491 in 2021, 2,900 in 2022, 1,601 in 2023, 1,390 in 2024, and 3,520 in 2025. The original 2026 accepted-DEVELOPMENT source count is explicitly zero pending separately qualified prospective evidence, not an assumption that there were no market opportunities. All 70 historical news partitions were SHA verified; 1,426,704 normalized article rows scanned. Exactly 3,002 cases had at least one prior-24h article and 8,121 had at least one prior-7d article under conservative original revision chronology. Feature-join fingerprint: \`0f42e414031837242d9838f88b00f6a1e55ca77ff0e1a208050aa3fbeb7a4a69\`. These counts describe source evidence only; no trades or option P&L.

Original native stock-open binder PR #273 merged (main SHA \`2a5753918f4f04392d52332e8c00292927ecb7ac\`) after all 20 checks passed. Operator verified 1,692 accepted original C:-native raw units, yielding 14,885 exact native raw-as-traded opening prices, 17 deferred late-2025 signals with 2026 entry, and 20 2022 cases without a qualifying frozen monthly expiry; full 14,902-case denominator preserved. Accepted derived native evidence SHA fingerprint: \`e0b29569ece159208cfa0303b7d94b596b6e08299a509367d0b0538939ae8e64\`. All research derived files resolve through D:-bound research evidence, options and news; stock base stays C:. No provider calls in these three local stages. The 1Day raw OPEN is not an executable 09:35 stock or option fill.

The new \`scripts/build_multiyear_option_gap_inventory_v1.py\` implements the next zero-GET source-inventory gate: preserve every actual 2021–2025 case, test exact 2022 preferred rank-zero option-plan member IDs and raw-open/OCC/expiry against the frozen 6,398-history original quote plan, report same-key and not-yet-reconciled 2022 source cases distinctly, acknowledge 2021 pre-rolling-floor decisions, and mark 2025 pilot and deferred 2026 cases for independent source reconciliation. It emits a provisional full-year raw-open ±8% physical chain-query *size preview*, not permission to spend paid credits or proof of historical option fill. Operator inventory result is still pending; do not infer new-call counts from the original 2022 2,643 reference denominator or reacquire the original 2022 corpus. Future source work must reconcile exact original 2022/2025 chain receipts first, then choose true missing PIT contracts, reuse original quote histories, and independently establish matched-clock stock/option marks, contract terms, costs and model-derived Greeks.


### 2026-09-27 — Full original options source inventory accepted; 2022/2025 physical source crosswalk implemented

The user's zero-GET multiyear option inventory completed under fingerprint \`8fe80351a13f328aaaf780d4631cb2245827407bb2fe2f58ead3f4222748122f\` and reused the earlier accepted 14,902 stock/news/native input files without rescanning. All 2,643 original frozen rank-zero 2022 preferred-CALL plan case IDs matched exactly. The 2022 full 2,900-case count partitions as 2,643 matched preferred, 27 original same-key cases needing their own contract ranking, 210 other source cases requiring the original physical-chain crosswalk, and 20 frozen no-monthly-expiration cases. 2021 had 4,138 cases before the current rolling-floor date and 1,353 potentially eligible; 2023 1,601; 2024 1,390; 2025 had 3,503 potentially eligible cases pending old-pilot attribution and 17 deferred entries requiring separate 2026 source. The 7,654 provisional multi-year chain query groups remain a pre-reconciliation size estimate, **not 7,654 new paid GETs**. D: free 225.50 GiB. This inventory neither selected new OCC contracts nor requested provider data.

The next implemented \`scripts/reconcile_multiyear_original_option_sources_v1.py\` is a **zero-provider** read-only physical-source identity crosswalk. It checks the 71 original 2022 additive source bundles/plans, the original 36-case 2022 pilot receipt subset, and the existing 2025 twelve-case closeout and shortlist, binding raw original stock OPEN, signal IDs, prior chain query keys and dates. It distinguishes 2,643 preferred source pointers, additive same-key other-case decisions, chain-source abstentions, first-2022 pilot IDs and previous-key collisions. For 2025 it distinguishes the prior eleven complete pilot source chains from one exact FSLY 404/no_data without declaring market-wide absence. Original 6,398 2022 quote bodies are **not rescanned**. Output is an immutable derived file on D: only if the actual local SHA-bound sources match all stated identities and denominations. No additional option fill, P&L, strategy, PAPER/LIVE or paid acquisition authority is created; continue with a separate physical missing-chain plan only after the crosswalk returns.

### 2026-09-27 — Original 2022 same-key source census mismatch: strict local-only audit

The first PR #275 workstation crosswalk stopped correctly after the 71 accepted 2022 source shards: 2,812 original physical representatives and 169 source abstentions matched, but the old source's full same-key ledger contained **29** IDs versus **27** identities in the accepted 14,902-case inventory. The two IDs have not yet been identified by the operator; this is not an accepted source closeout or permission to change the denominator. A follow-up offline gate compares every old member ID against **all** accepted census IDs and previously acquired physical roles. Only if the two extras are demonstrably outside the frozen accepted stock cohort, with no missing or conflicting in-cohort ID/physical role, does it retain them as two explicit prior-source-only provenance records separate from the 14,902 in-scope cases. In-census mismatch or physical-role overlap instead stops with exact ID/key/shard diagnostics. Original receipts remain untouched; zero provider GETs/credits; no option fill or new paid authority.

### 2026-09-27 — Exact ESLT/COKE source overlap clarified, second offline reconciliation stopped

The original-source member diagnostic established that the two extra old same-key IDs **are in the accepted 2022 2,900-case stock census**, not prior-only: ESLT 2022-02-08 / 2022-03-18 in shard 8, and COKE 2022-02-14 / 2022-03-18 in shard 18. The first 27 same-key identities came from the original preferred-CALL *quote* plan, which does not include alternate members of representative chain requests that produced no selected CALL or exact-query no-data. The 71-source ledger instead has 29; these two cases were previously in the 210 unresolved-source inventory. PR #276's prior-only hypothesis correctly failed closed and made no provider request. The next crosswalk gate requires the two exact IDs and keys to link to original source-gap representatives, preserves their source scope and independent raw-open strike coverage, counts all 29 same-key cases in 2,900, and independently verifies the remaining pilot-key collision count (three expected after separating the two). Neither a gap-linked alternate nor a no-CALL/exact-no-data parent proves entire-market option absence, an independently ranked CALL, or a fill. Source remains D:-bound, offline, immutable; no new provider requests or 2026 protected reads.

### 2026-09-27 — Full-case original-source accounting must keep real uncovered memberships (third offline attempt)

The workstation confirmed 2,812 original 2022 representatives, 29 same-key ledger members including the two verified ESLT/COKE gap-linked cases, and zero provider GETs. After 7,500/14,902 original stock cases, the crosswalk stopped on an accepted 2022 case **outside its exact-ID source and frozen pilot key lookups**. The previous fixed prediction of three pilot-key other cases was not physically demonstrated; do not force it or assert that all 2,900 accepted signals have an original 2022 physical chain. The source-only crosswalk now accounts for every accepted case and separately reports any exact-ID membership not present in original source bundles: an existing matching physical query key is retained only as a source-only possible pointer with its own verified raw OPEN/strike coverage and no inferred CALL selection; a truly absent original physical key is an explicit acquisition-candidate gap, not proven provider-market absence or authorized API demand. Older source representatives absent from the frozen accepted census remain separate immutable provenance, not invented new stock signals. Both cases retain the original 14,902-case denominator and fail-safe zero provider/P&L/PAPER/LIVE authority; print the actual case IDs, source keys, and pilot collision IDs. The full accepted source accounting may complete with openly reported source-membership gaps; it does not claim full option-trade coverage. No reacquisition/quote reread/2026 protected reads.

### 2026-09-27 — Accepted full-case 2022 source accounting complete; multi-year physical demand preview

The local crosswalk `45bb0490a38d2b0b5657115fc3dbc3e973dee2328da459c4ce427d92dd8ce682` succeeded: all 14,902 original stock cases accounted for, 2,900 2022 accepted, zero pilot-key colliders, zero prior source-only representatives and **three actual absent original 2022 physical chain keys:** ENPH, ESLT, MSTR (all 2022-12-30 signal → 2023-01-03 original stock entry; expiry 2023-02-17). The original 2022 chain/quote data and the 2025 pilot stay reusable without reacquisition; D: free 225.49 GiB. New offline `scripts/plan_multiyear_physical_chain_source_demand_v1.py` freezes actual multiyear source preview from this immutable crosswalk and 7,654 original provisional groups, excluding accepted 2025 pilot memberships and adding these three exact gaps. Expected candidate memberships: 1,353 2021, 3 2022, 1,601 2023, 1,390 2024, 3,491 2025 = **7,838**; distinct physical preview queries are computed, not assumed paid GETs. Separately retain 4,138 pre-rolling-floor signals, 20 no-expiry cases, 17 2026 native-entry deferrals, and zero new 2026 accepted stock signals. Zero network/credits, no source/quote body recrawl, no new paid-authority/fill claim. See `docs/research/multiyear_physical_chain_source_demand_v1_20260927.md`.

### 2026-09-27 — Zero-credit global physical chain-cache overlap and historical Greeks requirement

Accepted full source preview `7890c81e62905307fb1cc2c1bf3f2205eece3dfdf04b712ee1b8a09d419f084c`: 14,902 original stock cases, 7,838 unresolved source-case memberships → 7,646 distinct physical-key *previews*, zero paid authority, D: 225.47 GiB free. New `scripts/audit_multiyear_global_chain_cache_overlap_v1.py` indexes small signed original D: chain receipt/attempt metadata once, reads raw chain only for physical key + intersecting strike coverage, reuses frozen 2025 11+1 closeout and original 2022 source/6,398 quote pointers, classifies full/partial/exact no-data/missing/unresolved without retrying anything, and publishes a signed per-year/physical-query immutable report. This stage must precede new chain budget or quote history demand. **Greeks remain required:** derive observed-mid local IV, delta/gamma/theta/vega/rho only with time-matched two-sided option and underlying observations, exact standard contract terms and PIT rate/dividend evidence; never fabricate missing Greeks or call later EOD a 09:35 executable fill. Full runbook: `docs/research/multiyear_global_chain_cache_overlap_v1_20260927.md`.

### 2026-09-27 — Accepted global overlap now drives year-balanced paid acquisition

Operator-supplied signed overlap `056c70bc7163b793b3c4cc2c83bee48b19272d95171f8dee8c9d296b5c65d30b` established 7,574 genuinely absent local physical-query source keys, 71 reusable complete keys, and one exact-query no-data. The cross-year runner `scripts/run_multiyear_chain_campaign_v1.py` reads those original accepted D: manifests directly and dispatches new 2021/2022/2023/2024/2025 source keys fairly under operator-specified paid request/credit limits; exact original global receipts are never overwritten. The original 2022 6,398 full CALL quote series remain pointer-only reuse, and older-2021 rolling-provider gaps/2026 protected replay gaps remain visible. This is forward progress on source acquisition, **not** a repeat of the global cache audit and not a completed quote/Greeks/portfolio simulator. Strategy-development objective: empirically robust net compounding, not any target percentage or prescribed starting-account multiple. Runbook: `docs/research/multiyear_chain_campaign_v1_20260927.md`.

### 2026-09-27 — Offline bridge from accepted stock/news cases and D: chains to selected exact quote histories

The accepted 14,902 original stock/news/native-open case set and original crosswalk now feed `scripts/prepare_multiyear_option_quote_sources_v1.py`. This is a zero-provider, D:-bound source compiler: original 2022 CALL pointers must exist in the accepted 6,398 exact-series plan; new and intersecting verified original physical chain bodies give deterministic PIT nearest-ATM CALL/PUT identity by original raw stock OPEN (OTM tie-break); missing source/2021 rolling gap/no matching right remain explicit. It produces immutable full-case coverage and a deduplicated exact OCC/full-history quote-demand plan for the existing cache runner. It does not create fills, Greeks, portfolio P&L or previously unaccepted 2026 signals. The next stage is real quote-series acquisition/reuse and an offline common-clock/account-level simulation, not another full census or repeated small validations. See `docs/research/multiyear_option_quote_bridge_v1_20260927.md`.

### 2026-09-27 local / 2026-09-28 UTC — Operator accepted multiyear PIT option-source bridge output (zero paid reads)

Operator ran `scripts/prepare_multiyear_option_quote_sources_v1.py --rights both` after merging PR #283. The immutable D:-bound source-selection artifact is `data/options/manifests/multiyear_pit_selected_option_quotes_v1_3fa478312734f9c2.json`; the exact deduplicated quote-demand plan is `data/options/manifests/multiyear_demand_quote_v1_dbe759955e48946b.json` (the C: repository namespace is junction-bound to D: physical option storage). The run preserved **14,902 original accepted stock cases**, **29,804 case/right slots** and selected **7,788 case/right memberships** representing **6,622 distinct exact OCC/from/to quote-series demands**. Selection partitions: 2,654 accepted original PIT CALL pointers; 2,712 independently verified original chain picks; 2,422 verified newly cached PIT chain picks. Nonselected slot dispositions: 468 exact-query-only no-data, 13,126 missing exact chain sources, 40 without frozen expiration or native OPEN, 72 without original physical source identity, 8,276 pre-rolling-floor 2021 right slots (4,138 stock cases), and 34 protected 2026 entry slots (17 stock cases). These are **right-slot counts**, not independent stock cases or provider request counts, and exact-query no-data does not establish that no alternate contract existed. Reported available D: space: **225.212 GiB**; **no new provider GET, fill, Greeks result, P&L, or strategy authority**. The rolling source floor in the frozen quote plan is 2021-09-27.

**Immediate next distinct gate:** execute `scripts/run_multiyear_demand_quote_cache_v1.py --plan .\\data\\options\\manifests\\multiyear_demand_quote_v1_dbe759955e48946b.json` in zero-GET preview mode; capture accepted 2022 quote reuse, verified new cache, exact quote gaps and genuinely pending histories. Do **not** treat all 6,622 as missing, regenerate the plan, repeat original 2022 acquisitions, or authorize another chain-only campaign from this bridge count. Existing downloader has a hard 250-request/250-credit/8-worker/500-credit-floor policy; revise via separately tested, operator-controlled budget changes before any future paid run, preserving first observed header, immutable intent/body/receipt, D: quota, no automatic uncertain retry, and no overlapping provider jobs. Next engineering sequence is verified missing-history acquisition → common-clock stock/news/options quote adapter → historical rates/dividends and deliverable validation → conditional IV/Greeks → EOD account-level position replay with bid/ask, slippage, fees, expiry, cash/equity and explicit no-fill states. Original 09:35 replay requires independently sourced intraday option quotes; 2026 protected outcomes remain closed. Historical source readiness is not evidence of profitable or executable options trading.

### 2026-09-27 local / 2026-09-28 UTC — Accepted offline exact quote cache census; source-to-replay handoff

Operator ran the original frozen `dbe759955e48946b` 6,622-query quote plan in zero-GET preview mode. Accepted report fingerprint `09b634c4392f4ac326e9e58c6722ad0774d2cb565304ad11beea7438080b229c`: **2,229 original 2022 covering exact histories reused, zero complete in the new multiyear cache, zero exact quote-query gaps, and 4,393 pending in the currently indexed caches**; 7,788 selected case/right memberships remain eligible; zero API requests and credits. The 4,393 are **not proved to be absent across all legacy caches** and must not trigger indiscriminate paid downloads. This quote-history count is separate from missing chains, 468 right-specific exact chain-query no-data slots and 2021 pre-floor coverage.

New versioned `scripts/prepare_multiyear_option_quote_reuse_handoff_v1.py` compiles a signed **29,804-case/right full denominator** source-to-replay map from the already frozen PIT selection, quote plan and independently verified offline cache receipt census. One immutable D:-bound record per slot binds the original case, right, selected OCC, original source status, exact quote-query ID, existing 2022/cache body SHA and observation count when present, or explicit quote/source gap. Shared physical history never becomes several paid requests. Prints year-specific source reuse/gap counts, no provider GET, no quote fill/Greeks/return claim. This is an integration handoff, not another paid or strategy study. Existing `packages/simulation/stock_option_common_clock_v1.py` and `historical_option_greeks_v1.py` are source-agnostic research components; next connect the now signed handoff to actual verified quote observations and native stock marks with EOD same-clock constraints, then real account-state replay and cost/deliverable inputs. The old 2025 pilot full/partial overlap and later new caches must be evaluated before charging missing queries. The previous provider's **487** reported remaining credits is a historical observation, not a current balance or permission to spend.

### 2026-09-27 local / 2026-09-28 UTC — Accepted full-case source reuse handoff and actual option-observation adapter

The operator executed the merged offline full-case handoff successfully: fingerprint `46e4c27c3d203581ae92c2f0ff653c9c3e65b1fa07f093a195dca2ecd8aff8cd` at `data/options/manifests/multiyear_option_quote_reuse_handoff_v1_46e4c27c3d203581.json`. It retains **14,902 original cases / 29,804 right slots / 7,788 structurally selected case-rights**. Year-specific statuses, in right-slot counts: 2021 574 quote pending, 10,408 without selected OCC; 2022 2,670 with reused exact history, 2,678 pending, 452 without OCC; 2023 3 with reused original-2022 covering source, 625 pending, 2,574 without OCC; 2024 638 pending, 2,142 without OCC; 2025 600 pending, 6,440 without OCC. Hence **2,673 case/right uses share 2,229 physical original-2022 quote histories**, and 5,115 selected case/rights share 4,393 pending exact series. No historical option fill, account P&L, or provider call was claimed.

New offline `scripts/prepare_multiyear_observed_option_quote_timeline_v1.py` takes the accepted selection, exact plan and handoff, re-verifies only the original exact quote receipts/bodies actually referenced (not the whole 6,398-series accepted corpus), decodes each shared physical history once, preserves all original 29,804 slots, and freezes observed provider timestamp, positive/crossed bid-ask flags and first/next **strictly later-session** valid two-sided historical quote observations. An original 09:35 decision never receives a same-day EOD fill; option vendor `updated` is **not** presumed to be historical publication time or 16:00 ET. Missing/uncertain/changed evidence stops rather than substituting another symbol or sending a GET. This is the source-observation bridge needed by the existing `stock_option_common_clock_v1`; it has no native same-clock stock EOD mark, verified deliverable, local Greek input, fill, strategy authority, or account return yet. The recorded 2025 pilot and other old quote cache overlaps still need exact-range/receipt reconciliation before new paid quote histories are acquired.

### 2026-09-27 local / 2026-09-28 UTC — Cross-window original 2022 quote source normalization correction

The first actual run of `prepare_multiyear_observed_option_quote_timeline_v1.py` stopped offline at `quote timing, spread or source classification changed`, with no derived output, provider GET, credit expenditure or source mutation. The new adapter mistakenly required **every row in an intact original 2022 covering history** to fall within the narrower immutable selected quote request. The original accepted 2022 source can correctly begin in 2022 while a selected request starts in 2023 (three original 2023 selected memberships reuse original 2022 physical series). New implementation validates the **full physical raw source** using original exact intent/receipt/body SHA and every decoded source row, including earlier dates, then restricts its observed timeline to the signed selected from/to interval. The original 09:35 decision-day EOD exclusion and two-sided spread checks remain. Regression tests cover earlier same-year rows, 2022 full source covering a 2023 request, and invalid earlier rows that must still fail. All original 29,804 case/right slots and the accepted prior fingerprints remain unchanged; no new paid acquisition or source reconstruction. Rerun only the same offline timeline command after green CI/merge.

### 2026-09-27 local / 2026-09-28 UTC — Covering-history correction and combined offline stock/option advancement

The operator's first observed timeline run stopped safely on an overstrict selected-window check against verified covering original quote rows. PR #287 resolved this: the original complete source receipt/body and every original observation remain validated, then the selected demand view is narrowed without treating legitimate preceding source rows as a violation. Its cross-year 2023 and narrower 2022 tests passed; the original accepted source files were not altered. This is an adapter-window correction, **not evidence that the option prices were wrong or usable as historical 09:35 fills**.

The next single local command is `scripts/run_multiyear_option_stock_eod_preflight_v1.py` (zero paid calls). It performs three distinct, useful gates in one execution: (1) the corrected 29,804-slot option timeline with actual later-session two-sided source coverage from 2,229 reused exact original quote histories, (2) legacy 2025 pilot receipt/contract/range overlap against the 4,393 currently pending distinct quote requests without assuming a partial legacy history covers the entire demand, and (3) a signed deduplicated **native raw 1Day CLOSE demand** for the exact underlying instrument/ticker/session of observed option entry/next source records. It writes immutable D:-bound derived quote, overlap and native-close request evidence, using the original 14,902-case denominator and retaining no-data cases. A fourth gate now uses that exact native CLOSE manifest to verify original V2 acquisition-plan/checkpoint identities and SHA of only required C:-bound canonical daily units, then reads the exact regular-session raw-as-traded CLOSE bars with bounded 1–4-unit concurrency. Missing exact dates remain explicit gaps and the derived source is persisted on D:. It does **not** claim a proven same-minute stock/option mark, 100-share deliverable, executable EOD fill, account return or protected holdout authority. It never rescans the full multi-billion-row stock corpus or reselects original signals.

A separately tested, opt-in quote downloader policy also raises the per-invocation hard ceiling from 250 to 10,000 exact requests and from 250 to 20,000 observed credits, supports up to 24 workers, and adds `--min-remaining-credits` (default **500**, explicitly settable to zero rather than silently imposing an extra voluntary reserve). Up to **two credits of possible exposure are reserved per in-flight GET**, including the first GET used to observe live provider headers. The original offline preview/census report schema and frozen fingerprints are unchanged; no existing receipt/attempt is rewritten, uncertain paid attempts never retry, and the one-command offline preflight does not exercise any paid mode. Actual future paid batch caps and remaining allowance still require explicit operator authorization and an account balance. Legacy overlap must be considered before authorizing any quote history GET.


### 2026-09-28 — Same-run full-cohort stock/option dated source casebook (source-only)

The consolidated zero-GET workstation preflight now adds a fifth stage after targeted original C:-native raw daily CLOSE verification: an immutable D:-bound signed full-cohort source casebook. This is added to the same existing script, not a separate workstation command. It joins every original 14,902 signal / 29,804 case-right slots by immutable identities across the accepted quote reuse handoff, receipt-verified option timeline, frozen native-close demand and SHA-verified original native CLOSE source. Each selected slot retains its original OCC, quote-body SHA, observed later option bid/ask and provider update timestamp, and actual native raw stock CLOSE on exactly the corresponding ET session if present. Nonselected and missing-source slots remain in the denominator. It reports per-year counts for absent later two-sided option source, native exact daily gaps and dated stock+option source pairs; 2026 remains zero in this accepted 2021–2025 source population. Results are immutable under the configured D: options derived binding; source files and prior signed artifact fingerprints are not rewritten.

Dated source evidence **does not** prove matched stock/option observation timestamps: a provider update is not historical publication time, the original native daily bar does not carry a certified option-synchronous close timestamp, and original 09:35 entry cannot use later EOD. No deliverable/multiplier is inferred; no historical fill, Greek, option P&L, account return, PAPER/LIVE or new protected-holdout authority is granted. The source casebook is the bounded, receipt-linked join for subsequent independent clock/deliverable/cost validation and account replay, not a simulated trade. No new provider calls or broad original stock corpus scan are introduced. The fourth-stage native close reader remains 1–4 workers and stops on SHA/plan drift or an invalid required native source; exact missing daily bars remain explicit gaps.

One operator action after merge, from ATLAS PowerShell root:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\.venv\Scripts\python.exe scripts\run_multiyear_option_stock_eod_preflight_v1.py --native-workers 4; if ($LASTEXITCODE -ne 0) { throw 'Combined option-stock source preflight stopped; paste complete output. No blind paid retry.' } }
~~~

Next: inspect actual one-pass source counts and gaps before authorizing paid exact series; account-level simulation requires independent clock, original deliverable, commissions/fees, expiry and fill semantics, plus the accepted signed source population. Do not re-run earlier successful census/selection/acquisition stages merely for another status check.


### 2026-09-28 — Offline multiyear account mechanics and actual source-admission census

A separate, zero-provider account-mechanics kernel now supports four alternatives (STOCK, CALL, PUT, ABSTAIN) on **the same original synthetic signal cohort**. It orders events chronologically, releases exits before same-timestamp entries, enforces cash-only long positions, allocation fractions, maximum concurrent positions and units, adverse stock slippage, option ask-to-enter/bid-to-exit plus separate per-contract entry/exit fees, and reserves exit fees before new admissions. Every omitted leg, insufficient cash, unqualified clock/source, unknown option deliverable and expiry/assignment uncertainty is an explicit nontrade rather than a fabricated exit. Complete modeled exits return an auditable cash ledger and per-year status counts; no intraday mark/drawdown, historical fill or portfolio-return authority is claimed. Historical data **cannot** be smuggled into this fixture engine by merely setting a proof flag: the kernel admits `SYNTHETIC_FIXTURE_ONLY` source origin, while actual evidence requires its own later verified admission adapter.

The new `multiyear_account_readiness_v1` accepts the operator's original immutable signed `176aa0427a9ec34f...` 29,804-right casebook without decoding the historical raw corpus again. It checks the original case/right denominator, all C/P memberships, D: source fingerprint and unchanged source-only/unsynchronized authority; labels exactly why each historical right cannot yet enter a true replay. The current 2,648 **date-matched but unsynchronized** source pairs remain in the population, with zero qualified historical trades and NULL historical P&L; the 11 native-close gaps, 4,393 previously pending exact histories and 2026 protected/absent population are not silently promoted. Report is immutable and stored on the configured D:-bound options derived path, while the stock database and simulation code stay C:-resident. Neither operation issues a MarketData GET, touches the accepted receipts, or asserts that an option provider update equals the native stock close clock.

One future offline operator step after merge (from ATLAS repository root) audits the actual source-admission census and executes a **clearly labeled fabricated-price** smoke scenario for all four account modes:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only origin main; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\.venv\Scripts\python.exe scripts\run_multiyear_offline_account_replay_v1.py --synthetic-smoke; if ($LASTEXITCODE -ne 0) { throw 'Offline account source-admission/synthetic-engine run stopped; paste complete output.' } }
~~~

Next real-source integration: independently qualify option/publication and native underlying clock, verified historical deliverable/multiplier, source-proven entry/exit side plus cost/expiry policy; then add a receipt-bound historical adapter to the account kernel. Do not report the synthetic smoke P&L as historical performance or use same-date (unsynchronized) data as exact-minute execution. Paid exact-history acquisition remains a separate user-authorized, credit-capped preparation stage, not a hidden replay fallback.


### 2026-09-28 — Causal event replay and frozen real-execution proof demand

The initial two-case synthetic smoke passed but exposed a necessary historical-backtest design correction: a known future exit price must **never** be required to admit an earlier entry. The offline account engine now makes entry eligibility independent of later outcome/exit evidence. It accepts an explicit as-of UTC cutoff; future decisions and future entries stay in the original denominator, not silently dropped. Qualified entries debit and reserve cash immediately. If an exit is absent, after the cutoff, unqualified, or later than an option's expiry, the position remains OPEN with explicit missing-source/expiry status, its liquidity and exit-fee reserve remain locked, and **ending equity, unrealized P&L and flat-account cash-change return are NULL**. Realized P&L only sums completed modeled exits. The engine does not fabricate a zero-bid exit, intrinsic settlement, assignment or option expiration credit; stock/option clock and deliverable admission remain necessary. Tests cover incomplete exits, cutoff, unknown equity, expiry and no change in entry cash when future evidence disappears.

In the **same existing zero-provider account CLI**, `multiyear_historical_execution_requirements_v1.py` now reads the accepted signed full-case source casebook and previously signed replay-readiness result, freezes one immutable D:-bound source-work manifest for the **2,648 dated-but-unsynchronized pairs** and their first/next later option/stock observations, deduplicates exact quote observation and original native CLOSE request identities, and reports six-year blockers without dropping the remaining original 29,804 right slots. Every work item identifies original quote-body SHA, immutable request identity, observed bid/ask, provider update, exact-date native raw close, source unit SHA, and the independent clock, publication/availability, contract multiplier/deliverable, execution liquidity/cost and expiry proof still required. Provider update remains **not** publication proof; daily stock CLOSE remains **not** same-clock proof. No input may self-certify a historical fill or account return; all admission fields remain false/NULL. No new provider GET and no broad original stock corpus scan. This is **not** permission to pay for 5,296 source observations again—the historical source prices are already present; the manifest freezes what independent evidence is missing for safe account replay.

Next step: bind actual timestamped underlying trade/quote observations and independent option availability plus point-in-time corporate-action deliverables to these exact source identities, then implement genuine historical entry and exit adapters. Do not relabel synthetic cash-flow changes or EOD dates as actual 09:35 trades or reconstruct 2026 protected performance. The accepted origin-specific historical adapter must prove its inputs, not simply pass the synthetic fixture-origin flag.


### 2026-09-30 — Full exact-cache acquisition closeout, 2021 tail recovery and source refresh

The accepted exact quote acquisition completed every still-entitled original request: 3,906 new exact histories were persisted and SHA/receipt verified for 3,897 observed credits, alongside 2,229 reused original 2022 histories. The only remaining original-query gap was 487 requests whose immutable 2021-09-27 start had fallen behind the 2021-09-30 rolling Starter floor. Those requests remain immutable and are never retried with silently changed dates.

A new recovery layer derives a **separate signed clipped-tail request** only for a still-pending original exact request whose original FROM is older than the current five-year floor while its TO remains accessible. The recovery request starts at the current entitlement floor and carries the original request identity as provenance. Its raw body/receipt uses its own exact query identity in the existing D:-bound cache. Missing earlier days remain explicit; a clipped suffix can never claim original-window completeness, 09:35 availability, a historical fill or P&L. Recovery plans are deterministic for an Eastern calendar day, deduplicate identical clipped physical queries, and reuse the standard paid lock, durable pre-request intent, no-auto-retry, credit/header and storage guards.

The full-case source handoff can consume a zero-GET signed recovery overlay. A recovered case/right retains the original quote-demand ID for cohort membership but records the **actual physical recovery request ID, source FROM/TO and body SHA** separately. The observed timeline decodes each physical recovery body once, validates every returned session, and may use only two-sided observations actually present in the clipped source. The source casebook and execution-proof demand likewise bind the physical source identity; no clipped body may be mislabeled as the unavailable original full-window body.

`scripts/refresh_multiyear_sources_after_quote_cache_v1.py` performs the downstream rebuild with **zero provider GETs**: verify original/recovery local caches -> immutable recovery overlay -> fresh 29,804-right handoff -> observed option timelines -> exact native daily-CLOSE demand -> bounded local native-unit verification -> fresh source casebook -> replay-readiness census -> execution-proof demand. New quote coverage can therefore flow to the simulator without redownloading histories. Historical account P&L remains NULL until independent stock/option common-clock, as-traded deliverable/multiplier, entry/exit liquidity/cost and expiry/exercise proof gates are satisfied.


### 2026-09-30 — Reset-day multi-source acquisition orchestration

ATLAS now has a single bounded reset-day path that spends one explicitly asserted daily provider balance across the source bottlenecks in causal order rather than exhausting credits on one dataset. The orchestrator first verifies all local exact option quote receipts with zero GETs, derives and acquires only still-entitled clipped suffixes for stale 2021 exact requests, then advances the year-balanced PIT chain campaign from existing receipts. It rebuilds contract selection from those newly available local chains, freezes the rebuilt exact quote-demand plan on the original accepted research cutoff, uses the latest provider remaining-credit header to bound newly exposed quote-history acquisition, and finally invokes the full simulator source refresh with zero further provider GETs.

The cross-stage budget never increases from inference: each stage uses the lower of the operator-asserted remaining balance and the latest observed provider header. The first provider GET in each paid cache establishes headers before multiworker waves; in-flight work retains the existing two-credit reservation rule. No automatic retry is allowed for an uncertain attempt. The chain and quote workers use their existing durable intents, raw-body receipts, external D:-bound storage guards and immutable request identities.

This sequencing is designed to convert daily credits into new **PIT contract coverage plus exact quote coverage**, not merely accumulate redundant quote bodies. Native stock daily CLOSE verification, source casebook construction, replay-readiness census and execution-proof demand remain offline. Historical account P&L remains NULL until the independent common-clock, deliverable/multiplier, liquidity/cost and expiry/exercise gates are proven.


The rebuilt quote plan remains pinned to the original accepted planning as-of and last-completed-session values, so the research population cannot drift merely because the provider rolling window advances. Newly stale exact windows are handled only through separately signed clipped-tail recovery requests using the current entitlement floor.


### 2026-09-30 — Repository-root `.env` runtime credential contract

ATLAS workstation commands use the **repository-root `.env`** as the persistent local credential/configuration source. `packages/core/settings.py::load_settings(...)` calls `load_dotenv(ROOT / ".env", override=False)`; therefore scripts must load ATLAS settings **before** reading provider variables with `os.getenv(...)`. A normal operator run from the repository must not require a separate PowerShell `$env:` export when the credential is already present in the root `.env`.

This contract includes `MARKETDATA_TOKEN` for MarketData.app historical-options acquisition and `ATLAS_EXTERNAL_DATA_ROOT` for the secondary-data binding, alongside the other provider variables documented by `.env.example`. Real secrets remain local and ignored by git. Process-environment values may intentionally override `.env` because dotenv is loaded with `override=False`, but absence from the current shell is **not** evidence that the root `.env` lacks the value until `load_settings()` has run.

The reset-day multi-source orchestrator previously checked `MARKETDATA_TOKEN` before calling `load_settings()`, causing a false “not configured” stop even though the token existed in the root `.env`. That ordering defect is now regression-tested. Future orchestration/provider scripts must preserve: **find repository root -> load settings/root dotenv -> resolve credential -> perform explicit paid authorization checks -> provider access**.

Handoff/review rule for future ATLAS sessions: current code and the normative `README.md` + `docs/roadmap.md` must be reviewed before proposing workstation commands. Configuration assumptions, current merged acquisition state, D:-binding policy, immutable evidence rules, provider-credit controls and simulator authority gates must be taken from those sources rather than reconstructed from shell state or guessed defaults.


### 2026-09-30 — Additive reset-day source sweep supersedes the initial reset-day advance

The first invocation of `scripts/run_multiyear_reset_day_source_advance_v1.py` stopped before any provider GET because that new script resolved `MARKETDATA_TOKEN` before `load_settings()` had loaded the repository-root `.env`. Its targeted tests had passed (**34 passed**) but the paid path made **zero provider requests and consumed zero credits**. The credential-ordering defect is fixed and guarded repository-wide; however, the initial full-plan rebuild design is also superseded before first paid use.

The accepted reset-day path is now the **additive source sweep** in `scripts/run_multiyear_reset_day_source_sweep_v1.py`. It preserves every previously selected PIT OCC identity and every existing exact quote query/window from the accepted base selection/plan. Additional year-balanced PIT chain acquisition may make previously unselected CALL/PUT slots selectable; only those newly selectable slots are added to quote demand. Existing contract identities may not be replaced merely because more chain evidence becomes available. Newly selected 2021 slots already outside the current Starter window remain explicit source gaps with no invented full-window request.

One cumulative daily credit ceiling spans: (1) verified clipped-tail recovery for still-accessible portions of the 487 stale original 2021 exact requests; (2) year-balanced missing PIT chain snapshots; and (3) exact quote histories for newly selectable contracts. The sweep withholds a configurable portion of the daily budget from the chain stage only so newly discovered contracts can still obtain quote histories; `min_remaining_credits=0` may still allow the full operator-authorized daily budget to be used across the complete sweep. Provider headers remain the harder runtime balance after the first GET. All completed receipts are reused and no uncertain paid attempt is automatically retried.

After paid source work, the same command rebuilds the clipped-source overlay, full 29,804-right handoff, observed option timelines, targeted native raw daily CLOSE evidence, source casebook, account-readiness census and execution-proof demand with **zero further provider GETs**. Native stock stays on C:, options/news/evidence remain on the D:-bound secondary storage. Historical option P&L remains NULL; provider EOD quote timestamps are not 09:35/publication proof, native daily CLOSE is not a synchronized option clock, and deliverable/multiplier, executable liquidity/cost and expiry/exercise/assignment proof remain required.

For future ATLAS review sessions, do **not** resume from the older reset-day advance command. Review current `main`, this section, the repository-root `.env` credential contract, the latest operator output, and use the additive sweep as the sole reset-day multiyear paid orchestration path unless a later merged living-document revision explicitly replaces it.


### 2026-09-30 — Additive reset-day paid acquisition completed; offline native-2026 boundary repair

The first authoritative additive reset-day sweep completed its **paid acquisition stages** and then stopped only in the zero-provider native-stock verification stage. Operator output recorded:

- cumulative observed MarketData credits: **9,999**;
- last provider remaining header: **1**;
- verified clipped 2021 recovery overlay: **487 complete / 0 gaps / 0 pending**;
- additive exact quote cache after the run: **7,314 complete**, **2,235 reused accepted 2022 histories**, **0 exact source gaps**, **7,799 still pending**;
- the paid exact-quote stage ended cleanly at provider remaining 1 and persisted every completed body/attempt/receipt before the later offline stop.

**Do not rerun the paid sweep to recover from the subsequent error.** Those credits and source receipts are already retained on D:.

The later stop was:

`NativeEodCloseError: protected/adjusted native request cannot be read`.

Root cause: newly available 2025 option contracts can have first/next retained option-source observations in early **2026**. The accepted native-stock contract intentionally forbids opening 2026 stock outcomes. The original native-close resolver treated the presence of such a request as a fatal malformed demand instead of recording the protected boundary as an explicit source disposition.

The repaired contract now keeps an exact 2026 native CLOSE request in lineage but labels it `PROTECTED_2026_NATIVE_CLOSE_WITHHELD_NOT_READ`. No 2026 native stock unit, Parquet row, return, open or close is read. Pre-2026 native requests continue through SHA/checkpoint-verified local source reads. The source casebook exposes `OPTION_SOURCE_DATES_PRESENT_PROTECTED_2026_NATIVE_CLOSE_WITHHELD`, and replay readiness exposes `PROTECTED_2026_NATIVE_CLOSE_WITHHELD`; neither is an executable trade or an inferred price gap. `protected_2026_outcomes_read` remains zero.

The deterministic recovery command is now `scripts/continue_multiyear_source_refresh_offline_v1.py --acquisition-day-et 2026-09-30`. It performs **zero provider GETs**. It reconstructs the current PIT selection from local chain receipts, discovers exactly one additive quote plan bound to the accepted base-plan fingerprint + current selection fingerprint + September 30 acquisition day, discovers exactly one matching signed recovery overlay, verifies local quote receipts, then resumes handoff -> option timeline -> native CLOSE source -> casebook -> readiness -> execution-proof demand. If artifact lineage is ambiguous, it fails closed instead of choosing by modification time or performance.

Future ATLAS handoffs must preserve this distinction: the September 30 paid work is complete evidence acquisition, while the native-2026 repair is an offline source-classification fix. Remaining 7,799 exact quote histories are future acquisition work after another provider reset; they are not a reason to repeat already completed September 30 requests.

### 2026-10-01 — Offline source-refresh closeout and cross-day clipped-tail reuse guard

The post-#297 workstation continuation completed with **zero provider GETs/credits**.
It rebuilt the current PIT selection at **20,364 selected case/right memberships** and
bound the September 30 additive quote plan at **17,348 physical exact histories**
(6,622 base + 10,726 additive). The local exact-history census is **7,314 complete
new-cache histories + 2,235 reused accepted 2022 histories / 0 exact gaps / 7,799
pending**. The September 30 clipped recovery overlay remains **487 complete / 0 gaps /
0 pending**.

Targeted native verification completed all **1,494 / 1,494** required pre-2026 source
units, producing **14,409 exact native closes**, **13 native daily gaps** and **31
protected-2026 native CLOSE requests withheld without opening any 2026 stock outcome**.
The refreshed full casebook/readiness/proof demand reports **11,715 dated
stock+option source rights**, **24 protected-2026 withheld rights**, **22,781 distinct
option-observation proof targets**, **14,355 native-close proof targets** and
**0 historical executable option trades**. Historical option P&L remains NULL.

Before the October 1 reset-day paid continuation, review found a credit-efficiency
defect in clipped-tail recovery. A new calendar day advances the Starter rolling floor,
so the old implementation would derive a new narrower clipped query even when a
verified prior-day clipped body already covered the entire newer suffix. The recovery
layer now discovers signed prior recovery overlays and may reuse a prior physical
request only when it maps to the exact same immutable original request, the option
symbol and `to_exclusive` are unchanged, the prior `from_inclusive` is no later than
the current floor, and the prior body SHA-256 is retained. The normal quote-cache
census still re-verifies the actual receipt/body; a changed or missing body is not
silently replaced by a paid request. Original full-window completeness, historical
fill/P&L authority and the missing clipped prefix remain unchanged.

After exact-head CI and merge, the next reset-day run should prioritize clearing the
**7,799 existing exact-history backlog** while still advancing a bounded amount of new
PIT chain coverage. Do not use the old default chain-heavy reserve simply because a
new daily credit balance is available. The additive sweep remains the sole paid
orchestration path; completed September 30 receipts and prior clipped bodies must be
reused before any new GET.

### 2026-10-01 — Reset-day additive quote lineage must carry forward, never re-freeze from root

PR #298 closed one cross-day cache inefficiency by allowing an already verified
prior clipped-tail body to cover a later narrower entitlement suffix. A subsequent
pre-paid review found a broader orchestration defect that must be closed before the
October 1 provider reset is used.

`build_additive_quote_plan` already preserves every exact request/window supplied by
its base plan. The reset-day orchestrator, however, still supplied the original
September 27 7,788-selection / 6,622-query root on every day. The accepted September
30 additive head contains 20,364 selected case/right memberships and 17,348 physical
exact histories. Rebuilding all 12,576 non-root selections from the September 27 root
on October 1 would apply the newer 2021-10-01 rolling floor to them again. Floor-
sensitive 2021 requests could therefore be reclassified or receive new exact request
identities even though September 30 receipts already exist. This violates the
additive contract's immutable-window intent and risks duplicate provider spending.

The repaired reset-day path now discovers the unique signed additive lineage rooted
at the frozen September 27 selection/plan. Each child must bind the exact parent plan
fingerprint and the exact selection represented by that parent; the referenced
expanded-selection artifact is signature-checked and the child plan is revalidated
against it. Parent counts, exact request membership, selection extension and planning
day chronology are checked at every hop. A fork, missing selection, broken parent
link, signature drift or cycle fails closed. Unrelated/orphan manifests are not
selected by modification time or performance.

Before any paid stage, the orchestrator also rebuilds the current PIT selection
locally and proves it is a valid extension of the discovered carry-forward head. The
carry-forward plan—not the September 27 root—is then used for cache census and tail
recovery. After new chain acquisition, only genuinely new selected case/rights are
added; all prior exact request identities and windows remain byte-for-byte inherited.
The offline continuation entry point follows the same chained lineage, so a later
zero-provider resume no longer assumes every acquisition-day plan is a direct child
of September 27.

For the current workstation state, the expected carry-forward head before new October
1 acquisition is the accepted September 30 plan fingerprint
`90f940b2bf167a9451a3d569286ee2fc065c776a2e8df12edf9bef7e02bcbc03`,
with **17,348 physical exact histories**, **7,314 new-cache complete**, **2,235
accepted 2022 reused**, **0 exact gaps** and **7,799 pending**. The prior 487 clipped
tails remain reusable under PR #298. No historical fill/P&L, common-clock,
deliverable, strategy, PAPER or LIVE authority changes.

After exact-head CI and merge of this carry-forward repair, the next paid reset-day
run should spend from that lineage head and bias the daily budget toward the existing
7,799 exact-history backlog while retaining only bounded new PIT chain acquisition.
Do not run the paid reset-day sweep from a revision that still rebuilds additive
demand from the September 27 root.

### 2026-10-01 — Exact-history closeout and EOD snapshot/liquidity proof probe

The accepted reset-day source run completed without error at **7,297 observed
MarketData credits**, with the last provider header reporting **2,703 remaining**.
The final source partition contains **13,511 complete demand-cache exact histories +
2,235 reused accepted 2022 histories + 1,602 complete clipped recovery histories =
17,348 physical histories**, with zero exact/recovery source gaps. The 1,602 original
exact identities still shown as pending are rolling-floor-stale identities, not
missing source: the current recovery overlay covers all 1,602 (487 reused prior
covering bodies + 1,115 current-floor recovery bodies).

The refreshed casebook now contains **20,040 dated stock+option source rights**:
2,635 in 2021, 5,302 in 2022, 3,077 in 2023, 2,535 in 2024 and 6,491 in 2025.
Another 54 2025 rights require protected 2026 native closes and remain withheld.
Historical executable option trades remain **0** and historical account P&L remains
NULL.

Current MarketData documentation was re-reviewed on 2026-10-01. It documents
`updated` as the option quote snapshot timestamp and `underlyingPrice` as the last
underlying-security price at the time of that quote; historical bid/ask/volume/
underlyingPrice fields are documented as EOD values as of the row's updated time.
ATLAS previously preserved those raw fields but intentionally did not project
`underlyingPrice` into the derived timeline.

A new zero-provider V1 probe therefore reopens only SHA-verified accepted quote
bodies and measures same-row EOD stock/option snapshot shape, displayed bid/ask
size, reported volume and strict pre-expiry exit availability. The probe also freezes
the existing conservative one-contract entry-at-ask / exit-at-bid plus $1.30
round-trip fee policy for diagnostic use. It **does not** treat provider snapshot
time as independent proof of historical publication/retrieval availability, does not
verify deliverable/multiplier, and admits no trade or P&L. These remain explicit
execution-proof blockers.

The reset-day and zero-provider continuation orchestrators now emit this probe
automatically after execution-proof demand. For the already-completed October 1 run,
run the standalone zero-provider probe against the exact
`multiyear_historical_execution_proof_demand_v1_52a4830956f00c4d.json` artifact
after this change is merged. Do not spend the remaining 2,703 MarketData credits
merely to repeat source that is already complete; use them only if the new evidence
census identifies genuinely missing provider source that MarketData can supply.


### 2026-10-01 — Causal EOD standard-contract admission gate

The accepted EOD clock/liquidity probe produced **20,040** dated source rights and
**8,574** rights with both entry and later-exit EOD clock/liquidity/pre-expiry source
shape. That 8,574 count is not used as an entry population because requiring later
exit liquidity at admission would introduce lookahead.

A new zero-provider admission audit therefore rechecks the exact signed historical
chain receipt/body that supplied each dated selected OCC symbol. MarketData documents
the chain `nonstandard` parameter as defaulting to `false`; the accepted ATLAS
chain requests contain exactly `date`, `expiration` and `strike`, so they did not
opt into adjusted/non-standard contracts. The selected OCC root must also continue to
match the accepted underlying ticker. Provider documentation describes the standard
equity chain under the ordinary 100-share contract model.

The audit reports a **causal entry-ready** population using only entry-time EOD
snapshot, ask-side size/volume and provider-standard chain evidence. Later bid-side
exit liquidity is evaluated separately only when the later observation is reached.
The 100-share value is explicitly a provider-standard **modeled multiplier
assumption**, not independent OCC deliverable proof. The audit admits zero historical
trades, creates no historical account P&L authority and uses zero provider credits.


### 2026-10-01 — First receipt-bound historical EOD option account replay

The causal admission audit accepted **10,809** entry-ready dated option rights from
20,040 dated stock+option source rights. The prior 8,574 entry+later-exit intersection
is not used as an entry denominator because that would let future exit liquidity
decide whether an earlier trade existed.

A new historical EOD replay path remains separate from the synthetic fixture engine.
It preserves all 14,902 original accepted daily-LONG cases, treats CALL as the
direction-aligned primary option mode and PUT only as a counterfactual diagnostic.
Entry uses the signed causal-admission result and the exact SHA-verified 16:00 ET ask.
After entry, the engine advances through the same verified physical quote history and
attempts to sell at the **first subsequent** 16:00 ET two-sided bid with positive
displayed bid size and positive reported volume, strictly before expiration. 2026
outcomes are not opened.

An unresolved exit is not removed from the cohort: the position stays open/unmarked
and continues consuming cash, reserved exit fee and account capacity. The account
model is cash-only, defaults to $100,000 initial cash, 10% available-cash allocation,
five open positions and $0.65 per-contract entry/exit fees. Provider-standard
100-share treatment remains an explicit modeled multiplier assumption; independent
OCC deliverable proof remains false. Completed round trips may report modeled EOD
realized P&L, but historical fill/account-P&L authority, strategy promotion, PAPER
and LIVE authority remain false.


### 2026-10-02 — First real-data EOD option account replay completed

The first receipt-bound historical EOD option replay completed over the immutable
2021–2025 source set with zero provider requests. The scenario contained **10,809**
causal entry-ready option rights; **10,696** found a later qualified liquid EOD bid
and **113** did not.

The direction-aligned CALL account saw 5,785 source-entry-ready cases, admitted 345
positions under the initial five-position/10%-cash model, completed 343, ended with
two unresolved positions and $182.05 cash, and realized modeled P&L of -$99,108.00.
The PUT counterfactual admitted 442, completed 439, ended with three unresolved
positions and $304.15 cash, and realized modeled P&L of -$99,443.90.

These results close the first real-data option account-plumbing diagnostic only. The
exit rule in that V1 replay was the first subsequent qualified liquid EOD bid, not
the stock strategy's STOP/TARGET/TIME exit. Therefore the near-total modeled cash
loss is **not strategy evidence** and does not change promotion, PAPER or LIVE state.

The next replay binds CALL exits to the frozen stock strategy exit **session** for the
unchanged 2%/5% and 3%/5% candidate policies. Because historical option observations
are EOD, STOP/TARGET touch time remains unavailable: the option exits at the EOD bid
of that stock exit session. Cases whose stock exit occurred before or on the first
admissible option EOD entry are not option trades; exact-session option source gaps
remain unresolved rather than sliding forward.


### 2026-10-02 — Static strategy-session option controls completed; dynamic replay next

The stock-strategy-session-aligned static CALL controls completed with zero provider
GETs. Under STOP 2% / TARGET 5%, 1,493 cases had exact strategy-exit-session option
source ready; under STOP 3% / TARGET 5%, 2,055 were source ready. Exact-exit-source
gaps were 345 and 459 respectively. In both strict account replays, ten unresolved
positions accumulated early and permanently occupied the 10-position ceiling, causing
1,701 and 2,328 maximum-concurrency rejections. These account outputs therefore
primarily measure the conservative unresolved-source policy, not five-year strategy
performance.

The next option gate uses the existing Dynamic Exit V1 selector rather than one
static stop/target pair. Dynamic choices are rebuilt only from completed prior folds
through the safe 2025 boundary; current-fold outcomes and all 2026 outcomes remain
forbidden. The runner reports both (1) the same strict causal account and (2) a
separate paired-observation diagnostic over every dynamically selected case that has
both an admissible EOD entry and exact strategy-exit-session EOD bid. The paired
diagnostic is explicitly conditional on future exit-source availability and is not a
causal portfolio result.


### 2026-10-02 — Dynamic Exit V1 option replay completed; Continuous V2 preregistered

Dynamic Exit V1 completed over the bounded 2021–2025 option cohort with zero provider
GETs. It selected **354 / 14,733** eligible cases (**2.40%**), chose only the
`STOP_03_TARGET_05` action, and all selected cases occurred in 2025. The resulting
93 exact source-ready CALL pairs had mean modeled return on premium -11.56%, median
-19.30%, probability positive 27.96%, and mean modeled P&L -$63.91 per contract.

The strict account admitted 29 positions, completed 26, retained three unresolved
positions and ended with $58,622.05 cash; ending equity/return remain NULL. This V1
result remains diagnostic only and shows that the selector is too abstention-heavy
and too coarse to serve as the final ATLAS exit engine.

Continuous Dynamic Exit V2 is now preregistered to separate entry selection from exit
parameterization. Every eligible accepted LONG case receives case-specific stop/target
levels from strictly-prior training-cell MFE/MAE and return quartiles, bounded inside
the already researched 1–3% stop / 2–5% target envelope with minimum 1.5x
target-to-stop. Current-case/current-fold outcomes and option exit evidence are not
inputs to the level calculation.

## 2026-10-02 — Continuous Dynamic Exit V2 closes exit-geometry tuning; entry-clock fidelity next

The first workstation Continuous Dynamic Exit V2 run completed with zero provider GETs
and zero protected-2026 outcome reads. Across 14,733 usable daily-LONG cases, the stop
distribution was effectively pinned to the frozen upper bound (P25/median/P75 3.00%,
mean 2.9986%) and the target was exactly 5.00% for every case. The 2,055 exact-session
source-ready CALL pairs had modeled mean/median premium returns of -14.06%/-18.42%,
30.61% positive, and mean modeled P&L -$75.01 per contract. The strict account
completed 74 positions, retained ten unresolved positions, and reported modeled
realized P&L -$33,365.40; ending equity/total return remain NULL.

This closes the current exit-geometry branch. Do not create V3, widen bounds, weaken
causal rules, or retune another exit formula from the same DEVELOPMENT outcomes.
A separate zero-provider closeout now measures the more material trade-expression
problem exposed by the run: 3,230 cases had already reached the stock strategy exit
session by the time the accepted historical EOD CALL entry was available. The next
gate quantifies decision-to-option-entry session/time lag, underlying movement and
moneyness migration before option entry. Underlying alpha and option expression must
be evaluated separately before any further option-performance interpretation.

Detailed closeout:
`docs/research/continuous_dynamic_exit_v2_closeout_20261002.md`.

## 2026-10-02 — EOD option performance interpretation closed; intraday stock-exit clock next

The immutable EOD entry-clock closeout established that the current historical EOD
option replay does not preserve the original 09:35 stock/option decision clock.
Among 5,785 causal EOD CALL entries, 3,230 (55.83%) became available only after the
stock strategy had already reached STOP/TARGET/TIME. Median delay was one exchange
session / 30.42 hours, median absolute underlying movement before option entry was
2.32%, and CALL moneyness classification changed in 35.96% of cases.

Case-level joining also showed mechanical survival selection: 75.36% of STOP exits
and 57.55% of TARGET exits occurred before/not after EOD option entry, versus only
0.96% of TIME exits. There were zero source-ready paired observations once the
underlying had moved at least 5% before the delayed EOD entry. Therefore the paired
EOD option return distribution remains a valid descriptive result for its exact
future-source-conditioned sample, but it is not interpreted as performance of the
intended 09:35 option strategy.

ATLAS already owns accepted Alpaca SIP raw 1-minute stock history sufficient to
resolve the stock-side exit clock. The next zero-provider gate is
`multiyear_intraday_stock_exit_clock_v1`: resolve STOP/TARGET to the first causal
one-minute boundary event, use the official exchange close for TIME exits, identify
trades already finished at/before 09:35, and emit the exact future at-time option
NBBO demand plan. No option provider is read by this gate.

Detailed forensic closeout:
`docs/research/eod_option_entry_clock_forensics_v1_20261002.md`.

## 2026-10-02 — Intraday stock exit clock accepted; 09:35 contract clock correction

The zero-provider intraday stock-exit clock completed over 9,974 pre-2026 CALL/policy
cases using accepted Alpaca SIP raw 1-minute source. It resolved 9,667 cases (96.9220%)
to a causal option-expression window after the planned 09:35 decision; 304 stock
trades had already exited at or before 09:35 and three STOP/TARGET cases retained a
minute-trigger gap. Minute ordering changed the older daily STOP/TARGET disposition
in only 51 cases (0.5113%). No provider request or option outcome was read.

A final entry-side clock mismatch was identified before paid intraday option
acquisition: the provisional structural CALL symbol had been selected nearest-ATM
against the native stock open, while option expression is decided at 09:35 ET.
Therefore the previously emitted 18,921 exact single-contract quote demands are not
treated as final acquisition authority.

The replacement zero-provider gate is
`multiyear_option_decision_spot_v1`. It binds the last completed accepted stock
minute causally available at 09:35, measures open-to-decision movement and baseline
strike drift, and emits provider-agnostic CALL candidate-surface demand by
underlying/date/decision clock. Strike and expiration remain unselected until causal
option quotes can be evaluated by the existing option-economics/trade-expression
layer. Exact option exit source demand is second-stage after entry contract selection.



## 2026-10-03 — 09:35 decision spot accepted; ThetaData surface qualification next

The corrected zero-provider `multiyear_option_decision_spot_v1` workstation run
completed after PR #311 fixed the Eastern-time binding. It verified/read all 5,315
target minute bindings and resolved a causal stock decision spot for **9,654 / 9,667**
option-expressible cases (**99.8655%**). Thirteen cases remain explicitly missing a
completed regular minute available at the 09:35 decision; they are not imputed.

The open-to-09:35 absolute move had median **0.4660%**, mean **0.6562%**, P90
**1.5422%** and maximum **4.8678%**. **22.81%** of ready cases had moved at least 1%
from the raw open, **4.46%** at least 2%, and **0.89%** at least 3%. The old
open-selected structural CALL was ATM in only 54 cases at 09:35; 4,899 were ITM and
4,701 OTM, with median absolute strike distance **1.4266%**. This confirms that the
entry-contract clock correction was material and that the obsolete 18,921
single-contract request set must not be acquired.

The accepted output replaces that set with **9,455 unique provider-agnostic
underlying/date/09:35 CALL candidate surfaces** covering the 9,654 ready cases.
No option provider, option price or option outcome was read.

The next source gate is
`thetadata_candidate_surface_source_plan_v1`. ThetaData Options Standard is the
current provider candidate. Current official retail documentation observed for this
gate lists $80/month, ten years of data, four concurrent requests, tick-level data,
option-chain snapshots and every OPRA NBBO quote. The v3 at-time quote endpoint
supports `expiration=*`, `max_dte` and all strikes at a minute-boundary clock, so
ATLAS can qualify one bounded 09:35 surface per underlying/date without preselecting
an OCC.

The qualification stage remains outcome-blind and read-only. It freezes deterministic
2021–2025 anchors, persists raw response/receipt evidence, validates timestamp and
contract-surface semantics, distinguishes explicit no-data from entitlement/transport
failure, and repeats a 2021 surface for deterministic historical replay. Full 9,455
surface acquisition remains locked until that source gate passes. Contract selection,
historical open interest, local IV/Greeks, exact selected-contract exit quotes,
historical-fill authority, strategy evidence, PAPER and LIVE remain downstream.


## 2026-10-03 — ThetaData quote/OI enrichment path frozen before provider reads

The accepted 09:35 quote-surface plan remains immutable. A separate zero-provider
enrichment contract now maps each of the 9,455 quote surfaces to one historical
open-interest surface request using the same underlying/date, CALL-only, all
expirations/all strikes and max DTE 75.

Open interest is treated as previous-session state: ThetaData documents OPRA OI as
normally reported around 06:30 ET and representing the prior trading day's closing
open interest. The source qualification therefore requires OI timestamps to be on the
decision date and no later than the 09:35 option decision.

Greeks are intentionally deferred until quote + OI evidence has applied the frozen
Phase13 DTE (14-45 days), spread-to-mid (<=15%) and open-interest (>=100) screens.
Only expirations containing survivors are eligible for a Greeks request.

For those expirations ATLAS targets ThetaData Standard's historical first-order
**binomial** Greeks endpoint, bounded to the exact 09:35 minute, CALL only, all
strikes, 1-minute interval, version 1, 101 Leisen-Reimer tree steps and SOFR rate
type. Historical annual dividend amount is an explicit required PIT input; missing
dividend context blocks authoritative Greeks rather than silently assuming zero.

The first live provider source gate is now one bounded runner:
`qualify_thetadata_candidate_source_pipeline_v1.py`. It performs at most 32
read-only requests: 15 quote anchors plus one deterministic 2021 repeat, followed
only after quote success by 15 matching OI anchors plus one deterministic 2021
repeat. Full quote/OI acquisition, Greeks, contract selection, exact exit pricing,
historical P&L, strategy evidence, PAPER and LIVE remain locked.


## 2026-10-03 — ThetaData Terminal zero-data preflight

Before the first live ThetaData source qualification, ATLAS now requires a local
zero-market-data preflight. The preflight validates:

- Java 21 or newer;
- the loopback-only Theta Terminal listener at 127.0.0.1:25503;
- whether a local authentication source is observable via THETADATA_API_KEY,
  terminal .env, or terminal creds.txt;
- the immutable quote-surface plan and enrichment plan signatures and linkage.

The preflight opens only a local TCP socket and does not call a ThetaData HTTP/data
endpoint. It deliberately does not inspect running process command lines because a
Terminal may have been launched with an API key argument and process inspection could
expose the credential.

A reachable Terminal plus Java 21+ and valid ATLAS plan linkage is sufficient for
preflight readiness. Provider entitlement/schema is still proven only by the separate
bounded read-only quote/OI qualification gate.


## 2026-10-03 — ThetaData transport correction: direct Python library, no Terminal

ThetaData released a direct Python library in 2026 that connects to ThetaData over
HTTPS/gRPC and does **not** require Theta Terminal or Java. ATLAS therefore supersedes
the previously staged Terminal/localhost REST transport before any provider data was
requested.

The accepted scientific/source manifests are retained unchanged:
- quote-surface plan `acc9525a2930fe39`;
- enrichment plan `181645c252fc46f4`.

Their request geometry, causal clocks, DTE bounds, quote/OI staging and downstream
Greeks policy remain valid. The original source-plan field
`terminal_required=True` is retained only as immutable lineage metadata from the
transport assumption at plan-freeze time; it is not an active runtime requirement.

Active provider transport:
- pinned provider package `thetadata==1.0.12`;
- a dedicated `.provider_venvs/thetadata` Python >=3.12 environment;
- a persistent ATLAS worker process per acquisition thread;
- direct `ThetaClient(dataframe_type="pandas")` calls inside that isolated worker;
- direct methods `option_at_time_quote()`,
  `option_history_open_interest()`, and
  `option_history_binomial_greeks_first_order()`;
- API-key authentication via `THETADATA_API_KEY` or supported ThetaData credential
  discovery;
- no Java, JAR, localhost port or Theta Terminal.

The provider environment is intentionally isolated rather than installed into the
core ATLAS venv. ThetaData 1.0.12 requires `protobuf>=6.32.1`, while the accepted
Webull SDK requires `protobuf<6` on Python >=3.12. ATLAS will not resolve a
market-data dependency by changing a validated broker/runtime dependency.

Provider evidence receipts preserve a canonical JSON serialization of the returned
provider DataFrame together with provider method, transport, library version and a
fingerprint of the isolated provider dependency stack (ThetaData/protobuf/gRPC and
related serialization/network packages). They must not claim wire-level/raw HTTP bytes
because the direct library does not expose them.

`scripts/setup_thetadata_python_env_v1.py` creates/validates the isolated provider
environment without making a market-data request. The obsolete Terminal preflight
remains only as a compatibility shim that exits with a superseded message. The active
readiness gate is `scripts/preflight_thetadata_python_library_v1.py`, and it also
performs zero provider requests.
