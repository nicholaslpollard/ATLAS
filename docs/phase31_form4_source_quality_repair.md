# Phase 31 Form-4 Source-Quality Repair

**Status:** TARGET PASS. Scientific-policy freeze authorized. Original raw-feed `FEASIBILITY_FAIL` remains permanent provenance.

This repair does **not** erase or reinterpret the original failed feasibility run. It establishes the stricter source-authority boundary required because the Massive early-access/beta Form-4 feed returned one internally impossible accession association.

## Frozen provenance

- failed target head `b59a64938eb84c0c1e7df3aaea390cc437326f94`
- feasibility fingerprint `edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`
- diagnostic implementation head `80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7`
- diagnostic violation SHA256 `3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`
- source-quality implementation head `03dcd371e79554cc9e52a1bb4ed3b642a067ca4b`
- source-quality fingerprint `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`
- target/protected market outcomes read before/through repair: **0**
- trading authority: **0**.

## Root cause

The frozen diagnostic reconstructed 36,854 transaction rows with both dates:

- transaction before filing 33,510
- same day 3,343
- transaction after filing 1.

The impossible row belonged to accession `0000950170-23-043337`, filing date `2023-08-17`, returned transaction date `2023-09-15`, ticker WISH, code M, derivative Restricted Stock Unit, 496 shares.

Massive documents `filing_date` as SEC submission date, `transaction_date` as the transaction date, and timeliness `O` as on-time. ATLAS copies those fields directly. Root cause is therefore classified as a **Massive early-access/beta source-association/data-quality defect**, not an ATLAS parser bug.

ATLAS does not infer or fabricate a corrected accession.

## Frozen policy

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Generic rule:

1. preserve every raw provider row unchanged;
2. detect any transaction row with `transaction_date > filing_date`;
3. quarantine the **entire accession_number** containing the violation;
4. fail closed if a violating row lacks accession identity;
5. never clamp dates, swap fields, or infer replacement filing identity;
6. require zero chronology-invalid transaction rows in the alpha-authoritative corpus;
7. preserve provider-native ticker strings/case;
8. never use ticker, transaction code, security type, role, price, return, or profitability to decide quarantine.

There is no numeric anomaly tolerance. There is **no** "one bad row is acceptable" tolerance. The same classifier applies to one impossible accession or thousands.

## Target-machine PASS

Historical runner retained:

`scripts/run_phase31_form4_source_quality_repair.py`

This replay made **zero provider calls**.

Exact result:

- `SOURCE_QUALITY_REPAIR_PASS`
- raw rows **45,921**
- chronology violation seeds **1**
- contaminated accessions **1**
- quarantined accession rows **6**
- authoritative rows **45,915**
- quarantine SHA256 `586df9eb91fb8a9a949a0dc44e0765f7c4b7db54c2b383037012d0fb17aaf1eb`
- target outcome rows 0
- protected candidate rows 0
- protected return rows 0
- provider/broker/order/PAPER/LIVE activity 0
- scientific-policy freeze authorized True
- alpha support granted False
- Phase32 entry satisfied False.

Accepted authoritative window SHAs:

- research boundary `0378adc4364b0b49812f95f700ff47eb52d55b2cf2c17bbecad77a48d6f8a4d5`
- mid-history `d8acaf8834ce166901388b437d5df1adf097d798fefb2e86449d92683acd7afd`
- development boundary `76c250af73a5694751eeb5974dbc55410c3ec63335d57632ab39d4a80d4edd8c`
- protected boundary `a3b1b23c00ffbc7372f779d48171fa0a7aac04a5b3bf028c7b2e9bf74d0bb6e0`.

## Authority after PASS

The repair PASS means Form-4 source data is usable **only behind this fail-closed quarantine boundary**. It does not accept Phase31 or grant alpha support.

The scientific contract was subsequently frozen before any market-outcome read at fingerprint:

`e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`

See `docs/phase31_scientific_contract.md`.

The next target is full historical Form-4 acquisition under the frozen policy. Protected returns remain forbidden.
