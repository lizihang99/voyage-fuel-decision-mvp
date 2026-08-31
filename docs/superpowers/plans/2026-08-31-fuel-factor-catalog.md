# Fuel Factor Catalog and Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整 36 条内置航行燃料路径目录和统一因子解析器，覆盖固定因子、默认估算、认证覆盖、RFNBO 回退和 Cslip 规则。

**Architecture:** 在 `factors.py` 中以不可变 `FuelDefinition` 保存路径元数据，以 `resolve_factor()` 生成现有计算层使用的 `FuelFactor`。计算模块不再自行判断路径资格；它们只消费解析后的数值因子。

**Tech Stack:** Python 3.12；标准库 `dataclasses`、`decimal`、`unittest`；不引入运行时第三方依赖。

**Spec:** `docs/superpowers/specs/2026-08-31-fuel-factor-catalog-design.md`、`燃料因子库规范.md`、`docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md`

## Global Constraints

- MVP 开放 36 条航行燃料路径；`ELECTRICITY_OPS` 不作为普通燃料路径开放。
- 内核采用十进制高精度数值，计算上下文至少提供 34 位有效十进制数字。
- 中间步骤不得按显示精度舍入；默认 WtT 派生值必须运行时用 Decimal 公式计算。
- A 级路径状态为 `FIXED`；默认参数状态为 `ESTIMATED`；完整认可覆盖状态为 `VERIFIED`。
- RFNBO 未证明或不合格时必须完整回退到同类化石路径。
- LNG、生物 LNG、e-LNG 使用设备级 Cslip；LPG/NH3 默认 Cslip=0 只能标记 `ESTIMATED`。
- 自定义燃料证据对象、上传和报告来源展示不属于本计划。

### Task 1: FuelDefinition model and complete catalog

**Files:**
- Modify: `src/voyage_fuel/models.py`
- Modify: `src/voyage_fuel/factors.py`
- Test: `tests/test_factors.py`

**Interfaces:**
- `FuelDefinition` immutable dataclass with path identity, level, WtT mode, LCV, emissions, Cslip, RWD and fallback metadata.
- `builtin_path_ids() -> tuple[str, ...]` returns exactly the 36 open paths.
- `get_definition(path_id: str) -> FuelDefinition` rejects unknown paths and `ELECTRICITY_OPS`.

- [ ] **Step 1: Write the failing test**

```python
def test_open_catalog_contains_exactly_36_paths_and_excludes_ops():
    ids = builtin_path_ids()
    self.assertEqual(len(ids), 36)
    self.assertNotIn("ELECTRICITY_OPS", ids)
    self.assertEqual(get_definition("LNG_OTTO_MS").equipment_id, "LNG_OTTO_MS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_factors.FactorCatalogTests.test_open_catalog_contains_exactly_36_paths_and_excludes_ops -v`
Expected: FAIL because the complete definition registry and `get_definition()` do not exist.

- [ ] **Step 3: Write minimal implementation**

Register every path from sections 2 and 3 of `燃料因子库规范.md`, excluding only `ELECTRICITY_OPS`, `BIOFUEL_OTHER` and `CUSTOM`. Preserve canonical path IDs and equipment IDs, and store exact Decimal source values without display rounding.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_factors.FactorCatalogTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/voyage_fuel/models.py src/voyage_fuel/factors.py tests/test_factors.py
git commit -m "feat: register complete built-in fuel catalog"
```

### Task 2: Resolver status and RFNBO/biofuel branches

**Files:**
- Modify: `src/voyage_fuel/factors.py`
- Test: `tests/test_factor_resolution.py`

**Interfaces:**
- `resolve_factor(path_id: str, qualification_status: str = "NOT_DEMONSTRATED", e_value: Decimal | None = None, eu_value: Decimal | None = None, cslip_percent: Decimal | None = None, verified_wt_t: Decimal | None = None) -> FuelFactor`
- Raises `ValueError` with a stable reason code in the message for unknown paths, missing RFNBO inputs, missing required Cslip or invalid Cslip use.

- [ ] **Step 1: Write the failing tests**

Test these exact cases: A-level `HFO` returns `FIXED`; default `UCO_FAME` returns `ESTIMATED` and uses `14.9 - 2.834 / 0.037`; `E_DIESEL` with `NOT_DEMONSTRATED` returns the `MDO` factor; `E_DIESEL` with `ASSUMED_ELIGIBLE`, `E=28.2`, `eu=20` returns `rwd=2`; missing verified RFNBO E/eu raises `BLOCKED`; `LPG_PROPANE` with default Cslip=0 is `ESTIMATED`, while verified resolution without Cslip raises `BLOCKED`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_factor_resolution -v`
Expected: FAIL because `resolve_factor()` and the status branches are not implemented.

- [ ] **Step 3: Write minimal implementation**

Implement fixed/default/verified branches, complete RFNBO fallback mapping, biomass fraction propagation, exact WtT formulas, RWD=2 for eligible RFNBO paths, and RC Cslip validation. Keep `get_builtin_factor()` as a compatibility wrapper over the resolver.

- [ ] **Step 4: Run tests to verify it passes**

Run: `python -m unittest tests.test_factor_resolution -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/voyage_fuel/factors.py tests/test_factor_resolution.py
git commit -m "feat: resolve fuel factor qualification branches"
```

### Task 3: Integrate the resolver and protect existing calculations

**Files:**
- Modify: `src/voyage_fuel/json_io.py`
- Modify: `src/voyage_fuel/calculator.py`
- Modify: `tests/test_json_io.py`
- Modify: `tests/test_calculator.py`
- Test: `tests/test_regressions.py`

**Interfaces:**
- JSON `baseline.pathId` and `candidate.pathId` resolve through `resolve_factor()`.
- Existing `FuelComponent` construction from `get_builtin_factor()` remains source-compatible.

- [ ] **Step 1: Write the failing test**

Add JSON cases for `LNG_OTTO_MS`, `E_DIESEL` fallback and an unknown path returning a clear error. Add a regression asserting `UCO_FAME` remains energy-conserving and its default factor status is `ESTIMATED`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_json_io tests.test_calculator tests.test_regressions -v`
Expected: FAIL because JSON currently only supports the four first-slice paths and UCO status is `FIXED`.

- [ ] **Step 3: Write minimal implementation**

Route JSON path resolution through the resolver, preserve current error propagation, update UCO status semantics, and ensure existing voyage calculations still receive valid `FuelFactor` objects.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests -v`
Expected: all Python tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/voyage_fuel/json_io.py src/voyage_fuel/calculator.py tests
git commit -m "feat: integrate complete factor resolver"
```

### Task 4: Documentation and final verification

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md`

- [ ] **Step 1: Run the full verification suite**

```bash
$env:PYTHONPATH='src'; & "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
node --test port-identity-mapping.test.mjs port-scope-rates.test.mjs
```

- [ ] **Step 2: Update status documentation**

Record that all 36 open built-in paths and the resolver are implemented, while custom evidence, constraints, reports and UI remain pending.

- [ ] **Step 3: Run diff and link checks**

Run `git diff --check` and the repository Markdown relative-link check before committing.

- [ ] **Step 4: Commit and push**

```bash
git add README.md docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md
git commit -m "docs: record complete fuel factor catalog baseline"
git push -u origin python-calculation-kernel
```
