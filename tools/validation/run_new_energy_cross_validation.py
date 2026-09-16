"""Run independent decision checks and retain a reproducible, bounded record."""
import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import subprocess
import unittest

import test_c_layer_oracle
import test_new_energy_cross_validation
import test_new_energy_surfaces
import test_new_energy_matrix
from new_energy_matrix import expanded_cases, expanded_portfolios


ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "docs/validation/new-energy-cross-validation-results.json")
    args = parser.parse_args()
    modules = (test_c_layer_oracle, test_new_energy_cross_validation, test_new_energy_matrix, test_new_energy_surfaces)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(module) for module in modules)
    log = io.StringIO()
    with redirect_stdout(log), redirect_stderr(log):
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    paths = [
        *sorted((ROOT / "src/voyage_fuel").rglob("*.py")),
        *sorted((ROOT / "src/voyage_fuel/data").glob("*.csv")),
        ROOT / "src/voyage_fuel/static/app.js",
        ROOT / "src/voyage_fuel/templates/index.html",
        ROOT / "tests/e2e/test_mvp_flow.py",
        *(ROOT / "tools/validation" / name for name in (
            "c_layer_inputs.py", "c_layer_oracle.py", "test_c_layer_oracle.py",
            "new_energy_reference.py", "test_new_energy_cross_validation.py",
            "test_new_energy_surfaces.py", "run_new_energy_cross_validation.py",
            "new_energy_matrix.py", "test_new_energy_matrix.py",
        )),
    ]
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).splitlines(),
        "python": platform.python_version(),
        "packages": {name: importlib.metadata.version(name) for name in ("scipy", "numpy", "pypdf", "playwright")},
        "passed": result.wasSuccessful() and not result.skipped,
        "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped": len(result.skipped),
        "coverage": {
            "single_candidate_synthetic_cases": 60 + len(expanded_cases()),
            "expanded_single_candidate_categories": dict(Counter(case["category"] for case in expanded_cases())),
            "fixed_seed_multi_candidate_portfolios": 10 + len(expanded_portfolios()),
            "expanded_portfolio_sizes": [2, 3, 5, 8],
            "expanded_portfolios_checked_in_reverse_order": len(expanded_portfolios()),
            "relationship_checks": {"voyage_scales": 4, "price_scales": 3, "constraint_relaxation_steps": 10},
            "api_boundary_inputs": {"invalid_candidate": 10, "invalid_case": 6, "missing_prices": 3},
            "hand_multi_candidate_orderings": 3,
            "builtin_snapshot_cases": 1,
            "hand_surface_cases": test_new_energy_surfaces.SURFACE_CASE_COUNT,
            "surface_viewport_widths": [1440, 390],
            "mutated_outputs_detected": [
                "wrong_winner", "wrong_quantity", "wrong_cost", "wrong_savings_sign",
                "negative_ratio_tie", "wrong_missing_price_reason", "wrong_not_applicable_reason",
            ],
        },
        "tolerances": {
            "exact_absolute": "1e-20",
            "highs_objective_absolute": "1e-5",
            "highs_excludes_exact_only_boundaries": ["C-LP-17", "C-LP-18"],
            "expanded_highs_categories": [
                "price_reversal", "carbon_price_reversal", "energy_density",
                "simultaneous_constraints", "year_scope", "target_topology",
            ],
            "surface_hand_values": "literal displayed values; CSV exact decimal",
        },
        "limitations": [
            "Synthetic arithmetic fixtures; not real-voyage acceptance or a factor/legal audit.",
            "Exact vertices and HiGHS share reference coefficients, calibrated with separate hand literals.",
            "Mutation checks corrupt returned result objects; they do not rewrite the production algorithms.",
            "Surface checks cover six hand cases, not every synthetic input or every catalogue fuel.",
            "No annual FuelEU settlement, biomass qualification, RFNBO qualification or port classification audit.",
        ],
        "sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in paths},
        "test_output": log.getvalue(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(log.getvalue())
    print(f"Evidence: {args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
