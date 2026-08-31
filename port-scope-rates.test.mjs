import test from "node:test";
import assert from "node:assert/strict";
import * as portScope from "./port-scope-rates.mjs";

const EXPECTED_COLUMNS = [
  "unlocode",
  "portName",
  "countryCode",
  "territoryType",
  "territoryName",
  "euEtsStatus",
  "fuelEuStatus",
  "ruleSourceId",
  "sourceVersion",
];

test("runtime module exposes the table loader and voyage calculator", () => {
  assert.equal(typeof portScope.parsePortIdentityCsv, "function");
  assert.equal(typeof portScope.loadPortIdentityTable, "function");
  assert.equal(typeof portScope.getPortIdentity, "function");
  assert.equal(typeof portScope.calculateVoyageScopeRates, "function");
});

test("formal port table has one compact schema and no unresolved records", () => {
  const table = portScope.loadPortIdentityTable();
  assert.deepEqual(table.columns, EXPECTED_COLUMNS);
  assert.equal(table.ports.size, 17_519);

  const territoryCounts = {};

  for (const excluded of ["AUAIR", "JOAQB", "MYRAI", "THSBP", "CYNIC"]) {
    assert.equal(table.ports.has(excluded), false);
  }

  for (const row of table.ports.values()) {
    territoryCounts[row.territoryType] = (territoryCounts[row.territoryType] ?? 0) + 1;
    assert.notEqual(row.territoryType, "REVIEW_REQUIRED");
    assert.notEqual(row.euEtsStatus, "REVIEW_REQUIRED");
    assert.notEqual(row.fuelEuStatus, "REVIEW_REQUIRED");
    assert.ok(row.ruleSourceId.split(";").includes("PORT-02"));
  }

  assert.deepEqual(territoryCounts, {
    EEA_NO_IS: 821,
    EU_MEMBER: 5_651,
    EU_MEMBER_SPECIAL: 1,
    FAROE_ISLANDS: 23,
    OCT: 90,
    OMR: 124,
    SVALBARD: 4,
    THIRD_COUNTRY: 10_805,
  });
});

test("table parser rejects rows with inconsistent identity fields", () => {
  const header = EXPECTED_COLUMNS.join(",");
  const invalid = [
    "NLRTM,Rotterdam,DE,EU_MEMBER,EU member state ordinary territory,IN_SCOPE,IN_SCOPE,PORT-02;ETS-01;FEU-01,UN/LOCODE 2025-1",
    "NLRTM,Rotterdam,NL,EU_MEMBER,EU member state ordinary territory,UNKNOWN,IN_SCOPE,PORT-02;ETS-01;FEU-01,UN/LOCODE 2025-1",
  ];
  for (const row of invalid) {
    assert.throws(() => portScope.parsePortIdentityCsv(`${header}\n${row}\n`), /Invalid port identity row/);
  }
});

test("five reviewed Cyprus ports are stored as third-country ports", () => {
  const table = portScope.loadPortIdentityTable();
  for (const code of ["CYAKT", "CYDHK", "CYFMG", "CYKAR", "CYKYR"]) {
    const row = portScope.getPortIdentity(table, code);
    assert.equal(row.territoryType, "THIRD_COUNTRY");
    assert.equal(row.euEtsStatus, "THIRD_COUNTRY");
    assert.equal(row.fuelEuStatus, "THIRD_COUNTRY");
  }
});

test("unknown or malformed UN/LOCODE never falls back to third-country", () => {
  const table = portScope.loadPortIdentityTable();
  assert.throws(() => portScope.getPortIdentity(table, "CYNIC"), /Port not found/);
  assert.throws(() => portScope.getPortIdentity(table, "BAD"), /Invalid UN\/LOCODE/);
});

test("ordinary port pairs return the EU ETS and FuelEU 100/50/0 matrix", () => {
  const table = portScope.loadPortIdentityTable();
  const euEu = portScope.calculateVoyageScopeRates({ year: 2025, departurePort: "NLRTM", arrivalPort: "DEHAM", portTable: table });
  const thirdEu = portScope.calculateVoyageScopeRates({ year: 2025, departurePort: "CNSHG", arrivalPort: "NLRTM", portTable: table });
  const thirdThird = portScope.calculateVoyageScopeRates({ year: 2025, departurePort: "CNSHG", arrivalPort: "SGSIN", portTable: table });

  assert.deepEqual([euEu.euEtsScopeRate, euEu.fuelEuScopeRate], [1, 1]);
  assert.deepEqual([thirdEu.euEtsScopeRate, thirdEu.fuelEuScopeRate], [0.5, 0.5]);
  assert.deepEqual([thirdThird.euEtsScopeRate, thirdThird.fuelEuScopeRate], [0, 0]);
});

test("EU ETS annual surrender rate is separate from the territorial rate", () => {
  const table = portScope.loadPortIdentityTable();
  const expected = new Map([[2024, 0.4], [2025, 0.7], [2026, 1], [2027, 1], [2028, 1], [2029, 1], [2030, 1]]);
  for (const [year, surrenderRate] of expected) {
    const result = portScope.calculateVoyageScopeRates({ year, departurePort: "CNSHG", arrivalPort: "NLRTM", portTable: table });
    assert.equal(result.euEtsScopeRate, 0.5);
    assert.equal(result.euEtsSurrenderRate, surrenderRate);
    assert.equal(result.euEtsEffectiveRate, 0.5 * surrenderRate);
  }
});

test("FuelEU is N/A in 2024 and active from 2025", () => {
  const table = portScope.loadPortIdentityTable();
  const beforeStart = portScope.calculateVoyageScopeRates({ year: 2024, departurePort: "CNSHG", arrivalPort: "NLRTM", portTable: table });
  assert.equal(beforeStart.fuelEuApplicable, false);
  assert.equal(beforeStart.fuelEuScopeRate, null);
  assert.equal(beforeStart.fuelEuReason, "NOT_APPLICABLE_BEFORE_2025");

  const active = portScope.calculateVoyageScopeRates({ year: 2025, departurePort: "CNSHG", arrivalPort: "NLRTM", portTable: table });
  assert.equal(active.fuelEuApplicable, true);
  assert.equal(active.fuelEuScopeRate, 0.5);
});

test("FuelEU OMR half-energy rule takes priority for any OMR endpoint", () => {
  const table = portScope.loadPortIdentityTable();
  for (const [departurePort, arrivalPort] of [["NLRTM", "ESLPA"], ["CNSHG", "ESLPA"], ["PTFNC", "ESLPA"]]) {
    const result = portScope.calculateVoyageScopeRates({ year: 2026, departurePort, arrivalPort, portTable: table });
    assert.equal(result.fuelEuScopeRate, 0.5);
    assert.equal(result.fuelEuReason, "OMR_HALF_ENERGY");
  }
});

test("Norway and Iceland use the fixed legal snapshot stored in the table", () => {
  const table = portScope.loadPortIdentityTable();
  const result = portScope.calculateVoyageScopeRates({ year: 2026, departurePort: "NLRTM", arrivalPort: "NOOSL", portTable: table });
  assert.equal(result.euEtsScopeRate, 1);
  assert.equal(result.fuelEuScopeRate, 0.5);
});

test("years outside the maintained 2024-2030 snapshot are rejected", () => {
  const table = portScope.loadPortIdentityTable();
  assert.throws(
    () => portScope.calculateVoyageScopeRates({ year: 2031, departurePort: "NLRTM", arrivalPort: "DEHAM", portTable: table }),
    /Supported reporting years are 2024-2030/,
  );
});
