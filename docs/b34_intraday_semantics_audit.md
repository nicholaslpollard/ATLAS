# B34 Minute / Intraday Semantics Audit

Status: **IN PROGRESS — audit contract and deterministic validator implemented; workstation evidence still required before B34 closeout.**

B34 is a finite, read-only gate between the completed V2 native acquisition/daily replay work and any full minute-scale feature or strategy materialization. It does **not** authorize PAPER or LIVE trading and does not re-open the frozen reference strategies for rescue-retuning.

## Locked V2 minute contract

For the current V2 historical base, the canonical minute source is Alpaca SIP native `1Min` data with:

- provider feed: `sip`;
- provider timeframe: `1Min`;
- canonical timeframe: `1m`;
- adjustment: `raw`;
- `asof=-`;
- provider timestamp preserved as canonical `timestamp_utc`;
- timestamps interpreted as the left/start edge of the minute interval;
- `session_date` derived in `America/New_York`;
- session classification derived from the configured exchange calendar, including premarket, regular, after-hours, closed-session and DST behavior;
- missing minutes preserved as source absence — B34 must not fabricate bars;
- duplicate canonical bar keys rejected;
- canonical and raw-bundle hashes re-verified from completed acquisition checkpoints before a sample is accepted.

The timeframe-neutral physical schema is now named `canonical-stock-bar-v1`. The previous daily-named constants/functions remain compatibility aliases so existing daily evidence and imports do not change.

## Protected-holdout boundary

The one-time master holdout remains consumed and must not be reused to qualify later revisions.

B34 therefore refuses sample dates after **2026-04-30**. More importantly, its deterministic selector excludes the entire May 2026 minute partition, so the audit never opens a monthly canonical file that could physically overlap the protected **2026-05-12 through 2026-08-11** interval.

The B34 report records:

- zero provider calls;
- zero broker reads;
- zero broker writes;
- no PAPER authority;
- no LIVE authority;
- no full minute materialization authority.

## Deterministic sample classes

The workstation audit must account for all five roadmap classes:

1. `liquid_symbol_day` — highest observed minute count on the deterministic latest pre-protected sample session;
2. `sparse_or_no_trade_symbol_day` — deterministic source absence when available, otherwise the lowest positive-count symbol-day;
3. `split_day` — latest pre-protected split action with a provider-literal symbol/date that has a canonical minute representation;
4. `other_corporate_action_day` — latest pre-protected non-split action with a canonical minute representation;
5. `dst_session_boundary_day` — latest pre-protected exchange session where the New York UTC offset changed from the preceding session.

If no usable split or other corporate-action representation exists in the eligible source interval, the report must record `UNAVAILABLE_WITH_EVIDENCE`; it may not silently substitute a different semantic class.

## Acceptance criteria

For every represented canonical sample, B34 verifies:

- exact `1m` / `stock_minute_aggregates` classification;
- Alpaca V2 provider identity;
- raw/unadjusted state;
- SIP / `1Min` / raw / `asof=-` source identity;
- minute-start timestamp alignment;
- equality of canonical and provider timestamps;
- New York local date to `session_date` consistency;
- exchange-calendar session-segment consistency;
- unique canonical bar keys;
- monotonic timestamps;
- gaps preserved rather than synthesized.

Each selected acquisition unit must also pass current canonical/raw-bundle path and SHA-256 verification. A hash mismatch fails the audit closed.

B34 is accepted only after the real workstation audit returns `status=ACCEPTED` and the evidence is reconciled into the living status/roadmap. Only then may B35 full-universe minute materialization begin.

## Workstation command

From the ATLAS repository root in the project virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts\audit_v2_intraday_semantics.py
```

The persisted local evidence path is:

```text
data/v2_build/alpaca_sip_v2/validation/b34_intraday_semantics_audit.json
```

This command reads only existing V2 local evidence and canonical minute partitions. It does not contact Alpaca, Massive, Webull, or any broker.
