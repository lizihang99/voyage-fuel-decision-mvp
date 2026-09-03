# MVP Gap Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 修复独立 MVP 审计发现的领域不变量、案例级比较、结果契约、报告、网页和运行文档缺口，使当前航次级 FuelEU/EU ETS 产品可以按现行规格接受最终验收。

**Architecture:** 保留 calculate_voyage(VoyageInput) -> VoyageResult 作为单候选高精度内核，在案例层补齐共享 B0、跨候选全局排序和全局参考价值下包络。输入边界统一在 json_io.py 和因子解析器校验；所有结果继续由同一份 DecisionCaseResult 驱动 API、网页、CSV 和 PDF。网页只负责输入适配和展示，不绕过服务端资格与错误契约。

**Tech Stack:** Python 3.12；标准库 dataclasses、decimal、json、csv、unittest；FastAPI；Uvicorn；Jinja2；ReportLab；Python Playwright；现有 Node 港口规则测试。

**Spec:**
- docs/superpowers/specs/2026-08-07-voyage-fuel-decision-mvp-design.md
- docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md
- docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
- 项目目标与总体架构.md
- 港口比例功能说明.md
- 燃料因子库规范.md

## Global Constraints

- MVP 只计算 2024-2030 年两个用户确认相邻有效 Port of Call 之间的一个航段。
- 所有方案使用 B0 的物理能源需求；一个混兑方案只包含一种基准燃料和一种候选燃料。
- 内部计算、排序、目标判断和临界点搜索使用 Decimal，中间步骤不按显示精度舍入。
- MVP 开放 36 条航行燃料路径；ELECTRICITY_OPS 不进入输入、计算和比较。
- EU ETS 在 2024-2025 年只纳入 CO2，2026 年起纳入 CO2、CH4 和 N2O。
- FuelEU 结果是航次级按比例分配估算；指示性罚款等值固定为 EUR，不进入当前模型成本或默认排序。
- 当前模型成本只包含燃料采购成本和 EUA 成本；价格缺失不阻断排放和合规计算，但阻止经济排序和临界点。
- 所有可计算方案的执行状态固定为 EXECUTION_CONDITIONS_PENDING。
- 未证明 RFNBO 资格时不得使用 RFNBO 奖励；rwd=2 只允许在合格 RFNBO 情景中使用。
- 非甲烷路径不套用甲烷滑移公式；不受支持的非零自定义 Cslip 只阻断该路径。
- 只有适用生物燃料路径和有效资格才允许 EU ETS 生物质零额；CH4/N2O 不因生物质 CO2 零额而自动归零。
- 页面、CSV 和 PDF 必须消费同一份原始 DecisionCaseResult；显示格式不能影响内部值、排序和状态。
- 一个候选阻断时，B0 和其他候选仍必须返回；案例级港口或 B0 能源错误才阻断整个案例。
- 不实现正式年度 FuelEU 结算、真实年度罚款、Banking、Borrowing、Pooling、独立物理生命周期 WtW、OPS、登录和云端历史。

## Current Audit Baseline

审计基线为提交 1f997394，分支 python-calculation-kernel，工作树和远端一致。已有验证日志记录 Python 150、Playwright 12、Node 港口 29 通过；本次审计采用定向复现，没有重复全量测试。

当前代码已经具备：36 条内置路径、港口比例、B0/B100/质量混兑、能源守恒、EU ETS 年份气体规则、FuelEU 基础公式、单候选约束和临界价格、FastAPI、CSV/PDF、基础网页流程以及高级自定义候选输入。

本计划只处理以下已复现缺口：

1. 案例成本排名排除 B0，可能推荐更贵候选。
2. 跨候选目标最低成本、最大改善和参考价值下包络未统一计算。
3. 自定义 RFNBO 资格和 rwd=2 可由直接 JSON/API 绕过。
4. 解析错误码被统一吞成 MISSING_REQUIRED_FACTOR，部分断言可能造成 HTTP 500。
5. 非生物燃料可伪造生物质零额，EU ETS 结果缺少逐气体和零额状态。
6. TARGET_NO_SOLUTION 时 x_max_improvement 丢失。
7. 因子设备、模式、逐字段证据和结果追溯不完整。
8. CSV 缺少约束和经济记录，网页结果字段和精度不完整。
9. README 缺少独立安装、启动和健康检查命令。
10. 高级自定义是否覆盖 B0 尚未在产品契约中明确。

## File Map

- src/voyage_fuel/models.py: 扩展因子、EU ETS 和案例经济结果的数据结构。
- src/voyage_fuel/contracts.py: 添加案例级经济结果和全局切换点契约，并约束至少一个候选。
- src/voyage_fuel/custom_factors.py: 校验自定义资格、模式、年份、RWD 和缺失字段。
- src/voyage_fuel/factors.py: 保持内置 RFNBO/Cslip 回退语义，补齐因子元数据和逐字段证据。
- src/voyage_fuel/json_io.py: 传递报告年份，保留结构化错误码并把断言转换为输入问题。
- src/voyage_fuel/emissions.py: 生成逐气体范围、清缴排除和生物质零额状态。
- src/voyage_fuel/constraints.py: 独立计算目标无解时的最大改善边界。
- src/voyage_fuel/case_comparison.py: 统一 B0 排名、案例级建议和全局切换点。
- src/voyage_fuel/case_calculator.py: 编排案例级经济结果并消费新的比较接口。
- src/voyage_fuel/provenance.py: 保存有效范围、因子设备和证据来源。
- src/voyage_fuel/reports.py: 完整 CSV/PDF 结果和共享显示配置。
- src/voyage_fuel/static/app.js: 完整结果渲染和字符串十进制格式化。
- src/voyage_fuel/templates/index.html: 结果表、阈值、证据和基准高级输入控件。
- README.md: 可复制的安装、启动、健康检查和测试命令。
- tests: 为每个审计反例建立公开契约测试，不依赖页面文本解析来判断领域结果。

## Status Handling

执行本计划期间，旧交付台账中标为 VERIFIED 的模块只表示已有代码和历史测试，不代表本次审计已确认完整满足。每个任务通过自己的聚焦测试后，才可以把对应模块从 PARTIAL 提升为 VERIFIED。只有最后一次完整验收和代码审查通过后，才能更新 2026-09-01-mvp-delivery-plan.md 的最终状态。

---

### Task 1: Enforce Factor Qualification and Structured Input Errors

**Files:**
- Modify: src/voyage_fuel/custom_factors.py
- Modify: src/voyage_fuel/factors.py
- Modify: src/voyage_fuel/json_io.py
- Modify: src/voyage_fuel/contracts.py
- Test: tests/test_custom_factors.py
- Test: tests/test_case_json_io.py
- Test: tests/test_factor_resolution.py

**Interfaces:**
- resolve_custom_factor(payload, report_year=None) -> FuelFactor receives the report year when called from the case parser; non-RFNBO legacy callers may omit it.
- _parse_component(payload, field_prefix, report_year) passes the same year to built-in and custom resolution.
- _InputError(code, field, message) remains the JSON boundary representation for one structured issue.

- [ ] Step 1: Add failing qualification and error-code tests

~~~python
def test_custom_rfnbo_without_qualification_is_blocked():
    parsed = parse_decision_case(custom_rfnbo_payload(
        qualification_status="NOT_DEMONSTRATED", wt_t_mode="RFNBO_E", rwd="2",
    ))
    self.assertTrue(any(issue.code == "MISSING_REQUIRED_FACTOR"
                        for issue in parsed.issues))

def test_invalid_cslip_preserves_structured_error_code():
    parsed = parse_decision_case(custom_payload(cslip="101"))
    self.assertEqual(parsed.issues[0].code, "INVALID_CSLIP")

def test_bio_e_missing_cf_co2_returns_issue_instead_of_assertion_error():
    parsed = parse_decision_case(custom_bio_payload(cf_co2="NA"))
    self.assertEqual(parsed.issues[0].code, "MISSING_REQUIRED_FACTOR")
~~~

同时增加 rwd=2 在 2024 年被阻断、空 candidates 数组在 candidates 字段返回 MISSING_REQUIRED_FACTOR 的测试。

- [ ] Step 2: Run the focused tests and record the expected failures

~~~powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_custom_factors tests.test_case_json_io tests.test_factor_resolution -v
~~~

预期失败：未证明 RFNBO 被接受、INVALID_CSLIP 被改成 MISSING_REQUIRED_FACTOR、BIO_E 缺字段抛出断言，以及空候选列表被接受。

- [ ] Step 3: Implement explicit qualification and error normalization

在 resolve_custom_factor 中读取并规范化 qualificationStatus，仅允许 NOT_DEMONSTRATED、INELIGIBLE、ASSUMED_ELIGIBLE、VERIFIED_ELIGIBLE。wtTMode 为 RFNBO_E 时只允许两个 eligible 状态；rwd=2 只允许合格 RFNBO 且报告年份为 2025-2030；其他模式只允许 rwd=1。所有用户输入断言改成带最小规格错误码的 ValueError。

在 json_io.py 中增加从 ValueError 前缀提取最低错误码的辅助函数，使 INVALID_CSLIP、INVALID_RWD、INVALID_EMISSION_FACTOR、RFNBO_E_EXCEEDS_LIMIT 等保持原码。捕获 AssertionError 并转换为 MISSING_REQUIRED_FACTOR。DecisionCaseInput 和 parse_decision_case 拒绝空候选列表。

- [ ] Step 4: Run the focused tests to verify the input boundary

执行 Step 2 命令。预期所有资格、错误码、断言转换和空候选测试通过，现有 JSON 和因子测试保持通过。

- [ ] Step 5: Commit the input-boundary fix

~~~powershell
git add src/voyage_fuel/custom_factors.py src/voyage_fuel/factors.py src/voyage_fuel/json_io.py src/voyage_fuel/contracts.py tests/test_custom_factors.py tests/test_case_json_io.py tests/test_factor_resolution.py
git commit -m "fix: enforce custom fuel qualification contracts"
~~~

### Task 2: Correct Case-Level Ranking, Constraints, and Global Economics

**Files:**
- Modify: src/voyage_fuel/case_comparison.py
- Modify: src/voyage_fuel/case_calculator.py
- Modify: src/voyage_fuel/constraints.py
- Modify: src/voyage_fuel/contracts.py
- Modify: src/voyage_fuel/models.py
- Test: tests/test_case_comparison.py
- Test: tests/test_case_calculator.py
- Test: tests/test_constraints.py
- Test: tests/test_economics.py

**Interfaces:**
- Add CaseValueSwitchPoint with from_scenario_id, to_scenario_id, from_candidate_id, to_candidate_id and value_star.
- Add CaseEconomicsResult with comparison_status, cost_min_scenario_id, target_min_cost_scenario_id, max_improvement_scenario_id and switch_points.
- Extend DecisionCaseResult with economics: CaseEconomicsResult | None.
- Add calculate_case_value_switch_points(scenarios) -> tuple[CaseValueSwitchPoint, ...]; it operates on every eligible fixed-report scenario, including B0.
- Keep calculate_value_switch_points for single-candidate VoyageResult; case-level code calls the global function once after all candidates are assembled.

- [ ] Step 1: Add failing case-level counterexamples

~~~python
def test_current_model_cost_minimum_can_be_b0():
    result = calculate_decision_case(case_with_expensive_hfo_candidate())
    recommendation = next(item for item in result.recommendations
                           if item.recommendation_id == "CURRENT_MODEL_COST_MIN")
    self.assertEqual(recommendation.scenario_id, "B0")
    self.assertEqual(next(item for item in result.scenarios
                          if item.scenario_id == "B0").current_model_cost_rank, 1)

def test_global_switch_points_remove_dominated_candidate_intersections():
    result = calculate_decision_case(case_with_uco_and_lng_candidates())
    self.assertTrue(all(point.to_candidate_id != "lng"
                        for point in result.economics.switch_points))

def test_target_no_solution_still_reports_maximum_improvement_boundary():
    result = calculate_voyage(target_no_solution_request())
    self.assertEqual(result.constraints.target_status, "TARGET_NO_SOLUTION")
    self.assertIn(result.constraints.x_max_improvement,
                  (Decimal("0"), result.constraints.x_cap))
~~~

同时增加价格缺失时 B0 保持可计算、但不进入成本排序的测试。

- [ ] Step 2: Run the focused comparison and constraint tests

~~~powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_comparison tests.test_case_calculator tests.test_constraints tests.test_economics -v
~~~

预期失败：B0 当前没有排名、被 LNG 支配的局部交点仍然输出、TARGET_NO_SOLUTION 时最大改善仍为 None。

- [ ] Step 3: Include B0 in the eligible current-cost set

修改 build_case_scenarios，使 B0 在 model_cost 存在时获得可比较状态，否则保持 CALCULABLE。B0 与可行、可比较的候选场景共同排序，按 model_cost、scenario_id 排序并分配连续排名。build_recommendations 在 B0 最低时返回 B0；只有没有任何有价格的可行场景时才返回 PRICE_REQUIRED_FOR_COMPARISON。

- [ ] Step 4: Compute target and improvement decisions across candidates

所有候选场景组装完成后，选择全局最低成本且达到 FuelEU 目标的场景，以及全局最大合规改善场景。保留候选本地 ConstraintResult 供诊断，同时将案例级 winner ID 写入 CaseEconomicsResult 和条件式建议。阻断候选不能影响 B0 或其他候选。

- [ ] Step 5: Implement the global lower envelope and target-independent improvement

将所有合格 CaseScenario（包括 B0）传入 calculate_case_value_switch_points。使用未舍入 Decimal 计算非负交点，分别探测交点左右的实际胜者，只保留全局胜者发生改变的交点，并保留两侧 scenario/candidate ID。不要再把 VoyageResult.economics.switch_points 直接复制到案例建议。constraints.py 仅在 TARGET_NOT_APPLICABLE 时不返回最大改善；TARGET_NO_SOLUTION 仍按 Psi 返回 x_cap 或零。

- [ ] Step 6: Run focused tests and commit the case decision fix

~~~powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_comparison tests.test_case_calculator tests.test_constraints tests.test_economics -v
git add src/voyage_fuel/case_comparison.py src/voyage_fuel/case_calculator.py src/voyage_fuel/constraints.py src/voyage_fuel/contracts.py src/voyage_fuel/models.py tests/test_case_comparison.py tests/test_case_calculator.py tests/test_constraints.py tests/test_economics.py
git commit -m "fix: compare case scenarios including baseline"
~~~

### Task 3: Complete ETS Output, Biomass Qualification, and Provenance

**Files:**
- Modify: src/voyage_fuel/models.py
- Modify: src/voyage_fuel/emissions.py
- Modify: src/voyage_fuel/factors.py
- Modify: src/voyage_fuel/custom_factors.py
- Modify: src/voyage_fuel/provenance.py
- Modify: src/voyage_fuel/json_io.py
- Test: tests/test_ets.py
- Test: tests/test_factors.py
- Test: tests/test_factor_catalog_audit.py
- Test: tests/test_provenance.py
- Test: tests/test_case_json_io.py

**Interfaces:**
- Extend FuelFactor with equipment_id, wt_t_mode and factor_level metadata while retaining backward-compatible defaults for legacy constructors.
- Add EtsFuelComponentStatus(path_id, qualification_status, eligible_biomass_fraction, zero_rating_status).
- Extend EtsResult with mrv_raw_by_gas, ets_scope_by_gas, excluded_from_ets_surrender, s_ets_geo, s_ets_surrender, s_ets_effective and zero_rating_status_by_fuel_component.
- Extend ResultProvenance with eu_ets_effective_rate; factor traces must expose equipment and field-level source IDs through the factor object.

- [ ] Step 1: Add failing ETS and traceability tests

~~~python
def test_hfo_cannot_claim_biomass_zero_rating():
    with self.assertRaisesRegex(ValueError, "INVALID_BIOMASS_FRACTION"):
        FuelComponent(hfo_factor(), Decimal("600"),
                      eligible_biomass_fraction=Decimal("1"),
                      qualification_status="ASSUMED_ELIGIBLE")

def test_2024_exposes_ch4_n2o_excluded_from_surrender():
    result = calculate_eu_ets(2024, [hfo_amount()], scope_rates(), Decimal("80"))
    self.assertEqual(result.ets_scope_by_gas["CO2"], result.s_ets_effective)
    self.assertTrue(result.excluded_from_ets_surrender["CH4"])
    self.assertTrue(result.excluded_from_ets_surrender["N2O"])

def test_custom_factor_keeps_equipment_and_field_evidence():
    factor = resolve_custom_factor(verified_custom_payload())
    self.assertEqual(factor.equipment_id, "CUSTOM_ENGINE")
    self.assertEqual({item.field_name for item in factor.source_evidence},
                     {"lcv", "wtT", "cfCO2", "cfCH4", "cfN2O", "cslip",
                      "methaneSlipApplicable", "rwd", "eligibleBiomassFraction"})
~~~

增加 UCO_FAME 合格生物质、LPG/NH3 估算 Cslip 和 2026 三气体纳入测试。

- [ ] Step 2: Run the focused ETS and provenance tests

~~~powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_ets tests.test_factors tests.test_factor_catalog_audit tests.test_provenance tests.test_case_json_io -v
~~~

预期失败：ETS 字段、非生物燃料零额约束、设备元数据和逐字段证据均缺失。

- [ ] Step 3: Bind biomass eligibility to supported fuel definitions

添加目录元数据标识可携带合格生物质的路径。仅当路径受支持且资格为 ASSUMED_ELIGIBLE 或 VERIFIED_ELIGIBLE 时允许 eligibleBiomassFraction 大于零；NOT_DEMONSTRATED 和 INELIGIBLE 固定为零。输出 ZERO_RATED、NOT_ZERO_RATED 或 ZERO_RATING_NOT_VERIFIED 状态，不改变 CH4/N2O 因子。

- [ ] Step 4: Populate the complete ETS result fields

calculate_eu_ets 保留逐气体原始值，生成 mrv_raw_by_gas，在 2024-2025 标记 CH4/N2O 排除，分别应用 s_ets_geo、s_ets_surrender 和 s_ets_effective 后再求 EUAs。现有数值向量必须保持不变；范围为零时仍输出完整状态映射。

- [ ] Step 5: Preserve factor metadata and field-level evidence

从内置定义和自定义 payload 填充 equipment_id、wt_t_mode、factor_level。为目录因子每个字段生成正确单位和状态的证据记录。自定义证据保留自身 field_name、source_id 和 verification_status，禁止将一条来源记录复制到不相关字段。ResultProvenance 增加有效 ETS 比例。

- [ ] Step 6: Run focused tests and commit the result contract fix

~~~powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_ets tests.test_factors tests.test_factor_catalog_audit tests.test_provenance tests.test_case_json_io -v
git add src/voyage_fuel/models.py src/voyage_fuel/emissions.py src/voyage_fuel/factors.py src/voyage_fuel/custom_factors.py src/voyage_fuel/provenance.py src/voyage_fuel/json_io.py tests/test_ets.py tests/test_factors.py tests/test_factor_catalog_audit.py tests/test_provenance.py tests/test_case_json_io.py
git commit -m "fix: preserve ETS and factor provenance detail"
~~~

### Task 4: Make CSV and PDF Fully Auditable

**Files:**
- Modify: src/voyage_fuel/reports.py
- Modify: src/voyage_fuel/formatting.py
- Test: tests/test_case_reports.py
- Test: tests/test_reports.py

**Interfaces:**
- decision_case_to_csv(result, display_config=None) returns raw, unrounded values and does not recalculate.
- Add stable CSV record types constraint and economics; retain existing case, port, scenario, recommendation, switch_point, factor_evidence and issue records.
- decision_case_to_pdf(result, display_config=None) consumes the same DecisionCaseResult and DisplayConfig used by the page export.

- [ ] Step 1: Add failing CSV/PDF contract tests

断言 CSV 含约束和经济记录，且包含 x_budget、x_supply、x_cap、x_target_min、x_max_improvement、comparison_status、pc_break_even、pe_break_even 和全局切换 ID。断言 CSV/PDF 含 ETS effective rate、排除气体、零额状态、设备 ID、逐字段证据，以及“不输出独立物理生命周期 WtW 减排”的明确限制语句。

- [ ] Step 2: Run focused report tests and confirm missing records

~~~powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_reports tests.test_reports -v
~~~

- [ ] Step 3: Add constraint/economics CSV rows without changing raw precision

扩展 CASE_CSV_COLUMNS。新增记录使用完整非科学计数法 Decimal 字符串、内部单位和案例币种；CSV 忽略 display_config。switch_point 只使用 result.economics 的全局切换点；候选本地经济结果必须显式标记为 local。

- [ ] Step 4: Complete PDF sections and shared boundary language

沿用现有 PDF 分区，补充 ETS 映射和状态、完整因子证据、案例级约束/经济结果和全局切换点。页面和 PDF 使用同一段边界文案：FuelEU WtW/GHGI 是法规口径的航次级输出，不提供独立物理生命周期 WtW 减排、正式年度罚款结算或采购建议。

- [ ] Step 5: Run focused tests and commit report changes

~~~powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_reports tests.test_reports -v
git add src/voyage_fuel/reports.py src/voyage_fuel/formatting.py tests/test_case_reports.py tests/test_reports.py
git commit -m "feat: complete auditable case exports"
~~~

### Task 5: Complete Web Results, Precision, and Advanced Input Coverage

**Files:**
- Modify: src/voyage_fuel/static/app.js
- Modify: src/voyage_fuel/templates/index.html
- Modify: src/voyage_fuel/static/styles.css
- Modify: src/voyage_fuel/web.py
- Test: tests/test_web_api.py
- Test: tests/test_web_page.py
- Test: tests/e2e/test_mvp_flow.py
- Test: tests/e2e/test_display_precision.py

**Interfaces:**
- The page keeps one state.result raw object and passes it to every view. Export endpoints use the same validated calculation-and-serialization path on the server, never trust client-calculated fields, and serialize the resulting DecisionCaseResult once for the requested format.
- Add a pure JavaScript formatDecimalString(value, decimals) that rounds decimal strings without converting them through Number; formatField(value, kind, displayConfig) selects mass, energy, ratio, scope, intensity, gas, price or factor precision.
- The payload builder may render a reusable custom fuel editor for both baseline and candidate roles. Its generated payload uses the same resolve_custom_factor contract as the API.

- [ ] Step 1: Freeze the advanced-mode role contract

采用完整解释：高级自定义燃料输入同时适用于 B0 和候选燃料。增加页面测试：切换基准为高级模式，只输入核心值，提交后确认生成稳定 pathId、equipmentId、单位和逐字段证据。候选高级自定义流程保留为回归测试。

- [ ] Step 2: Add failing page output assertions

要求页面可见或可通过稳定 data 属性读取以下字段：

- 港口名称、两制度身份、范围比例和判断理由；
- 场景基准/候选质量、物理能源、燃料成本和模型成本；
- EU ETS CO2/CH4/N2O、纳入气体、排除气体、EUAs 和 EUA 成本；
- FuelEU WtT、TtW、GHGI、目标、余额、指示性罚款和相对 B0 变化；
- 目标、预算、供应和混兑边界；
- 候选因子模式、资格、因子状态、设备和来源 ID；
- 全局当前成本、目标最低成本、最大改善和切换点建议。

- [ ] Step 3: Run focused web tests and record failures

~~~powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web_api tests.test_web_page tests.e2e.test_display_precision -v
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.e2e.test_mvp_flow -v
~~~

预期失败对应缺失 DOM 字段、基准高级编辑器和精度不一致。

- [ ] Step 4: Render complete result views from the raw result

扩展 overview、scenario、thresholds 和 evidence 面板。所有字段只从 state.result 读取，不在前端重新计算。显示 recommendation.value_star、全局 from/to candidate ID 和 EXECUTION_CONDITIONS_PENDING。保留移动端横向滚动和候选局部阻断行为。

- [ ] Step 5: Align page and PDF display precision

使用与 DisplayConfig 默认值一致的 displayConfig。气体和合规余额使用 gas 精度，WtT/TtW/GHGI/target 使用 intensity 精度，范围使用 scope 精度，因子使用 factor 精度。保留当前四个可见控件，其余类别使用共享默认值；导出请求发送同一个配置对象。

- [ ] Step 6: Run browser acceptance tests and commit web changes

~~~powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web_api tests.test_web_page tests.e2e.test_display_precision -v
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.e2e.test_mvp_flow -v
git add src/voyage_fuel/static/app.js src/voyage_fuel/templates/index.html src/voyage_fuel/static/styles.css src/voyage_fuel/web.py tests/test_web_api.py tests/test_web_page.py tests/e2e/test_mvp_flow.py tests/e2e/test_display_precision.py
git commit -m "feat: complete MVP web result workflow"
~~~

### Task 6: Make Installation and Product Boundaries Reproducible

**Files:**
- Modify: README.md
- Modify: docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
- Test: tests/test_web_api.py
- Test: tests/e2e/test_mvp_flow.py

**Interfaces:**
- README commands use the project runtime and packaged voyage-fuel-web entry point; no command relies on globally installed packages.
- The existing delivery plan remains the module status ledger; this remediation plan records implementation steps and evidence for the gaps.

- [ ] Step 1: Add a clean-environment command block to README

Document this reproducible flow:

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[dev]"
.\.venv\Scripts\voyage-fuel-web.exe --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/health
~~~

同时写明如何用 tests/fixtures/multi_candidate_case.json 调用 /api/calculate、CSV/PDF 导出、聚焦测试以及 FuelEU 航次级和物理 WtW 限制。

- [ ] Step 2: Add boundary text consistency checks

增加测试，检查页面源代码、提取后的 PDF 文本和 README 均包含 voyage-level、not a formal annual penalty、not a procurement recommendation、independent physical lifecycle WtW reduction、EXECUTION_CONDITIONS_PENDING。若出现正式年度合规、真实罚款或物理 WtW 正向声明则失败。

- [ ] Step 3: Update the status ledger only from observed evidence

Tasks 1-5 通过后，将受影响模块在 2026-09-01-mvp-delivery-plan.md 中更新为真实中间状态；Task 7 通过后再设为 VERIFIED。验证日志只记录实际运行的命令、通过数、Python/浏览器版本和提交 ID，不填写预期数字。

- [ ] Step 4: Run clean installation verification and commit documentation

在仓库外创建临时 Python 3.12 环境，安装 wheel，启动已安装 CLI，验证 /health、/api/calculate、CSV 和 PDF，随后删除临时环境。完成边界文案检查后提交：

~~~powershell
git add README.md docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md tests/test_web_api.py tests/e2e/test_mvp_flow.py
git commit -m "docs: make MVP runtime and boundaries reproducible"
~~~

### Task 7: Final Targeted Matrix, Full Acceptance, and Review Gate

**Files:**
- Modify: tests/test_spec_matrix.py
- Modify: tests/test_regressions.py
- Modify: docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
- Test: all existing Python, Node and E2E test files

**Interfaces:**
- Tests exercise public JSON/API and result objects wherever a contract-level test is possible.
- Final status is VERIFIED only when every M01-M17 completion condition has current code, focused tests, one final full run and final review.

- [x] Step 1: Add missing specification-matrix cases

覆盖所有审计反例：B0 低于所有候选、被支配的跨候选交点、自定义 RFNBO 不匹配、2024 年 rwd=2、BIO_E 缺 cfCO2、Cslip 错误码、非生物零额、目标无解最大改善、空候选、ETS 排除气体映射、设备和逐字段证据、CSV 约束/经济记录、页面/PDF 精度一致性和基准高级自定义。

- [x] Step 2: Run each focused suite after the corresponding task

使用各任务命令进行短回归；小改动后不重复运行完整仓库套件，完整套件只在最终验收阶段运行一次。

- [x] Step 3: Run the final full acceptance once

~~~powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
node --test port-identity-mapping.test.mjs port-scope-rates.test.mjs
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m compileall -q src tests
node --check src/voyage_fuel/static/app.js
git diff --check
~~~

预期证据：Python 完整通过且包含 E2E、Node 29 项、compileall、JavaScript 语法检查和 diff-check 均通过。若失败，先修复相应任务并运行聚焦测试，再重新执行最终命令。

- [x] Step 4: Perform final code review and status update

使用 superpowers:requesting-code-review，处理已确认问题，重新运行受影响的聚焦套件和最终验收命令，再使用 superpowers:finishing-a-development-branch 选择合并方式。只根据实际证据更新 M01-M17；所有排除项保持 OUT_OF_SCOPE。

- [x] Step 5: Commit the final acceptance record

~~~powershell
git add tests/test_spec_matrix.py tests/test_regressions.py docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md
git commit -m "test: close audited MVP gaps"
git push origin python-calculation-kernel
~~~

## Completion Gate

本计划只有在以下条件全部满足后才算完成：

- B0 参与当前成本排序，并且可以成为最低成本推荐方案。
- 目标最低成本、最大改善和参考价值切换均在完整候选场景集合上计算。
- 直接 JSON/API 无法在未具备 RFNBO 资格时使用奖励；最低错误码保持结构化。
- 生物质零额受燃料路径和资格约束；ETS 结果包含原始气体、纳入/排除气体、三个范围比例和组分状态。
- 因子结果保留设备、模式、状态和逐字段证据。
- 目标无解时仍暴露独立最大改善结果。
- CSV 和 PDF 含完整案例、约束、经济、追溯和限制文案。
- 页面显示完整 MVP 结果契约、全局建议和正确的共享精度。
- README 可以复现安装、启动、健康检查和一次 API/导出流程。
- 聚焦反例测试和唯一一次最终完整验收通过；交付台账只记录实际证据。

以下能力继续明确排除：正式年度 FuelEU 结算、真实年度罚款、年度低 GHGI 分配、Banking、Borrowing、Pooling、OPS/Port Stay、自动 Port of Call 判断、船舶/冰级豁免、独立物理生命周期 WtW、认证登录、云端存储、案例历史和币种/报价单位换算。
