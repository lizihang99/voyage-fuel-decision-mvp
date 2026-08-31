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

Python 计算内核第一阶段已实现并通过测试，覆盖 B0、可选 B100、质量混兑、能源守恒、燃料成本、港口范围、EU ETS 和 FuelEU 航次级估算。`voyage_fuel.json_io.calculate_voyage_json` 提供无 Web 框架的 JSON 输入/输出验证入口；Decimal 结果以字符串输出，便于无损复核。当前只注册首批测试路径（MDO、MGO、HFO、UCO_FAME），不代表完整 36 条燃料路径已经完成。

尚未实现的 MVP 模块包括完整燃料因子目录、预算/供应量约束搜索、固定报告方案集合、报告导出和前端界面。FuelEU 结果仍是航次比例估算，不代表正式年度合规余额、真实罚款或独立物理生命周期 WtW 减排。
