"""Record focused test output and confirm the original checkout is untouched."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT.parents[1]
OUT = ROOT / "docs/validation/c-layer/fixes"
sys.stdout.reconfigure(encoding="utf-8")


def snapshot():
    paths = subprocess.check_output(
        ["git", "-c", "core.quotepath=false", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=ORIGINAL).decode("utf-8").split("\0")
    return {
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ORIGINAL, text=True).strip(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ORIGINAL, text=True).strip(),
        "status": subprocess.check_output(["git", "status", "--porcelain=v1", "-z"], cwd=ORIGINAL).decode("utf-8"),
        "files": {p: hashlib.sha256((ORIGINAL / p).read_bytes()).hexdigest()
                  for p in sorted(set(paths)) if p and (ORIGINAL / p).is_file()},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("modules", nargs="*")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.label == "original-snapshot":
        data = snapshot()
    elif args.label == "original-unchanged":
        before = json.loads((OUT / "original-snapshot.json").read_text(encoding="utf-8"))
        now = snapshot()
        data = {"original_unchanged": now == before, "branch": now["branch"], "head": now["head"],
                "files_checked": len(now["files"])}
        if now != before:
            data["changed_files"] = [p for p in set(before["files"]) | set(now["files"])
                                     if before["files"].get(p) != now["files"].get(p)]
    else:
        cmd = [sys.executable, "-m", "unittest", *args.modules, "-v"]
        run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        data = dict(command=cmd, returncode=run.returncode, stdout=run.stdout, stderr=run.stderr,
                    timestamp=datetime.now(timezone.utc).isoformat())
        print(run.stderr)
    (OUT / f"{args.label}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data.get("returncode", 0 if data.get("original_unchanged", True) else 1)


if __name__ == "__main__":
    sys.exit(main())
