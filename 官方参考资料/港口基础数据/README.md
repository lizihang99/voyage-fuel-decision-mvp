# 港口基础数据说明

> 数据版本：UN/LOCODE 2025-1。制度身份核验日期：2026-07-23。

这份文档只说明港口表是什么、各列怎样看，以及怎样从官方数据重新生成。比例规则和使用方法见[港口比例功能说明](../../港口比例功能说明.md)。

## 1. 项目使用哪份数据

项目只有一份正式港口运行表：

[UNLOCODE_2025-1_港口制度身份清单.csv](./UNLOCODE_2025-1_港口制度身份清单.csv)

人工查询和代码运行都使用这份 CSV。同目录的 [UNLOCODE_2025-1_官方发布包.zip](./UNLOCODE_2025-1_官方发布包.zip) 是 UNECE 原始资料，只用于重新生成和核对结果。

## 2. 九个字段怎样看

| 列名 | 含义 | 示例 |
| --- | --- | --- |
| `unlocode` | 5 位港口代码，也是查询主键 | `NLRTM` |
| `portName` | UNECE 记录的港口或地点名称 | `Rotterdam` |
| `countryCode` | ISO 两位国家或地区代码 | `NL` |
| `territoryType` | 项目用于归类港口的地域类型 | `EU_MEMBER` |
| `territoryName` | 便于人阅读的地域名称 | `EU member state ordinary territory` |
| `euEtsStatus` | 该港口在 EU ETS 下的基础身份 | `IN_SCOPE` 或 `THIRD_COUNTRY` |
| `fuelEuStatus` | 该港口在 FuelEU 下的基础身份 | `IN_SCOPE`、`OMR` 或 `THIRD_COUNTRY` |
| `ruleSourceId` | 本行使用的官方依据编号，多个编号用分号分隔 | `PORT-02;ETS-01;FEU-01` |
| `sourceVersion` | 本行使用的港口数据版本 | `UN/LOCODE 2025-1` |

正式表共 17,519 行，归类情况如下：

| `territoryType` | 通俗含义 | 条数 |
| --- | --- | ---: |
| `EU_MEMBER` | 普通欧盟地区 | 5,651 |
| `THIRD_COUNTRY` | 普通第三国或按第三国计算的地区 | 10,805 |
| `OMR` | 欧盟最外围地区 | 124 |
| `OCT` | 欧盟海外国家和领地 | 90 |
| `SVALBARD` | 斯瓦尔巴 | 4 |
| `FAROE_ISLANDS` | 法罗群岛 | 23 |
| `EEA_NO_IS` | 挪威、冰岛和 Jan Mayen | 821 |
| `EU_MEMBER_SPECIAL` | 奥兰群岛 | 1 |

`CYAKT`、`CYDHK`、`CYFMG`、`CYKAR`、`CYKYR` 已按官方材料核对，并固定使用两项制度的第三国计算标签。这里的标签只服务于比例计算，不表达主权判断。

港口表保存的是单个港口的身份。代码会把开始港和到达港的身份组合起来，再计算航段的 0%、50% 或 100%。

## 3. CSV 怎样生成

生成过程不经过 Excel，也没有人工维护的中间表：

```text
UNECE 官方 ZIP
  -> ZIP 内三个 UNLOCODE CodeListPart*.csv
  -> generate-port-identity-mapping.mjs
  -> 唯一正式 CSV
```

脚本选取 `Function` 第一位为 `1` 的 Port 候选。同一 UN/LOCODE 出现多条记录时，先保留日期最新的记录，再排除删除项和已核实的异常项，最后补充 EU ETS 与 FuelEU 身份。

重新生成：

```powershell
Expand-Archive `
  -LiteralPath '.\官方参考资料\港口基础数据\UNLOCODE_2025-1_官方发布包.zip' `
  -DestinationPath "$env:TEMP\unlocode-2025-1-release-current" `
  -Force

$env:UNLOCODE_RELEASE_DIR = "$env:TEMP\unlocode-2025-1-release-current\release"
node .\generate-port-identity-mapping.mjs
```

UNECE 2025-1 中有 17,524 个唯一 Port 候选代码，正式表排除以下 5 条后保留 17,519 条：

| 排除代码 | 原因 |
| --- | --- |
| `AUAIR` | UNECE `Change=X`，表示删除记录 |
| `JOAQB` | UNECE `Change=X`，表示删除记录 |
| `MYRAI` | UNECE `Change=X`，表示删除记录 |
| `THSBP` | UNECE `Change=X`，表示删除记录 |
| `CYNIC` | Nicosia 记录为关闭机场，不适合作为海运 Port of Call 候选 |

脚本结束时会输出源记录数、正式表条数、排除记录和各地域数量，用于核对生成结果。制度身份需要调整时，应修改分类规则后重新生成整张表，不应直接手工修改 CSV。

## 4. 数据使用边界

UNECE 的 Port 标记只说明该地点被列为港口候选，不能证明它一定适用于海运法规，也不能判断某次停靠是否属于法规意义上的 `Port of Call`。当前表没有逐一核验全部 17,519 个地点的实际海运停靠条件，产品使用时由用户确认输入的是相邻的有效 `Port of Call`。

`CYNIC` 是当前版本中已经发现并核实的明显冲突记录。排除这一条，不代表其他候选地点均经过了同等程度的海运真实性核验。

这张表只提供基础地域身份。船舶适用性、转运港、航线豁免、冰级减免和 FuelEU 年度合规需要在其他步骤判断。

## 5. 官方来源

- [UNECE UN/LOCODE 下载页](https://unece.org/trade/cefact/UNLOCODE-Download)
- [UN/LOCODE 2025-1 官方发布包](https://opensource.unicc.org/un/unece/uncefact/vocab-locode/-/jobs/artifacts/2025-1/download?job=package-release)
- [UNECE Recommendation No. 16](https://unece.org/sites/default/files/2023-10/rec16_ece-trd-227E.pdf)
- [UNECE 字段说明](https://service.unece.org/trade/locode/Service/LocodeColumn.htm)
- [EU ETS、FuelEU 与特殊地域官方来源索引](../航程范围规则/来源索引.md)
