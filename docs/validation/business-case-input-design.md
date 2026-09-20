# 业务案例输入设计与覆盖审计

审计日期：2026-09-18。对象为 `tools/validation/business_case_inputs.py` 的 `cases()`，以及已机械导出的 61 个业务案例。本文是输入设计和独立审计记录，不是使用教程、演示脚本、产品完成声明或主 runner 的验收报告。

## 1. 范围与结论

实施阶段保留了最初的只读审计结论，并据此修正六条非甲烷生物路径的 Cslip 快照、UCO 状态、增加非零合规参考价值案例，再统一刷新冻结期望。生产计算代码、法规公式、端口规则和现有未提交文档没有被改回或覆盖。

| 项目 | 审计值 |
| --- | --- |
| 案例数 | 61；A=7、B=18、C=8、D=28；已全部导出 |
| 候选输入 / 可解析候选快照 | 当前 builder 231 / 221；10 个无效候选不提供伪造的因子快照 |
| compact | 8；A、B、C、D 各2个 |
| 内置路径 | 36个不同请求路径，合并为6个 smoke 案例；不包含 OPS |
| 年份分布 | 2024：2；2025：5；2026：4；2030：49 |
| 港口对分布 | CNSHG→NLRTM：3；CNSHG→SGSIN：1；NLRTM→DEHAM：56 |
| HTTP 预期 | 59个200；1个422 |
| `expected_issues` | 16条：5条警告、10条候选阻断、1条案例阻断；不能把16条全部算成阻断 |
| builder 验证 | 19项测试通过；新增 Cslip 测试先在六条路径上失败，再通过 |

用户原计划明确要求的 A–D 输入形态、12个原有 B 变体、5个 B 扩展和36路径 smoke 均有见证。该结论仅指输入存在且具备相应测试条件。它不等于所有计算分支、全部设备资格组合、导出表面或所有经济切换结果已验证。

## 2. 元数据与快照语义

| 字段 | 冻结语义 |
| --- | --- |
| `id` | 稳定案例身份；匹配 `[A-D]-[A-Za-z0-9_-]+`；集合内唯一，前缀与 `family` 一致 |
| `family` | A：基准/范围；B：报价/约束；C：甲烷设备/资格；D：因子契约/异常/smoke |
| `name`、`purpose` | 中文人类元数据；分别描述案例名称和可核验目的，不充当计算输入 |
| `compact` | 显式选择的小规模代表集合；不是按执行结果动态筛选，也不是全覆盖声明 |
| `synthetic` | 必须为布尔值 `true`；所有报价、预算、供应、资格及自定义来源均为合成条件 |
| `assumptions` | 非空 `list[str]`；保存适用边界、非现实燃料需求、认证声明限制与兼容性边界 |
| `coverage` | 非空 `list[str]`；稳定见证标签，不证明该标签对应的下游断言已执行或通过 |
| `request` | 完整生产 API 请求形状；年份为整数，十进制量为字符串，缺价显式为 `null`；故意无效的字段仍按原样保留 |
| `snapshot.scope` | 独立冻结的 `geo`、`surrender`、`fueleu`；2024年的 `fueleu` 为 `null`，不写成0 |
| `snapshot.baseline` | 基准的归一化预期因子；确认失败案例中仅描述预定输入，不代表计算成功 |
| `snapshot.candidates` | 按 `candidateId` 索引的可解析因子；缺价候选仍保留；因子/比例错误候选不伪造快照 |
| `expected_issues` | 人工复核后冻结的输入错误和所需价格/预算警告；参考端会从请求字段独立推导同一集合并比较，不能把该字段当作计算输入；元素只有 `code`、`scope`、`candidate_id` |
| `expected_http_status` | 接口响应预期，独立于经济可比性；警告和局部候选阻断仍为200，未确认有效挂靠为422 |

归一化因子要求 `path_id/lcv/wtt/co2/ch4/n2o/slip/methane/rwd/biomass/factor_status/qualification/mode/equipment_id`。`csf_co2/csf_ch4/csf_n2o`、`e/eu`、`source_ids` 为可选扩展；当前 builder 为每个因子给出滑移组成。

- `lcv` 为 MJ/gFuel；`wtt`、`e/eu` 为 gCO2eq/MJ；三种燃烧和滑移气体因子为 gGHG/gFuel。
- `slip` 是质量百分比字符串，如 `"3.1"`；使用时仅除以100一次。`None` 表示不适用，`"0"` 表示有适用来源语义的数值零。
- `wtt` 可为精确分数字符串。例：UCO 为 `"-22827/370"`。这种分数只用于快照，不发送给生产 JSON 数值解析器。
- `biomass` 为资格处理后的有效合格比例，未证明资格或 RFNBO 不自动获得生物质零额。燃烧 `co2` 本身不被预先清零。
- `path_id` 为实际解析路径。未证明资格的 `E_DIESEL` 请求对应 `MDO` 快照；请求身份保存在 `request` 中。
- `equipment_id` 保留接口标识，例如 `LNG_OTTO_MS`、`BIOLNG_OTTO_MS`、`E_LNG_OTTO_MS` 表示同一设备类型的不同路径标识，不能按字符串相等判断同设备类型。
- 非适用燃烧气体可按零参加归一化算术，例如 `H2_NG_FC.n2o="0"`；该缩减快照没有逐字段 `na_fields`，不能声称穷尽生产因子证据语义。
- `CERTIFIED` 是 WtT 输入模式，不强制 `factor_status=VERIFIED`。自定义证据均为合成 SA，四种模式均保持 `ESTIMATED`。
- 内置资格 `VERIFIED_ELIGIBLE` 仅用于接口分支测试，没有真实 PoS/PoC。它不是认证证明。
- 候选映射按键关联。`B-reverse` 只反转请求候选顺序；快照字典迭代顺序无需同步，adapter 不得将两者位置配对。

## 3. 八个 Compact 选择

| 案例 | 选择理由 | 能观察的差异 |
| --- | --- | --- |
| `A-2024` | 年度与半范围的最小基准 | `geo=0.5`、清缴0.4、FuelEU尚未适用、无候选 |
| `A-manual-zero` | 不依赖复杂因子的手算锚点 | 1000吨×1000000×0.04=40000000 MJ；排放和采购/EUA成本均为零 |
| `B-default` | 保留业务比较主体 | 六报价、重复路径不同价格、供应约束、E公式、RFNBO奖励 |
| `B-combined-constraints` | 同请求内组合三种约束 | 对 HVO 同时输入预算1000、供应50、比例上限0.05 |
| `C-OTTO_MS-2025` | 滑移量较大的代表设备 | 生物三资格与RFNBO四资格；ETS仅清缴CO2 |
| `C-OTTO_MS-2026` | 与上一条组成年度控制对 | 相同设备和资格输入，切换为三气体清缴 |
| `D-custom-rfnbo_e` | 复杂自定义模式代表 | 逐字段来源、`E-eu`、RWD=2、资格与估算状态 |
| `D-missing-evidence` | 局部阻断代表 | 缺 `cfCH4` 证据，仅阻断该候选，保留有效对照 |

compact 刻意没有包含零范围、缺价警告、HTTP422、B100禁止、输入反序、重复报价并列、其他三类气体设备或36路径目录。尤其不能用 compact 通过来声称缺价不阻断；此次发现的 CASE 警告误分类正位于 full 集合。

## 4. 用户计划逐项见证

### A：基准和范围

| 要求 | 见证 |
| --- | --- |
| 2024、2025、2030，无候选 | `A-2024`、`A-2025`、`A-2030`，均为 CN→NL |
| 零范围 B0 | `A-zero-scope`，2030年 CN→SG |
| 缺少价格 | `A-missing-fuel-price`、`A-missing-eua-price`，分别缺基准价和EUA价 |
| 手算零锚点 | `A-manual-zero`，全部排放因子、WtT、采购价和EUA价为零 |

### B：六报价、十二原变体和五扩展

共同输入：2030年 NLRTM→DEHAM；MDO 1000吨、700 EUR/吨；EUA 80 EUR/tCO2e。所有基础报价指定质量比例0.01和0.05；明确声明该1000吨需求仅为合成能源测试，不是鹿特丹至汉堡实际油耗。

| 候选身份 | 路径 | 价格 | 比例上限 | 其他 |
| --- | --- | ---: | ---: | --- |
| `uco-limited` | UCO_FAME | 950 | 0.5 | 供应30吨；E=14.9 |
| `uco-bulk` | UCO_FAME | 1150 | 0.5 | E=14.9 |
| `hvo` | HVO | 1100 | 0.5 | E=20 |
| `bio` | BIODIESEL | 1200 | 0.5 | E=35 |
| `e-diesel` | E_DIESEL | 1600 | 0.7 | 假设合格；缺批次E，采用28.2 |
| `uco-high` | UCO_FAME | 1400 | 0.5 | E=14.9 |

十三个变体均以 `B-` 为前缀：`default`、`eua0`、`eua200`、`hvo-budget0`、`hvo-budget1000`、`hvo-supply0`、`hvo-supply50`、`hvo-cap005`、`rfnbo-unqualified`、`all-budgets1000`、`hvo-price600`、`reverse`、`reference-value100`。

五个扩展：`B-combined-constraints`、`B-missing-price-budget`、`B-b100-allowed`、`B-b100-forbidden`、`B-duplicate-ties`。并列扩展使用不同 `candidateId` 的相同报价，不是重复ID错误测试。B100禁止案例明确指定比例1并禁止纯用，其余五报价继续有效。`B-reference-value100` 是同一六报价输入的独立快照副本，仅给 HVO 增加 `complianceImprovementValue="100"`，以见证参考价值进入条件式成本线而不改变因子快照。

联合约束的精确手算给出 HVO `xBudget=7625/871156`、`xSupply=427/8527`、混兑上限 `1/20`，预算严格最小。因此该输入见证三种约束共同参与取最小值，不见证三条约束同时绑定或精确并列。

### C：同设备资格与气体年份

八条为 `C-{OTTO_MS|OTTO_SS|DIESEL_SS|LBSI}-{2025|2026}`。每条包含同设备化石LNG基准与7候选：生物LNG的未证明/假设/核验三资格，以及e-LNG的未证明/假设/核验/不合格四资格。

四设备 Cslip 依次为3.1%、1.7%、0.2%、2.6%。生物LNG显式E=20，使用第三节 LCV=0.050；其 ETS 生物质比例依次为0、1、1。合格e-LNG假设E=28.2或核验测试E=20，eu=56.2；不合格及未证明路径完整回退。

这是同设备数学比较；没有液体与气体混兑兼容性、真实设备改造或操作安全结论。

### D：模式、资格、错误与目录

| 要求 | 见证 |
| --- | --- |
| 四种自定义模式与逐字段证据 | `D-custom-static`、`D-custom-bio_e`、`D-custom-rfnbo_e`、`D-custom-certified` |
| 内置生物三资格 | `D-bio-unqualified`、`D-bio-assumed`、`D-bio-verified`；有效比例0、0.5、1 |
| RFNBO四资格 | `D-rfnbo-unqualified`、`D-rfnbo-assumed`、`D-rfnbo-verified`、`D-rfnbo-ineligible` |
| 负燃烧因子 | `D-negative-co2`、`D-negative-ch4`、`D-negative-n2o` |
| 缺证据、错误单位 | `D-missing-evidence`、`D-wrong-unit` |
| 非甲烷非零Cslip | `D-nonmethane-slip` |
| 年份及E上界 | `D-rwd2-2024`、`D-e283` |
| 缺报价、未知路径、确认失败 | `D-missing-price`、`D-unknown-path`、`D-confirmation-false` |
| 36内置请求路径 | `D-smoke-liquid` 5条；`D-smoke-fossil-gas` 10条；`D-smoke-bio-liquid` 5条；`D-smoke-bio-gas` 6条；`D-smoke-renewable-liquid` 2条；`D-smoke-renewable-gas` 8条 |

smoke 的最大混兑比例为0、指定比例为空、显式允许纯用数学参考。因此它覆盖目录解析和受约束不可行的B100参考，不覆盖36条路径各自的可执行混兑或全部合格分支。

## 5. 冻结常量的独立来源

定义两个本地来源：

- **CALC**：[航次燃料决策工具 MVP 计算规格](../superpowers/specs/2026-08-07-voyage-fuel-decision-calculation-spec.md)，包括其2026-09-07修订文本。
- **FACTORS**：[燃料因子库规范](../../燃料因子库规范.md)，法规核对日期2026-07-21、默认估算参数核对日期2026-07-24。本次未把这些日期表述为最新法规核验。

数字抄录与公式均来自上述冻结本地材料及用户给出的合成条件，不从生产因子表、reference输出或产品历史快照反推。产品代码仅用于确认接口形状、设备标识拼写及错误码封装；审计中的产品结果只用于复现缺价警告处理。

| 常量族 | 冻结值 | 依据 |
| --- | --- | --- |
| 范围 | CN→NL=0.5；NL→DE=1；CN→SG=0；2024/2025/2026–2030清缴0.4/0.7/1 | 用户指定三对；CALC §5；未调用生产港口解析生成预期 |
| HFO / LFO / MDO与MGO | `(LCV,WtT,CO2)` 分别为 `(0.0405,13.5,3.114)`、`(0.041,13.2,3.151)`、`(0.0427,14.4,3.206)` | FACTORS 第二节；FEU-01 Annex II p43，MRV-02 p6 |
| 常见液体燃烧 CH4/N2O | 0.00005 / 0.00018 | FACTORS 第二、三节各行RD/RF来源；不能应用到所有氢或LNG路径 |
| 化石LNG四设备 | LCV=0.0491、WtT=18.5、CO2=2.750、CH4=0、N2O=0.00011；滑移3.1/1.7/0.2/2.6 | FACTORS 第二节；FEU-01 p44，MRV-02 p6 |
| LNG滑移组成 | CsfCO2=0、CsfCH4=1、CsfN2O=0 | CALC §8.1 |
| 化石甲醇 | LCV=0.0199、WtT=31.3、CO2=1.375 | FACTORS 第二节 |
| 化石H2 | LCV=0.12、WtT=132、CO2=CH4=0；FC的N2O为NA，ICE为0.00018 | FACTORS 第二节；FC的NA仅在算术快照归一化为0 |
| LPG propane / butane | LCV=0.046、WtT=7.8、CO2=3.000/3.030；Cslip=0为SA估算 | FACTORS 第三节及§4.2；RC无认可值时不能称核验 |
| 化石NH3 FC/ICE | LCV=0.0186、WtT=121、CO2=0、CH4/N2O=0.00005/0.00018；Cslip=0为SA | FACTORS 第三节及§4.2 |
| 默认生物液体 | BIOETHANOL `(0.02685,20,1.913)`；BIODIESEL `(0.037,20,2.834)`；HVO `(0.044,15,3.115)`；BIOMETHANOL `(0.01986,18,1.375)` | FACTORS §4.2网站参数，状态ESTIMATED；元组为LCV/WtT/CO2；Cslip依NA规则单独处理 |
| 默认生物气体 | BIOLNG的LCV=0.0491、WtT=10；BIOH2的LCV=0.120、WtT=25，ICE的N2O=0.00002 | FACTORS §4.2；不能替换成第三节认证LCV或RF值 |
| UCO精确派生 | E=14.9、LCV=0.037、CO2=2.834；WtT=`-22827/370` | FACTORS 第三节、§4.3；RED-01 p129，CALC §4.2禁止舍入常量 |
| 显式E生物情景 | HVO E20：WtT=`-2235/44`；BIODIESEL E35：`-1539/37`；BIOLNG E20、LCV0.050：WtT=-35 | 用户合成E；FACTORS 第三节；`E-CO2/LCV`，CALC §4.2 |
| 合格电柴油 | LCV=0.0427、eu=73.2；E28.2→WtT=-45；E20→WtT=-53.2；RWD=2 | FACTORS 第三节、§5.5；CALC §4.4；RFNBO-02 p8、FEU-02相关指南 |
| 合格e-LNG | LCV=0.0491、eu=56.2；E28.2→WtT=-28；E20→WtT=-36.2；同设备滑移与RWD=2 | 同上；E为显式假设或核验分支的合成输入 |
| RFNBO回退 | 电柴油→MDO；电甲醇→METHANOL_NG；四e-LNG→同设备LNG；e-H2/e-NH3→同设备天然气制路径 | CALC §4.4完整回退表；不得保留低WtT仅取消奖励 |
| 自定义四模式 | LCV0.04、CO2=3、CH4=N2O=0；STATIC WtT10；CERTIFIED WtT12；BIO E25→WtT-50；RFNBO E20/eu70→WtT-50 | 人工合成，不属于官方燃料常量；公式与逐字段证据契约来自CALC §3.4、§4.2 |
| 手算零锚点 | LCV0.04，WtT与三气体因子均0；1000吨、两种价格均0 | 人工合成；CALC §6、§7、§9 |

报价、供应、预算、质量及自定义字段证据 `SYNTHETIC:<path>:<field>` 均是测试材料。内置快照未填写逐字段 `source_ids`，因此本文提供文档级出处，不宣称已经覆盖全部内置来源ID或证据链校验。

### Cslip NA 修订裁决

FACTORS §4.2网站参数表把多条非甲烷生物路径列为 Cslip=0；第三节正式路径表对 BIOETHANOL、BIODIESEL、HVO、BIOMETHANOL、BIOH2_FC、BIOH2_ICE 均明确标注 `null`、`NA·FEU-01·p45/46·C9`。第五节规则1要求保存NA与0的区别，规则4明确Cslip不参加通常的TBM/N/A回退；CALC §4.3同样要求保留NA语义。

归一化采用上述适用性规则：这六条路径的 `slip` 为 `None`，其余默认LCV/WtT/排放值仍按网站估算表保留。UCO原本已为 `None`。LPG和氨正式表为RC，且§4.2专门允许SA零估算，继续保留 `"0"` 和 `ESTIMATED`。LNG系列保留设备特定滑移。

本次修改只影响 `D-smoke-bio-liquid` 中四条快照和 `D-smoke-bio-gas` 中两条快照。全部请求和其他因子数值不变；这是证据适用性修正，不是依据产品数值配平预期。

## 6. 独立错误预期与非阻断警告

`scope` 表示影响对象，不表示严重性。参考端依据 CALC §13.2 从请求字段独立推导错误类别，再与冻结的 `expected_issues` 比较；因此错误码写错时会在调用产品前失败。`candidate_id=None` 的 CASE 缺价警告不能使 B0 消失；候选警告不能因为出现在 `expected_issues` 中就被移除快照。

| 案例 | 代码 / 作用域 | 独立推导及处理 |
| --- | --- | --- |
| `A-missing-fuel-price`、`A-missing-eua-price` | PRICE_REQUIRED_FOR_COMPARISON / CASE | CALC §7.3、§9、§13.2：成本缺失但能源和排放继续；HTTP200、CALCULABLE |
| `D-missing-price` | PRICE_REQUIRED_FOR_COMPARISON / CANDIDATE `missing` | 同上；候选因子仍有效 |
| `B-missing-price-budget` | PRICE_REQUIRED_FOR_COMPARISON 与 BUDGET_UNAVAILABLE_WITHOUT_PRICES / CANDIDATE `hvo` | CALC §10.3：预算不可评估，不参加上限取最小值；其他可计算约束与排放继续 |
| `D-negative-co2/ch4/n2o` | INVALID_EMISSION_FACTOR / CANDIDATE `invalid` | CALC §3.4、§13.2：燃烧因子负值不合法；不将合法负WtT当错误 |
| `D-missing-evidence` | MISSING_REQUIRED_FACTOR / CANDIDATE `invalid` | CALC §3.4：参与计算字段缺逐字段证据，不能以默认值补齐 |
| `D-wrong-unit` | MISSING_REQUIRED_FACTOR / CANDIDATE `invalid` | CALC §2.1、§3.4：声明MJ/kg却未提供换算记录；该fixture未构造有效转换 |
| `D-nonmethane-slip` | INVALID_CSLIP / CANDIDATE `invalid` | CALC §4.3：非甲烷路径给出非零滑移且没有支持规则 |
| `D-rwd2-2024` | MISSING_REQUIRED_FACTOR / CANDIDATE `invalid` | CALC §4.4禁止该年份奖励；当前自定义解析器以一般BLOCKED异常封装，JSON边界映射到此代码 |
| `D-e283` | RFNBO_E_EXCEEDS_LIMIT / CANDIDATE `invalid` | CALC §4.4：28.3大于28.2 |
| `D-unknown-path` | MISSING_REQUIRED_FACTOR / CANDIDATE `invalid` | CALC §3.1、§3.4：既非内置路径又无完整自定义因子；不得套默认值 |
| `B-b100-forbidden` | INVALID_BLEND_RATIO / CANDIDATE `hvo` | CALC §11.6：明确禁止纯用却指定比例1 |
| `D-confirmation-false` | PORT_OF_CALL_CONFIRMATION_REQUIRED / CASE | CALC §3.1、§5：案例前提失败，HTTP422，不计算B0 |

上表10个候选阻断均保留独立有效对照或其他报价，所以预期HTTP200。数值/物理规则来自规范；错误码封装和HTTP状态来自只读检查 `custom_factors.resolve_custom_factor`、`json_io._as_input_error`、`json_io._parse_candidate`、`json_io.parse_decision_case`、`web.calculate`。特别是2024 RWD=2的通用代码是当前边界映射，不是规范要求它必须叫 `MISSING_REQUIRED_FACTOR`。

`ZERO_BASELINE` 也是非阻断原因；`TARGET_NOT_APPLICABLE`、`TARGET_NO_SOLUTION`、`TARGET_UNREACHABLE_UNDER_CONSTRAINTS` 是目标搜索结果。本集合未把它们穷举进 `expected_issues`，必须由结果字段和原因码检查单独处理。不得把 `len(expected_issues)` 当失败数。

### 警告审计结果

只读复现曾发现 `business_case_reference.calculate_reference` 和 `ledger` 仅凭 `scope=="CASE"` 判阻断，使两个 A 缺价案例返回BLOCKED、B0为空；同请求生产计算保留B0。并行任务随后增加 `_case_blocked`，按代码排除非阻断警告和目标结果。本审计再次运行后，两个A缺价案例及B/D缺价案例均为CALCULABLE；两个A案例的 `ledger` 也可计算；确认失败仍为BLOCKED。

这两个 A 缺价案例的冻结 `expected.json` 已在最终冻结中重建，当前独立参考结果均为 `CALCULABLE`，产品输出也保留 B0、能源和排放字段，只将价格相关经济字段置空并给出原因。

当前 assertions 将两种价格/预算警告从顶层阻断 `issues` 的相等比较中排除，并对案例、候选、场景和 `field_reasons` 的目标范围检查警告是否实际出现。这样既不会把非阻断警告误算为阻断，也不会仅凭删除警告来让比较通过。

## 7. 未覆盖或只部分覆盖的范围

以下不影响“用户明确输入计划已有见证”的结论，但阻止把本集合称为完整规格矩阵：

1. **年度与港口组合**：没有2027–2029输入，尤其没有 CALC §16 提及的2029边界；没有无效年份、无效港口、未知港口或反向港口对。半范围仅覆盖MDO无候选基准，没有同一混合方案的0.5/1成对对照；零范围也没有带候选场景。
2. **全部资格组合**：36路径 smoke 对RFNBO只验证未证明资格的完整回退。合格分支集中于电柴油和四设备e-LNG；合格电甲醇、e-H2、e-NH3及其认可Cslip证据未覆盖。
3. **认证与证据**：自定义四模式仅有SA估算证据；没有自定义全字段VERIFIED正例、有效单位转换正例、真实认证文件核验、部分证据状态混合优先级或内置来源ID逐字段断言。
4. **滑移负例**：覆盖非甲烷非零滑移，没有负Cslip、超过100、甲烷缺失Cslip、自定义正滑移及完整Csf证据组合；LPG/氨仅为SA零估算，无RC认可值核验正例。
5. **一般无效输入**：负燃烧因子有三例；负/零LCV、缺E/eu、无效RWD值、无效生物质比例、非有限数、错误数据类型、负价格/预算/供应、重复候选ID、缺候选ID、全部候选都阻断等没有专门输入。
6. **约束几何**：预算/供应零值、有限值、比例上限及共同参与均有见证；精确多约束同时绑定、全部约束不绑定、B0已达标但便宜候选恶化GHGI形成达标上界等没有专门构造。`B-b100-forbidden` 覆盖显式指定1的拒绝，不穷尽优化器在无显式1输入时的纯用限制。
7. **数学边界与经济切换**：有重复报价并列、低价HVO、碳价变化与输入反序；未手工构造所有退化交点、极近交点、隐藏交点、精确ON_TARGET有限小数锚点。B组可支撑主runner计算全局下包络，但输入标签本身不证明这些结果已验收。
8. **警告组合**：有独立基准/EUA/候选缺价以及候选缺价带预算；没有所有价格同时缺失、非零参考价值显式输入、零范围缺EUA价等交叉组合。`ZERO_BASELINE`有条件见证，但不在 `expected_issues` 内声明具体结果位置。
9. **输出表面**：页面/PDF/CSV一致性、显示精度切换、移动端布局和截图证据属于主runner及surface任务；builder通过不代表这些通过。
10. **产品范围排除**：OPS、岸电能源输入、多设备质量分配、年度池化/借用/结转、正式年度罚款、特殊豁免、汇率、物理生命周期核算与真实采购建议均不由这些输入验证。

## 8. Schema 元数据校验

`business_case_schema.validate_case` 现在检查稳定 ID 格式及 family 前缀、中文/字符串元数据、非空 `list[str]`、synthetic/compact 布尔声明、request/snapshot 信封、expected issue 的代码/作用域/候选归属、HTTP 状态、嵌套浮点、范围键、归一化因子必填字段和数值边界。案例集合的 ID 唯一性由 worker 冻结/读取时检查，builder 测试另行检查 compact 各族代表和 36 路径覆盖。

单案例内存变异测试覆盖了错误 family、类型混用、缺 issue 字段、空请求、非数字因子、零/负 LCV、负气体因子、越界 biomass 和越界 slip。生产请求允许有意非法，因为它承载阻断案例；schema 只验证案例信封和归一化快照，不把“所有 request 必须解析成功”误设为约束。

## 9. 验证记录与冻结身份

本次运行 `python -B -m unittest tools.validation.test_business_case_inputs -v`：19项通过。新增测试 `test_smoke_preserves_nonmethane_na_separately_from_rc_estimate_zero` 在修改前产生六个预期失败，修改后通过，并同时保护LPG/氨SA零值与全部LNG设备滑移；随后新增 UCO 状态和非零 `complianceImprovementValue` 两项测试。

最终冻结后，61 个落盘案例均可由 `load_case` 读取、重新计算并与期望指纹一致；本文不把输入设计结论扩大成独立计算正确性结论，跨实现结果见 [business-case-validation-report.md](./business-case-validation-report.md) 和 [business-case-results.json](./business-case-results.json)。

| 对象 | SHA-256 |
| --- | --- |
| 当前builder文件 | `FD924736E757956D013BEB6E57A3227963477A1CD52F295FBFC010EC55D06D94` |
| 当前builder测试文件 | `166738EA8E9E1C2FB610C6AA2CBF11C2C1ACDC25452B92D4703B0B21E4CEDB44` |
| 当前案例manifest | `57A1B6F4E74F6A28E8F20DE7D099D8862EC42D64BA99488F8F7AB75263044716` |
| CALC源文件 | `1f5360800ac9e9a7d880409311d9eee2ea87d58a1814d92bc112912aa98323d5` |
| FACTORS源文件 | `d1d390308e33df62deb713babeae2143f0e56e601e03236ca4248fd0822959cd` |
| 当前schema文件 | `83701E8CF19AC1606A831FFF6177DA916B3476C9699868E1E19DBE83BD34A7A7` |

案例指纹使用排序键、UTF-8、无额外空格并保留案例列表顺序；它不是文件字节摘要。输入变更必须通过显式 `--freeze` 重建独立期望，不能用产品运行结果回填，也不能通过改变案例 ID 或删除正确警告来迁就旧预期。
