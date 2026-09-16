# C 层独立交叉验证实验计划与执行台账

> **For agentic workers:** 按本计划逐项执行并记录证据。本任务是验证实验，不修改生产实现；用户已确认在当前会话执行。使用 writing-plans 组织任务，verification-before-completion 核实结果。无需另开产品开发分支或提交现有未提交工作。

**Goal:** 独立核验 M07/M08/M09/M11 的数值求解与决策行为，保存输入、独立输出、项目输出及差异，更新功能矩阵。

**Architecture:** 被测端使用现有 Python 公开计算入口；参考端不导入 voyage_fuel，以两个组分吨数建立线性约束，用 SciPy/HiGHS 求解。Fraction 精确顶点法补充边界判定，Brent 求根复核临界价格，独立有效区间法核验固定方案下包络。

**Tech Stack:** Python 3.12；实验专用 SciPy 1.16.2 / NumPy 2.3.3；标准库 Fraction、Decimal、unittest、JSON。依赖安装到 git 忽略的 tmp/c-layer-deps，不改生产依赖。

**Spec:** `docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md` §10–12；`docs/validation/external-validation-matrix.md` C 层 31 个功能点。

## 全局约束与证据边界

- 固定 B0 物理能源、质量混兑、线性吨价；预算为燃料加 EUA 相对 B0 的增量。
- FuelEU 仅为单航次法规估算；执行条件待确认。验证不涉及独立物理 WtW、正式年度合规或采购可执行性。
- 合成数据用于隔离 C 层算法，不宣称认证燃料批次或再次核验因子库。
- 数值实验输入仅从固定数据集读取；参考端不得调用生产能源、排放、constraints/economics/case_comparison 函数。
- 内部状态验收不升级为外部平台验证；第三方求解器一致单独标记。
- 保留发现的真实差异，不在实验过程中修正生产代码或改预期迁就实现。
- 不运行全项目测试；仅运行实验自检和四个 C 层相关 unittest 模块。

## 文件分工

| 文件 | 责任 |
|---|---|
| `tools/validation/c_layer_oracle.py` | 不依赖生产包的 LP、精确顶点与有效区间参考算法 |
| `tools/validation/test_c_layer_oracle.py` | 手算锚点、不可行、分式目标与下包络自检 |
| `tools/validation/c_layer_inputs.py` | 固定合成数据与内置路径快照生成器 |
| `tools/validation/run_c_layer_experiments.py` | 固定输入、被测适配、差分比较、生成机器结果 |
| `tools/validation/summarize_c_layer.py` | 机械生成完整实验/功能表并同步矩阵的31个C行 |
| `tools/validation/verify_c_layer_artifacts.py` | 轻量自检、聚焦测试与源文件/输入哈希复核 |
| `docs/validation/c-layer/inputs.json` | 确定性案例与固定种子随机案例，全部保存输入 |
| `docs/validation/c-layer/results.json` | 环境、输入/源文件哈希、原始输出、逐字段预期/实际、偏差 |
| `docs/validation/c-layer/report.md` | 统一实验表、差异复现、31 功能覆盖与剩余边界 |
| `docs/validation/c-layer/experiment-tables.md` | 每个实验和每个功能的完整统一结果表 |
| `docs/validation/c-layer/coverage.json` | 31功能覆盖分类机器索引 |
| `docs/validation/c-layer/verification.json` | 自检与聚焦测试原始输出、命令、退出码和哈希检查 |
| `docs/validation/external-validation-matrix.md` | 原有实验保留，C 行追加本轮证据 |

## 实验定义

### C-LP：约束与目标（M07，M11-F03/F04/F05）

参考变量为 `u=基准吨数/M0`、`v=候选吨数/M0`：

```text
u + (Lc/Lb)v = 1
u,v >= 0
(1-cap)v - cap*u <= 0
v <= supply/M0
Kb*u + Kc*v <= Kb + budget/M0
(Nb-target*Db)u + (Nc-target*Dc)v <= 0  [仅达标任务]
```

最小/最大候选用量对应最小/最大质量比例；成本目标直接使用 `Kb*u+Kc*v`。GHGI 最小化使用 Charnes–Cooper 变换，保留 RWD 分母。精确有理数枚举顶点核对临界可达性和最优点。

- [x] 保存普通、成本下降、零供应/预算、三个约束、无解、不可达、B0已达标且候选恶化、端点达标、RFNBO奖励、缺价、2024/2030/范围零案例。
- [x] 加入固定种子32个随机案例；不作覆盖率或统计正确率外推。
- [x] 比较 xBudget/xSupply/xCap/目标状态/最低比例/达标成本最低/最大改善/最低成本；保存 HiGHS 状态及残差。

### C-EC：临界价格与下包络（M08）

- [x] 独立成本函数使用燃料吨数×报价及独立单位排放计算；Brent 求非负临界价格，精确有理数检查零分母、负阈值和全区间并列。
- [x] 临界价代回并验证两侧成本符号；候选燃料临界价在两个不同正比例重复核验。
- [x] 对每条 `cost - V*improvement` 直线求同时不高于其余所有直线的 V>=0 区间；比较产品的全局切换点。
- [x] 覆盖无切换、被支配交点、平行、重合、三线共点、V=0、极近交点；记录并列与零宽区间，不强行选相同 ID。

### C-CASE：端到端比较与状态（M09/M11，M07-F08/F09）

- [x] 使用固定合成燃料分别计算候选与共享 B0；独立重算每条输出成本、GHGI、改善、delta、百分比。
- [x] 对固定输出集检查可行性筛选、B0成本排名、达标最便宜与最大改善候选；与连续 LP 最优值比较以检测漏掉必要报告点。
- [x] 检查候选置换、局部阻断、缺价、并列、零基线、条件式建议及执行状态。状态实验单独标记 CONTRACT，不作为 HiGHS 外部证据。

## 执行顺序与判据

1. [x] 写参考算法手算自检，先确认尚无实现导致失败，再实现并运行自检。新增B0缺价自检先失败后修正参考端。
2. [x] 执行 C-LP，保存最小复现；检查参考建模、单位、残差再归因。
3. [x] 执行 C-EC 和 C-CASE，保存 JSON 原始数据；额外通过内置路径和JSON入口确认D1。
4. [x] 运行四个聚焦模块：test_constraints、test_economics、test_case_comparison、test_case_calculator，25项通过。
5. [x] 检查 31 功能点映射、生成报告、更新原矩阵；核验生产源文件哈希未变化。最终记录见 verification.json。

数值比较：普通 LP 比例绝对误差 1e-8、成本绝对误差 1e-5 与相对 1e-9 取较宽者；Fraction/Decimal 对照比例 1e-24。目标可达性、非负余额、缺值、原因码不能用普通浮点容差覆盖；近边界另列精确判定。并列解比较目标值和可行性，不要求求解器返回相同代表点。

结果码：`MATCH`、`MATCH_WITH_ROUNDING`、`DIFFERENCE`、`NOT_TESTED`。证据类型另列 `SOLVER`、`INDEPENDENT_EXACT`、`CONTRACT`，不混淆外部行业认证。

## 执行记录

计划制定并执行于 2026-09-07。107个实验、2115项检查已完成；13个差异实验涉及D1达标优化缺陷、D2极近切换点、D3有限Decimal边界以及V1浮点求解器精度限制。完整归因见 `docs/validation/c-layer/report.md`。

实验完成不代表产品问题已修复。本轮仅改实验与记录，生产代码保持不变；没有提交或推送现有工作。
