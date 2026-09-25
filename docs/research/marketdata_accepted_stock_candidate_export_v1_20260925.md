# Accepted Stock Candidate Export V1 for MarketData — 2026-09-25

## Status

**SOURCE-ONLY EXPORT IMPLEMENTED / FIRST WORKSTATION EXPORT PENDING.**
Contract: atlas-marketdata-accepted-stock-candidate-export-v1.

The prior chain planner and gated source cache are now connected to accepted
recurrent-successor stock evidence without inventing example opportunities.
The exporter calls the existing accepted successor conditioning/selected-replay
loader and hash-verifies its exact normalized DEVELOPMENT source receipts.
It opens **no** protected consumed-master or future-blind data, makes no
provider or broker call, and does not grant strategy, option-price or PAPER/LIVE
authority.

## Frozen first cohort

Default: calendar year **2025**, exactly the one lowest SHA-256-scored
eligible opportunity in each month with at least one qualifying case
(12 rows at most). The score hashes a fixed V1 salt and exact pre-existing
opportunity identifier. It is deterministic, independent of input row order,
news, options and realized trade outcome. The source population is the
already accepted walk-forward selected, comparable, daily LONG stock cases
with canonical tickers admissible under the frozen chain planner's literal
symbol grammar; no provider-native symbol is guessed or rewritten.
SHORT funding, minute-entry options and new strategy selection are not
invented. The user can explicitly choose 1..3 rows/month and a year in
2022..2026; 2026 is hard-limited to April 30 within DEVELOPMENT.

Each selected row binds its accepted instrument/session to the exact raw,
as-traded V2 next-session stock OPEN using the existing protected-data-safe
source adapter. The source entry-open timestamp is the accepted XNYS
regular open; candidate planning decision is fixed five minutes later
to avoid treating an opening print as known before its occurrence.
The chain snapshot is the *prior signal session* EOD, never the same
decision-session close. The option request expiration is a bounded
exchange-session-adjusted monthly expiration 28..60 calendar days after
the snapshot; it is a **candidate query**, not provider-proven contract
availability or final option selection. Side is CALL for LONG underlying
exposure. The existing planner derives the +/-8% explicit strike interval
only from the known raw stock entry-open price, not EOD-D provider
underlyingPrice or moneyness.

## Immutable outputs and exact physical source binding

The exporter first writes a small JSON stock-evidence bundle containing
only selected IDs, raw open prices, dates, frozen selection rule, accepted
conditioning lineage and accepted raw-daily manifest fingerprints. The
exact SHA-256 of that on-disk bundle is assigned to each source binding in
the opportunity manifest. The existing batch planner builds the chain
plan from that manifest, and the gated chain cache can physically verify
this same bundle via --stock-source-file before an actual provider request.

All three artifacts use a deterministic cohort ID and reject conflicting
existing bytes. The bundle lives under data/research/evidence and the
opportunity/chain plans under data/options/manifests, so an activated
external-storage binding relocates only eligible secondary outputs.
The accepted stock corpus and ATLAS installation stay internal.

The bundle SHA verifies bytes of the exported selection, while source
acceptance relies on the upstream hash-validated conditioning and raw-daily
adapters. It is not proof of historical option pricing or an independent
provider entitlement query.

## First workstation command

This command is local, offline and can be run outside market hours:

~~~powershell
git checkout main; git pull
.\.venv\Scripts\python.exe scripts\export_marketdata_accepted_stock_candidates_v1.py --year 2025 --per-month 1 --duckdb-threads 4
~~~

It may take time to verify the 546 accepted normalized source partitions
and reconstruct accepted source context; it does not redo the Dynamic Exit
V1 experiment or call a market-data provider. Keep the printed
stock-source-file and plan-file paths; the next command is the dry-run
chain-cache preview using --plan. No live acquisition is implied.

## Authority boundary

This is source selection/planning only. It deliberately does not use
post-entry outcomes for cohort selection, claim the selected opportunities
represent winning strategies, verify the chosen option exists, select a
contract, validate prior-day OI, derive IV/Greeks, treat last/bid/ask as
executable fills, download quote histories, infer intraday option
STOP/TARGET paths, or integrate news/options into recurrent account P&L.
Those require new preregistered packages. The earlier negative exit
evidence and consumed protected master remain unchanged.
