# ATLAS Pre-Phase33 FINRA Consolidated Short-Interest Source Feasibility

**State:** frozen source-only feasibility contract; market outcomes remain forbidden.

## Purpose

ATLAS has closed the SEC Schedule 13D/13G beneficial-ownership family `ACCEPTED_NEGATIVE`. The next research mechanism must be materially different rather than a post-result retuning of that family.

This gate tests a new **market-positioning / crowding** information mechanism using FINRA consolidated short-interest position reports. It does **not** test returns, choose a signal direction, rank alpha ideas, consume protected performance, or grant Phase33 authority.

Parent accepted merge:

`208529c5562920cc0b2bcf2bae546e2b9af0a25b`

Mechanism:

`PIT_FINRA_CONSOLIDATED_SHORT_INTEREST_POSITIONING_AND_CROWDING`

Feasibility contract:

`alpha-gate-finra-short-interest-feasibility-v1-consolidated-position-source-only-no-market-outcomes`

Frozen feasibility fingerprint:

`cc80a87f020a4dece88430d20aa62e13d4dcd898656d60d53dea49b3ef975bc4`

## Why this mechanism is materially different

FINRA Rule 4560 short interest is an aggregate position measure reported by broker-dealers twice monthly. That differs economically from the prior SEC families, which studied public corporate disclosures, insiders, fundamental accounting changes, and beneficial ownership filings. This gate is about **positioning/crowding state**, not another issuer event taxonomy.

ATLAS is deliberately not substituting FINRA daily short-sale volume for short interest. FINRA warns that daily short-sale volume is not the same as short interest and is not a complete consolidated measure of market short positioning.

Official source references frozen for this source decision:

- FINRA Short Interest Reporting: `https://www.finra.org/filing-reporting/regulatory-filing-systems/short-interest`
- FINRA Equity Short Interest Data: `https://www.finra.org/finra-data/browse-catalog/equity-short-interest/data`
- FINRA Query API documentation / Consolidated Short Interest: `https://developer.finra.org/docs`
- historical public file shape observed from FINRA: `https://cdn.finra.org/equity/otcmarket/biweekly/shrt20260731.csv`

The historical public download path is used for feasibility so this gate does not require FINRA API credentials.

## Frozen source sample

Exactly these 12 month-end settlement-date anchors are attempted:

- `2021-06-30`
- `2021-12-31`
- `2022-06-30`
- `2022-12-30`
- `2023-06-30`
- `2023-12-29`
- `2024-06-28`
- `2024-12-31`
- `2025-06-30`
- `2025-12-31`
- `2026-03-31`
- `2026-07-31`

The two 2021 anchors are intentionally allowed to fail without changing the gate because FINRA's consolidated exchange-listed history has changed over time. The frozen gate therefore requires **at least 10 of 12** files, which still requires the complete 2022–2026 breadth represented by the anchor set if the 2021 files are not available in the current CSV archive format.

No dates may be added, removed, or substituted after the target run merely to convert a source failure into PASS. A demonstrated FINRA archive/path semantic change must be preserved as evidence and repaired at the source layer under a separately fingerprinted repair if warranted.

## Frozen source-only acceptance gates

The target source census must establish all of the following without reading market outcomes:

- successful historical files: **>= 10**;
- represented settlement years: **>= 5**;
- parsed short-interest rows across successful files: **>= 20,000**;
- exchange-listed rows using documented exchange codes `A/B/E/H/R`: **>= 10,000**;
- unique exchange-listed symbols: **>= 2,500**;
- every successful file resolves the required semantics:
  - settlement date;
  - symbol;
  - current short position;
  - at least one exchange/market identity field;
- every row settlement date exactly matches the requested historical file date;
- only comma, pipe, or tab delimiters are accepted;
- current short position must be a finite nonnegative whole-share quantity.

Historical and current documented field aliases are accepted only for the same semantic concept. Ambiguous duplicate semantic columns fail closed.

`revisionFlag` and `stockSplitFlag` are recorded as source diagnostics only. They are **not** interpreted into performance rules at feasibility.

## Authority boundary

During this gate:

- alpha hypotheses frozen: **false**;
- target market outcome reads: **forbidden / 0**;
- protected market outcome reads: **forbidden / 0**;
- protected holdout consumed: **false**;
- FINRA historical source reads: **allowed**;
- provider writes: **0**;
- broker reads/writes: **0 / 0**;
- order writes: **0**;
- PAPER submits: **0**;
- LIVE writes: **0**;
- automation writes: **0**;
- automatic broker failover: **false**.

A `FEASIBILITY_PASS` grants only permission to proceed to a separate point-in-time source/chronology/identity audit. It does not establish alpha.

## Required next gate after feasibility PASS

Before any performance hypothesis is frozen or any stock/SPY return is opened, ATLAS must independently bind:

1. exact FINRA publication availability for each settlement cycle;
2. decision timestamp/session no earlier than information actually became public;
3. revision semantics and whether historical downloadable rows represent original or later-revised state;
4. stock-split handling;
5. point-in-time symbol and active common-stock identity;
6. an immutable predictor population suitable for a finite preregistered hypothesis family.

If those facts cannot be established without leakage or revision ambiguity, the mechanism must fail closed before performance.

## Target-machine runner

After exact-head repository certification:

```powershell
git fetch origin
git switch alpha-gate-finra-short-interest-feasibility
git pull --ff-only origin alpha-gate-finra-short-interest-feasibility
git rev-parse HEAD

.\.venv\Scripts\python.exe scripts\run_alpha_gate_finra_short_interest_feasibility.py
```

The runner writes only a local derived source-census artifact. It performs no market outcome reads and no external mutations.
