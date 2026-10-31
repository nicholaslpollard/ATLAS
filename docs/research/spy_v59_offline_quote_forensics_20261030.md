# V59 — archived quote-path forensics for V56/V58 June 11–13 blockers

**Scope**: Read-only, exact native V56 report + SHA-linked V55 journal + preexisting V38 cached option quote archive. No ThetaData read-through, no historical GET, no source writes or repairs, no broker calls. Causally inadmissible future rows are examined **only to explain retrospective failures**, never to change a past trade decision.

## Proven starting observations

On 2026-10-30 22:18 EDT the user's workstation ran V58 V56 June 9–20 campaign stored under `data/research/spy_v56_june_cohort_20261030_214336`. The accepted V56 parent has **five processed weekdays**, not ten; it stopped at June 13. Original June 9 V55 $600 0DTE call quote reference: $1.18 entry ask (4 contracts, $474.60 entry cost), $0.72 close bid at 15:30, net -$189.20. V57 independently verified and modeled an earlier $0.88 risk-stop quote and -$125.20 on 552 original quote decisions. June 10 and June 12 no signal; June 11 a NO_ENTRY with unspecified cause in the pasted console; June 13 UNRESOLVED_POSITION with cause unspecified in the pasted console. V58 properly reported CENSORED_AT_PARENT_BASELINE_EXIT for June 13, exactly one paired trade, +$64 improvement on June 9 only and **no full-cohort adaptive equity**. Do **not** assume why June 11 rejected or June 13 censored until their original per-date reports and source archives have been independently read.

## What the V59 forensic artifact verifies

1. Original V56 account summary fingerprint and per-date JSON fingerprint.
2. Per-date hash-chained V55 event journal and its original summary tip.
3. The date, original signal status, exact option contract if present, decision clock, source receipt ID/SHA, original modeled entry/exit, and exact no-entry or unresolved reason code.
4. The first relevant event (`ENTRY_QUOTE_REJECTION`, `ACTION_QUOTE_REJECTION`, `SOURCE_CLOCK_REJECTION`, `EXIT_SOURCE_REJECTION`, triggering `EXIT_REVIEW`) including its original source row index and timestamp.
5. If the V38 read-only archive already exists, *original* source-identity binding, raw and gzip SHA verification via the existing V38 reader, timestamp coverage, largest timestamp gap, first invalid quote and reason-category counts.
6. The original two neighboring rows on either side of a decisive rejection, with clock, bid/ask and size, individually qualified using the **unchanged** V55 `_quote` policy. This helps distinguish an isolated invalid quote or wide spread from pervasive source failure, a long observation gap, missing action clock or insufficient displayed size.
7. If the exact archive is missing, report `EXACT_QUERY_NOT_IN_INDEX` (or no index) rather than silently making a provider GET or substituting a price.
8. Output one *new* immutable forensic JSON, fingerprinted. Never overwrite a trading report or fabricate cash.

Example offline command:

```powershell
& '.\.venv\Scripts\python.exe' -m scripts.run_spy_v59_offline_quote_forensics `
  --cohort-dir 'data/research/spy_v56_june_cohort_20261030_214336' `
  --dates 2025-06-11 2025-06-13 `
  --output "data/research/spy_v59_forensic_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

V59 deliberately does **not** repair source rows, relabel an earlier trade, skip an invalid quote, relax the 60-second gap gate, or continue the cumulative account after June 13. The next change must be justified by the actual report and archived quotes. An out-of-sample comparison requires a predeclared causal admissibility rule, unchanged original source and independent later testing.

**Before proposing any recovery:** classify whether June 13 was (a) data corruption/provider no-data, (b) illiquid quote at the active stop/target, (c) excessive bid/ask spread or size, (d) >60-second missing observation path, or (e) no qualifying quote near 15:30. A stop price is not a guaranteed broker execution price. Demand and persist the source query SHA, quote-row evidence and alternative rule's outcome before promoting it into multi-session simulation.

**Future strategy research:** keep V55 baseline and V57 exploratory dynamic policy separately versioned. Trade-specific forward maximum favorable/adverse excursion predictions require earlier-only training folds and strictly decision-time observable features, explicit spread/latency/fees and per-window profitability before combining any strategies. The June 9 adaptive policy was selected after observing June 9; do not call that a clean holdout result.
