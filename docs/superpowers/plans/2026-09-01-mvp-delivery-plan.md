# Voyage Fuel Decision MVP Delivery Plan and Status

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留现有高精度 Python 计算内核的基础上，完成案例级多候选决策、结构化结果与错误、可追溯报告和单用户网页工作流，并在同一文件持续记录 MVP 完成状态。

**Architecture:** 现有 `calculate_voyage(VoyageInput) -> VoyageResult` 继续负责一种基准燃料与一种候选燃料的单候选计算。新增案例层契约和编排器，把多个候选分别送入现有内核，隔离候选级错误，再在统一、未舍入的结果对象上生成跨候选排序、条件式建议、CSV、PDF 和网页展示。网页采用 FastAPI、Jinja2 和原生 JavaScript，不保存服务器案例；浏览器刷新即清空当前案例。

**Tech Stack:** Python 3.12；标准库 `dataclasses`、`decimal`、`unittest`；FastAPI；Uvicorn；Jinja2；ReportLab；Python Playwright（端到端验收）；现有 Node 港口规则测试。

**Spec:** `项目目标与总体架构.md`、`港口比例功能说明.md`、`燃料因子库规范.md`、`docs/superpowers/specs/2026-08-07-voyage-fuel-decision-mvp-design.md`、`docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md`

## Document Role

本文件是 MVP 开发状态和剩余实施任务的唯一事实来源。它同时回答：

1. 当前哪些模块已经满足规格并通过验证；
2. 哪些模块只有部分代码，尚未满足完整 MVP；
3. 剩余任务按什么顺序实施；
4. 每项任务以什么测试和证据判定完成。

`README.md`只链接本文件并提供运行入口，不维护第二份模块清单。`docs/superpowers/plans/`中的其他文件是已经执行或曾经拟定的阶段计划，保留用于历史追溯，不覆盖本文件的当前状态。

## Status Rules

| Status | Definition |
| --- | --- |
| `NOT_STARTED` | 没有可用于该能力的实现 |
| `IN_PROGRESS` | 已有部分实现，但缺少规格要求、集成或测试 |
| `IMPLEMENTED` | 代码已完成，尚未通过完整验收 |
| `VERIFIED` | 满足对应规格，并有当前自动化测试或审计证据 |
| `BLOCKED` | 已明确记录阻碍原因，当前无法继续 |
| `OUT_OF_SCOPE` | 现行 MVP 文档明确排除，完成 MVP 不要求实现 |

状态更新规则：

- 只有代码、测试和文档契约一致时才能标记为 `VERIFIED`；
- 能生成文件或返回数值不等于满足完整输出规格；
- 每完成一个任务，先运行该任务的聚焦测试，再运行完整回归测试，最后更新本文件的模块状态和验证记录；
- 不在 `README.md`、提交信息或聊天结论中创建另一套完成度数字。

## Global Constraints

- MVP计算范围是2024-2030报告年份中两个相邻有效 `Port of Call` 之间的单个航段。
- 所有方案使用B0物理能源作为共同需求，单个混兑方案只含一种基准燃料和一种候选燃料。
- 内部计算使用 `Decimal` 高精度数值；中间步骤、排序、判断和临界点搜索不按显示精度舍入。
- MVP开放36条航行燃料路径；`ELECTRICITY_OPS`不进入航段输入、计算和比较。
- 2024-2025年EU ETS只纳入CO2；2026年起纳入CO2、CH4和N2O。
- FuelEU结果是航次级按比例分配估算；指示性罚款等值固定为EUR，不进入当前模型成本或默认排序。
- 当前模型成本只包含燃料采购成本和EUA成本，二者使用同一个案例币种。
- 所有可计算方案的执行状态均为 `EXECUTION_CONDITIONS_PENDING`。
- 普通用户无需输入E、eu、PoS、PoC或Cslip；高级自定义或认证数据必须满足逐字段证据契约。
- 价格缺失不阻断能源、排放和FuelEU计算，但阻止成本排序、预算结论和经济临界点输出。
- 页面、PDF和CSV消费同一个原始结果对象；CSV保留完整十进制字符串，页面与PDF共享显示配置。
- 一个候选方案阻断时，其他候选和B0仍应计算；案例级港口或B0能源错误阻断整个案例。
- 网页无账号、无云端存储、无案例历史；案例只存在于当前浏览器会话，刷新后清空。
- 结果不得表述为采购建议、正式年度FuelEU合规余额、真实年度罚款或独立物理生命周期WtW减排。

## Current Verified Baseline

基线日期：2026-09-03。

基线分支：`python-calculation-kernel`。

当前已验证提交：`571f6ae fix: close report provenance audit gaps`。

验证结果：

```text
Python unittest: 189 passed
Node port tests: 29 passed
Playwright E2E: 12 passed (included in the repository discovery run)
Python compileall: passed
JavaScript syntax check: passed
git diff --check: passed
```

复核命令：

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
node --test port-identity-mapping.test.mjs port-scope-rates.test.mjs
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m compileall -q src tests
git diff --check
```

## Module Status

| ID | Module | Status | Current evidence | Remaining MVP gap | Completion condition |
| --- | --- | --- | --- | --- | --- |
| M01 | 港口身份表和范围计算 | `VERIFIED` | `ports.py`；`test_ports.py`；29项Node测试 | 核心计算无缺口；港口解释和来源输出归M10 | 现有规则测试持续通过 |
| M02 | 36条内置燃料路径和解析器 | `VERIFIED` | `factors.py`；`test_factors.py`；`test_factor_catalog_audit.py`；`test_factor_resolution.py` | 核心解析无缺口；运行时追溯归M10 | 36条路径及全部资格分支测试持续通过 |
| M03 | 自定义燃料逐字段证据校验 | `VERIFIED` | `custom_factors.py`；`test_custom_factors.py`；JSON/API 自定义路径阻断矩阵；Task 7 资格、年份、BIO_E、Cslip 反例矩阵；网页高级自定义最小输入 E2E | 页面只负责适配输入，不替代后端证据校验 | 缺字段、单位、滑移、证据状态和网页 payload 组装测试持续通过 |
| M04 | B0、B100、质量混兑和能源守恒 | `VERIFIED` | `energy.py`；`calculator.py`；`test_energy.py`；`test_calculator.py` | 无 | 所有报告方案保持B0能源且测试通过 |
| M05 | EU ETS航次计算 | `VERIFIED` | `emissions.py`；`test_ets.py`；Task 11 `test_spec_matrix.py` 12项矩阵 | 无 | 年份、气体、范围和清缴比例矩阵通过 |
| M06 | FuelEU航次级GHGI、余额和罚款等值 | `VERIFIED` | `emissions.py`；`test_fueleu.py`；Task 11 `test_spec_matrix.py` 12项矩阵 | 无；仍限于航次级比例估算 | 适用性、年度目标、范围、余额和罚款向量通过 |
| M07 | 预算、供应、最大混兑和目标比例 | `VERIFIED` | `constraints.py`；`test_constraints.py` | 跨候选统一结论归M09 | 向量G和边界状态测试持续通过 |
| M08 | 单候选经济临界点和下包络切换 | `VERIFIED` | `economics.py`；`test_economics.py` | 跨候选统一排序归M09 | 临界价、参考价值和下包络测试持续通过 |
| M09 | 案例级多候选编排和统一比较 | `VERIFIED` | `case_calculator.py`；`case_comparison.py`；`test_case_calculator.py`；`test_case_comparison.py` | 追溯和展示归M10、M13-M15 | 多候选、共享B0、可行可比全局排序和局部阻断回归测试通过 |
| M10 | 结构化状态、错误、追溯和版本 | `VERIFIED` | `provenance.py`；`test_provenance.py`；任务5聚焦审查通过 | 报告和网页呈现归M13-M15 | 结果逐项满足计算规格第13、14、17节 |
| M11 | 相对B0变化和条件式建议 | `VERIFIED` | `case_comparison.py`；`test_case_comparison.py` | 页面和报告呈现归M13-M15 | 原始Decimal差值、零基线、条件式结论和临界点关联测试通过 |
| M12 | JSON/API输入输出契约 | `VERIFIED` | `json_io.py`、`web.py`；`test_case_json_io.py`；`test_web_api.py` | 无；后续页面和报告仅消费同一结果契约 | 案例级JSON、结构化422错误和API集成测试通过 |
| M13 | CSV完整报告 | `VERIFIED` | `formatting.py`；`reports.py`；`test_case_reports.py`；571f6ae 回归测试 | - | Case、港口、场景、建议、临界点、因子依据和问题记录均固定导出；原始Decimal、单位、币种、版本、`E/eu` 证据值和实际生物质比例保持可审计 |
| M14 | PDF完整报告和共享显示配置 | `VERIFIED` | `reports.py`；Task 8 报告测试与渲染；Task 12 安装后 PDF 13页渲染、文本和边界审计；571f6ae 回归测试 | 无 | PDF满足MVP设计第14节并通过渲染检查，包含自定义 `BIO_E/RFNBO_E` 公式证据值和实际生物质比例 |
| M15 | 单用户网页工作流 | `VERIFIED` | `web.py`、`index.html`、`app.js`；内置燃料 desktop/mobile flow；高级自定义最小输入与 RFNBO 保护 E2E；网页证据字段聚焦测试 | 无；正式年度模式仍属范围外 | 用户可在浏览器完成内置路径或高级自定义燃料的一次航次案例，并查看字段级来源类型、单位、核验状态和值 |
| M16 | 完整测试矩阵和端到端验收 | `VERIFIED` | Task 7 反例矩阵 20/20；最新完整验收 Python unittest discover 189；Node port tests 29；compileall；`node --check`；`git diff --check` | 无 | 计算规格第16节和网页主流程全部自动验证 |
| M17 | 安装、运行和依赖声明 | `VERIFIED` | `pyproject.toml`；2026-09-03 临时 Python 3.12 venv 安装 `.[dev]`；安装后 `voyage-fuel-web` `/health`、fixture API、CSV/PDF 实测 | 无 | 干净环境按README命令可启动并通过健康检查 |

总体判断：计划内的案例级计算、约束与经济比较、结构化结果、CSV/PDF、单用户网页、安装后运行链路和本轮报告审计修复均已通过聚焦验证及最新完整验收。产品边界仍保持航次级 FuelEU 估算、执行条件待确认和明确排除项。逐字段自定义燃料因子已经在 Python/JSON/API 层完成，网页现已提供最小输入的高级自定义因子表单和完整证据摘要；CSV/PDF 同时保留自定义 `BIO_E` 的 `E`、`RFNBO_E` 的 `E/eu` 证据值，以及实际 `eligibleBiomassFraction`。剩余的浏览器运行时证据值断言属于低优先级测试增强，不构成本轮已复现的 MVP 功能缺口。

---

### Task 1: Case-Level Contracts and Stable Identifiers

**Status impact:** M09 `NOT_STARTED -> IN_PROGRESS`；M10、M12继续保持 `IN_PROGRESS`。

**Files:**
- Create: `src/voyage_fuel/contracts.py`
- Modify: `src/voyage_fuel/models.py`
- Modify: `src/voyage_fuel/__init__.py`
- Create: `tests/test_contracts.py`

**Interfaces:**
- Consumes: existing `FuelComponent`, `VoyageResult`, `Decimal`.
- Produces: `CandidateInput`, `DecisionCaseInput`, `ParsedDecisionCase`, `Issue`, `CandidateResult`, `CaseScenario`, `DecisionCaseResult`, `MetricDelta`, `ConditionalRecommendation`.

- [x] **Step 1: Write the failing contract tests**

Add `tests/test_contracts.py` with these exact behaviors:

```python
from decimal import Decimal
import unittest

from voyage_fuel.contracts import CandidateInput, DecisionCaseInput, Issue
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.models import FuelComponent


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.baseline = FuelComponent(get_builtin_factor("MDO"), Decimal("700"))
        self.candidate = FuelComponent(get_builtin_factor("UCO_FAME"), Decimal("1000"))

    def test_case_requires_confirmed_adjacent_port_of_call(self):
        with self.assertRaisesRegex(ValueError, "PORT_OF_CALL_CONFIRMATION_REQUIRED"):
            DecisionCaseInput(
                report_year=2026, departure_port="CNSHG", arrival_port="NLRTM",
                adjacent_valid_port_of_call_confirmed=False, currency="EUR",
                baseline_component=self.baseline, baseline_mass_tonnes=Decimal("100"),
                eua_price_per_tco2e=Decimal("80"), candidates=(),
            )

    def test_candidate_and_scenario_ids_are_stable(self):
        candidate = CandidateInput(
            candidate_id="uco-quote-1", component=self.candidate,
            specified_blend_ratios=(Decimal("0.20"),),
        )
        self.assertEqual(candidate.candidate_id, "uco-quote-1")
        self.assertEqual(candidate.scenario_id(Decimal("0.20")), "uco-quote-1@0.2")

    def test_issue_identifies_scope_candidate_and_field(self):
        issue = Issue(
            code="INVALID_BLEND_RATIO", scope="CANDIDATE", field="specifiedBlendRatios[0]",
            blocking=True, message="ratio must be between zero and one",
            candidate_id="uco-quote-1",
        )
        self.assertEqual(issue.candidate_id, "uco-quote-1")
        self.assertTrue(issue.blocking)
```

- [x] **Step 2: Run the contract tests and confirm they fail**

Run:

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_contracts -v
```

Expected: FAIL because `voyage_fuel.contracts` does not exist.

- [x] **Step 3: Implement immutable case-level contracts**

Create these public shapes in `contracts.py`:

```python
@dataclass(frozen=True)
class Issue:
    code: str
    scope: str
    field: str
    blocking: bool
    message: str
    candidate_id: str | None = None
    scenario_id: str | None = None
    component: str | None = None


@dataclass(frozen=True)
class CandidateInput:
    candidate_id: str
    component: FuelComponent
    specified_blend_ratios: tuple[Decimal, ...] = ()
    max_blend_ratio: Decimal = Decimal("1")
    allows_pure_use: bool = False
    supply_tonnes: Decimal | None = None
    incremental_budget: Decimal | None = None
    compliance_improvement_value: Decimal | None = None

    def scenario_id(self, ratio: Decimal) -> str:
        canonical = format(ratio.normalize(), "f")
        return f"{self.candidate_id}@{canonical}"


@dataclass(frozen=True)
class DecisionCaseInput:
    report_year: int
    departure_port: str
    arrival_port: str
    adjacent_valid_port_of_call_confirmed: bool
    currency: str
    baseline_component: FuelComponent
    baseline_mass_tonnes: Decimal
    eua_price_per_tco2e: Decimal | None
    candidates: tuple[CandidateInput, ...]


@dataclass(frozen=True)
class ParsedDecisionCase:
    request: DecisionCaseInput | None
    issues: tuple[Issue, ...]
```

Validation must reject an empty/duplicate `candidate_id`, empty `currency`, false Port of Call confirmation, invalid baseline mass, invalid candidate constraints and duplicate candidate IDs with stable calculation-spec error codes.

Define result contracts without calculation logic:

```python
@dataclass(frozen=True)
class CandidateResult:
    candidate_id: str
    calculation_status: str
    voyage_result: VoyageResult | None
    issues: tuple[Issue, ...]


@dataclass(frozen=True)
class MetricDelta:
    absolute: Decimal | None
    delta: Decimal | None
    percent_delta: Decimal | None
    reason_code: str | None = None


@dataclass(frozen=True)
class ConditionalRecommendation:
    recommendation_id: str
    condition: str
    scenario_id: str | None
    reason: str
    assumptions: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class CaseScenario:
    scenario_id: str
    candidate_id: str | None
    calculation_status: str
    result: ScenarioResult
    deltas: Mapping[str, MetricDelta]


@dataclass(frozen=True)
class DecisionCaseResult:
    report_year: int
    departure_port: str
    arrival_port: str
    currency: str
    baseline_scenario: ScenarioResult | None
    candidate_results: tuple[CandidateResult, ...]
    scenarios: tuple[CaseScenario, ...]
    recommendations: tuple[ConditionalRecommendation, ...]
    issues: tuple[Issue, ...]
    provenance: object | None = None
```

Export the new contracts from `voyage_fuel.__init__` without changing existing public functions.

- [x] **Step 4: Run contract and existing model tests**

Run:

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_contracts tests.test_models -v
```

Expected: PASS.

- [x] **Step 5: Commit the contract foundation**

```powershell
git add src/voyage_fuel/contracts.py src/voyage_fuel/models.py src/voyage_fuel/__init__.py tests/test_contracts.py docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "feat: define decision case contracts"
```

After the focused and full regression suites pass, update M09 from `NOT_STARTED` to `IN_PROGRESS` and record the new test count in `Current Verified Baseline`.

---

### Task 2: Structured JSON Parsing and Error Mapping

**Status impact:** M12 remains `IN_PROGRESS` until the case API in Task 6 is verified.

**Files:**
- Modify: `src/voyage_fuel/json_io.py`
- Create: `src/voyage_fuel/issues.py`
- Modify: `src/voyage_fuel/__init__.py`
- Create: `tests/test_case_json_io.py`

**Interfaces:**
- Consumes: `DecisionCaseInput`, `CandidateInput`, `Issue`, existing `_component()` factor resolution behavior.
- Produces: `parse_decision_case(payload: str | Mapping[str, Any]) -> ParsedDecisionCase`, `issue_from_exception(...) -> Issue`, `decision_case_result_to_dict(...) -> dict[str, Any]`.

- [x] **Step 1: Write failing tests for the complete input contract**

Add tests that parse this minimum payload:

```python
payload = {
    "reportYear": 2026,
    "departurePort": "CNSHG",
    "arrivalPort": "NLRTM",
    "adjacentValidPortOfCallConfirmed": True,
    "currency": "EUR",
    "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
    "euaPricePerTCO2e": "80",
    "candidates": [
        {
            "candidateId": "uco-quote-1",
            "pathId": "UCO_FAME",
            "pricePerTonne": "1000",
            "specifiedBlendRatios": ["0.2"],
            "maxBlendRatio": "0.3",
            "candidateSupplyTonnes": "20",
        },
        {
            "candidateId": "lng-quote-1",
            "pathId": "LNG_OTTO_MEDIUM_SPEED",
            "pricePerTonne": "850",
            "specifiedBlendRatios": ["0.1"],
        },
    ],
}
```

Assertions must cover:

- two valid candidates preserve their IDs and Decimal values in `parsed.request`;
- false or missing `adjacentValidPortOfCallConfirmed` maps to `PORT_OF_CALL_CONFIRMATION_REQUIRED`;
- duplicate candidate IDs map to a case-level blocking issue;
- an invalid second candidate can be represented as a candidate-level issue without discarding the first candidate;
- `calculate_voyage_json()` remains available for legacy single-candidate regression tests until Task 8 removes the need for it.

- [x] **Step 2: Run the focused JSON tests and confirm failure**

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_json_io -v
```

Expected: FAIL because the case-level parser and issue mapper do not exist.

- [x] **Step 3: Implement parsing without binary floats**

Move reusable component parsing into a public, typed helper. Every numeric input must pass through `Decimal(str(value))`; booleans must reject string values such as `"false"`. Map known exceptions to the minimum error-code set in calculation-spec section 13.2. Do not parse error messages in the webpage; return `Issue` fields explicitly.

The parser returns `ParsedDecisionCase(request, issues)`. Candidate-level input failures are excluded from `request.candidates` and retained as candidate-scoped issues so Task 3 can continue with unaffected candidates. Case-level failures return `ParsedDecisionCase(request=None, issues=(...))`; the API later projects that into a `DecisionCaseResult` with `baseline_scenario=None` and no calculations.

- [x] **Step 4: Run JSON and factor resolution tests**

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_json_io tests.test_json_io tests.test_factor_resolution tests.test_custom_factors -v
```

Expected: PASS.

- [x] **Step 5: Commit structured parsing**

```powershell
git add src/voyage_fuel/json_io.py src/voyage_fuel/issues.py src/voyage_fuel/__init__.py tests/test_case_json_io.py docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "feat: parse decision case inputs"
```

---

### Task 3: Multi-Candidate Case Orchestration and Local Blocking

**Status impact:** M09 `IN_PROGRESS -> IMPLEMENTED` after focused tests; it becomes `VERIFIED` only after Task 4 cross-candidate comparisons pass.

**Files:**
- Create: `src/voyage_fuel/case_calculator.py`
- Modify: `src/voyage_fuel/calculator.py`
- Modify: `src/voyage_fuel/contracts.py`
- Modify: `src/voyage_fuel/__init__.py`
- Create: `tests/test_case_calculator.py`

**Interfaces:**
- Consumes: `ParsedDecisionCase`, `DecisionCaseInput`, `CandidateInput`, existing `calculate_voyage(VoyageInput)`.
- Produces: `calculate_decision_case(request: DecisionCaseInput, initial_issues: tuple[Issue, ...] = ()) -> DecisionCaseResult`, `calculate_parsed_decision_case(parsed: ParsedDecisionCase) -> DecisionCaseResult`, `calculate_baseline_scenario(...) -> ScenarioResult`.

- [x] **Step 1: Write failing orchestration tests**

Test these behaviors:

```python
result = calculate_decision_case(case_with_uco_and_lng)
self.assertEqual([item.candidate_id for item in result.candidate_results], ["uco-1", "lng-1"])
self.assertEqual(result.baseline_scenario.ratio, Decimal("0"))
self.assertTrue(all(
    item.voyage_result.scenarios[0].physical_energy_mj == result.baseline_scenario.physical_energy_mj
    for item in result.candidate_results if item.voyage_result is not None
))
```

Also assert:

- B0 appears once at the case level even though each candidate reuses the same baseline calculation;
- a blocked LNG candidate returns `calculation_status="BLOCKED"` while UCO remains `COMPARABLE`;
- missing prices produce `CALCULABLE` for the affected candidate and do not block emissions/FuelEU results;
- an invalid port blocks the whole case and no candidate calculation runs;
- candidate order in the output follows input order, while economic rankings are stored separately.

- [x] **Step 2: Run orchestration tests and confirm failure**

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_calculator -v
```

Expected: FAIL because `calculate_decision_case()` does not exist.

- [x] **Step 3: Implement the case orchestrator over the stable single-candidate kernel**

For every valid candidate, build the existing `VoyageInput` with shared case fields and call `calculate_voyage()`. `calculate_parsed_decision_case()` passes `parsed.issues` into `calculate_decision_case()` so invalid raw candidates remain visible beside valid results; when `parsed.request is None`, it returns a blocked case result without calling any calculator. Catch only domain-validation exceptions and convert them to candidate-scoped `Issue` objects; unexpected programming exceptions must still fail the test or request visibly.

Compute B0 through a dedicated baseline function using the shared port scope and baseline component. Verify every candidate's B0 is numerically identical to the case B0 before discarding duplicate baseline rows. A mismatch raises a case-level blocking `INCONSISTENT_BASELINE` issue because cross-candidate comparison would be invalid.

Set candidate calculation status as follows:

```text
BLOCKED    -> no voyage result because required candidate data or factor is invalid
CALCULABLE -> energy/emissions/FuelEU available, but required economic prices are incomplete
COMPARABLE -> prices and comparison inputs are complete
```

- [x] **Step 4: Run case, calculator, constraint and economics tests**

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_calculator tests.test_calculator tests.test_constraints tests.test_economics -v
```

Expected: PASS.

- [x] **Step 5: Commit multi-candidate orchestration**

```powershell
git add src/voyage_fuel/case_calculator.py src/voyage_fuel/calculator.py src/voyage_fuel/contracts.py src/voyage_fuel/__init__.py tests/test_case_calculator.py docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "feat: calculate multi-candidate cases"
```

---

### Task 4: Cross-Candidate Metrics and Conditional Recommendations

**Status impact:** M09 and M11 become `VERIFIED` after the full regression suite passes.

**Files:**
- Create: `src/voyage_fuel/case_comparison.py`
- Modify: `src/voyage_fuel/contracts.py`
- Modify: `src/voyage_fuel/case_calculator.py`
- Create: `tests/test_case_comparison.py`

**Interfaces:**
- Consumes: case B0, each valid candidate's fixed report scenarios, constraints and economics results.
- Produces: stable `CaseScenario` records, `MetricDelta` values, global rankings and `ConditionalRecommendation` objects.

- [x] **Step 1: Write failing cross-candidate comparison tests**

Build a case with two candidates and assert:

- every report scenario has `scenario_id`, `candidate_id`, absolute values and relative-to-B0 values;
- `delta = scenario - B0` and `percent_delta = delta / abs(B0) * 100` use unrounded Decimal values;
- a zero B0 field returns `percent_delta=None` with `reason_code="ZERO_BASELINE"`;
- current-model-cost ranking includes only feasible `COMPARABLE` scenarios from all candidates;
- `CURRENT_MODEL_COST_MIN`, `TARGET_MIN_COST` and `MAX_COMPLIANCE_IMPROVEMENT` recommendations include condition, scenario ID, reason, assumptions and status;
- candidates that cannot reach the GHGI target produce an explicit target status and do not silently disappear;
- switch points retain candidate and scenario IDs on both sides of each transition.

- [x] **Step 2: Run comparison tests and confirm failure**

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_comparison -v
```

Expected: FAIL because case-level scenario and recommendation builders do not exist.

- [x] **Step 3: Implement comparison as a pure projection**

`case_comparison.py` must not recalculate energy, emissions or compliance. It consumes `VoyageResult` objects and produces:

```python
def metric_delta(value: Decimal | None, baseline: Decimal | None) -> MetricDelta: ...

def build_case_scenarios(
    baseline: ScenarioResult,
    candidates: tuple[CandidateResult, ...],
) -> tuple[CaseScenario, ...]: ...

def build_recommendations(
    scenarios: tuple[CaseScenario, ...],
    candidates: tuple[CandidateResult, ...],
) -> tuple[ConditionalRecommendation, ...]: ...
```

FuelEU compliance-improvement value may affect only `reference_adjusted_cost` sensitivity recommendations. It must never change `model_cost` or `CURRENT_MODEL_COST_MIN`. Recommendations with missing economic inputs use `status="UNAVAILABLE"` and include `PRICE_REQUIRED_FOR_COMPARISON` in assumptions.

- [x] **Step 4: Run all calculation and comparison tests**

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_comparison tests.test_case_calculator tests.test_economics tests.test_constraints tests.test_fueleu tests.test_ets -v
```

Expected: PASS.

- [x] **Step 5: Commit unified comparisons**

```powershell
git add src/voyage_fuel/case_comparison.py src/voyage_fuel/contracts.py src/voyage_fuel/case_calculator.py tests/test_case_comparison.py docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "feat: compare candidates and build recommendations"
```

Update M09 and M11 to `VERIFIED` only after the complete Python suite also passes.

---

### Task 5: Port, Fuel and Formula Provenance

**Status impact:** M10 `IN_PROGRESS -> VERIFIED` after result-contract tests pass.

**Files:**
- Create: `src/voyage_fuel/provenance.py`
- Modify: `src/voyage_fuel/models.py`
- Modify: `src/voyage_fuel/ports.py`
- Modify: `src/voyage_fuel/factors.py`
- Modify: `src/voyage_fuel/case_calculator.py`
- Create: `tests/test_provenance.py`

**Interfaces:**
- Consumes: formal port-table rows, requested and resolved factor paths, calculation-spec constants.
- Produces: `PortDecision`, `FactorResolutionTrace`, `ResultProvenance` carried by every `DecisionCaseResult`.

- [x] **Step 1: Write failing provenance tests**

Assert a Shanghai-Rotterdam 2026 case returns:

```text
departure UN/LOCODE, port name, EU ETS identity, FuelEU identity, ruleSourceId, sourceVersion
arrival UN/LOCODE, port name, EU ETS identity, FuelEU identity, ruleSourceId, sourceVersion
EU ETS reason = ONE_IN_SCOPE
FuelEU reason = ONE_IN_SCOPE
EU ETS geographic rate = 0.5
EU ETS surrender rate = 1
FuelEU rate = 0.5
```

Assert unproven `E_DIESEL` records:

```text
requestedPathId = E_DIESEL
resolvedPathId = MDO
resolutionReason = RFNBO_QUALIFICATION_NOT_DEMONSTRATED
qualificationStatus = NOT_DEMONSTRATED
factorStatus = FIXED
```

Also assert every case result carries non-empty calculation-spec, fuel-factor and port-rule versions plus a deduplicated source-ID collection.

- [x] **Step 2: Run provenance tests and confirm failure**

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_provenance -v
```

Expected: FAIL because the current `ScopeRates` drops port identities/reasons and factors drop resolution trace metadata.

- [x] **Step 3: Preserve provenance at resolution boundaries**

Add these constants and immutable contracts in `provenance.py`:

```python
CALCULATION_SPEC_VERSION = "2026-08-07"
FUEL_FACTOR_VERSION = "2026-08-31-audit"
PORT_RULE_VERSION = "2026-07-23"
```

Do not infer provenance later from numeric results. `ports.py` must retain both `_matrix_rate()` reasons and formal table rows when it calculates scope. `factors.py` must return requested path, resolved path and fallback reason alongside the resolved factor. Keep the existing `resolve_factor()` return type available as a compatibility wrapper and introduce a trace-returning resolver for new case calculations.

Aggregate source IDs from port rows, built-in factor field sources and custom `sourceEvidence`. `VERIFIED` continues to mean factor evidence completeness, not formal annual FuelEU verification or execution readiness.

- [x] **Step 4: Run provenance, port and factor audit tests**

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_provenance tests.test_ports tests.test_factor_catalog_audit tests.test_factor_resolution tests.test_custom_factors -v
node --test port-identity-mapping.test.mjs port-scope-rates.test.mjs
```

Expected: PASS.

- [x] **Step 5: Commit provenance support**

```powershell
git add src/voyage_fuel/provenance.py src/voyage_fuel/models.py src/voyage_fuel/ports.py src/voyage_fuel/factors.py src/voyage_fuel/case_calculator.py tests/test_provenance.py docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "feat: preserve calculation provenance"
```

---

### Task 6: Complete JSON API and Reproducible Runtime

**Status impact:** M12 and M17 are `VERIFIED` after API integration and the Task 12 clean-environment check.

**Files:**
- Create: `pyproject.toml`
- Create: `src/voyage_fuel/web.py`
- Modify: `src/voyage_fuel/json_io.py`
- Modify: `src/voyage_fuel/__init__.py`
- Create: `tests/test_web_api.py`

**Interfaces:**
- Consumes: `parse_decision_case()`, `calculate_decision_case()`, report functions from Tasks 7 and 8 when available.
- Produces: `GET /health`, `GET /api/fuels`, `GET /api/ports`, `POST /api/calculate`.

- [x] **Step 1: Write failing API tests**

Using `fastapi.testclient.TestClient`, assert:

- `GET /health` returns `{"status":"ok"}`;
- `GET /api/fuels` returns exactly 36 open path IDs and excludes `ELECTRICITY_OPS`;
- `GET /api/ports?q=rotter` returns matching UN/LOCODE and identity labels without returning the full port table;
- `POST /api/calculate` accepts the Task 2 payload and returns both candidates, one B0, recommendations, provenance and Decimal strings;
- malformed case-level input returns HTTP 422 with structured case issues;
- a blocked candidate returns HTTP 200 with that candidate marked `BLOCKED` and unaffected candidates calculated;
- no endpoint writes case data to disk or server session storage.

- [x] **Step 2: Run API tests and confirm failure**

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web_api -v
```

Expected: FAIL because `voyage_fuel.web` and FastAPI dependencies are absent.

- [x] **Step 3: Add the Python package and service entry point**

Declare Python `>=3.12` and these bounded compatible dependencies in `pyproject.toml`:

```toml
dependencies = [
  "fastapi>=0.116,<1",
  "uvicorn>=0.35,<1",
  "jinja2>=3.1,<4",
  "reportlab>=4.4,<5",
]

[project.optional-dependencies]
dev = [
  "httpx>=0.28,<1",
  "playwright>=1.55,<2",
  "pypdf>=5,<6",
]
```

Expose:

```toml
[project.scripts]
voyage-fuel-web = "voyage_fuel.web:main"
```

`main()` starts Uvicorn on `127.0.0.1:8000` by default and accepts standard command-line host/port overrides. API responses use the common dataclass-to-dict Decimal serializer; business issues are data, while malformed transport requests use HTTP 422.

- [x] **Step 4: Install and run API tests**

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pip install -e ".[dev]"
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web_api tests.test_case_json_io tests.test_json_io -v
```

Expected: installation succeeds and tests PASS.

- [x] **Step 5: Commit API and package metadata**

```powershell
git add pyproject.toml src/voyage_fuel/web.py src/voyage_fuel/json_io.py src/voyage_fuel/__init__.py tests/test_web_api.py docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "feat: expose decision case API"
```

---

### Task 7: Shared Display Configuration and Complete CSV Export

**Status impact:** M13 becomes `VERIFIED`；M14 remains `IN_PROGRESS` until Task 8.

**Files:**
- Create: `src/voyage_fuel/formatting.py`
- Modify: `src/voyage_fuel/reports.py`
- Create: `tests/test_case_reports.py`

**Interfaces:**
- Consumes: `DecisionCaseResult`, `ResultProvenance`, `MetricDelta`.
- Produces: `DisplayConfig`, `format_for_display()`, `decision_case_to_csv()` and `write_decision_case_csv()`.

- [x] **Step 1: Write failing display and CSV tests**

Assert that `DisplayConfig` defaults match calculation-spec section 14.2:

```text
fuel mass: 3 decimals
energy: 3 decimals in GJ
ratios: 4 percentage-point decimals
scope rates: 2 percentage-point decimals
GHGI/WtT/TtW/target: 4 decimals
gas/EUA/compliance values: 6 decimals
prices/costs/penalty equivalent: 2 decimals
factors: at most 9 decimals with insignificant trailing zeros removed
```

CSV tests must assert fixed record types for case, ports, scenarios, recommendations, switch points, factor evidence and issues. Every row must include applicable units, currency, formula versions and source IDs. Decimal values must use `format(value, "f")`, never scientific notation or display rounding.

Change two display configurations and assert serialized raw results, scenario IDs, statuses, rankings, recommendations and CSV bytes remain identical.

- [x] **Step 2: Run case-report tests and confirm failure**

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_reports -v
```

Expected: FAIL because case-level exports and shared display configuration do not exist.

- [x] **Step 3: Implement formatting as a presentation-only dependency**

`DisplayConfig` must never enter calculation, constraints, sorting or search functions. Keep existing `voyage_result_to_csv()` for regression compatibility while adding case-level export functions. The CSV must consume a completed `DecisionCaseResult`; it must not call any calculator.

Use a stable column order and explicit `record_type`. Include absolute, delta, percent delta and reason-code columns for every required comparison metric. Include FuelEU penalty currency as `EUR` separately from the case currency used by fuel, EUA and model costs.

- [x] **Step 4: Run old and new report tests**

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_reports tests.test_reports -v
```

Expected: PASS.

- [x] **Step 5: Commit complete CSV and formatting**

```powershell
git add src/voyage_fuel/formatting.py src/voyage_fuel/reports.py tests/test_case_reports.py docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "feat: export auditable decision cases"
```

---

### Task 8: Complete PDF Report from the Unified Result

**Status impact:** M14 becomes `VERIFIED` after automated content and visual rendering checks pass.

**Files:**
- Modify: `src/voyage_fuel/reports.py`
- Modify: `src/voyage_fuel/web.py`
- Modify: `tests/test_case_reports.py`
- Create: `tests/fixtures/multi_candidate_case.json`

**Interfaces:**
- Consumes: `DecisionCaseResult`, `DisplayConfig`.
- Produces: `decision_case_to_pdf(result, display_config) -> bytes`, `POST /api/export/pdf`, `POST /api/export/csv`.

- [x] **Step 1: Write failing complete-PDF tests**

Generate the multi-candidate fixture and extract PDF text. Assert it contains:

- report year, both ports, case currency and voyage-level boundary statement;
- EU ETS/FuelEU identities, scope rates, surrender rate, reasons and source IDs;
- B0 and all candidate report scenarios;
- fuel mass, energy, fuel cost, each gas, EUAs, EUA cost and model cost;
- FuelEU WtT, TtW, GHGI, target, compliance balance, indicative penalty equivalent and its EUR/annual-limit disclaimer;
- absolute and relative-to-B0 changes;
- factor status, qualification, requested/resolved path, fallback reason and evidence;
- calculation, constraint and execution statuses;
- conditional recommendations and concrete switch points;
- calculation, factor and port-rule versions.

Assert changing `DisplayConfig` changes only rendered strings and never the input result object or CSV output.

- [x] **Step 2: Run PDF tests and confirm failure**

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_reports -v
```

Expected: FAIL because the current PDF is a single-candidate summary and omits required sections.

- [x] **Step 3: Build a multi-section auditable report**

Use repeated table headers and fixed A4 margins. Split the report into case boundary, conclusions, scenario comparison, constraints/thresholds, factor evidence, port evidence, issues and methodology/version sections. Long source IDs and Decimal strings must wrap within cells. The PDF consumes `DecisionCaseResult` and `DisplayConfig` only.

Add export endpoints that calculate once from the submitted case payload and pass the same result object directly to CSV/PDF serialization. Do not accept client-supplied calculated values as report truth.

- [x] **Step 4: Render and inspect the report**

Run tests, generate `output/pdf/mvp-multi-candidate.pdf`, render all pages with Poppler, and inspect page PNGs for clipped tables, overlapping text, missing glyphs and blank pages. Record the command and successful page count in this document's verification log.

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_reports tests.test_web_api -v
```

Expected: tests PASS and every rendered page is nonblank with no overflow.

- [x] **Step 5: Commit the complete reports**

```powershell
git add src/voyage_fuel/reports.py src/voyage_fuel/web.py tests/test_case_reports.py tests/fixtures/multi_candidate_case.json docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "feat: generate complete decision reports"
```

---

### Task 9: Single-Page Web Calculator

**Status impact:** M15 `NOT_STARTED -> IMPLEMENTED` after component and API tests; browser verification in Task 10 promotes it to `VERIFIED`.

**Files:**
- Create: `src/voyage_fuel/templates/index.html`
- Create: `src/voyage_fuel/static/app.js`
- Create: `src/voyage_fuel/static/styles.css`
- Modify: `src/voyage_fuel/web.py`
- Create: `tests/test_web_page.py`

**Interfaces:**
- Consumes: fuel/port lookup APIs, `POST /api/calculate`, CSV/PDF export endpoints.
- Produces: an in-browser, no-login, session-only workflow at `/`.

- [x] **Step 1: Write failing page contract tests**

Using `TestClient`, assert `/` loads an HTML page containing stable accessible IDs for:

```text
report year
departure and arrival port search
adjacent valid Port of Call confirmation
case currency
baseline fuel, mass and price
EUA price
candidate collection and add/remove commands
calculate command
result boundary summary
scenario comparison table
conditional recommendations
calculation basis/evidence view
display precision settings
CSV and PDF download commands
```

Assert JavaScript source references structured issue fields and never extracts error codes by parsing message text.

- [x] **Step 2: Run page tests and confirm failure**

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web_page -v
```

Expected: FAIL because no HTML application exists.

- [x] **Step 3: Implement the operational calculator workflow**

Use a restrained work-focused layout:

- persistent top bar with product name, calculation boundary status and export actions;
- input workspace with voyage fields followed by repeatable candidate rows;
- results workspace with `Overview`, `Scenarios`, `Thresholds` and `Evidence` tabs;
- compact tables for comparison, with units in headers and status text adjacent to affected results;
- inline field errors and candidate-level blocked panels that do not hide other candidates;
- display settings as numeric controls that change formatting only;
- no landing page, decorative hero, nested cards, animations that shift layout or marketing copy.

The browser holds input, raw result and display preferences only in JavaScript memory. Do not use cookies, `localStorage`, `sessionStorage`, IndexedDB or server sessions. A page reload must restore initial defaults and clear the previous case.

Use native controls for numeric input, checkboxes for binary confirmations, selects/menus for path choices, tabs for result views and clear command labels. Ensure table containers scroll horizontally on narrow screens without clipping text or controls.

- [x] **Step 4: Run page and API tests**

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web_page tests.test_web_api -v
```

Expected: PASS.

- [x] **Step 5: Commit the web calculator**

```powershell
git add src/voyage_fuel/templates/index.html src/voyage_fuel/static/app.js src/voyage_fuel/static/styles.css src/voyage_fuel/web.py tests/test_web_page.py docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "feat: add voyage decision web calculator"
```

---

### Task 10: Browser End-to-End and Responsive Verification

**Status impact:** M15 and M16 become `VERIFIED` when all acceptance checks pass.

**Files:**
- Create: `tests/e2e/test_mvp_flow.py`
- Create: `tests/e2e/test_display_precision.py`
- Modify: `pyproject.toml`
- Modify: `README.md`

**Interfaces:**
- Consumes: installed `voyage-fuel-web` command and complete browser application.
- Produces: repeatable desktop/mobile MVP acceptance evidence.

- [x] **Step 1: Write the complete browser flow tests**

With Python Playwright, automate:

1. open `/` at desktop `1440x900`;
2. enter 2026, `CNSHG`, `NLRTM`, confirm adjacent Port of Call and select EUR;
3. enter MDO B0 values and EUA price;
4. add UCO FAME and LNG candidates with different constraints;
5. calculate and assert B0, both candidates, target ratio, cost ranking and execution-pending status appear;
6. verify evidence includes port/factor sources and RFNBO fallback when an RFNBO candidate is added without proof;
7. change display decimals and assert raw API result, scenario IDs and ordering remain unchanged;
8. download CSV and PDF and assert nonempty files with expected headers/text;
9. reload and assert the case is cleared;
10. repeat the core flow at mobile `390x844` and assert no incoherent overlap or off-screen action controls.

Add a second flow where one custom candidate is blocked by missing evidence while another built-in candidate remains calculated.

- [x] **Step 2: Run E2E tests and confirm the first actionable failure**

Start the server on a free local port, then run:

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests/e2e -v
```

Expected before final implementation: at least one assertion fails for an incomplete browser behavior; collection and browser launch must succeed.

- [x] **Step 3: Fix only behavior proven by E2E failures**

Iterate on templates, JavaScript, CSS or API responses without moving calculations into the browser. Preserve stable element IDs and result contracts. For every fixed browser failure, rerun the smallest affected E2E test before the complete E2E suite.

- [x] **Step 4: Inspect desktop and mobile screenshots**

Capture results, scenario comparison, evidence and blocked-candidate states at both viewports. Verify:

- no overlapping text, controls or tables;
- all buttons and fields fit or wrap within their parent;
- fixed-format controls do not shift when values change;
- mobile tables use intentional horizontal scrolling;
- units, warnings and boundary language remain visible;
- no blank regions caused by failed assets or JavaScript errors.

- [x] **Step 5: Run the complete automated suite**

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
node --test port-identity-mapping.test.mjs port-scope-rates.test.mjs
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m compileall -q src tests
git diff --check
```

Expected: every Python, browser and Node test passes; compile and diff checks produce no error.

- [x] **Step 6: Commit browser verification and run instructions**

```powershell
git add tests/e2e pyproject.toml README.md docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "test: verify complete MVP workflow"
```

Update M15 and M16 to `VERIFIED` and record desktop/mobile screenshots and final test counts in `Verification Log`.

---

### Task 11: Calculation-Spec Boundary Completion

**Status impact:** Closes remaining test-matrix gaps in M05, M06 and M16.

**Files:**
- Modify: `tests/test_ets.py`
- Modify: `tests/test_fueleu.py`
- Modify: `tests/test_constraints.py`
- Modify: `tests/test_economics.py`
- Modify: `tests/test_case_calculator.py`
- Create: `tests/test_spec_matrix.py`

**Interfaces:**
- Consumes: all domain and case-level public interfaces.
- Produces: explicit coverage for every item in calculation-spec section 16.

- [x] **Step 1: Add an executable specification matrix**

Cover these previously incomplete boundaries explicitly:

- 2024, 2025, 2026, 2029 and 2030 targets, gas inclusion and surrender rates;
- EU ETS and FuelEU GWP constants remain isolated;
- port ranges `0`, `0.5`, `1` with surrender `0.4`, `0.7`, `1`;
- target exactly met, no mathematical solution and unreachable under constraints;
- budget, supply and blend limits individually and jointly binding;
- B100 retained as an infeasible mathematical reference when pure use is allowed;
- zero baseline percentage returns `ZERO_BASELINE` without division;
- one invalid candidate does not block B0 or other candidates;
- `null`, zero, `NA`, `RC` and blocking values remain distinct in JSON and reports;
- every result carries specification versions and source IDs;
- page/PDF display settings cannot alter CSV or raw result values.

- [x] **Step 2: Run the matrix and confirm any missing behavior fails**

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_spec_matrix -v
```

Expected: collection succeeds; any failure identifies one specific contract gap.

- [x] **Step 3: Correct only specification mismatches**

Make the smallest domain or output change needed for each failing matrix assertion. Do not broaden the MVP into annual FuelEU allocation, real penalties, banking, borrowing, pooling or physical lifecycle WtW.

- [x] **Step 4: Run the complete suite**

Use the Task 10 complete verification command. Expected: PASS.

- [x] **Step 5: Commit the specification matrix**

```powershell
git add tests src docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "test: complete MVP specification matrix"
```

---

### Task 12: Final MVP Acceptance and Branch Integration

**Status impact:** M01-M17 must be `VERIFIED`; exclusions remain `OUT_OF_SCOPE`.

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md`

**Interfaces:**
- Consumes: complete implementation and all verification evidence.
- Produces: one reproducible run path, final status record and integration-ready branch.

- [x] **Step 1: Verify a clean installation and startup**

Create a temporary virtual environment outside the repository, install `.[dev]`, start `voyage-fuel-web`, request `/health`, run one fixture through `/api/calculate`, and verify CSV/PDF downloads. Do not rely on undeclared globally installed packages.

Observed on 2026-09-02: non-editable install succeeded in a temporary Python 3.12 environment; the installed CLI returned `/health` 200, the fixture returned 200 with 12 scenarios and no case issues, CSV returned 200 with a non-empty structured export, and PDF returned 200 with a valid `%PDF-` signature. The wheel explicitly contains the HTML template, JavaScript, CSS and packaged port CSV.

- [x] **Step 2: Run all automated and visual checks**

Run the Task 10 full suite and the Task 8 PDF render check. Run Playwright desktop/mobile flows against the installed service. Record exact pass counts, Python version, browser version and verification date in `Verification Log`.

Observed on 2026-09-02: installed-package Playwright E2E `3/3` passed; Poppler rendered the installed-service PDF to 13 pages with exit code 0, and representative first/last pages were visually inspected. `pypdf` extraction confirmed the voyage-level limitation, annual-penalty disclaimer, procurement limitation and execution-pending status.

- [x] **Step 3: Audit the product boundary language**

Search application text, PDF output and README for claims of formal annual FuelEU compliance, real penalty, procurement recommendation or independent physical WtW reduction. Every FuelEU result must remain explicitly voyage-level and proportional; every execution status must remain pending.

Observed on 2026-09-02: no forbidden positive claim was found in application text or extracted PDF; required boundary language was present. The README and module table record that advanced custom-factor entry is available in the webpage as a minimal input adapter, while final factor completeness and evidence validation remain server-side.

- [x] **Step 4: Update the module table from evidence**

Set a module to `VERIFIED` only when its completion condition is met. Leave no P0/P1 module as `NOT_STARTED`, `IN_PROGRESS`, `IMPLEMENTED` or `BLOCKED`. Do not change excluded future capabilities to completed.

- [x] **Step 5: Commit the final status**

```powershell
git add README.md docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "docs: record verified MVP delivery"
git push origin python-calculation-kernel
```

- [ ] **Step 6: Finish the development branch**

Use `superpowers:requesting-code-review` for a final review, address verified findings, rerun all checks, then use `superpowers:finishing-a-development-branch` to choose merge, pull request or continued branch retention. Do not claim the MVP complete before this document shows M01-M17 as `VERIFIED` with a current verification log.

当前状态：代码审查和最终验收已完成；分支集成方式仍为 `PENDING_USER_DECISION`，工作树保留在 `python-calculation-kernel`。

## MVP Acceptance Checklist

- [x] A user can enter 2024-2030, two valid ports and confirm adjacent valid `Port of Call`.
- [x] A user can select a case currency, B0 fuel/mass/price and EUA price.
- [x] A user can add, edit and remove multiple independent candidate fuels or quotations.
- [x] Every candidate supports allowed pure use, specified ratios, blend cap, supply and incremental budget inputs.
- [x] B0, B100 when allowed, user ratios, target ratio and effective constraint boundaries form the fixed report set.
- [x] One candidate can be blocked without losing B0 or other candidate results.
- [x] Every scenario uses unrounded Decimal calculations and preserves B0 physical energy.
- [x] EU ETS years, gases, geographic rates and surrender rates match the specification.
- [x] FuelEU GHGI, target, balance and penalty equivalent match the voyage-level specification.
- [x] Current-model-cost and reference-adjusted-cost concepts remain separated.
- [x] Cross-candidate rankings and conditional recommendations use only eligible scenarios.
- [x] Results show absolute values, absolute changes and percentage changes relative to B0.
- [x] Results distinguish `BLOCKED`, `CALCULABLE`, `COMPARABLE` and `EXECUTION_CONDITIONS_PENDING`.
- [x] Errors identify case/candidate/scenario, component and field without message parsing.
- [x] Port identities, reasons, factor resolution, evidence, source IDs and versions are visible.
- [x] CSV contains raw values, units, currencies, statuses, versions, evidence and issues.
- [x] PDF contains the complete decision case and mandatory limitation language.
- [x] Page and PDF share display precision; display changes never alter raw values or decisions.
- [x] Browser refresh clears the case and no server/cloud history is created.
- [x] Desktop and mobile workflows pass Playwright tests and screenshot inspection.
- [x] A clean environment can install and start the application from README instructions.
- [x] All Python, Node, API, report and browser tests pass at the recorded final commit.
- [x] 高级自定义燃料模式只要求用户填写实际可获得的核心因子和一个来源编号；页面自动生成后端所需的单位、设备、资格和逐字段证据结构。
- [x] 普通非甲烷自定义路径默认隐藏 Cslip/滑移因子；CH4/N2O 按 0 估算必须由用户明确确认并标记为 `ESTIMATED`。
- [x] 气体自定义路径按需显示甲烷滑移适用性、Cslip 和滑移因子；未证明 RFNBO 资格时页面锁定普通 WtT 输入，不直接发送 RFNBO 公式模式。
- [x] 自定义 `pathId` 和自动生成的 `candidateId` 在页面会话内保持稳定且唯一；生物燃料 `BIO_E` 不因未证明资格被错误降级为静态 WtT。

网页现在通过最小输入适配支持高级自定义燃料因子录入；页面只负责默认值、条件显示、稳定身份和 payload 组装，最终字段、单位、滑移和证据完整性仍由 API/JSON 层校验，不改变本计划已验证的内核和报告边界。页面层会阻断未证明 RFNBO 的奖励公式；本轮遵循“不修改后端计算逻辑”的范围，直接构造 custom RFNBO JSON 时的资格一致性仍记录为后端后续加固项。

## Explicit MVP Exclusions

| Capability | Status | Reason |
| --- | --- | --- |
| `ELECTRICITY_OPS`, Port Stay and port zero-emission obligations | `OUT_OF_SCOPE` | Explicitly excluded by MVP design |
| Independent physical lifecycle WtW emissions or reduction | `OUT_OF_SCOPE` | Requires a separate lifecycle boundary and factor system |
| Automatic legal `Port of Call` determination | `OUT_OF_SCOPE` | User confirms adjacent valid calls |
| Vessel type, tonnage, ice class and ice-energy adjustment | `OUT_OF_SCOPE` | Explicitly excluded by MVP design |
| Special-route, member-state and vessel exemptions | `OUT_OF_SCOPE` | Explicitly excluded by MVP design |
| Formal annual low-GHGI energy allocation | `OUT_OF_SCOPE` | Requires complete annual data |
| Real annual FuelEU penalty settlement | `OUT_OF_SCOPE` | Current value is indicative voyage-level equivalent only |
| Banking, Borrowing and Pooling | `OUT_OF_SCOPE` | Future annual compliance stage |
| Annual rolling planning and fleet compliance | `OUT_OF_SCOPE` | Future product stages 4 and 5 |
| Login, cloud storage, case history and multi-user collaboration | `OUT_OF_SCOPE` | Single-user, session-only MVP |
| Exchange rates, volume quotations and energy-price conversion | `OUT_OF_SCOPE` | User supplies normalized case-currency/tonne prices |

## Verification Log

| Date | Commit | Evidence | Result |
| --- | --- | --- | --- |
| 2026-09-01 | `3ac7ebf` | Python unittest 59；Node port tests 29；compileall；`git diff --check` | Current single-candidate kernel baseline verified |
| 2026-09-01 | `1180092` | Task 1 focused contracts/models 10；Python unittest 67；compileall；`git diff --check` | Case contracts and report-year boundary verified |
| 2026-09-01 | `a168b6b` | Task 2 focused JSON/factor tests 24；Python unittest 77；Node port tests 29；compileall；`git diff --check` | Structured case parsing, exact field issues and legacy JSON compatibility verified |
| 2026-09-01 | `d019970` | Task 5 fix-focused provenance/port/factor tests 18；compileall；`git diff --check`；independent fix re-review | Factor/port provenance, partial unavailable states and OMR rule trace verified |
| 2026-09-01 | `86e86a0` | Task 3 focused orchestration/kernel tests 16 | Multi-candidate B0 orchestration, local blocking and price-status isolation verified |
| 2026-09-01 | `52abd74` | Task 4 focused calculation/comparison unittest 25；Python unittest 88；`git diff --check` | Cross-candidate Decimal projections, eligible rankings and conditional result contracts verified |
| 2026-09-01 | `8c062c3` | `pip install -e ".[dev]"`；API/JSON unittest 21；Python unittest 103；Node port tests 29；compileall；`git diff --check` | Stateless FastAPI calculation boundary, structured issues and Decimal response serialization verified |
| 2026-09-01 | `aa9bcf2` | Task 8 focused PDF/API unittest 20；Poppler `pdftoppm -png -r 120` rendered 4 pages；`pypdf` text extraction；compileall；`git diff --check` | Complete multi-candidate PDF sections, shared-result CSV/PDF exports, display-only precision and nonblank page rendering verified |
| 2026-09-02 | `abefa13` + Task 10 review fix round 3 | Python unittest 128；Node port tests 29；Playwright E2E 3；desktop/mobile/blocked screenshots；CSV parsed header/case/port/scenario/status assertions；PDF text extraction assertions for case/ports/scenarios/status/limitation；compileall；`git diff --check` | Browser workflow, responsive controls, RFNBO fallback evidence, display precision stability, blocked-candidate isolation and report content verified; generated PDF is local ignored output |
| 2026-09-02 | `58c6a81` | Temporary non-editable wheel install；installed CLI `/health`、case API、CSV/PDF；installed-package Playwright 3；Poppler 13-page render；pypdf boundary audit；Python unittest 140；Node port tests 29；compileall；`git diff --check` | Package assets and dev dependencies fixed; clean-environment runtime and final acceptance evidence verified |
| 2026-09-02 | working tree | Initial web page/API tests 16；MVP web-flow E2E 7；`node --check`；`git diff --check` | Advanced custom-factor minimal input adapter, explicit zero-estimate semantics, gas-field conditional display, rule-defined RWD, unqualified RFNBO protection and candidate-collection state preservation verified without backend changes |
| 2026-09-02 | working tree (review fixes) | Focused page/API/custom JSON 23；MVP web-flow E2E 11；`node --check`；`git diff --check` | BIO_E qualification handling, stable custom path IDs, unique generated candidate IDs, explicit gas methane-slip applicability and certified-WtT warning verified; backend calculation logic unchanged |
| 2026-09-02 | working tree (final verification) | Python unittest discover 150（含 Playwright E2E 12）；Node port tests 29；compileall；`node --check`；`git diff --check` | Advanced custom-factor webpage adapter and review fixes pass the complete repository acceptance run; no Python calculation files changed |
| 2026-09-03 | `9072dc1` + Task 6 documentation changes | Web/API/E2E focused suite 32；README boundary/runtime contract test；temporary Python 3.12 venv `.[dev]` install；installed CLI `/health`；fixture API 12 scenarios/0 case issues；CSV non-empty；PDF `%PDF-` signature；`node --check`；`git diff --check` | Complete web result contract, baseline advanced custom input, reproducible runtime instructions and boundary language verified; Task 7 final matrix remained |
| 2026-09-03 | `48e3481` | Task 7 focused matrix 20/20；最终 Python unittest discover 170；Node port tests 29；compileall；`node --check`；`git diff --check` | Counterexample fixtures strengthened after review; final acceptance evidence recorded; generated E2E artifacts remain uncommitted |
| 2026-09-03 | `7bed200` | Python factor/report/JSON focused suite 48；最终 Python unittest discover 185；Node port tests 29；compileall；`node --check`；`git diff --check` | 旧版 JSON 入口传递 report year；CSV/PDF 保留 source type、field name、unit、status、value；内置目录区分 FIXED/ESTIMATED 并补齐 eligibleBiomassFraction；最新生产代码已完成完整验收 |
| 2026-09-03 | `571f6ae` | 报告/自定义因子/JSON/追踪聚焦 62；网页契约聚焦 20；最终 Python unittest discover 189；Node port tests 29；compileall；`node --check`；`git diff --check`；独立代码审查无正确性发现 | CSV/PDF 保留自定义 `BIO_E` 的 `E`、`RFNBO_E` 的 `E/eu` 证据值；报告使用实际 `FuelComponent.eligible_biomass_fraction`；网页证据面板展示字段、来源类型、单位、核验状态和值；当前 MVP gap 已关闭 |

Future entries must record evidence after it has been run. Do not add expected pass counts as if they were observed results.

## Plan Self-Review

### 2026-09-03 Final Acceptance Update

Task 7 反例矩阵已在 `48e3481` 通过（20/20）。代码审查发现的旧版 JSON 年份传递、CSV/PDF 逐字段证据和内置证据状态语义问题已在 `7bed200` 修复；后续独立审计发现并在 `571f6ae` 修复了自定义 `E/eu` 证据值丢失、实际生物质比例误报和网页证据摘要不完整。修复后的聚焦套件和完整验收 Python 189、Node 29、`compileall`、`node --check` 和 `git diff --check` 均通过。M01-M17 当前满足 MVP 交付条件；分支集成方式仍待用户决定。工作树中四个 E2E 生成工件仍为未提交的本地输出。

- Spec coverage: tasks cover the MVP design's product shape, input, calculation, multi-candidate comparison, status, traceability, exports, webpage and acceptance requirements.
- Boundary coverage: annual FuelEU, real penalties and physical WtW remain explicit exclusions.
- Type consistency: case contracts originate in Task 1 and are consumed by Tasks 2-10; presentation never changes calculation inputs.
- Dependency order: contracts -> parsing -> orchestration -> comparison -> provenance -> API/runtime -> reports -> webpage -> browser/spec acceptance.
- Source of truth: this file contains both current status and remaining execution steps; README only points here.
