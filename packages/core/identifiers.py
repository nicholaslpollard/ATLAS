from __future__ import annotations

import hashlib


def stable_id(*parts: object, prefix: str | None = None, length: int = 24) -> str:
    """Generate a deterministic identifier from normalized values."""
    normalized = "|".join(str(part).strip() for part in parts)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}" if prefix else digest
