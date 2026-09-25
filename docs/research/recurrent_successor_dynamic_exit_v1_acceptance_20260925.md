# Recurrent Successor Dynamic Exit V1 — First-Run Closeout (2026-09-25)

## Status and immutable source

**COMPLETE_DYNAMIC_EXIT_V1_SELECTOR_DIAGNOSTIC / NO_PROMOTION**

This record captures the operator-supplied first-run console output of the
previously frozen DEVELOPMENT-only Dynamic Exit V1. It is not a GitHub-hosted
rerun, a portfolio backtest, or a source-data rewrite.

- Frozen contract: `atlas-recurrent-successor-dynamic-exit-selector-v1`
- Contract fingerprint:
  `db538c8cc72189d4fcdb06b854ac8c8bf44e5b5b2798745dd0128f20b8f7cd9a`
- Source static-regime fingerprint:
  `60989a10985973bff48d3d2a82a633282b62e664f22f5c3fac4c35bfee380ede`
- First-run fingerprint:
  `560b35765e82b2ab5fb59f8b00cc641f28112232bf89a994fdb0637f069a2b5b`
- Scope: daily LONG DEVELOPMENT cases, `2018-01-01..2026-04-30`.
- Complete verified source lineage: 546/546 normalized parts.
- Loaded selected comparable opportunities: 36,254; 755 distinct prior-training
  cells.
- Daily path support: 22,604 usable cases / 25,617 selected daily LONG;
  3,013 excluded for insufficient prior path support.
- 32 folds; six predefined STOP/TARGET geometries plus ABSTAIN.
- Provider calls: zero.

## First-run selector observations

| Measure | Observed |
| --- | ---: |
| Usable cases | 22,604 |
| Selected cases | 535 |
| Abstained cases | 22,069 |
| Selection rate | 2.37% |
| Mean realized selected-case net return | -0.058% |
| Median realized selected-case net return | -2.099% |
| Realized selected-case probability positive | 41.31% |
| STOP 2% / TARGET 5% selections | 49 |
| STOP 3% / TARGET 5% selections | 486 |
| Other four actions selected | 0 |

| Year | Usable cases | Selected | Selection rate | Mean selected net return | P(positive) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2018 | 2,974 | 0 | 0.00% | n/a | n/a |
| 2019 | 865 | 5 | 0.58% | -0.217% | 40.00% |
| 2020 | 2,141 | 0 | 0.00% | n/a | n/a |
| 2021 | 5,443 | 0 | 0.00% | n/a | n/a |
| 2022 | 2,854 | 0 | 0.00% | n/a | n/a |
| 2023 | 1,601 | 0 | 0.00% | n/a | n/a |
| 2024 | 1,375 | 0 | 0.00% | n/a | n/a |
| 2025 | 3,520 | 354 | 10.06% | +0.147% | 44.35% |
| 2026 Jan–Apr | 1,831 | 176 | 9.61% | -0.468% | 35.23% |

The first six folds were entirely abstained, and selections occurred in only
three calendar years. The 2026 diagnostic is later in DEVELOPMENT than 2025, but
it is not the isolated FUTURE_BLIND holdout and does not establish generalization.

## Disposition

The selector ran to completion under its frozen training chronology, but the
observed choices do **not** substantiate a robust usable exit policy: overall
selected net return was slightly negative; the selected 2026 cohort was negative;
nearly all opportunities abstained; and the 2025 selected-case +0.147% is not
a replacement for an account-level or independent later-regime result.

This does not retrospectively change the failed static V1/V2 confirmations,
relabel any held-out period, or authorize post-result tuning of V1. No exit policy,
selector, strategy, portfolio rule, PAPER, LIVE, broker/order or confluence
authority is promoted.

The console does not show the aggregate split between
`INSUFFICIENT_PRIOR_CONTEXT_SUPPORT` and
`NO_SUPPORTED_ACTION_HAS_POSITIVE_ROBUST_LCB`. Both reason counts and the annual
breakdown are already stored in the immutable local report. The separate read-only
closeout command reads that report and validates its fingerprint and count
reconciliation without rescanning source parts or consuming provider credits:

~~~powershell
git checkout main; git pull
.\.venv\Scripts\python.exe scripts\inspect_recurrent_successor_dynamic_exit_v1.py
~~~

Retained report path (project-relative):

`data/research/recurrent_successor_dynamic_exit_v1/db538c8cc72189d4/560b35765e82b2ab/dynamic_exit_v1_summary.json`

The subsequent task is to interpret the reason split and decide on a separately
preregistered, genuinely new research hypothesis if justified. The current
Dynamic Exit V1 must not be rerun merely to obtain a favorable result.

## News and options work remains a separate path

The same underlying stock cases can support a separately frozen feature/catalyst
and option-economics challenger. This does **not** mean retroactively adding future
news or options to V1. A prospective adapter must join news using its accepted
conservative PIT `max(created_at, updated_at)` availability rule and use historical
option EOD prices only at/after their release to the strategy clock. D-1 OI is
separate from EOD-D volume and price; zero-volume `last` is not an executable fill;
the actual option intraday path cannot be fabricated from EOD snapshots.

The accepted MarketData paid Starter source and sparse-activity evidence, and
the merged offline candidate batch planner, are research infrastructure rather than
simulator option-price authority. The main ATLAS installation/stock corpus remain
internal. The external NVMe activation is a separate storage gate.
