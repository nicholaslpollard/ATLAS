# Historical Option Reference V6 ARTC conflict closeout and V7 preregistration — 2026-09-22

## V6 remains truthfully incomplete

Historical Option Reference V6 failed closed in `expired-2014-07` on
`O:ARTC140719C00025000` because two unversioned same-rank provider rows differed in
both `additional_underlyings` and `cfi`. Those fields were outside every frozen V6
resolution/quarantine branch. V6 is not rewritten and is not rerun.

The read-only diagnostic contract
`atlas-historical-option-reference-v6-artc-deliverable-cfi-conflict-diagnostic-v1`
completed on the target workstation under evidence fingerprint:

`c7c52de6fb807957ecdb0fe5c6c9c2efb65baa739831fe7f25a64a2a5d77b48c`

The diagnostic itself granted no resolution, quarantine, bulk-acquisition,
strategy, PAPER or LIVE authority.

## Provider-native evidence

The current `as_of=2026-09-19` structural list is repeat-stable and contains exactly
two ARTC target rows across a three-page result set. The rows share ticker,
underlying ticker `ARTC`, call type, American exercise, 2014-07-19 expiration,
$25 strike, BATO primary exchange and 100 shares per contract. They differ exactly in:

- `additional_underlyings`: one row carries `4825 USD` currency and one carries no
  additional underlying;
- `cfi`: `OCASCN` versus `OCASPS`.

Both current rows are unversioned / correction-null.

The historical boundary is much less ambiguous:

- `2014-07-17, expired=false`: exactly one target row; repeated list requests are
  stable; repeated Contract Overview is present/stable; list and overview match;
- `2014-07-18, expired=false`: the same exact one-row result and the same exact
  list/overview agreement;
- the historical row hash on both dates is
  `6f1274868c60e6d23c42c96e4698a08724b3ff1014dd6ecf5b3a992f9794d3d8`;
- that historical payload exactly matches one and only one of the two current rows:
  the `OCASCN` row carrying the $4,825 USD additional-underlying cash amount;
- beginning with `2014-07-19, expired=true`, the structural list exposes both
  conflicting rows while exact Contract Overview is no longer available.

The historical list/overview agreement therefore supplies provider-native
point-in-time evidence for one structural payload before expiration. V7 does not
infer from the current two-row state alone.

## Independent corporate-action corroboration

External evidence explains why the provider-native historical payload is economically
coherent, but it is **corroboration only** and is not consumed by the runtime resolver.

ArthroCare's SEC Form 8-K for the transaction reports that the Smith & Nephew merger
completed on 2014-05-29 and each outstanding ArthroCare common share was converted
into the right to receive **$48.25 cash**.

Primary references:

- SEC EDGAR:
  `https://www.sec.gov/Archives/edgar/data/1005010/000095010314003960/dp46729_8k.htm`
- Smith & Nephew completion release:
  `https://www.smith-nephew.com/en/news/2014/05/29/20140529-sn-completes-acquisition-of-arthrocare`

With 100 shares per option contract, `100 * $48.25 = $4,825`, exactly matching the
Massive historical `additional_underlyings` cash amount.

CFI classification references independently support the direction of the classification
difference: `OCASPS` is the standardized American call / stock / physical-delivery
form, while the `...C...` settlement position in the CFI code family denotes cash
settlement and the terminal `N` denotes non-standardized settlement. OCC documentation
also uses `OCASCN` as an option-position sample, and OCC's June 2014 expiration memo
explicitly references a separate ARTC option expiration-pricing consideration memo.

Context references:

- OCC Ovation/DDS option-position guide:
  `https://www.theocc.com/getmedia/eab72bd1-1beb-4c11-80b0-c191b25a3428/OV_DDS_OnDemand_Positions_Guide.pdf`
- OCC expiration prices memo #34823:
  `https://infomemo.theocc.com/infomemos?date=201406&lastModifiedDate=06%2F20%2F2014+19%3A55%3A55&number=34823`

The combined evidence therefore supports a corporate-action cash-deliverable
representation issue, not random duplicate metadata.

## V7 frozen successor rule

Historical Option Reference V7 is separately versioned. It preserves all V6 branches
unchanged and adds one new **unversioned cash-deliverable/classification** branch.

The new branch may run only when all of the following are true:

1. reference state is EXPIRED;
2. every conflicting row is unversioned / highest correction rank -1;
3. the differing fields are **exactly**
   `additional_underlyings` + `cfi`;
4. there are exactly two conflicting rows;
5. both rows share the same non-empty underlying ticker, primary exchange,
   shares-per-contract and immutable option economics;
6. exactly one row carries one positive USD currency additional-underlying and exactly
   one row has no additional-underlying;
7. the two rows carry two distinct non-empty CFI values;
8. the repeated pre-expiration structural-list target is exactly one row;
9. repeated pre-expiration Contract Overview is present/stable and exactly equals that
   structural-list row;
10. that historical payload exactly matches one and only one current conflicting row;
11. the historically selected row itself carries the positive USD cash
    additional-underlying.

Anything outside that exact class still fails closed. A future conflict that merely
looks similar but violates any one requirement receives no automatic extension.

ARTC is a mandatory pre-acquisition probe and freezes the expected selected provider
row hash, selected CFI `OCASCN`, and $4,825 USD cash deliverable. The known-conflict
probe now fully paginates current structural-list results because ARTC is found within
a three-page candidate set; first-page-only probing is no longer sufficient.

The existing ACIW ambiguity quarantine remains unchanged and preserved. Under the
project's source-preservation doctrine, quarantine remains reversible authority
withholding, not deletion; later corroborating evidence may recover it under another
separately frozen contract.

## Reuse and efficiency

V7 verifies and reuses V7 receipts first, then verified V6 raw lineage, then V5/V4/V3/
V2/V1 raw lineage. Raw bytes are not copied simply to create a new version. Reusable
source data is re-normalized locally under the V7 contract and only partitions lacking
verified reusable raw require provider acquisition.

Bounded worker scheduling remains the default: five workers and at most five
partitions in flight. A source failure stops replacement work from being submitted.

## Authority boundary

V7 remains structural-reference acquisition only. Selecting the historical ARTC cash
row establishes neither historical candidate availability nor historical dynamic
deliverable/price truth for strategy simulation. Those later authorities still require
separately accepted historical option market-data evidence.

No predictor, strategy-outcome, promotion, PAPER or LIVE authority is created.
The Strategy Evidence Register remains unchanged.

## Next workstation gate

After the V7 package is accepted on `main`, run:

```powershell
git checkout main; git pull; .\.venv\Scripts\python.exe scripts\run_historical_option_reference_v7.py --authorize-source-acquisition --workers 5
```

If V7 encounters another new source-semantic class, preserve the completed/reusable
work and stop for another bounded diagnostic. Do not widen V7 after seeing the new
failure.
