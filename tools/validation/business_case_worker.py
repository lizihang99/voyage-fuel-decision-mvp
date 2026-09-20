"""Isolated reference process. Importing product modules is a hard error."""
import argparse
import importlib.abc
import json
from pathlib import Path
import sys


class ProductImportBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "voyage_fuel" or fullname.startswith("voyage_fuel."):
            raise ImportError("independent reference forbids production import: " + fullname)
        return None


def main():
    sys.meta_path.insert(0, ProductImportBlocker())
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    from business_case_reference import calculate_reference
    from business_case_schema import VERSION, DISCLAIMER, fingerprint, load_case, write_case, write_json
    if args.freeze:
        from business_case_inputs import cases
        inputs = cases()
    else:
        manifest = json.loads((args.root / "case-manifest.json").read_text(encoding="utf-8"))
        inputs = [load_case(args.root / entry["id"]) for entry in manifest["cases"]]
        for entry, case in zip(manifest["cases"], inputs):
            if entry["input_sha256"] != fingerprint(case):
                raise ValueError(case["id"] + ": manifest fingerprint mismatch")
    ids = [case["id"] for case in inputs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids")
    results = []
    for case in inputs:
        expected = calculate_reference(case)
        if args.freeze:
            write_case(args.root, case, expected)
        else:
            frozen = json.loads((args.root / case["id"] / "expected.json").read_text(encoding="utf-8"))
            if fingerprint(expected) != frozen["expected_sha256"]:
                raise ValueError(case["id"] + ": recalculated reference differs from frozen expectation")
        results.append({"case": case, "expected": expected})
    loaded = [name for name in sys.modules if name == "voyage_fuel" or name.startswith("voyage_fuel.")]
    if loaded:
        raise RuntimeError("reference isolation violated: " + repr(loaded))
    if args.freeze:
        write_json(args.root / "case-manifest.json", {
            "schema_version": 1, "reference_version": VERSION, "disclaimer": DISCLAIMER,
            "full_automatic_set": "All listed requests; compact is a subset, not additional inputs",
            "unit_contract": {
                "massTonnes": "tFuel", "lcv": "MJ/gFuel", "wtt": "gCO2eq/MJ",
                "co2/ch4/n2o": "gGHG/gFuel", "slip": "%", "rwd": "ratio",
                "pricePerTonne": "EUR/tFuel", "euaPricePerTCO2e": "EUR/tCO2e",
                "complianceImprovementValue": "EUR/tCO2e (synthetic reference value)",
            },
            "authority": ["docs/validation/business-case-input-design.md",
                          "docs/validation/business-case-coverage.md"],
            "cases": [{"id": c["id"], "family": c["family"], "compact": c["compact"],
                       "input_sha256": fingerprint(c), "coverage": c["coverage"]} for c in inputs],
        })
    write_json(args.output, {"production_modules_loaded": loaded, "results": results})


if __name__ == "__main__":
    main()
