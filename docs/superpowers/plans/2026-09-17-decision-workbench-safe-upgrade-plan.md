# 航次燃料决策工作台安全升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有页面升级为目标驱动、方案联动的工作台，补充可解释图表，同时保护计算口径、已有功能、结果精度和快照导出。

**Architecture:** 一套计算内核和原始结果，上层使用只读展示模型联动目标、方案列表与图表。保留旧界面，通过显式预览入口渐进接入；推荐口径、输入序列化、结果失效和导出通过独立关卡后才能切换默认入口。

**Tech Stack:** 现有 Python 3.12+、FastAPI、Jinja2、原生 JavaScript/ES modules、CSS、SVG、ReportLab；测试沿用 unittest/pytest、Playwright、Node 内置测试运行器。不引入前端框架、数据库或在线图表服务。

**Spec:** [航次燃料决策工作台设计](D:/projects/工具MVP/docs/superpowers/specs/2026-09-17-decision-workbench-design.md)。执行者同时阅读该设计与现有计算规格，不得仅凭界面草图实现业务判断。

**Status:** 2026-09-17，任务 0-4 的主要实现、任务 5 的兼容验证和任务 6 的自动化回归已完成。新版工作台仍为显式预览入口，默认继续使用旧版；业务用户验收和默认入口切换尚未执行。

## Global Constraints

- 计算公式、默认因子、港口制度规则、同能源比较和质量混兑口径不因 UI 改版改变。
- 当前模型成本保持“燃料采购成本 + EU ETS 成本”；FuelEU 指示性金额不进入模型成本、预算或现金节省。
- 目标为成本最低、达到当年 GHGI 参考线的最低成本、最大合规改善；不新增综合评分或综合最优。
- 执行状态保持 `EXECUTION_CONDITIONS_PENDING`，不得生成已可执行或采购结论。
- 页面、CSV、PDF 使用同一次原始 `DecisionCaseResult`；导出继续要求 `resultSnapshotId`。
- API 比例仍为 0 到 1 的质量比例，新 UI 百分数转换使用十进制字符串，不降低内部精度。
- 显示精度、目标切换、查看方案不能改变原始值、服务端排序、状态或推荐。
- 保留 B0-only、候选错误隔离、高级自定义、资格回退、空值原因和证据追溯。
- 不新增年度结算、OPS、换汇、云历史、自动证书认证或多种候选同时混兑。
- 所有阶段保留已有未提交修改；不得使用 `git reset --hard`、整文件回退或清理未跟踪文件恢复环境。
- 不自动提交、推送、合并或覆盖现有服务。需要提交基线或发布时单独取得授权。

---

## 1. 当前基线及已知风险

### 1.1 核对范围

2026-09-17 编写时：

- 工作目录：`D:\projects\工具MVP`。
- 分支：`codex/safe-decision-contract-fixes`。
- HEAD：`8e465fa3a5e890c19c893f0945d5186eacafb2fa`。
- 工作区包含尚未提交的安全修复、目标对齐修复、测试、E2E 产物和产品总纲更新。**HEAD 单独不代表本次升级基线。**
- 当前结果由 `case_calculator.py` 汇总，`case_comparison.py` 输出案例经济结果、条件建议和摘要；页面 `app.js` 将多个摘要依次展示。
- `web.py` 已采用服务端结果快照，30 分钟有效期、最多 32 份、进程内保存；重启或淘汰后需要重新计算。

本次对话前序记录的验证结果为 Python 非 E2E 221 项、E2E 22 项、Node 29 项通过；这些是历史结果，本轮文档编写未重跑。实施起点必须重新执行并记录数量、失败、解释器与当前 diff。

### 1.2 必须先解决的文档和语义分歧

1. 旧安全计划仍有“导出重新计算/成功输入快照”的描述；本轮基线以实际 `web.py`、README 和目标对齐测试中的**服务端结果快照**为准。
2. 新能源 spec 中“旧 API/导出继续可用”不能解释为恢复旧的完整输入导出请求。当前兼容基线已经是 `resultSnapshotId`，需在本轮文档收口时写明例外和迁移说明。
3. 前序页面实测出现过案例摘要有“最大合规改善”方案、候选级推荐却不可用的现象。它可能涉及报告集合与连续约束边界的不同含义，尚不能仅凭该现象断定算法错误。
4. 当前页面按方案 ID 查找推荐，多个目标选择同一方案时可能拿到不对应目标的原因。新展示模型必须按目标类型和候选/方案身份关联。

第 3 项须在任务 0 复现并区分作用范围。若不能在既有契约中解释一致，则先形成有失败测试的独立缺陷修复，不得靠改标题或忽略 `UNAVAILABLE` 掩盖。业务口径需要变化时停止对应目标交付并向用户确认。

## 2. 改动地图

以下新文件均为**计划新增**，本计划不宣称已存在。

| 文件 | 责任与允许改动 |
| --- | --- |
| `src/voyage_fuel/web.py` | 仅增加白名单界面选择和模板上下文；计算、导出端点保持合同 |
| `src/voyage_fuel/templates/index.html` | 保留旧分支，在新模式包含工作台结果片段，复用已有表单和消息容器 |
| `src/voyage_fuel/templates/workbench_results.html` | 新工作台目标、列表、详情、图表与证据区域；不复制领域公式 |
| `src/voyage_fuel/static/app.js` | 保留输入校验、请求序号、候选编辑、快照导出；加入明确的展示适配入口 |
| `src/voyage_fuel/static/display-values.mjs` | 抽取现有精确格式化函数，新增百分数无损转换；新旧界面共用 |
| `src/voyage_fuel/static/workbench-model.mjs` | 原始结果到只读视图模型；目标引用、查看状态、原因码和图表数据映射 |
| `src/voyage_fuel/static/workbench-view.mjs` | 目标、方案、详情联动与生命周期；不发起计算或导出请求 |
| `src/voyage_fuel/static/workbench-charts.mjs` | SVG 图表绘制、键盘选择、文本替代与销毁 |
| `src/voyage_fuel/static/workbench-labels.mjs` | 中文显示名称、目标及已知状态翻译；保留原 ID 与原码 |
| `src/voyage_fuel/static/workbench.css` | 仅在 `[data-view="workbench"]` 下生效，避免污染旧版 |
| `src/voyage_fuel/reports.py` | 首期不改数据合同、不嵌入图表；只验证同源结果与完整案例导出 |
| `tests/test_workbench_page.py` | 模式路由、模板、静态资源与降级入口 |
| `tests/test_workbench_contracts.py` | 原结果、目标引用、推荐作用范围与快照导出契约 |
| `tests/frontend/*.test.mjs` | 使用 Node 内置测试，验证纯展示模型、转换、图表数据映射 |
| `tests/e2e/test_workbench_flow.py` | 新工作台真实交互、输入往返、目标联动、无候选/错误状态 |
| `tests/e2e/test_workbench_charts.py` | 图表数值、键盘、移动端、空状态与截图 |
| `tests/e2e/test_mvp_flow.py` | 测试 helper 增加显式 view 参数，旧用例仍锁定旧入口 |
| `pyproject.toml` | 核对新 `.mjs` 和 HTML 是否进入安装包；优先维持当前扁平静态文件布局 |

`emissions.py`、`energy.py`、`constraints.py`、`economics.py`、`factors.py`、`ports.py` 和数据表均不属于 UI 升级编辑范围。若任务 0 证实独立业务缺陷，必须单列修复和验收，不能夹带到布局提交。

## 3. 接口与数据流冻结

### 3.1 页面入口

预览使用 `/?view=workbench`，旧版使用 `/?view=legacy`；无参数时读取本地配置 `VOYAGE_FUEL_UI`，首期默认值为 `legacy`。仅允许这两个值；其他查询值返回 422。环境配置值无效时回退 `legacy` 并记录配置警告，不把用户输入直接作为模板路径。

模板通过 `body[data-view]` 选择呈现。旧页面的 `/api/calculate` 和 `/api/export/*` 不因界面选择改变。

不复制整份旧 `app.js` 做新控制器，也不依赖隐藏旧结果 DOM 才能让新页面运行。必须将结果绘制和清空操作分发到当前展示适配器；旧版沿用原绘制函数。

### 3.2 最小模块接口

以下为本计划定义的新增接口，供后续任务使用，不是已有 API：

| 模块 | 导出函数签名 | 返回与副作用 |
| --- | --- | --- |
| `display-values.mjs` | `percentInputToRatio(text)` | canonical 十进制字符串；空输入返回 null；非法输入抛错 |
| `display-values.mjs` | `ratioToPercentInput(text)` | 无损百分数文本；null 返回空字符串 |
| `display-values.mjs` | `formatDecimalStringScaled(value, decimals, power10 = 0)` | 保留已有格式化输出 |
| `workbench-model.mjs` | `buildWorkbenchModel(result, submittedInput)` | 下述只读视图模型，不修改输入对象 |
| `workbench-model.mjs` | `selectGoal(model, goal)` | 返回新模型，不修改原模型与原始结果 |
| `workbench-model.mjs` | `selectScenario(model, scenarioId)` | 返回新模型；未知 ID 保持原选择并报告不可用状态 |
| `workbench-model.mjs` | `buildChartData(result, scenarioId)` | 返回成本、GHGI、散点数据与可用性原因；不做领域重算 |
| `workbench-charts.mjs` | `renderCharts(root, chartData, onScenarioSelect)` | 返回 `cleanup()`；选择图点时仅回调已有方案 ID |
| `workbench-view.mjs` | `createWorkbenchView(root, callbacks)` | 返回下述展示生命周期对象 |

展示生命周期对象包含 `render(result, submittedInput, display)`、`clear(status)`、`setDisplay(display)` 和 `destroy()`；callbacks 为 `onEditInputs()`、`onOpenEvidence()`。功能要求、算法边界和测试断言以下文任务为准。

`goal` 仅允许 `cost`、`target`、`improvement`。模型包含：

```text
activeGoal
recommendedScenarioId: string | null
selectedScenarioId: string | null
selectionSource: "goal" | "manual"
goalAvailability: "available" | "unavailable" | "inconsistent" | "not_applicable"
goalReasonCodes: string[]
scenarioById: Map<string, 原始 CaseScenario>
submittedInput: 本次成功请求的只读副本
```

提交的输入副本仅用于名称和输入摘要，不代替服务端原始结果，也不成为导出来源。候选自定义名称必须取自成功请求，不使用后来修改的表单值。

金额、比例与状态的数据来源：

| 展示内容 | 原始字段或规则 |
| --- | --- |
| 目标方案 | `decision_summary` 中三类方案 ID，与 `economics` 对应字段核对 |
| 目标原因 | `recommendations` 的目标类型及作用范围；不能仅按 `scenario_id` 查第一条 |
| 吨数和质量占比 | 选中 `scenarios[].result` 的质量字段和 `ratio` |
| 模型成本与净变化 | `result.model_cost` 与 `deltas.model_cost.delta` |
| 燃料成本变化、EU ETS 成本变化 | `deltas.fuel_cost.delta`、`deltas.eua_cost.delta` |
| 参考线、GHGI、余额 | 选中 `result.fuel_eu`；界面不自行计算目标达成 |
| 指示性金额 | `result.fuel_eu.indicative_penalty_eur`，EUR 单列 |
| 空值原因 | `field_reasons`、原始 issue/状态，查无明确理由时显示“原因未提供” |

案例级赢家与候选级建议的作用范围必须先核清。不同候选不可用不应误伤可用赢家；同一作用范围确实矛盾才进入 `inconsistent`，不得由前端重排赢家。

## 4. 实施任务与关卡

每个任务按“失败测试 -> 最小实现 -> 聚焦测试 -> 检查差异”推进。每次仅由一个执行者修改 `app.js`/`index.html`，纯模型、图表和测试可在接口固定后并行。每个任务结束形成独立检查点；未经授权不执行提交。

### 任务 0：保护基线，核清推荐作用范围

**文件：**读取现有实现与测试；新增 `tests/test_workbench_contracts.py`；记录写入 `output/workbench-upgrade/`，不得覆盖已跟踪 E2E 产物。

**输入/产出：**输入为当前工作树而非单独 HEAD；产出为可恢复的文件清单、基线测试记录和目标契约结论。

- [ ] 记录 `git status --short`、`git rev-parse HEAD`、`git diff --stat`，枚举已跟踪修改和未跟踪文件。
- [ ] 对即将编辑的文件保存带哈希的副本，并保存 binary diff；diff 不包含未跟踪文件，后者必须单独备份。用 PowerShell 原生文件命令，备份路径限定在 `output/workbench-upgrade/baseline/`；不得将凭据或无关用户文件放入备份。
- [ ] 新建 worktree 之前确保未提交安全修复、总纲更新和新增测试均可恢复。未获得基线提交授权时不得只从 HEAD 新开工作树开始升级。
- [ ] 重跑第 6 节现有测试，记录解释器与输出；环境错误与业务失败分别记录。
- [ ] 增加目标契约测试，复现 `maxBlendRatio="1"`、`allows_pure_use=False`、指定比例 `"0.2"` 场景，以及最大比例 `"0.3"` 对照场景。
- [ ] 区分“固定报告集合内最佳”“候选连续最大改善边界”“候选推荐可用性”；确认 UI 应显示的准确作用范围。不同语义不强行判成相等。
- [ ] 若发现真实矛盾，先做独立失败用例及最小修复评审；原始数值预期的变化必须有计算规格依据。

契约测试至少包含以下可执行断言：

```python
def test_b0_only_does_not_create_candidate_advice():
    from fastapi.testclient import TestClient
    from voyage_fuel.web import app
    from tests.test_goal_alignment_fixes import payload

    response = TestClient(app).post("/api/calculate", json=payload(candidates=[]))
    assert response.status_code == 200
    result = response.json()
    assert [row["scenario_id"] for row in result["scenarios"]] == ["B0"]
    assert result["recommendations"] == []
    assert result["decision_summary"] is None
    assert result["result_snapshot_id"]
```

该基线用例应已通过。新增失败用例应来自推荐作用范围的实际复现，不能为了满足“红灯”流程而写错误业务预期。

**关卡 G0：**基线可恢复、旧测试通过、目标语义已确定。未满足时允许做独立草图，不得接入真实推荐并声称升级完成。

### 任务 1：建立新旧入口与展示适配边界

**文件：**修改 `web.py`、`index.html`、`app.js`；新增 `workbench_results.html`、`workbench-view.mjs`、`workbench.css`、`tests/test_workbench_page.py`。

**输入/产出：**接收原响应和成功输入副本；生成不影响旧 UI 的工作台入口与 `createWorkbenchView()` 生命周期。

- [ ] 先写路由测试：默认旧版、显式新版、显式旧版、非法模式 422、两种模式静态文件均可获取。
- [ ] 运行 `.\.venv\Scripts\python.exe -m pytest tests/test_workbench_page.py -q`，确认新增模式断言在改动前失败。
- [ ] 路由只传 `view_mode`，模板使用白名单分支。保留旧结果 HTML 分支，新分支不生成旧结果容器。
- [ ] 在 `app.js` 的初始化流程中按模式加载适配器，完成加载后才启用提交；模块失败时禁用计算并显示旧版入口，不留下半初始化表单。
- [ ] 将 render、clear、精度重绘分发到适配器；共享原请求、错误隔离、`requestSerial` 和导出逻辑。不得对不存在的旧 DOM 节点继续写入。
- [ ] 新样式限定 `[data-view="workbench"]`；旧版不加载新 CSS，不更换旧版布局。
- [ ] 旧 E2E helper 增加 `view="legacy"` 默认参数，新用例传 `workbench`，两套测试持续可运行。

```python
def test_explicit_workbench_route():
    from fastapi.testclient import TestClient
    from voyage_fuel.web import app

    response = TestClient(app).get("/?view=workbench")
    assert response.status_code == 200
    assert 'data-view="workbench"' in response.text
    assert 'id="workbench-root"' in response.text
```

**关卡 G1：**旧版页面/API/安全 E2E 无回归；新模式加载错误可见且不会触发错误计算或导出。仅 DOM 元素存在不算完成。

### 任务 2：输入分层、名称映射与百分数转换

**文件：**修改 `app.js`、`index.html`；新增 `display-values.mjs`、`workbench-labels.mjs`、`tests/frontend/display-values.test.mjs`；扩展 `test_workbench_flow.py`。

**输入/产出：**新界面百分数输入到旧 API 十进制比例；候选 ID 不变，中文名称仅用于显示。

- [ ] 先写百分数双向转换、空值、0、100、负数、超过 100、非法字符、长精度和重复切换的 Node 测试。
- [ ] 将现有 `formatDecimalStringScaled` 原样抽取到共享模块，保留精度行为；共享加载完成后再绑定新旧页面事件。
- [ ] `percentInputToRatio()` 对空字符串返回 null；仅接受非负十进制文本，校验 0 到 100，并以字符串移位或 BigInt 完成除以 100。多比例字段按逗号分隔逐项转换，错误指出具体项。
- [ ] `ratioToPercentInput()` 无损转换已有 canonical 比例。不得从已格式化的四位小数标签恢复输入，也不得读写 `Number(value) / 100` 作为业务数据。
- [ ] 新模式使用带 `%` 单位的输入，旧模式继续使用原 0 到 1 输入。模式判断集中在序列化/回显边界，其他校验不再重复乘除 100。
- [ ] 新模式按设计 §3 分组，默认收起高级证据；收起不清空。Port of Call 确认在新模式初始未勾选。
- [ ] 名称映射逐条核对当前目录，保留设备细分；未知名称回退到原路径 ID。候选 ID 自动生成但保持可在高级区编辑和复核。
- [ ] 对表单重绘、候选增删、从结果返回编辑做请求体断言，核对值没有消失、串到其他候选或被再次转换。

```javascript
import test from "node:test";
import assert from "node:assert/strict";
import { percentInputToRatio, ratioToPercentInput } from "../../src/voyage_fuel/static/display-values.mjs";

test("percent input preserves exact mass ratio", () => {
  assert.equal(percentInputToRatio("20"), "0.2");
  assert.equal(percentInputToRatio("0"), "0");
  assert.equal(percentInputToRatio("100"), "1");
  assert.equal(percentInputToRatio("2.2130676682982508109"), "0.022130676682982508109");
  assert.equal(ratioToPercentInput("0.022130676682982508109"), "2.2130676682982508109");
  assert.equal(percentInputToRatio(""), null);
  assert.throws(() => percentInputToRatio("100.01"));
});
```

运行：`node --test tests/frontend/display-values.test.mjs`，再运行旧精度 E2E 与新输入往返用例。

**关卡 G2：**同一业务输入的新旧请求体等价；除主动确认和可读百分数显示外，原有输入能力均可访问，旧精度结果不变。

### 任务 3：目标、方案与解释联动

**文件：**新增 `workbench-model.mjs`、`tests/frontend/workbench-model.test.mjs`；完善 `workbench-view.mjs`、`workbench_results.html`、`workbench.css` 和 `test_workbench_flow.py`。

**输入/产出：**消费原始响应与成功输入副本，输出 §3.2 的模型和单一当前方案视图。

- [ ] 先写模型测试：目标切换、手动选择、相同方案承载多个目标、目标不可用、未知状态、候选全阻断、B0-only、原结果未被修改。
- [ ] `buildWorkbenchModel()` 建立稳定 ID 索引，从服务端目标字段取赢家。推荐原因为目标与候选作用范围匹配，不重新按价格或改善值选择赢家。
- [ ] `selectGoal()` 选择对应赢家；无赢家时以 B0 作为查看对象但不给它虚构推荐。`selectScenario()` 只改变查看对象和 `selectionSource`。
- [ ] 采用精简方案列表、单份详情和就近风险提示。目标最低比例和最低成本比例分别展示；保留未选目标的切换入口。
- [ ] 已知状态翻译为中文；空值显示明确原因，未知原因显示原码和“原因未提供”，不推断成功。
- [ ] 使用 `textContent` 或已有转义机制输出用户名称、错误与来源；新增动态 HTML 不直接插入未转义字符串。
- [ ] 修改输入使模型、推荐引用和快照同时失效；候选增删、港口选择、高级参数修改遵循相同规则。
- [ ] 目标切换、手动查看、精度变化和展开详情不增加 `/api/calculate` 调用，不修改快照 ID。

核心状态断言（输入为测试夹具，字段 `result` 为从基线 API 捕获的原始响应）：

```javascript
const before = JSON.stringify(result);
const model = buildWorkbenchModel(result, submittedInput);
const target = selectGoal(model, "target");
assert.equal(target.recommendedScenarioId, result.decision_summary.target_min_cost_scenario_id);
const browsing = selectScenario(target, "B0");
assert.equal(browsing.selectedScenarioId, "B0");
assert.equal(browsing.recommendedScenarioId, target.recommendedScenarioId);
assert.equal(browsing.selectionSource, "manual");
assert.equal(JSON.stringify(result), before);
```

夹具来自任务 0 的真实结果，保存时只移除随机 `result_snapshot_id`；不伪造数值填补缺失结果。语义冲突用例允许构造不一致 fixture，必须标注其为故障注入。

**关卡 G3：**用户查看与系统推荐可清楚区分；三类目标语义与 G0 一致；无法推荐和数据不足状态不被“好看”的默认值掩盖。

### 任务 4：图表与深入比较

**文件：**新增 `workbench-charts.mjs`、`tests/frontend/workbench-charts.test.mjs`、`tests/e2e/test_workbench_charts.py`；修改工作台模型和视图。

**输入/产出：**`buildChartData()` 输出只读数据系列，`renderCharts()` 绘制并返回清理函数。

- [ ] 先测试成本、GHGI、散点的字段映射；覆盖负差额、零、null、不适用、非有限坐标、超长数值和重叠点。
- [ ] 以设计 §5 字段作为唯一数值来源。成本系列包含 `baseline_total`、`fuel_delta`、`ets_delta`、`selected_total`；标签保留 `rawValue`。
- [ ] 将 Decimal 字符串转换成 Number 仅用于像素坐标，先验证 finite；tooltip、状态、排序和推荐使用原始值。
- [ ] 瀑布图画出增减方向，FuelEU 金额单列；GHGI 图含单位、参考线及适用性；散点图只显示已有方案，不构造曲线或额外最优点。
- [ ] 点击散点回调 `selectScenario()`，图、表、详情同步。键盘可选择相同方案；重叠点有列表替代。
- [ ] 每次更新先调用前一次 cleanup，避免重复监听、累积 SVG 节点或过期方案点击。
- [ ] 在 1440×900、1024×768、390×844、320×740 检查布局和截图，增加桌面 200% 缩放检查。除明确包裹的数据表外，页面不得产生水平溢出。
- [ ] 验证图形非空、单位可见、数值与 API 一致，长名称和长 ID 不遮挡；截图统一写入 `output/workbench-upgrade/screenshots/`。

```javascript
const chosen = result.scenarios.find(row => row.scenario_id === scenarioId);
const data = buildChartData(result, scenarioId);
assert.equal(data.cost.items.find(item => item.key === "fuel_delta").rawValue, chosen.deltas.fuel_cost.delta);
assert.equal(data.cost.items.find(item => item.key === "selected_total").rawValue, chosen.result.model_cost);
assert.equal(data.cost.currency, result.currency);
assert.ok(!data.cost.items.some(item => item.key.includes("penalty")));
```

约定 `data.cost` 包含 `status`、`currency`、`items`；`items` 元素包含 `key` 和 `rawValue`。数据不齐时 `status="unavailable"` 且不画完整成本图；不得让一个缺价格方案的测试读取虚假 `0`。

**关卡 G4：**图表读数等价于原结果，不能制造不存在的收益/可行性；移动端和键盘操作可用，图表失败有文本数据替代。

### 任务 5：快照、并发与导出闭环

**文件：**扩展 `test_workbench_contracts.py`、`test_workbench_flow.py`；必要时仅调整 `app.js` 的显示状态与导出错误处理，不改报告数据合同。

**输入/产出：**成功结果快照到完整案例 CSV/PDF；无论当前查看什么方案，所有相关结果保持同源。

- [ ] 先写计算请求乱序、旧错误晚到、编辑中返回、导出过程中输入改变和快照失效测试。
- [ ] 选择目标或查看不同方案后，断言导出 body 仍使用原快照；完整输入和 `calculatedResult` 不得发送给导出端点。
- [ ] 导出按钮命名为“导出完整案例”，菜单选择 CSV/PDF；不让用户误以为只导出了当前方案。
- [ ] 快照 409 时将导出标记为不可用，提示重新计算；不悄悄自动重算后下载新结果。重算成功后恢复导出。
- [ ] 页面、CSV、PDF 核对 B0、各候选量、成本、差额、目标和风险边界；PDF 按显示精度核对，CSV 按原始值核对。
- [ ] 输入变化后阻止旧导出响应触发下载；前端错误文本不包含内部异常栈。

```python
def test_export_never_recalculates_successful_snapshot():
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from voyage_fuel.web import app
    from tests.test_goal_alignment_fixes import payload

    client = TestClient(app)
    calculated = client.post("/api/calculate", json=payload()).json()
    with patch("voyage_fuel.web.calculate_parsed_decision_case",
               side_effect=AssertionError("export recalculated")):
        response = client.post("/api/export/csv",
                               json={"resultSnapshotId": calculated["result_snapshot_id"]})
    assert response.status_code == 200
```

**关卡 G5：**新界面保留全部已修复的结果失效和导出安全行为。快照随机 ID 不参与新旧数值相等判断，不能据此忽略其他字段差异。

### 任务 6：全量回归、文档同步和默认切换

**文件：**README、产品总纲、MMD/PNG、与当前导出机制冲突的历史说明；新增 `docs/validation/2026-09-17-decision-workbench-acceptance.md` 记录实际执行日期与结果。

- [ ] 执行第 6 节全部命令和第 5 节矩阵，保留新旧两种 UI 的结果。
- [ ] 使用设计 §8 的业务任务开展至少一例真实使用者验收；无业务用户时明确保留待验收状态。
- [ ] 更新 README 的新旧入口、无损百分数、完整案例导出和回退方式；给旧计划增加历史说明，不把旧执行记录改写成新机制一直存在。
- [ ] 产品总纲只补充已落地能力；MMD 保持“统一计算 + 选择/解释联动 + 同源交付”，PNG 从同一 MMD 重新生成，不手工单独维护。
- [ ] 新静态资源保持扁平目录或同步调整打包规则；构建安装包后检查 HTML、`.mjs`、CSS 确实包含并可访问。
- [ ] 做独立代码与产品边界复核：安全性、回归、不可用目标、图表误导、输入精度、跨端操作。
- [ ] 用户确认发布后才将运行配置设为 `VOYAGE_FUEL_UI=workbench`。保留 `/?view=legacy`，不在同一次发布删除旧实现。
- [ ] 发布后执行健康、B0-only、一个多候选案例和 CSV/PDF 导出冒烟验证；完成回退演练后记录结果。

**关卡 G6：**G0–G5 全部通过、全量回归通过、业务验收与发布授权完成。测试通过不自动等于合并或发布。

## 5. 必须覆盖的验收矩阵

| 场景 | 必须成立 |
| --- | --- |
| 无候选 | B0 可计算、可导出，无新能源推荐或虚构零收益图 |
| 一种/多种候选 | 共用 B0、稳定候选 ID、独立约束，互不串值 |
| 同一方案满足多个目标 | 原因随目标正确切换，手动查看不改推荐 |
| B0 成本最低 | 允许结论为保持基准，不为推广新能源强选候选 |
| 目标已满足/可达/不可达 | 正确解释三种状态，最低比例不与最低成本比例混用 |
| 2024 / FuelEU 不适用 | 不画零参考线、不声称达标或改善最大 |
| 缺价格 / 价格为 0 | null 与 0 区分，不伪造净成本 |
| 有预算但缺价格 | 显示约束未验证，保留可计算结果但不标为预算已满足 |
| 供应、预算、最大比例分别起作用 | UI 提示与原 constraints、issues 相符 |
| 禁止纯用且上限为 1 | 不伪造 B100 或 1-epsilon，先按 G0 明确最大改善语义 |
| 同路径不同报价 / 自定义名称 | 不合并候选，名称与成功提交绑定 |
| RFNBO 未证明与资格回退 | 实际使用路径和估算状态可见 |
| 单候选阻断 / 所有候选阻断 / B0 阻断 | 分层处理，不混淆空候选；B0 阻断禁止导出 |
| 长精度比例、百分数反复编辑、同显示比例 | 原始比例和稳定 ID 不变，无双重转换 |
| EU ETS 成本增加 | 用“增加”表达，不能强标“节省”或画成收益 |
| 负差额、零基准、不同币种 | 符号和单位正确，FuelEU EUR 独立，无换汇 |
| 图点重叠、无点、缺值 | 可通过列表选择，不画虚假 0 或插值最优曲线 |
| 修改输入、请求乱序、旧错误晚到 | 最新版本有效，旧结果/旧下载不能覆盖当前状态 |
| 快照过期、容量淘汰、服务重启 | 明确需要重算，不恢复旧不安全导出 |
| 恶意 HTML 名称、未知状态码 | 不执行脚本、不默认转成成功 |
| 安装包运行、旧版显式入口 | 所有新增资源可加载，旧版可用于回退 |

## 6. 验证命令与产物

所有命令在 `D:\projects\工具MVP` 运行，每条分别执行并检查退出码。Python 使用项目 `.venv`；若未安装 pytest，先报告环境缺项，使用仓库 unittest 入口或经确认补装，不把启动失败记成业务回归。

```powershell
.\.venv\Scripts\python.exe -m pytest tests --ignore=tests/e2e -q
.\.venv\Scripts\python.exe -m pytest tests/e2e -q
node --test port-identity-mapping.test.mjs port-scope-rates.test.mjs
node --test tests/frontend/display-values.test.mjs tests/frontend/workbench-model.test.mjs tests/frontend/workbench-charts.test.mjs
node --check src/voyage_fuel/static/app.js
node --check src/voyage_fuel/static/display-values.mjs
node --check src/voyage_fuel/static/workbench-model.mjs
node --check src/voyage_fuel/static/workbench-view.mjs
node --check src/voyage_fuel/static/workbench-charts.mjs
node --check src/voyage_fuel/static/workbench-labels.mjs
.\.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

任务 0 尚未创建 `tests/frontend/` 和新模块时只运行已存在的测试；不得用不存在的文件导致的错误作为新功能失败证据。

新旧视图由测试参数显式选择；默认配置两种取值分别进行 route 测试。安装包验证复用现有 `VOYAGE_FUEL_USE_INSTALLED_PACKAGE` 约定，并在隔离解释器中运行；不卸载开发目录的 editable 安装来做打包测试。

产物目录为 `output/workbench-upgrade/`：基线、请求/结果脱敏 fixture、测试日志、截图、人工验收记录。现有 E2E 默认会写已跟踪 artifacts，执行前将新测试输出定向到该目录；旧测试产生的文件差异必须单独检查，禁止批量回退。

验收记录包含：执行时间、分支/HEAD/工作区状态、解释器、每组测试数量、截图路径、真实案例来源与脱敏说明、未通过项、默认模式、回退结果。不能复制历史通过数字当作本次验证。

## 7. 回退与停止条件

### 7.1 回退顺序

1. 未切换默认入口前出现问题：停止新模式交付，继续使用 `/?view=legacy`；保留问题现场和测试。
2. 已切换后出现 UI 问题：先通过显式旧版入口恢复操作；配置改回 `VOYAGE_FUEL_UI=legacy`。若重启服务，明确旧快照会丢失，用户需要重新计算。
3. 公共 `app.js` 改动使两种模式都受影响：界面开关不足以回退，恢复到已验证的升级前完整代码检查点，而非只替换模板。恢复前核对当前差异，保留用户之后的独立改动。
4. 回退必须保留本次升级前已经存在的安全修复，不直接回到只有 HEAD 的版本。
5. 不声称切换入口能保留尚未提交的表单或跨进程恢复结果；本期没有新增持久化。

### 7.2 立即停止默认切换的条件

- 原始结果、单位、比例、排序或推荐出现无法解释的变化。
- 候选级/案例级结论矛盾尚未解决，或只靠 UI 隐藏了矛盾。
- 新旧页面同一业务输入不能生成等价请求。
- 报告与页面来自不同计算，或修改输入后仍可导出旧结果。
- 缺价格、不适用或约束未知被展示为 0、已达标或可执行。
- 移动端无法完成核心操作，或关键风险只存在于看不到的区域。
- 安装包缺失资源、回退未经验证，或真实用户仍误读成本/合规边界。

## 8. 完成定义与本轮交付

全部任务通过不代表可以省略业务验收，也不代表授权提交或合并。最终交付应分别标记：

- 设计已确认；
- 代码与自动化验证已完成；
- 业务案例验收已完成或待完成；
- 默认入口已切换或仍为预览；
- 当前已知限制及回退入口。

## 9. 已执行记录

### 基线

- 实施前工作区：`codex/safe-decision-contract-fixes`，HEAD `8e465fa3a5e890c19c893f0945d5186eacafb2fa`，已有未提交安全修复和文档更新。
- 可恢复副本：`output/workbench-upgrade/baseline/`，包含工作区 `tracked-working-tree.diff`、文件哈希和状态记录。
- 任务 1 前顶层 Python 非 E2E：`224 passed`；Node 港口：`29 passed`。

### 已实现

- 新增白名单入口：默认 `/?view=legacy`，新版 `/?view=workbench`，非法 view 返回 422。
- 新版工作台采用目标、方案列表、当前方案解释、成本拆分和成本/合规散点图布局。
- 百分比输入通过 `display-values.mjs` 转换为 API 质量比例，长小数精度保留。
- B0-only 保留基础结果和导出，不生成候选目标推荐。
- 目标选择与手动查看分离；报告集合赢家和连续约束推荐保持后端语义，不在前端重排。
- 新旧视图共用原计算请求、结果快照、错误隔离和导出路径；默认入口未切换。

### 自动化验证

- 顶层 Python 非 E2E：`229 passed, 77 subtests passed`。
- 全部 E2E：`26 passed, 2 subtests passed`。
- Node 港口测试：`29 passed`。
- 前端展示模型和精度测试：`6 passed`。
- JavaScript 语法、Python `compileall`、`git diff --check`：通过。
- 浏览器截图：`output/workbench-upgrade/screenshots/desktop-v2.png`、`mobile-v2.png`；桌面与移动均无水平溢出。

### 服务冒烟

已启动 `http://127.0.0.1:8765/`：

- `/health` 返回 `ok`；
- 根路径仍为 legacy，`/?view=workbench` 返回工作台；
- `/static/workbench.css` 和 `/static/workbench-view.mjs` 返回 200；
- 一个单候选请求返回 4 个场景和结果快照。

### 尚未完成

- 业务使用者按设计 §8 完成五项验收。
- 用户确认后将默认入口切换为 workbench；当前保留旧版回退。
- 本轮未提交、推送或合并 Git 变更。
