# Pre-Phase33 SEC Form 13F Institutional Positioning — Gate0 Source Feasibility

## Status

`FROZEN_BEFORE_PROVIDER_READ`

Feasibility contract:

`alpha-gate-sec-13f-feasibility-v1-official-bulk-source-only-no-market-outcomes`

Policy fingerprint:

`8959769669d4c2e51b86627b8c03a67509a339698025683108cbda4e287fb310`

Source-main lineage:

`579e94d0dfe861e37c25d2d67099f44c4f1c2351`

Economic mechanism candidate:

`PIT_SEC_FORM13F_INSTITUTIONAL_POSITIONING_CHANGE_AND_CONSENSUS_ACCUMULATION`

This Gate0 does **not** freeze an alpha hypothesis and cannot establish trading support.

## Why this family is materially different

The candidate mechanism concerns changes in positions disclosed by institutional investment managers on Form 13F and possible cross-manager accumulation/dispersion. It is not insider trading, issuer 8-K events, beneficial-ownership activism, short interest, earnings innovation, public-news arrival, technical self-features, cross-sectional ML, lead-lag, or statistical arbitrage.

## Official source

Gate0 uses the SEC's official quarterly flattened Form 13F data-set ZIPs under:

`https://www.sec.gov/files/structureddata/data/form-13f-data-sets/`

The SEC documentation states that these data sets are extracted from Form 13F XML filings and may include initial holdings reports, amendments, notices, and notice amendments. The documented primary keys are `ACCESSION_NUMBER` for `SUBMISSION` and `(ACCESSION_NUMBER, INFOTABLE_SK)` for `INFOTABLE`.

The SEC also states that the bulk data is an analysis aid rather than a substitute for the original filing and that historical data sets were refreshed in March 2024 for common-format and extraction fixes. ATLAS therefore preserves each Gate0 ZIP byte-for-byte with SHA-256 and treats original EDGAR filings as a required later provenance-reconciliation layer.

## Frozen anchor packages

Only four source anchors are authorized at Gate0:

- `2016Q1` — `2016q1_form13f.zip`
- `2020Q2` — `2020q2_form13f.zip`
- `2023Q1` — `2023q1_form13f.zip`
- `2025MAM` — `01mar2025-31may2025_form13f.zip`

The newest anchor ends on **2025-05-31**, before the master protected outcome window. No 2026 13F source package is authorized at Gate0.

## Frozen source semantics and capacity gates

Every anchor must contain `SUBMISSION.tsv`, `COVERPAGE.tsv`, and `INFOTABLE.tsv`.

The frozen minimums are deliberately broad source-capacity tests, not performance thresholds:

- at least **500** original `13F-HR` submissions per anchor;
- at least **50,000** `INFOTABLE` rows tied to original `13F-HR` submissions per anchor;
- at least **500** unique original-`13F-HR` manager CIKs per anchor;
- at least **99.5%** of original-`13F-HR` holding rows carry a nonblank nine-character CUSIP;
- zero duplicate `SUBMISSION.ACCESSION_NUMBER` primary keys;
- zero duplicate `(ACCESSION_NUMBER, INFOTABLE_SK)` primary keys;
- zero `INFOTABLE` rows whose accession is absent from `SUBMISSION`;
- zero original `13F-HR` filing dates before their reported period end;
- only the documented submission types `13F-HR`, `13F-HR/A`, `13F-NT`, `13F-NT/A`;
- observed initial-`13F-HR` period coverage spans at least **10 calendar years** across the four anchors.

Each compressed ZIP is capped at **128,000,000 bytes** and each archive at **1,500,000,000 uncompressed bytes**. ZIP traversal, encrypted members, duplicate required-table basenames, malformed required schemas, and source-scope changes fail closed.

## Identity and chronology boundary

Form 13F holdings are CUSIP-based. ATLAS does not currently possess accepted historical CUSIP-to-tradable-instrument authority for this family. Gate0 therefore grants **no CUSIP-to-ATLAS identity authority**, performs no ticker mapping, and reads no market data.

The holdings describe quarter-end positions, but that does not mean the market knew them at quarter end. Any later scientific gate must reconcile exact original EDGAR accessions and freeze a public-availability/decision-session rule before outcomes are opened. Backdating a signal to `PERIODOFREPORT` is forbidden.

Optional FIGI cannot be used to bridge the full history because it became an optional Form 13F field only with the 2023 form changes.

## Immutability and reruns

On the first target-machine run, missing frozen anchor ZIPs are fetched read-only from SEC and persisted under:

`data/canonical/regulatory/sec/form13f/feasibility_v1/`

The report is written to:

`data/derived/strategy_evaluation/pre_phase33/sec_13f_feasibility_v1/source_census.json`

Once the report exists, reruns are read-only: the exact local ZIP hashes must match the accepted report. Missing or changed accepted source evidence fails closed rather than silently refetching or overwriting it.

## Forbidden at Gate0

- market-price or return reads;
- development target outcomes;
- protected returns;
- protected holdout consumption;
- ticker/CUSIP identity guessing;
- fuzzy issuer-name matching;
- alpha-hypothesis freezing;
- full-history 13F acquisition;
- provider writes;
- broker reads/writes;
- order writes;
- PAPER or LIVE submission;
- automation writes;
- Phase33 signal-to-trade authority.

If Gate0 passes, the next step is to prospectively freeze full source acquisition, sampled original-EDGAR reconciliation, exact filing chronology, and a CUSIP-to-ATLAS PIT identity prerequisite before any market outcomes are opened.
