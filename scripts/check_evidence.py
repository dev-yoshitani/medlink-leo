"""Regenerate the unchanged canonical routing matrix and compare numerical evidence."""

import json
import tempfile
from pathlib import Path

import pandas as pd

from medlink.experiments.routing_analysis import write_analysis
from medlink.experiments.routing_benchmark import run_routing_benchmark

ROOT = Path(__file__).resolve().parents[1]
evidence = ROOT / "docs/assets/routing-analysis"
with tempfile.TemporaryDirectory() as directory:
    generated = Path(directory)
    report = run_routing_benchmark(ROOT / "experiments/canonical_routing_benchmark.json", generated)
    assert report.run_count == 216
    write_analysis(generated, generated)
    for name in (
        "raw_results.csv",
        "item_results.csv",
        "factor_summary.csv",
        "matched_summary.csv",
        "matched_conditions.csv",
        "matched_factors.csv",
    ):
        pd.testing.assert_frame_equal(
            pd.read_csv(generated / name),
            pd.read_csv(evidence / name),
            check_exact=False,
            rtol=1e-9,
            atol=1e-7,
        )
    # Preserve the released summary, allowing only machine floating point differences.
    pd.testing.assert_frame_equal(
        pd.read_csv(generated / "summary.csv"),
        pd.read_csv(ROOT / "docs/assets/routing-benchmark/summary.csv"),
        check_exact=False,
        rtol=1e-9,
        atol=1e-7,
    )
    summary = json.loads((generated / "summary.json").read_text())
    assert summary["config_id"] == "canonical-contact-plan-routing-v1.1"
print("216 routing runs, item evidence, factor/matched analysis and released summary agree")
