from pathlib import Path
import re

readme = Path('README.md')
roadmap = Path('docs/roadmap.md')
evidence = Path('docs/strategy_evidence_register.md')
assert evidence.is_file()

r = readme.read_text(encoding='utf-8')
old = """**Current as of 2026-09-11 (UTC). This README and `docs/roadmap.md` are the only
living project documents. Every continuation chat must read both in full before
making recommendations or changes.**"""
new = """**Current as of 2026-09-11 (UTC). The root README, `docs/roadmap.md`, and
`docs/strategy_evidence_register.md` are the three living project documents. Every
continuation chat must read all three in full before making recommendations or changes.**"""
assert old in r
r = r.replace(old, new, 1)

old = """2. Read [`docs/roadmap.md`](docs/roadmap.md) for the complete mission, evidence,
   practitioner-strategy catalog, testing design, gates, and ordered work.
3. Inspect code, tests, immutable phase evidence, and Git history only as needed to
   perform the active roadmap package. Those materials support the two living
   documents; they do not compete with them as current plans.
4. If the two living documents conflict, stop and reconcile both in the same change
   before proceeding.
5. Every repository-changing implementation package must update this README and
   `docs/roadmap.md` in the same commit before it is accepted or merged. The update
   must state the package goal, capability change, result/test evidence, exact
   authority or safety impact, unresolved limitations, and next work. A future chat
   must be able to reconstruct the current product and research state from these two
   living documents without depending on a prior conversation window."""
new = """2. Read [`docs/roadmap.md`](docs/roadmap.md) for the complete mission, testing
   design, gates, and ordered work.
3. Read [`docs/strategy_evidence_register.md`](docs/strategy_evidence_register.md)
   for strategy/version evidence, condition specialties, dispositions, robustness
   state, and successor hypotheses.
4. Inspect code, tests, immutable phase evidence, and Git history only as needed to
   perform the active roadmap package. Those materials support the three living
   documents; they do not compete with them as current plans.
5. If the three living documents conflict, stop and reconcile them in the same
   package before proceeding.
6. Every repository-changing implementation package must update this README and
   `docs/roadmap.md` before acceptance. Any package that opens, changes, interprets,
   closes, calibrates, or promotes strategy evidence must update the Strategy
   Evidence Register in the same package. A future chat must be able to reconstruct
   current product state, research direction, and strategy evidence without a prior
   conversation window."""
assert old in r
r = r.replace(old, new, 1)

pattern = re.compile(
    r"- \*\*B35 strategy x condition / frozen walk-forward selector analyzer is IMPLEMENTED / ACCEPTANCE PENDING in PR #76\.\*\*.*?(?=\n- \*\*B34 intraday source readiness)",
    re.S,
)
replacement = """- **B35 strategy x condition / frozen walk-forward selector analysis is COMPLETE / PROFILE-ONLY.** PR #76 merged as `cceccdc23569f6d48395a52322a83f59ba555b23`. Analysis fingerprint `8369790cc019e84091d9ff431e0ba82678e8b23ec09f65f010cdfaca35d3254f` normalized all 20,171,286 accepted compact opportunities and built 33 complete-XNYS 504/63/63/1 folds. The frozen selector evaluated 17,030,985 test opportunities, selected 3,747 (3,188 comparable), and abstained on 99.978%. Selected mean return was +0.2984% / +0.1984% / +0.0485% / -0.2015% / -0.7014% at 0/10/25/50/100 bps. No strategy or selector is promoted. The material research interpretation and per-strategy dispositions are maintained in `docs/strategy_evidence_register.md`.
- **B35 remaining gate is robustness and final research disposition, not replay.** Complete BH FDR, Deflated Sharpe, PBO/CSCV where evaluable, deterministic 10,000-draw session-bootstrap tail/drawdown analysis, losing-streak/P&L-concentration diagnostics, perturbation diagnostics, and selector comparison versus same-fold standalone/reference/cash before freezing any condition-gated v2. The future blind remains untouched.
"""
r, count = pattern.subn(replacement, r, count=1)
assert count == 1

old_doc = """Documentation is part of acceptance, not cleanup. Every repository-changing
package must update this README and `docs/roadmap.md` together before merge with the
exact current capability, test/CI state when known, safety/authority effect,
unresolved limitations, and next action. If implementation changes but the two
living documents do not, the package is incomplete and must not be treated as the
new handoff."""
new_doc = """Documentation is part of acceptance, not cleanup. Every repository-changing
package must update this README and `docs/roadmap.md` together before merge with the
exact current capability, test/CI state when known, safety/authority effect,
unresolved limitations, and next action. Strategy-evidence-changing packages must
also update `docs/strategy_evidence_register.md`. If implementation or strategy
evidence changes but the applicable living documents do not, the package is
incomplete and must not be treated as the new handoff."""
if old_doc in r:
    r = r.replace(old_doc, new_doc, 1)
readme.write_text(r, encoding='utf-8')

d = roadmap.read_text(encoding='utf-8')
old = """**Current as of 2026-09-08 (UTC). This roadmap and the root `README.md` are the
only living project documents.**"""
new = """**Current as of 2026-09-11 (UTC). This roadmap, the root `README.md`, and
`docs/strategy_evidence_register.md` are the three living project documents.**"""
assert old in d
d = d.replace(old, new, 1)

old = """Every continuation chat must read the root `README.md` and this roadmap in full
before recommending or changing anything. Update both in the same commit whenever
mission, current state, authority, roadmap order, active work, material evidence, or
implemented capability changes. Every repository-changing implementation package
must document its goal, capability change, result/test evidence, exact authority or
safety impact, unresolved limitations, and next work in both living documents before
it is accepted or merged. A future chat must be able to reconstruct the current
product and research state from these two files without depending on a prior chat.
Do not create another current-status, handoff, plan, roadmap, or living README."""
new = """Every continuation chat must read the root `README.md`, this roadmap, and
`docs/strategy_evidence_register.md` in full before recommending or changing
anything. Update README and roadmap whenever mission, current state, authority,
roadmap order, active work, material evidence, or implemented capability changes.
Any package that opens, changes, interprets, closes, calibrates, or promotes strategy
evidence must also update the Strategy Evidence Register in the same package. A
future chat must be able to reconstruct current product state, research direction,
and strategy evidence from these three files without depending on a prior chat. Do
not create another competing current-status, handoff, plan, roadmap, evidence
register, or living README."""
assert old in d
d = d.replace(old, new, 1)

old = """If these two living documents conflict, progression fails closed until both are
reconciled. Code and tests remain the authority for actual behavior; Git history and
accepted artifacts remain the authority for what happened. A code package with
stale living documents is incomplete even if its tests pass."""
new = """If the three living documents conflict, progression fails closed until they are
reconciled. Code and tests remain the authority for actual behavior; Git history and
accepted artifacts remain the authority for what happened. A code or research
package with stale applicable living documents is incomplete even if its tests pass."""
assert old in d
d = d.replace(old, new, 1)

marker = "## 21. Living Strategy Evidence Register"
if marker not in d:
    d += """

## 21. Living Strategy Evidence Register

`docs/strategy_evidence_register.md` is the living scientific ledger for
strategy/version evidence. It preserves observed baseline results, supported and
unsupported condition evidence, walk-forward behavior, robustness status, current
research disposition, successor hypotheses, unresolved limitations, and authority.
It does not replace immutable receipts/artifacts or code behavior; it prevents future
research chats from reconstructing strategy truth from conversational memory.

B35 canonical replay and the first strategy x condition / selector profile are
complete. The current Track-B gate is the remaining preregistered B35 robustness and
final research-disposition package. Do not rerun the canonical minute replay and do
not freeze condition-gated v2 rules until robustness is complete. The register's
current dispositions are: Gap Continuation = condition-gate/calibrate candidate;
Opening Range Breakout = condition-gate/calibrate plus execution audit; Premarket
Rel-Vol = cost/execution-sensitive R&D candidate; Highest-Volume-Day style =
redefine/insufficient evidence. None is promoted.

After B35 robustness closes, freeze successor strategy versions and the broader
18-family/confluence package under new fingerprints. The long-term router should
activate/deactivate strategy specialties using trailing point-in-time evidence and
abstain when no specialty clears support, cost, robustness, risk, and authority
gates. Continuous market coverage is desirable; forced continuous trading is not.
"""
roadmap.write_text(d, encoding='utf-8')
