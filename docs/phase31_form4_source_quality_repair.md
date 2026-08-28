# Phase 31 Form-4 Source-Quality Repair

**Status:** FROZEN BEFORE ANY PHASE31 MARKET-OUTCOME READ. Local frozen-evidence replay is pending.

This repair does **not** erase or reinterpret the original failed feasibility run. The original `FEASIBILITY_FAIL` remains permanent provenance. This package defines the stricter source-authority boundary required after root-cause diagnosis proved that the Massive early-access/beta Form-4 feed can contain an internally impossible source association.

## Provenance

- Failed target head: `b59a64938eb84c0c1e7df3aaea390cc437326f94`
- Frozen feasibility fingerprint: `edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`
- Diagnostic implementation head: `80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7`
- Diagnostic violation artifact SHA256: `3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`
- Source-quality policy fingerprint: `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`
- Phase31 market outcomes read before this freeze: **0**
- Protected candidate rows read: **0**
- Protected return rows read: **0**
- Broker/order/PAPER/LIVE authority: **0**

## Root-cause evidence

The frozen diagnostic reconstructed **36,854** Form-4 transaction rows with both filing and transaction dates:

- transaction before filing: **33,510**
- transaction same day as filing: **3,343**
- transaction after filing: **1**

The one impossible row was:

- accession `0000950170-23-043337`
- filing date `2023-08-17`
- transaction date `2023-09-15`
- gap: transaction 29 calendar days after filing
- ticker `WISH`
- reporting owner CIK `0001967530`
- officer title `Chief Product Officer`
- transaction code `M`
- derivative `Restricted Stock Unit`
- acquired `A`
- direct ownership `D`
- 10b5-1 false
- transaction timeliness `O`
- 496 shares.

This classification is **not** based on ticker, transaction code, security type, officer identity, or performance. Those fields are diagnostic context only.

Massive's current Form-4 documentation defines:

- `filing_date` as the date submitted to the SEC;
- `transaction_date` as the date of the transaction;
- `transaction_timeliness` `O` as **on time** and `L` as late;
- Form 4 as a filing that follows reportable insider transactions.

The ATLAS provider adapter copies Massive rows directly and does not swap or synthesize those date fields. Therefore a row whose transaction date is 29 days after its filing date is not a valid alpha-authoritative representation of that accession under the provider's documented semantics.

Massive also labels this endpoint early-access/beta. The root cause is therefore classified as a **Massive beta source-association/data-quality defect**, not an ATLAS parser defect and not an authorized future-dated Form-4 semantic category.

Relevant public references:

- Massive Form 4 documentation: `https://massive.com/docs/rest/stocks/filings/form-4`
- ContextLogic/Wish filing index showing accession `0000950170-23-043337` filed on 2023-08-17 and later Form-4 filings on 2023-09-19: `https://wish.gcs-web.com/financial-information/sec-filings/`

ATLAS does **not** infer or fabricate a corrected accession for the anomalous row. The raw evidence is retained exactly as received.

## Frozen source-quality policy

Policy identifier:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

The generic rule is:

1. Preserve every raw provider row and its immutable source SHA.
2. For every Form-4 transaction row with both dates, evaluate the existing invariant: `transaction_date <= filing_date`.
3. If any transaction row has `transaction_date > filing_date`, mark that row as a source chronology violation.
4. Because the defect can be an accession/source association error, quarantine the **entire accession_number**, not only the triggering row.
5. Never alter dates, swap fields, infer a replacement accession, or mutate the raw provider evidence.
6. The alpha-authoritative corpus must contain **zero** transaction rows with `transaction_date > filing_date`.
7. Missing accession identity on a violating row fails closed because accession-level quarantine cannot be performed safely.
8. Provider-native ticker strings/case remain unchanged.
9. The quarantine rule is independent of ticker, transaction code, security type, role, price, return, profitability, or any market outcome.

There is no numeric anomaly tolerance such as "allow one bad row." One impossible row and one thousand impossible rows are treated by the same deterministic source-integrity classifier. Whether the post-quarantine source remains usable is decided by the remaining non-performance feasibility checks, not by ignoring an error count.

## Frozen-evidence repair gate

`scripts/run_phase31_form4_source_quality_repair.py` must make **zero provider calls** and use only:

- the original failed feasibility report;
- its immutable four raw JSONL evidence files;
- the completed frozen chronology diagnostic;
- the exact diagnostic violation artifact SHA above.

The repair gate must prove:

- original feasibility failed **only** `transaction_dates_do_not_postdate_filings`;
- all raw evidence SHAs still match the failed report;
- the diagnostic lineage and violation artifact are exact;
- the raw chronology violation population is reproduced;
- every contaminated accession is quarantined;
- raw row conservation is exact: `raw = authoritative + quarantined`;
- authoritative rows contain zero post-filing transaction dates;
- all authoritative probe windows remain nonempty and retain transaction/ticker linkage;
- authoritative purchase and sale populations remain present;
- every original non-chronology feasibility check remains PASS;
- `NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE` remains unchanged;
- target/protected outcomes remain unread;
- provider/broker/order/PAPER/LIVE authority remains zero.

The repair writes separate derived authoritative and quarantine artifacts. It never overwrites the original provider JSONL or the original failed feasibility report.

## Authority if repair PASSes

A `SOURCE_QUALITY_REPAIR_PASS` means only:

- the Massive Form-4 source is usable **behind this fail-closed quarantine boundary** for Phase31 research;
- the original raw-feed feasibility failure remains historical evidence;
- the next Phase31 action may freeze a finite scientific hypothesis/evaluation contract.

It does **not** mean:

- Phase31 is accepted;
- any alpha is supported;
- market returns may be read before the scientific contract is frozen;
- protected returns may be read;
- Phase32 is unlocked;
- PAPER or LIVE authority exists.

If the repair fails, Phase31 remains in feasibility repair and no performance work begins.
