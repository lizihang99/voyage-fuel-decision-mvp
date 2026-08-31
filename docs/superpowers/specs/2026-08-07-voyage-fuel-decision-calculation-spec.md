# 航次燃料决策工具 MVP 计算规格

> 状态：待用户审阅
>
> 日期：2026-08-07
>
> 本文把已确认的 MVP 产品边界落实为可实现、可复算、可测试的数学定义。产品范围见[航次燃料决策工具 MVP 设计](./2026-08-07-voyage-fuel-decision-mvp-design.md)，港口比例见[港口比例功能说明](../../../港口比例功能说明.md)，因子数据见[燃料因子库规范](../../../燃料因子库规范.md)。

## 1. 规范用语与计算边界

本文中的“必须”“不得”“应返回”属于验收要求。“建议”只影响实现方式，不改变输出契约。

MVP 计算对象为报告年份和两个相邻有效 `Port of Call` 之间的一个航段。所有候选方案保持与 B0 相同的物理能源需求。单个混兑方案只包含一种基准燃料、一种候选燃料和一个候选燃料质量占比。

FuelEU 输出是“当前航段在比例分配假设下的独立合规情景估算”，不属于法规规定的船舶年度 compliance balance。该结果不得跨航次累加，也不得表述为正式年度合规余额、真实罚款或现金节省。

MVP 不输出独立物理生命周期 WtW 排放或减排。本文中的 WtW、WtT、TtW 和 GHGI 均指 FuelEU 法规口径。

## 2. 数值、单位与空值规则

### 2.1 规范内部单位

| 量 | 规范内部单位 |
| --- | --- |
| 燃料质量 `m` | `gFuel` |
| 用户燃料用量、价格和供应量 | 输入为公吨，进入内核前乘 `1,000,000 g/t` |
| 物理能源 `E` | `MJ` |
| LCV | `MJ/gFuel` |
| WtT、TtW、GHGI | `gCO2eq/MJ` |
| CO2、CH4、N2O、Cslip相关质量因子 | `gGHG/gFuel`；Cslip原值为质量百分比 |
| 合规余额 | 内部为 `gCO2eq`；对外同时提供 `tCO2eq` |
| EU ETS气体排放和EUAs | `tGHG`或`tCO2e` |
| 燃料价格 | 案例币种/公吨 |
| EUA价格 | 案例币种/`tCO2e` |
| FuelEU合规改善参考价值 | 案例币种/`tCO2e`合规余额改善 |
| FuelEU指示性罚款等值 | `EUR` |

`1 t = 1,000,000 g`。单位转换只在输入边界和输出格式化层进行，公式内部不得混用吨和克。

### 2.2 数值精度

- 内核必须采用十进制高精度数值，计算上下文至少提供 34 位有效十进制数字。
- 输入十进制数应以字符串解析，不能先经过二进制浮点数再进入高精度类型。
- 中间步骤不得按显示精度舍入。
- 方案排序、目标线判断、约束判断、临界点求解和状态分类全部使用未舍入内部值。
- 有限小数运算保持精确；除法和求根使用同一高精度上下文。
- `-0`在输出边界统一规范化为`0`。

跨实现验收时，有限精确结果应完全一致；循环小数和数值求根满足：

```text
absolute_error <= max(1e-12 × abs(expected), 1e-12 in the asserted unit)
ratio_absolute_error <= 1e-12
```

该误差只用于测试不同实现，不得用作业务判断前的舍入规则。

### 2.3 `null`、零和阻断

- `null`表示不适用、未提供或没有定义；字段必须同时携带原因码。
- 数值`0`表示该量已计算且结果为零。
- 因子中的`NA/null`、法规数值零和`RC`必须保留不同语义。
- 必需输入缺失或无效时返回`BLOCKED`，不得以零代替。

## 3. 输入契约

### 3.1 案例级输入

| 字段 | 必填 | 约束 |
| --- | --- | --- |
| `reportYear` | 是 | 整数，2024-2030 |
| `departurePort` | 是 | 5位有效UN/LOCODE |
| `arrivalPort` | 是 | 5位有效UN/LOCODE |
| `adjacentValidPortOfCallConfirmed` | 是 | 必须为`true` |
| `currency` | 是 | 案例内唯一币种代码或明确币种名称 |
| `baselineFuelPathId` | 是 | 可解析的航行燃料路径 |
| `baselineMassTonnes` | 是 | `> 0` |
| `baselinePricePerTonne` | 经济比较时必填 | `>= 0` |
| `euaPricePerTCO2e` | 当前模型成本比较时必填 | `>= 0` |

### 3.2 候选级输入

| 字段 | 必填 | 约束 |
| --- | --- | --- |
| `candidateFuelPathId` | 是 | 可解析的航行燃料路径 |
| `candidatePricePerTonne` | 经济比较时必填 | `>= 0` |
| `specifiedBlendRatios` | 否 | 每个值在`[0,1]`，候选质量/混合总质量 |
| `maxBlendRatio` | 否 | `[0,1]`；缺失表示1 |
| `candidateSupplyTonnes` | 否 | 整个输入航段可使用的实际质量，`>= 0` |
| `incrementalBudget` | 否 | 相对B0增加的当前模型成本上限，`>= 0` |
| `complianceImprovementValue` | 否 | 案例币种/`tCO2eq`，`>= 0` |

MVP 将“允许混兑范围”固定为`[0, maxBlendRatio]`。因子库和计算器不证明混兑兼容性；执行状态始终为`EXECUTION_CONDITIONS_PENDING`。

### 3.3 资格与证据输入

生物燃料 EU ETS 资格状态：

```text
NOT_DEMONSTRATED
ASSUMED_ELIGIBLE
VERIFIED_ELIGIBLE
```

- `NOT_DEMONSTRATED`：合格生物质比例按0，CO2按适用化石排放因子计算。
- `ASSUMED_ELIGIBLE`：允许建立估算情景，合格生物质比例按明确的`[0,1]`场景值处理，因子状态为`ESTIMATED`。
- `VERIFIED_ELIGIBLE`：必须有有效RED可持续性、减排资格及`[0,1]`适用生物质比例证据，因子状态可为`VERIFIED`。
- CH4和N2O不因上述CO2处理而归零。

RFNBO资格状态：

```text
NOT_DEMONSTRATED
ASSUMED_ELIGIBLE
VERIFIED_ELIGIBLE
INELIGIBLE
```

具体规则见第4.4节。

### 3.4 自定义燃料因子输入

自定义路径不得使用默认占位值。每个参与计算的自定义燃料/设备组合至少必须提供：

| 字段 | 内部单位或类型 | 要求 |
| --- | --- | --- |
| `pathId`、`equipmentId` | 字符串 | 组合身份必须稳定且唯一 |
| `lcv` | `MJ/gFuel` | `> 0`；必须给出单位和换算来源 |
| `wtTMode` | `STATIC`、`BIO_E`、`RFNBO_E`或`CERTIFIED` | 必须显式声明，不能由名称推断 |
| `wtT`、`E`、`eu`（按模式择一或组合） | `gCO2eq/MJ` | `STATIC/CERTIFIED`提供适用`wtT`；`BIO_E`提供`E`并按公式计算；`RFNBO_E`提供`E`和`eu`并按公式计算 |
| `cfCO2`、`cfCH4`、`cfN2O` | `gGHG/gFuel`或明确`NA` | 每个适用字段都必须有数值、单位和证据；不适用时必须显式记录`NA`；适用的法规零值也必须显式记录 |
| `eligibleBiomassFraction` | `[0,1]` | 生物燃料EU ETS资格分支需要；必须与资格状态和证据关联 |
| `cslip` | 质量百分比`[0,100]`或`NA` | 需要滑移时必须提供认可值或明确`SA`估算及其证据；`NA`只能用于明确不适用的路径 |
| `methaneSlipApplicable` | 布尔值 | 必须显式提供；决定EU ETS是否扣除未燃质量并计入CH4 |
| `csfCO2`、`csfCH4`、`csfN2O` | `gGHG/gFuel` | `cslip>0`时必填；定义FuelEU滑移气体组成 |
| `rwd` | `1`或适用的`2` | 必须附适用年份和资格证据；不能由燃料名称自动推断 |
| `sourceEvidence` | 结构化证据对象 | 每个数值字段至少一个来源ID、来源类型、单位和核验状态 |

自定义输入只提供聚合GHGI、单一“CO2e因子”或没有逐字段证据时，返回`BLOCKED`；不能用一个总强度值替代上述分子、分母和滑移字段。任何单位转换必须在解析阶段完成并保留原始值及换算记录。

## 4. 燃料因子解析

### 4.1 解析顺序

每个燃料组分按以下顺序解析：

1. 识别燃料路径和设备；
2. 读取法规固定值、法规回退值和单位换算值；
3. 应用适用的WtT模式；
4. 应用认证覆盖值或明确场景假设；
5. 处理生物燃料及RFNBO资格；
6. 验证LCV、排放因子、Cslip、RWD和证据完整性；
7. 输出逐字段来源和聚合因子状态。

同一燃料进入不同设备时必须按`m[i,j]`分别计算。LNG等设备相关路径不得使用通用Cslip。

### 4.2 WtT模式

```text
STATIC     -> WtT_i = 库内固定值
BIO_E      -> WtT_i = E_i - CfCO2_i / LCV_i
RFNBO_E    -> WtT_i = E_i - eu_i
CERTIFIED  -> WtT_i = 认可WtT
```

`BIO_E`和`RFNBO_E`必须从原始输入执行公式。文档中为阅读而显示的派生小数不得作为运行时常量。例如`UCO_FAME`应使用`14.9 - 2.834 / 0.037`，不能直接使用已显示舍入的`-61.694595`。

负WtT是合法法规结果，不得钳制为零，也不得解释为物理负排放。

### 4.3 Cslip

```text
p[i,j] = Cslip[i,j] / 100
```

- 数值Cslip必须在`[0,100]`。
- `NA/null`表示该路径无适用滑移值，计算使用`p=0`，证据语义仍保留`NA`。
- `RC`在核验结果中必须提供认可值；估算结果可使用明确`SA`。
- Cslip只除以100一次。

只有因子明确声明Cslip不适用时，`NA/null`才可按`p=0`处理。路径或设备需要Cslip而记录为`TBM/RC`且没有可用认可值时，正式结果必须阻断；估算结果必须显式使用`SA`并标记`ESTIMATED`。

Cslip 不作为普通用户输入。内置化石 LNG、生物 LNG 和 e-LNG 必须按燃料库中的对应设备路径读取 Cslip；其他内置路径不套用甲烷滑移公式。自定义或覆盖数据若对其他路径提供非零 Cslip，且没有明确支持的其他滑移气体规则，返回 `INVALID_CSLIP`，但只阻断该路径。LPG 和氨的参考网站 `Cslip=0` 只能用于估算并标记 `ESTIMATED`；正式核验必须提供适用的认可 Cslip，不能把该零值标记为 `VERIFIED`。

### 4.4 RFNBO

资格状态的计算规则：

| 状态 | FuelEU路径 | E与WtT | RWD | 因子状态 |
| --- | --- | --- | ---: | --- |
| `NOT_DEMONSTRATED` | 同类化石回退 | 使用回退路径 | 1 | 按回退因子确定 |
| `INELIGIBLE` | 同类化石回退 | 使用回退路径 | 1 | 按回退因子确定 |
| `ASSUMED_ELIGIBLE` | RFNBO估算情景 | 缺少批次E时采用保守场景`E=28.2`，再按`E-eu`推导 | 2025-2030为2 | `ESTIMATED` |
| `VERIFIED_ELIGIBLE` | RFNBO核验情景 | 必须有认证E且`E<=28.2`，再按`E-eu`推导 | 2025-2030为2 | `VERIFIED` |

MVP年份范围内，合格RFNBO的`RWD=2`。`E=28.2`是缺少批次数据时采用的最不利合格场景假设，必须标记为`SA`，不得称为法规默认值。

现有参考网站RFNBO WtT值不能作为合格估算情景的运行时常量。例如`E_DIESEL WtT=3`结合`eu=73.2`会反推出`E=76.2`，与`E<=28.2`冲突。

同类化石回退映射：

| RFNBO路径 | 回退路径 |
| --- | --- |
| `E_DIESEL` | `MDO` |
| `E_METHANOL` | `METHANOL_NG` |
| 四条`E_LNG_*`设备路径 | 对应设备的化石`LNG_*`路径 |
| `E_H2_FC` | `H2_NG_FC` |
| `E_H2_ICE` | `H2_NG_ICE` |
| `E_NH3_FC` | `NH3_NG_FC` |
| `E_NH3_ICE` | `NH3_NG_ICE` |

回退必须替换完整路径，包括WtT、TtW、Cslip和RWD。只取消RWD并保留RFNBO低WtT属于错误实现。

FuelEU资格不能自动转换为EU ETS零CO2资格。RFNBO或RCF只有在提供EU ETS适用规则下的认可CO2因子时才覆盖MRV因子；其余情形使用解析后的MRV因子并显示证据边界。

EU ETS零额状态按燃料纯组分分别保存：

```text
FOSSIL_TREATMENT
ESTIMATED_ASSUMED_ELIGIBLE
VERIFIED_ELIGIBLE
```

RFNBO或RCF的FuelEU资格状态不能自动赋予EU ETS零额状态。用户显式建立EU ETS合格假设时可生成`ESTIMATED_ASSUMED_ELIGIBLE`情景；只有适用EU ETS规则下的证据完整时才可生成`VERIFIED_ELIGIBLE`结果。

### 4.5 聚合因子状态

按以下优先级确定方案因子状态：

1. 任一必需字段缺失或无效：计算`BLOCKED`；
2. 任一参与计算字段为`SA`，或使用`ASSUMED_ELIGIBLE`：`ESTIMATED`；
3. 存在认证必需字段，且全部由有效证据支持：`VERIFIED`；
4. 其余仅由`RD/RF/UC/FD/NA`构成：`FIXED`。

固定法规字段与完整认证字段共同参与时可为`VERIFIED`。`VERIFIED`只说明当前因子证据完整，不代表年度FuelEU核证或方案可执行。

## 5. 港口与范围比例

港口模块输出：

```text
sETS_geo        ∈ {0, 0.5, 1}
sETS_surrender  = 0.4 (2024), 0.7 (2025), 1 (2026-2030)
sETS_effective  = sETS_geo × sETS_surrender
sFuelEU         = null (2024), or one of {0, 0.5, 1} (2025-2030)
```

三个EU ETS比例字段必须分别保留和展示。港口无效、年份无效或用户未确认相邻有效`Port of Call`时，整个案例`BLOCKED`。

若港口模块已经返回`sETS_effective`，计算内核只能读取该派生字段，不能再次乘以`sETS_geo`或`sETS_surrender`。实现必须在单一层完成乘法，并在测试中断言不存在重复清缴比例。

MVP假设范围内外使用相同燃料组成。`sFuelEU=0.5`时所有燃料组分等比例纳入。系统不支持只在范围内使用候选燃料的分配策略。

## 6. B0、纯燃料与质量混兑

设：

```text
μ       = 1,000,000 g/t
M0      = B0输入质量，t
m0      = μ × M0，g
Lb, Lc  = 基准和候选LCV，MJ/g
x       = 候选燃料占混合总质量的比例，[0,1]
```

B0物理能源：

```text
E0 = m0 × Lb
```

纯候选燃料质量：

```text
Mc_100 = M0 × Lb / Lc
```

质量混兑：

```text
Lmix(x)   = (1-x)Lb + xLc
Mtotal(x) = M0 × Lb / Lmix(x)
Mb(x)     = (1-x) × Mtotal(x)
Mc(x)     = x × Mtotal(x)
Eb(x)     = μ × Mb(x) × Lb
Ec(x)     = μ × Mc(x) × Lc
```

必须满足：

```text
Eb(x) + Ec(x) = E0
x=0 -> Mb=M0, Mc=0
x=1 -> Mb=0, Mc=Mc_100
```

纯候选方案始终作为数学参考计算。超出用户最大混兑、预算或供应约束时标记`CONSTRAINT_INFEASIBLE`，仍保留其参考结果。

## 7. EU ETS计算

### 7.1 MRV逐气体排放

对燃料`i`和设备`j`逐项计算：

```text
mNC[i,j]   = methaneSlipApplicable[i,j]
               ? m[i,j] × p[i,j]
               : 0
mBurn[i,j] = m[i,j] - mNC[i,j]

CO2_i_g = Σj mBurn[i,j] × EF_CO2[i,j]_effective
CH4_i_g = Σj (mBurn[i,j] × EF_CH4[i,j]
              + (methaneSlipApplicable[i,j] ? mNC[i,j] : 0))
N2O_i_g = Σj mBurn[i,j] × EF_N2O[i,j]
```

`methaneSlipApplicable`是逐路径、逐设备字段；内置化石LNG、生物LNG和e-LNG设备路径为`true`，其他内置路径为`false`。自定义燃料必须显式提供该字段及证据。只有适用甲烷滑移的设备才从燃烧质量中扣除`Cslip`并把扣除质量计入CH4；不能先在燃料级汇总后再套用一个设备因子，也不能在完整燃烧排放上额外加入滑移。自定义或覆盖数据对非甲烷路径给出大于零的`Cslip`时，只有在没有明确支持的其他滑移气体规则的情况下才返回`INVALID_CSLIP`，且仅阻断该路径。

生物燃料有效CO2因子：

```text
EF_CO2[i,j]_effective
  = EF_CO2[i,j] × (1 - eligibleBiomassFraction_i)
```

`NOT_DEMONSTRATED`时`eligibleBiomassFraction=0`；`ASSUMED_ELIGIBLE`使用明确场景比例；`VERIFIED_ELIGIBLE`使用认证比例。

每个纯燃料组分独立保存资格和比例。混兑方案不得先求一个平均生物质比例，再覆盖所有组分。

逐气体总量转为吨：

```text
CO2_t = Σi CO2_i_g / μ
CH4_t = Σi CH4_i_g / μ
N2O_t = Σi N2O_i_g / μ
```

### 7.2 年份气体范围与GWP

EU ETS使用：

```text
GWP_CO2 = 1
GWP_CH4 = 28
GWP_N2O = 265
```

```text
ETS_CO2e_preScope(y) =
  CO2_t                                      , y ∈ {2024, 2025}
  CO2_t + 28×CH4_t + 265×N2O_t              , y >= 2026
```

2024-2025仍可在明细中显示MRV监测得到的CH4和N2O，但必须标记`excludedFromEtsSurrender=true`。

### 7.3 范围、EUAs和成本

```text
ETS_CO2e_geo      = ETS_CO2e_preScope × sETS_geo
EUAs_required     = ETS_CO2e_geo × sETS_surrender
EUA_cost          = EUAs_required × euaPricePerTCO2e
```

一个EUA对应一吨纳入清缴的CO2e。`sETS_geo=0`时`EUAs_required=0`。EUA价格缺失时仍计算排放和EUAs，`EUA_cost=null`。

`EUAs_required`在MVP中保持连续十进制值，中间步骤和展示前均不向上取整。若未来正式清缴流程要求整数处理，应由年度合规模块另行定义。

EU ETS原始输出至少包括：

```text
mrvRawByGas { CO2_t, CH4_t, N2O_t }
mrvRawCO2e
etsIncludedGases
etsScopeByGas
sETS_geo
sETS_surrender
sETS_effective
EUAs_required
EUA_cost
zeroRatingStatusByFuelComponent
```

MVP不应用冰级、特殊航线、成员国豁免或其他额外系数。

## 8. FuelEU法规WtW、GHGI与合规余额估算

### 8.1 GWP和逐设备TtW

FuelEU使用：

```text
GWP_CO2 = 1
GWP_CH4 = 25
GWP_N2O = 298
fwind   = 1
```

```text
combustionEq[i,j]
  = CfCO2[i,j] + 25×CfCH4[i,j] + 298×CfN2O[i,j]

slipEq[i,j]
  = CsfCO2[i,j] + 25×CsfCH4[i,j] + 298×CsfN2O[i,j]

ttwMassEq[i,j]
  = (1-p[i,j]) × combustionEq[i,j]
  + p[i,j] × slipEq[i,j]
```

内置LNG、生物LNG和e-LNG路径的滑移因子为`CsfCO2=0,CsfCH4=1,CsfN2O=0`，因此`slipEq=25`。Cslip为`0`或`NA`时，滑移分子不影响结果。自定义燃料只要`Cslip>0`，就必须同时提供滑移气体因子和证据。`ttwMassEq`单位为`gCO2eq/gFuel`；TtW分子不得再乘LCV。

### 8.2 方案聚合

```text
D_RWD = Σi m_i × LCV_i × RWD_i
N_WtT = Σi m_i × LCV_i × WtT_i
N_TtW = Σi Σj m[i,j] × ttwMassEq[i,j]

WtT_intensity = N_WtT / D_RWD
TtW_intensity = N_TtW / D_RWD
GHGI_actual    = WtT_intensity + TtW_intensity
```

`RWD`只进入`D_RWD`，不得乘排放分子。`D_RWD<=0`时计算阻断。MVP无OPS和风助推进输入。

不能先计算每种燃料的GHGI再按质量平均。必须聚合分子和法规分母。

### 8.3 年度目标

```text
GHGI_target(y) = 91.16 × (1 - reduction_y)
```

| 年份 | 降低比例 | 未舍入目标，gCO2eq/MJ |
| --- | ---: | ---: |
| 2024 | 不适用 | `null` |
| 2025-2029 | 2% | `89.3368` |
| 2030 | 6% | `85.6904` |

目标值按表中未舍入值参与判断。

### 8.4 航段比例估算

当`reportYear>=2025`且`sFuelEU>0`：

```text
E_physical = Σi m_i × LCV_i
E_scoped   = sFuelEU × E_physical

CB_est_g = (GHGI_target - GHGI_actual) × E_scoped
CB_est_t = CB_est_g / μ
```

合规余额分类：

```text
CB_est_g > 0 -> SURPLUS_ESTIMATE
CB_est_g = 0 -> ON_TARGET_ESTIMATE
CB_est_g < 0 -> DEFICIT_ESTIMATE
```

分类使用未舍入值。合规余额单位是`gCO2eq`或`tCO2eq`，不能标成`gCO2eq/MJ`。

`E_scoped`使用未奖励物理能源，不能使用`D_RWD`。当所有燃料等比例纳入时，50%范围不会改变GHGI，只会把合规余额估算减半。

边界行为：

| 条件 | FuelEU状态 | `GHGI/CB/penalty` |
| --- | --- | --- |
| 2024 | `NOT_YET_APPLICABLE` | `null` |
| 2025-2030且`sFuelEU=0` | `OUT_OF_SCOPE` | `null`；`E_scoped=0` |
| 2025-2030且`sFuelEU>0` | `VOYAGE_PROPORTIONAL_ESTIMATE` | 按公式计算 |

范围为0时不以`CB=0`表示“恰好达标”。

### 8.5 指示性罚款等值

仅当`CB_est_g<0`时：

```text
indicativePenaltyEUR
  = abs(CB_est_g) / (GHGI_actual × 41,000) × 2,400
```

当FuelEU适用且`CB_est_g>=0`时，`indicativePenaltyEUR=0`。2024或范围为0时返回`null`。

结果币种始终为EUR，不进行案例币种换算，不进入当前模型成本、预算或默认排序。连续年度缺口加成、RFNBO子目标罚款、Banking、Borrowing和Pooling均不进入MVP。

## 9. 成本与相对变化

设价格单位为案例币种/吨：

```text
FuelCost(x) = Mb(x) × Pb + Mc(x) × Pc
EuaCost(x)  = EUAs_required(x) × Pe
ModelCost(x)= FuelCost(x) + EuaCost(x)
```

当前模型成本只包含燃料采购成本和EUA成本。

```text
delta(Y,x) = Y(x) - Y(B0)
percentDelta(Y,x) = delta(Y,x) / abs(Y(B0)) × 100%
```

当`Y(B0)=0`时，百分比变化返回`null`并标记`ZERO_BASELINE`。

任一必需价格缺失时：

- 排放、能源和FuelEU结果继续计算；
- 相应成本字段返回`null`；
- 方案不能进入当前模型成本排序、预算约束和经济切换点；
- 计算状态最高为`CALCULABLE`。

## 10. 预算、供应和混兑上限

为便于解析约束，定义每吨燃料的当前模型单位成本：

```text
Qb, Qc = EU ETS模块在当前年份和气体资格下的单位燃料CO2e，tCO2e/tFuel
κ      = sETS_effective
Kb     = Pb + Pe × κ × Qb
Kc     = Pc + Pe × κ × Qc
Ω      = Lb×Kc - Lc×Kb
```

当前模型成本及相对B0增量：

```text
ModelCost(x)
  = M0×Lb × [(1-x)Kb + xKc] / Lmix(x)

DeltaModelCost(x)
  = M0×x×Ω / Lmix(x)
```

### 10.1 增量预算上限

预算语义已经固定为：

```text
DeltaModelCost(x) <= incrementalBudget
```

定义纯候选增量：

```text
DeltaCost_100 = M0×Ω/Lc
```

预算允许的最大比例`xBudget`：

```text
预算缺失                              -> 1
Ω <= 0                                -> 1
Ω > 0 且 budget >= DeltaCost_100      -> 1
Ω > 0 且 0 <= budget < DeltaCost_100  ->
  budget×Lb / [M0×Ω - budget×(Lc-Lb)]
```

### 10.2 供应上限

```text
Supply >= Mc_100 -> xSupply=1
0 <= Supply < Mc_100 ->
  xSupply = Supply×Lb / [M0×Lb - Supply×(Lc-Lb)]
```

供应量是完整航段实际候选燃料质量，不乘EU ETS或FuelEU范围比例。

### 10.3 最终约束区间

```text
xCap = min(1, maxBlendRatio, all provided constraint upper bounds)
```

缺失预算或供应量表示不施加该项约束。价格不完整时`xBudget=null`，预算约束不可评估，计算`xCap`时省略该项；其他约束仍可计算。此情形返回`BUDGET_UNAVAILABLE_WITHOUT_PRICES`作为非阻断警告，方案仍可保持`CALCULABLE`，但不得进入经济排序或预算可行性结论。

## 11. 目标比例、最大改善与条件式方案

### 11.1 GHGI作为比例函数

对基准和候选燃料，定义：

```text
n_i = LCV_i×WtT_i + ttwMassEq_i
d_i = LCV_i×RWD_i

G(x) = [(1-x)n_b + xn_c] / [(1-x)d_b + xd_c]
```

若一种燃料对应多个设备，`n_i`使用该方案明确的设备质量分配聚合值。

### 11.2 达到目标的最低比例

```text
h_b = n_b - target×d_b
h_c = n_c - target×d_c
```

| 条件 | 结果 |
| --- | --- |
| 2024或FuelEU范围0 | `NOT_APPLICABLE` |
| `h_b<=0` | `xTargetMin=0` |
| `h_b>0`且`h_c>0` | `NO_SOLUTION` |
| `h_b>0`且`h_c=0` | `xTargetMin=1` |
| `h_b>0`且`h_c<0` | `xTargetMin=h_b/(h_b-h_c)` |

`xTargetMin<=xCap`表示约束下可达；否则返回`TARGET_UNREACHABLE_UNDER_CONSTRAINTS`，并同时展示无约束最低比例。

### 11.3 达标方案中当前模型成本最低的比例

“最低达标混兑比例”和“达标方案中成本最低的比例”是两个字段。

在价格完整、`xTargetMin`存在且`xTargetMin<=xCap`时：

```text
Ω > 0 -> xTargetMinCost = xTargetMin
Ω < 0 -> xTargetMinCost = xCap
Ω = 0 -> [xTargetMin, xCap]全部并列，代表比例取xTargetMin
```

候选燃料按同等物理能源更便宜时，增加混兑比例可能继续降低当前模型成本。

若无数学解、FuelEU不适用或`xTargetMin>xCap`，则`xTargetMinCost=null`并返回对应原因码；无约束的`xTargetMin`仍可单独展示。

### 11.4 约束下最大FuelEU改善

```text
Psi = n_c×d_b - n_b×d_c
```

```text
Psi < 0 -> GHGI随x降低，最大改善取xCap
Psi = 0 -> GHGI不变，所有比例并列，代表比例取0
Psi > 0 -> 候选使GHGI恶化，B0改善最大
```

主要改善量定义为：

```text
ComplianceImprovement_t(x)
  = [CB_est_g(x) - CB_est_g(B0)] / μ
```

在固定物理能源和范围比例下，最大合规余额改善与最低GHGI具有相同排序。2024或FuelEU范围0时不生成该建议。

### 11.5 当前模型成本最低方案

在价格完整且约束可评估时，成本优先方案定义为：

```text
xCostMin = argmin ModelCost(x), x ∈ [0, xCap]
```

在线性吨价和固定因子下：

```text
Ω > 0 -> xCostMin=0 (B0)
Ω < 0 -> xCostMin=xCap
Ω = 0 -> [0,xCap]全部并列，代表方案取B0
```

成本优先只使用`ModelCost`。FuelEU合规改善参考价值和指示性罚款等值不得改变该结论。

### 11.6 报告方案集合

连续区间用于求目标比例和约束边界。价格及合规价值切换表使用固定、可复核的报告方案集合：

```text
S_report = 去重后的集合：
  B0
  B100（仅当候选燃料允许单独使用）
  用户指定比例
  xTargetMin
  有效约束边界（xCap、预算/供应量边界、约束下最大改善比例）
```

集合按未舍入比例去重。B100即使受约束不可行也保留为参考，但不进入“约束下”排序。`xTargetMinCost`保留为结果字段；在线性成本模型下它复用`xTargetMin`或有效约束边界，不作为额外独立报告点。

## 12. 临界价格和方案切换点

### 12.1 候选燃料相对B0的临界吨价

对任意`x>0`：

```text
Pc_breakEven
  = (Lc/Lb)×(Pb + Pe×κ×Qb) - Pe×κ×Qc
```

在线性吨价和固定物理能源下，该临界价与混兑比例无关：

```text
Pc < threshold -> 任意正混兑降低当前模型成本
Pc = threshold -> 所有比例与B0当前模型成本相同
Pc > threshold -> 任意正混兑增加当前模型成本
```

临界价小于0时，所有合法非负候选价格都无法与B0持平。按照已确认的产品边界，候选报价、基准价格或EUA价格缺失时不对外输出经济临界价。

### 12.2 EUA价格临界点

```text
Pe_breakEven =
  [(Lc/Lb)×Pb - Pc]
  / {κ×[Qc - (Lc/Lb)×Qb]}
```

- 分母和分子均为0：所有EUA价格并列；
- 仅分母为0：无有限临界点；
- `κ=0`：EUA价格不改变排序；
- 只展示`Pe_breakEven>=0`的结果。

### 12.3 FuelEU合规改善参考价值

设`V`单位为案例币种/`tCO2eq`合规余额改善：

```text
I_s = ComplianceImprovement_t(s)
ReferenceAdjustedCost_s(V) = ModelCost_s - V×I_s
```

`ReferenceAdjustedCost`只用于敏感性分析，不能替代`ModelCost`，也不能进入默认成本排序。

任意两个固定报告方案`s,t`的切换点：

```text
V_star = (ModelCost_s - ModelCost_t) / (I_s - I_t)
```

分母为0且分子为0表示全区间并列；只有分母为0表示无切换点。仅考虑`V>=0`。

全局切换表必须计算所有可比较报告方案的下包络。两个方案虽有数学交点，但交点两侧始终存在成本更低的第三方案时，该交点不得显示为实际切换。

该参考价值不得与指示性罚款等值混用。

## 13. 状态与错误契约

### 13.1 计算状态

| 状态 | 定义 |
| --- | --- |
| `BLOCKED` | 港口、能源、比例、路径或必需因子无效/缺失 |
| `CALCULABLE` | 能源、排放和适用合规结果可计算，经济比较输入不完整 |
| `COMPARABLE` | 在可计算基础上，价格和比较口径完整，可进入相应排序 |

执行状态始终为：

```text
EXECUTION_CONDITIONS_PENDING
```

### 13.2 最低错误码集合

```text
INVALID_YEAR
INVALID_PORT_CODE
PORT_NOT_FOUND
PORT_OF_CALL_CONFIRMATION_REQUIRED
INVALID_BASELINE_MASS
INVALID_LCV
INVALID_BLEND_RATIO
MISSING_REQUIRED_FACTOR
INVALID_CSLIP
INVALID_RWD
INVALID_EMISSION_FACTOR
INVALID_BIOMASS_FRACTION
RFNBO_E_EXCEEDS_LIMIT
PRICE_REQUIRED_FOR_COMPARISON
BUDGET_UNAVAILABLE_WITHOUT_PRICES
TARGET_NOT_APPLICABLE
TARGET_NO_SOLUTION
TARGET_UNREACHABLE_UNDER_CONSTRAINTS
ZERO_BASELINE
```

`PRICE_REQUIRED_FOR_COMPARISON`、`BUDGET_UNAVAILABLE_WITHOUT_PRICES`和`ZERO_BASELINE`是非阻断警告；`TARGET_NOT_APPLICABLE`、`TARGET_NO_SOLUTION`和`TARGET_UNREACHABLE_UNDER_CONSTRAINTS`是目标搜索结果。其余代码在命中对应必需输入或因子时阻断受影响的案例或候选方案。

错误必须指向具体案例、方案、燃料组分和字段。一个候选方案阻断时，其他独立候选和B0仍可计算；案例级港口或B0能源错误阻断整个案例。

## 14. 输出与显示精度

### 14.1 原始输出

内核返回未按页面精度舍入的十进制字符串。页面、PDF和CSV必须消费同一份原始结果对象，不能分别重算。

CSV使用规范内部单位和完整内部十进制字符串，不使用科学计数法，并携带单位列、因子状态、资格状态、范围比例、公式版本和来源ID。

### 14.2 默认显示精度

页面和PDF共用同一显示配置：

| 字段族 | 默认显示 |
| --- | --- |
| 燃料质量 | 3位小数，t |
| 能源 | 3位小数，GJ；计算明细可显示MJ |
| 混兑及临界比例 | 4位小数，百分比点 |
| 港口范围和清缴比例 | 2位小数，百分比点 |
| GHGI、WtT、TtW和目标 | 4位小数 |
| 气体排放、EUAs、合规余额 | 6位小数，t或tCO2e |
| 价格、成本和罚款等值 | 2位小数 |
| 因子 | 最多9位小数，保留来源给定精度并去除无意义尾零 |

用户可在当前会话调整显示小数位。调整只改变格式化字符串，并同时应用于页面和随后导出的PDF；内部数值、CSV原始值、判断、排序和搜索结果保持不变。

必须测试：同一输入切换任意允许显示配置后，所有原始字段、方案ID、状态、排序和临界点完全一致。

## 15. 规范测试向量

所有预期值均来自本规格公式，断言使用第2.2节误差要求。

### 15.1 向量A：B0与质量混兑能源守恒

```text
M0=100 t
Lb=0.04 MJ/g
Lc=0.05 MJ/g
x=0.25
```

预期：

```text
E0       = 4,000,000 MJ
Mtotal   = 94.1176470588235294117647058824 t
Mb       = 70.5882352941176470588235294118 t
Mc       = 23.5294117647058823529411764706 t
Eb + Ec  = 4,000,000 MJ
```

### 15.2 向量B：FuelEU固定燃料、Cslip、负WtT和RWD

均为2025年、100% FuelEU范围、`fwind=1`。

| 场景 | 质量 | GHGI | CB估算，gCO2eq | 结果 |
| --- | ---: | ---: | ---: | --- |
| HFO | 1 t | `91.744197530864197530864197531` | `-97,499.6` | `DEFICIT_ESTIMATE` |
| LNG Otto中速，Cslip=3.1% | 1 t | `89.202929124236252545824847251` | `6,573.06` | `SURPLUS_ESTIMATE` |
| UCO_FAME，E=14.9 | 1 t | `16.383513513513513513513513514` | `2,699,271.6` | `SURPLUS_ESTIMATE` |
| 合格E_DIESEL，E=20、RWD=2 | 1 t | `11.583723653395784543325526932` | `3,320,056.36` | `SURPLUS_ESTIMATE` |
| E_DIESEL资格失败，回退MDO | 1 t | `90.767447306791569086651053864` | `-61,088.64` | `DEFICIT_ESTIMATE` |

E_DIESEL向量必须显式记录`eu=73.2`。这里的`E=20`是该测试情景的输入，原始WtT因子为`E-eu=-53.2 gCO2eq/MJ`；由于`RWD=2`只进入法规分母，聚合后的`WtT_intensity=-26.6`，不是把原始WtT因子改写成`-26.6`。该向量的完整复核值为：

```text
D_RWD          = 85,400 MJ
WtT_intensity  = -26.6 gCO2eq/MJ
TtW_intensity  = 38.183723653395784543325526932 gCO2eq/MJ
GHGI           = 11.583723653395784543325526932 gCO2eq/MJ
```

`E=20`只代表测试场景；实际运行仍须按RFNBO资格状态和证据规则确定`ESTIMATED`或`VERIFIED`，不能把它当作该路径的固定默认值。

LNG向量还必须断言：

```text
combustionEq = 2.78278
ttwMassEq    = 0.969×2.78278 + 0.031×25
             = 3.47151382 gCO2eq/gFuel
```

UCO向量必须从`WtT=14.9-2.834/0.037`计算，不能读取舍入常量。

### 15.3 向量C：FuelEU范围比例

```text
组合：50%质量HFO + 50%质量UCO_FAME
总质量：1 t
年份：2025
sFuelEU=0.5
```

预期：

```text
E_physical = 38,750 MJ
E_scoped   = 19,375 MJ
GHGI       = 55.765548387096774193548387097
CB_est     = 650,443 gCO2eq
```

同一组合在100%范围下GHGI不变，CB为`1,300,886 gCO2eq`。

### 15.4 向量D：目标、正负号和罚款等值

```text
year=2025
GHGI_actual=100 gCO2eq/MJ
E_physical=41,000,000 MJ
sFuelEU=1
```

预期：

```text
target       = 89.3368
CB_est       = -437,191,200 gCO2eq
classification = DEFICIT_ESTIMATE
penalty      = 255,916.80 EUR
```

`sFuelEU=0.5`时：

```text
CB_est  = -218,595,600 gCO2eq
penalty = 127,958.40 EUR
```

另断言2030目标为`85.6904`。盈余场景罚款等值为0；2024和范围0场景为`null`。

### 15.5 向量E：EU ETS年份气体与Cslip

```text
燃料：LNG Otto中速
质量：1,000 t
Cslip：3.1%
范围：EU ETS 100%
```

MRV逐气体预期：

```text
CO2  = 2,664.75 t
CH4  = 31 t
N2O  = 0.10659 t
三气体CO2e（GWP 1/28/265）= 3,560.99635 tCO2e
```

EUAs预期：

```text
2024 = 2,664.75 × 40% = 1,065.9
2025 = 2,664.75 × 70% = 1,865.325
2026 = 3,560.99635 × 100% = 3,560.99635
```

补充年度和地理范围断言：

```text
TV-E1: 2024，100 t HFO，双端EU ETS范围，EUA价格=80
  raw CO2=311.4 t，raw CH4=0.005 t，raw N2O=0.018 t
  included gases={CO2}，geo=1，phase=0.4
  EUAs=124.56，EUA成本=9,964.8

TV-E2: 2025，100 t MDO，一端范围、一端第三国，EUA价格=100
  raw CO2=320.6 t，raw CH4=0.005 t，raw N2O=0.018 t
  included gases={CO2}，geo=0.5，phase=0.7
  EUAs=112.21，EUA成本=11,221
```

两组测试中的原始CH4/N2O可以进入审计明细，但不得进入2024-2025 EUAs。

### 15.6 向量F：生物燃料EU ETS资格

```text
燃料：UCO_FAME
质量：1 t
年份：2026
EU ETS范围和清缴比例：100%
```

预期：

```text
NOT_DEMONSTRATED:
  CO2e = 2.834 + 28×0.00005 + 265×0.00018
       = 2.8831 tCO2e

ASSUMED_ELIGIBLE or VERIFIED_ELIGIBLE, eligible fraction=1:
  CO2e = 28×0.00005 + 265×0.00018
       = 0.0491 tCO2e
```

两种资格模式分别产生`ESTIMATED`和`VERIFIED`因子状态。

### 15.7 向量G：约束、达标比例和临界点

共同输入：

```text
B0=MGO, M0=100 t, Lb=0.0427, Pb=600
候选=UCO_FAME, Lc=0.037, Pc=1000
年份=2026
EU ETS地理比例=50%，清缴比例=100%，Pe=80
FuelEU范围=50%，target=89.3368
UCO EU ETS资格=ASSUMED_ELIGIBLE
```

必须解析：

```text
Qb=3.2551 tCO2e/tFuel
Qc=0.0491 tCO2e/tFuel
n_b=3.87577 gCO2eq/gFuel
n_c=0.60619 gCO2eq/gFuel
```

B20预期：

```text
Mtotal = 102.74302213666987488 t
Mb     = 82.19441770933589990 t
Mc     = 20.54860442733397498 t
FuelCost = 69,865.25505293551492
EUAs     = 134.27999278152069297
ModelCost= 80,607.65447545717036
GHGI     = 77.52295476419634264
CB_est   = 25,222,559.57844080847 gCO2eq
```

最低达标比例：

```text
xTargetMin = 0.0221306766829825081092
GHGI       = 89.3368
CB_est     = 0 within calculation tolerance
```

约束输入：

```text
incrementalBudget=5,000
candidateSupply=10 t
maxBlendRatio=0.30
```

预期：

```text
xBudget = 0.13301091073237190514
xSupply = 0.09868269008550959094
xCap    = 0.09868269008550959094
Mc      = 10 t
DeltaModelCost = 3,692.34538641686183
GHGI    = 84.32200105304147996
```

临界点：

```text
Pc_breakEven = 630.76546135831381733 /t
Pe_breakEven = 346.45311859774705762 /tCO2e

B20相对B0：
ComplianceImprovement = 28.27699157844080847 tCO2eq
DeltaModelCost        = 7,587.25447545717036
V_star                = 268.31901315986921862 /tCO2eq
```

### 15.8 向量H：空值和显示独立性

- 2024年任何航段：FuelEU `target/GHGI/CB/penalty=null`。
- 2025年FuelEU范围0：`E_scoped=0`且`GHGI/CB/penalty=null`。
- EU ETS范围0：`EUAs=0`；EUA价格缺失时`EUA_cost=null`。
- 价格缺失：能源和排放结果不变，状态为`CALCULABLE`，经济排序为空。
- 将页面显示比例从2位改为6位：所有原始值、状态、排序和临界点必须逐字段相同。

## 16. 最低自动化测试矩阵

实现至少覆盖：

1. 36条MVP航行燃料路径的因子解析和来源状态；
2. 自定义燃料逐字段单位、设备和证据契约，以及缺字段阻断；
3. 每种WtT模式；
4. 每种Cslip语义和设备路径；
5. 甲烷与非甲烷路径的`methaneSlipApplicable`分支，包括自定义或覆盖路径非零Cslip无受支持规则时的路径级阻断，以及LPG/氨参考零值的估算状态；
6. 2024、2025、2026、2029、2030年度边界；
7. EU ETS与FuelEU两套GWP隔离；
8. 港口范围`0/0.5/1`及EU ETS清缴`0.4/0.7/1`；
9. 生物燃料三种资格状态；
10. RFNBO四种资格状态、`E=28.2`边界和全部回退映射；
11. B0、B100、任意质量比例和不同LCV组合；
12. 预算、供应和最大比例分别绑定及共同绑定；
13. 达标、恰好达标、无解和约束下不可达；
14. 价格、EUA价格和合规改善价值切换；
15. 零基准、缺失价格、无效因子和候选局部阻断；
16. 页面/PDF共享格式化和CSV原始精度；
17. 所有导出字段与页面使用同一原始结果对象。

## 17. 依据与版本

| 规则 | 依据 |
| --- | --- |
| FuelEU GHGI、WtT、TtW、RWD、Cslip | Regulation (EU) 2023/1805 Annex I、II |
| FuelEU目标 | Regulation (EU) 2023/1805 Article 4 |
| 合规余额和罚款公式 | Regulation (EU) 2023/1805 Annex IV |
| EU ETS逐气体MRV公式 | Delegated Regulation (EU) 2023/2776 Annex I |
| EU ETS GWP | Delegated Regulation (EU) 2020/1044 |
| FuelEU GWP | Directive (EU) 2018/2001 |
| 港口和范围比例 | 项目《港口比例功能说明》及其来源索引 |
| 燃料路径和因子 | 项目《燃料因子库规范》及其核对记录 |

法规和港口规则核验日期沿用各来源文件记录。每次计算结果必须携带：计算规格版本、燃料因子版本、港口规则版本、报告年份和来源ID集合。
