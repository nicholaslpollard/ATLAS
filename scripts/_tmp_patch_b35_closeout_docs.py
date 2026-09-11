from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:120]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"anchor is not unique in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


readme = Path("README.md")
roadmap = Path("docs/roadmap.md")

replace_once(
    readme,
    "Native minute evidence, extended-hours semantics, and initial intraday strategy readiness are accepted by B34. Gap, opening-range, and premarket performance remain unopened until a separately frozen pre-outcome evaluation contract authorizes development outcome access.",
    "Native minute evidence, extended-hours semantics, and initial intraday strategy readiness are accepted by B34. **B35 DEVELOPMENT replay CLOSED / ACCEPTED (2026-09-11).** The frozen `2016-01-04..2026-04-30` replay completed all **482/482 groups** and **59,768/59,768 source units**, with **482 validated receipt ids**, **20,171,286 fired opportunity/context/outcome records**, and run fingerprint `8955a282453cb89a24d3bcdf819d80451bebfa3ec9752dc24c113efc668cffe6`. The authoritative summary confirms consumed-master rows read `0`, future-blind rows read `0`, provider calls `0`, broker reads/writes `0/0`, PAPER/LIVE authority `false/false`, and strategy/selector promotion `false/false`. This closes the canonical B35 replay itself; the next Track-B work is the preregistered strategy x condition evidence and selector analysis, not another replay.",
)

replace_once(
    readme,
    "The active B35 experiment remains frozen around its four B34 strategies and **must\nnot be modified while that replay is running**. The broader library is successor\nwork under a new preregistered fingerprint.",
    "The completed B35 DEVELOPMENT experiment remains frozen around its four B34\nstrategies and is now immutable historical evidence. It must not be rewritten or\nreplayed to rescue a disappointing result. The broader library is successor work\nunder a new preregistered fingerprint.",
)

replace_once(
    readme,
    "For B35 specifically, the measured path moved from about **660.6 units/hour** in the serial restart to a final isolated exact-equivalent benchmark of **2,942.2 units/hour** at 10 x 1, while preserving **10/10 byte-identical sampled outputs** and all scientific/authority boundaries. This is the reference case for the protocol; its final canonical real-run result will be added after completion.",
    "For B35 specifically, the measured path moved from about **660.6 units/hour** in the serial restart to a final isolated exact-equivalent benchmark of **2,942.2 units/hour** at 10 x 1, while preserving **10/10 byte-identical sampled outputs** and all scientific/authority boundaries. The accepted canonical continuation then reused 82 validated groups and computed the remaining **400 groups / 49,600 units in 11:40:46 at 4,246.7 units/hour**. That sustained real-run rate was about **6.43x the original serial rate** and **44.3% faster than the accepted isolated benchmark**, saving about **63.4 hours** versus serial processing for the remaining 49,600 units. At that sustained rate the equivalent full 59,768-unit workload is about **14.1 hours** instead of roughly **90.5 hours** serial. This completed case is the reference example for the reusable ATLAS efficiency protocol.",
)

replace_once(
    roadmap,
    "**Active pre-outcome contract (2026-09-08): v2 FROZEN; finite DEVELOPMENT replay implementation FROZEN PRE-OUTCOME.** Repository acceptance is exact-head gated and does not itself open B35 outcomes.",
    "**B35 DEVELOPMENT replay status (2026-09-11): CLOSED / ACCEPTED; strategy x condition / selector analysis NEXT.** The v2 contract remains frozen. Repository acceptance did not itself open outcomes; the later immutable DEVELOPMENT authorization opened only the exact frozen replay described below.",
)

replace_once(
    roadmap,
    "Next Track-B sequence: (1) explicitly run the one canonical `--authorize-development-outcomes` replay; (2) preserve its immutable authorization/read-start/group-receipt/run fingerprints; (3) analyze frozen DEVELOPMENT strategy × stock-condition evidence without rescue retuning; (4) build the preregistered walk-forward selector/profile evidence; (5) later evaluate the genuinely new future blind after its required accrual; and (6) never reuse the consumed master interval. Full mechanics and methodology anchors are maintained in `docs/b35_a36_preoutcome_conditional_evidence.md`.",
    "**Canonical DEVELOPMENT replay ACCEPTED (2026-09-11).** The one authorized replay completed `482/482` deterministic groups and `59,768/59,768` frozen source units with exactly `482` validated receipt ids. It produced `20,171,286` fired opportunity/context/outcome records and run fingerprint `8955a282453cb89a24d3bcdf819d80451bebfa3ec9752dc24c113efc668cffe6`. Bound identities remained unchanged: B35 fingerprint `145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6`, source fingerprint `af371478a68d2dca486ffbaa1a339d24e1166257a67ba5f6ededfdda202a04cd`, split fingerprint `3bcccaddf3937368c675fb27a441f9bbac8cbf34816c26e37a4a3e84d03554f6`, and authorization `562d7104d56151e6203a1bf85457f9d1a90bbf19e60cd4d9359a3f96bc0a7be5`. Consumed-master rows read `0`; future-blind rows read `0`; provider calls `0`; broker reads/writes `0/0`; PAPER/LIVE authority `false/false`; strategy/selector promotion `false/false`; no permanent minute feature lake was created. Aggregate fired/comparable counts were: gap continuation `2,875,318 / 1,811,231`; opening-range breakout `16,982,463 / 12,626,529`; premarket relative-volume consolidation `313,447 / 309,304`; highest-volume-day style `58 / 58`. These are replay coverage counts, not profitability conclusions.\n\nThe canonical continuation reused 82 validated groups and computed the remaining **400 groups / 49,600 units in 11:40:46 at 4,246.7 units/hour**. This was about **6.43x** the original ~660.6-unit/hour serial restart and **44.3% faster** than the accepted 2,942.2-unit/hour isolated 10 x 1 equivalence benchmark, saving about **63.4 hours** versus serial processing of the remaining work.\n\nNext Track-B sequence: (1) analyze the frozen B35 DEVELOPMENT strategy x condition evidence without rescue retuning; (2) run the preregistered walk-forward selector/profile analysis and compare it with the frozen standalone baselines; (3) perform the bounded diagnostic review required by the practitioner-library plan while preserving v1 results; (4) freeze the eight-new-family successor contract and confluence schema before opening their outcomes; (5) later evaluate the genuinely new future blind only after its required accrual and without refitting on it; and (6) never reuse the consumed master interval. No additional B35 canonical replay is required for these steps. Full mechanics and methodology anchors are maintained in `docs/b35_a36_preoutcome_conditional_evidence.md`.",
)

replace_once(
    roadmap,
    "**Status: PLANNED SUCCESSOR WORK; DO NOT ALTER THE ACTIVE B35 FOUR-STRATEGY\nEXPERIMENT.** ATLAS already has **six accepted daily practitioner families** in the",
    "**Status: PLANNED SUCCESSOR WORK; B35 DEVELOPMENT REPLAY CLOSED / ACCEPTED.**\nThe completed four-strategy B35 DEVELOPMENT result is immutable historical evidence\nand must not be rewritten for rescue tuning. ATLAS already has **six accepted daily practitioner families** in the",
)

replace_once(
    roadmap,
    "1. Close and validate the active B35 canonical replay; record final throughput and\n   scientific summary without changing the frozen four-strategy result.\n2. Produce the preregistered B35 strategy x condition evidence and selector result.",
    "1. **COMPLETE (2026-09-11):** close and validate the B35 canonical replay; all\n   482 groups / 59,768 units completed with zero protected/future/provider/broker\n   leakage, immutable run fingerprint, and final 4,246.7-unit/hour production rate.\n2. **NEXT:** produce the preregistered B35 strategy x condition evidence and selector result.",
)

replace_once(
    roadmap,
    "The B35 reference case improved the measured serial restart from about **660.6 units/hour** to an isolated exact-equivalent **2,942.2 units/hour** at 10 x 1, roughly **4.45x faster**, while preserving 10/10 sampled output hashes and all frozen scientific and authority semantics. A seemingly attractive single-Parquet-scan rewrite was retained as a negative optimization result because it fell to **820.8 units/hour** despite exact equivalence. This combination—measure, isolate, prove equivalence, benchmark, reject regressions, preserve restart state, then resume—is the default ATLAS efficiency pattern when long-running work becomes a material project bottleneck.",
    "The B35 reference case improved the measured serial restart from about **660.6 units/hour** to an isolated exact-equivalent **2,942.2 units/hour** at 10 x 1, roughly **4.45x faster**, while preserving 10/10 sampled output hashes and all frozen scientific and authority semantics. The accepted canonical continuation then reused 82 valid groups and completed the remaining **400 groups / 49,600 units in 11:40:46 at 4,246.7 units/hour**—about **6.43x the original serial rate**, **44.3% faster than the accepted isolated benchmark**, and about **63.4 hours saved** versus serial processing of the remaining work. The equivalent full 59,768-unit workload at that sustained rate is about **14.1 hours** versus roughly **90.5 hours** serial. A seemingly attractive single-Parquet-scan rewrite was retained as a negative optimization result because it fell to **820.8 units/hour** despite exact equivalence. This combination—measure, isolate, prove equivalence, benchmark, reject regressions, preserve restart state, resume, then record actual production performance—is the default ATLAS efficiency pattern when long-running work becomes a material project bottleneck.",
)

print("B35 closeout documentation patch applied successfully")
