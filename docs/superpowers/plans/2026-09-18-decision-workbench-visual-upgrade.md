# Decision Workbench Visual Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved decision-workbench display design without changing the calculation kernel or result API.

**Architecture:** Extend the existing read-only frontend adapter so one result snapshot produces a complete decision view model: goal conclusions, all 2.5-level scenarios, the selected scenario's B0 deltas, candidate thresholds, switch points, and status explanations. Render those values in a master-detail workbench with native SVG charts and deterministic display formatting.

**Tech Stack:** Existing FastAPI/Jinja page, browser ES modules, native SVG, Node `node:test`, Python `unittest`/Playwright.

**Spec:** `docs/superpowers/specs/2026-09-17-decision-workbench-design.md`

## Global Constraints

- Do not modify calculation formulas, result JSON contracts, export contracts, or the legacy route.
- Read server-provided decimal strings; never recalculate domain values in the browser.
- FuelEU indicative EUR amounts remain outside case-currency model-cost charts.
- Preserve `recommendedScenarioId` and `selectedScenarioId` as separate states.
- Missing values must remain missing; never coerce them to zero.
- Keep the workbench responsive with no root horizontal overflow.
- Use native SVG and existing frontend modules; do not add a runtime dependency or CDN.

### Task 1: Freeze the visual view-model contract

**Files:**
- Modify: `tests/frontend/workbench-model.test.mjs`
- Modify: `src/voyage_fuel/static/workbench-model.mjs`

**Interfaces:**
- Produce `buildWorkbenchDisplayModel(result, submittedInput)` with `goalCards`, `scenarioRows`, `selectedDetail`, `thresholdGroups`, `switchPoints`, and `chartData`.
- Preserve `buildWorkbenchModel`, `selectGoal`, `selectScenario`, and `buildChartData` compatibility for existing callers.

- [ ] Write failing Node tests for three goal cards, all scenario rows, selected B0 deltas, threshold groups, switch points, and explicit report-vs-boundary labels.
- [x] Run `node --test tests/frontend/workbench-model.test.mjs` and confirm the new assertions fail because the view model is absent.
- [x] Implement the smallest pure mapping functions using existing result fields only.
- [x] Run the focused Node test and confirm it passes.
- [x] Add cases for B0-only, missing prices, unavailable goals, and unverified constraints.
- [x] Run all frontend tests and confirm no regression.

### Task 2: Implement semantic result sections

**Files:**
- Modify: `src/voyage_fuel/templates/workbench_results.html`
- Modify: `src/voyage_fuel/static/workbench-view.mjs`
- Modify: `tests/test_workbench_page.py`

**Interfaces:**
- Render stable hooks for `workbench-goal-cards`, `workbench-scenario-table`, `workbench-selected-detail`, `workbench-sensitivity`, and `workbench-evidence`.
- All click handlers select an existing scenario ID and never invoke calculation.

- [x] Add page contract assertions for the new section hooks and labels.
- [x] Run the focused Python page tests and confirm the assertions fail against the current template.
- [x] Render goal cards and the master-detail scenario workspace.
- [x] Render the selected scenario before/after table, reasons, statuses, and all 2.5-level scenario rows.
- [x] Render the sensitivity section with thresholds, price break-even values, switch points, and explicit empty states.
- [x] Run page contract and frontend tests.

### Task 3: Implement charts and display precision

**Files:**
- Modify: `src/voyage_fuel/static/workbench-charts.mjs`
- Modify: `src/voyage_fuel/static/workbench-view.mjs`
- Modify: `tests/frontend/workbench-model.test.mjs`

**Interfaces:**
- Add deterministic SVG builders for the cost waterfall, GHGI comparison, ratio-boundary rail, and value-switch rail.
- Chart builders receive pre-mapped data and never calculate domain economics.

- [x] Add failing tests for SVG labels, units, selected scenario state, missing-value fallback, and no FuelEU amount in the cost chart.
- [x] Run focused Node tests and verify expected failures.
- [x] Implement SVG builders with text alternatives and keyboard-selectable scenario points.
- [x] Implement display precision using the existing display settings without changing raw result strings.
- [x] Run all frontend tests.

### Task 4: Apply the visual system and responsive layout

**Files:**
- Modify: `src/voyage_fuel/static/workbench.css`
- Modify: `src/voyage_fuel/templates/workbench_results.html`
- Modify: `tests/e2e/test_workbench_flow.py`

- [x] Add E2E assertions for the merged master-detail section, table-to-detail selection, sensitivity visibility, and mobile no-overflow.
- [x] Run the new E2E assertions and confirm they fail before the CSS/template changes.
- [x] Implement color tokens, typography, spacing, table hierarchy, status styles, chart framing, and desktop/mobile breakpoints from the design spec.
- [x] Run focused E2E tests at desktop and 390px mobile widths.
- [x] Capture updated screenshots for visual review.

### Task 5: Full verification and evidence

**Files:**
- Modify: `docs/superpowers/plans/2026-09-18-decision-workbench-visual-upgrade.md`
- Create: `output/workbench-upgrade/screenshots/visual-upgrade-desktop.png`
- Create: `output/workbench-upgrade/screenshots/visual-upgrade-mobile.png`

- [x] Run frontend Node tests.
- [x] Run project Python tests with the repository virtual environment.
- [x] Run all Playwright E2E tests relevant to legacy and workbench flows.
- [x] Run JavaScript syntax checks, Python compileall, and `git diff --check`.
- [x] Inspect desktop and mobile screenshots for overlap, clipping, missing labels, and root horizontal overflow.
- [x] Record exact results and remaining business-acceptance gaps in this plan.

## Verification Record

日期：2026-09-18

实现结果：

- 结果工作台保留三类核心结论，同时展示全部 2.5 级报告方案；
- 方案表、目标卡、散点图和当前方案 B0 对比详情使用同一 `selectedScenarioId` 联动；
- 手动查看方案不再复用系统推荐原因；
- 成本图使用 B0 总成本、燃料成本变化、EU ETS 成本变化和当前方案总成本的累计瀑布结构；
- GHGI 图、比例边界轨道、实际报告点、当前报价/临界价格、EUA 报价/临界价格和方案切换点均有独立展示；
- FuelEU 指示性金额未进入案例货币成本图；
- 显示精度只作用于页面文本和图表标签，原始十进制结果和导出合同保持不变。

验证命令与结果：

| 验证项 | 结果 |
| --- | --- |
| `node --test tests/frontend/*.test.mjs` | 9 passed |
| `pytest tests/e2e/test_workbench_flow.py -q` | 4 passed |
| `pytest tests/test_workbench_page.py tests/test_workbench_contracts.py -q` | 8 passed，2 warnings |
| `pytest -q` | 255 passed，79 subtests passed，2 warnings |
| `node --test port-scope-rates.test.mjs port-identity-mapping.test.mjs` | 29 passed |
| `python -m compileall -q src tests` | passed |
| `node --check` 工作台 3 个 ES module | passed |
| `git diff --check` | passed，无空白错误 |

截图证据：

- [桌面工作台](D:/projects/工具MVP/output/workbench-upgrade/screenshots/visual-upgrade-desktop.png)
- [移动端工作台](D:/projects/工具MVP/output/workbench-upgrade/screenshots/visual-upgrade-mobile.png)

截图检查：

- 1440px：根节点 `scrollWidth=1440`，页面宽度无溢出；3 个目标卡、5 个报告方案、6 个 SVG 图表、1 个当前方案散点高亮；
- 390px：根节点 `scrollWidth=390`，页面宽度无溢出；表格仅在自身容器内滚动；
- 当前候选报价和 EUA 报价与各自临界值并列显示；
- 敏感性轨道使用短标签，完整名称和精确值保留在表格与悬浮说明中。

剩余事项：

- 技术验收已完成；
- 仍需真实业务使用者按设计第 8 节完成五项任务，确认“系统推荐”“手动查看”“FuelEU 指示性金额”和“航次级估算边界”没有被误读；
- 业务验收前不把新版工作台表述为正式采购建议或年度合规结算工具。
