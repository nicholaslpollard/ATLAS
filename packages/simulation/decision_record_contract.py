from __future__ import annotations

import hashlib
import json


SIMULATION_DECISION_RECORD_CONTRACT = {
    "contract_id": "atlas-simulation-decision-record-v1",
    "scope": "PRODUCT_SIMULATION_DECISION_RECORD_ONLY",
    "input_contracts": [
        "atlas-underlying-move-time-forecast-v1",
        "atlas-stock-economics-adapter-v1",
        "atlas-trade-expression-foundation-v1",
    ],
    "records_actionability_policy": True,
    "records_trade_expression_mode": True,
    "records_forecast_fingerprint": True,
    "records_stock_economics_contract_fingerprint": True,
    "records_trade_expression_contract_fingerprint": True,
    "records_option_candidate_fingerprints": True,
    "records_gate_reason_lineage": True,
    "records_selection_reason_lineage": True,
    "option_input_order_normalized": True,
    "deterministic_record_fingerprint": True,
    "decision_timestamp_is_explicit_input": True,
    "provider_reads": 0,
    "provider_writes": 0,
    "broker_reads": 0,
    "broker_writes": 0,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_payload() -> dict[str, object]:
    return json.loads(json.dumps(SIMULATION_DECISION_RECORD_CONTRACT))


def contract_fingerprint() -> str:
    raw = json.dumps(
        SIMULATION_DECISION_RECORD_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT = (
    "62dceacde38687828e610c096d8c0a39479d5bc65b26b56aed2bf4164d8c8af8"
)
