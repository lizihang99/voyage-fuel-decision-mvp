# Fuel Factor Catalog and Resolver Design

## Goal

为 Python 航次计算内核建立完整的 36 条内置航行燃料路径目录和统一因子解析器，保证固定法规因子、默认估算、认证覆盖、RFNBO 回退和 Cslip 规则由单一模块处理。

## Scope

本阶段开放 36 条航行燃料路径。`ELECTRICITY_OPS` 保留在参考资料中，但不作为普通燃料路径开放。覆盖 A/B 级路径、FuelEU/MRV 计算字段、设备级 Cslip、RWD、RFNBO 回退和生物燃料资格状态。

本阶段不实现自定义燃料逐字段证据对象、文件上传、来源证据展示和报告层字段映射；这些内容在内置目录稳定后单独实现。

## Architecture

`FuelDefinition` 保存路径身份、设备、因子等级、WtT 模式、固定值、默认估算值、资格和回退元数据。`resolve_factor()` 根据路径和资格输入生成现有计算层使用的不可变 `FuelFactor`。能源、EU ETS、FuelEU 和航次编排模块只消费解析后的 `FuelFactor`，不自行判断 RFNBO 或 Cslip 资格。

兼容接口 `get_builtin_factor(path_id)` 继续保留。无资格参数时，它返回该路径的默认可计算情景；对 RFNBO 返回同类化石回退， 对需要运行时数据的路径返回估算状态或明确阻断。

## Resolution Rules

- A 级路径使用法规固定值，状态为 `FIXED`。
- B 级非 RFNBO 路径无认证数据时使用规范第四节默认参数，状态为 `ESTIMATED`；有完整认可覆盖时状态为 `VERIFIED`。
- 生物燃料资格为 `NOT_DEMONSTRATED` 时按化石 CO2 处理；`ASSUMED_ELIGIBLE` 生成估算场景；`VERIFIED_ELIGIBLE` 要求认证输入。
- RFNBO 的 `NOT_DEMONSTRATED`/`INELIGIBLE` 必须完整回退到同类化石路径；`ASSUMED_ELIGIBLE` 使用 E/eu 估算并设置 RWD=2；`VERIFIED_ELIGIBLE` 要求认证 E、eu 和资格输入。
- LNG、生物 LNG、e-LNG 使用设备级 Cslip。LPG/NH3 的默认 Cslip=0 只能是 `ESTIMATED`；正式核验缺少认可 Cslip 时阻断。
- 非甲烷路径收到非零 Cslip 且无明确支持规则时返回 `INVALID_CSLIP`。
- `UCO_FAME` 的默认 E=14.9 通过 `WtT=E-CfCO2/LCV` 高精度推导，默认状态为 `ESTIMATED`，不能标记为 `FIXED`。

## Acceptance

- 36 条开放路径均可枚举；`ELECTRICITY_OPS` 不可作为航行燃料查询。
- 关键 A/B 路径数值与燃料因子规范一致。
- RFNBO 回退、估算、核验和缺失输入阻断均有测试。
- Cslip 设备差异和 RC Cslip 规则均有测试。
- 现有能源、EU ETS、FuelEU、航次和 JSON 测试保持通过。
