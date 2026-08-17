# Phase 07 — Universe Registry

## Goal

Phase 07 converts ATLAS's stable instrument identity/reference layer into a deterministic, auditable point-in-time market universe for broad discovery, watchlist processing, position monitoring, custom scopes, research, and backtesting.

The universe registry answers **which instruments ATLAS must consider and why**. It does not score setups, rank activity, select strategies, or make trading decisions.

```text
Phase 4 instrument identity/reference
        ↓
Phase 7 metadata eligibility + routing + exclusion audit
        ↓
Phase 8 data health + activity + cheap vector setup discovery
        ↓
Regime / ML / strategies / simulation / options / AI
```

Universe membership is keyed by stable ATLAS `instrument_id`. Provider-native ticker case is retained exactly as point-in-time routing/market-data metadata.

## Identity correction accepted

The first real 2026-08-14 reference inventory found 36,417 rows but only 31,540 stable instrument IDs. All 2,587 duplicate identity groups were multi-ticker groups. Representative collisions included distinct preferred-share series and other separate listed securities.

The legacy medium key was:

```text
CIK + primary_exchange + security_type
```

CIK is issuer-level rather than security-level, so that key could collapse multiple securities from one issuer.

The accepted identity contract is now:

```text
STRONG:
  Composite FIGI
  or Share Class FIGI

MEDIUM:
  CIK + exact provider-native ticker + primary_exchange + security_type

FALLBACK:
  exact provider-native ticker + snapshot date
```

Contracts:

```text
reference-v4-security-safe-medium-identity
instrument-identity-v4-no-issuer-level-medium-collapse
```

All three locally stored reference snapshots were re-keyed offline with zero strong-FIGI identity changes.

For 2026-08-14 the correction changed:

```text
stable instruments:       31,540 → 35,226
duplicate identity groups: 2,587 → 1,110
multi-ticker groups:       2,587 → 1,110
```

The remaining duplicate groups are security-level alias/continuity observations, primarily strong identities observed under multiple historical tickers.

The decisive current-routing result is:

```text
active rows:                    13,110
active stable instruments:      13,110
multi-active-ticker groups:           0
maximum active tickers per ID:        1
```

Therefore one point-in-time provider ticker per stable identity is accepted for Phase 7. Any future snapshot with more than one active ticker for one stable identity is explicitly blocked as `ambiguous_active_ticker`; ATLAS does not guess.

## Locked initial discovery metadata policy

Policy contract:

```text
universe-eligibility-v1-us-listed-core-and-income-securities
```

The policy is based on the corrected real 2026-08-14 active reference inventory.

### Required market/locale

```text
market = stocks
locale = us
```

### Accepted active exchanges

```text
ARCX
BATS
XASE
XNAS
XNYS
```

These are the five exchanges observed across all 13,110 active reference rows.

### Broad-discovery security types

```text
ADRC
CS
ETF
ETN
ETS
ETV
FUND
PFD
```

These keep ordinary equities, ADR common shares, exchange-traded products, closed-end/income funds, and preferred shares available to the later data-health/activity/liquidity funnel instead of prematurely narrowing the opportunity set.

### Special-situation types excluded from broad discovery

```text
WARRANT
RIGHT
UNIT
SP
```

These are not deleted from ATLAS. They are simply excluded from the default broad-discovery route because corporate-action, expiry, redemption, unit-composition, and structured-product behavior requires specialized handling. Position/watchlist/custom routes can still force deterministic processing with explicit override reasons.

### Identity-quality requirement

Broad discovery accepts:

```text
strong
medium
```

The 25 active fallback identities observed on 2026-08-14 are excluded from broad discovery. Fallback identity is intentionally snapshot-scoped and is therefore not stable enough for longitudinal discovery/research. Forced routes remain possible when an exact provider-native ticker is supplied.

## Point-in-time contract

Current universe contract:

```text
universe-v2-point-in-time-routing-and-exclusion-audit
```

A production build currently requires an exact corrected reference snapshot for the requested `as_of_date`. The builder does not substitute a later reference file, which prevents future ticker/listing state from leaking into historical research.

Within a stable identity group:

1. exactly one active row → use its exact provider ticker;
2. more than one active row → exclude from discovery as ambiguous;
3. no active row → exclude from discovery as inactive;
4. a forced position/watchlist/custom route may bypass discovery ineligibility only when an unambiguous exact routing ticker is available.

## Eligibility versus mandatory routing

Broad-discovery eligibility and mandatory processing are separate.

Example:

```text
discovery_eligible = false
routes = [position]
reason_codes = [reference_inactive, position_override]
```

An open position therefore cannot disappear merely because it fails broad-market discovery rules. The same contract applies to watchlist and custom-scope overrides.

## Explicit reason codes

Blocking reasons include:

- inactive or delisted reference state;
- non-US locale;
- unsupported market;
- unsupported exchange;
- unsupported security type;
- unsupported identity quality;
- missing reference metadata;
- ambiguous active ticker;
- unavailable market data;
- quarantined data;
- explicit manual exclusion.

Override reasons are recorded for position, watchlist, and custom routing when they bypass discovery ineligibility.

## Data-health hooks

Phase 7 exposes deterministic hooks for:

- `data_unavailable`;
- `data_quarantined`;
- `manual_exclude`.

The actual broad data-health/activity calculations remain Phase 8 responsibility. This keeps metadata eligibility separate from market-data quality and setup ranking.

## Persisted artifacts

Routed universe members:

```text
data/derived/universe/snapshots/year=YYYY/date=YYYY-MM-DD/part-000.parquet
```

Per-instrument exclusion audit:

```text
data/derived/universe/exclusions/year=YYYY/date=YYYY-MM-DD/part-000.parquet
```

Manifest:

```text
data/manifests/universe/YYYY/YYYY-MM-DD.json
```

Manifest contract:

```text
universe-manifest-v1-source-policy-routing-bound
```

The manifest binds the persisted output to:

- universe contract version;
- identity/reference contract versions;
- exact source reference Parquet SHA-256;
- eligibility-policy version and fingerprint;
- dynamic routing/data-health input fingerprint;
- semantic universe fingerprint;
- routed/excluded counts;
- reason counts;
- discovery security-type counts;
- output Parquet SHA-256 values.

A repeated build is skipped only when all dependencies and persisted hashes still match.

## Build command

```powershell
.\.venv\Scripts\python.exe scripts\build_universe.py --date YYYY-MM-DD
```

The CLI reports source/routed/excluded counts, discovery type distribution, reason counts, wall time, artifact sizes, semantic fingerprint, and whether the build was an idempotent skip.

## Automated acceptance coverage

Tests cover:

- exact provider-native ticker case;
- security-safe medium identity separation;
- strong-identity ticker continuity;
- metadata security-type/exchange policy;
- fallback identity exclusion;
- one active routing alias selection;
- explicit multi-active ambiguity exclusion;
- persisted exclusion audit;
- inactive position override semantics;
- source/policy/routing-bound idempotency;
- exact historical snapshot behavior with no future ticker leakage;
- normalized reference Parquet string schemas across snapshots, including optional all-null metadata fields.

## Remaining Phase 07 real-data gates

1. Build the real corrected 2026-08-14 universe snapshot.
2. Confirm a second identical build is idempotently skipped.
3. Inspect real discovery count, security-type distribution, reason counts, runtime, and artifact sizes.
4. Build 2021-08-16 from the exact historical reference snapshot and confirm point-in-time behavior.
5. If real acceptance passes, close Phase 7 and proceed to the Phase 8 broad-discovery/data-health/activity performance funnel.
