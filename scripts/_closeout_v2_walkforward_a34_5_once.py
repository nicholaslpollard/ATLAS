from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ROADMAP = ROOT / "docs" / "roadmap.md"
WORKFLOW = ROOT / ".github" / "workflows" / "a34-5-closeout-once.yml"
SELF = Path(__file__).resolve()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing closeout anchor: {label}")
    return text.replace(old, new, 1)


readme = README.read_text(encoding="utf-8")
readme = replace_once(
    readme,
    """- The master protected outcome window `2026-05-12..2026-08-11` remains\n  **unconsumed as of this handoff**. Protected return rows read remain **0** for the\n  retained branches. The operator has now authorized its future one-time use as the\n  frozen practitioner-library walk-forward interval; it remains protected until the\n  explicit command records the immutable authorization and opens it.\n""",
    """- The retained master protected outcome window `2026-05-12..2026-08-11` was\n  **consumed exactly once on 2026-09-07** by the frozen A33/B33 V2 walk-forward.\n  The completed receipt/accounting reports **93,380 master-protected return rows\n  read**. The frozen version then continued unchanged through the accepted V2\n  source cutoff `2026-09-03`; rows after `2026-08-11` are separately tracked as\n  post-protected continuation, not a redefinition of the master holdout. This is\n  historical out-of-sample evidence, not prospective PAPER.\n""",
    "README master holdout",
)
readme = replace_once(
    readme,
    """  accepted volume divergence and rejected price-factor corruption. This changes no\n  source bytes, strategy/portfolio policy, trading authority, or protected-return\n  state; the master holdout remains unopened.\n""",
    """  accepted volume divergence and rejected price-factor corruption. At repair\n  acceptance this changed no source bytes, strategy/portfolio policy, trading\n  authority, or protected-return state; the later frozen replay described below\n  subsequently consumed the master holdout exactly once.\n""",
    "README volume-repair historical boundary",
)
readme = replace_once(
    readme,
    """  price-factor mismatch. No source bytes, strategy/portfolio policy, holdout receipt,\n  protected-return state, PAPER authority, or LIVE authority are changed.\n""",
    """  price-factor mismatch. At repair acceptance it changed no source bytes,\n  strategy/portfolio policy, holdout receipt, protected-return state, PAPER\n  authority, or LIVE authority; the later frozen replay subsequently consumed the\n  master holdout exactly once.\n""",
    "README price-repair historical boundary",
)
readme = replace_once(
    readme,
    """  on Windows and Ubuntu. It has not yet run against the operator database. Its\n  single resume-safe post-build\n""",
    """  on Windows and Ubuntu. It has now run successfully against the completed operator\n  V2 source: native validation passed **67,480 / 67,480 units**, the provider-native\n  split source reused **5,302 / 5,302 complete units**, and the reconciled research\n  view materialized **2,706,154 rows across 1,582 symbols**. Its single resume-safe\n  post-build\n""",
    "README post-build operator run",
)
readme = replace_once(
    readme,
    """  The final closeout changes only the two living documents. Full CI on the final PR\n  revision and post-merge `main` verification remain mandatory release gates.\n  The next operation is the authorized workstation command below: source acceptance,\n  DEVELOPMENT, then the frozen one-time walk-forward. No workstation outcomes were\n  opened during implementation; all nine policies remain RESEARCH and PAPER/LIVE\n  authority remains absent.\n""",
    """  The implementation closeout changed only the two living documents after the code\n  package. The authorized workstation run has now completed. DEVELOPMENT produced\n  **161,347 opportunities**, account replay **-17.912608%** return and\n  **-20.803073%** max drawdown. The frozen walk-forward evaluated signals\n  `2026-05-12..2026-09-03`, produced **14,081 opportunities**, consumed the retained\n  master holdout exactly once with **93,380 protected return rows read**, and ended\n  with account replay **-8.372772%** return and **-8.372772%** max drawdown. Signal-\n  level mean net return was positive for Bollinger-long, EMA-pullback-long,\n  MACD-long, and RSI-recovery-long, but the aggregate account evidence is negative,\n  the RSI sample is small, cash-distribution economics remain incomplete, and\n  **authority promotion is none**. All nine policies remain RESEARCH; PAPER/LIVE\n  authority remains absent.\n""",
    "README PR61 operator closeout",
)
readme = replace_once(
    readme,
    """- The existing browser can inspect historical/research replay artifacts, but it is\n  not yet the accepted near-live Operational PAPER dashboard. It must be connected\n  to the same authoritative decision/order/position/account event state before A35\n  starts; a separate UI-only trading state or manual-refresh workflow is not\n  acceptable.\n""",
    """- A34.5 now supplies the accepted read-only near-live Operational PAPER dashboard\n  contract over engine-owned evidence: no second GUI trading truth, no independent\n  trade decisions, bounded automatic refresh, and visible fail-closed degraded/\n  invalid state. A35 broker mutation remains a separate authority package.\n""",
    "README limitation A34.5",
)
readme = replace_once(
    readme,
    """The native V2 acquisition is complete; the immediate operation is the\npost-build command below. V2 source preparation can stop without opening\nperformance, one flag can continue through the frozen DEVELOPMENT replay, or the\nexplicit two-flag authorization can run DEVELOPMENT and then consume the master\nholdout once as a chronological walk-forward through the V2 cutoff. The browser read model\nprefers hash-valid V2 replay artifacts; if V2 artifacts exist but are invalid it\nfails closed and does not silently display legacy results. No empirical V2 result\nhas been produced in this repository checkout. Protected return rows read: **0**;\nperformance opened: **false**.\n""",
    """The native V2 acquisition, post-build, DEVELOPMENT replay, and frozen one-time\nwalk-forward have all completed on the operator workstation. The browser read model\nprefers the hash-valid completed walk-forward and fails closed rather than silently\nfalling back to legacy or DEVELOPMENT evidence when protected-state artifacts are\ninvalid. DEVELOPMENT account replay returned **-17.912608%** with\n**-20.803073%** max drawdown. The frozen walk-forward through `2026-09-03` returned\n**-8.372772%** with **-8.372772%** max drawdown and read **93,380** rows from the\nretained master protected interval. Performance is now opened for these frozen\nversions; no strategy was promoted.\n""",
    "README V2 immediate operation",
)
readme = replace_once(
    readme,
    """It retains fired, rejected, selected-independent, and overlap-suppressed\ncounterfactual opportunities across the `0/5/10/25/50` bps grid. This is not yet an\naccount portfolio replay and contains no empirical ATLAS result. Master\nprotected return rows read: **0**; holdout consumed: **false**; broker writes:\n**0**; PAPER submits: **0**; LIVE writes: **0**.\n""",
    """It retains fired, rejected, selected-independent, and overlap-suppressed\ncounterfactual opportunities across the `0/5/10/25/50` bps grid. Empirical V2\nDEVELOPMENT and frozen walk-forward account replays now exist. The retained master\nholdout was consumed exactly once; **93,380** master-protected return rows were\nread. The frozen walk-forward continued unchanged through `2026-09-03`; no\nparameter revision or strategy promotion occurred. Broker writes: **0**; PAPER\nsubmits: **0**; LIVE writes: **0**.\n""",
    "README A33 empirical result",
)
readme = replace_once(
    readme,
    """promotion: **false**; protected return rows read: **0**; provider writes: **0**;\nbroker writes: **0**; PAPER submits: **0**; LIVE writes: **0**.\n""",
    """promotion: **false**; master-protected return rows read: **93,380**; holdout\nconsumed: **true exactly once**; provider writes: **0**; broker writes: **0**; PAPER\nsubmits: **0**; LIVE writes: **0**.\n""",
    "README A34 read model status",
)
readme = replace_once(
    readme,
    """Chat 4's operator-console work remains separate in draft PR #60\n(`a34-5-frontend-operator-dashboard`). It has not been merged or accepted as the\nA34.5 gate. Its living-document reconciliation and full acceptance remain pending;\nthe present backend package only maintains the existing replay display contract.\n\nOperational PAPER may not start until the current browser/control plane is connected\nto the authoritative runtime event/state path and proves near-live operator\nobservability. This is a product-readiness gate, not a strategy-evidence promotion.\n""",
    """PR #60 (`a34-5-frontend-operator-dashboard`) completes the A34.5 read-only\noperator-observability gate when this closeout is accepted and merged.\n`PaperDashboardService` reads accepted local Phase15 execution evidence plus\nPhase5 persisted marks, verifies artifact path/hash/schema before display, and\nnever initializes a provider or broker merely to refresh the browser. Fresh LONG\npositions mark conservatively at bid and SHORT positions at ask; stale marks cannot\ncreate P&L, provider uncertainty is visibly `DEGRADED`, and invalid evidence is\n`INVALID`. Strategy provenance and realized net P&L remain explicitly unavailable\nwhere the accepted upstream evidence does not bind them.\n\nThe production surface is GET-only at `/api/v1/ops/paper-dashboard` on the existing\nloopback-only Phase19 server. The operator console uses bounded 5/15/30-second\npolling and organizes Overview, Market, Research, Portfolio, Execution, Brokers &\nData, Operations, and Controls without maintaining a second trading truth. A\nseparate synthetic Codespaces preview never loads `.env`, never initializes real\nproviders/brokers, disables mutation controls, and rejects POST. A34.5 grants no\nPAPER strategy authority or broker-write authority; it only satisfies the\nobservability prerequisite so A35 can begin under its own explicit authority gate.\n\nThis is a product-readiness gate, not a strategy-evidence promotion.\n""",
    "README A34.5 closeout",
)
README.write_text(readme.rstrip() + "\n", encoding="utf-8")

roadmap = ROADMAP.read_text(encoding="utf-8")
roadmap = replace_once(
    roadmap,
    """- Master protected window: `2026-05-12..2026-08-11` — **unconsumed as of this\n  handoff, with explicit operator authorization now granted for one frozen,\n  separately recorded practitioner walk-forward use**.\n""",
    """- Master protected window: `2026-05-12..2026-08-11` — **consumed exactly once\n  on 2026-09-07** by the frozen practitioner-library V2 walk-forward. Completed\n  accounting records **93,380 master-protected return rows read**. The same frozen\n  version continued without parameter change through the accepted V2 source cutoff\n  `2026-09-03`; later rows are tracked separately as post-protected continuation.\n""",
    "roadmap master holdout",
)
roadmap = replace_once(
    roadmap,
    """  price-factor mismatch. No source, strategy, portfolio, PAPER/LIVE authority,\n  or protected-window state changes; the one-time walk-forward remains pending\n  repository acceptance before operator execution.\n- Retained branch protected return reads: **0**.\n""",
    """  price-factor mismatch. At repair acceptance it changed no source, strategy,\n  portfolio, PAPER/LIVE authority, or protected-window state. The later frozen\n  replay subsequently consumed the master holdout exactly once.\n- Frozen A33/B33 V2 master-protected return reads: **93,380**. DEVELOPMENT account\n  replay: **-17.912608%** return / **-20.803073%** max drawdown. Frozen walk-forward\n  account replay through `2026-09-03`: **-8.372772%** return / **-8.372772%** max\n  drawdown. Authority promotion: **none**.\n""",
    "roadmap section 9 results",
)
roadmap = replace_once(
    roadmap,
    """The current checkout has\nno market lake, so no empirical run or ATLAS performance result has been produced.\nPR #47 accepted the retained legacy adapter and merged it as\n`646db6e6e44ccd2355c7c2263221f35cd01d5da8`; post-merge Windows and Ubuntu full\ntests passed. Protected return rows read: **0**; performance opened:\n**false**; provider/broker/PAPER/LIVE writes: **0**. The daily feature fingerprint\nchanged before any outcome access solely to bind the unadjusted PIT price-floor\ncorrection; strategy policy and authority fingerprints remain unchanged.\n""",
    """The operator V2 run has now produced the first empirical frozen reference results.\nPR #47 accepted the retained legacy adapter and merged it as\n`646db6e6e44ccd2355c7c2263221f35cd01d5da8`; post-merge Windows and Ubuntu full\ntests passed. DEVELOPMENT produced **161,347 opportunities** and account return\n**-17.912608%** with **-20.803073%** max drawdown. The frozen walk-forward produced\n**14,081 opportunities**, read **93,380** rows from the retained master holdout,\nand returned **-8.372772%** with **-8.372772%** max drawdown through `2026-09-03`.\nProvider/broker/PAPER/LIVE writes remained **0**. The daily feature fingerprint\nchanged before outcome access solely to bind the unadjusted PIT price-floor\ncorrection; strategy policy and authority fingerprints remain unchanged and no\nstrategy was promoted.\n""",
    "roadmap A33 empirical result",
)
roadmap = replace_once(
    roadmap,
    """**First vertical-slice status (2026-09-03): implemented; empirical account replay\nnot started.** Frozen portfolio-policy fingerprint:\n""",
    """**First vertical-slice status (2026-09-07): implemented and empirically replayed;\nresult is negative at the account level and grants no authority promotion.** Frozen\nportfolio-policy fingerprint:\n""",
    "roadmap A34 status",
)
roadmap = replace_once(
    roadmap,
    """Chat 4's operator-console implementation remains in draft PR #60 on\n`a34-5-frontend-operator-dashboard`. It is separate from this backend correction,\nhas not been merged, and still needs its two living documents reconciled and full\nacceptance. Existing historical replay display support does not satisfy A34.5.\n\n**New hard prerequisite established 2026-09-03 before Operational PAPER.** Extend\nthe authoritative stacked Phase19 browser/control plane from historical/research\ninspection into the near-live operator surface that will be used during A35. The\nfront end must be connected before PAPER broker testing begins so the operator can\nsee the product acting rather than infer behavior later from logs.\n""",
    """PR #60 on `a34-5-frontend-operator-dashboard` now implements the A34.5\noperator-observability gate and closes it when this exact-head package is accepted\nand merged. `PaperDashboardService` reads accepted local Phase15 execution evidence\nplus Phase5 persisted marks; path/hash/schema drift fails `INVALID`, stale or\nuncertain provider state is visibly `DEGRADED`, and passive refresh initializes no\nprovider or broker object. Fresh LONG positions mark at bid and SHORT positions at\nask. Upstream-unbound strategy provenance and gross-only realized P&L remain\nexplicitly unavailable rather than fabricated.\n\nThe existing loopback-only Phase19 server exposes GET-only\n`/api/v1/ops/paper-dashboard`. The browser uses bounded 5/15/30-second polling over\nthe same engine-owned evidence and organizes the operator console into Overview,\nMarket, Research, Portfolio, Execution, Brokers & Data, Operations, and Controls.\nThe separate synthetic preview never loads `.env`, never initializes a real provider\nor broker, disables mutation controls, and rejects POST. **A34.5 grants no PAPER\nstrategy authority and no broker-write authority.** Its completion only removes the\nobservability prerequisite so A35 may begin under a separate explicit authority\npackage.\n""",
    "roadmap A34.5 closeout",
)
roadmap = replace_once(
    roadmap,
    """- Preserve the existing master protected window until the frozen practitioner\n  specifications, data lineage, and evaluation boundaries are hash-bound. It may\n  then be consumed once as the one-time walk-forward interval. A new future\n  prospective PAPER period remains necessary and cannot be backfilled from history.\n""",
    """- The retained master protected window was hash-bound and consumed exactly once\n  by the frozen practitioner V2 walk-forward on 2026-09-07. It may never be reused\n  to qualify a revision. The unchanged frozen version continued afterward through\n  the V2 source cutoff as post-protected historical continuation. A new future\n  prospective PAPER period remains necessary and cannot be backfilled from history.\n""",
    "roadmap chronology holdout",
)
roadmap = replace_once(
    roadmap,
    """### A35 — Operational PAPER and Operator Web Beta\n\n**May begin only after A34.5 is accepted.** Run the same engine prospectively with\n""",
    """### A35 — Operational PAPER and Operator Web Beta\n\n**Next Track-A package after PR #60 merges. A34.5 observability is satisfied, but\nA35 PAPER/broker authority has not begun and must be granted separately.** Run the\nsame engine prospectively with\n""",
    "roadmap A35 next",
)
ROADMAP.write_text(roadmap.rstrip() + "\n", encoding="utf-8")

WORKFLOW.unlink(missing_ok=True)
SELF.unlink(missing_ok=True)
