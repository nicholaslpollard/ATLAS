import csv
import gzip

from packages.core.enums import ValidationStatus
from packages.ingestion.staging import FlatFileValidator


HEADERS = ["ticker", "volume", "open", "close", "high", "low", "window_start", "transactions"]


def make_gzip(path):
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        writer.writerow(["AAPL", 10, 1, 2, 2, 1, 123, 5])


def test_validator_accepts_valid_massive_csv(tmp_path):
    path = tmp_path / "x.csv.gz"
    make_gzip(path)
    result = FlatFileValidator(validate_gzip_crc=True, count_rows=True).validate(path, expected_columns=HEADERS)
    assert result.status == ValidationStatus.VALID
    assert result.row_count == 1
    assert result.sha256


def test_validator_rejects_corrupt_gzip(tmp_path):
    path = tmp_path / "x.csv.gz"
    path.write_bytes(b"not gzip")
    result = FlatFileValidator().validate(path, expected_columns=HEADERS)
    assert result.status == ValidationStatus.INVALID
    assert result.errors
