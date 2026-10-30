# ATLAS V50 — chronological two-long-option quote-reference simulator and complete lifecycle journal

Date: 2026-10-30. Research artifact, source adapter and runtime foundation. It is **NOT** a validated historical strategy backtest, independently certified point-in-time dataset or a broker execution engine. It deliberately consumes no ThetaData capacity and does not disturb original V37–V49 pilot data or results.

## Why this is a substantive simulator integration

The user needs to review all potential trades and the reasons they were taken/rejected, and compare one-second vs three-second CALL/PUT quote synchrony and observed adverse price movement during action latency. V49 retained 361 original pilot source decisions and provided an immutable observation journal; V50 is the **strategy-neutral chronological trade lifecycle** that integrates the V49 actual-action quote gate, source-availability checks, account risk and dynamic exits, preserving the decisions for **every** opportunity.

### Core engine

`packages/simulation/options_pair_chronological_runtime_v50.py`, exported function `replay_pairs(cases, ...)`.

1. Takes a chronological list of opportunities, each with immutable candidate/original CALL and PUT contract identities, signal status `ENTER_LONG_PAIR`, `ABSTAIN` or `REJECT`, source context, model/strategy version and explicit decision time.
2. For every date, evaluates already-open exits chronologically **before** a later discovery. Records every evaluation and preserves one-slot capital constraints.
3. A proposed entry must have an independently supported **feature availability timestamp at or before** signal time and an explicit caller-provided causal-qualification flag. This flag alone is not independent source proof. The V46 historical scenario-based raw-return features are explicitly non-PIT, therefore **MUST NOT be marked qualified**.
4. Requires independently supplied option quote observations at **both order and action** time, not interpolated price quotes. For each original right, requires original contract identity, observation timestamp, first-known/available timestamp, query and archive SHA provenance, quote age <=30s, positive bid/ask and sizes, bid<=ask, relative spread <=15%, and accepted cross-leg quote skew. Calls the existing V49 `execution_action_diagnostic` for the additional delayed-action same-contract price movement/synchrony checks.
5. Explicit original baseline CALL/PUT timestamp skew **<=1 second** and separately labeled **<=3 seconds** scenario; price-drift thresholds for max *adverse change in pair purchase ASK debit* **0.5%, 1%, 2%**. The engine never chooses a threshold retroactively on 2018–2025 P&L. These are source-quality/latency hypotheses, not evidence of real fill probability.
6. One paired position at a time, debit capped by original cash risk fraction (default **5% of current model cash**), $100 option multiplier and explicit $0.65 per contract per side. Each order accepted/rejected/no signal emits `OPPORTUNITY_DECISION`; accepted quote-reference entries emit `MODELED_ENTRY_QUOTE_REFERENCE`, **not** `BROKER_FILL`.
7. Every historical future exit review uses quote availability as of its review time, exact original rights and the same size/spread/age/skew rules. Records quote details and the **computed net liquidation P&L** against the original net debit. Exit triggers: take profit (default **+20%**), stop loss (default **-10%**), or maximum hold reviews (default **5**). Exit triggers and qualifications are retained, including continued holds.
8. Source absence, future quote, missing right, invalid quoted size/price or rejected sync/price leave an **unresolved open position**, not a made-up winning, losing or zero-value fill. No same-strategy new entries while the original slot is occupied. Final equity is `null` until positions are fully closed/valued.
9. No broker order receipts, order-book queue-position reconstruction, bid/ask fill guarantee, assignment or exercise/settlement proof. Hypothetical sale proceeds are immediately reflected in **quote-reference cash**, not claimed to be real settled buying power. Actual historical performance remains **unvalidated** even if sample data contains apparently clean quotes.

### Auditable durable outputs

`packages/simulation/options_pair_runtime_journal_v50.py` writes a NEW immutable JSONL event journal containing a RUN_MANIFEST, every runtime decision/entry/review/exit/unresolved event, and RUN_CLOSEOUT. Each line has its sequence, previous-record SHA and canonical SHA; a full readback rejects missing, truncated, altered, out-of-order or post-closeout records. No overwrite; no raw market-chain duplication.

`scripts/run_options_pair_chronological_runtime_v50.py` accepts `--cases file.json --output new.json` and optional predeclared simulation policy flags. It saves an independent SHA/fingerprint-linked JSON replay + sibling `.jsonl` journal, prints counts, denials, missing exposure and account equity completeness. Inputs are source-supplied; the CLI does NOT use raw ThetaData APIs or promote independently unverifiable PIT flags.

### Input adapter contract

```json
{
  "cases": [
    {
      "opportunity_id": "unique-SPY-2020-01-02",
      "strategy_version": "predeclared-strategy-version",
      "signal_status": "ENTER_LONG_PAIR",
      "signal_at_utc": "2020-01-02T15:00:00+00:00",
      "feature_available_at_utc": "2020-01-02T14:59:00+00:00",
      "causal_signal_evidence_verified": true,
      "reason_codes": ["signal-approved-by-PIT-input-gates"],
      "source_context": {"input_evidence_sha256": "independently-pinned-SHA"},
      "call_identity": "SPY:2020-02-21:270:C",
      "put_identity": "SPY:2020-02-21:270:P",
      "order_at_utc": "2020-01-02T15:01:00+00:00",
      "action_at_utc": "2020-01-02T15:01:03+00:00",
      "order_quote_pair": {
        "call": {
          "contract_identity": "SPY:2020-02-21:270:C",
          "timestamp_et": "2020-01-02T15:01:00+00:00",
          "available_at_utc": "2020-01-02T15:01:00+00:00",
          "bid": "4.90", "ask": "5.00", "bid_size": 100, "ask_size": 100,
          "source_query_id": "exact-query-ID", "source_sha256": "sha256-of-source"
        },
        "put": {"same-structure-as-call": "must match original put identity"}
      },
      "action_quote_pair": {"call": {"later-original-call": "requires all same fields"}, "put": {"later-original-put": "requires all same fields"}},
      "exit_reviews": [
        {"review_at_utc": "2020-01-03T15:01:00+00:00", "hold_sessions": 1,
         "quote_pair": {"call": {"same-original-contract-and-quote-fields": "required"},
                        "put": {"same-original-contract-and-quote-fields": "required"}}}
      ]
    }
  ]
}
```

The JSON illustration is **schematic**: placeholders are not valid source evidence. The test cases construct complete fictional dated quotes for precise causal/event invariant tests.

### Tested failure and accounting invariants

Unit tests cover: one complete profit-target lifecycle; no-signal/rejected/unverified PIT features; missing action quote; spread/unrealistic adverse movement; 1-second baseline vs separate 3-second policy; risk budget and occupied slot; stop loss / max hold; rejected future/unqualified exit and null terminal equity; duplicate IDs/timestamp chronology; exit-price perturbation cannot change earlier entry events; and a hash-chained runtime journal that rejects altered/truncated/same-path files.

The next required production step is **an adapter supplying independently qualified causal SPY signal features and actual delayed-action source quotes**. V45 contains valid source observations but does not establish independent historical first-publication times, prior-20 economic return PIT sourcing, dated SOFR and discrete SPY dividends/OCC deliverables. V46's robust hypothetical signals cannot be pasted into V50 as eligible true historical signals. V50 intentionally leaves those cases untraded, with reasons. Once a PIT adapter exists, the source runtime can automatically fetch and save genuinely missing independent contracts through V39/ThetaData; no blanket 10-year options download is necessary.

The frozen 2026 protected outcomes have already been viewed and cannot be treated as newly held out. Out-of-sample evidence requires a separately preregistered fresh future interval. Never infer strategy profitability from the quote-reference engine.
