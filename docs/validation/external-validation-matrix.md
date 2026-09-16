# 外部计算验证矩阵

更新时间：2026-09-16（本次同步 C 层修复后结论）
验证对象：`voyage_fuel` Python 单航次计算内核
验证原则：先用公开法规常数和独立 Decimal 公式重算，再与项目输出逐字段比较；本轮不修改生产计算逻辑。

## 0. MVP 功能交叉验证总表

本表按 MVP 设计和交付台账的 M01-M17 模块组织，并进一步拆到可独立验收的功能点。每一行只描述一个输入、计算、边界、输出或运行行为；实验编号沿用本文后面的详细记录，同一功能对应多个实验时逐条列出。结果码只使用以下固定形式：

| 结果码 | 含义 |
|---|---|
| `MATCH` | 对照结果一致，无业务差异 |
| `MATCH_WITH_ROUNDING` | 只有显示舍入或浮点尾差，业务结果一致 |
| `EXPLAINED_DIFFERENCE` | 存在差异，且可由外部项目的已知边界、默认值或实现缺口解释 |
| `INTERNAL_ONLY` | 有本项目独立公式或自动化测试，但没有同口径公开项目可交叉 |
| `NOT_TESTED` | 当前既没有可复现实验，也没有对应内部证据 |
| `OUT_OF_SCOPE` | MVP 明确排除，不作为本期缺口 |
| `DIFFERENCE` | 独立参考与被测结果不同，需区分产品缺陷、数值边界与求解器精度限制 |

“覆盖结论”只描述外部交叉覆盖程度：`交叉已验证`、`部分交叉验证`、`仅内部验证`、`未验证`、`MVP排除`。实验列统一使用 `实验或证据=结果码`；`INTERNAL_ONLY` 不是外部通过，`EXPLAINED_DIFFERENCE` 也不是结果一致。

2026-09-07 C 层补充三种结论：`部分独立交叉`（独立数学模型/求解器的有限样例）、`契约补充验收`（状态与编排行为，非外部背书）、`存在差异`。它们不能混称为外部航运平台认证。连续实验编号 `C-LP-01～03` 表示该区间各个实验均已执行且结果相同；逐字段数据见 `docs/validation/c-layer/results.json`。

### 0.1a C 层修复后汇总

同一组 107 个独立实验复跑结果：修复前 `MATCH=41`、`MATCH_WITH_ROUNDING=53`、`DIFFERENCE=13`；修复后 `MATCH=45`、`MATCH_WITH_ROUNDING=61`、`DIFFERENCE=1`。剩余差异仅为 `C-LP-17` 的 `SOLVER_PRECISION_LIMIT`：HiGHS 浮点求解器未分辨约 `1e-20` 的边界差，项目结果与 Fraction 精确参考一致，不属于产品差异。修复后 C 层不再有已确认的产品逻辑差异；逐实验对照见 `docs/validation/c-layer/fixes/comparison.json` 与 `comparison.md`。

### 0.1 架构分层总览

这里按模块的主职责和依赖方向分类。分类用于定位功能责任，不改变 M01-M17 的模块边界、功能点 ID 或验收结论。典型依赖方向是：输入数据与规则 -> 基础计算引擎 -> 高层求解与决策 -> 应用服务与结果契约 -> 报告与交互；质量与运行层对所有层提供验证和启动保障。

| 架构类别 | 主要职责 | 模块 | 典型输入/输出 | 备注 |
|---|---|---|---|---|
| A. 输入数据与规则层 | 提供港口范围、燃料因子、资格规则和自定义证据，形成可计算的规范化输入 | M01、M02、M03 | 输入数据、因子状态、资格和证据 -> 解析后的领域对象 | 不负责航次排放或成本公式 |
| B. 基础计算引擎层 | 执行确定性的能源、EU ETS 和 FuelEU 基础公式 | M04、M05、M06 | 规范化燃料和港口数据 -> 能源、排放、GHGI、余额和指示性金额 | 所有内部计算使用未舍入 Decimal |
| C. 高层求解与决策层 | 在基础结果之上搜索约束边界、临界点、方案排序和条件式结论 | M07、M08、M09、M11 | 方案结果、价格和约束 -> 比例、排名、切换点和建议 | 不重新定义底层排放公式 |
| D. 应用服务与结果契约层 | 编排案例、统一状态/错误/追溯，并提供 JSON/API 边界 | M10、M12 | 领域结果和问题 -> 稳定的案例结果契约 | M10 的追溯与状态横切 A-E 各层 |
| E. 报告与交互层 | 将同一原始结果转换为 CSV、PDF 和单用户网页工作流 | M13、M14、M15 | 案例结果契约 -> 可审计文件和页面交互 | 不在出口层复制计算逻辑 |
| F. 质量与运行层 | 验证规格、回归测试、安装、健康检查和导出启动链路 | M16、M17 | 代码、依赖和运行环境 -> 测试证据与可运行服务 | 对 A-E 提供交付保障 |

### 0.2 按架构类别的 MVP 功能点

以下六张表按上面的架构类别组织；每一行仍是一个可独立验收的功能点。M10 虽然归入应用服务层，但其状态和追溯字段会贯穿输入、计算、算法和输出。

#### A. 输入数据与规则层

| 功能点 ID | 模块 | MVP 功能点 | 实验或证据（结果码） | 差异/备注 | 覆盖结论 |
|---|---|---|---|---|---|
| M01-F01 | M01 港口与范围 | UN/LOCODE 格式和存在性校验 | `test_ports=INTERNAL_ONLY` | 公开项目未提供同一港口主数据校验契约。 | 仅内部验证 |
| M01-F02 | M01 港口与范围 | EU ETS 港口身份和地理范围比例 | `E1=MATCH`；`E2=MATCH`；`E3=MATCH`；`X3=MATCH`；`X4=MATCH`；`N-D(2024/25)=MATCH`；`N-D(2026)=EXPLAINED_DIFFERENCE`；`N-E=MATCH`；`N-F=MATCH` | Navigator unified 2026 入口仍传 CO2-only；底层预聚合三气体后与本项目一致。 | 部分交叉验证 |
| M01-F03 | M01 港口与范围 | FuelEU 港口身份和范围比例 | `E2=MATCH`；`E3=MATCH`；`X5=MATCH`；`N-E=MATCH`；`N-F=MATCH` | 统一案例为一端第三国、一端 EU，范围比例为 0.5。 | 交叉已验证 |
| M01-F04 | M01 港口与范围 | EU ETS 清缴比例（2024/2025/2026+） | `E1=MATCH`；`E2=MATCH`；`E3=MATCH`；`X3=MATCH`；`X4=MATCH`；`N-D(2024/25)=MATCH` | 2024=0.4、2025=0.7、2026+=1.0，按排放发生年度解释。 | 交叉已验证 |
| M01-F05 | M01 港口与范围 | 港口范围分类原因 | `test_ports=INTERNAL_ONLY`；`test_provenance=INTERNAL_ONLY` | 外部项目只核验数值，未提供同一原因字段。 | 仅内部验证 |
| M01-F06 | M01 港口与范围 | 相邻有效 Port of Call 用户确认 | `test_case_json_io=INTERNAL_ONLY`；`test_contracts=INTERNAL_ONLY` | 缺少确认时案例级阻断。 | 仅内部验证 |
| M01-F07 | M01 港口与范围 | 港口来源 ID | `test_provenance=INTERNAL_ONLY` | 公开项目没有同一来源追溯字段。 | 仅内部验证 |
| M01-F08 | M01 港口与范围 | 港口身份解释输出 | `test_provenance=INTERNAL_ONLY` | 由内部结果契约覆盖。 | 仅内部验证 |
| M02-F01 | M02 内置因子 | 36 条开放航行燃料路径 | `test_factors=INTERNAL_ONLY`；`test_factor_catalog_audit=INTERNAL_ONLY` | 未找到公开项目提供同一完整目录。 | 仅内部验证 |
| M02-F02 | M02 内置因子 | 完整 37 条因子库保留 `ELECTRICITY_OPS`，但开放输入排除该路径 | `test_factors=INTERNAL_ONLY` | OPS 属于明确排除项。 | 仅内部验证 |
| M02-F03 | M02 内置因子 | `FIXED` 法规固定因子状态 | `test_factors=INTERNAL_ONLY`；`test_factor_catalog_audit=INTERNAL_ONLY` | 公开项目没有逐字段状态对照。 | 仅内部验证 |
| M02-F04 | M02 内置因子 | `ESTIMATED` 默认参数状态 | `test_factors=INTERNAL_ONLY`；`test_factor_catalog_audit=INTERNAL_ONLY` | 默认值与法规固定值分开记录。 | 仅内部验证 |
| M02-F05 | M02 内置因子 | `VERIFIED` 用户确认数据状态 | `test_factors=INTERNAL_ONLY`；`test_factor_resolution=INTERNAL_ONLY` | 需要用户提供认证数据。 | 仅内部验证 |
| M02-F06 | M02 内置因子 | LCV、WtT、Cf 等基础因子解析 | `test_factor_resolution=INTERNAL_ONLY`；`test_factor_catalog_audit=INTERNAL_ONLY` | 公开项目未提供同一逐字段解析契约。 | 仅内部验证 |
| M02-F07 | M02 内置因子 | LNG/生物 LNG/e-LNG 设备路径和 Cslip | `E3=MATCH`；`A-D=MATCH_WITH_ROUNDING` | LNG Cslip 数量级和方向一致；网页端存在浮点尾差。 | 部分交叉验证 |
| M02-F08 | M02 内置因子 | 非甲烷路径不套用甲烷滑移公式 | `test_factor_resolution=INTERNAL_ONLY`；`test_factor_catalog_audit=INTERNAL_ONLY` | 非甲烷内置路径的 Cslip 保持 NA/不适用语义。 | 仅内部验证 |
| M02-F09 | M02 内置因子 | 未证明 RFNBO 资格时回退同类化石路径 | `E4=MATCH`；`test_factor_resolution=INTERNAL_ONLY` | `E_DIESEL` 无资格证明时回退 `MDO`，不使用 RFNBO 奖励。 | 交叉已验证 |
| M02-F10 | M02 内置因子 | 已假设合格 RFNBO 使用 `rwd=2` | `test_factor_resolution=INTERNAL_ONLY`；`test_factor_catalog_audit=INTERNAL_ONLY` | 没有公开项目形成可复现的正向 RFNBO 对照。 | 仅内部验证 |
| M02-F11 | M02 内置因子 | 生物燃料资格和可纳入生物质比例 | `test_factor_resolution=INTERNAL_ONLY`；`test_factor_catalog_audit=INTERNAL_ONLY` | 未证明资格时不能声明生物质零额比例。 | 仅内部验证 |
| M03-F01 | M03 自定义燃料 | 自定义 LCV 输入 | `test_custom_factors=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY` | 必须提供数值和单位。 | 仅内部验证 |
| M03-F02 | M03 自定义燃料 | 自定义静态 WtT 输入 | `test_custom_factors=INTERNAL_ONLY` | 不使用默认占位因子。 | 仅内部验证 |
| M03-F03 | M03 自定义燃料 | 自定义 `BIO_E` 公式输入 | `test_custom_factors=INTERNAL_ONLY`；`test_case_reports=INTERNAL_ONLY` | 需要公式输入及其证据。 | 仅内部验证 |
| M03-F04 | M03 自定义燃料 | 自定义 `RFNBO_E` 的 `E`/`eu` 输入 | `test_custom_factors=INTERNAL_ONLY`；`test_case_reports=INTERNAL_ONLY` | 资格和两个值均需满足后端契约。 | 仅内部验证 |
| M03-F05 | M03 自定义燃料 | 自定义 CO2、CH4、N2O 因子 | `test_custom_factors=INTERNAL_ONLY` | 逐字段单位和数值均需校验。 | 仅内部验证 |
| M03-F06 | M03 自定义燃料 | 自定义 Cslip 和滑移适用性 | `test_custom_factors=INTERNAL_ONLY` | 非零 Cslip 必须同时提供滑移因子及证据。 | 仅内部验证 |
| M03-F07 | M03 自定义燃料 | 自定义因子单位 | `test_custom_factors=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY` | 单位错误返回结构化问题。 | 仅内部验证 |
| M03-F08 | M03 自定义燃料 | 自定义设备类型 | `test_custom_factors=INTERNAL_ONLY` | 设备用于决定滑移适用性和排放路径。 | 仅内部验证 |
| M03-F09 | M03 自定义燃料 | 逐字段证据对象 | `test_custom_factors=INTERNAL_ONLY`；`test_case_reports=INTERNAL_ONLY` | anuroop 有自定义输入，但没有本项目的证据契约。 | 仅内部验证 |
| M03-F10 | M03 自定义燃料 | 缺少必需字段时阻断自定义路径 | `test_custom_factors=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY` | 仅阻断问题路径，不吞掉其他有效候选。 | 仅内部验证 |
| M03-F11 | M03 自定义燃料 | 状态和资格校验 | `test_custom_factors=INTERNAL_ONLY`；`test_factor_resolution=INTERNAL_ONLY` | 覆盖 `FIXED/ESTIMATED/VERIFIED`、BIO 和 RFNBO 保护。 | 仅内部验证 |

#### B. 基础计算引擎层

| 功能点 ID | 模块 | MVP 功能点 | 实验或证据（结果码） | 差异/备注 | 覆盖结论 |
|---|---|---|---|---|---|
| M04-F01 | M04 能源与成本 | 质量单位转换 | `E1=MATCH`；`E2=MATCH`；`E3=MATCH`；`test_energy=INTERNAL_ONLY` | 质量先转为克参与高精度计算。 | 部分交叉验证 |
| M04-F02 | M04 能源与成本 | LCV 转物理能源 | `E1=MATCH`；`E2=MATCH`；`E3=MATCH`；`X5=MATCH` | 物理能源不在中间步骤舍入。 | 交叉已验证 |
| M04-F03 | M04 能源与成本 | B0 基准能源计算 | `E1=MATCH`；`E2=MATCH`；`E3=MATCH` | 三个独立案例均一致。 | 交叉已验证 |
| M04-F04 | M04 能源与成本 | 允许单独使用时生成 B100 | `test_calculator=INTERNAL_ONLY`；`test_spec_matrix=INTERNAL_ONLY` | 候选不允许纯用时不生成 B100。 | 仅内部验证 |
| M04-F05 | M04 能源与成本 | 指定质量比例混兑 | `E3=MATCH`；`A-B=MATCH_WITH_ROUNDING`；`test_energy=INTERNAL_ONLY` | A-B 浮点尾差不改变业务结论。 | 部分交叉验证 |
| M04-F06 | M04 能源与成本 | 所有方案保持 B0 共同能源 | `E3=MATCH`；`test_energy=INTERNAL_ONLY`；`test_calculator=INTERNAL_ONLY` | 混兑通过候选质量反推保持共同能源。 | 部分交叉验证 |
| M04-F07 | M04 能源与成本 | 方案燃料质量分配 | `test_energy=INTERNAL_ONLY`；`test_calculator=INTERNAL_ONLY` | B0、B100 和混兑质量可审计。 | 仅内部验证 |
| M04-F08 | M04 能源与成本 | 燃料采购成本 | `E1=MATCH`；`E2=MATCH`；`E3=MATCH`；`X4=MATCH`；`X5=MATCH` | 公开项目只能核验部分成本链；案例币种和价格契约以本项目为准。 | 部分交叉验证 |
| M04-F09 | M04 能源与成本 | 固定报告方案集合 | `test_calculator=INTERNAL_ONLY`；`test_constraints=INTERNAL_ONLY`；`test_spec_matrix=INTERNAL_ONLY` | 连续比例只用于求解，不展示全部连续点。 | 仅内部验证 |
| M05-F01 | M05 EU ETS | raw CO2 排放 | `E1=MATCH`；`E2=MATCH`；`E3=MATCH`；`X3=MATCH`；`X4=MATCH` | 独立 Decimal 结果一致。 | 交叉已验证 |
| M05-F02 | M05 EU ETS | raw CH4 排放 | `E1=MATCH`；`E2=MATCH`；`E3=MATCH` | 2024-2025虽输出审计值，但不纳入清缴。 | 交叉已验证 |
| M05-F03 | M05 EU ETS | raw N2O 排放 | `E1=MATCH`；`E2=MATCH`；`E3=MATCH` | 2024-2025虽输出审计值，但不纳入清缴。 | 交叉已验证 |
| M05-F04 | M05 EU ETS | 2024-2025 仅纳入 CO2 | `E1=MATCH`；`E2=MATCH`；`X3=MATCH`；`N-D(2024/25)=MATCH` | CH4/N2O保留为审计字段。 | 交叉已验证 |
| M05-F05 | M05 EU ETS | 2026 起纳入 CO2、CH4、N2O | `E3=MATCH`；`X4=MATCH`；`N-D(2026)=EXPLAINED_DIFFERENCE` | Navigator unified 2026 入口遗漏 CH4/N2O；其底层聚合后数值一致。 | 部分交叉验证 |
| M05-F06 | M05 EU ETS | 地理范围比例应用 | `E1=MATCH`；`E2=MATCH`；`E3=MATCH`；`X3=MATCH`；`X4=MATCH` | 统一航线按 0.5 纳入。 | 交叉已验证 |
| M05-F07 | M05 EU ETS | 2024 清缴比例 40% | `E1=MATCH`；`X3=MATCH`；`N-D(2024/25)=MATCH` | 按排放发生年度字段解释。 | 交叉已验证 |
| M05-F08 | M05 EU ETS | 2025 清缴比例 70% | `E2=MATCH`；`N-D(2024/25)=MATCH` | 按排放发生年度字段解释。 | 交叉已验证 |
| M05-F09 | M05 EU ETS | 2026 起清缴比例 100% | `E3=MATCH`；`X4=MATCH`；`N-D(2026)=EXPLAINED_DIFFERENCE` | Navigator unified 入口的差异仅在气体输入，不在 phase-in。 | 部分交叉验证 |
| M05-F10 | M05 EU ETS | EUA 数量 | `E1=MATCH`；`E2=MATCH`；`E3=MATCH`；`X3=MATCH`；`X4=MATCH` | 地理范围和清缴比例均已纳入。 | 交叉已验证 |
| M05-F11 | M05 EU ETS | EUA 成本 | `E1=MATCH`；`E2=MATCH`；`E3=MATCH`；`X3=MATCH`；`X4=MATCH` | X4以已汇总 CO2e 对照成本层。 | 交叉已验证 |
| M05-F12 | M05 EU ETS | 合格生物质 CO2 零额 | `test_ets=INTERNAL_ONLY`；`test_factors=INTERNAL_ONLY` | 需要生物质资格，不能由燃料名称自动推断。 | 仅内部验证 |
| M05-F13 | M05 EU ETS | 生物质路径 CH4/N2O 保留 | `test_ets=INTERNAL_ONLY`；`test_provenance=INTERNAL_ONLY` | 没有公开项目提供同一资格和逐气体对照。 | 仅内部验证 |
| M05-F14 | M05 EU ETS | 逐气体审计字段 | `test_ets=INTERNAL_ONLY`；`test_provenance=INTERNAL_ONLY` | raw 值、纳入状态和有效因子均可追溯。 | 仅内部验证 |
| M06-F01 | M06 FuelEU | WtT 强度 | `E2=MATCH`；`E3=MATCH`；`X1=MATCH_WITH_ROUNDING`；`X2=MATCH_WITH_ROUNDING`；`X5(GHGI)=MATCH_WITH_ROUNDING`；`P-A/N-A=MATCH_WITH_ROUNDING`；`A-A/A-B/A-C/A-D/M-A=MATCH_WITH_ROUNDING` | 外部实现使用 float 或预置 8 位 GHGI。 | 部分交叉验证 |
| M06-F02 | M06 FuelEU | TtW 强度（含设备级滑移） | `E3=MATCH`；`A-D=MATCH_WITH_ROUNDING` | LNG Cslip 已在燃料级转换后进入 TtW。 | 部分交叉验证 |
| M06-F03 | M06 FuelEU | GHGI = WtT + TtW | `E2=MATCH`；`E3=MATCH`；`X1=MATCH_WITH_ROUNDING`；`X2=MATCH_WITH_ROUNDING`；`X5(GHGI)=MATCH_WITH_ROUNDING` | 浮点尾差不改变排序或达标判断。 | 部分交叉验证 |
| M06-F04 | M06 FuelEU | 2025-2029 目标轨迹 | `X1=MATCH_WITH_ROUNDING`；`P-A/N-A=MATCH_WITH_ROUNDING`；`P-B/N-B(target,CB)=MATCH_WITH_ROUNDING`；`2029=INTERNAL_ONLY` | 2029沿用目标轨迹，但无外部同年度案例。 | 部分交叉验证 |
| M06-F05 | M06 FuelEU | 2030 目标值 | `X2=MATCH_WITH_ROUNDING`；`P-C/N-C=MATCH` | 2030 外部年度目标一致。 | 交叉已验证 |
| M06-F06 | M06 FuelEU | FuelEU 范围能源按同一比例纳入 | `E2=MATCH`；`E3=MATCH`；`X1=MATCH_WITH_ROUNDING`；`X5(target,energy)=MATCH` | 单航次模式保持混兑组成并统一使用 50% 范围比例。 | 交叉已验证 |
| M06-F07 | M06 FuelEU | 合规余额正负号 | `X1=MATCH_WITH_ROUNDING`；`X2=MATCH_WITH_ROUNDING`；`P-B/N-B(target,CB)=MATCH_WITH_ROUNDING` | `target - GHGI`；低于目标为赤字负值。 | 交叉已验证 |
| M06-F08 | M06 FuelEU | 盈余状态和正余额 | `P-C/N-C=MATCH`；`test_fueleu=INTERNAL_ONLY` | 外部项目数值一致，状态文字契约仍以本项目为准。 | 部分交叉验证 |
| M06-F09 | M06 FuelEU | 赤字状态和负余额 | `X1=MATCH_WITH_ROUNDING`；`X2=MATCH_WITH_ROUNDING`；`P-B/N-B(target,CB)=MATCH_WITH_ROUNDING` | P-B罚款记录另按 Annex IV 独立复算。 | 交叉已验证 |
| M06-F10 | M06 FuelEU | 2024 `NOT_YET_APPLICABLE` | `E1=MATCH`；`test_fueleu=INTERNAL_ONLY` | 不生成 FuelEU GHGI/余额指标。 | 交叉已验证 |
| M06-F11 | M06 FuelEU | 0 范围时 `OUT_OF_SCOPE` | `M-C=EXPLAINED_DIFFERENCE`；`test_fueleu=INTERNAL_ONLY` | M-C 数值为 0，但网页文字显示盈余；本项目保留边界状态。 | 部分交叉验证 |
| M06-F12 | M06 FuelEU | 指示性罚款等值 | `E2=MATCH`；`E3=MATCH`；`X1=MATCH_WITH_ROUNDING`；`X2=MATCH_WITH_ROUNDING`；`P-B(penalty)=INTERNAL_ONLY` | P-B 外部记录有另一数值，按 Annex IV 独立复算作为本项目依据。 | 部分交叉验证 |
| M06-F13 | M06 FuelEU | 明确不代表正式年度罚款 | `P-D=OUT_OF_SCOPE`；`M-B=EXPLAINED_DIFFERENCE`；`test_fueleu=INTERNAL_ONLY` | M-B 含连续年度 1.2 倍加成，属于本期范围外能力。 | 部分交叉验证 |

#### C. 高层求解与决策层

修复分支补充（2026-09-16，尚未合入main）：D1/D2/D3已在隔离worktree修复，同一107案例复跑仅剩C-LP-17的第三方求解器精度限制。下表的“修复前”内容保留审计历史；当前结论以本段及 `c-layer/fixes/README.md`、`c-layer/fixes/results.json` 为准。C-LP-17 标记为 `SOLVER_PRECISION_LIMIT`：项目结果与 Fraction 精确参考一致，不属于产品差异。

2026-09-07：已新增 107 个独立求解/精确重算/契约实验，发现达标优化缺陷及数值边界差异。结论与影响见 `c-layer/report.md`，逐实验和31功能表见 `c-layer/experiment-tables.md`。下表保留历史内部测试并追加本轮证据；`DIFFERENCE` 不全部代表生产缺陷，C-LP-17 是第三方浮点求解器精度限制。

| 功能点 ID | 模块 | MVP 功能点 | 实验或证据（结果码） | 差异/备注 | 覆盖结论 |
|---|---|---|---|---|---|
| M07-F01 | M07 约束搜索 | 最大混兑比例约束 | `test_constraints=INTERNAL_ONLY`；`test_spec_matrix=INTERNAL_ONLY`；本轮C验证：C-LP-01～04、C-LP-08～16、C-LP-19～28、C-RND-01、C-RND-03～04、C-RND-07、C-RND-09～18、C-RND-20～21、C-RND-23～24、C-RND-26～30、C-RND-32=MATCH；C-LP-05～07、C-LP-17～18、C-RND-02、C-RND-05～06、C-RND-08、C-RND-19、C-RND-22、C-RND-25、C-RND-31=MATCH_WITH_ROUNDING | 约束边界使用未舍入比例。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M07-F02 | M07 约束搜索 | 候选供应量约束 | `test_constraints=INTERNAL_ONLY`；`test_spec_matrix=INTERNAL_ONLY`；本轮C验证：C-LP-01～04、C-LP-08～16、C-LP-19～28、C-RND-01、C-RND-03～04、C-RND-07、C-RND-09～18、C-RND-20～21、C-RND-23～24、C-RND-26～30、C-RND-32=MATCH；C-LP-05～07、C-LP-17～18、C-RND-02、C-RND-05～06、C-RND-08、C-RND-19、C-RND-22、C-RND-25、C-RND-31=MATCH_WITH_ROUNDING | 供应量与最大混兑共同形成上界。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M07-F03 | M07 约束搜索 | 增量预算约束 | `test_constraints=INTERNAL_ONLY`；`test_spec_matrix=INTERNAL_ONLY`；本轮C验证：C-LP-01～04、C-LP-08～16、C-LP-19～28、C-RND-01、C-RND-03～04、C-RND-07、C-RND-09～18、C-RND-20～21、C-RND-23～24、C-RND-26～30、C-RND-32=MATCH；C-LP-05～07、C-LP-17～18、C-RND-02、C-RND-05～06、C-RND-08、C-RND-19、C-RND-22、C-RND-25、C-RND-31=MATCH_WITH_ROUNDING | 成本为燃料采购加 EUA 成本相对 B0 的增量。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M07-F04 | M07 约束搜索 | 最低达标混兑比例 | `test_constraints=INTERNAL_ONLY`；`test_spec_matrix=INTERNAL_ONLY`；本轮C验证：C-LP-17=DIFFERENCE；C-LP-11～16、C-LP-18、C-LP-21、C-LP-27、C-RND-01～06、C-RND-08～10、C-RND-12、C-RND-14～15、C-RND-17、C-RND-21～23、C-RND-26～27、C-RND-29～30、C-RND-32=MATCH；C-LP-01～10、C-LP-19～20、C-LP-22～26、C-LP-28、C-RND-07、C-RND-11、C-RND-13、C-RND-16、C-RND-18～20、C-RND-24～25、C-RND-28、C-RND-31=MATCH_WITH_ROUNDING | 连续求解得到最低满足目标比例。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。；浮点极近边界以精确参考复核 | 部分独立交叉 |
| M07-F05 | M07 约束搜索 | 无数学解的目标状态 | `test_constraints=INTERNAL_ONLY`；`test_spec_matrix=INTERNAL_ONLY`；本轮C验证：C-LP-11～18、C-LP-21、C-LP-27、C-RND-01～06、C-RND-08～10、C-RND-12、C-RND-14～15、C-RND-17、C-RND-21～23、C-RND-26～27、C-RND-29～30、C-RND-32=MATCH；C-LP-01～10、C-LP-19～20、C-LP-22～26、C-LP-28、C-RND-07、C-RND-11、C-RND-13、C-RND-16、C-RND-18～20、C-RND-24～25、C-RND-28、C-RND-31=MATCH_WITH_ROUNDING | 保留无约束结果和结构化原因。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M07-F06 | M07 约束搜索 | 约束下目标不可达 | `test_constraints=INTERNAL_ONLY`；`test_spec_matrix=INTERNAL_ONLY`；本轮C验证：C-LP-17=DIFFERENCE；C-LP-04～09、C-LP-11～16、C-LP-18、C-LP-21、C-LP-27、C-RND-01～06、C-RND-08～10、C-RND-12、C-RND-14～17、C-RND-21～32=MATCH；C-LP-01～03、C-LP-10、C-LP-19～20、C-LP-22～26、C-LP-28、C-RND-07、C-RND-11、C-RND-13、C-RND-18～20=MATCH_WITH_ROUNDING | `TARGET_UNREACHABLE_UNDER_CONSTRAINTS`，同时显示无约束最低比例。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。；浮点极近边界以精确参考复核 | 部分独立交叉 |
| M07-F07 | M07 约束搜索 | 约束下最大合规改善 | `test_constraints=INTERNAL_ONLY`；`test_case_comparison=INTERNAL_ONLY`；本轮C验证：C-LP-01～04、C-LP-08～16、C-LP-19～28、C-RND-01～05、C-RND-07～18、C-RND-20～21、C-RND-23～24、C-RND-26～30、C-RND-32=MATCH；C-LP-05～07、C-LP-17～18、C-RND-06、C-RND-19、C-RND-22、C-RND-25、C-RND-31=MATCH_WITH_ROUNDING | 目标不可达时仍保留可行最大改善边界。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M07-F08 | M07 约束搜索 | 价格缺失时预算不可评估 | `test_constraints=INTERNAL_ONLY`；`test_case_calculator=INTERNAL_ONLY`；本轮C验证：C-LP-01～28、C-RND-01～32=MATCH | 返回警告，能源和排放计算继续。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M07-F09 | M07 约束搜索 | 约束边界状态和固定报告点 | 历史：C-CASE-01、C-CASE-04=DIFFERENCE；当前：C-CASE-01、C-CASE-04已修复为MATCH，其余实验结论不变 | 报告 xCap、目标比例和有效边界，不展示全部连续比例；修复后新增报告点遵守 `allows_pure_use=False`。 | 部分独立交叉 |
| M08-F01 | M08 经济临界点 | 当前模型燃料加 EUA 成本 | `test_economics=INTERNAL_ONLY`；`test_case_comparison=INTERNAL_ONLY`；本轮C验证：C-CASE-04～05、C-CASE-07～08=MATCH；C-CASE-01～03、C-CASE-06=MATCH_WITH_ROUNDING | 价格完整时才可计算。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M08-F02 | M08 经济临界点 | 候选燃料相对 B0 临界吨价 | `test_economics=INTERNAL_ONLY`；本轮C验证：C-EC-02～03、C-EC-10、C-EC-13、C-EC-15～18、C-EC-23～24、C-EC-27=MATCH；C-EC-01、C-EC-04～09、C-EC-11～12、C-EC-14、C-EC-19～20、C-EC-25～26、C-EC-28=MATCH_WITH_ROUNDING | 线性吨价和固定能源模型下求解。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M08-F03 | M08 经济临界点 | EUA 临界价 | `test_economics=INTERNAL_ONLY`；本轮C验证：C-EC-01～20、C-EC-23、C-EC-25～28=MATCH；C-EC-24=MATCH_WITH_ROUNDING | 退化分母和无有限解返回结构化状态。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M08-F04 | M08 经济临界点 | FuelEU 合规改善参考价值 | `test_economics=INTERNAL_ONLY`；本轮C验证：C-CASE-04～05、C-CASE-07～08=MATCH；C-CASE-01～03、C-CASE-06、C-VALUE-01=MATCH_WITH_ROUNDING | 只用于敏感性和切换点，不进入默认成本。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M08-F05 | M08 经济临界点 | 两方案成本切换点 | `test_economics=INTERNAL_ONLY`；历史C-ENV-07=DIFFERENCE；当前C-ENV-07=MATCH | 使用未舍入成本和临界值；极近交点只在数学上完全相同时合并。 | 部分独立交叉 |
| M08-F06 | M08 经济临界点 | 全局下包络和支配交点剔除 | `test_case_comparison=INTERNAL_ONLY`；`test_economics=INTERNAL_ONLY`；历史C-ENV-07=DIFFERENCE；当前C-ENV-07=MATCH | 只保留有效方案切换；原固定容差造成的极近交点误合并已修复。 | 部分独立交叉 |
| M08-F07 | M08 经济临界点 | 价格缺失时不输出临界价 | `test_economics=INTERNAL_ONLY`；`test_case_comparison=INTERNAL_ONLY`；本轮C验证：C-CASE-01～08、C-EC-21～22=MATCH | 排放和 FuelEU 仍可计算。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 契约补充验收 |
| M08-F08 | M08 经济临界点 | 经济排序 | `test_economics=INTERNAL_ONLY`；`test_case_comparison=INTERNAL_ONLY`；本轮C验证：C-CASE-01～08、C-VALUE-01=MATCH | 仅可比且价格完整的方案进入排序。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M09-F01 | M09 多候选比较 | 所有候选共享同一 B0 | `test_case_calculator=INTERNAL_ONLY`；`test_case_comparison=INTERNAL_ONLY`；本轮C验证：C-CASE-01～08=MATCH | B0 只计算一次并用于所有相对变化。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 契约补充验收 |
| M09-F02 | M09 多候选比较 | 多候选独立计算 | `test_case_calculator=INTERNAL_ONLY`；本轮C验证：C-BUILTIN-01、C-CASE-04～05、C-CASE-07～08=MATCH；C-CASE-01～03、C-CASE-06=MATCH_WITH_ROUNDING | 每个候选保留自己的方案集合和结果。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M09-F03 | M09 多候选比较 | 候选级局部阻断 | `test_case_calculator=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY`；本轮C验证：C-CASE-01～08=MATCH | 一个候选失败不阻断其他候选和 B0。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 契约补充验收 |
| M09-F04 | M09 多候选比较 | B0 参与当前模型成本排名 | `test_case_comparison=INTERNAL_ONLY`；本轮C验证：C-CASE-01～08=MATCH | B0 可成为成本最低方案。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M09-F05 | M09 多候选比较 | 跨候选成本、达标和改善排名 | `test_case_comparison=INTERNAL_ONLY`；历史C-CASE-01、C-CASE-03=DIFFERENCE；当前修复后对应结果与精确参考一致 | 排名使用未舍入原始值；差异由达标方案选择缺陷修复后消除。 | 部分独立交叉 |
| M09-F06 | M09 多候选比较 | 达标方案最低成本选择 | `test_case_comparison=INTERNAL_ONLY`；历史多项实验为DIFFERENCE；当前修复后除C-LP-17求解器精度限制外与精确参考一致 | 仅在目标可达且价格完整时给出；C-LP-17不属于产品差异。 | 部分独立交叉 |
| M09-F07 | M09 多候选比较 | 约束下最大改善候选选择 | `test_case_comparison=INTERNAL_ONLY`；本轮C验证：C-CASE-04～05、C-CASE-07～08=MATCH；C-CASE-01～03、C-CASE-06=MATCH_WITH_ROUNDING | 结果带执行条件待确认状态。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M11-F01 | M11 相对 B0 与建议 | 相对 B0 绝对变化 | `test_case_comparison=INTERNAL_ONLY`；本轮C验证：C-CASE-04～05、C-CASE-07～08、C-STATE-01=MATCH；C-CASE-01～03、C-CASE-06=MATCH_WITH_ROUNDING | 保留未舍入 `delta`。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M11-F02 | M11 相对 B0 与建议 | 相对 B0 百分比变化 | `test_case_comparison=INTERNAL_ONLY`；本轮C验证：C-CASE-04～05、C-CASE-07～08、C-STATE-01=MATCH；C-CASE-01～03、C-CASE-06=MATCH_WITH_ROUNDING | B0 为零时返回原因，不做除零。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M11-F03 | M11 相对 B0 与建议 | 当前模型成本最低方案 | `test_case_comparison=INTERNAL_ONLY`；`test_economics=INTERNAL_ONLY`；本轮C验证：C-CASE-01～08、C-LP-01～28、C-RND-01、C-RND-03～21、C-RND-23～32、C-VALUE-01=MATCH；C-RND-02、C-RND-22=MATCH_WITH_ROUNDING | 只在可比方案中排序。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M11-F04 | M11 相对 B0 与建议 | 达标方案最低成本比例 | `test_case_comparison=INTERNAL_ONLY`；历史多项实验为DIFFERENCE；当前修复后与精确参考一致，C-LP-17为SOLVER_PRECISION_LIMIT | 目标不可达或价格缺失时保留对应原因；浮点极近边界以精确参考复核。 | 部分独立交叉 |
| M11-F05 | M11 相对 B0 与建议 | 最大合规改善比例和候选 | `test_case_comparison=INTERNAL_ONLY`；`test_constraints=INTERNAL_ONLY`；本轮C验证：C-CASE-04～05、C-CASE-07～08、C-LP-01～04、C-LP-08～16、C-LP-19～28、C-RND-01～05、C-RND-07～18、C-RND-20～21、C-RND-23～24、C-RND-26～30、C-RND-32=MATCH；C-CASE-01～03、C-CASE-06、C-LP-05～07、C-LP-17～18、C-RND-06、C-RND-19、C-RND-22、C-RND-25、C-RND-31=MATCH_WITH_ROUNDING | 约束下仍可报告可行最大改善。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 部分独立交叉 |
| M11-F06 | M11 相对 B0 与建议 | 条件式建议 | `test_case_comparison=INTERNAL_ONLY`；历史C-BUILTIN-01、C-CASE-01、C-CASE-04为差异；当前修复后对应结果与精确参考一致 | 建议包含条件、假设和执行状态；C-CASE-04的候选选择差异已修复。 | 部分独立交叉 |
| M11-F07 | M11 相对 B0 与建议 | 不输出“综合最优”结论 | `test_case_comparison=INTERNAL_ONLY`；`test_spec_matrix=INTERNAL_ONLY`；本轮C验证：C-CASE-01～08=MATCH | 只输出成本、达标、改善等条件式结果。 本轮C验证：证据类型与逐字段值见 c-layer/experiment-tables.md。 | 契约补充验收 |

#### D. 应用服务与结果契约层

| 功能点 ID | 模块 | MVP 功能点 | 实验或证据（结果码） | 差异/备注 | 覆盖结论 |
|---|---|---|---|---|---|
| M10-F01 | M10 状态与追溯 | `CALCULABLE` 状态 | `test_provenance=INTERNAL_ONLY`；`test_contracts=INTERNAL_ONLY` | 输入和因子完整时可计算。 | 仅内部验证 |
| M10-F02 | M10 状态与追溯 | `COMPARABLE` 状态 | `test_case_comparison=INTERNAL_ONLY`；`test_provenance=INTERNAL_ONLY` | 价格、范围和结果满足比较条件时可比。 | 仅内部验证 |
| M10-F03 | M10 状态与追溯 | `BLOCKED` 状态 | `test_contracts=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY` | 错误路径返回结构化阻断问题。 | 仅内部验证 |
| M10-F04 | M10 状态与追溯 | `EXECUTION_CONDITIONS_PENDING` | `test_provenance=INTERNAL_ONLY`；`test_case_reports=INTERNAL_ONLY` | 系统不确认认证、兼容性、供应和交付条件。 | 仅内部验证 |
| M10-F05 | M10 状态与追溯 | 错误范围、候选、场景和字段定位 | `test_provenance=INTERNAL_ONLY`；`test_contracts=INTERNAL_ONLY` | 保留 `scope/candidate_id/scenario_id/field`。 | 仅内部验证 |
| M10-F06 | M10 状态与追溯 | 因子版本和来源 ID | `test_provenance=INTERNAL_ONLY`；`test_case_reports=INTERNAL_ONLY` | 结果和报告均可追溯到版本及来源。 | 仅内部验证 |
| M10-F07 | M10 状态与追溯 | 因子逐字段证据摘要 | `test_provenance=INTERNAL_ONLY`；`test_case_reports=INTERNAL_ONLY` | 证据值、单位、状态和来源一起输出。 | 仅内部验证 |
| M12-F01 | M12 案例输入 | 报告年份 2024-2030 | `test_contracts=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY` | 超出范围或非整数时结构化阻断。 | 仅内部验证 |
| M12-F02 | M12 案例输入 | 两个港口输入 | `test_contracts=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY` | 由港口模块解析身份和范围。 | 仅内部验证 |
| M12-F03 | M12 案例输入 | 相邻有效 Port of Call 确认 | `test_contracts=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY` | 未确认时案例级阻断。 | 仅内部验证 |
| M12-F04 | M12 案例输入 | 案例币种 | `test_contracts=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY` | 价格和成本使用同一币种。 | 仅内部验证 |
| M12-F05 | M12 案例输入 | B0 基准燃料和质量 | `test_contracts=INTERNAL_ONLY`；`test_case_calculator=INTERNAL_ONLY` | B0 是所有方案共同能源基准。 | 仅内部验证 |
| M12-F06 | M12 案例输入 | 一个或多个候选燃料 | `test_contracts=INTERNAL_ONLY`；`test_case_calculator=INTERNAL_ONLY` | 候选 ID 必须稳定且不重复。 | 仅内部验证 |
| M12-F07 | M12 案例输入 | 预算、供应量和最大混兑等可选约束 | `test_contracts=INTERNAL_ONLY`；`test_constraints=INTERNAL_ONLY` | 缺失表示不施加该项约束。 | 仅内部验证 |
| M12-F08 | M12 JSON/API | Decimal 使用字符串传输 | `test_json_io=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY` | 避免 JSON 浮点丢失精度。 | 仅内部验证 |
| M12-F09 | M12 JSON/API | 结构化 422 输入错误 | `test_web_api=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY` | 保留代码、范围、字段和消息。 | 仅内部验证 |
| M12-F10 | M12 JSON/API | 候选级问题与有效候选隔离 | `test_web_api=INTERNAL_ONLY`；`test_case_calculator=INTERNAL_ONLY` | 局部阻断不吞掉有效结果。 | 仅内部验证 |
| M12-F11 | M12 JSON/API | 计算、CSV、PDF API 共用案例结果 | `test_web_api=INTERNAL_ONLY`；`test_case_reports=INTERNAL_ONLY` | 所有出口消费同一原始结果对象。 | 仅内部验证 |

#### E. 报告与交互层

| 功能点 ID | 模块 | MVP 功能点 | 实验或证据（结果码） | 差异/备注 | 覆盖结论 |
|---|---|---|---|---|---|
| M13-F01 | M13 CSV | Case 记录 | `test_case_reports=INTERNAL_ONLY` | 包含案例身份、年份和币种。 | 仅内部验证 |
| M13-F02 | M13 CSV | Port 记录 | `test_case_reports=INTERNAL_ONLY` | 包含港口身份、范围和来源。 | 仅内部验证 |
| M13-F03 | M13 CSV | Scenario 记录 | `test_case_reports=INTERNAL_ONLY` | 包含方案、比例、质量、能源和结果。 | 仅内部验证 |
| M13-F04 | M13 CSV | Recommendation 记录 | `test_case_reports=INTERNAL_ONLY` | 包含条件式建议及状态。 | 仅内部验证 |
| M13-F05 | M13 CSV | Switch 记录 | `test_case_reports=INTERNAL_ONLY` | 包含临界点和方案切换信息。 | 仅内部验证 |
| M13-F06 | M13 CSV | Evidence 记录 | `test_case_reports=INTERNAL_ONLY` | 包含因子值、单位、状态和证据。 | 仅内部验证 |
| M13-F07 | M13 CSV | Issue 记录 | `test_case_reports=INTERNAL_ONLY` | 保留候选、场景和字段位置。 | 仅内部验证 |
| M13-F08 | M13 CSV | 单位和案例币种 | `test_case_reports=INTERNAL_ONLY` | 金额字段标明币种，数量字段标明单位。 | 仅内部验证 |
| M13-F09 | M13 CSV | 原始 Decimal 精度 | `test_reports=INTERNAL_ONLY`；`test_case_reports=INTERNAL_ONLY` | 不因显示格式改变可复核值。 | 仅内部验证 |
| M14-F01 | M14 PDF | 完整人工复核报告 | `test_reports=INTERNAL_ONLY`；`test_case_reports=INTERNAL_ONLY` | 包含案例、港口、场景、建议、证据和问题。 | 仅内部验证 |
| M14-F02 | M14 PDF | 页面和 PDF 共享显示精度 | `test_case_reports=INTERNAL_ONLY` | 两个出口使用同一显示配置。 | 仅内部验证 |
| M14-F03 | M14 PDF | 调整显示格式不改变原始结果 | `test_case_reports=INTERNAL_ONLY` | 原始 JSON、排序、状态和临界点保持不变。 | 仅内部验证 |
| M14-F04 | M14 PDF | 自定义公式证据和实际生物质比例 | `test_case_reports=INTERNAL_ONLY` | `BIO_E`、`RFNBO_E` 的证据值和实际比例均保留。 | 仅内部验证 |
| M15-F01 | M15 网页工作流 | 单用户会话 | `test_web_api=INTERNAL_ONLY`；`tests/e2e=INTERNAL_ONLY` | 不登录、不共享用户状态。 | 仅内部验证 |
| M15-F02 | M15 网页工作流 | 无登录和无云端案例存储 | `test_web_api=INTERNAL_ONLY`；`tests/e2e=INTERNAL_ONLY` | 服务器不保存案例文件或会话 cookie。 | 仅内部验证 |
| M15-F03 | M15 网页工作流 | 当前浏览器会话内保存输入 | `tests/e2e=INTERNAL_ONLY` | 页面重绘保持当前案例状态。 | 仅内部验证 |
| M15-F04 | M15 网页工作流 | 刷新后清空案例 | `tests/e2e=INTERNAL_ONLY` | 符合无历史的 MVP 边界。 | 仅内部验证 |
| M15-F05 | M15 网页输入与结果 | 内置燃料日耗量、天数和 LCV 输入 | `X5=MATCH`；`A-A/A-B/A-C/A-D=MATCH_WITH_ROUNDING`；`M-A=MATCH_WITH_ROUNDING` | 外部网页使用 JavaScript `Number` 和预置舍入值。 | 部分交叉验证 |
| M15-F06 | M15 网页输入与结果 | 燃料混合和港口范围输入 | `X5=MATCH`；`M-C=EXPLAINED_DIFFERENCE` | M-C 的 0 范围状态文字与本项目不同。 | 部分交叉验证 |
| M15-F07 | M15 网页输入与结果 | FuelEU/EU ETS 结果呈现 | `A-A/A-B/A-C/A-D=MATCH_WITH_ROUNDING`；`M-A=MATCH_WITH_ROUNDING`；`M-B=EXPLAINED_DIFFERENCE` | M-B 含连续年度加成，当前产品不采用。 | 部分交叉验证 |
| M15-F08 | M15 高级自定义网页 | 最小自定义输入表单 | `tests/e2e=INTERNAL_ONLY`；`test_web_page=INTERNAL_ONLY` | 普通非甲烷路径不要求用户填写不需要的字段。 | 仅内部验证 |
| M15-F09 | M15 高级自定义网页 | 条件显示 Cslip 和气体字段 | `tests/e2e=INTERNAL_ONLY`；`test_web_page=INTERNAL_ONLY` | 只有适用路径才显示相关输入。 | 仅内部验证 |
| M15-F10 | M15 高级自定义网页 | RFNBO 资格保护 | `tests/e2e=INTERNAL_ONLY`；`test_web_page=INTERNAL_ONLY` | 未证明资格时页面锁定 RFNBO 专属输入。 | 仅内部验证 |
| M15-F11 | M15 高级自定义网页 | 稳定候选 ID 和候选重绘状态 | `tests/e2e=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY` | 页面 ID 与后端候选问题定位一致。 | 仅内部验证 |
| M15-F12 | M15 高级自定义网页 | 阻断候选隔离 | `tests/e2e=INTERNAL_ONLY`；`test_case_calculator=INTERNAL_ONLY` | 一个候选阻断不隐藏其他结果。 | 仅内部验证 |

#### F. 质量与运行层

| 功能点 ID | 模块 | MVP 功能点 | 实验或证据（结果码） | 差异/备注 | 覆盖结论 |
|---|---|---|---|---|---|
| M16-F01 | M16 测试矩阵 | 规格测试向量 | `test_spec_matrix=INTERNAL_ONLY` | 覆盖目标、边界、约束和经济场景。 | 仅内部验证 |
| M16-F02 | M16 测试矩阵 | 36 条因子目录审计 | `test_factor_catalog_audit=INTERNAL_ONLY` | 逐路径字段、状态、资格和回退矩阵通过。 | 仅内部验证 |
| M16-F03 | M16 测试矩阵 | JSON/API 回归 | `test_json_io=INTERNAL_ONLY`；`test_case_json_io=INTERNAL_ONLY`；`test_web_api=INTERNAL_ONLY` | 传输精度和结构化错误持续验证。 | 仅内部验证 |
| M16-F04 | M16 测试矩阵 | CSV/PDF 报告回归 | `test_reports=INTERNAL_ONLY`；`test_case_reports=INTERNAL_ONLY` | 字段、精度、证据和渲染持续验证。 | 仅内部验证 |
| M16-F05 | M16 测试矩阵 | 网页端到端回归 | `tests/e2e=INTERNAL_ONLY` | 覆盖桌面、移动、多候选和高级自定义流程。 | 仅内部验证 |
| M17-F01 | M17 安装与运行 | 独立 Python 环境安装 | `test_web_api=INTERNAL_ONLY`；`README=INTERNAL_ONLY` | 临时 Python 3.12 环境安装 `.[dev]` 已实测。 | 仅内部验证 |
| M17-F02 | M17 安装与运行 | CLI 启动链路 | `README=INTERNAL_ONLY`；`test_web_api=INTERNAL_ONLY` | 按 README 命令启动。 | 仅内部验证 |
| M17-F03 | M17 安装与运行 | `/health` 健康检查 | `test_web_api=INTERNAL_ONLY` | 服务可用性返回结构化状态。 | 仅内部验证 |
| M17-F04 | M17 安装与运行 | API 计算链路 | `test_web_api=INTERNAL_ONLY` | 计算和错误响应可从安装环境访问。 | 仅内部验证 |
| M17-F05 | M17 安装与运行 | CSV/PDF 导出链路 | `test_web_api=INTERNAL_ONLY`；`test_case_reports=INTERNAL_ONLY` | 安装后可生成非空、可审计文件。 | 仅内部验证 |
### 0.3 明确排除项

| MVP 设计排除项 | 实验（结果码） | 备注 |
|---|---|---|
| `ELECTRICITY_OPS`、Port Stay、港内零排放义务 | `OUT_OF_SCOPE` | 完整因子库保留路径，当前不进入输入和计算。 |
| 独立物理生命周期 WtW 排放/减排 | `OUT_OF_SCOPE` | 当前只输出 FuelEU 法规口径 WtW/GHGI。 |
| 自动判断 Port of Call、转运港排除、特殊航线和豁免 | `OUT_OF_SCOPE` | 用户确认相邻有效港口，系统不替用户做法律判断。 |
| 船型、吨位、冰级、冰区能源调整 | `OUT_OF_SCOPE` | 不属于当前单航段输入。 |
| 正式年度低 GHGI 能源优先分配 | `OUT_OF_SCOPE` | 当前只做航次级按比例估算；`M-C` 的外部年度/范围语义差异不改变边界。 |
| 真实年度 FuelEU 罚款结算、连续年度加成 | `P-D=OUT_OF_SCOPE`；`M-B=EXPLAINED_DIFFERENCE` | 本项目只输出首年航次级指示性金额。 |
| Banking、Borrowing、Pooling、年度滚动和船队合规 | `P-E=OUT_OF_SCOPE`；补充燃料切换实验=`OUT_OF_SCOPE` | Pool Optimiser 的 fleet LP 能力不属于本项目单航次范围。 |
| 登录、云端存储、案例历史、多用户协作 | `OUT_OF_SCOPE` | 网页只保留当前浏览器会话。 |
| 汇率、体积/能量报价换算 | `OUT_OF_SCOPE` | 用户输入前提供统一案例币种/吨价格。 |

总表结论：0.2 节已将 M01-M17 拆为 150 个可独立验收的功能点，并按六个架构类别重新组织。外部或独立公式已覆盖输入数据层的主要范围比例、基础计算层的能源/EU ETS/FuelEU 算术和网页层的部分输入映射；其余没有同口径公开实现的功能点均明确标为 `INTERNAL_ONLY`。这些模块的内部测试可以证明项目自身契约，但不能写成外部交叉通过。详细输入、公式、外部版本和逐字段数值仍见后续章节。

## 1. 公开来源

| 来源 | 用途 | 版本或访问信息 |
|---|---|---|
| [Regulation (EU) 2023/1805](https://eur-lex.europa.eu/eli/reg/2023/1805/oj) | FuelEU 参考强度、目标、RFNBO reward、Annex II 因子、Annex IV 罚款参数 | 2026-09-03 访问；Article 4/5、Annex II、Annex IV |
| [European Commission: Reducing emissions from the shipping sector](https://climate.ec.europa.eu/areas-action/transport-decarbonisation/reducing-emissions-shipping-sector_en) | EU ETS 地理覆盖、气体范围和 phase-in | 2026-09-03 访问 |
| [FuelEU-ghg-calculator](https://github.com/IliasChatzip/FuelEU-ghg-calculator) | 第二实现的结构和常数对照 | `main` at `02940e6346e8f6c18514b728138ed5c1adc493f9`; 2026-09-03 访问 |

法规关键常数：参考强度 `91.16 gCO2e/MJ`；2025-2029 目标为 `91.16 x 0.98 = 89.3368 gCO2e/MJ`；EU ETS GWP 为 CH4=`28`、N2O=`265`；FuelEU 罚款参数为 VLSFO 等值能量 `41,000 MJ/t`、`EUR 2,400/t`。MDO Annex II 因子为 LCV `0.0427 MJ/g`、WtT `14.4 g/MJ`、CO2 `3.206 g/g`、CH4 `0.00005 g/g`、N2O `0.00018 g/g`。LNG Otto 中速因子为 LCV `0.0491 MJ/g`、WtT `18.5 g/MJ`、CO2 `2.750 g/g`、CH4 `0`、N2O `0.00011 g/g`、Cslip `3.1%`。

## 2. 独立公式

所有重算均使用 Python `Decimal`，质量先转换为克，内部不舍入。

```text
E = sum(m_g x LCV)
WtT = sum(m_g x LCV x WtT) / (E x rwd)
TtW = sum(m_g x (1-p) x (CF_CO2 + 25 x CF_CH4 + 298 x CF_N2O)
         + m_g x p x (CSF_CO2 + 25 x CSF_CH4 + 298 x CSF_N2O))
       / (E x rwd)
GHGI = WtT + TtW
CB_g = (target - GHGI) x E x sFuelEU
penalty = abs(CB_g) / (GHGI x 41,000) x 2,400, when CB_g < 0
```

EU ETS：

```text
CO2_t = sum(m_burn x CF_CO2_effective) / 1,000,000
CH4_t = sum(m_burn x CF_CH4 + m_non_combusted) / 1,000,000
N2O_t = sum(m_burn x CF_N2O) / 1,000,000
preScope = CO2_t                         (2024-2025)
          = CO2_t + 28 x CH4_t + 265 x N2O_t (2026+)
EUAs = preScope x sETS_geo x sETS_surrender
```

欧盟委员会页面的 phase-in 文字为：2025 年交回 2024 年报告排放量的 40%，2026 年交回 2025 年报告排放量的 70%，2027 年起 100%。项目的 `reportYear` 明确定义为排放发生年度，因此实现映射为 `reportYear=2024 -> 0.4`、`2025 -> 0.7`、`2026+ -> 1.0`。若未来改成“清缴年度”输入，必须同时改字段命名和映射，不能静默改变含义。

## 3. 案例结果

测试航线均为 `CNSHG -> NLRTM`：一端第三国、一端 EU，项目港口表解析为 `sETS_geo=0.5`、`sFuelEU=0.5`。每个案例的项目结果通过显式调用 Python 内核获得；独立结果由上面的公式重算。

### E1：2024，100 t HFO，B0

| 字段 | 独立结果 | 项目结果 | 分类 |
|---|---:|---:|---|
| 物理能源 MJ | 4,050,000 | 4,050,000 | MATCH |
| raw CO2 t | 311.400 | 311.400 | MATCH |
| raw CH4 t | 0.00500 | 0.00500 | MATCH |
| raw N2O t | 0.01800 | 0.01800 | MATCH |
| ETS 纳入气体 | CO2 | CO2 | MATCH |
| ETS pre-scope tCO2e | 311.400 | 311.400 | MATCH |
| EUAs（0.5 x 0.4） | 62.28000 | 62.28000 | MATCH |
| EUA 成本（EUR 80） | 4,982.40000 | 4,982.40000 | MATCH |
| FuelEU | 未适用 | `NOT_YET_APPLICABLE` | MATCH |

### E2：2025，100 t MDO，B0

| 字段 | 独立结果 | 项目结果 | 分类 |
|---|---:|---:|---|
| 物理能源 MJ | 4,270,000 | 4,270,000 | MATCH |
| raw CO2 t | 320.600 | 320.600 | MATCH |
| raw CH4 t | 0.00500 | 0.00500 | MATCH |
| raw N2O t | 0.01800 | 0.01800 | MATCH |
| ETS 纳入气体 | CO2 | CO2 | MATCH |
| ETS pre-scope tCO2e | 320.600 | 320.600 | MATCH |
| EUAs（0.5 x 0.7） | 112.21000 | 112.21000 | MATCH |
| FuelEU WtT g/MJ | 14.4 | 14.4 | MATCH |
| FuelEU GHGI g/MJ | 90.767447306791569... | 90.767447306791569... | MATCH |
| 2025 target g/MJ | 89.3368 | 89.3368 | MATCH |
| compliance balance t | -3.054432000000... | -3.054432000000... | MATCH |
| indicative penalty EUR | 1,969.825359392... | 1,969.825359392... | MATCH |

### E3：2026，MDO/LNG Otto 中速，候选质量比例 30%

采用 B0 能源守恒的连续质量混兑。LNG Cslip 采用法规设备路径值 `3.1%`。

| 字段 | 独立结果 | 项目结果 | 分类 |
|---|---:|---:|---|
| 物理能源 MJ | 4,270,000 | 4,270,000 | MATCH |
| raw CO2 t | 291.26577207530255 | 291.26577207530255 | MATCH |
| raw CH4 t | 0.89333146571044375 | 0.89333146571044375 | MATCH |
| raw N2O t | 0.015117924473330345 | 0.015117924473330345 | MATCH |
| ETS pre-scope tCO2e | 320.28530310062752 | 320.28530310062752 | MATCH |
| EUAs（2026，0.5 x 1） | 160.14265155031376 | 160.14265155031376 | MATCH |
| FuelEU WtT g/MJ | 15.753496190049305... | 15.753496190049305... | MATCH |
| FuelEU TtW g/MJ | 74.497470775437024... | 74.497470775437024... | MATCH |
| FuelEU GHGI g/MJ | 90.250966965486329... | 90.250966965486329... | MATCH |
| compliance balance t | -1.951746471313312... | -1.951746471313312... | MATCH |
| indicative penalty EUR | 1,265.898613... | 1,265.898613... | MATCH |

### E4：2025，未证明资格的 `E_DIESEL`，纯候选燃料

项目将请求路径解析为 `MDO`，原因 `RFNBO_QUALIFICATION_NOT_DEMONSTRATED`。独立重算使用 MDO 因子，因此与 E2 的 MDO 结果一致：GHGI、合规余额、罚款和 ETS CO2-only 结果全部 `MATCH`。这验证了未提供 RFNBO 资格证明时不使用 `rwd=2` 奖励的回退规则。

## 4. 公开 GitHub 实现对照

GitHub 项目可用于结构和常数的交叉检查，但不能作为本轮数值真值：其 `app.py` 的罚款代码为：

```python
penalty = (abs(compliance_balance) / (ghg_intensity * VLSFO_ENERGY_CONTENT)) * PENALTY_RATE * 1_000_000
```

本项目 `compliance_balance` 已按吨表示时，额外的 `* 1_000_000` 会把罚款放大约一百万倍。因此该实现若与本项目的罚款输出不一致，分类为 `EXPLAINED_DIFFERENCE`，不能据此改动项目公式。该仓库还允许 AR4/AR5 GWP 切换，GWP 选择不同也会造成可解释差异。其余可比的目标强度和燃料常数与本项目方向一致。

## 5. 结论与后续回归

- 4 个法规独立重算案例均通过：能源、WtT/TtW/GHGI、FuelEU 余额和指示性罚款、EU ETS 年份气体规则、地理/phase-in 比例、LNG Cslip、RFNBO 回退均得到 `MATCH`。这里的“独立”指使用本项目之外的手工 Decimal 公式重算；它不表示每个功能都有外部项目实现可对照。
- 2025 phase-in 已解决：项目按排放发生年度解释 `reportYear`，与公开 phase-in 文字一致。未来若引入清缴年度，必须建立新的字段或转换层。
- 本轮没有发现需要修改生产逻辑的差异。
- 当前证据仍属于法规常数和合成案例验证，不能替代经核证的船舶 MRV、燃料批次证明或年度合规审计。
- 后续回归应保留 E1-E4 的输入和期望值；日常开发运行聚焦测试即可，不需要每次重复全量测试。

## 6. 进一步检索到的网页计算器项目

以下项目于 2026-09-03 通过 GitHub API、公开 README 和可访问部署地址检查。这里的“可用”只表示可以访问源码或网页，不表示其结果已经通过法规审计。

| 项目 | 网页/源码 | 形态 | 能验证什么 | 不能直接当作什么 |
|---|---|---|---|---|
| `rizwanalimondal/fueleu-pool-optimiser` | [源码](https://github.com/rizwanalimondal/fueleu-pool-optimiser)；[在线 Streamlit](https://fueleu-pool-optimiser.streamlit.app) | Python + Streamlit，船队年度优化 | 目标轨迹、CB 符号、Annex IV 罚款链、连续年度加成；有 `docs/VERIFICATION.md` 和 pytest | 单航次质量混兑、逐燃料 MRV/Cslip；它的输入是已汇总的 attained intensity 和 in-scope energy |
| `rizwanalimondal/ghg-compliance-navigator` | [源码](https://github.com/rizwanalimondal/ghg-compliance-navigator) | Python + Streamlit/CLI 内核 | FuelEU 与 EU ETS 的年度目标、40/70/100 phase-in、范围桶和法规引用；有 46 项测试的公开记录 | 当前未确认独立公开部署；FuelEU 输入为已汇总强度，不能验证本项目的燃料级能源守恒 |
| `anuroop0003/fueleu-calculator` | [源码](https://github.com/anuroop0003/fueleu-calculator)；[部署入口](https://fueleu-calculator.vercel.app/app.html) | 静态 HTML/JavaScript，多页 Maritime calculator | 可以观察网页输入组织、燃料选项和 FuelEU 结果呈现；`fueleu/fueleu-calculator.html` 含完整前端计算代码 | 使用 JavaScript `Number` 和默认燃料 GHGI，缺少本项目的 Decimal/因子证据契约；部署入口带导航/登录层，自动化复现路径不稳定 |
| `xxblxs/fueleu-miniapp` | [源码](https://github.com/xxblxs/fueleu-miniapp)；[浏览器预览说明](https://github.com/xxblxs/fueleu-miniapp#运行) | 微信小程序 + 静态预览 | 可借鉴四步输入向导、航段/港停范围输入和结果页信息架构 | 只覆盖 HFO/LFO/MGO 三类简化燃料，没有本项目的 ETS 逐气体、Cslip、RFNBO 和证据状态 |
| `Slack-Hacker/FuelEU_Project` | [源码](https://github.com/Slack-Hacker/FuelEU_Project) | Flask + SQLAlchemy | 可参考持久化、船舶和合规记录的网页骨架 | 没有足够的公开测试和逐字段法规推导，当前不适合作为数值基准 |
| `NikosMav/maritime-optimization-case-study` | [源码/案例](https://github.com/NikosMav/maritime-optimization-case-study) | 静态案例页和 CSV/PNG | 可参考方案比较和成本展示 | 核心实现未公开，结果无法独立复算 |

### 6.1 推荐的使用优先级

1. **数值交叉验证**：优先使用 `FuelEU Pool Optimiser` 和 `ghg-compliance-navigator` 的法规核心代码，并逐项对照目标、CB、罚款和 phase-in。两者都是年度汇总模型，不能替代本项目的燃料级验证。
2. **网页交互参考**：使用 `anuroop0003/fueleu-calculator` 和 `fueleu-miniapp` 观察输入分组、航段/港停配置、结果解释和报告入口。它们的 UI 或默认参数不能直接写回本项目因子库。
3. **工程结构参考**：`Slack-Hacker/FuelEU_Project` 可用于 Flask/数据库组织方式；`NikosMav` 只适合参考案例呈现。

### 6.2 本轮检索结论

目前没有找到一个同时满足以下条件的公开网页工具：燃料级 LCV 与 Cf 输入、LNG 设备级 Cslip、2024-2026 EU ETS 气体切换、FuelEU RFNBO 回退、港口范围比例、质量混兑能源守恒，以及逐字段可审计证据。公开项目通常只覆盖其中一部分。因此本项目仍应以 Regulation (EU) 2023/1805、欧盟委员会 EU ETS 页面和自身独立 Decimal 公式为主基准；网页项目用于发现输入/输出遗漏和解释实现差异。

## 7. 跨项目实验设计与执行结果

### 7.1 统一实验数据

为避免燃料因子差异干扰，跨项目实验先使用公开项目都能接受的“已汇总强度 + 范围能源”输入，再单独用本项目燃料级输入验证上游转换。

| 实验 | 年度 | 统一输入 | 来源项目接口 |
|---|---:|---|---|
| X1 | 2025 | `attained_intensity=90.767447306791569... g/MJ`；`energy=2,135,000 MJ`；连续赤字年数=1 | Pool Optimiser `compliance_balance/penalty_eur`；Navigator `fueleu.evaluate` |
| X2 | 2030 | X1 输入不变，仅年度改为 2030 | 同上 |
| X3 | 2024 | 地理范围后 CO2=`155.7 t`；EUA=`80 EUR/t` | Navigator `eu_ets.evaluate`；本项目 100 t HFO 的 E1 输出 |
| X4 | 2026 | 地理范围后 CO2e=`160.14265155031376 t`；EUA=`80 EUR/t` | Navigator `eu_ets.evaluate`；本项目 E3 的 ETS 输出 |
| X5 | 2025 | 网页输入：1 个航段，10 天，MGO=10 t/天，范围 `non_eu_to_eu`；其他燃料为 0 | `xxblxs/fueleu-miniapp` 的 `calculateFuelEU`；本项目 CNSHG→NLRTM、100 t MDO |

X1/X2 的 `2,135,000 MJ` 来自本项目 100 t MDO 的 4,270,000 MJ 物理能源乘以 FuelEU 50% 范围。X5 完全从网页字段推导同一数值：`10 天 x 10 t/天 x 50% x 1,000,000 g/t x 0.0427 MJ/g = 2,135,000 MJ`。

### 7.2 X1/X2：FuelEU 年度核心交叉核对

| 年度 | 字段 | 本项目 Decimal | Pool Optimiser | GHG Navigator | 分类 |
|---:|---|---:|---:|---:|---|
| 2025 | target g/MJ | 89.3368 | 89.3368 | 89.3368 | MATCH |
| 2025 | CB gCO2e | -3,054,432.000000000... | -3,054,432.000000003 | -3,054,432.000000003 | MATCH_WITH_ROUNDING |
| 2025 | penalty EUR | 1,969.825359392000... | 1,969.825359392002 | 1,969.825359392002 | MATCH_WITH_ROUNDING |
| 2030 | target g/MJ | 85.6904 | 85.6904 | 85.6904 | MATCH |
| 2030 | CB gCO2e | -10,839,496.000000000... | -10,839,496.000000002 | -10,839,496.000000002 | MATCH_WITH_ROUNDING |
| 2030 | penalty EUR | 6,990.469620482023... | 6,990.469620482025 | 6,990.469620482025 | MATCH_WITH_ROUNDING |

差异只来自公开项目使用 Python `float`，没有改变可见精度或排序结论。X1/X2 证明本项目的目标轨迹、CB 正负号和 Annex IV 罚款链与两个独立公开内核一致。

### 7.3 X3/X4：EU ETS phase-in 和成本

| 实验 | 年度 | 地理范围后排放 | phase-in | 本项目 EUA 成本 | Navigator 成本 | 分类 |
|---|---:|---:|---:|---:|---:|---|
| X3 | 2024 | 155.7 t CO2 | 0.4 | 4,982.4 | 4,982.4 | MATCH |
| X4 | 2026 | 160.14265155031376 t CO2e | 1.0 | 12,811.4121240251 | 12,811.4121240251 | MATCH |

X3 的 155.7 t 是本项目 100 t HFO 的 311.4 t raw CO2 乘 50% 地理范围；X4 的范围后 CO2e 来自本项目 LNG 混兑 E3，Navigator 将其作为已汇总的范围排放接收。因此 X4 验证的是 ETS phase-in 与成本层，LNG Cslip 和三气体上游排放仍由本项目 E3 独立公式验证。

### 7.4 X5：网页输入到 FuelEU 结果

| 字段 | 本项目 Decimal | `fueleu-miniapp` JavaScript | 差异分类 |
|---|---:|---:|---|
| target g/MJ | 89.3368 | 89.3368 | MATCH |
| scoped energy MJ | 2,135,000 | 2,135,000 | MATCH |
| actual GHGI g/MJ | 90.767447306791569... | 90.76744731 | MATCH_WITH_ROUNDING |
| CB gCO2e | -3,054,432.000000000... | -3,054,432.006849995 | EXPLAINED_DIFFERENCE |
| penalty EUR | 1,969.825359392000... | 1,969.8253637399823 | EXPLAINED_DIFFERENCE |

网页项目把 MGO 的默认 GHGI 固定为 `90.76744731`，并使用 JavaScript 双精度；相对于本项目完整因子重算，罚款差异约 `0.00000435 EUR`，小于一美分，不构成业务差异。这个案例验证了网页端“天数 × 日耗量 × 范围 × LCV”到 FuelEU 结果的转换逻辑。

### 7.5 执行环境与可重复命令

本轮使用仓库当前 Python 内核、公开仓库 raw 文件和 Node.js 运行 JavaScript 模块；所有公开源码按记录的 URL 和 commit 读取。核心执行结果可用以下方式复现：

```text
Python: 直接调用 voyage_fuel.emissions、voyage_fuel.calculator
Pool:   regulation.target_ghg_intensity / compliance_balance / penalty_eur
Nav:    fueleu.evaluate / eu_ets.evaluate
JS:     FuelEUCalculator.calculateFuelEU
```

实验结论：公开 Python 内核在年度汇总层与本项目一致；网页 JavaScript 在输入映射和结果数量级上吻合，只有由预先舍入和浮点数造成的微小差异；没有出现需要修改本项目生产逻辑的未解释差异。

## 8. 按项目功能上限的独立核验

本节把“项目能做到什么”和“因此能核验本项目哪一段”分开。`MATCH` 只表示在共同输入域内结果一致；`EXPLAINED_DIFFERENCE` 表示差异能由外部项目的已知实现边界、默认值或精度解释；`OUT_OF_SCOPE` 表示该功能不属于当前单航次 MVP，不能据此判定本项目错误。

### 8.1 FuelEU Pool Optimiser

源码快照：[`rizwanalimondal/fueleu-pool-optimiser`](https://github.com/rizwanalimondal/fueleu-pool-optimiser)，commit `fd520aad23e4492d1ab84f005fc249a29b65dfa8`；在线页面：[fueleu-pool-optimiser.streamlit.app](https://fueleu-pool-optimiser.streamlit.app)。

功能上限：输入船队级 `attained_intensity`、`energy_mj`，可选连续赤字年数和燃料切换价格/上限；输出 FuelEU 目标、CB、罚款、船队内部 pooling、燃料切换和总成本。它没有本项目的燃料级 LCV/Cf/Cslip、EU ETS 或航次质量混兑层；banking、borrowing、跨公司池、OPS 和 RFNBO 子目标明确不在 v1。

| 实验 | 输入 | 外部结果 | 对本项目的核验结论 |
|---|---|---|---|
| P-A | 2025，`g=91`，`E=1,000,000 MJ` | target `89.3368`；CB `-1,663,200 g`；penalty `1,069.868667917... EUR` | 与本项目自定义因子同值计算 `MATCH_WITH_ROUNDING` |
| P-B | 2030，`g=91`，`E=1,000,000 MJ` | target `85.6904`；CB `-5,309,600 g`；按公式重算 penalty `3,415.448941302... EUR` | 目标和 CB 可核对；agent 原始摘要中的 `3,409.500?` 为记录笔误，已按 Annex IV 公式复核，不作为证据；项目本身 2030 首期结果可核验 |
| P-C | 2025，`g=85`，`E=1,000,000,000 MJ` | CB `+4,336,800,000 g`；penalty `0` | 正号表示盈余且无罚款，`MATCH` |
| P-D | 2025，`g=95`，`E=1,000,000,000 MJ`，连续年数=3 | CB `-5,663,200,000 g`；罚款 `4,187,423.876765... EUR` | 外部连续赤字公式正确；当前 MVP 航次估算不接受年度连续赤字参数，归类 `OUT_OF_SCOPE` |
| P-E | 赤字船 95/2M MJ + 盈余船 80/2M MJ | pooling 后总成本 `0`，节省约 `6,979.039795 EUR` | 外部船队 pooling 上限验证；当前项目单航次无该接口，`OUT_OF_SCOPE` |

补充燃料切换实验：95 g/MJ、1,000,000 MJ 的船切换到 50 g/MJ 燃料，价差 `0.000001 EUR/MJ` 时外部切换约 `125,848.89 MJ`，成本约 `0.12584889 EUR`；价差 `1 EUR/MJ` 时不切换。该结果核验的是外部 LP 的决策能力，当前项目的单航次比例/成本模型不是同一问题，归类 `OUT_OF_SCOPE`。

### 8.2 GHG Compliance Navigator

源码快照：[`rizwanalimondal/ghg-compliance-navigator`](https://github.com/rizwanalimondal/ghg-compliance-navigator)，commit `f7998ee388b8d0a997507469b374bd7ed2c26036`。

功能上限：FuelEU 年度汇总、四类航段范围 `100%/100%/50%/0%`、EU ETS phase-in `40%/70%/100%`，并列输出 NZF/CII。FuelEU 入口接收汇总 GHGI 和范围能源，不能验证燃料级因子。重要限制：代码中的 `RFNBO_REWARD_MULTIPLIER=2` 只有常量/文档，`fueleu.evaluate` 没有 RFNBO 能量参数，实际不应用奖励；EU ETS 的 `includes_non_co2=True` 也只是标志，`unified.evaluate` 仍把 CO2-only 数值传入 ETS。

| 实验 | 输入 | Navigator 结果 | 本项目对应结论 |
|---|---|---|---|
| N-A | 2025，`g=91`，`E=1,000,000 MJ` | target `89.3368`；CB `-1,663,200 g`；penalty `1,069.868667917... EUR` | `MATCH_WITH_ROUNDING` |
| N-B | 2030，同输入 | target `85.6904`；CB `-5,309,600 g`；penalty按 Annex IV 公式 | `MATCH_WITH_ROUNDING` |
| N-C | 2025，200 t HFO 分为 100 t intra-EEA + 100 t outside；使用本项目 HFO GHGI override `91.74419753` | FuelEU 范围能源 `4,050,000 MJ`；CB `-9,749,960 g`；penalty `6,220.876973... EUR` | 范围能源、CB、罚款与本项目匹配；`MATCH` |
| N-D | 2024/2025/2026，100 t MDO，CNSHG→NLRTM，50% 地理范围 | 2024 EUA `64.12`、成本 `5,129.6`；2025 EUA `112.21`、成本 `8,976.8`；2026 unified EUA `160.3`、成本 `12,824` | 2024/2025 `MATCH`；2026 差异为 Navigator unified 漏计 CH4/N2O，`EXPLAINED_DIFFERENCE` |
| N-E | 2026，直接调用低层 ETS，预先传入范围后 `325.510 tCO2e` | EUA `325.510`，成本 `26,040.8 EUR`（全范围） | 与本项目三气体 CO2e 结果 `MATCH`；说明低层接口可核验，但 unified 集成未完成 |
| N-F | CNSHG→JPTYO（0% outside route），100 t MDO，2024/25/26 | EUA 和成本均 `0` | 与本项目 `sETS_effective=0`、EUA=0 `MATCH` |

### 8.3 anuroop0003/fueleu-calculator

源码快照：[`anuroop0003/fueleu-calculator`](https://github.com/anuroop0003/fueleu-calculator)，commit `d84f453`；部署入口：[fueleu-calculator.vercel.app/app.html](https://fueleu-calculator.vercel.app/app.html)。

功能上限：静态 HTML/JavaScript 页面，支持多行燃料、航段/港停、约 36/37 条燃料选项、LCV/WtT/Cf/Cslip、PoS/PoC、自定义因子、RFNBO reward、风力/CII、报告导出。它没有本项目 Decimal 输出契约，也没有项目级 EU ETS 逐气体表或本项目的 B0 能源守恒混兑约束搜索；网页使用 JavaScript `Number` 和默认/四舍五入值。

| 实验 | 页面输入 | 页面结果 | 当前内核对照 | 分类 |
|---|---|---|---|---|
| A-A | 2025，100 t MDO，non-EEA→EEA（50%） | GHGI `90.76745`；范围能源 `2,135,000 MJ`；CB `-3.05 t`；罚款 `1,969.83 EUR`；WtT `14.40000`、TtW `76.36745` | GHGI `90.767447306...`；CB `-3.054432 t`；罚款 `1,969.825359... EUR` | `MATCH_WITH_ROUNDING` |
| A-B | 2026，HFO 10 t + MDO 4 t，EEA→EEA | GHGI `91.45446`；能量 `575,800 MJ`；CB `-1.22 t`；罚款 `780.46 EUR` | 使用等能源的质量组合得到 GHGI `91.454463355...`；CB `-1.21935056 t`；罚款 `780.460739... EUR` | `MATCH_WITH_ROUNDING` |
| A-C | 2030，100 t MDO，non-EEA→EEA | CB `-10.84 t`；罚款 `6,990.47 EUR` | CB `-10.839496 t`；罚款 `6,990.469620... EUR` | `MATCH_WITH_ROUNDING` |
| A-D | 2026，100 t LNG Otto medium-speed，EEA→EEA | GHGI `89.20293`；WtT `18.5`；TtW `70.70293`；CB `+0.66 t`；无罚款 | GHGI `89.202929124...`；CB `+0.657306 t`；LNG Cslip `3.1%`，ETS raw CH4 `3.1 t` | `MATCH_WITH_ROUNDING` |

这些实验首次用网页实际 DOM 输出核验了 LNG Cslip 和多燃料混合输入；网页结果只能证明数量级和页面公式一致，不能替代本项目逐字段证据和高精度结果。

### 8.4 xxblxs/fueleu-miniapp

源码快照：[`xxblxs/fueleu-miniapp`](https://github.com/xxblxs/fueleu-miniapp)，commit `e5afd2d`。

功能上限：3 种燃料（HFO/LFO/MGO）、多航段和港停、四类航段范围、FuelEU 目标/加权 GHGI/CB/罚款，并支持连续赤字年数的 `1+10%` 加成。它没有 EU ETS、逐气体、Cslip、RFNBO 或证据状态。

| 实验 | 输入与结果 | 与本项目的关系 |
|---|---|---|
| M-A | 2025，MGO 10 t/天×10 天，non-EU→EU；范围能源 `2,135,000 MJ`，CB `-3,054,432.00685 g`，罚款 `1,969.82536374 EUR` | 与本项目匹配到预置 8 位 GHGI 的浮点误差，`MATCH_WITH_ROUNDING` |
| M-B | 2026，EU→EU 航段 HFO 10 t + MGO 2 t，EU 港停 MGO 2 t，连续赤字年数=3；CB `-1,219,350.560198 g`，罚款 `936.5528881 EUR` | 能源/GHGI/CB 与本项目匹配；网页额外应用 1.2 倍年度加成，而当前航次 MVP 只输出基础指示性金额，`EXPLAINED_DIFFERENCE` |
| M-C | 2030，non-EU→non-EU，MGO/HFO 各 5 t/天×10 天 | 网页把 0 能量显示成“合规盈余”；本项目返回 `OUT_OF_SCOPE` | 数值均为 0，但状态语义不同；本项目状态更适合审计，`EXPLAINED_DIFFERENCE` |

### 8.5 其他网页项目

`Slack-Hacker/FuelEU_Project`（Flask + SQLAlchemy）可参考船舶/燃料/合规记录的持久化结构，但未找到足够公开的可复现公式实验，归类为工程结构参考。`NikosMav/maritime-optimization-case-study` 只有静态案例和汇总 CSV/PNG，核心实现未公开，归类为结果呈现参考，不能进行数值交叉验证。

## 9. 综合判定

| 本项目功能 | 可用外部项目 | 独立判定 |
|---|---|---|
| FuelEU 2025/2030 目标、CB、首年罚款 | Pool Optimiser、Navigator、anuroop、miniapp | `MATCH` 或 `MATCH_WITH_ROUNDING` |
| 2024/2025 CO2-only、2026 三气体 ETS | Navigator + 本项目独立逐气体公式 | 2024/2025 `MATCH`；2026 Navigator unified 为外部能力缺口，项目结果由独立公式确认 |
| 100%/50%/0% 航段范围 | Navigator、anuroop、miniapp | `MATCH`，miniapp 的 0% 状态文字需区别于数值 0 |
| LNG 设备级 Cslip | anuroop 网页 + 本项目 | `MATCH_WITH_ROUNDING`；无公开项目能提供同等逐字段审计证据 |
| B0 能源守恒质量混兑 | 本项目独立公式；公开项目只接受汇总量 | 外部项目无法直接核验，保留本项目 E3 证据 |
| RFNBO 资格回退与 `rwd=2` | 本项目 resolver；Navigator 文档/代码不一致，anuroop 页面未形成可复现 RFNBO fixture | 当前仍以本项目规则为主，不能宣称有外部独立确认 |
| 燃料因子状态、逐字段证据 | 无 | 当前只能依靠本项目目录审计和自有测试 |
| 单航次经济比较、约束边界 | Pool 的 fleet LP 只能作概念参考；网页项目未覆盖同一接口 | 公开项目不能 1:1 核验，保留本项目专用测试 |

综合结论：不同公开项目的功能上限互补，足以独立核验本项目的年度 FuelEU 算术、范围比例、EU ETS phase-in、网页输入映射，以及 LNG Cslip 的数量级和结果方向；它们无法共同覆盖本项目的燃料因子证据、B0 能源守恒混兑、RFNBO 回退和单航次约束经济学。外部项目的缺失或实现偏差已被逐项标注，没有发现需要修改本项目生产逻辑的未解释差异。

## 10. 回归固化

E1-E4 的跨项目锚点已经固化为 `tests/fixtures/external-validation-vectors.json`，由 `tests/test_external_validation.py` 通过真实 JSON 输入边界重放。该测试只断言手工记录的关键字段：B0 物理能源、逐气体 MRV、EU ETS 纳入气体和 EUA 成本、FuelEU GHGI/目标/余额/指示性金额，以及未证明 RFNBO 资格时的回退路径和原因。它不重新访问外部网页或 GitHub，因此日常运行不依赖网络，也不会把外部项目的浮点尾差写入生产结果。

日常聚焦验证命令：

```text
$env:PYTHONPATH='src'
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_external_validation tests.test_ets tests.test_fueleu tests.test_energy
```

本节只记录回归入口；每次运行的实际通过数量以终端输出和交付台账为准。
