# P0-P1现行设计基线

这个文件夹集中保存本轮确认的产品骨架、两个固定基础，以及支撑它们的数据、法规原文、核对材料和港口可再生成链。

## 阅读顺序

1. [项目目标与总体架构](./项目目标与总体架构.md)：现行产品骨架；
2. [港口比例功能说明](./港口比例功能说明.md)：已经固定的港口范围和比例规则；
3. [燃料因子库规范](./燃料因子库规范.md)：已经固定的37条燃料路径、因子值、资格分支和默认估算参数；
4. [MVP设计](./docs/superpowers/specs/2026-08-07-voyage-fuel-decision-mvp-design.md)：把产品边界展开为开发功能和验收范围；
5. [MVP计算规格](./docs/superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md)：固定计算公式、单位、边界、状态、输出和测试向量。

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
│  └─ 核对记录/燃料因子核对记录.md
└─ 官方参考资料/
   ├─ 港口基础数据/
   ├─ 航程范围规则/
   └─ 燃料因子来源/
```

其中，港口生成、分类、查询代码和测试属于固定港口成果；它们与旧计算器代码的性质不同。

本文件夹不包含旧碳税计算器实现、历史设计稿、原始截图或临时提取文件，这些内容统一放在相邻的`历史归档资料`文件夹。

## 当前开发状态

项目的模块状态、已验证证据、剩余任务、执行顺序和最终验收条件统一维护在[MVP交付计划与进度](./docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md)。其他计划文件作为历史记录保留，不作为当前完成度依据。

当前分支已经完成并验证案例级多候选计算、结构化结果与追溯、CSV/PDF报告、单用户网页工作流，以及安装后服务和浏览器验收。唯一事实来源和逐模块证据见[MVP交付计划与进度](./docs/superpowers/plans/2026-09-01-mvp-delivery-plan.md)。

FuelEU结果仍是航次级按比例分配估算，不代表正式年度合规余额或真实年度罚款；系统不输出采购建议或独立物理生命周期WtW减排。逐字段自定义燃料因子已在Python/JSON/API层支持并要求证据，网页当前提供内置路径和候选约束输入，网页高级自定义因子表单仍属于后续界面增强。

## 浏览器验收

网页端到端测试位于 `tests/e2e/`，使用 Python Playwright 启动隔离的本地 `voyage-fuel-web` 服务，并覆盖桌面 `1440x900`、移动 `390x844`、多候选比较、RFNBO 回退证据、阻断候选隔离、显示精度和 CSV/PDF 导出。运行前请安装 Playwright 浏览器；也可以通过 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 指向已有 Chrome：

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m playwright install chromium
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests/e2e -v
```

测试截图和导出证据写入 `tests/e2e/artifacts/`；其中 PDF 导出会在本地生成但已加入忽略清单，因为 ReportLab 的运行元数据会使二进制内容随运行变化。服务状态和计算结果保持浏览器内存与本地临时进程范围内，不创建案例会话文件。

要验证非 editable 安装后的包和 CLI，可在临时虚拟环境中安装 `.[dev]`，并设置 `VOYAGE_FUEL_PYTHON` 指向该环境的 Python；设置 `VOYAGE_FUEL_USE_INSTALLED_PACKAGE=1` 后运行上述 E2E 命令，测试服务不会回退到仓库源码路径。
