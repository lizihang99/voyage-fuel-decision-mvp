# P0-P1现行设计基线

## Python MVP运行

项目计算内核和网页服务使用 Python 3.12。下面的命令在仓库根目录执行，创建独立虚拟环境并安装当前包及开发依赖：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[dev]"
.\.venv\Scripts\voyage-fuel-web.exe --host 127.0.0.1 --port 8000
```

另开一个 PowerShell 窗口检查服务：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

预期返回 `status: ok`。浏览器访问 `http://127.0.0.1:8000/` 使用原版单航次计算器；访问 `http://127.0.0.1:8000/?view=workbench` 使用目标驱动的新版决策工作台。当前默认入口仍为原版，`/?view=legacy` 可显式回退。

### API和导出

`tests/fixtures/multi_candidate_case.json` 是可复现的双候选案例。服务启动后，可以直接计算并保存 JSON 结果：

```powershell
$caseBody = Get-Content -Raw .\tests\fixtures\multi_candidate_case.json
$result = Invoke-RestMethod http://127.0.0.1:8000/api/calculate -Method Post -ContentType "application/json" -Body $caseBody
$result | ConvertTo-Json -Depth 20
```

计算成功后服务端返回短期有效的 `result_snapshot_id`。CSV 和 PDF 读取这份服务端结果快照，不重新计算，也不接受客户端提交的结果字段：

```powershell
$exportBody = @{ resultSnapshotId = $result.result_snapshot_id } | ConvertTo-Json
Invoke-WebRequest http://127.0.0.1:8000/api/export/csv -Method Post -ContentType "application/json" -Body $exportBody -OutFile .\voyage-fuel-decision.csv
Invoke-WebRequest http://127.0.0.1:8000/api/export/pdf -Method Post -ContentType "application/json" -Body $exportBody -OutFile .\voyage-fuel-decision.pdf
```

### 聚焦测试

不需要每次运行全量测试。开发时按改动范围运行对应套件：

```powershell
$env:PYTHONPATH = "src"
& ".\.venv\Scripts\python.exe" -m unittest tests.test_case_reports tests.test_reports -v
& ".\.venv\Scripts\python.exe" -m unittest tests.test_web_api tests.test_web_page -v
node --test tests/frontend/display-values.test.mjs tests/frontend/workbench-model.test.mjs
& ".\.venv\Scripts\python.exe" -m pytest tests/e2e/test_workbench_flow.py -q
& ".\.venv\Scripts\python.exe" -m unittest tests.e2e.test_display_precision tests.e2e.test_mvp_flow -v
```

最终验收才运行完整 Python、Node、编译和 JavaScript 语法检查，命令以 `docs/superpowers/plans/2026-09-02-mvp-gap-remediation-plan.md` 的 Task 7 为准。

## MVP边界

结果是 `voyage-level` 的 FuelEU 法规口径比例估算。FuelEU 指示性金额 `not a formal annual penalty`，结果 `not a procurement recommendation`，也不提供 `independent physical lifecycle WtW reduction`。所有可计算方案的执行状态为 `EXECUTION_CONDITIONS_PENDING`，表示认证、兼容性、供应和交付条件仍待确认。

本期只处理 2024-2030 年两个相邻有效 Port of Call 之间的单航段；固定因子库开放 36 条航行燃料路径，`ELECTRICITY_OPS` 不进入本期。2024-2025 年 EU ETS 只纳入 CO2，2026 年起纳入 CO2、CH4 和 N2O。系统不实现正式年度 FuelEU 结算、真实年度罚款、Banking、Borrowing、Pooling、OPS 或登录和云端案例历史。

这个文件夹集中保存本轮确认的产品骨架、两个固定基础，以及支撑它们的数据、法规原文、核对材料和港口可再生成链。

安全使用约定：

- 页面计算成功后会绑定本次成功提交的输入快照；修改航次、燃料、候选或约束输入会使旧结果失效，必须重新计算后才能导出；
- 新版工作台默认显示百分比单位，但发送给 API 的仍是 0 到 1 的质量比例；转换保留十进制输入精度；
- CSV/PDF 直接消费服务端保存的同一份成功计算结果，快照过期或不存在时必须重新计算；显示精度只影响页面和 PDF，不改变原始计算；
- `candidates: []` 是合法的 B0-only 请求，继续返回基础能源、排放、EU ETS 和 FuelEU 结果，不生成新能源建议；
- 案例结果通过 `field_reasons` 说明关键空值，CSV/PDF 同步输出原因码；
- `B100` 只有在候选明确允许纯用时才进入报告点；未经允许的显式比例会返回候选级 `INVALID_BLEND_RATIO`；
- 价格缺失时，预算不能验证，相关非零混兑场景标记为 `CONSTRAINT_UNVERIFIED`，不进入预算相关的条件式建议；
- 案例货币只作为价格口径标签，系统不做换汇；FuelEU 指示性金额固定以 EUR 表示；证据状态是输入声明，系统不自动核验证书真实性。

## 阅读顺序

1. [项目目标与总体架构](./项目目标与总体架构.md)：现行产品骨架；
2. [港口比例功能说明](./港口比例功能说明.md)：已经固定的港口范围和比例规则；
3. [燃料因子库规范](./燃料因子库规范.md)：已经固定的37条燃料路径、因子值、资格分支和默认估算参数；
4. [MVP设计](./docs/superpowers/specs/2026-08-07-voyage-fuel-decision-mvp-design.md)：把产品边界展开为开发功能和验收范围；
5. [MVP计算规格](./docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md)：固定计算公式、单位、边界、状态、输出和测试向量。
6. [外部计算验证矩阵](./docs/validation/external-validation-matrix.md)：记录公开项目功能上限、交叉实验和已解释差异。

发生冲突时：产品能力和表达以《项目目标与总体架构》为准；港口身份和比例以《港口比例功能说明》为准；燃料路径、因子值、资格和证据以《燃料因子库规范》为准；计算单位、公式、状态、输出和测试契约以《MVP计算规格》为准。研究文档和核对记录用于追溯依据，不覆盖上述现行契约。

## 文件结构

```text
P0-P1/
├─ 项目目标与总体架构.md
├─ 港口比例功能说明.md
├─ 燃料因子库规范.md
├─ generate-port-identity-mapping.mjs
├─ port-identity-mapping.mjs
├─ port-identity-mapping.test.mjs
├─ port-scope-rates.mjs
├─ port-scope-rates.test.mjs
├─ docs/
│  ├─ superpowers/specs/2026-08-07-voyage-fuel-decision-mvp-design.md
│  ├─ superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md
│  ├─ research/航程范围与覆盖规则调研.md
│  ├─ 核对记录/燃料因子核对记录.md
│  └─ validation/external-validation-matrix.md
└─ 官方参考资料/
   ├─ 港口基础数据/
   ├─ 航程范围规则/
   └─ 燃料因子来源/
```

其中，港口生成、分类、查询代码和测试属于固定港口成果；它们与旧计算器代码的性质不同。

本文件夹不包含旧碳税计算器实现、历史设计稿、原始截图或临时提取文件，这些内容统一放在相邻的`历史归档资料`文件夹。

## 当前开发状态

项目的模块状态、已验证证据、剩余任务、执行顺序和最终验收条件统一维护在[MVP交付计划与进度](./docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md)。其他计划文件作为历史记录保留，不作为当前完成度依据。

当前分支已经完成并验证案例级多候选计算、结构化结果与追溯、CSV/PDF报告、单用户网页工作流，以及基于现有燃料目录的新能源混兑决策摘要展示；安装后运行和最终验收状态以[MVP交付计划与进度](./docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md)为准。该文件是模块状态和剩余任务的唯一事实来源。

FuelEU结果仍是航次级按比例分配估算，不代表正式年度合规余额或真实年度罚款；系统不输出采购建议或独立物理生命周期WtW减排。新能源决策层复用现有燃料因子、计算、约束和推荐结果，展示新增燃料成本、EU ETS成本节省、净成本变化、FuelEU指标变化以及推荐用量/混兑比例；不新增燃料因子、不实现年度FuelEU结算，也不代表采购执行。逐字段自定义燃料因子已在Python/JSON/API层支持并要求证据，网页高级自定义模式提供最小输入适配：普通非甲烷燃料默认隐藏Cslip等设备字段，CH4/N2O可由用户明确勾选“按0估算”，气体路径可显式选择甲烷滑移是否适用，适用时才填写Cslip和滑移因子；生物燃料可在未证明资格时使用BIO_E估算，EU ETS合格生物质比例仍按0处理；未证明RFNBO资格时页面锁定普通WtT输入，避免直接套用RFNBO奖励。自定义路径和候选身份由页面会话内稳定 ID 管理，最终字段、单位和证据完整性仍由后端校验。

## 浏览器验收

网页端到端测试位于 `tests/e2e/`，使用 Python Playwright 启动隔离的本地 `voyage-fuel-web` 服务，并覆盖桌面 `1440x900`、移动 `390x844`、多候选比较、高级自定义燃料最小输入、RFNBO 资格保护、候选重绘状态保留、阻断候选隔离、显示精度和 CSV/PDF 导出。运行前请安装 Playwright 浏览器；也可以通过 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 指向已有 Chrome：

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m playwright install chromium
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests/e2e -v
```

测试截图和导出证据写入 `tests/e2e/artifacts/`；其中 PDF 导出会在本地生成但已加入忽略清单，因为 ReportLab 的运行元数据会使二进制内容随运行变化。服务状态和计算结果保持浏览器内存与本地临时进程范围内，不创建案例会话文件。

要验证非 editable 安装后的包和 CLI，可在临时虚拟环境中安装 `.[dev]`，并设置 `VOYAGE_FUEL_PYTHON` 指向该环境的 Python；设置 `VOYAGE_FUEL_USE_INSTALLED_PACKAGE=1` 后运行上述 E2E 命令，测试服务不会回退到仓库源码路径。
