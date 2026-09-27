# Offline multi-year historical news context — 2026-09-27

The 2022 source join was a pilot. This index works from **2021 through the accepted end of 2026 news** and scans provider historical metadata once, caching its derived feature counts per accepted stock signal in a later manifest. It does not perform a new API request or assume 2022 is the simulator's horizon.

The original local Alpaca history has an accepted V2 source-integrity report with 2,211,606 normalized articles. Before indexing, the reader validates that exact V2 fingerprint and the SHA of each selected normalized monthly Parquet against its original immutable receipt on D:. For full coverage, it checks 70 months from **2020-12 through 2026-09**, including December 2020 so early January 2021's seven-day lookback is not silently truncated. The later source corpus is used to find latest retrieved article revisions, then each article is unavailable until \`max(created_at,updated_at)\`; final retrieved text is never treated as originally available before the latest provider update. Exact article IDs are deduplicated across months; ticker-specific 24-hour/seven-day context is indexed, and no news text sentiment or outcome values enter this stage.

The accepted acquisition cutoff is **2026-09-19**. A decision after that date gets a **missing news-source coverage** status and null counts—not a false zero-headline signal. This also keeps 2026 outside the pre-existing protected development selected-stock source, pending a separate original predecision signal/stock source. The old 2022 casebook retains its original frozen 2022 source contract; this is the separate general six-year index.

Physical data stays in the D:-bound \`data/news\` namespace; no existing source/raw/receipt is mutated. A subsequent case builder will write a compact per-signal PIT-news feature manifest under D:-bound research evidence. The simulator reads that manifest offline, rather than rescanning all news on each tuning iteration.

This index has **zero MarketData calls** and no PAPER/LIVE authority. It does not claim historical fill prices, Greeks or cross-asset P&L.
