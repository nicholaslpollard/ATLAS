# B34 Minute / Intraday Semantics Audit

Status: **SOURCE-READINESS V1 ACCEPTED — opening/premarket pack frozen; enhanced OHLCV closeout rerun pending.**

B34 is a finite, read-only gate between the completed V2 native acquisition/daily replay work and any broad minute-scale feature or strategy materialization. It does **not** authorize PAPER or LIVE trading and does not re-open the frozen daily reference strategies for rescue-retuning.

## Accepted workstation evidence

The operator ran the accepted B34 V1 audit on **2026-09-08 UTC**. The returned report was `status=ACCEPTED` with evidence SHA-256:

```text
aad355e57c089a7aaea84a3f941091dec69d89ce87235972f13472a308550237
```

A workstation-path-free summary is retained at `docs/evidence/b34_intraday_source_readiness_acceptance.json`.

The accepted deterministic samples were:

- liquid symbol/day: `ZSL`, `2026-04-30`, 720 rows, including 254 premarket / 388 regular / 78 after-hours;
- sparse/no-trade symbol/day: `ZNTEW`, `2026-04-30`, zero canonical rows with explicit absence evidence;
- split day: `UK`, reverse split, `2026-04-30`, 111 rows;
- other corporate-action day: `YQQQ`, cash dividend, `2026-04-30`, 63 rows;
- DST/session-boundary day: `AA`, `2026-03-09`, 489 rows, including 69 premarket / 390 regular / 30 after-hours.

All four selected acquisition units passed canonical/raw-bundle SHA-256 verification. Three were `COMPLETE`; the DST unit was `COMPLETE_WITH_QUARANTINE` and still passed its selected-unit integrity checks. The audit made zero provider calls, zero broker reads, zero broker writes, and opened zero canonical partitions overlapping the protected master interval.

## Locked V2 minute contract

For the current V2 historical base, the canonical minute source is Alpaca SIP native `1Min` data with:

- provider feed `sip`;
- provider timeframe `1Min`;
- canonical timeframe `1m`;
- adjustment `raw`;
- `asof=-`;
- provider timestamp preserved as canonical `timestamp_utc`;
- timestamp interpreted as the left/start edge of the minute interval;
- a historical 1m bar usable only after `timestamp + 1 minute`;
- `session_date` derived in `America/New_York`;
- exchange-calendar classification into premarket, regular, after-hours, closed, or unknown;
- missing minute stamps preserved as absence rather than synthesized bars;
- duplicate canonical bar keys rejected;
- canonical and raw-bundle hashes re-verified from completed acquisition checkpoints.

The timeframe-neutral physical schema is `canonical-stock-bar-v1`; the previous daily-named symbols remain compatibility aliases.

## Missing bars, auctions, and halts

A missing canonical minute is **not** converted to a zero-volume bar and is **not** labeled as a halt. It means the accepted provider aggregate stream contains no canonical bar for that stamp. This can reflect no eligible trades or other market-state effects that the aggregate itself does not distinguish. Strategy aggregates therefore use observed provider bars only.

B34 does not invent a separate opening-auction record from minute aggregates. Any eligible opening trades reported inside the 09:30 aggregate remain part of that provider bar. A future auction-specific mechanism would require separate accepted auction/trade-condition evidence.

## Split handling

The accepted minute source is raw/unadjusted. B34 does not fabricate adjusted minute bars. Any gap, price-range, or volume lookback that crosses a split effective between compared observations is ineligible and fails closed. The accepted split-day sample proves that split-affected raw minute data can be represented, not that cross-split comparisons are economically valid.

## Exact information clock

The frozen opening/premarket pack uses these clocks:

- premarket feature window: `04:00 <= stamp < 09:30` ET; latest eligible stamp `09:29`; state available at `09:30`;
- opening range: `09:30 <= stamp < 09:45` ET; latest eligible range stamp `09:44`; range available at `09:45`;
- a bar stamped `T` is never available to a historical decision before `T + 1 minute`;
- post-open breakout signals use only fully closed bars.

## Enhanced V2 closeout

The original V1 audit already proved timestamp/session/source/hash semantics and the five required sample classes. The B34 continuation adds an explicit OHLCV scan to the same command so the readiness report itself verifies finite positive OHLC prices, valid bar geometry, nonnegative volume, positive VWAP when present, and nonnegative transaction counts.

It also binds the frozen four-strategy opening/premarket pack defined in `packages/strategies/intraday_opening_pack.py`:

1. `b34_gap_continuation_v1`;
2. `b34_opening_range_breakout_15m_v1`;
3. `b34_premarket_relvol_consolidation_v1`;
4. `b34_highest_volume_day_style_v1`.

All remain `RESEARCH`, expose no performance, and grant no broker/PAPER/LIVE authority. The HVD-style variant is deliberately quantified and omits a small-cap market-cap filter until ATLAS has an accepted PIT market-cap source.

## Protected-holdout boundary

The one-time master holdout remains consumed and may never be reused to qualify a revision. B34 refuses sample dates after **2026-04-30** and excludes the entire May 2026 minute partition, so it cannot open a monthly canonical file overlapping the protected **2026-05-12 through 2026-08-11** interval.

## Final closeout command

After the continuation package is merged, rerun from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\audit_v2_intraday_semantics.py
```

The evidence path remains:

```text
data/v2_build/alpaca_sip_v2/validation/b34_intraday_semantics_audit.json
```

The command remains local/read-only with respect to providers and brokers. B34 is not fully closed, and broad B35 minute materialization is not authorized, until this enhanced report returns `status=ACCEPTED` and the exact package passes repository acceptance.
