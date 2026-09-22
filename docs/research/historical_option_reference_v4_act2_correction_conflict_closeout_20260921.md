# Historical Option Reference V4 ACT2 correction-conflict diagnostic closeout — 2026-09-21

## Status

The read-only `atlas-historical-option-reference-v4-explicit-correction-conflict-diagnostic-v1`
completed successfully on the target workstation.

Diagnostic contract fingerprint:

`54a4436ba1cfee33c6dc3eaabfedd4334c50985d2ee696fab2cc97cfc22620c7`

Evidence fingerprint:

`283f736a73a742704c7d005b9c0c48aee2b11cf2dd1eccc8bf44fd52a443e1e3`

Target:

- partition: `expired-2014-07`
- ticker: `O:ACT2140719C00045000`
- contract type: call
- expiration: `2014-07-19`
- strike: 45
- current reference as-of: `2026-09-19`
- pre-expiration as-of: `2014-07-18`

## Observed provider evidence

All repeated option-reference requests were stable.

At current `as_of=2026-09-19`:

- the structural list returned two target rows;
- both target rows carried explicit correction value `2`;
- the rows differed only in `additional_underlyings`;
- both `additional_underlyings` payloads were USD cash deliverables;
- the observed amounts were `2604` and `2617.04`;
- exact current Contract Overview returned stable HTTP 404 / `NOT_FOUND`.

At pre-expiration `as_of=2014-07-18`:

- the structural list returned exactly one target row;
- that row carried correction value `2`;
- exact Contract Overview returned one stable HTTP-200 row;
- the historical Contract Overview payload matched the historical structural-list row exactly; and
- that historical provider payload matched exactly one of the two current conflicting correction-2 rows.

The workstation evidence manifest preserves the complete returned rows, hashes,
request IDs and exact matching payload.

## Interpretation

The failure that stopped V4 is not an unversioned identity ambiguity. Massive currently
exposes two rows for the same option ticker at the same explicit correction rank, with
only the cash deliverable payload differing. The provider's pre-expiration point-in-time
list and exact Contract Overview independently agree on one exact historical row.

This supports a narrowly separate successor rule for **expired, explicit same-correction
conflicts whose only differing field is `additional_underlyings`**. It does not support
a generic explicit-correction fallback and does not broaden the existing unversioned
`primary_exchange` / `underlying_ticker` resolver.

Any successor rule must continue to require:

1. one shared nonnegative highest correction rank across the conflicting current rows;
2. only the frozen explicit-correction differing field(s);
3. two stable pre-expiration structural-list observations with exactly one target row;
4. two stable exact Contract Overview observations;
5. exact list/overview payload agreement;
6. historical correction rank equal to the current highest correction rank; and
7. the historical payload matching exactly one current conflicting raw row.

Anything else remains fail-closed.

## Authority boundary

This diagnostic does not create historical dynamic-deliverable authority. Selecting the
provider-native pre-expiration structural reference row does not prove that a deliverable
was available unchanged at every earlier point in time and does not supply historical
market prices. Candidate availability, dynamic deliverables, option prices, predictors,
strategy evidence, promotion, PAPER and LIVE authority remain separate gates.
