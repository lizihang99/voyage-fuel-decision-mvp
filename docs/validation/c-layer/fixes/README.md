# C 层修复与验证记录

日期：2026-09-07。分支：`codex/c-layer-correctness-fixes`；基线：`fcf5ba6`。
工作目录：`D:\projects\工具MVP\.worktrees\c-layer-correctness-fixes`。

原始实验 `../results.json`、`../report.md` 为修复前历史快照，保留不覆盖。当前目录保存修复后证据。

## 修复范围

| 问题 | 处理 | 验收 |
|---|---|---|
| D1 达标优化遗漏上界 | 成本下降时取达标上界与约束上限的较小者；必要最优点进入报告；建议出口再次检查余额 | 合成案例目标比例恢复为0.46684；内置UCO_FAME→MGO案例不再建议未达标的100% |
| D3 临界余额符号与组分比例 | 输入Decimal以有理数作目标判定；临界比例向可行侧投影；组分质量精确保留共同质量比例；余额按精确残差计算 | 不把极小负余额当成零；RWD=2和普通分母均通过 |
| D2 极近切换点 | 有理数交点与区间比较；共同模型系数避免舍入制造伪切换点 | 真正1e-31间距的两个切换保留；原规格中的共点仍为一个有效切换 |
| V1 HiGHS精度限制 | 不修改产品，不隐藏差异 | 继续记录为SOLVER_PRECISION_LIMIT，产品与Fraction一致 |

未改变因子库、港口规则、EUA/FuelEU法规公式、年度边界、JSON字段、生产依赖或UI。数值实现精度改进会使极末尾Decimal位、临界方案ID、状态和必要报告点按修复后的正确值变化。

## 验证与数据

- `d1-red.json`：5个失败、2个既有行为通过，定位达标上界/报告/建议问题。
- `d1-green.json`：12项通过。
- `d3-red.json`：5个失败、1个通过，定位精确目标与质量比例问题。
- `d3-green.json`：19项通过。
- `d3-complement-red.json`：RWD=2的小比例补数丢位复现失败；已由精确补数修复。
- `d2-red.json`：单候选与跨候选极近切换点2项失败。
- `d2-green.json`：16项通过。
- `targeted-regression.json`：18项新增测试及相关约束/经济/案例/能源/FuelEU/规格回归，共68项通过。
- `b-layer-json-regression.json`：原有B层外部验证锚点和JSON契约25项通过；确认数值精度修正未破坏这些样例。
- `results.json`：同一107案例复跑；45项MATCH、61项MATCH_WITH_ROUNDING、1项DIFFERENCE。该差异仅为V1；2126项检查中1959一致、165尾差、2项求解器精度限制。
- `comparison.md` / `comparison.json`：107个实验逐项前后对照及输入、oracle、当前源文件哈希验证。
- `original-snapshot.json` / `original-unchanged.json`：原始main目录的分支、HEAD、未提交状态和可见文件哈希前后比较。
- `review-pure-use-red.json` / `review-pure-use-green.json`：独立审阅指出新增最优点绕过禁止纯用限制，两个测试先失败后通过。

实验输入和独立oracle未改。实验执行器仅增加 `--output-dir` 将修复后数据写到本目录，预期值和通过条件保持原样。比较结果中一个案例的检查数可随正确增加的报告方案点增长，因此逐字段检查总数与修复前不同。

补充环境说明：测试环境沿用Python3.12.14、SciPy1.16.2、NumPy2.3.3。规格矩阵测试需要当前临时Starlette环境的httpx2，已在忽略的临时依赖目录补充，不改pyproject.toml。没有运行全项目/浏览器/性能测试。

## 隔离与后续

原始项目仍在main，已有文档/实验未提交工作保留；修复只存在于本worktree。本分支未合并、未推送。不应将“所列实验无产品差异”等同于所有输入域完全正确。

独立审阅发现一项P2回归：新增最优点可能绕过 `allows_pure_use=False`。已在原报告点生成处补上同一纯用保护，并补充有价格、便宜改善候选的单航次/案例两项测试。审阅者独立重跑2/2通过，确认关闭该P2。未以近100%比例代替禁用纯用；独立审阅未指出其他确定回归。后续可审阅此分支再决定合并；无需直接改动原目录。

最终核验：原main的HEAD仍为 `fcf5ba6e5eea48b6588f735f24cfec6de76c0a66`，144个受检文件、未提交状态和分支均未改变。当前修复工作保留为本分支worktree的未提交改动，未执行commit、merge或push；这不等于已生成可供远端拉取的修复提交。

## 复现

在本worktree运行，Python路径替换为实际Python3.12：

```powershell
$env:PYTHONPATH = "D:/projects/工具MVP/tmp/c-layer-deps;$PWD/src"
python tools/validation/record_fix_evidence.py targeted-regression tests.test_c_layer_fixes tests.test_constraints tests.test_economics tests.test_case_comparison tests.test_case_calculator tests.test_energy tests.test_fueleu tests.test_spec_matrix
python tools/validation/run_c_layer_experiments.py --output-dir docs/validation/c-layer/fixes
# 实验退出码2：仅保留已知V1差异，不是基础设施失败。
python tools/validation/record_fix_evidence.py original-unchanged
```
