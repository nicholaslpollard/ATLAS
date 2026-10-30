# V49 — Every-options-opportunity audit trail and delayed-action quote policy

**2026-10-30 specification and offline implementation; NO changes to the frozen SPY options strategy, V43/V44/V45 source admission, V46 non-PIT hypothetical signal, V47 exits, or their results.**

## Why this milestone exists

The user requires ATLAS to preserve **every meaningful consideration for every prospective trade**, including failed and skipped opportunities and their precise underlying measurements, while examining whether an alternative **three-second** CALL/PUT quote synchronization window could address asynchrony. The user also proposed checking the price difference between decision and action rather than blindly accepting an old quote.

We inspected immutable V47 `spy_v47_exits_20261030_123519.json`: **18/530** candidate exit observations were censored for CALL/PUT timestamp differences over one second. **14** of those measured mismatches were >1 and <=3 seconds; **four** exceeded three seconds. Those 14 are *potential skew-only review cases*, **not** newly qualified quotes, fills or profitable trades. One separate quoted exit failed the still-valid relative spread threshold (**19.52% vs 15%**), and one exit pair is unpriced because of two ThetaData SDK-worker ValueErrors (same 2020-05-01 date). Do not infer that a widened skew rule remedies either issue.

## Three distinct clocks; three independent quality gates

1. **Signal clock** 10:00 ET: the entry decision can read only originally timestamp-qualified predecision facts, in this example 09:59 option quote observations, 09:59 underlying, prior-20 return evidence, as-of available OI/rate/corporate action news. **NEVER** let the later 10:01 bid/ask change the 10:00 forecast or strike/expiry selection.
2. **Order-reference clock** 10:01 ET: the expected one-call+one-put debit uses same original contract identity, each leg's quote age (<=30s), bid/ask/sizes/spread (<=15%), independent quote publication qualification, and paired source timestamp skew. **Original baseline <=1 second remains unchanged.**
3. **Delayed action clock** 10:01:01 / 10:01:02 / 10:01:03 ET when independent historical quote tapes exist: require independently observed, as-of available bid/ask for BOTH original contract rights at the delayed action time. Calculate *actual* action delay, each leg's quote age/spread/sizes, CALL/PUT skew, same-leg bid and ask drift, combined pair ASK debit drift. **No fill guarantee** merely because a quote passes. Missing later quotes mean UNKNOWN/REJECT, never a fabricated no-price-movement fill.

**A CALL's quote price and a PUT's quote price are not the same contract.** Do not compare them as a discrepancy. CALL-vs-PUT *timestamps* are compared for synchronization. Historical price drift is compared for CALL vs its own earlier CALL, PUT vs its own PUT, and the two-leg package cost versus its own earlier cost.

The available V45 quotes measure **09:59→10:01, a two-minute interval**, not a realistic 1–3 second broker latency. That separate measurement may reveal pair premium changes but **cannot stand in for** delayed 10:01:01–10:01:03 price data. V49 explicitly labels it and refuses to assume unobserved action prices.

### Predeclared diagnostics, not a policy optimization

- Side-by-side baseline **1s** and separate **3s** CALL/PUT timestamp-skew review, using unchanged positive size, <=30s quote age, <=15% spread and exact source requirements.
- Independent maximum *adverse* paired-ASK debit increases **0.5%, 1%, 2%**, not limits on each arbitrary right's raw price and not new alpha; improvement in usable coverage does not establish more realistic fills.
- Reject future timestamps, out-of-order snapshots, invalid two-sided markets and unqualified missing/sparse quotes. Future action price tape must carry explicit matching per-right `contract_identity` (including original expiry/strike/right) and original query/SHA provenance; a quote on a different contract is a reject, even if its price happens to look comparable.
- Never retrospectively choose 1s or 3s or a price band by the observed 2018–2025 V47 returns. Keep original-vs-alternate strategy versions separated, and require unseen prospective/held-out evidence for a new policy.

**Additional pre-execution observation (not fill evidence):** Among 339 V45 source cases with a recorded pair on both clocks, 13 original predecision 09:59 pairs had CALL/PUT quote skew strictly above 1s but at most 3s. The already-qualified 106 V46 hypothetical LONGs had observed 09:59→10:01 paired-ASK price drift median approximately **-0.01977%**, with **1/106** adverse paired-ASK price increases above **0.5%**, **0/106** above **1%**, and **0/106** above **2%**. These are within-two-minute price changes, not measured order-routing/acknowledgment delay or executable fill costs. Non-hypothetical dates are retained without outcomes.

## V49 initial audit: all evaluated cases, not just trades

V49 is a reproducible offline **source-fingerprint-pinned** derived report from three already completed workstation reports:
- `data/research/spy_v45_two_clock_20261030_111449.json`
- `data/research/spy_v46_provisional_20261030_115607.json`
- `data/research/spy_v47_exits_20261030_123519.json`

It preserves a complete source-linked trace for **361** original selected weekly candidates, covering source-eligible and source-rejected days, **hypothetical** model abstains and robust long signals. It carries the V45 original/alternate identity and all present source reasons, OI and quote timestamp/age/size/spread/bid/ask and provenance; all V46 assumed rate, dividend, call/put IV and prior raw-vol scenarios; V47 observed 1–5-session exit per-case quote/P&L/censor states only for the 106 hypothetical LONGs; and the 30 separately labeled account-scenario event entries. Fields that did not happen/are not proven remain explicit NULL. It never fabricates 255 historical outcomes for no-trade decisions.

The original historical 411 frozen decision dates included **50 initial selections that abstained** before V45's 361-case data; the three reports do not contain per-date identities for those 50. V49 keeps the 411/361/50 denominators and **does not invent rows**. Future integrated simulator must log these preselection abstentions individually at the time of discovery, plus reasons. The V49 event records are explicitly hypothetical and do not represent a historical live or paper execution.

**Auditable append-only artifact now implemented:** The same V49 CLI also creates a NEW sibling `.jsonl` journal (manifest + one complete event for each of 361 evaluated cases + closeout = **363** records). Every record includes its chronological sequence, unique event identity, prior-record SHA-256 and its own canonical SHA-256; file writes are flushed/fsynced, and the resulting chain is re-read and verified. Truncated, altered, repeated or existing journals fail closed. It retains complete per-opportunity source provenance, reasons and contextual observations but references existing underlying archives via SHA rather than rewriting raw chains. The V49 journal is an **offline derived research journal**; future live simulator execution must append observed order/ack/partial/cancel/fill/exit/mark/account events using this same audited-event principle.

Code: `packages/simulation/options_opportunity_trace_v49.py` with `build_trace`, `clock_gate`, `same_contract_two_clock_drift`, and `execution_action_diagnostic`. The last function is a future input seam: it can analyze **supplied** delayed reference/action quote packets but does not fetch or interpolate them.

## Required simulator logging contract for the next integrated development

A complete simulator must persist **one attempt/decision record for every discovery clock**, including no-signal/no-data days, PLUS an append-only event stream for each evaluated candidate. Recommended schema and status values:

| Required layer | Persist every available point, including failures |
|---|---|
| Opportunity context | unique decision ID, strategy/version+frozen fingerprint, symbol, session, venue, timezone, account and portfolio state, experimental policy identity, run/fold/training boundary and model version |
| Candidate selection | all considered underlyings/contracts, expiration/DTE/strike/right, candidate ranks and ties, excluded candidates with all gating reason codes; no outcome-informed re-selection |
| As-of provenance | raw source query ID + gzip/SHA, contract/OPRA series identity, provider/source versions, actual observation and known/published timestamps, retrieval clock, freshness/age, corporate actions as published, rates/OI/deliverable and prior return chain |
| Signal/risk | feature values and provenance, IV/growth/forecast/variance computations, model assumptions, spread/size/OI/liquidity, cash/margin limits, available buying power, one-slot/position conflicts, rejected or passed signals and ALL reason codes |
| Latency and price | 09:59 predecision and 10:01 order reference snapshots, per-right timestamps/skews/ages, decision→order clock, independent action/ack/fill timestamps if any, per-leg and pair ask drift, any price caps, vendor/source gaps, action-quote censoring |
| Lifecycle and economics | order intent/limit/size, accepted/rejected/partial/cancelled events, fill receipts if ACTUAL (else modeled), fees/slippage, entry reserves/settlement, each exit trigger considered and why fired/not, assignment/expiry risk, position marks and missing marks |
| Sequential accounting | each trade's cost basis, gross/net realized and unrealized P&L, occupied capital, any open/unresolved exposure, account equity when knowable, interval drawdowns, calendar week/month/year aggregates and folds with explicit completeness |
| Negative and exceptional evidence | quote/signal/no-contract/no-OI/no-volume/unknown-period errors, any broker/provider error stages, retry state, incomplete source, postponed order, rejected rule, censored exits, timeouts and safe stop reasons |

**Preservation rules:** write structured JSONL decision events into a dedicated per-run append-only journal, plus compact SQLite/parquet indexed summaries for queries. Store raw market data once by immutable SHA and reference it rather than duplicating large option chains in the trace. Include run manifest and checksums, stable source-to-trade linkage, checkpoint/resume and unique event IDs for idempotence. Never rewrite an older decision, erase rejected candidates, overwrite a completed experiment, silently coerce unknown P&L to zero or log provider secrets. Both structured original reason codes and human-readable reason descriptions should survive.

V49 supplies the **offline SPY evidence trace and a tested quote comparison primitive**, NOT the entire future production journal writer or broker fill gateway. Reuse ATLAS's existing `packages/simulation/decision_record.py` for stock-versus-option decision lineage and `packages/simulation/options_native_pair_account_v1.py` for separately labeled synthetic per-leg receipt accounting; extend and integrate under a versioned real simulator rather than replacing established modules.

## Workstation run after verified merge

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
    if ((git branch --show-current).Trim() -ne 'main') { throw 'ATLAS must be on main' }
    if (@(git status --porcelain --untracked-files=no).Count -gt 0) { throw 'Tracked changes present' }
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
    $v45 = 'data/research/spy_v45_two_clock_20261030_111449.json'
    $v46 = 'data/research/spy_v46_provisional_20261030_115607.json'
    $v47 = 'data/research/spy_v47_exits_20261030_123519.json'
    foreach ($p in @($v45,$v46,$v47)) {
        if (-not (Test-Path $p)) { throw "Missing retained report: $p" }
    }
    $output = "data/research/spy_v49_opportunity_trace_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    & '.\.venv\Scripts\python.exe' -m scripts.run_options_opportunity_trace_v49 `
        --v45 $v45 --v46 $v46 --v47 $v47 --output $output
    if ($LASTEXITCODE -ne 0) { throw 'V49 source-linked trace failed; preserve console output' }
    Write-Host "V49 complete: $output"
}
```

Zero provider/broker calls. The command creates **both** the new fingerprinted `.json` report and matching hash-chained `.jsonl` opportunity journal. The resulting trace is a development audit; it does not need to be rerun when the integrated simulator adds real-time later quote capture. The repository work order must explicitly make future fully integrated simulator traces a launch-readiness gate.
