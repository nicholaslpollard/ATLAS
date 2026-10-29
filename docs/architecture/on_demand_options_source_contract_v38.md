# ATLAS invariant: demand-driven historical data for every strategy revision

## Product requirement (2026-10-28)

A change to strategy parameters, eligible universe, contract selection, risk schedule, entry time, dynamic exit, or model features may produce **new trading opportunities not present in any earlier frozen research plan**.

ATLAS **must generate data requests from the current strategy's actual input demand**. It must not use a fixed SPY pilot, previous 361 selected option pairs, arbitrary lifetime count of API calls, hard-coded candidate quota, or a single "initial download complete" flag as a reason to suppress new requests.

The required behavior is:

1. Determine the strategy version, requested event clock, contract identity and exact provider source query. Do not select contracts using future quote/return outcomes.
2. Read the persistent local historical-source registry first. Reuse a verified **exact matching** source instead of issuing the same paid request again. A nearby expiry, different quote time, earlier data source, or different parameter set is not interchangeable.
3. For a verified cache miss, **automatically issue the necessary provider read-only historical request** through the isolated ThetaData SDK. There is no manual authorization prompt per request.
4. Preserve the original response, query identity, source SHA-256, compressed archive and indexed provenance **before** returning it to the strategy. Explicit no-data responses must be recorded separately from errors and unqualified empty results.
5. A new strategy parameter set creates new exact query identities and new cache rows. Reuse newly cached responses across later simulations and even different strategy families. Unknown or failed sources must not silently become complete coverage.
6. Support ongoing requests, partitioned batches, and resume across restarts. Do not set an artificial total number of provider GETs or total candidate contracts. Native request/window sizes, provider entitlements and physical storage availability still constrain individual calls; chunk large requests instead of discarding needed research work.
7. Only chronologically **available** observations may influence strategy entry/exit decisions. A historical source retained in 2026 does not prove it was historically available at 09:35 or 10:00 ET. Retrospective quotes do not count as broker fills, nor do inferred expiry assumptions count as settlements.
8. When provider service, supported API semantics, or physical disk prevents a query, make the blockage **visible and resumable**; never fabricate a response, treat a missing mark as zero without an explicit separately labeled stress policy, or pretend the simulation fully covered its opportunity set.

## V38 implementation (first integration piece)

\`packages/data/options_on_demand_source_cache_v38.py\` implements one **read-through, source-only** API: \`read_through_historical_options(settings, method, kwargs)\`.

It supports the existing read-only ThetaData client methods: exact and broad at-time option quotes; hourly quote surface; historical open-interest surface; and 101-step binomial first-order Greeks. New \`kwargs\` produce new cryptographically keyed identities. The handler first checks a SQLite index and immutable compressed JSON archive under the existing external **options** binding. On a miss it calls ThetaData, checks canonical source bytes, stores losslessly compressed original provider rows and their SHA-256, updates the index and returns. Explicit provider no-data is indexed. Identical future requests use local data; different strategy versions can share the exact query key. Failed transient GETs can be retried by a future request; in-flight protection avoids duplicate concurrent requests.

**No total-call or candidate-set limit exists in V38.** Per-response 24 MiB, maximum row count and minimum physical disk headroom guard are resource/integrity protections, not a static strategy universe. The helper deliberately does not assert PIT feature acceptance, order execution, or actual strategy performance.

## Important integration work still pending

- **Use V38 from the production historical strategy runner.** V38 alone is the source gateway, not a simulator scheduling integration. Strategy candidate generation must call it for each missing exact source, including newly selected contracts and dynamic review clocks. Develop a reusable pending/replay queue that resumes temporarily blocked jobs without dropping opportunities.
- **Unify older source indexes:** archived V30 exact-right receipts and V6 compressed historical hourly sources predate V38. Add compatible lookup/verified import bridges so on-demand requests reuse these receipts before requesting the same source again. Existing V30/V6 sources must remain immutable and retain their original diagnostic qualification.
- **Provider specialization and account simulation:** wire actual PIT SPY 20-return volatility, previous-session OI, historical rate/dividend and American IV; do not infer these from pair premium. Once prior information and executable 10:01 options evidence is qualified, schedule new source needs for any changed strategy entry/exit rules and replay account chronology.

### Consequence for research process

Frozen research plans remain useful for reproducibility. **Freezing a research cohort never freezes the system's ability to acquire newly demanded data**. New strategy runs must get a new strategy version/fingerprint and should obtain missing compatible historical sources automatically. One account simulation's incomplete coverage must be reported, not silently treated as an unfavorable trade or global acquisition endpoint.

## V42 operational observability requirement

Long source acquisition and strategy runs with a known denominator must display **ET timestamped progress once per 10% completed**, including completed/total, actual API attempts, cache/archiving/no-data/failure counts, elapsed time, throughput and rough observed ETA. Do not require 15-second heartbeat messages or separate progress logs. Completed source receipts and lineage remain persisted for recovery. There is no artificial lifetime provider-call limit or frozen candidate roster; finite provider, source-schema and disk safeguards continue to apply. [Full operating requirements](atlas_living_operating_requirements_20261029.md).
