import test from "node:test";
import assert from "node:assert/strict";

import * as portIdentity from "./port-identity-mapping.mjs";

const { classifyPort } = portIdentity;

const port = (overrides = {}) => ({
  countryCode: "DE",
  locationCode: "HAM",
  name: "Hamburg",
  subdivision: "HH",
  functionCode: "1-345---",
  status: "AI",
  date: "0401",
  coordinates: "5333N 00959E",
  ...overrides,
});

test("ordinary EU port is in scope under both paths", () => {
  assert.deepEqual(classifyPort(port()), {
    territoryType: "EU_MEMBER",
    euEtsStatus: "IN_SCOPE",
    fuelEuStatus: "IN_SCOPE",
  });
});

test("ordinary third-country port is outside both paths", () => {
  assert.deepEqual(classifyPort(port({ countryCode: "CN", locationCode: "SHA", name: "Shanghai", subdivision: "31" })), {
    territoryType: "THIRD_COUNTRY",
    euEtsStatus: "THIRD_COUNTRY",
    fuelEuStatus: "THIRD_COUNTRY",
  });
});

test("OMR ports override country defaults and receive FuelEU OMR status", () => {
  assert.deepEqual(classifyPort(port({ countryCode: "PT", locationCode: "FNC", name: "Funchal, Madeira", subdivision: "30" })), {
    territoryType: "OMR",
    euEtsStatus: "IN_SCOPE",
    fuelEuStatus: "OMR",
  });

  assert.deepEqual(classifyPort(port({ countryCode: "ES", locationCode: "LPA", name: "Las Palmas", subdivision: "GC" })), {
    territoryType: "OMR",
    euEtsStatus: "IN_SCOPE",
    fuelEuStatus: "OMR",
  });
});

test("known Canary and Azores ports remain OMR when UN/LOCODE subdivision is blank", () => {
  const missingSubdivisionOmrPorts = [
    ["ES", "ARI", "Arguineguin"],
    ["ES", "BBJ", "Breña Baja"],
    ["ES", "CDI", "Carrizal"],
    ["ES", "FUE", "Puerto del Rosario-Fuerteventura"],
    ["ES", "HIE", "Puerto de la Estaca"],
    ["ES", "LCR", "Los Cristianos"],
    ["ES", "LES", "La Estaca"],
    ["ES", "LSI", "Los Silos"],
    ["ES", "PAF", "Pajara Fuerteventura"],
    ["ES", "QFU", "Corralejo"],
    ["ES", "QLY", "Playa Blanca"],
    ["ES", "SAT", "Salinetas"],
    ["ES", "SCT", "Santa Cruz de Tenerife"],
    ["ES", "SGT", "San Agustin"],
    ["ES", "SSG", "San Sebastian de la Gomera"],
    ["ES", "TJI", "La Tejita"],
    ["ES", "VGR", "Valle Gran Rey"],
    ["PT", "SMI", "São Miguel"],
  ];

  for (const [countryCode, locationCode, name] of missingSubdivisionOmrPorts) {
    assert.equal(classifyPort(port({ countryCode, locationCode, name, subdivision: "" })).territoryType, "OMR");
  }

});

test("OMR location overrides retain official port-authority evidence", () => {
  const canary = portIdentity.describePortIdentity(port({
    countryCode: "ES",
    locationCode: "SCT",
    name: "Santa Cruz de Tenerife",
    subdivision: "",
  }));
  const azores = portIdentity.describePortIdentity(port({
    countryCode: "PT",
    locationCode: "SMI",
    name: "São Miguel",
    subdivision: "",
  }));
  assert.ok(canary.ruleSourceIds.includes("ES-CANARY-PORTS-01"));
  assert.ok(canary.ruleSourceIds.includes("ES-TENERIFE-PORTS-01"));
  assert.ok(azores.ruleSourceIds.includes("PT-AZORES-PORTS-01"));
});

test("coordinates catch new Canary ports with incomplete subdivisions", () => {
  assert.equal(classifyPort(port({
    countryCode: "ES",
    locationCode: "NEW",
    name: "New Canary port",
    subdivision: "",
    coordinates: "2810N 01530W",
  })).territoryType, "OMR");
});

test("OCT ports do not inherit the associated member-state identity", () => {
  assert.deepEqual(classifyPort(port({ countryCode: "GL", locationCode: "GOH", name: "Nuuk" })), {
    territoryType: "OCT",
    euEtsStatus: "THIRD_COUNTRY",
    fuelEuStatus: "THIRD_COUNTRY",
  });
});

test("Svalbard and Faroe Islands remain third countries", () => {
  assert.deepEqual(classifyPort(port({ countryCode: "SJ", locationCode: "LYR", name: "Longyearbyen" })), {
    territoryType: "SVALBARD",
    euEtsStatus: "THIRD_COUNTRY",
    fuelEuStatus: "THIRD_COUNTRY",
  });
  assert.deepEqual(classifyPort(port({ countryCode: "FO", locationCode: "THO", name: "Torshavn" })), {
    territoryType: "FAROE_ISLANDS",
    euEtsStatus: "THIRD_COUNTRY",
    fuelEuStatus: "THIRD_COUNTRY",
  });
});

test("Jan Mayen is not silently classified as Svalbard", () => {
  assert.deepEqual(classifyPort(port({ countryCode: "SJ", locationCode: "JAM", name: "Jan Mayen" })), {
    territoryType: "EEA_NO_IS",
    euEtsStatus: "IN_SCOPE",
    fuelEuStatus: "THIRD_COUNTRY",
  });

  assert.throws(
    () => classifyPort(port({ countryCode: "SJ", locationCode: "NEW", name: "Unknown SJ location" })),
    /Unclassified SJ location/,
  );
});

test("Norway and Iceland split EU ETS and FuelEU identities", () => {
  for (const countryCode of ["NO", "IS"]) {
    assert.deepEqual(classifyPort(port({ countryCode, locationCode: "AAA", name: countryCode })), {
      territoryType: "EEA_NO_IS",
      euEtsStatus: "IN_SCOPE",
      fuelEuStatus: "THIRD_COUNTRY",
    });
  }
});

test("Åland is retained as a separately labelled EU special territory", () => {
  assert.deepEqual(classifyPort(port({ countryCode: "AX", locationCode: "MHQ", name: "Mariehamn" })), {
    territoryType: "EU_MEMBER_SPECIAL",
    euEtsStatus: "IN_SCOPE",
    fuelEuStatus: "IN_SCOPE",
  });
});

test("five reviewed Cyprus ports are fixed as third-country ports", () => {
  for (const locationCode of ["AKT", "DHK", "FMG", "KAR", "KYR"]) {
    assert.deepEqual(classifyPort(port({ countryCode: "CY", locationCode, name: locationCode })), {
      territoryType: "THIRD_COUNTRY",
      euEtsStatus: "THIRD_COUNTRY",
      fuelEuStatus: "THIRD_COUNTRY",
    });
  }
});

test("UN/LOCODE deletion records cannot be classified into the formal table", () => {
  assert.throws(() => classifyPort(port({ countryCode: "DE", locationCode: "OLD", change: "X" })), /Change=X/);
});

test("ordinary Republic of Cyprus port remains in scope", () => {
  assert.deepEqual(classifyPort(port({ countryCode: "CY", locationCode: "LCA", name: "Larnaca", subdivision: "03" })), {
    territoryType: "EU_MEMBER",
    euEtsStatus: "IN_SCOPE",
    fuelEuStatus: "IN_SCOPE",
  });
});

test("Åland evidence points to the 1994 accession protocol", () => {
  assert.equal(typeof portIdentity.describePortIdentity, "function");
  const result = portIdentity.describePortIdentity(port({ countryCode: "AX", locationCode: "MHQ", name: "Mariehamn" }));
  assert.ok(result.ruleSourceIds.includes("TFEU-355"));
  assert.ok(result.ruleSourceIds.includes("ALAND-ACC-P2"));
  assert.ok(result.ruleSourceUrls.some((url) => url.includes("11994N%2FPRO%2F02")));
  assert.ok(!result.ruleSourceUrls.some((url) => url.includes("12016E%2FPRO%2F02")));
});

test("Svalbard and Faroe evidence does not use the OCT annex", () => {
  assert.equal(typeof portIdentity.describePortIdentity, "function");
  const svalbard = portIdentity.describePortIdentity(port({ countryCode: "SJ", locationCode: "LYR", name: "Longyearbyen" }));
  const faroe = portIdentity.describePortIdentity(port({ countryCode: "FO", locationCode: "THO", name: "Torshavn" }));
  assert.deepEqual(svalbard.ruleSourceIds, ["EEA-PROT-40", "ETS-03", "FEU-02", "FEU-03"]);
  assert.deepEqual(faroe.ruleSourceIds, ["TFEU-355", "ETS-03", "FEU-02"]);
});

test("Jan Mayen evidence follows Norway while retaining the Svalbard exclusion source", () => {
  const janMayen = portIdentity.describePortIdentity(port({ countryCode: "SJ", locationCode: "JAM", name: "Jan Mayen" }));
  assert.deepEqual(janMayen.ruleSourceIds, [
    "PORT-02",
    "NO-JAN-MAYEN-ACT",
    "EEA-AGR-126",
    "EEA-PROT-40",
    "ETS-03",
    "FEU-02",
    "EEA-FEU-01",
  ]);
});

test("Cyprus fixed third-country evidence follows the applicable protocol", () => {
  assert.equal(typeof portIdentity.describePortIdentity, "function");
  const sba = portIdentity.describePortIdentity(port({ countryCode: "CY", locationCode: "AKT", name: "Akrotiri" }));
  const protocol10 = portIdentity.describePortIdentity(port({ countryCode: "CY", locationCode: "FMG", name: "Famagusta" }));
  assert.deepEqual(sba.ruleSourceIds, ["PORT-02", "CY-PROT-3"]);
  assert.deepEqual(protocol10.ruleSourceIds, ["PORT-02", "CY-PROT-10", "CY-PORTS-01"]);
  assert.ok(protocol10.ruleSourceUrls.some((url) => url === "https://www.cpa.gov.cy/en/closed-ports"));
});
