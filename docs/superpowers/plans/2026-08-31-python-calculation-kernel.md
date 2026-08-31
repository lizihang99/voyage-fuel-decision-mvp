# Python Calculation Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个可复核的 Python 航次燃料计算内核第一纵向切片，覆盖 B0、B100、质量混兑、能源守恒、成本、港口范围、EU ETS 和 FuelEU 航次级结果。

**Architecture:** 使用纯 Python 领域包，按模型、燃料因子、港口范围、能源、排放和航次编排拆分。计算函数只接收结构化输入并返回结构化结果；界面和导出不在本阶段实现。既有港口 CSV 作为权威输入，Python 侧读取同一文件并用测试锁定规则。

**Tech Stack:** Python 3.12；标准库 `dataclasses`、`decimal`、`csv`、`unittest`；不引入运行时第三方依赖。

**Spec:** `docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md`

## Global Constraints

- 内核采用十进制高精度数值，计算上下文至少提供 34 位有效十进制数字。
- 中间步骤不得按显示精度舍入；方案判断使用未舍入值。
- 所有候选方案保持与 B0 相同的物理能源需求。
- 2024-2025 年 EU ETS 清缴只纳入 CO2；2026 年起纳入 CO2、CH4、N2O。
- FuelEU 结果是航次级比例估算，不得表述为正式年度合规余额或真实罚款。
- 执行状态统一为 `EXECUTION_CONDITIONS_PENDING`。
- 第一阶段仅实现已选测试路径 `MDO`、`HFO`、`UCO_FAME`，因子目录接口保留后续扩展位置。
- 航次编排在候选燃料显式允许单独使用时加入 B100；JSON 边界通过 `voyage_fuel.json_io.calculate_voyage_json` 提供精度不丢失的字符串化输出。

---

### Task 1: Python 包骨架与模型契约

**Files:**
- Create: `src/voyage_fuel/__init__.py`
- Create: `src/voyage_fuel/models.py`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces immutable dataclasses `FuelFactor`, `FuelComponent`, `VoyageInput`, `ScenarioResult`。
- Decimal 字段由调用方传入 `Decimal`；解析辅助函数负责把十进制字符串转为 `Decimal`。

- [x] **Step 1: Write the failing test**

```python
from decimal import Decimal
import unittest

from voyage_fuel.models import FuelComponent, FuelFactor


class ModelTests(unittest.TestCase):
    def test_factor_keeps_decimal_values_and_component_price(self):
        factor = FuelFactor(
            path_id="MDO",
            lcv_mj_per_g=Decimal("0.0427"),
            wt_t_g_per_mj=Decimal("14.4"),
            cf_co2_g_per_g=Decimal("3.206"),
            cf_ch4_g_per_g=Decimal("0.00005"),
            cf_n2o_g_per_g=Decimal("0.00018"),
            rwd=Decimal("1"),
            cslip_percent=None,
            methane_slip_applicable=False,
            factor_status="FIXED",
        )
        component = FuelComponent(factor=factor, price_per_tonne=Decimal("600"))
        self.assertEqual(component.factor.lcv_mj_per_g, Decimal("0.0427"))
        self.assertEqual(component.price_per_tonne, Decimal("600"))


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_models -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'voyage_fuel'`.

- [x] **Step 3: Write minimal implementation**

Create the package and frozen dataclasses with the exact fields used by the test and later tasks. Validate non-negative prices and positive LCV in `__post_init__`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_models -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/voyage_fuel tests
git commit -m "feat: add Python calculation models"
```

### Task 2: 因子目录和能源/成本计算

**Files:**
- Create: `src/voyage_fuel/factors.py`
- Create: `src/voyage_fuel/energy.py`
- Create: `tests/test_energy.py`

**Interfaces:**
- `get_builtin_factor(path_id: str) -> FuelFactor`
- `baseline_energy_mj(mass_tonnes: Decimal, factor: FuelFactor) -> Decimal`
- `blend_masses_tonnes(baseline_energy_mj: Decimal, baseline: FuelComponent, candidate: FuelComponent, ratio: Decimal) -> tuple[Decimal, Decimal]`
- `fuel_cost(mass_tonnes: Decimal, component: FuelComponent) -> Decimal | None`
- `model_cost(baseline_cost: Decimal | None, candidate_cost: Decimal | None, eua_cost: Decimal | None) -> Decimal | None`

- [x] **Step 1: Write the failing test**

```python
from decimal import Decimal
import unittest

from voyage_fuel.energy import baseline_energy_mj, blend_masses_tonnes
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.models import FuelComponent


class EnergyTests(unittest.TestCase):
    def test_twenty_percent_blend_preserves_baseline_energy(self):
        baseline = FuelComponent(get_builtin_factor("MDO"), Decimal("600"))
        candidate = FuelComponent(
            get_builtin_factor("UCO_FAME"), Decimal("1000"),
            eligible_biomass_fraction=Decimal("1"),
        )
        energy = baseline_energy_mj(Decimal("100"), baseline.factor)
        baseline_t, candidate_t = blend_masses_tonnes(energy, baseline, candidate, Decimal("0.20"))
        self.assertEqual(baseline_t, Decimal("82.1944177093358999041880991"))
        self.assertEqual(candidate_t, Decimal("20.5486044273339749760470248"))
        self.assertEqual(
            (baseline_t * Decimal("1000000") * baseline.factor.lcv_mj_per_g)
            + (candidate_t * Decimal("1000000") * candidate.factor.lcv_mj_per_g),
            energy,
        )


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_energy -v`
Expected: FAIL because `voyage_fuel.energy` and `voyage_fuel.factors` do not exist.

- [x] **Step 3: Write minimal implementation**

Register `MDO`, `HFO`, `MGO` alias, and `UCO_FAME` using the authoritative factor values. Compute total mass from `baseline_energy / weighted_lcv`, then split by mass ratio without rounding. Reject ratios outside `[0, 1]` and non-positive weighted LCV.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_energy -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/voyage_fuel/factors.py src/voyage_fuel/energy.py tests/test_energy.py
git commit -m "feat: add factor registry and energy blending"
```

### Task 3: 港口范围与 EU ETS

**Files:**
- Create: `src/voyage_fuel/ports.py`
- Create: `src/voyage_fuel/emissions.py`
- Create: `tests/test_ports.py`
- Create: `tests/test_ets.py`

**Interfaces:**
- `load_port_table(path: str | None = None) -> dict[str, PortIdentity]`
- `calculate_scope_rates(year: int, departure_port: str, arrival_port: str, table: Mapping[str, PortIdentity] | None = None) -> ScopeRates`
- `calculate_eu_ets(year: int, components: Sequence[FuelAmount], scope: ScopeRates, eua_price_per_tco2e: Decimal | None) -> EtsResult`

- [x] **Step 1: Write the failing tests**

Add tests for an ordinary EU/third-country pair returning EU ETS geo rate `0.5`, surrender rate `0.7` in 2025, and FuelEU scope `0.5`; add tests asserting a 2024 LNG/HFO result excludes CH4/N2O from EUAs while 2026 includes all three gases.

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_ports tests.test_ets -v`
Expected: FAIL because the Python port and emissions modules do not exist.

- [x] **Step 3: Write minimal implementation**

Read the existing formal CSV with `csv.DictReader`, validate the five-character UN/LOCODE and stored statuses, preserve OMR FuelEU half-energy behavior, and apply the calculation-spec GWP and surrender rates. Keep raw gas tonnes in the result and expose the included gas names.

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_ports tests.test_ets -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/voyage_fuel/ports.py src/voyage_fuel/emissions.py tests/test_ports.py tests/test_ets.py
git commit -m "feat: add Python port scope and EU ETS"
```

### Task 4: FuelEU 航次级结果与统一编排

**Files:**
- Modify: `src/voyage_fuel/emissions.py`
- Create: `src/voyage_fuel/calculator.py`
- Create: `tests/test_fueleu.py`
- Create: `tests/test_calculator.py`

**Interfaces:**
- `calculate_fueleu(year: int, amounts: Sequence[FuelAmount], fuel_eu_scope_rate: Decimal | None) -> FuelEuResult`
- `calculate_voyage(request: VoyageInput) -> VoyageResult`

- [x] **Step 1: Write the failing tests**

Add tests for 2025 `sFuelEU=0.5` returning the same GHGI as 100% scope with half the balance, 2024 returning null FuelEU target/GHGI/CB/penalty, and the vector-D penalty formula returning `255916.80 EUR` for the specified deficit.

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_fueleu tests.test_calculator -v`
Expected: FAIL because FuelEU and voyage orchestration are not implemented.

- [x] **Step 3: Write minimal implementation**

Aggregate `D_RWD`, `N_WtT`, and `N_TtW` with FuelEU GWP values, calculate the 2025-2029 target `89.3368`, classify positive/zero/negative balance, and calculate the indicative penalty only for deficits. Build B0, specified ratios, and optional B100 scenarios using the energy helpers; attach `EXECUTION_CONDITIONS_PENDING` to every result.

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -v`
Expected: all Python tests PASS and the existing Node port tests still PASS.

- [x] **Step 5: Commit**

```bash
git add src/voyage_fuel/emissions.py src/voyage_fuel/calculator.py tests/test_fueleu.py tests/test_calculator.py
git commit -m "feat: calculate voyage FuelEU results"
```

### Task 5: 基线验收与远端同步

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md`

- [x] **Step 1: Run Python and Node test suites**

```bash
python -m unittest discover -s tests -v
node --test port-identity-mapping.test.mjs port-scope-rates.test.mjs
```

Expected: all tests pass with zero failures.

- [x] **Step 2: Run precision and link checks**

Re-run the documented Markdown link check and assert the energy-conservation vector using an unrounded `Decimal` result.

- [x] **Step 3: Update project status**

Document that the Python kernel first slice is implemented, while the remaining factor paths, constraints, UI, and exports are pending.

- [x] **Step 4: Commit and push**

```bash
git add README.md docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md
git commit -m "docs: record Python kernel baseline"
git push -u origin python-calculation-kernel
```

## 后续增量

- [x] 预算、供应量、最大混兑比例约束与连续比例求解；
- [x] 固定报告方案集合；
- [x] 候选燃料临界吨价与 EUA 临界价格；
- [x] FuelEU 合规改善参考价值、参考成本和真实下包络切换点；
- [ ] 自定义燃料逐字段证据对象；
- [ ] CSV/PDF 报告导出；
- [ ] 前端界面。

上述经济比较仍基于航次级 FuelEU 估算。它不代表正式年度合规结算、真实年度罚款或独立物理生命周期 WtW 减排。
