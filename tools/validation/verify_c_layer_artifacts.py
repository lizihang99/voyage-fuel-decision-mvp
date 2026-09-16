"""Persist lightweight verification output without running the full test suite."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/validation/c-layer"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    checks = {}
    checks["inputs_hash_matches"] = result["input_sha256"] == digest(OUT / "inputs.json")
    checks["production_hashes_match"] = all(digest(ROOT / p) == v for p, v in result["production_sha256"].items())
    checks["experiment_hashes_match"] = all(digest(Path(__file__).parent / p) == v
                                           for p, v in result["experiment_sha256"].items())
    checks["experiment_count_107"] = len(result["records"]) == 107
    checks["31_features_indexed"] = len(json.loads((OUT / "coverage.json").read_text(encoding="utf-8"))["functions"]) == 31
    checks["recorded_differences_not_hidden"] = sum(r["result"] == "DIFFERENCE" for r in result["records"]) == 13
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tools/validation", "-p", "test_c_layer_oracle.py", "-v"],
        [sys.executable, "-m", "unittest", "tests.test_constraints", "tests.test_economics",
         "tests.test_case_comparison", "tests.test_case_calculator", "-v"],
    ]
    executions = []
    for cmd in commands:
        run = subprocess.run(cmd, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
        executions.append(dict(command=cmd, returncode=run.returncode, stdout=run.stdout, stderr=run.stderr))
        print(run.stderr)
    artifact = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), checks=checks,
                    results_sha256=digest(OUT / "results.json"), executions=executions,
                    success=all(checks.values()) and all(x["returncode"] == 0 for x in executions),
                    meaning="Artifact and focused-test verification only; experiment differences remain unfixed.")
    (OUT / "verification.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checks": checks, "success": artifact["success"]}, ensure_ascii=True))
    return 0 if artifact["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
