/**
 * Classifies one UN/LOCODE port for the first-release base territorial rules.
 *
 * This module deliberately does not evaluate vessel, route, exemption,
 * transhipment, ice-class, or Port-of-Call facts. Those are separate rules.
 */

const EU_MEMBER_CODES = new Set([
  "AT", "BE", "BG", "HR", "CY", "CZ", "DE", "DK", "EE",
  "ES", "FI", "FR", "GR", "HU", "IE", "IT", "LT", "LU",
  "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
]);

const OMR_CODES = new Set(["GF", "GP", "MQ", "YT", "RE", "MF"]);
const OCT_CODES = new Set(["GL", "PF", "NC", "BL", "PM", "WF", "TF", "AW", "BQ", "CW", "SX"]);
const OMR_LOCATION_OVERRIDES = new Set([
  "ESARI", "ESBBJ", "ESCDI", "ESFUE", "ESHIE", "ESLCR",
  "ESLES", "ESLSI", "ESPAF", "ESQFU", "ESQLY", "ESSAT",
  "ESSCT", "ESSGT", "ESSSG", "ESTJI", "ESVGR", "PTSMI",
]);
const SVALBARD_LOCATION_CODES = new Set(["BAR", "LYR", "NYA", "SVE"]);
const CYPRUS_THIRD_COUNTRY_LOCATIONS = new Set(["AKT", "DHK", "EPK", "FMG", "KAR", "KYR"]);
const CYPRUS_SBA_LOCATIONS = new Set(["AKT", "DHK", "EPK"]);
const OMR_NAMES = Object.freeze({
  GF: "French Guiana",
  GP: "Guadeloupe",
  MQ: "Martinique",
  YT: "Mayotte",
  RE: "Reunion",
  MF: "Saint Martin",
});
const OCT_NAMES = Object.freeze({
  GL: "Greenland",
  PF: "French Polynesia",
  NC: "New Caledonia",
  BL: "Saint Barthelemy",
  PM: "Saint Pierre and Miquelon",
  WF: "Wallis and Futuna",
  TF: "French Southern and Antarctic Territories",
  AW: "Aruba",
  BQ: "Bonaire, Saba and Sint Eustatius",
  CW: "Curacao",
  SX: "Sint Maarten",
});
const RULE_SOURCE_URLS = Object.freeze({
  "PORT-02": "https://opensource.unicc.org/un/unece/uncefact/vocab-locode/-/jobs/artifacts/2025-1/download?job=package-release",
  "ETS-01": "https://eur-lex.europa.eu/eli/dir/2003/87/2024-03-01/eng",
  "ETS-03": "https://climate.ec.europa.eu/document/download/31875b4f-39b9-4cde-a4e2-fbb8f65ee703_en?filename=policy_transport_shipping_gd1_maritime_en.pdf",
  "FEU-01": "https://eur-lex.europa.eu/eli/reg/2023/1805/oj/eng",
  "FEU-02": "https://transport.ec.europa.eu/document/download/d4426ccc-ef46-4292-8b6d-5bf7a620f5ba_en?filename=fueleu_guidance_document_for_shipping_companies.pdf",
  "FEU-03": "https://transport.ec.europa.eu/transport-modes/maritime/decarbonising-maritime-transport-fueleu-maritime/questions-and-answers-regulation-eu-20231805-use-renewable-and-low-carbon-fuels-maritime-transport_en",
  "EEA-ETS-01": "https://eur-lex.europa.eu/eli/dec/2024/1420/oj/eng",
  "EEA-FEU-01": "https://www.efta.int/eea-lex/32023R1805",
  "EEA-FEU-02": "https://www.sdir.no/en/news/FuelEu_delayed_in_Norway/",
  "EEA-AGR-126": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A21994A0103%2801%29",
  "EEA-PROT-40": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A21994A0103%2841%29",
  "NO-JAN-MAYEN-ACT": "https://lovdata.no/dokument/NL/lov/1930-02-27-2",
  "TFEU-349": "https://eur-lex.europa.eu/eli/treaty/tfeu_2016/art_349/oj/eng",
  "TFEU-355": "https://eur-lex.europa.eu/eli/treaty/tfeu_2016/art_355/oj/eng",
  "TFEU-ANNEX-II": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A12016E%2FTXT",
  "ALAND-ACC-P2": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A11994N%2FPRO%2F02",
  "CY-PROT-3": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A12003T%2FPRO%2F03",
  "CY-PROT-10": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A12003T%2FPRO%2F10",
  "CY-PORTS-01": "https://www.cpa.gov.cy/en/closed-ports",
  "ES-CANARY-PORTS-01": "https://www.puertoscanarios.es/puertos/",
  "ES-TENERIFE-PORTS-01": "https://www.puertosdetenerife.org/en/",
  "PT-AZORES-PORTS-01": "https://portosdosacores.pt/",
  "PT-MADEIRA-PORTS-01": "https://www.apram.pt/",
});

function normalize(value) {
  return String(value ?? "").trim().toUpperCase();
}

function parseCoordinates(value) {
  const match = normalize(value).match(/^(\d{2})(\d{2})([NS])\s+(\d{3})(\d{2})([EW])$/);
  if (!match) return null;
  const latitude = (Number(match[1]) + Number(match[2]) / 60) * (match[3] === "S" ? -1 : 1);
  const longitude = (Number(match[4]) + Number(match[5]) / 60) * (match[6] === "W" ? -1 : 1);
  return { latitude, longitude };
}

function within({ latitude, longitude }, { minLatitude, maxLatitude, minLongitude, maxLongitude }) {
  return latitude >= minLatitude && latitude <= maxLatitude
    && longitude >= minLongitude && longitude <= maxLongitude;
}

function hasOmrLocationOverride(port) {
  return OMR_LOCATION_OVERRIDES.has(`${normalize(port.countryCode)}${normalize(port.locationCode)}`);
}

function isMadeiraOrAzores(port) {
  if (normalize(port.countryCode) !== "PT") return false;
  if (["20", "30"].includes(normalize(port.subdivision)) || hasOmrLocationOverride(port)) return true;
  const coordinates = parseCoordinates(port.coordinates);
  if (!coordinates) return false;
  return within(coordinates, { minLatitude: 31, maxLatitude: 34.5, minLongitude: -18.5, maxLongitude: -14 })
    || within(coordinates, { minLatitude: 36, maxLatitude: 40.5, minLongitude: -32, maxLongitude: -23 });
}

function isCanaryIslands(port) {
  if (normalize(port.countryCode) !== "ES") return false;
  if (["GC", "TF"].includes(normalize(port.subdivision)) || hasOmrLocationOverride(port)) return true;
  const coordinates = parseCoordinates(port.coordinates);
  return coordinates !== null && within(coordinates, {
    minLatitude: 27,
    maxLatitude: 30,
    minLongitude: -19,
    maxLongitude: -12,
  });
}

function identity(territoryType, euEtsStatus, fuelEuStatus) {
  return { territoryType, euEtsStatus, fuelEuStatus };
}

function eeaNorwayIcelandResult() {
  return identity("EEA_NO_IS", "IN_SCOPE", "THIRD_COUNTRY");
}

function classifyGeography(port) {
  const countryCode = normalize(port?.countryCode);
  const locationCode = normalize(port?.locationCode);

  if (countryCode === "SJ") {
    if (locationCode === "JAM" || normalize(port?.name).includes("JAN MAYEN")) return eeaNorwayIcelandResult();
    if (SVALBARD_LOCATION_CODES.has(locationCode)) {
      return identity("SVALBARD", "THIRD_COUNTRY", "THIRD_COUNTRY");
    }
    throw new Error(`Unclassified SJ location: SJ${locationCode}`);
  }

  if (countryCode === "FO") {
    return identity("FAROE_ISLANDS", "THIRD_COUNTRY", "THIRD_COUNTRY");
  }

  if (OMR_CODES.has(countryCode) || isMadeiraOrAzores(port) || isCanaryIslands(port)) {
    return identity("OMR", "IN_SCOPE", "OMR");
  }

  if (OCT_CODES.has(countryCode)) {
    return identity("OCT", "THIRD_COUNTRY", "THIRD_COUNTRY");
  }

  if (countryCode === "NO" || countryCode === "IS") return eeaNorwayIcelandResult();

  if (countryCode === "CY" && CYPRUS_THIRD_COUNTRY_LOCATIONS.has(locationCode)) {
    return identity("THIRD_COUNTRY", "THIRD_COUNTRY", "THIRD_COUNTRY");
  }

  if (countryCode === "AX") {
    return identity("EU_MEMBER_SPECIAL", "IN_SCOPE", "IN_SCOPE");
  }

  if (EU_MEMBER_CODES.has(countryCode)) {
    return identity("EU_MEMBER", "IN_SCOPE", "IN_SCOPE");
  }

  return identity("THIRD_COUNTRY", "THIRD_COUNTRY", "THIRD_COUNTRY");
}

/**
 * @param {{countryCode:string, subdivision?:string}} port
 * @returns {{territoryType:string, euEtsStatus:string, fuelEuStatus:string}}
 */
export function classifyPort(port) {
  if (normalize(port?.change) === "X") {
    throw new Error(`UN/LOCODE Change=X record cannot enter the formal table: ${normalize(port?.countryCode)}${normalize(port?.locationCode)}`);
  }
  return classifyGeography(port ?? {});
}

function territoryName(port, territoryType) {
  const countryCode = normalize(port?.countryCode);
  const subdivision = normalize(port?.subdivision);
  if (territoryType === "OMR") {
    if (countryCode === "PT" && subdivision === "20") return "Azores";
    if (countryCode === "PT" && subdivision === "30") return "Madeira";
    if (countryCode === "PT" && normalize(port?.locationCode) === "SMI") return "Azores";
    if (countryCode === "ES") return "Canary Islands";
    return OMR_NAMES[countryCode] ?? "OMR";
  }
  if (territoryType === "OCT") return OCT_NAMES[countryCode] ?? "OCT";
  if (territoryType === "SVALBARD") return "Svalbard";
  if (territoryType === "FAROE_ISLANDS") return "Faroe Islands";
  if (territoryType === "EEA_NO_IS") {
    if (countryCode === "SJ") return "Jan Mayen";
    return countryCode === "NO" ? "Norway mainland" : "Iceland";
  }
  if (territoryType === "EU_MEMBER_SPECIAL") return "Aland Islands";
  if (territoryType === "EU_MEMBER") return "EU member state ordinary territory";
  return "Other third country or territory";
}

function ruleSourceIds(port, territoryType) {
  const countryCode = normalize(port?.countryCode);
  const locationCode = normalize(port?.locationCode);
  const subdivision = normalize(port?.subdivision);
  if (countryCode === "CY" && CYPRUS_THIRD_COUNTRY_LOCATIONS.has(locationCode)) {
    return CYPRUS_SBA_LOCATIONS.has(locationCode)
      ? ["PORT-02", "CY-PROT-3"]
      : ["PORT-02", "CY-PROT-10", "CY-PORTS-01"];
  }
  if (territoryType === "OMR" && countryCode === "ES" && !["GC", "TF"].includes(subdivision)) {
    return ["PORT-02", "TFEU-349", "ES-CANARY-PORTS-01", "ES-TENERIFE-PORTS-01", "ETS-01", "FEU-01"];
  }
  if (territoryType === "OMR" && countryCode === "PT" && !["20", "30"].includes(subdivision)) {
    const authoritySources = locationCode === "SMI"
      ? ["PT-AZORES-PORTS-01"]
      : ["PT-AZORES-PORTS-01", "PT-MADEIRA-PORTS-01"];
    return ["PORT-02", "TFEU-349", ...authoritySources, "ETS-01", "FEU-01"];
  }
  if (territoryType === "EEA_NO_IS" && countryCode === "SJ") {
    return ["PORT-02", "NO-JAN-MAYEN-ACT", "EEA-AGR-126", "EEA-PROT-40", "ETS-03", "FEU-02", "EEA-FEU-01"];
  }
  const sources = {
    EU_MEMBER: ["ETS-01", "FEU-01"],
    EU_MEMBER_SPECIAL: ["TFEU-355", "ALAND-ACC-P2", "ETS-01", "FEU-01"],
    OMR: ["TFEU-349", "ETS-01", "FEU-01"],
    OCT: ["TFEU-ANNEX-II", "ETS-01", "FEU-01"],
    SVALBARD: ["EEA-PROT-40", "ETS-03", "FEU-02", "FEU-03"],
    FAROE_ISLANDS: ["TFEU-355", "ETS-03", "FEU-02"],
    EEA_NO_IS: ["EEA-ETS-01", "EEA-FEU-01", "EEA-FEU-02"],
    THIRD_COUNTRY: ["ETS-01", "FEU-01"],
  };
  return sources[territoryType] ?? ["PORT-02"];
}

export function describePortIdentity(port) {
  const classification = classifyPort(port);
  const sourceIds = ruleSourceIds(port, classification.territoryType);
  return {
    ...classification,
    territoryName: territoryName(port, classification.territoryType),
    ruleSourceIds: sourceIds,
    ruleSourceUrls: sourceIds.map((sourceId) => RULE_SOURCE_URLS[sourceId]),
  };
}

export const mappingCategories = Object.freeze({
  EU_MEMBER: "普通欧盟成员国港口",
  EU_MEMBER_SPECIAL: "欧盟成员国特殊地区（Åland 等）",
  OMR: "欧盟最外围地区",
  OCT: "海外国家和领地",
  SVALBARD: "斯瓦尔巴",
  FAROE_ISLANDS: "法罗群岛",
  EEA_NO_IS: "挪威/冰岛（EU ETS 与 FuelEU 身份分裂）",
  THIRD_COUNTRY: "普通第三国港口",
});
