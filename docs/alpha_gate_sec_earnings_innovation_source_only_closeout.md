# SEC diluted-EPS earnings innovation — accepted-negative source-only closeout

Status: **CLOSED `ACCEPTED_NEGATIVE_PIT_SOURCE_INTEGRITY_FAILURE`; MARKET OUTCOMES UNREAD**

Closeout contract:

`alpha-gate-sec-earnings-innovation-closeout-v1-pit-source-integrity-failure-no-market-outcomes`

Closeout fingerprint:

`29e72b427aa63c6ae2e0c25917fad0c9c948f2a2cd97c0d51f390ecd343baacc`

Frozen PIT audit fingerprint:

`423528f7518273f91432ee0cfaf0f43fec8cf33fa11a59f40af5523b4f9d6baa`

Accepted failed PIT report SHA-256:

`ca5d5494b9c4be0158bd5d89c2f5b70aae0ba3a717a4af60f437bf4eaad37cea`

Accepted feasibility-parent SHA-256:

`3c299447e0ed8fd48d10c8cc792cf57396d87378cb21575e219b624c6a50566a`

V2 diagnostic fingerprint:

`399e7d0bece8088e63c4835566d276b51375a5031d81f4db4781675351a87961`

## Source-only result

The frozen PIT audit retained 5,896 audited diluted-EPS observations from 5,902 original-accession candidates, with 300/300 Company Facts hashes matching, 300/300 SEC submissions roots succeeding, zero missing accession metadata, and acceptance chronology proven for 99.8983% of candidates.

The audit nevertheless failed exactly two frozen zero-tolerance source-integrity gates:

- **three ambiguous earliest period contexts**;
- **six accession/form/filing-date contradictions**.

All other frozen source gates passed. Target market outcomes read = **0**. Protected return rows read = **0**. Protected holdout consumed = **false**.

## Data-quality and refetch boundary

This result is a **source-quality limitation**, but it is not evidence of corrupted ATLAS bytes, a stale local database, or a damaged cache. The V2 diagnostic re-fetched all 300 official SEC Company Facts documents and reproduced **300/300 exact Gate0 source hashes**. It also re-read official SEC submissions metadata for all 300 issuers and reproduced the same six contradictions with zero missing accession metadata.

Therefore purging the Parquet/data lake, deleting SEC caches, or blindly refetching the same endpoints is neither required nor scientifically justified. A fresh official-source replay already reproduced the evidence. The owning issue is semantic/provenance inconsistency or ambiguity **between and within official SEC representations**: multiple qualifying contexts may exist for one accession/period, Company Facts `filed` may differ from Submissions `filingDate`, and Company Facts may label a fact `10-Q` when the exact accession is officially `10-Q/A` in Submissions.

ATLAS should preserve the raw official values and provenance rather than overwrite one representation with another. Any future canonicalization rule must be defined prospectively under a new contract before governed outcomes are read.

## Why this cannot be repaired under v1

The frozen original-accession rule requires the earliest retained non-amendment `10-Q` or `10-K` accession to have an **unambiguous direct-quarter context and value**. The V2 diagnostic proved three cases where the same earliest accession contained multiple qualifying direct-quarter contexts. Two also had different diluted-EPS values. Choosing one after observing the failure would add a new source-selection rule that was not preregistered.

The frozen chronology rule separately requires the accession, form, and filing date to reconcile **exactly** against official SEC submissions metadata. The V2 diagnostic proved six violations. Three are filing-date differences despite matching accession/form, while the other three are facts represented by Company Facts as `10-Q` even though official SEC submissions identify the accession as `10-Q/A`. Because amendments are chronology-only and never predictor-ready under the frozen contract, reclassifying or ignoring those contradictions after observation would change the v1 source rule.

These are therefore genuine failures under the preregistration, not a reason to weaken the gates.

## Diagnostic lessons retained for future designs

The closeout preserves two useful source-engineering findings for any future, separately preregistered SEC XBRL study:

1. Company Facts `filed` can differ from official SEC submissions `filingDate` even when accession and form match.
2. A Company Facts fact row can carry `10-Q` while official submissions metadata identifies that exact accession as `10-Q/A`.

A future mechanism may define authoritative reconciliation semantics before seeing outcomes, but this v1 family may not be retrofitted with them.

## Scientific disposition

The exact disposition is:

`ACCEPTED_NEGATIVE_PIT_SOURCE_INTEGRITY_FAILURE`

No return, profitability, benchmark-relative, win-rate, or alpha-performance claim may be inferred because market outcomes remain unread.

This exact diluted-EPS periodic-filing earnings-innovation v1 family is permanently closed. It may not be rescued by selecting a preferred start date, preferring framed facts, tolerating filing-date drift, treating `10-Q/A` as `10-Q`, dropping the offending observations after seeing them, or relaxing either zero-tolerance source-integrity gate.

## Downstream authority

Historical supported alpha remains **0**. Phase33 Signal-to-Trade Construction remains blocked. Provider writes, broker reads/writes, orders, PAPER, LIVE, automation, and automatic broker failover remain disabled for this research family.

The next authorized alpha research program must preregister a **materially different economic/information mechanism** before any target outcomes are opened.
