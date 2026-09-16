from pathlib import Path

OLD = "39ab7ed68ce001b0bd663a6085c71bb62220416324eba8216db71366ecb73c22"
NEW = "b18b7e1388cd58518a5261143fdffa2f81b46d2366162a6074f113a31ea2ca33"

for path in (Path("README.md"), Path("docs/roadmap.md")):
    text = path.read_text(encoding="utf-8")
    if OLD not in text:
        raise SystemExit(f"old option economics fingerprint missing from {path}")
    text = text.replace(OLD, NEW)
    path.write_text(text, encoding="utf-8")

readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
old = """The option `capital_required_dollars` value is only the economic denominator used to
compare return on capital. This package deliberately grants **no simulator option
reservation/collateral semantics**."""
new = """The option `capital_required_dollars` value is the economic denominator used to
compare return on capital, but for a long option it may never be below the explicit
ask-debit cash requirement (`ask * contract_multiplier * contracts`). This prevents
artificial ROC inflation before account admission. The value still grants **no
simulator option reservation/collateral semantics**."""
if old not in text:
    raise SystemExit("README capital paragraph not found")
readme.write_text(text.replace(old, new, 1), encoding="utf-8")

roadmap = Path("docs/roadmap.md")
text = roadmap.read_text(encoding="utf-8")
old = """6. compute signed net value and return on explicit economic capital without clamping
   negative economics; the capital input is **not** simulator reservation authority;"""
new = """6. compute signed net value and return on explicit economic capital without clamping
   negative economics; for long options the denominator cannot be below the
   executable ask debit (`ask * multiplier * contracts`), preventing artificial ROC
   inflation, while the capital input remains **not** simulator reservation authority;"""
if old not in text:
    raise SystemExit("roadmap capital rule not found")
roadmap.write_text(text.replace(old, new, 1), encoding="utf-8")
