# 系统演示案例 Implementation Plan

> 本文件为原示例加载功能的历史计划。后续画面框选与教程以 [示例就地教程开发计划](2026-09-20-contextual-example-tutorial.md) 为准；不再安排修改条件练习，既有编辑和核验能力保留。新计划尚未实施。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有航次燃料决策页面增加两个低操作成本的可加载演示案例，并用独立冻结案例逐项核验用户实际操作路径。

**Architecture:** 静态资源保存两个完整产品请求，不保存标准答案。前端先校验并一次性映射到现有表单，再调用现有计算 API；后端只提供可选说明页。浏览器测试在产品请求前启动独立参考计算，测试输入、结果、导出和状态保护。

**Tech Stack:** FastAPI/Jinja2、原生 JavaScript、CSS、Playwright、Python `unittest`、现有 `tools/validation/business_case_*` 独立参考核验器。

**Spec:** `docs/superpowers/specs/2026-09-20-teaching-examples-design.md`

## Global Constraints

- 不修改生产计算公式、计算结果 JSON、推荐算法、CSV/PDF 合同。
- 示例请求必须与 `tests/fixtures/business-cases/A-2025/request.json` 和 `B-default/request.json` 一致。
- 浏览器不加载 `expected.json`，标准答案只能在测试进程中由独立参考端生成或校验。
- 所有报价、用量、供应、资格和证据均标记为合成条件，不表达真实采购或认证结论。
- 输入模式草稿只供前端重绘，不能把无关草稿字段发送到 `/api/calculate`。
- 任何替换操作必须先完成资源校验；失败不得清空当前输入或结果。
- 保留当前工作区中用户和之前任务的未提交修改，不执行 reset、checkout 或大范围格式化。
- 生产代码变更遵循失败测试、最小实现、聚焦回归的 TDD 顺序。

---

### Task 1: Freeze example resource and validation contract

**Files:**
- Create: `src/voyage_fuel/static/teaching-examples.json`
- Create: `tests/test_teaching_examples.py`
- Test reference: `tests/fixtures/business-cases/A-2025/request.json`, `tests/fixtures/business-cases/B-default/request.json`

**Interfaces:**
- Produces static JSON shape `{version: 1, examples: {basic, comparison}}`.
- Test helper validates that every distributed request equals its frozen business-case request and contains no `expected` or `result` field.

- [ ] **Step 1: Write the failing contract tests** for two IDs, synthetic flag, exact request equality, no standard answer, and invalid version/missing required request fields.
- [ ] **Step 2: Run `\.venv/Scripts/python.exe -m unittest tests.test_teaching_examples -v` and verify it fails because the static resource and loader contract do not exist.**
- [ ] **Step 3: Add the exact two request copies from the fixtures, with `version: 1`, names, case IDs and `synthetic: true`.**
- [ ] **Step 4: Run the same focused test and confirm it passes.**
- [ ] **Step 5: Confirm the new file is covered by the existing `static/*` package-data rule.**

### Task 2: Add the single example entry point and safe loader

**Files:**
- Modify: `src/voyage_fuel/templates/index.html`
- Modify: `src/voyage_fuel/static/app.js`
- Modify: `src/voyage_fuel/static/styles.css`
- Modify: `tests/e2e/test_teaching_examples.py`

**Interfaces:**
- UI IDs: `try-examples`, `example-menu`, `example-status`, `example-error`.
- Loader: `loadExample(key)` fetches `/static/teaching-examples.json`, validates the request, projects it into the existing form, then calls `calculate()`.
- Existing `payload()`, `calculate()`, `invalidateResults()`, export controls and result renderers remain the only calculation path.

- [ ] **Step 1: Write failing browser tests** for menu loading basic/comparison, actual request equality, automatic calculation, result status, two views, export availability and 390px no-overflow.
- [ ] **Step 2: Run `\.venv/Scripts/python.exe -m unittest tests.e2e.test_teaching_examples -v` and verify the entry point is absent.**
- [ ] **Step 3: Add the menu and minimal status/error markup; do not add a new page or wizard.**
- [ ] **Step 4: Implement loader validation for version, metadata, all required fields, decimal strings, path IDs, duplicate candidate IDs, RFNBO E/eu and candidate array shape; replace DOM only after validation.**
- [ ] **Step 5: Add state invalidation so edits disable export and mark the example as modified; confirm before replacing modified input; preserve state on cancel/failure.**
- [ ] **Step 6: Run focused browser tests and fix only failures in this flow.**

### Task 3: Preserve advanced candidate drafts without polluting API requests

**Files:**
- Modify: `src/voyage_fuel/static/app.js`
- Modify: `tests/e2e/test_teaching_examples.py`

**Interfaces:**
- Each candidate has `builtinDraft` and `customDraft` in UI state.
- `readCandidates()` returns only the active mode's API fields; draft-only keys are removed before `payload()`.

- [ ] **Step 1: Add failing browser tests** for builtin E/eu/qualification preservation across custom switch, candidate add/remove and rerender; add the inverse custom draft test.
- [ ] **Step 2: Run the focused test and capture the lost-field failure.**
- [ ] **Step 3: Implement separate draft capture and restoration; add the visible `eu` input for RFNBO verified qualification and require it when that branch is active.**
- [ ] **Step 4: Add a path-change reset test and implementation so old path qualifications are cleared.**
- [ ] **Step 5: Run the focused browser test and inspect the submitted JSON to verify no `builtinDraft` or `customDraft` is sent.**

### Task 4: Add optional short guide page

**Files:**
- Create: `src/voyage_fuel/templates/examples_guide.html`
- Modify: `src/voyage_fuel/web.py`
- Modify: `src/voyage_fuel/static/styles.css`
- Modify: `tests/test_teaching_examples.py`

**Interfaces:**
- Route: `GET /examples/guide` returns a standalone HTML page.
- Guide links back to `/?view=workbench` and describes only the two supported flows.

- [ ] **Step 1: Add failing route/template contract tests** for both page views linking to the guide and the guide containing the two case names and synthetic-data boundary.
- [ ] **Step 2: Run focused tests and confirm 404/missing link.**
- [ ] **Step 3: Add the route and concise guide content; preserve the existing route and static asset contracts.**
- [ ] **Step 4: Run focused tests and inspect desktop/mobile rendering for wrapping and no-overflow.**

### Task 5: Independent end-to-end verification and packaging

**Files:**
- Modify: `tests/e2e/test_teaching_examples.py`
- Create: `docs/validation/teaching-examples-design.md` only after implementation notes are updated if needed
- Output only: `output/teaching-examples-business-validation.json` (ignored artifact)

**Interfaces:**
- Browser test starts an isolated worker using `business_case_worker.py`, asserts no production modules in the reference process, then uses `business_case_assertions.validate_product_result` for actual results.
- The verification report remains separate from the frozen `docs/validation/business-case-results.json`.

- [ ] **Step 1: Add failing mutation/state tests** for incomplete resource, failed fetch, loading-time edit, cancel/accept overwrite, failed export preservation, unsupported RFNBO and mobile keyboard behavior.
- [ ] **Step 2: Run focused browser tests and inspect each failure before implementation.**
- [ ] **Step 3: Implement the smallest fixes and rerun focused tests.**
- [ ] **Step 4: Run independent business suite: `\.venv/Scripts/python.exe tools/validation/business_case_runner.py --output output/teaching-examples-business-validation.json`; require 61/61, 0 differences, production imports 0.**
- [ ] **Step 5: Run Python tests: `\.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py'`; require zero failures.**
- [ ] **Step 6: Run Node tests: `node --test port-identity-mapping.test.mjs port-scope-rates.test.mjs tests/frontend/display-values.test.mjs tests/frontend/workbench-model.test.mjs`; require 41/41.**
- [ ] **Step 7: Build a wheel and inspect it contains `voyage_fuel/static/teaching-examples.json` and `voyage_fuel/templates/examples_guide.html`; install/import in an isolated temp directory and request both resources.**
- [ ] **Step 8: Run `git diff --check` and inspect `git status --short`; report unrelated dirty files without reverting them.**

## Review Checkpoints

- After Task 1: resource contract review; no product code changed.
- After Task 2: browser loading and state invalidation review.
- After Task 3: advanced input and API payload review.
- After Task 4: guide scope and copy review.
- After Task 5: full verification and package review.

## Self-review

- The plan uses one static resource and one optional route; no example-specific calculation subsystem is introduced.
- Both cases map to existing independently frozen inputs, and the modified supply case is already independently frozen.
- Incomplete resource validation occurs before DOM replacement, covering the most dangerous failure mode.
- RFNBO verified E and eu are explicitly covered.
- Test steps have concrete commands and expected outcomes; no placeholder task remains.
