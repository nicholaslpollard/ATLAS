from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


LIT02_SOURCE_CONTRACT_VERSION = (
    "lit02-momseason-delisting-aware-monthly-return-source-v1-pre-outcome-feasibility"
)
LIT02_SOURCE_POLICY_STATUS = "LIT02_DELISTING_AWARE_SOURCE_CONTRACT_FROZEN"
LIT02_LIT01_CLOSEOUT_FINGERPRINT = (
    "d60c1a57a3567ad927ddffc10e71c0736b7774ace472b1c518f9b635858c0e79"
)
LIT02_LIT01_OPENED_DEVELOPMENT_START = "2021-09"
LIT02_LIT01_OPENED_DEVELOPMENT_END = "2026-04"
LIT02_REQUIRED_SOURCE_COVERAGE = 1.0
LIT02_PROTECTED_OUTCOME_READS_ALLOWED = False
LIT02_ECONOMIC_OUTCOME_READS_ALLOWED_DURING_FEASIBILITY = False
LIT02_BROKER_READS_ALLOWED = False
LIT02_BROKER_WRITES_ALLOWED = False
LIT02_ORDER_WRITES_ALLOWED = False
LIT02_PAPER_SUBMITS_ALLOWED = False
LIT02_LIVE_WRITES_ALLOWED = False


@dataclass(frozen=True, slots=True)
class LIT02ReturnPath:
    path_id: str
    economic_rule: str
    required_authority: tuple[str, ...]
    permitted_during_source_feasibility: bool = True


LIT02_RETURN_PATHS: tuple[LIT02ReturnPath, ...] = (
    LIT02ReturnPath(
        path_id="ORDINARY_MONTH_END",
        economic_rule=(
            "same economic security remains trading through the target month-end; future economic "
            "evaluation uses the frozen adjusted month-end total-return close source"
        ),
        required_authority=(
            "ATLAS stable identity / PIT reference",
            "Alpaca 1Day adjustment=all exact target session",
        ),
    ),
    LIT02ReturnPath(
        path_id="TICKER_CONTINUITY",
        economic_rule=(
            "same economic security continues under an authoritative successor ticker; future "
            "evaluation follows the successor security rather than the stale symbol"
        ),
        required_authority=(
            "ATLAS stable identity",
            "Massive Composite-FIGI ticker events and/or explicit official SEC ticker-change fact",
            "successor ticker must remain identity-consistent",
        ),
    ),
    LIT02ReturnPath(
        path_id="TERMINAL_CASH",
        economic_rule=(
            "security terminates for explicit per-share cash consideration; terminal economic value "
            "is the authoritative executed cash consideration, not an invented month-end close"
        ),
        required_authority=(
            "official SEC executed transaction filing",
            "explicit effective/closing date",
            "explicit per-share cash consideration",
        ),
    ),
    LIT02ReturnPath(
        path_id="TERMINAL_STOCK",
        economic_rule=(
            "security terminates for successor shares; terminal economic value is the authoritative "
            "exchange ratio multiplied by the successor security value under the future frozen "
            "target-return source"
        ),
        required_authority=(
            "official SEC executed transaction filing",
            "explicit effective/closing date",
            "explicit share exchange ratio",
            "authoritative successor security identity",
        ),
    ),
    LIT02ReturnPath(
        path_id="TERMINAL_MIXED",
        economic_rule=(
            "security terminates for cash plus successor shares; terminal economic value is the "
            "authoritative cash component plus exchange-ratio successor value"
        ),
        required_authority=(
            "official SEC executed transaction filing",
            "explicit effective/closing date",
            "explicit cash component",
            "explicit share exchange ratio",
            "authoritative successor security identity",
        ),
    ),
    LIT02ReturnPath(
        path_id="TERMINAL_DISTRIBUTION",
        economic_rule=(
            "liquidation or other terminal distribution uses only authoritative per-share proceeds "
            "actually payable to the security holder"
        ),
        required_authority=(
            "official issuer/SEC terminal distribution evidence",
            "explicit per-share proceeds or an authoritative licensed delisting-return source",
        ),
    ),
)

LIT02_PROHIBITED_REPAIRS: tuple[str, ...] = (
    "DROP_UNAVAILABLE_HOLDING",
    "ZERO_FILL_UNAVAILABLE_RETURN",
    "ARBITRARY_LAST_TRADED_PRICE",
    "ASSUME_CASH_CONSIDERATION_WITHOUT_AUTHORITY",
    "ASSUME_SUCCESSOR_SECURITY_WITHOUT_IDENTITY_AUTHORITY",
    "MODEL_IMPUTED_DELISTING_RETURN_WITHOUT_A_PREDECLARED_LICENSED_SOURCE",
    "USE_LIT01_RETURN_SIGN_OR_MAGNITUDE_TO_CHOOSE_SOURCE_RULE",
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def lit02_source_policy_payload() -> dict[str, object]:
    return {
        "contract_version": LIT02_SOURCE_CONTRACT_VERSION,
        "status": LIT02_SOURCE_POLICY_STATUS,
        "lit01_closeout_fingerprint": LIT02_LIT01_CLOSEOUT_FINGERPRINT,
        "lit01_opened_development_interval": {
            "start": LIT02_LIT01_OPENED_DEVELOPMENT_START,
            "end": LIT02_LIT01_OPENED_DEVELOPMENT_END,
            "fresh_confirmatory_reuse_allowed": False,
        },
        "required_source_coverage": LIT02_REQUIRED_SOURCE_COVERAGE,
        "return_paths": [asdict(item) for item in LIT02_RETURN_PATHS],
        "prohibited_repairs": list(LIT02_PROHIBITED_REPAIRS),
        "feasibility_inputs": {
            "lit01_missing_source_keys_allowed": True,
            "lit01_missing_identity_metadata_allowed": True,
            "lit01_return_signs_or_magnitudes_allowed": False,
            "new_price_or_return_reads_allowed": LIT02_ECONOMIC_OUTCOME_READS_ALLOWED_DURING_FEASIBILITY,
        },
        "authority": {
            "massive_reference_and_composite_figi": "identity/ticker continuity only",
            "official_sec": "transaction, ticker-change, closing-date, and consideration authority",
            "alpaca_adjustment_all": "future tradable-session total-return price source only; not read during feasibility",
            "arbitrary_last_price": "prohibited",
            "silent_deletion": "prohibited",
        },
        "safety": {
            "protected_outcome_reads_allowed": LIT02_PROTECTED_OUTCOME_READS_ALLOWED,
            "broker_reads_allowed": LIT02_BROKER_READS_ALLOWED,
            "broker_writes_allowed": LIT02_BROKER_WRITES_ALLOWED,
            "order_writes_allowed": LIT02_ORDER_WRITES_ALLOWED,
            "paper_submits_allowed": LIT02_PAPER_SUBMITS_ALLOWED,
            "live_writes_allowed": LIT02_LIVE_WRITES_ALLOWED,
            "phase33_authority": False,
            "production_authority": False,
        },
    }


def lit02_source_policy_fingerprint() -> str:
    return hashlib.sha256(
        _canonical_json(lit02_source_policy_payload()).encode("utf-8")
    ).hexdigest()


assert LIT02_REQUIRED_SOURCE_COVERAGE == 1.0
assert LIT02_ECONOMIC_OUTCOME_READS_ALLOWED_DURING_FEASIBILITY is False
assert LIT02_PROTECTED_OUTCOME_READS_ALLOWED is False
assert LIT02_BROKER_READS_ALLOWED is False
assert LIT02_BROKER_WRITES_ALLOWED is False
assert LIT02_ORDER_WRITES_ALLOWED is False
assert LIT02_PAPER_SUBMITS_ALLOWED is False
assert LIT02_LIVE_WRITES_ALLOWED is False
assert len({item.path_id for item in LIT02_RETURN_PATHS}) == len(LIT02_RETURN_PATHS)
