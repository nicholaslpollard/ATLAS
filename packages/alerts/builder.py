from __future__ import annotations

from packages.schemas.ai_review import AIReviewRecord, AlertArtifactRecord
from packages.schemas.case_file import Phase13CaseFile


def _fmt(value: float | None, digits: int = 4) -> str:
    return "UNAVAILABLE" if value is None else f"{value:.{digits}f}"


def engine_summary(case: Phase13CaseFile) -> str:
    geometry = case.geometry
    risk = case.portfolio_risk
    instrument = case.instrument_selection
    option_count = len(instrument.ranked_option_alternatives)
    return (
        f"Engine: {case.direction.value} {case.ticker}; primary={instrument.primary_kind.value}; "
        f"market_regime={case.market_state or 'UNAVAILABLE'}; "
        f"ticker_regime={case.ticker_state or 'UNAVAILABLE'}; "
        f"reference_entry={_fmt(geometry.reference_entry)}; stop={_fmt(geometry.stop)}; "
        f"target={_fmt(geometry.target)}; horizon_sessions={geometry.horizon_sessions}; "
        f"reward_to_risk={_fmt(geometry.reward_to_risk, 3)}; "
        f"portfolio_risk={risk.status.value}; proposed_quantity="
        f"{risk.proposed_quantity if risk.proposed_quantity is not None else 'UNAVAILABLE'}; "
        f"news={case.news_context.availability.value}/{case.news_context.article_count}_articles; "
        f"option_alternatives={option_count}. Reference geometry and proposed quantity are "
        "planning evidence only, not fills or orders."
    )


def build_alert_artifact(
    case: Phase13CaseFile,
    *,
    phase13_case_sha256: str,
    review_record: AIReviewRecord,
    ai_review_sha256: str,
) -> AlertArtifactRecord:
    if not case.phase14_review_ready:
        raise ValueError("alert artifact requires a Phase 14 review-ready deterministic case")
    if review_record.instrument_id != case.instrument_id or review_record.ticker != case.ticker:
        raise ValueError("AI review identity differs from deterministic case")
    if review_record.as_of_date != case.as_of_date:
        raise ValueError("AI review date differs from deterministic case")
    if review_record.phase13_case_sha256 != phase13_case_sha256:
        raise ValueError("AI review is not bound to the supplied Phase 13 case hash")
    return AlertArtifactRecord(
        instrument_id=case.instrument_id,
        ticker=case.ticker,
        as_of_date=case.as_of_date,
        phase13_case_sha256=phase13_case_sha256,
        ai_review_sha256=ai_review_sha256,
        disposition=review_record.review.disposition,
        engine_summary=engine_summary(case),
        ai_summary=review_record.review.summary,
        risk_flags=tuple(item.text for item in review_record.review.risk_flags),
        disagreements=tuple(item.text for item in review_record.review.disagreements),
        external_delivery_enabled=False,
        delivered=False,
        execution_present=False,
    )
