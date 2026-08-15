from packages.core.enums import DataQualityCode, DataQualitySeverity, DatasetType, ValidationStatus
from packages.schemas.data_quality import DataQualityIssue, DataQualityReport


def test_empty_report_is_valid():
    report = DataQualityReport(dataset=DatasetType.STOCK_MINUTE_AGGREGATES, checked_rows=100)
    assert report.status == ValidationStatus.VALID
    assert report.blocking_issue_count == 0


def test_warning_report_is_warning():
    report = DataQualityReport(
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        checked_rows=100,
        issues=[DataQualityIssue(code=DataQualityCode.MISSING_BAR, severity=DataQualitySeverity.WARNING, message="gap")],
    )
    assert report.status == ValidationStatus.WARNING


def test_error_report_is_invalid_and_blocking():
    report = DataQualityReport(
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        checked_rows=100,
        issues=[DataQualityIssue(code=DataQualityCode.INVALID_OHLC, severity=DataQualitySeverity.ERROR, message="bad")],
    )
    assert report.status == ValidationStatus.INVALID
    assert report.blocking_issue_count == 1
