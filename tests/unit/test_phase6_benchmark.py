from packages.features.benchmark import build_feature_benchmark_summary, project_feature_storage


def test_feature_benchmark_summary_and_projection_are_deterministic():
    summary = build_feature_benchmark_summary(
        timeframe="4h",
        sessions=20,
        rows=1000,
        symbols=100,
        source_bytes=10_000,
        output_memory_bytes=80_000,
        output_parquet_bytes=25_000,
        wall_seconds=5.0,
        process_cpu_seconds=4.0,
        peak_rss_bytes=123_456,
        registered_features=33,
    )
    assert summary["rows_per_second"] == 200.0
    assert summary["cpu_one_core_percent"] == 80.0
    assert summary["output_parquet_bytes_per_row"] == 25.0
    assert summary["output_to_source_ratio"] == 2.5

    projection = project_feature_storage(summary, target_sessions=100)
    assert projection["projected_rows"] == 5000
    assert projection["projected_parquet_bytes"] == 125_000
    assert projection["projected_compute_seconds"] == 25.0
