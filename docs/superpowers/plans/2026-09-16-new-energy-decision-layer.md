# 新能源混兑经济性决策层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有计算内核、API 输入含义和旧结果的前提下，把已有的新能源方案计算能力呈现为金老师要求的“加多少、花多少、省多少、净变化多少、推荐哪个”的决策功能。

**Architecture:** 保留 `calculate_voyage()`、`calculate_decision_case()`、`constraints.py` 和 `case_comparison.py` 的现有计算责任。新增内容集中在案例结果投影、页面决策摘要、CSV/PDF 业务摘要和回归测试；页面与报告只消费已有的 `DecisionCaseResult`、`CaseScenario.deltas`、约束结果和推荐结果，不重新计算。

**Tech Stack:** Python 3.12, `unittest`, FastAPI, Jinja2, 原生 JavaScript, ReportLab, Playwright, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-16-new-energy-decision-layer-design.md`

## Global Constraints

- 只在 `codex/new-energy-decision-layer` worktree 开发，不在 `main` 上修改代码。
- 不修改现有燃料因子、能源守恒、EU ETS、FuelEU 和混兑公式。
- 以现有 `DecisionCaseResult` 为唯一结果来源；页面、CSV 和 PDF 不得重新计算。
- FuelEU 指示性金额继续是航次级参考值，不进入当前模型成本、预算或默认成本排序。
- 没有新能源候选时，既有结果、API、旧导出字段和旧页面流程保持兼容。
- 新能源比例为 `0` 时必须与 B0 逐字段一致。
- 所有推荐继续显示 `EXECUTION_CONDITIONS_PENDING`，不能表述为采购或执行结论。
- 每个任务先写失败测试，再写最小实现；每个任务完成后运行对应聚焦测试并单独提交。

---

### Task 1: Freeze the decision-summary projection contract

**Files:**
- Modify: `src/voyage_fuel/contracts.py`
- Modify: `src/voyage_fuel/case_comparison.py`
- Modify: `src/voyage_fuel/case_calculator.py`
- Test: `tests/test_case_comparison.py`
- Test: `tests/test_case_calculator.py`

**Interfaces:**
- Consumes: `CaseScenario`, `ScenarioResult`, `DecisionCaseResult`, existing `MetricDelta`, `ConditionalRecommendation`.
- Produces: a stable `DecisionSummary` dataclass and `DecisionCaseResult.decision_summary`.

- [ ] **Step 1: Write the failing contract tests**

Add tests that calculate the existing UCO case and assert:

```python
summary = result.decision_summary
assert summary is not None
assert summary.baseline_scenario_id == "B0"
assert summary.cost_min_scenario_id == result.economics.cost_min_scenario_id
assert summary.target_min_cost_scenario_id == result.economics.target_min_cost_scenario_id
assert summary.max_improvement_scenario_id == result.economics.max_improvement_scenario_id

uco = next(row for row in result.scenarios if row.scenario_id == "uco@0.2")
assert summary.scenario_deltas["uco@0.2"]["fuel_cost"].delta == uco.deltas["fuel_cost"].delta
assert summary.scenario_deltas["uco@0.2"]["eua_cost"].delta == uco.deltas["eua_cost"].delta
assert summary.scenario_deltas["uco@0.2"]["model_cost"].delta == uco.deltas["model_cost"].delta
```

Also assert a blocked case has `decision_summary is None`, and an ordinary existing case result still serializes all pre-existing fields.

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```powershell
$env:PYTHONPATH = "src"
& ".\.venv\Scripts\python.exe" -m unittest tests.test_case_comparison tests.test_case_calculator -v
```

Expected: FAIL because `DecisionCaseResult.decision_summary` and `DecisionSummary` do not exist.

- [ ] **Step 3: Add the minimal immutable contract**

Add:

```python
@dataclass(frozen=True)
class DecisionSummary:
    baseline_scenario_id: str
    cost_min_scenario_id: str | None
    target_min_cost_scenario_id: str | None
    max_improvement_scenario_id: str | None
    scenario_deltas: Mapping[str, Mapping[str, MetricDelta]]
```

Extend `DecisionCaseResult` with `decision_summary: DecisionSummary | None = None`. Build it in `case_calculator.py` from the already-built scenarios and their `deltas`; do not call any calculation function. For each scenario expose only these business metrics in the summary map: `fuel_cost`, `eua_cost`, `model_cost`, `fueleu_ghgi_actual_g_per_mj`, `fueleu_compliance_balance_t`, and `fueleu_indicative_penalty_eur`.

- [ ] **Step 4: Run focused tests and legacy serialization tests**

Run:

```powershell
$env:PYTHONPATH = "src"
& ".\.venv\Scripts\python.exe" -m unittest tests.test_case_comparison tests.test_case_calculator tests.test_case_json_io tests.test_json_io -v
```

Expected: PASS; existing serialized keys remain present and the new field is additive.

- [ ] **Step 5: Commit**

```powershell
git add src/voyage_fuel/contracts.py src/voyage_fuel/case_comparison.py src/voyage_fuel/case_calculator.py tests/test_case_comparison.py tests/test_case_calculator.py
git commit -m "feat: add explicit new energy decision summary"
```

### Task 2: Add explicit decision results to CSV and PDF

**Files:**
- Modify: `src/voyage_fuel/reports.py`
- Test: `tests/test_case_reports.py`

**Interfaces:**
- Consumes: `DecisionCaseResult.decision_summary`, scenario-level `MetricDelta`, existing recommendation and constraint records.
- Produces: additive CSV `decision_summary` records and a PDF “New energy decision summary” section.

- [ ] **Step 1: Write failing report tests**

Add a CSV test that parses `decision_case_to_csv(make_result())` and asserts:

```python
summary_rows = [row for row in rows if row["record_type"] == "decision_summary"]
assert {row["metric_name"] for row in summary_rows} >= {
    "fuel_cost_delta",
    "eua_cost_savings",
    "model_cost_delta",
    "fueleu_ghgi_delta",
    "fueleu_balance_delta",
}
assert any(row["scenario_id"] == "B0" for row in summary_rows)
```

Add a PDF test requiring the text fragments `New energy decision summary`, `Additional fuel cost`, `EU ETS cost saving`, `Net cost change`, `Recommended quantity`, and `Blend ratio`.

- [ ] **Step 2: Run the tests and verify failure**

Run:

```powershell
$env:PYTHONPATH = "src"
& ".\.venv\Scripts\python.exe" -m unittest tests.test_case_reports -v
```

Expected: FAIL because the additive record type and PDF section are absent.

- [ ] **Step 3: Implement additive CSV rows**

Extend `CASE_CSV_COLUMNS` with `decision_type`, `recommended_quantity_tonnes`, and `recommended_blend_ratio`. Add one `decision_summary` row per recommended scenario and one row for the B0 baseline. Populate:

```text
fuel_cost_delta       = scenario.deltas["fuel_cost"].delta
eua_cost_savings      = -scenario.deltas["eua_cost"].delta
model_cost_delta      = scenario.deltas["model_cost"].delta
fueleu_ghgi_delta     = scenario.deltas["fueleu_ghgi_actual_g_per_mj"].delta
fueleu_balance_delta  = scenario.deltas["fueleu_compliance_balance_t"].delta
```

For each recommendation, set `decision_type` to its recommendation ID, `recommended_quantity_tonnes` to the scenario’s `candidate_mass_tonnes`, and `recommended_blend_ratio` to its ratio. Use empty values for unavailable recommendations. Keep all existing CSV record types and raw precision unchanged.

- [ ] **Step 4: Implement the PDF decision summary**

Before the generic scenario-change table, add a compact table with one row per available recommendation and columns:

```text
Decision type | Candidate | Recommended quantity (t) | Blend ratio
Additional fuel cost | EU ETS cost saving | Net cost change | FuelEU GHGI change
```

Read values from `DecisionSummary` and the referenced `CaseScenario.deltas`. Display unavailable recommendations with `-` and preserve the existing limitation text. Do not alter the existing scenario, evidence, or methodology sections.

- [ ] **Step 5: Run report regression tests**

Run:

```powershell
$env:PYTHONPATH = "src"
& ".\.venv\Scripts\python.exe" -m unittest tests.test_case_reports tests.test_reports -v
```

Expected: PASS, including existing byte/precision and auditability tests.

- [ ] **Step 6: Commit**

```powershell
git add src/voyage_fuel/reports.py tests/test_case_reports.py
git commit -m "feat: export new energy decision summary"
```

### Task 3: Present the decision workflow in the web page

**Files:**
- Modify: `src/voyage_fuel/templates/index.html`
- Modify: `src/voyage_fuel/static/app.js`
- Modify: `src/voyage_fuel/static/styles.css`
- Test: `tests/test_web_page.py`
- Test: `tests/e2e/test_mvp_flow.py`

**Interfaces:**
- Consumes: JSON `decision_summary`, `scenarios`, `recommendations`, `economics`, and `constraints`.
- Produces: a visible “新能源决策摘要” section and explicit scenario comparison labels.

- [ ] **Step 1: Write failing page and E2E assertions**

Add page-template assertions for these IDs and labels:

```text
#new-energy-decision-summary
新能源决策摘要
新增燃料成本
EU ETS 成本节省
净成本变化
推荐新能源用量
推荐混兑比例
```

In the complete E2E flow, after calculation assert the summary contains all six labels and a concrete candidate quantity/ratio. Assert that the existing B0 row, scenario IDs, ranking and display-precision invariance remain unchanged.

- [ ] **Step 2: Run the tests and verify failure**

Run:

```powershell
$env:PYTHONPATH = "src"
& ".\.venv\Scripts\python.exe" -m unittest tests.test_web_page -v
& ".\.venv\Scripts\python.exe" -m unittest tests.e2e.test_mvp_flow -v
```

Expected: FAIL because the summary container and labels do not exist.

- [ ] **Step 3: Add the summary container**

In `index.html`, add `#new-energy-decision-summary` inside the overview panel before the generic economics section. Keep the existing tabs, form IDs, table ID, and export controls unchanged.

- [ ] **Step 4: Render from the server result only**

In `app.js`, add:

```javascript
function scenarioMap(result) {
  return new Map((result.scenarios || []).map((row) => [row.scenario_id, row]));
}

function deltaValue(row, metric) {
  return row?.deltas?.[metric]?.delta ?? null;
}
```

Implement `renderNewEnergyDecisionSummary(result)`:

- Find the referenced scenario for `CURRENT_MODEL_COST_MIN`, `TARGET_MIN_COST:*`, and `MAX_COMPLIANCE_IMPROVEMENT:*`;
- Show candidate mass and ratio from the scenario result;
- Show `fuel_cost` delta as “新增燃料成本”;
- Show the negative of `eua_cost` delta as “EU ETS 成本节省”;
- Show `model_cost` delta as “净成本变化”;
- Show GHGI and compliance-balance deltas;
- Show `UNAVAILABLE` reason and assumptions when no economic recommendation exists;
- Always show `EXECUTION_CONDITIONS_PENDING`.

The helper must read precomputed `row.deltas`; it must not calculate any emissions, cost, balance, or ratio.

- [ ] **Step 5: Add explicit scenario columns without removing old columns**

Add columns for `新增燃料成本`, `EU ETS 成本节省`, and `净成本变化` using `row.deltas`. Keep all existing columns and scenario IDs so existing consumers and E2E ranking checks remain valid. Update the empty-row `colspan` to match the new column count.

- [ ] **Step 6: Add restrained responsive styling**

Style the summary as an unframed result section using the existing typography, spacing, and color tokens. Keep the comparison table horizontally scrollable on mobile and ensure the summary cards wrap without page-level horizontal overflow.

- [ ] **Step 7: Run web regressions**

Run:

```powershell
$env:PYTHONPATH = "src"
& ".\.venv\Scripts\python.exe" -m unittest tests.test_web_page tests.test_web_api -v
& ".\.venv\Scripts\python.exe" -m unittest tests.e2e.test_mvp_flow tests.e2e.test_display_precision -v
```

Expected: PASS at desktop and mobile sizes; existing API payloads, ranking, refresh clearing, blocked-candidate isolation and display precision remain unchanged.

- [ ] **Step 8: Commit**

```powershell
git add src/voyage_fuel/templates/index.html src/voyage_fuel/static/app.js src/voyage_fuel/static/styles.css tests/test_web_page.py tests/e2e/test_mvp_flow.py
git commit -m "feat: present new energy decision workflow"
```

### Task 4: Documentation, full verification, and branch handoff

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-09-16-new-energy-decision-layer-design.md`
- Test: `tests/test_spec_matrix.py`

**Interfaces:**
- Consumes: all implemented decision summary, report and web behavior.
- Produces: updated feature status and final verification evidence.

- [ ] **Step 1: Write the failing boundary/status test**

Add a specification-matrix assertion that the rendered page and report boundary text contain:

```text
新能源决策摘要
航次级 FuelEU
not a formal annual penalty
EXECUTION_CONDITIONS_PENDING
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```powershell
$env:PYTHONPATH = "src"
& ".\.venv\Scripts\python.exe" -m unittest tests.test_spec_matrix -v
```

Expected: FAIL until the feature-status documentation and rendered boundary assertions are aligned.

- [ ] **Step 3: Update documentation**

Update README current status to state that the branch adds the first-stage new-energy decision presentation and uses existing catalog paths. Record that the implementation does not add new fuel factors, annual FuelEU settlement, or procurement execution. Change the design document status from `待审核` to `已确认并进入实现` only after all preceding tasks pass.

- [ ] **Step 4: Run focused and full verification**

Run:

```powershell
$env:PYTHONPATH = "src"
& ".\.venv\Scripts\python.exe" -m unittest tests.test_case_comparison tests.test_case_calculator tests.test_case_reports tests.test_reports tests.test_web_api tests.test_web_page tests.test_spec_matrix -v
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
node --test port-scope-rates.test.mjs port-identity-mapping.test.mjs
python -m compileall src tests
node --check src/voyage_fuel/static/app.js
git diff --check
```

Run the E2E suite separately when Playwright is available:

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests/e2e -v
```

Record exact pass counts and any environment-only skips. Do not claim full completion if required E2E dependencies are unavailable or if any regression fails.

- [ ] **Step 5: Inspect the final diff**

Verify:

- no change to core formula modules unless required by a failing contract test;
- old CSV columns and record types remain;
- no page-level mobile overflow;
- no raw FuelEU annual-penalty wording;
- no uncommitted generated artifacts are included;
- the main worktree’s existing `tests/e2e/artifacts/desktop-result.csv` remains untouched.

- [ ] **Step 6: Commit documentation and verification evidence**

```powershell
git add README.md docs/superpowers/specs/2026-09-16-new-energy-decision-layer-design.md tests/test_spec_matrix.py
git commit -m "docs: record new energy decision feature verification"
```

## Completion Gate

The branch is ready for review only when:

- Task 1-4 tests pass;
- the existing feature behavior remains unchanged without candidates or at 0% blend;
- the page clearly answers quantity, blend ratio, added cost, EU ETS saving, FuelEU change and net cost;
- CSV and PDF contain the same decision summary values from the same result object;
- the implementation remains limited to the first-stage single-voyage decision layer.
