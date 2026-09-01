# SEC Form 13F original-EDGAR reconciliation V2

The first original-EDGAR reconciliation run preserved a real implementation failure after more than 330 of the 374 frozen malformed 2016Q1 accessions had already been acquired and reconciled. The failure was HTTP 404 during archive retrieval. No final V1 report was written, no cached filing was deleted, and no market or protected outcome was read.

The root cause is archive-location authority. V1 instantiated the SEC archive path from the flattened bulk `SUBMISSION.CIK`. That is not a sufficient authoritative locator for every EDGAR submission. SEC's EDGAR access documentation defines the quarterly index filename as the route to the raw complete-submission text and documents that filing/archive CIK context can differ from the CIK embedded in an accession when a submitting entity or agent is involved.

V2 therefore changes only the location-resolution layer:

1. Reconstruct the exact same frozen 2016Q1 population: 374 affected initial `13F-HR` accessions and 10,431 malformed bulk CUSIP rows.
2. Read the official SEC `2016/QTR1/master.idx`.
3. Require every frozen accession to have exactly one authoritative `13F-HR` archive filename from that index.
4. Reuse a V1-cached complete submission only after the master index confirms the accession's exact archive filename and the cached text identifies the expected accession.
5. Fetch only still-missing complete submissions using those master-index filenames.
6. Run the unchanged original-vs-bulk CUSIP comparison and classification.

V1 evidence is not rewritten. Existing raw complete submissions remain immutable and resumable. V2 records the master-index SHA-256, exact filename per accession, bulk-vs-master archive CIK differences, V1 cache reuse count, and provider reads.

Contract:

`alpha-gate-sec-13f-original-edgar-reconciliation-v2-master-index-authoritative-locator-same-frozen-population-source-only-no-market-outcomes`

Fingerprint:

`88402d747d52c4631f12661aa5d8d35738f114775795243c82ab123d6c22cf61`

Governance remains unchanged:

- CUSIP repair: forbidden
- CUSIP-to-ATLAS identity: not granted
- economic hypotheses: not frozen
- target outcome rows: 0
- protected return rows: 0
- protected holdout consumed: false
- scientific freeze: not granted
- Phase33 Signal-to-Trade authority: blocked

A completed V2 reconciliation is still source evidence only. Its purpose is to determine whether the 2016 malformed CUSIPs are present in the original as-filed XML or are artifacts of the flattened bulk extraction before any complete-capacity or scientific-freeze work can proceed.
