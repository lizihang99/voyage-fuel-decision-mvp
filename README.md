# 航次燃料决策 MVP

单航次 FuelEU / EU ETS 燃料方案计算与比较工具。

项目面向船东、租家、燃油采购和燃料供应相关人员。用户给定一条航段、当前基准燃料和若干候选燃料，系统比较各方案的燃料成本、EU ETS、FuelEU 和约束结果，帮助团队判断哪些方案值得进一步讨论。

当前版本属于航次级 MVP，适用于测算、比较和内部讨论，不能替代年度合规结算、采购审批或供应交付确认。

![航次燃料决策产品全景](./docs/diagrams/product-overview.svg)

*图 1：从航次问题到方案比较、条件式建议和结果交付。*

## 1. 用户怎么使用

![一次航次决策的用户路径](./docs/diagrams/user-journey.svg)

*图 2：一次航次决策的六个步骤，以及调整条件后的重新计算路径。*

一次使用围绕一个“航次决策案例”展开。案例包含报告年份、两个相邻有效 `Port of Call`、基准燃料、候选方案、价格和约束。所有候选方案使用同一航段和同一能源口径比较。

需要理解的核心概念：

- **基准方案 B0**：继续使用当前基准燃料的方案，也是所有比较的参照点；
- **候选方案**：某种替代燃料、供应商报价或质量混兑方案；
- **EU ETS 与 EUA**：EU ETS 是欧盟碳排放交易体系，EUA 是排放一吨 CO2e 对应的配额；系统估算本航次需要的配额和成本；
- **FuelEU 与 GHGI**：FuelEU 是欧盟航运燃料法规，GHGI 是法规口径下的温室气体强度；系统只做本航次的法规比例估算；
- **条件式建议**：在成本优先、达到 GHGI 参考线或合规改善等不同目标下给出的方案；
- **执行条件**：认证、船舶兼容性、供应和交付条件仍待人工确认的状态。

系统不提供一个脱离目标和约束的“综合最优”。目标或约束变化后，推荐方案可能随之变化。

## 2. 主要功能

- **航次与范围判断**：根据报告年份、港口身份和航段关系判断 EU ETS、FuelEU 的适用范围与比例；
- **燃料方案计算**：计算单燃料和质量混兑方案的能量、燃料用量、排放、EU ETS、FuelEU 与成本；
- **多方案比较**：比较 B0 与一个或多个候选方案，展示成本、EUA、GHGI、合规余额及相对变化；
- **约束与边界**：处理预算、供应量、最大混兑比例等条件，并展示目标比例、成本边界和切换点；
- **结果交付**：在决策工作台查看结论和依据，导出同一次成功计算的 CSV / PDF。

当前覆盖 2024-2030 年、两个相邻有效 `Port of Call` 和 36 条本期航行燃料路径。`ELECTRICITY_OPS` 保留在完整因子库中，但不进入本期航段输入。

## 3. 项目结构

下图展示规则、案例、计算、决策和交付之间的关系：

![计算流程与支撑关系](./docs/diagrams/calculation-flow.svg)

*图 3：从基础信息、统一口径、逐方案计算到比较和交付。该图表达信息与计算关系，不表示代码调用顺序。*

读图时只需要看四件事：

- 法规、港口和燃料数据先确定计算依据；
- 所有方案先统一年份、航段、能源需求和币种；
- 每个方案分别计算，再放到同一张表里比较；
- 页面和报告展示结果，同时保留数据来源、问题说明和执行条件限制。

| 产品模块 | 主要位置 | 作用 |
| --- | --- | --- |
| 页面与交互 | `src/voyage_fuel/templates/`、`src/voyage_fuel/static/` | 输入、工作台、方案详情和结果图表 |
| 接口与案例契约 | `src/voyage_fuel/web.py`、`contracts.py`、`json_io.py` | HTTP 接口、输入校验、结果结构和短期导出快照 |
| 港口与法规范围 | `src/voyage_fuel/ports.py`、`port-identity-mapping.mjs`、`port-scope-rates.mjs` | 港口身份、航段关系和范围比例 |
| 燃料与证据 | `src/voyage_fuel/factors.py`、`custom_factors.py`、`provenance.py` | 燃料路径、因子、资格、来源和版本追溯 |
| 计算与决策 | `src/voyage_fuel/calculator.py`、`case_calculator.py`、`case_comparison.py` | 单方案计算、多候选比较和条件式建议 |
| 约束与经济性 | `src/voyage_fuel/constraints.py`、`economics.py` | 预算、供应、比例、临界价格和切换点 |
| 报告与验证 | `src/voyage_fuel/reports.py`、`tests/`、`tools/validation/` | CSV/PDF 输出、自动化测试和独立验证 |

产品能力按“港口范围 → 燃料因子 → 单方案计算 → 多方案决策 → 页面和报告”排列。修改某个规则前，先确认它所在的层，再查看对应规格和测试。

更完整的规则、计算和交付关系见 [计算流程与支撑关系图](./docs/diagrams/calculation-flow.svg)，图表生成脚本位于 [generate_diagrams.py](./tools/diagrams/generate_diagrams.py)。

## 4. 结果边界

- 结果是法规口径的航次级比例估算，不等于正式年度结算结果；
- FuelEU 指示性金额用于辅助比较，不代表本航次真实应付罚款；
- 方案可以计算，只说明数学测算成立，认证、兼容性、供应和交付仍需确认；
- 缺少价格时可以比较排放和合规表现，但不能完成完整经济排序；
- 当前不覆盖年度罚款、Banking、Borrowing、Pooling、船队优化、采购执行、货币换算、多候选燃料同时混兑和独立物理生命周期 WtW；
- 证据状态来自输入或已整理因子，系统不会自动核验证书真实性。

所有方案的执行状态统一保留待确认信息，不能把航次级推荐直接当作采购结论。

Boundary contract: voyage-level proportional estimate; not a formal annual penalty; not a procurement recommendation; independent physical lifecycle WtW reduction is not provided. `EXECUTION_CONDITIONS_PENDING` remains until execution conditions are confirmed.

## 5. 快速启动

要求：Python 3.12+、Node.js。Windows PowerShell 下在仓库根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[dev]"
.\.venv\Scripts\voyage-fuel-web.exe --host 127.0.0.1 --port 8000
```

浏览器访问：

- `http://127.0.0.1:8000/?view=workbench`：决策工作台；
- `http://127.0.0.1:8000/`：默认计算页面；
- `http://127.0.0.1:8000/health`：健康检查，预期返回 `{"status":"ok"}`。

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

用双候选样例完成一次计算：

```powershell
$body = Get-Content -Raw .\tests\fixtures\multi_candidate_case.json
$result = Invoke-RestMethod http://127.0.0.1:8000/api/calculate `
  -Method Post -ContentType "application/json" -Body $body
$result | ConvertTo-Json -Depth 20
```

计算接口为 `/api/calculate`；结果导出接口为 `/api/export/csv` 和 `/api/export/pdf`。导出时，将计算响应中的 `result_snapshot_id` 值写入请求字段 `resultSnapshotId`。

交接前运行完整测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/frontend/*.test.mjs port-scope-rates.test.mjs port-identity-mapping.test.mjs
```

浏览器端到端测试位于 `tests/e2e/`，运行前安装 Playwright Chromium：

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest tests/e2e -q
```

## 6. 接手入口

建议按以下顺序阅读：

1. [项目目标与总体架构](./项目目标与总体架构.md)：产品目标、核心能力和长期边界；
2. [决策工作台设计](./docs/superpowers/specs/2026-09-17-decision-workbench-design.md)：用户路径和结果组织；
3. [港口比例功能说明](./港口比例功能说明.md)：港口身份和范围规则；
4. [燃料因子库规范](./燃料因子库规范.md)：燃料路径、因子和证据；
5. [MVP 计算规格](./docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md)：公式、单位、状态和接口契约；
6. `docs/validation/`：交叉验证、外部验证和业务案例证据。

接手时先执行 `git status --short`，启动工作台，用双候选样例完成一次计算和导出，再运行完整测试。当前工作台已完成技术验收；真实业务使用者仍需确认推荐、手动查看和航次级边界不会被误读。业务验收完成前，不应把项目描述为正式采购建议或年度合规结算工具。
