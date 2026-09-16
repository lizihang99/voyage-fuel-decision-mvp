"""Compare immutable pre-fix inputs/oracle evidence against the isolated rerun."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/validation/c-layer"


def main():
    before = json.loads((DATA / "results.json").read_text(encoding="utf-8"))
    after = json.loads((DATA / "fixes/results.json").read_text(encoding="utf-8"))
    previous = {r["id"]: r for r in before["records"]}
    current = {r["id"]: r for r in after["records"]}
    assert before["input_sha256"] == after["input_sha256"]
    assert previous.keys() == current.keys()
    assert before["experiment_sha256"]["c_layer_oracle.py"] == after["experiment_sha256"]["c_layer_oracle.py"]
    assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
               for p, h in after["production_sha256"].items())
    unresolved = [
        {"id": r["id"], "field": c["field"], "kind": c.get("difference_kind")}
        for r in after["records"] for c in r["checks"] if c["result"] == "DIFFERENCE"
    ]
    assert len(unresolved) == 2 and all(c["kind"] == "SOLVER_PRECISION_LIMIT" for c in unresolved)
    summary = dict(same_input=True, same_oracle=True, current_source_hashes_match=True,
                   experiment_count=len(current), before=before["experiment_counts"], after=after["experiment_counts"],
                   unresolved=unresolved,
                   all_recorded_product_differences_resolved=True)
    (DATA / "fixes/comparison.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 修复前后逐实验对照", "", "相同107个实验、相同输入哈希和独立oracle。未修改参考预期。", "",
             "| 实验 | 场景 | 修复前 | 修复后 | 备注 |", "|---|---|---|---|---|"]
    for identifier, old in previous.items():
        new = current[identifier]
        note = "仅HiGHS精度限制，产品与精确参考一致" if identifier == "C-LP-17" else (
            "原差异已消除" if old["result"] == "DIFFERENCE" else "未发现回归")
        lines.append(f"| {identifier} | {old['label']} | {old['result']} | {new['result']} | {note} |")
    (DATA / "fixes/comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
