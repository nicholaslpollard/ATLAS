from pathlib import Path

OLD_FP = "b18b7e1388cd58518a5261143fdffa2f81b46d2366162a6074f113a31ea2ca33"
NEW_FP = "798b05ab3867058865301c35a52491ee9a8cde82c6f1b019b8d27bae34e88178"

# Focused test reconciliation.
path = Path("tests/test_option_economics_adapter.py")
text = path.read_text(encoding="utf-8")
text = text.replace(OLD_FP, NEW_FP)
old_import = """    OptionEconomicsInputs,\n    build_option_economic_candidate,\n)"""
new_import = """    OptionEconomicsInputs,\n    build_option_economic_candidate,\n    option_evidence_fingerprint,\n)"""
if old_import not in text:
    raise SystemExit("option economics test import anchor missing")
text = text.replace(old_import, new_import, 1)
old_assert = """    assert OPTION_ECONOMICS_CONTRACT[\"capital_required_floor\"] == \"entry_cash_debit\"\n"""
new_assert = old_assert + """    assert OPTION_ECONOMICS_CONTRACT[\"option_evidence_fingerprint_required\"] is True\n    assert OPTION_ECONOMICS_CONTRACT[\"candidate_identifier_includes_option_evidence_fingerprint\"] is True\n"""
if old_assert not in text:
    raise SystemExit("option contract assertion anchor missing")
text = text.replace(old_assert, new_assert, 1)
marker = "def test_exact_option_evidence_snapshot_is_fingerprinted_and_bound()"
if marker not in text:
    text += """


def test_exact_option_evidence_snapshot_is_fingerprinted_and_bound() -> None:
    forecast = _forecast()
    option = _option()
    result = build_option_economic_candidate(
        forecast=forecast,
        option=option,
        inputs=_inputs(forecast),
    )
    expected = option_evidence_fingerprint(option)
    assert result.source_option_evidence_fingerprint == expected
    assert expected[:16] in result.candidate.identifier

    changed_delta = _option(delta=0.50)
    changed_open_interest = _option(open_interest=999)
    assert option_evidence_fingerprint(changed_delta) != expected
    assert option_evidence_fingerprint(changed_open_interest) != expected
"""
path.write_text(text, encoding="utf-8")

# Living documents: replace superseded fingerprint and make exact evidence binding explicit.
for filename in ("README.md", "docs/roadmap.md"):
    p = Path(filename)
    body = p.read_text(encoding="utf-8")
    if OLD_FP not in body:
        raise SystemExit(f"superseded option fingerprint missing from {filename}")
    body = body.replace(OLD_FP, NEW_FP)
    p.write_text(body, encoding="utf-8")

readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
old = """scenario model, and that model must bind the exact underlying-forecast instance
fingerprint. Scenario prices must satisfy `adverse <= expected <= favorable` and the"""
new = """scenario model, and that model must bind the exact underlying-forecast instance
fingerprint. The full `OptionCandidateEvidence` snapshot is also SHA-256-fingerprinted
and bound into the economics result and candidate identity, so changes to delta, IV,
open interest, volume, eligibility or quote evidence cannot silently reuse an older
candidate. Scenario prices must satisfy `adverse <= expected <= favorable` and the"""
if old not in text:
    raise SystemExit("README option lineage anchor missing")
readme.write_text(text.replace(old, new, 1), encoding="utf-8")

roadmap = Path("docs/roadmap.md")
text = roadmap.read_text(encoding="utf-8")
old = """2. bind every scenario model to the exact underlying-forecast fingerprint and require
   an explicit model id plus SHA-256 fingerprint;
3. require explicit expected/favorable/adverse terminal premiums and model"""
new = """2. bind every scenario model to the exact underlying-forecast fingerprint and require
   an explicit model id plus SHA-256 fingerprint; independently fingerprint the full
   `OptionCandidateEvidence` snapshot and include that lineage in both the economics
   result and option candidate identity;
3. require explicit expected/favorable/adverse terminal premiums and model"""
if old not in text:
    raise SystemExit("roadmap option lineage anchor missing")
roadmap.write_text(text.replace(old, new, 1), encoding="utf-8")
