import pandas as pd

from research.stabil_arrow_quality import audit_file


def test_raw_quality_separates_zero_volume_and_invalid_rows(tmp_path):
    path = tmp_path / "x.csv.gz"
    pd.DataFrame({"bar_time": ["2025-01-01", "2025-01-02", "2025-01-02"], "open": [10, 10, None], "high": [11, 9, 11],
                  "low": [9, 9, 9], "close": [10, 10, 10], "volume": [0, -1, None]}).to_csv(path, index=False)
    report = audit_file(path)
    assert report == {"rows": 3, "nan_ohlc_rows": 1, "nonfinite_ohlc_rows": 1, "nonpositive_ohlc_rows": 0,
                      "invalid_ohlc_rows": 1, "negative_or_nonfinite_volume_rows": 2,
                      "zero_volume_rows": 1, "invalid_timestamp_rows": 0, "duplicate_timestamp_rows": 1}
