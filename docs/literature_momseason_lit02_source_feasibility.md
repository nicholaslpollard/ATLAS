# LIT-02 MomSeason — delisting-aware source feasibility

## Purpose

LIT-01 closed as `SOURCE_INTEGRITY_INCONCLUSIVE`. The economic signal was not classified because the frozen month-end adjusted-close return contract could not produce complete returns for every frozen holding.

LIT-02 is a new exploratory attempt. It does **not** modify, repair, or reinterpret LIT-01. Its first gate is source-only: determine whether ATLAS can support a delisting-aware monthly-return contract for every frozen LIT-01 source-missing stress case before any new MomSeason economic evaluation is permitted.

Authority remains **EXPLORATORY / NON-AUTHORITATIVE**. No Phase33, PAPER, LIVE, broker-write, production, or merge authority is granted.

## Why a new return-source contract is required

The original LIT-01 target return used adjusted month-end close divided by prior adjusted month-end close minus one. That rule fails when the security ceases exchange trading before month-end.

The external OpenSourceAP/CRSP workflow does not assume every security has a month-end trading close. Its CRSP construction joins monthly stock returns to delisting records and incorporates `dlret` into the monthly return. LIT-02 therefore treats terminal-event economics as part of the return-source problem rather than as missing prices to be silently discarded.

ATLAS does **not** copy CRSP's empirical delisting-return imputations unless an equivalent licensed authoritative source is prospectively declared. In particular, LIT-02 will not invent a performance-delisting loss merely to make the sample complete.

## Frozen LIT-02 source paths

The source policy defines the following admissible economic paths:

1. `ORDINARY_MONTH_END` — the same economic security remains trading through target month-end and the future frozen adjusted total-return price source supplies the exact target session.
2. `TICKER_CONTINUITY` — the same economic security continues under an authoritative successor ticker. Massive Composite-FIGI ticker-event evidence and/or explicit official SEC ticker-change evidence may establish continuity, but the successor must remain identity-consistent.
3. `TERMINAL_CASH` — an executed transaction terminates the security for explicit per-share cash consideration. The authoritative transaction consideration is the terminal economic value; ATLAS does not fabricate a month-end close.
4. `TERMINAL_STOCK` — an executed transaction terminates the security for successor shares. The future return calculation uses the authoritative exchange ratio and authoritative successor identity.
5. `TERMINAL_MIXED` — an executed transaction pays both cash and successor shares. Both components must be explicit and authoritative.
6. `TERMINAL_DISTRIBUTION` — liquidation or another terminal distribution uses only authoritative per-share proceeds or a separately declared authoritative licensed delisting-return source.

## Explicitly prohibited repairs

LIT-02 prohibits:

- dropping an unavailable holding;
- zero-filling an unavailable return;
- arbitrary last-traded-price substitution;
- assuming merger cash consideration without authority;
- assuming a successor security without identity authority;
- model-imputing a delisting return without a prospectively declared licensed source;
- using any LIT-01 return sign or magnitude to choose a source rule.

## Source authority hierarchy

- **ATLAS PIT identity / Massive reference:** security identity, Composite FIGI, CIK, point-in-time ticker facts.
- **Massive Composite-FIGI ticker events:** ticker continuity evidence only; not economic merger consideration authority.
- **Official SEC filings:** explicit ticker-change facts, transaction closing/effective dates, transaction form, per-share cash consideration, exchange ratios, and other issuer-filed terminal-event facts.
- **Alpaca `1Day`, `adjustment=all`:** future tradable-session adjusted total-return price source only. It is not read during this source-feasibility gate.

Missing or contradictory authoritative evidence fails closed as `SOURCE_UNRESOLVED`.

## LIT-01 contamination boundary

The LIT-01 development interval from 2021-09 through 2026-04 already opened 40,819 holding returns under the old frozen contract. LIT-02 therefore marks that interval as **not fresh confirmatory evidence**.

The current source-feasibility gate may use only the accepted LIT-01 missing-source keys and source/identity metadata as stress cases. It may not use LIT-01 return signs or magnitudes to select or modify source rules.

Any later LIT-02 economic-development/protected design must be separately frozen after source feasibility and must explicitly address this non-reuse boundary.

## Feasibility population and criterion

The local freeze-plan builder imports the accepted LIT-01 source diagnostic and closeout, verifies their fingerprints and safety fields, and freezes the unique missing provider `(endpoint_session, historical_ticker)` cases.

The gate requires **100% source coverage** of that frozen stress population. Each case must resolve to an admissible return path with authoritative evidence or the source remains infeasible for a new complete-portfolio economic test.

The freeze-plan stage performs:

- zero new price/return reads;
- zero source-metadata provider reads;
- zero protected reads;
- zero broker reads/writes;
- zero order/PAPER/LIVE writes.

## Current command

```powershell
git fetch origin
git switch literature-anchored-alpha-exploration
git pull --ff-only origin literature-anchored-alpha-exploration
git rev-parse HEAD

.\.venv\Scripts\python.exe scripts\run_literature_momseason_lit02_source_feasibility.py
```

A successful local freeze-plan run must report `LIT02_DELISTING_AWARE_SOURCE_FEASIBILITY_PLAN_READY`, 100% required source coverage, zero outcome/provider/protected reads, and deterministic source-policy and feasibility-plan fingerprints.
