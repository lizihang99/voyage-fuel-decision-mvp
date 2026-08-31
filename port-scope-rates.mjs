import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const PORT_TABLE_COLUMNS = Object.freeze([
  "unlocode",
  "portName",
  "countryCode",
  "territoryType",
  "territoryName",
  "euEtsStatus",
  "fuelEuStatus",
  "ruleSourceId",
  "sourceVersion",
]);

export const DEFAULT_PORT_TABLE_PATH = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "官方参考资料",
  "港口基础数据",
  "UNLOCODE_2025-1_港口制度身份清单.csv",
);

let defaultTableCache;

const EXPECTED_STATUSES = Object.freeze({
  EU_MEMBER: ["IN_SCOPE", "IN_SCOPE"],
  EU_MEMBER_SPECIAL: ["IN_SCOPE", "IN_SCOPE"],
  OMR: ["IN_SCOPE", "OMR"],
  EEA_NO_IS: ["IN_SCOPE", "THIRD_COUNTRY"],
  OCT: ["THIRD_COUNTRY", "THIRD_COUNTRY"],
  SVALBARD: ["THIRD_COUNTRY", "THIRD_COUNTRY"],
  FAROE_ISLANDS: ["THIRD_COUNTRY", "THIRD_COUNTRY"],
  THIRD_COUNTRY: ["THIRD_COUNTRY", "THIRD_COUNTRY"],
});

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (character === '"') {
      if (quoted && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (character === "," && !quoted) {
      row.push(field);
      field = "";
    } else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && text[index + 1] === "\n") index += 1;
      row.push(field);
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      field = "";
    } else {
      field += character;
    }
  }

  if (quoted) throw new Error("Invalid CSV: unclosed quoted field");
  if (field !== "" || row.length > 0) {
    row.push(field);
    if (row.some((value) => value !== "")) rows.push(row);
  }
  return rows;
}

function normalizeUnlocode(value) {
  const normalized = String(value ?? "").trim().toUpperCase().replace(/[\s/-]/g, "");
  if (!/^[A-Z]{2}[A-Z0-9]{3}$/.test(normalized)) {
    throw new Error(`Invalid UN/LOCODE: ${value ?? ""}`);
  }
  return normalized;
}

export function parsePortIdentityCsv(text) {
  const rows = parseCsv(String(text ?? "").replace(/^\uFEFF/, ""));
  if (rows.length === 0) throw new Error("Port identity table is empty");
  const columns = rows[0];
  if (columns.length !== PORT_TABLE_COLUMNS.length || columns.some((column, index) => column !== PORT_TABLE_COLUMNS[index])) {
    throw new Error(`Unexpected port table columns: ${columns.join(",")}`);
  }

  const ports = new Map();
  for (let index = 1; index < rows.length; index += 1) {
    const values = rows[index];
    if (values.length !== columns.length) throw new Error(`Invalid port table row ${index + 1}: expected ${columns.length} columns`);
    const record = Object.fromEntries(columns.map((column, columnIndex) => [column, values[columnIndex]]));
    const unlocode = normalizeUnlocode(record.unlocode);
    const expectedStatuses = EXPECTED_STATUSES[record.territoryType];
    const validIdentity = record.countryCode === unlocode.slice(0, 2)
      && record.portName !== ""
      && expectedStatuses?.[0] === record.euEtsStatus
      && expectedStatuses?.[1] === record.fuelEuStatus
      && record.ruleSourceId.split(";").includes("PORT-02")
      && record.sourceVersion !== "";
    if (!validIdentity) throw new Error(`Invalid port identity row ${index + 1}: ${unlocode}`);
    if (ports.has(unlocode)) throw new Error(`Duplicate UN/LOCODE in port table: ${unlocode}`);
    ports.set(unlocode, Object.freeze({ ...record, unlocode }));
  }

  return Object.freeze({ columns: Object.freeze([...columns]), ports });
}

export function loadPortIdentityTable(filePath = DEFAULT_PORT_TABLE_PATH) {
  const resolvedPath = path.resolve(filePath);
  if (resolvedPath === path.resolve(DEFAULT_PORT_TABLE_PATH) && defaultTableCache) return defaultTableCache;
  const table = parsePortIdentityCsv(fs.readFileSync(resolvedPath, "utf8"));
  if (resolvedPath === path.resolve(DEFAULT_PORT_TABLE_PATH)) defaultTableCache = table;
  return table;
}

export function getPortIdentity(portTable, unlocode) {
  const code = normalizeUnlocode(unlocode);
  const record = portTable?.ports?.get(code);
  if (!record) throw new Error(`Port not found in formal table: ${code}`);
  return record;
}

function matrixRate(statuses) {
  const inScopeCount = statuses.filter((status) => status === "IN_SCOPE").length;
  if (statuses.some((status) => !["IN_SCOPE", "THIRD_COUNTRY"].includes(status))) {
    throw new Error(`Unsupported port status combination: ${statuses.join(",")}`);
  }
  if (inScopeCount === 2) return { rate: 1, reason: "BOTH_IN_SCOPE" };
  if (inScopeCount === 1) return { rate: 0.5, reason: "ONE_IN_SCOPE" };
  return { rate: 0, reason: "BOTH_THIRD_COUNTRY" };
}

function surrenderRateForYear(year) {
  if (year === 2024) return 0.4;
  if (year === 2025) return 0.7;
  return 1;
}

function validateYear(year) {
  if (!Number.isInteger(year) || year < 2024 || year > 2030) {
    throw new Error(`Supported reporting years are 2024-2030: ${year}`);
  }
}

export function calculateVoyageScopeRates({ year, departurePort, arrivalPort, portTable } = {}) {
  validateYear(year);
  const table = portTable ?? loadPortIdentityTable();
  const departure = getPortIdentity(table, departurePort);
  const arrival = getPortIdentity(table, arrivalPort);
  const euEts = matrixRate([departure.euEtsStatus, arrival.euEtsStatus]);
  const euEtsSurrenderRate = surrenderRateForYear(year);

  let fuelEuScopeRate = null;
  let fuelEuReason = "NOT_APPLICABLE_BEFORE_2025";
  if (year >= 2025) {
    if ([departure.fuelEuStatus, arrival.fuelEuStatus].includes("OMR")) {
      fuelEuScopeRate = 0.5;
      fuelEuReason = "OMR_HALF_ENERGY";
    } else {
      const fuelEu = matrixRate([departure.fuelEuStatus, arrival.fuelEuStatus]);
      fuelEuScopeRate = fuelEu.rate;
      fuelEuReason = fuelEu.reason;
    }
  }

  const ruleSourceIds = [...new Set(
    [departure.ruleSourceId, arrival.ruleSourceId]
      .flatMap((value) => value.split(";"))
      .filter(Boolean),
  )];

  return Object.freeze({
    year,
    departurePort: departure,
    arrivalPort: arrival,
    euEtsScopeRate: euEts.rate,
    euEtsSurrenderRate,
    euEtsEffectiveRate: euEts.rate * euEtsSurrenderRate,
    euEtsReason: euEts.reason,
    fuelEuApplicable: year >= 2025,
    fuelEuScopeRate,
    fuelEuReason,
    ruleSourceIds: Object.freeze(ruleSourceIds),
  });
}
