"""Generate audit tables and mechanically append C evidence to existing matrix."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/validation/c-layer"


def compact(ids):
    """Compress only contiguous IDs; never hide a missing experiment."""
    groups = defaultdict(list)
    for value in sorted(set(ids)):
        prefix, suffix = value.rsplit("-", 1)
        groups[prefix].append(int(suffix))
    rendered = []
    for prefix, numbers in groups.items():
        start = end = numbers[0]
        for n in numbers[1:] + [None]:
            if n is not None and n == end + 1:
                end = n
                continue
            rendered.append(f"{prefix}-{start:02d}" + (f"～{end:02d}" if end != start else ""))
            start = end = n
    return "、".join(rendered)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-matrix", action="store_true")
    args = parser.parse_args()
    result = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    matrix_path = ROOT / "docs/validation/external-validation-matrix.md"
    matrix = matrix_path.read_text(encoding="utf-8")
    functions = {}
    for line in matrix.splitlines():
        if re.match(r"\| M(?:07|08|09|11)-F\d\d \|", line):
            cells = [x.strip() for x in line.split("|")[1:-1]]
            functions[cells[0]] = cells
    evidence = defaultdict(list)
    for rec in result["records"]:
        for check in rec["checks"]:
            for feature in check["features"]:
                evidence[feature].append((rec["id"], check))
    assert len(functions) == 31
    assert not (set(functions) - evidence.keys())

    lines = ["# C 层逐实验与逐功能结果表", "",
             "由 `tools/validation/summarize_c_layer.py` 根据 results.json 生成；结果对应 2026-09-07 快照。",
             "每项检查保留原始预期、实际、误差及证据类型。表内一个实验可有多项检查；实验数不能解释为独立用户样本数。",
             "", "## 逐实验结果", "",
             "| 实验 | 场景 | 一致 / 尾差 / 差异检查数 | 结果 | 差异备注 |",
             "|---|---|---|---|---|"]
    for rec in result["records"]:
        counts = Counter(c["result"] for c in rec["checks"])
        diff_fields = [c["field"] for c in rec["checks"] if c["result"] == "DIFFERENCE"]
        kinds = {c.get("difference_kind") for c in rec["checks"] if c["result"] == "DIFFERENCE"}
        if rec["id"] == "C-LP-17":
            note = "SOLVER 精度不足；生产目标状态与精确参考一致"
        elif "DECIMAL_BOUNDARY_SIGN" in kinds:
            note = "约1e-49 t余额的严格符号差异；不按大额经济误差解释"
        elif rec["id"] == "C-ENV-07":
            note = "2个极近切换点合并为1个"
        elif diff_fields:
            note = "达标成本最优点或建议未满足目标"
        else:
            note = "—"
        lines.append(f"| {rec['id']} | {rec['label']} | {counts['MATCH']} / {counts['MATCH_WITH_ROUNDING']} / "
                     f"{counts['DIFFERENCE']} | {rec['result']} | {note} |")
    lines.extend(["", "## 逐功能汇总", "",
                  "按该功能的检查汇总，不把同一实验中其他功能的失败传播过来。"
                  "SOLVER 数值精度差异保留，但不记为生产失败。`部分独立交叉`仅表示所列样例，未穷尽该功能的全部输入和分支。",
                  "", "| 功能ID | 功能 | 全部实验及结果（同结果连续编号压缩） | 证据类型 | 结论 |",
                  "|---|---|---|---|---|"])
    coverage = {}
    notes = {}
    for feature, cells in functions.items():
        by_id = defaultdict(list)
        for identifier, check in evidence[feature]:
            by_id[identifier].append(check)
        grouped = defaultdict(list)
        for identifier, checks in by_id.items():
            code = "DIFFERENCE" if any(c["result"] == "DIFFERENCE" for c in checks) else (
                "MATCH_WITH_ROUNDING" if any(c["result"] == "MATCH_WITH_ROUNDING" for c in checks) else "MATCH")
            grouped[code].append(identifier)
        summary = "；".join(f"{compact(ids)}={code}" for code, ids in sorted(grouped.items()))
        types = sorted({c["evidence"] for _, c in evidence[feature]})
        real_diffs = [c for _, c in evidence[feature] if c["result"] == "DIFFERENCE"
                      and c.get("difference_kind") != "SOLVER_PRECISION_LIMIT"]
        solver_limits = any(c.get("difference_kind") == "SOLVER_PRECISION_LIMIT" for _, c in evidence[feature])
        status = "存在差异" if real_diffs else (
            "契约补充验收" if types == ["CONTRACT"] else "部分独立交叉")
        note = "；浮点极近边界以精确参考复核" if solver_limits else ""
        lines.append(f"| {feature} | {cells[2]} | {summary} | {' / '.join(types)} | {status}{note} |")
        coverage[feature] = status
        notes[feature] = (summary, status, note)
    (OUT / "experiment-tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "coverage.json").write_text(json.dumps(
        {"function_count": len(coverage), "counts": dict(Counter(coverage.values())), "functions": coverage},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.sync_matrix:
        # Mechanical update scoped to the 31 C rows only, preserving historical evidence.
        updated = []
        for line in matrix.splitlines():
            m = re.match(r"\| (M(?:07|08|09|11)-F\d\d) \|", line)
            if m:
                feature = m.group(1)
                cells = [x.strip() for x in line.split("|")[1:-1]]
                old_evidence = cells[3].split("；本轮C验证：")[0]
                old_note = cells[4].split(" 本轮C验证：")[0]
                summary, status, note = notes[feature]
                cells[3] = old_evidence + "；本轮C验证：" + summary
                cells[4] = old_note + " 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。" + note
                cells[5] = status
                line = "| " + " | ".join(cells) + " |"
            updated.append(line)
        matrix_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    print(json.dumps(dict(Counter(coverage.values())), ensure_ascii=True))


if __name__ == "__main__":
    main()
