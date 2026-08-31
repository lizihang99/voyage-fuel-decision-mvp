import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describePortIdentity } from "./port-identity-mapping.mjs";

/**
 * 将 UNECE UN/LOCODE 2025-1 官方发布包转换为项目唯一的港口运行表。
 *
 * 转换顺序：
 * 1. 读取官方 ZIP 解压目录中的三个 CodeList CSV 分片；
 * 2. 只保留 Function 第一位为 1 的 Port 候选记录；
 * 3. 按 5 位 UN/LOCODE 合并重复记录，并选取日期最新的官方记录；
 * 4. 排除官方删除记录和已核实不属于海运 Port of Call 候选的 CYNIC；
 * 5. 根据 port-identity-mapping.mjs 补充 EU ETS 与 FuelEU 制度身份；
 * 6. 只输出查询和计算需要的 9 列 CSV。
 *
 * 脚本不读取或生成任何人工维护的中间表。制度身份的修改应进入分类代码，
 * 然后从同一份官方发布包重新生成完整 CSV，避免直接手工修改结果文件。
 */

const root = path.dirname(fileURLToPath(import.meta.url));

// UNLOCODE_RELEASE_DIR 应指向 ZIP 解压后的 release 目录；未设置时使用约定的临时目录。
const archiveExtracted = process.env.UNLOCODE_RELEASE_DIR;
const defaultReleaseDir = path.join(process.env.TEMP ?? ".", "unlocode-2025-1-release-current", "release");
const releaseDir = archiveExtracted || defaultReleaseDir;
const csvDir = path.join(releaseDir, "csv");
const outputPath = path.join(root, "官方参考资料", "港口基础数据", "UNLOCODE_2025-1_港口制度身份清单.csv");

function parseCsvLine(line) {
  // UNECE 名称和备注可能包含逗号或双引号，因此不能直接使用 line.split(",")。
  // 这里按 RFC 4180 的常用引号规则读取单行，并将连续两个双引号还原为一个。
  const fields = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (quoted && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (char === "," && !quoted) {
      fields.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  fields.push(current);
  return fields;
}

function dateRank(value) {
  // UNECE Date 字段采用 YYMM。80-99 解释为 1980-1999，00-79 解释为 2000-2079，
  // 转成 YYYYMM 数值后即可比较同一 UN/LOCODE 下不同记录的新旧顺序。
  const match = String(value ?? "").match(/^(\d{2})(\d{2})$/);
  if (!match) return -1;
  const year = Number(match[1]);
  const month = Number(match[2]);
  return (year >= 80 ? 1900 + year : 2000 + year) * 100 + month;
}

function recordRank(row) {
  // 日期相同时优先采用带 Change 标记的记录，因为它表达了 UNECE 对旧记录的正式变更。
  // 这一步必须发生在过滤 Change=X 之前，否则旧的有效记录可能错误地重新进入正式表。
  return [dateRank(row.date), row.change ? 1 : 0];
}

function isLaterRecord(candidate, current) {
  const [candidateDate, candidateChange] = recordRank(candidate);
  const [currentDate, currentChange] = recordRank(current);
  return candidateDate > currentDate || (candidateDate === currentDate && candidateChange > currentChange);
}

function csvEscape(value) {
  // 输出字段包含逗号、双引号或换行时加引号，保证生成结果可被标准 CSV 解析器读取。
  const text = String(value ?? "");
  return /[\",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

if (!fs.existsSync(csvDir)) {
  throw new Error(`找不到 UNECE CSV 目录：${csvDir}。请先解压官方发布包，并设置 UNLOCODE_RELEASE_DIR。`);
}

const files = fs.readdirSync(csvDir)
  // 2025-1 官方发布包将 CodeList 拆成三个分片。SubdivisionCodes.csv 不属于地点记录。
  .filter((file) => /^UNLOCODE CodeListPart\d+\.csv$/i.test(file))
  .sort();
if (files.length !== 3) throw new Error(`预期 3 个 UNLOCODE CSV 分片，实际找到 ${files.length} 个。`);

const sourceRows = [];
for (const file of files) {
  const content = fs.readFileSync(path.join(csvDir, file), "utf8");
  for (const line of content.split(/\r?\n/)) {
    if (!line) continue;
    const fields = parseCsvLine(line);

    // 官方字段顺序为：
    // Change, Country, Location, Name, NameWoDiacritics, Subdivision,
    // Function, Status, Date, IATA, Coordinates, Remarks。
    // Function 是 8 位功能码，第一位为 1 表示该地点具有 Port 功能。
    // 它只能筛选港口候选，不能证明某次实际停靠构成法规意义上的 Port of Call。
    if (fields.length < 12 || !fields[2] || !fields[6]?.startsWith("1")) continue;
    const row = {
      countryCode: fields[1],
      locationCode: fields[2],
      name: fields[3],
      nameWoDiacritics: fields[4],
      subdivision: fields[5],
      functionCode: fields[6],
      status: fields[7],
      date: fields[8],
      iata: fields[9],
      coordinates: fields[10],
      remarks: fields[11],
      change: fields[0],
    };
    sourceRows.push(row);
  }
}

const sourceRecordCount = sourceRows.length;
const groupedRows = new Map();
for (const row of sourceRows) {
  // 国家代码 2 位 + 地点代码 3 位组成项目查询使用的 5 位 UN/LOCODE，例如 NL + RTM。
  const key = `${row.countryCode}${row.locationCode}`;
  const group = groupedRows.get(key) ?? [];
  group.push(row);
  groupedRows.set(key, group);
}

const canonicalSourceRows = [];
for (const group of groupedRows.values()) {
  // 同一代码可能因改名、状态更新或删除而出现多条记录。这里只保留最新的规范记录。
  const canonical = group.reduce((current, candidate) => (isLaterRecord(candidate, current) ? candidate : current));
  canonicalSourceRows.push(canonical);
}

const excludedRows = [];
const canonicalRows = [];
for (const row of canonicalSourceRows) {
  const unlocode = `${row.countryCode}${row.locationCode}`.toUpperCase();

  // Change=X 是 UNECE 的删除标记。规范记录为 X 时整个代码退出正式表，不能回退使用旧记录。
  if (String(row.change ?? "").toUpperCase() === "X") {
    excludedRows.push({ unlocode, reason: "UNLOCODE_CHANGE_X" });
    continue;
  }

  // CYNIC 的官方记录虽然带 Port 功能位，但名称为 Nicosia、备注为 Closed airport。
  // 它不满足本项目海运双港查询的数据用途，因此作为经核实的单点例外排除。
  if (unlocode === "CYNIC") {
    excludedRows.push({ unlocode, reason: "NOT_A_MARITIME_PORT_OF_CALL" });
    continue;
  }

  // 分类模块集中维护普通欧盟、第三国、OMR、OCT、挪威/冰岛和塞浦路斯等规则。
  // 生成器只负责把分类结果写入表，避免在转换脚本中复制一套制度判断。
  const portIdentity = describePortIdentity(row);
  canonicalRows.push({
    unlocode,
    portName: row.name,
    countryCode: row.countryCode,
    territoryType: portIdentity.territoryType,
    territoryName: portIdentity.territoryName,
    euEtsStatus: portIdentity.euEtsStatus,
    fuelEuStatus: portIdentity.fuelEuStatus,
    // PORT-02 追溯到 UNECE 原始包，其余 ID 追溯到制度或特殊地域官方依据。
    ruleSourceId: [...new Set(["PORT-02", ...portIdentity.ruleSourceIds])].join(";"),
    sourceVersion: "UN/LOCODE 2025-1",
  });
}
canonicalRows.sort((a, b) => a.unlocode.localeCompare(b.unlocode));
excludedRows.sort((a, b) => a.unlocode.localeCompare(b.unlocode));

const columns = [
  // 列顺序属于运行时数据契约；port-scope-rates.mjs 会严格校验这 9 列。
  "unlocode", "portName", "countryCode", "territoryType", "territoryName",
  "euEtsStatus", "fuelEuStatus", "ruleSourceId", "sourceVersion",
];
const csv = [columns.join(","), ...canonicalRows.map((row) => columns.map((column) => csvEscape(row[column])).join(","))].join("\n") + "\n";
fs.writeFileSync(outputPath, csv, "utf8");

// 生成摘要用于人工和自动核对：源记录数、唯一代码数、排除项和最终地域分布应保持可解释。
const territoryCounts = Object.fromEntries(
  [...new Set(canonicalRows.map((row) => row.territoryType))]
    .sort()
    .map((key) => [key, canonicalRows.filter((row) => row.territoryType === key).length]),
);
console.log(JSON.stringify({
  outputPath,
  sourceRecordCount,
  sourceUniquePortCodes: canonicalSourceRows.length,
  formalPortCodes: canonicalRows.length,
  excludedRows,
  territoryCounts,
}, null, 2));
