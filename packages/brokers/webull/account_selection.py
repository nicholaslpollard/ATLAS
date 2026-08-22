from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from packages.core.atomic_io import atomic_write_text


@dataclass(frozen=True)
class WebullSandboxAccountCandidate:
    account_id: str
    account_type: str
    balance_readable: bool
    open_orders_readable: bool
    positions_readable: bool
    open_order_count: int | None
    position_count: int | None

    @property
    def account_ref(self) -> str:
        return hashlib.sha256(self.account_id.encode("utf-8")).hexdigest()[:16]

    @property
    def readable(self) -> bool:
        return self.balance_readable and self.open_orders_readable and self.positions_readable

    @property
    def flat(self) -> bool:
        return self.open_order_count == 0 and self.position_count == 0


def select_webull_sandbox_candidate(
    candidates: tuple[WebullSandboxAccountCandidate, ...],
    *,
    preferred_ref: str | None = None,
) -> tuple[WebullSandboxAccountCandidate, str]:
    """Select one sandbox account while failing closed on ambiguity.

    A sanitized account ref may explicitly select any candidate that passed all
    required Phase 17 read probes. Without an explicit ref, automatic selection is
    allowed only when exactly one readable candidate exists. Multiple readable
    candidates remain ambiguous and require user selection; account type, flatness,
    or hash ordering must never be used as implicit trading/account authority.
    """

    if preferred_ref:
        normalized = preferred_ref.strip().lower()
        matched = tuple(candidate for candidate in candidates if candidate.account_ref == normalized)
        if len(matched) != 1:
            raise ValueError("preferred Webull sandbox account ref did not match exactly one candidate")
        candidate = matched[0]
        if not candidate.readable:
            raise ValueError("preferred Webull sandbox account did not pass all required read probes")
        return candidate, "EXPLICIT_SANITIZED_REF"

    readable = tuple(candidate for candidate in candidates if candidate.readable)
    if not readable:
        raise ValueError("no Webull sandbox account passed all required read probes")
    if len(readable) > 1:
        raise ValueError(
            "multiple readable Webull sandbox accounts remain ambiguous; rerun with --account-ref using one sanitized candidate ref"
        )
    return readable[0], "SINGLE_UNAMBIGUOUS_READABLE_ACCOUNT"


def update_dotenv_webull_account_id(env_path: Path, account_id: str) -> None:
    """Persist WEBULL_PAPER_ACCOUNT_ID locally without logging the raw value."""

    account_id = str(account_id).strip()
    if not account_id or "\n" in account_id or "\r" in account_id:
        raise ValueError("invalid Webull sandbox account id")

    env_path = Path(env_path)
    existing = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
    lines = existing.splitlines()
    key = "WEBULL_PAPER_ACCOUNT_ID"
    replacement = f"{key}={account_id}"
    replaced = False
    updated: list[str] = []
    for line in lines:
        if line.startswith(f"{key}="):
            if not replaced:
                updated.append(replacement)
                replaced = True
            continue
        updated.append(line)
    if not replaced:
        if updated and updated[-1].strip():
            updated.append("")
        updated.append(replacement)
    atomic_write_text(env_path, "\n".join(updated) + "\n")
