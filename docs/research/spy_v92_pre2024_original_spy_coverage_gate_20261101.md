# V92 frozen pre-2024 original SPY minute source coverage gate — 2026-11-01

## Background
Signed V89–V91 six-family original source-first research finished with 186 original option demands, 4,464 original entry/exit SHA journals, 504 signed portfolio ledgers and an independently audited three-cohort matrix. The 8 configurations with positive results in all three cohorts are strongly correlated early-reversal + runner settings, supported by only 7 actual **hypothetical** quote entries across all period samples; the common balanced/3s/10s policy did not validate any of the six new entry families. See `docs/research/spy_v89_v91_20261101_completed_independent_evidence_audit.md`.

## What V92 does
Before further paid ThetaData option acquisition, V92 surveys **exactly January 2018 through December 2023**, using original local Alpaca SIP V2 SPY 1-minute checkpoint partitions. No network, no new source acquisition, no options data or broker calls.

- Enumerate complete original checkpoint records only inside each specific pre-2024 year/month subtree, not a whole-drive scan.
- Verify SPY-containing completed source unit cardinality and fail closed on symlinks, ambiguous units or missing source.
- When one source unit exists, SHA-256 **both full original canonical SPY parquet and original raw bundle gzip**. Log only validated original source SHA and unit identity; preserve missing, invalid and symlink month classifications explicitly. A month without a checkpoint is **not** assumed to contain missing market activity, but is not qualified.
- Sign `original_month_inventory.json` with all 72 monthly result entries and `summary.json` with SHA link, zero source/provider/broker calls, and no 2026 holdout access. An original monthly SHA pass does **not** establish every daily 09:30–09:40 minute being present; a future complete V89 causal per-session run would still have to verify daily data before any exact option requests.
- Retain original signed report as immutable ZIP. This stage neither tests strategy P&L nor selects which execution variant to trade, and does not retroactively adjust the six entry hypotheses.

**Decision after inventory:** If adequate source-covered 2022–2023 and/or earlier contiguous cohorts exist locally, formally freeze an independent prior-regime historical exploration plan before purchasing exact 1s option tapes, and treat them as additional **retrospective** regimes rather than a virgin forward holdout. If necessary local source months are absent, do not infer or fabricate data; choose alternative ex-ante hypotheses that use existing original stock/options data or defer historical extension. Existing 2026-05-12..2026-08-11 protected master holdout stays sealed.

## Implementation
- `scripts/run_spy_v92_pre2024_original_minute_coverage.py`: immutable signed original month inventory.
- `tests/test_spy_v92_pre2024_original_minute_coverage.py`: synthetic source/absent/corrupt/symlink/protected boundary regressions, no providers.
- `scripts/run_spy_v92_pre2024_inventory_20261101.ps1`: Windows compilation+regression+full SHA inventory+evidence ZIP.

**Status:** committed to research branch; not yet executed on user's workstation. Do not claim which pre-2024 SPY months exist until actual signed inventory is returned.
