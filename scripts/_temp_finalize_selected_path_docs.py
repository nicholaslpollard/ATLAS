from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

README_SECTION = """
### Successor selected-path evidence — COMPLETE / NO PROMOTION (2026-09-15)

The retained option-worthiness pass showed that 20-session MFE is too broad to answer whether a signal moves fast and cleanly enough for stock/option construction: even losing routes frequently reached 1-5% favorable excursion eventually. ATLAS therefore froze a separate five-session path diagnostic before opening those results. The completed selected-daily run is bound by contract fingerprint `14d3598599e21a8603f95933368c9bdfaf6480577a51064d6110706a9682d1ca` and analysis fingerprint `e89d1d61b7fe6875353816a11727f7ad4a0797917eac0ef4b2d437812a053e20`. It covered exactly **35,995** already-selected comparable daily DEVELOPMENT opportunities, entered at the next regular-session open and measured favorable/adverse path through five instrument trading sessions at frozen 1/2/3/5% thresholds. Same-session two-sided daily touches remain unordered; no intraday ordering is inferred from daily bars.

The path result reinforces specialization rather than promotion. The broadest positive diagnostic remains `pract_bollinger_mean_reversion_v1` LONG (n=5,516; mean five-session gross +0.55%; MFE5 5.19%; adverse excursion 4.93%; favorable-before-adverse 43.49% at 2% and 43.65% at 3%). `pract_flag_pennant_v1` SHORT is cleaner but much smaller (n=191; +0.98%; favorable-before-adverse 54.45% at 2% and 50.79% at 3%). `donchian_breakout_20_volume_short_v1` SHORT (+0.72%, n=379), `pract_adx_dmi_continuation_v1` LONG (+0.63%, n=204), and `rsi_recovery_14_trend_long_v1` LONG (+0.47%, n=189) remain bounded specialist hypotheses. Triangle LONG is positive but only n=57 and highly concentrated. These are post-result DEVELOPMENT diagnostics, not a new valid portfolio or historical qualification result.

The important system-level finding is **path quality**: many routes reach 2-3% favorable excursion within five sessions while favorable-before-adverse rates are only about 30-50%. Expected endpoint return alone is therefore insufficient for options. Trade construction must model move magnitude, speed, adverse path, and then contract-specific delta/gamma/theta/vega, IV/skew/term structure, DTE/strike, spread/liquidity and scenario P&L before an option can pass the universal actionability gate. A stock candidate may remain valid when the option expression fails in modes that permit stock fallback.

The arithmetic mean of per-opportunity `five_session_return / MFE` is denominator-unstable when MFE is near zero and produced misleading aggregate values; it is **not** route evidence. Operator output now uses the retained median capture statistic and explicitly labels the mean as unsuitable for comparison. Underlying path/MFE/MAE/threshold artifacts remain unchanged.

The **259** selected comparable intraday opportunities are deliberately separate. They are all `orb_15m_close_retest_v2` and now have a preregistered exact-minute diagnostic: retained actual entry through retained actual exit, frozen 1/2/3/5% favorable/adverse thresholds, exact minute-bar first-touch time, same-minute collisions unordered, and no use of exit-bar high/low extremes after the strategy may already have exited. The accepted serialized native-unit bindings are reused; only selected symbol/month units are SHA-verified and selected symbol/session paths are queried. This is DEVELOPMENT diagnosis only and grants no consumed-master, future-blind, provider, broker, confluence, promotion, PAPER/LIVE or option-trading authority.

After this minute-path closeout, Track B proceeds through failure-specific external research and at most a small bounded set of versioned specialist hypotheses. Track A account simulation/control-plane work remains free to advance using clearly labeled baseline evidence; alpha research does not block product construction.

"""

EVIDENCE_SECTION = """
### 9.7 Selected daily five-session path closeout and minute-path preregistration — 2026-09-15

**Daily path state: COMPLETE / DESCRIPTIVE / NO PROMOTION.** Contract fingerprint `14d3598599e21a8603f95933368c9bdfaf6480577a51064d6110706a9682d1ca`; analysis fingerprint `e89d1d61b7fe6875353816a11727f7ad4a0797917eac0ef4b2d437812a053e20`. The run validated the accepted retained conditioning/option-worthiness lineage, then evaluated exactly **35,995 selected comparable daily DEVELOPMENT opportunities**. Source lineage was 11 accepted daily partitions / 2,706,154 manifest rows; the optimized implementation projected 1,015 selected instruments, 2,117,873 daily rows and 184,478 targeted rows, then produced all 35,995 five-session paths and 143,980 threshold rows without reading the consumed master or future blind.

Frozen semantics: entry is next regular-session open; horizon is five instrument trading sessions; thresholds are 1%, 2%, 3%, and 5% in favorable and adverse directions; first-touch resolution is session-level; a bar touching both sides is `SAME_SESSION_COLLISION_UNORDERED`. These results are post-result diagnostic evidence and cannot validate a strategy version that was selected or redesigned from them.

Selected positive specialist diagnostics:

- `pract_bollinger_mean_reversion_v1` LONG: n=5,516; mean five-session gross +0.55%; MFE5 5.19%; adverse excursion 4.93%; favorable hit 73.11% / favorable-before-adverse 43.49% at 2%; favorable hit 59.72% / favorable-before-adverse 43.65% at 3%. Broadest current specialist hypothesis; no validation.
- `pract_flag_pennant_v1` SHORT: n=191; +0.98%; MFE5 5.78%; adverse excursion 4.60%; 2% hit 74.35% / favorable-before-adverse 54.45%; 3% hit 61.26% / favorable-before-adverse 50.79%. Cleaner path signal but limited sample and prior fold concentration remain material.
- `donchian_breakout_20_volume_short_v1` SHORT: n=379; +0.72%; MFE5 4.98%; adverse excursion 4.40%; 2% favorable-before-adverse 42.22%; 3% 41.16%. Secondary bounded hypothesis.
- `pract_adx_dmi_continuation_v1` LONG: n=204; +0.63%; MFE5 5.78%; adverse excursion 4.92%; 2% favorable-before-adverse 43.14%; 3% 42.16%. Exploratory only.
- `rsi_recovery_14_trend_long_v1` LONG: n=189; +0.47%; MFE5 4.04%; adverse excursion 3.68%; 2% favorable-before-adverse 49.74%; 3% 48.68%. Smaller sample but relatively cleaner adverse path.
- `pract_triangle_breakout_v1` LONG: n=57; +0.43%; MFE5 6.33%; adverse excursion 6.26%; insufficient and highly concentrated despite positive endpoint mean.

The dominant cross-route finding is not merely move magnitude: many negative routes also reach 2-3% favorable excursion within five sessions. Favorable-before-adverse rates are commonly only ~30-50%, so **speed/order/adverse path and exit construction are binding research variables**. This supports the options-aware architecture in which ATLAS forecasts an underlying move distribution and timing, then separately tests whether a specific option contract can monetize that path after theta, IV/vega, delta/gamma, spread/liquidity, strike/DTE and event risks. Endpoint movement is not option P&L.

**Capture-ratio caution:** the arithmetic mean of per-opportunity `gross_return_5 / MFE5` is unstable when MFE5 is near zero and yielded extreme negative aggregates. It must not be used to rank routes or justify a revision. The retained median capture statistic is the operator-facing summary; raw return, MFE, adverse excursion, give-back and first-touch distributions remain the primary evidence.

**Minute-path state: PREREGISTERED BEFORE RESULTS.** Population is exactly the already-selected comparable minute opportunities: expected 259, all `orb_15m_close_retest_v2`. The frozen minute package measures retained actual entry through retained actual exit at 1/2/3/5% thresholds. Pre-exit minute bars may establish favorable/adverse touches; if both sides first touch in one minute, the class is `SAME_MINUTE_COLLISION_UNORDERED`. The actual exit minute does **not** use that bar's high/low because those extrema may occur after exit; only the retained realized gross return is applied on the terminal minute. Tick order is never inferred. Source access reuses the accepted serialized successor native-unit bindings, verifies exact checkpoint/path/SHA identity for only needed symbol/month units, and queries only selected symbol/session paths. Historical option P&L, Greeks/IV path, confluence, promotion and trading authority remain closed.

Authority after the daily closeout is unchanged: consumed-master rows 0; future-blind rows 0; provider calls 0; broker reads/writes 0/0; confluence false; strategy/selector promotion false; PAPER/LIVE false; option-trading authority false.

"""

ROADMAP_SECTION = """

## Successor selected-path closeout and exact-minute continuation — 2026-09-15

The retained 20-session excursion diagnostic is closed as useful but insufficient for trade-expression timing. The separately frozen selected-daily five-session diagnostic completed under analysis fingerprint `e89d1d61b7fe6875353816a11727f7ad4a0797917eac0ef4b2d437812a053e20` across exactly 35,995 selected comparable daily DEVELOPMENT opportunities. It confirms that magnitude alone is not enough: many routes eventually reach 2-3% inside five sessions while favorable-before-adverse path quality is often only ~30-50%. Positive post-result specialist evidence remains concentrated in Bollinger mean-reversion LONG (broadest sample), Flag/Pennant SHORT (cleaner 2-3% path but small sample), Donchian SHORT, ADX/DMI LONG and RSI-recovery LONG. These findings are diagnostic and create no promotion.

Immediate Track B sequence:

1. complete the preregistered **259-case exact-minute ORB path diagnostic** using only accepted serialized native-unit bindings and selected symbol/session paths;
2. preserve daily and minute path results as descriptive evidence; do not retrofit selector thresholds or open confluence to rescue them;
3. diagnose each promising family by failure mode (adverse-first path, regime mismatch, entry timing, exit/give-back, cost sensitivity, support/concentration);
4. perform targeted external research against that observed failure mechanism;
5. freeze at most a small bounded set of materially different successor versions, preserving v1 permanently;
6. require untouched/new/prospective evidence before any validation/promotion claim.

The options-oriented construction path remains: `strategy edge -> underlying move magnitude/speed/path distribution -> universal actionability gate -> operator trade-expression mode -> stock and/or option evaluation -> contract economics -> portfolio/risk/sizing -> trade or abstain`. Option evaluation must include delta, gamma, theta, vega/IV, skew/term structure, DTE, strike/moneyness, rates/dividends/early exercise where relevant, spread/liquidity/open interest, event risk, break-even/max loss and scenario expected P&L. A model-relative Black-Scholes value is evidence, not executable historical P&L. In modes permitting stock fallback, an underlying candidate may remain eligible when no option contract is economically acceptable.

Track A should continue account simulator/control-plane work in parallel using clearly labeled baselines. Historical alpha qualification is still zero; consumed master remains permanently closed, future blind unopened, confluence closed, and PAPER/LIVE/promotion authority false.
"""


def insert_before(path: Path, marker: str, heading: str, section: str) -> None:
    text = path.read_text(encoding="utf-8")
    if heading in text:
        return
    if marker not in text:
        raise RuntimeError(f"marker not found in {path}: {marker!r}")
    path.write_text(text.replace(marker, section + marker, 1), encoding="utf-8", newline="\n")


def append_once(path: Path, heading: str, section: str) -> None:
    text = path.read_text(encoding="utf-8")
    if heading in text:
        return
    path.write_text(text.rstrip() + section + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    insert_before(
        ROOT / "README.md",
        "## How progress is reported",
        "### Successor selected-path evidence — COMPLETE / NO PROMOTION (2026-09-15)",
        README_SECTION,
    )
    insert_before(
        ROOT / "docs" / "strategy_evidence_register.md",
        "## 10. Successor option-worthiness diagnostic — PRE-RUN implementation",
        "### 9.7 Selected daily five-session path closeout and minute-path preregistration — 2026-09-15",
        EVIDENCE_SECTION,
    )
    append_once(
        ROOT / "docs" / "roadmap.md",
        "## Successor selected-path closeout and exact-minute continuation — 2026-09-15",
        ROADMAP_SECTION,
    )


if __name__ == "__main__":
    main()
