# V39 — Historical strategy-data demand, dynamically resolved at runtime

## Behavior

The simulator must NOT promise in advance that provider calls will be absent. For every new strategy revision, entry candidate, source requirement, changed contract, review timestamp, or dynamic exit, ATLAS evaluates the exact source requirement **when that requirement arises**:

- Already stored and verified: return the immutable cached original source and record the new strategy/candidate use.
- Missing locally: **automatically execute the supported historical ThetaData read**, verify/retain the original provider rows in the persistent compressed archive, index the receipt by exact method+arguments, and record which strategy/candidate used it.
- Explicit provider no-data: retain that distinction and leave the simulation's input unresolved. Provider error/physical storage interruption: persist a retryable request and fail or continue only with explicit unresolved-coverage status.
- New parameters / newly selected opportunities: construct new exact query fingerprints, so no earlier frozen set of options, SPY cohort, date window, strategy ID, or supposed lifetime call cap suppresses a request.
- Requests are serviced through a streaming generator. There is no arbitrary total number of candidates or source queries. Each individual result must still meet source/schema bounds, physical storage headroom, provider entitlements and platform rate limits.

The source resolver is independent of the research's *causal input admissibility*. Source rows may only become decision inputs if historical observed/available times, corporate actions, and option bid/ask/OI/IV provenance actually qualify. Raw historical quotes do **not** represent real executed trades.

## Implementation

`packages/simulation/strategy_options_source_runtime_v39.py` exposes:

```python
resolve_strategy_source_demands(
    settings,
    strategy_version="research_spy_variant_4",
    demands=generate_current_strategy_source_needs(),
    on_source=handle_verified_source_before_decision,
)
```

Each generated demand is an exact one-query record:

```json
{"candidate_id":"SPY-2025-06-09-605-call","purpose":"entry","method":"option_at_time_quote","kwargs":{"symbol":"SPY","date_et":"2025-06-09","expiration":"2025-06-20","strike":"605","right":"call","time_of_day_et":"10:01:00.000"}}
```

New source needs may be generated after processing an earlier source. Every query uses V38's exact-key, shared, immutable archive and SQLite metadata. A second `strategy_version` with the same query automatically reuses its archived data; a different `strike` or `date_et` automatically initiates a new source request if missing.

The coordinator writes a durable `strategy_source_uses` lineage table in the same SQLite cache, linking strategy revision, candidate, purpose and source query. Re-running a partially interrupted strategy's generator reconciles and reuses completed queries, and retries demand whose previous acquisition failed.

`scripts/run_strategy_options_source_runtime_v39.py` supports a newline-delimited JSON stream produced by a strategy research runner:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_strategy_options_source_runtime_v39 --strategy-version research_spy_variant_4 --demands-jsonl data/research/current_strategy_source_demands.jsonl --output data/research/strategy_source_resolution.json
```

The tool reports **actual** provider dispatch attempts after processing, including failed calls, plus new archived receipts, local cache hits and unresolved demands. There is deliberately **no flag requiring the number of provider calls to be zero** and no preflight claim that future source access will be unnecessary.

## Scope still to integrate

This is the reusable **simulator-facing source resolver**. The existing V34/V36 retrospective quote-account programs and V37 pretrade report do not yet generate the full true historical SPY variance/IV/OI/10:01 executable order stream through V39. The immediate follow-on is to wire real historical candidate/exit generation to the resolver and verify time-qualified inputs before producing actual trade/account P&L. Need an adapter to recognize earlier V30 and V6 archived sources before reissuing equivalent old provider requests. A zero-provider off-line report builder must never imply that the overall simulator is forbidden from calling providers on new requirements.

**Do not use this as an authorization to trade live, as permission to forge missing quote/settlement events, or as independent historical strategy qualification.**
