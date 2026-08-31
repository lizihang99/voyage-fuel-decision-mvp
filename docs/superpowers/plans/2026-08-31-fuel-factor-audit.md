# Fuel Factor Catalog Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 逐字段核对 36 条 MVP 内置航行燃料路径与《燃料因子库规范》，修复数值、默认估算状态、WtT 模式、RFNBO 回退和 Cslip 语义偏差，并用可重复测试锁定结果。

**Architecture:** 以规范中的 36 条开放路径作为期望清单，测试通过 `get_definition()` 和 `resolve_factor()` 验证目录元数据与各资格分支。默认估算、有效认证覆盖和 RFNBO 情景分别测试，不把默认快照误当成认证结果。

**Tech Stack:** Python 3.12；标准库 `decimal`、`unittest`；不引入运行时第三方依赖。

**Spec:** `燃料因子库规范.md`、`docs/superpowers/specs/2026-08-31-fuel-factor-catalog-design.md`、`docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md`

## Global Constraints

- MVP 开放 36 条航行燃料路径；`ELECTRICITY_OPS` 不进入普通航行燃料目录。
- 所有内部数值使用 Decimal，不按显示精度舍入。
- A 级路径为 `FIXED`；B 级默认参数为 `ESTIMATED`；有效认证覆盖为 `VERIFIED`。
- B 级非 RFNBO 默认估算直接使用规范第四节 WtT；只有提供有效 E 时才按 `WtT=E-CfCO2/LCV` 推导。
- RFNBO 未证明或不合格时完整回退到同类化石路径；假设合格只生成 `ESTIMATED` 情景；核验必须有认证输入。
- LNG、生物 LNG、e-LNG 使用设备级 Cslip；LPG/NH3 默认零值只用于估算，核验缺失认可值时阻断。

### Task 1: Build executable catalog expectations

**Files:**
- Create: `tests/test_factor_catalog_audit.py`
- Modify: `src/voyage_fuel/models.py` only if the audit needs an explicit metadata field

- [x] **Step 1: Write the failing tests**

  Assert all 36 canonical paths exist, and for every path assert LCV, WtT mode, emissions, Cslip applicability and RWD match the specification. Add a focused test that default `BIOETHANOL`, `BIODIESEL`, `HVO`, `BIOLNG_*`, and `BIOMETHANOL` use the published WtT snapshot and are `ESTIMATED`.

- [x] **Step 2: Run the audit tests and confirm expected failures**

  Run:

  ```powershell
  $env:PYTHONPATH='src'; & "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_factor_catalog_audit -v
  ```

  Expected: failures identify any metadata or default WtT mismatch, rather than a test collection error.

- [x] **Step 3: Implement the smallest catalog corrections**

  Correct only values or metadata proven inconsistent with the specification. Keep aliases and the 36-path boundary stable.

- [x] **Step 4: Run the focused audit tests**

  Expected: all audit tests pass.

### Task 2: Lock qualification branch semantics

**Files:**
- Modify: `tests/test_factor_resolution.py`
- Modify: `src/voyage_fuel/factors.py` only for failing branch behavior

- [x] **Step 1: Write failing branch tests**

  Cover: default B-level WtT snapshots; explicit biofuel E formula; `UCO_FAME` formula; RFNBO fallback, assumed eligibility and verified eligibility; `E<=28.2`; LPG/NH3 Cslip; non-methane non-zero Cslip rejection; and verified status requirements.

- [x] **Step 2: Run focused tests and confirm failures**

  Run `tests.test_factor_resolution` and record each failure reason.

- [x] **Step 3: Implement minimal resolver fixes**

  Separate default snapshot WtT from explicit E-derived WtT. Preserve factor status and fallback identity in the returned factor.

- [x] **Step 4: Run focused and existing tests**

  Expected: resolver tests and existing calculation tests pass.

### Task 3: Final verification and audit record

**Files:**
- Modify: `docs/superpowers/specs/2026-08-31-fuel-factor-catalog-design.md`
- Modify: `README.md`

- [x] **Step 1: Run full Python and Node verification**

  ```powershell
  $env:PYTHONPATH='src'; & "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
  node --test port-identity-mapping.test.mjs port-scope-rates.test.mjs
  git diff --check
  ```

- [x] **Step 2: Record audit coverage and remaining boundaries**

  Document that 36 paths are machine-checked, while custom evidence objects, constraints, reports and UI remain outside this audit.

- [ ] **Step 3: Commit the verified audit**

  ```powershell
  git add tests src docs README.md
  git commit -m "fix: audit fuel factor catalog semantics"
  git push origin python-calculation-kernel
  ```
