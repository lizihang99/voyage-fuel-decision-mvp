(() => {
  "use strict";

  const state = {
    candidates: [],
    result: null,
    ports: { departure: null, arrival: null },
    display: { mass: 3, energy: 3, ratio: 4, price: 2 },
    nextCandidateSerial: 1,
  };

  const $ = (id) => document.getElementById(id);
  const text = (value, fallback = "-") => value === null || value === undefined || value === "" ? fallback : String(value);
  function formatDecimalStringScaled(value, decimals, power10 = 0) {
    if (value === null || value === undefined || value === "") return "-";
    const raw = String(value).trim();
    const match = raw.match(/^([+-]?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/);
    if (!match) return raw;
    const sign = match[1] === "-" ? "-" : "";
    const digits = `${match[2]}${match[3] || ""}`;
    const exponent = Number.parseInt(match[4] || "0", 10) + power10;
    const decimalPosition = match[2].length + exponent;
    const shift = decimalPosition - digits.length + decimals;
    let scaled;
    if (shift >= 0) {
      scaled = BigInt(`${digits}${"0".repeat(shift)}`);
    } else {
      const divisor = 10n ** BigInt(-shift);
      const integerPart = BigInt(digits) / divisor;
      const remainder = BigInt(digits) % divisor;
      scaled = integerPart + (remainder * 2n >= divisor ? 1n : 0n);
    }
    const scale = 10n ** BigInt(decimals);
    let integerText;
    if (decimals > 0) {
      const whole = scaled / scale;
      const fraction = String(scaled % scale).padStart(decimals, "0");
      integerText = `${whole}.${fraction}`;
    } else {
      integerText = String(scaled);
    }
    if (sign && scaled !== 0n) return `-${integerText}`;
    return integerText;
  }
  function formatDecimalString(value, decimals) { return formatDecimalStringScaled(value, decimals, 0); }
  function formatField(value, kind, displayConfig = state.display) {
    const config = displayConfig || state.display;
    const places = {
      mass: config.mass ?? config.fuel_mass_decimals ?? 3,
      energy: config.energy ?? config.energy_decimals ?? 3,
      ratio: config.ratio ?? config.ratio_decimals ?? 4,
      scope: config.scope ?? config.scope_rate_decimals ?? 2,
      intensity: config.intensity ?? config.intensity_decimals ?? 4,
      gas: config.gas ?? config.gas_decimals ?? 6,
      price: config.price ?? config.price_decimals ?? 2,
      factor: config.factor ?? config.factor_decimals ?? 9,
    }[kind] ?? 6;
    const power10 = kind === "energy" ? -3 : (kind === "ratio" || kind === "scope" ? 2 : 0);
    const rendered = formatDecimalStringScaled(value, places, power10);
    return kind === "ratio" || kind === "scope" ? `${rendered}%` : rendered;
  }
  const number = (value, places) => formatDecimalString(value, places);
  const percent = (value) => formatField(value, "ratio");
  function negateDecimalString(value) {
    if (value === null || value === undefined || value === "") return null;
    const raw = String(value).trim();
    if (raw.startsWith("-")) return raw.slice(1);
    if (raw.startsWith("+")) return `-${raw.slice(1)}`;
    return `-${raw}`;
  }
  const esc = (value) => String(value ?? "").replace(/[&<>\"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;",
  }[char]));
  const selected = (actual, expected) => actual === expected ? " selected" : "";
  const checked = (value) => value ? " checked" : "";

  const EVIDENCE_UNITS = {
    lcv: "MJ/gFuel",
    wtT: "gCO2eq/MJ",
    E: "gCO2eq/MJ",
    eu: "gCO2eq/MJ",
    cfCO2: "gGHG/gFuel",
    cfCH4: "gGHG/gFuel",
    cfN2O: "gGHG/gFuel",
    cslip: "%",
    methaneSlipApplicable: "boolean",
    rwd: "ratio",
    eligibleBiomassFraction: "fraction",
    csfCO2: "gGHG/gFuel",
    csfCH4: "gGHG/gFuel",
    csfN2O: "gGHG/gFuel",
  };

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const body = await response.json();
    if (!response.ok) {
      const error = new Error("request failed");
      error.body = body;
      throw error;
    }
    return body;
  }

  function candidateTemplate(candidate, index) {
    const mode = candidate.candidateMode || "builtin";
    const customType = candidate.customFuelType || "non_methane";
    const methaneSlip = candidate.methaneSlipApplicable === undefined
      ? customType === "gas"
      : candidate.methaneSlipApplicable === true || candidate.methaneSlipApplicable === "true";
    const profile = candidate.customProfile || "ordinary";
    const wtTMode = candidate.wtTMode || "STATIC";
    const qualification = candidate.qualificationStatus || "NOT_DEMONSTRATED";
    const verification = candidate.verificationStatus || "ESTIMATED";
    const sourceType = candidate.sourceType || "SUPPLIER_SPEC";
    return `<article class="candidate-row" data-index="${index}" data-custom-path-id="${esc(candidate.customPathId || "")}">
      <div class="candidate-row-header">
        <h3>候选燃料 ${index + 1}</h3>
        <button type="button" class="button danger remove-candidate" aria-label="移除候选燃料 ${index + 1}">移除</button>
      </div>
      <div class="candidate-grid">
        <label>候选 ID<input data-field="candidateId" value="${esc(candidate.candidateId)}" required></label>
        <label>输入模式<select data-field="candidateMode">
          <option value="builtin"${selected(mode, "builtin")}>目录燃料</option>
          <option value="custom"${selected(mode, "custom")}>高级自定义</option>
        </select></label>
        <label class="builtin-path-field">燃料路径<select data-field="pathId" class="candidate-fuel" data-desired-path="${esc(candidate.pathId || "UCO_FAME")}"></select></label>
        <label>价格 / t<input data-field="pricePerTonne" type="number" min="0" step="any" value="${esc(candidate.pricePerTonne)}"></label>
      </div>
      <div class="candidate-grid">
        <label>最大混合比例<input data-field="maxBlendRatio" type="number" min="0" max="1" step="any" value="${esc(candidate.maxBlendRatio || "1")}"></label>
        <label>指定混合比例<input data-field="specifiedBlendRatios" type="text" inputmode="decimal" placeholder="例如 0.2, 0.4" value="${esc(candidate.specifiedBlendRatios)}"></label>
        <label>供应量 (t)<input data-field="candidateSupplyTonnes" type="number" min="0" step="any" value="${esc(candidate.candidateSupplyTonnes)}"></label>
        <label>增量预算<input data-field="incrementalBudget" type="number" min="0" step="any" value="${esc(candidate.incrementalBudget)}"></label>
      </div>
      <div class="custom-editor" hidden>
        <div class="custom-grid">
          <label>自定义燃料名称 *<input data-field="customFuelName" value="${esc(candidate.customFuelName)}" autocomplete="off"></label>
          <label>燃料用途<select data-field="customProfile">
            <option value="ordinary"${selected(profile, "ordinary")}>普通燃料</option>
            <option value="biofuel"${selected(profile, "biofuel")}>生物燃料</option>
            <option value="rfnbo"${selected(profile, "rfnbo")}>RFNBO</option>
          </select></label>
          <label>燃料形态<select data-field="customFuelType">
            <option value="non_methane"${selected(customType, "non_methane")}>非甲烷路径</option>
            <option value="gas"${selected(customType, "gas")}>气体路径</option>
          </select></label>
          <label>WtT 数据方式<select data-field="wtTMode">
            <option value="STATIC"${selected(wtTMode, "STATIC")}>直接输入 WtT</option>
            <option value="CERTIFIED"${selected(wtTMode, "CERTIFIED")}>认证 WtT</option>
            <option value="BIO_E"${selected(wtTMode, "BIO_E")}>生物燃料 E 公式</option>
            <option value="RFNBO_E"${selected(wtTMode, "RFNBO_E")}>RFNBO E - eu 公式</option>
          </select></label>
        </div>
        <div class="custom-grid">
          <label>LCV (MJ/gFuel) *<input data-field="lcv" type="number" min="0" step="any" value="${esc(candidate.lcv)}"></label>
          <label data-custom-block="wtT">WtT (gCO2eq/MJ) *<input data-field="wtT" type="number" step="any" value="${esc(candidate.wtT)}"></label>
          <label data-custom-block="E">E (gCO2eq/MJ) *<input data-field="e" type="number" step="any" value="${esc(candidate.e)}"></label>
          <label data-custom-block="eu">eu (gCO2eq/MJ) *<input data-field="eu" type="number" step="any" value="${esc(candidate.eu)}"></label>
        </div>
        <div class="custom-grid">
          <label>CO2 因子 (gGHG/gFuel) *<input data-field="cfCO2" type="number" step="any" value="${esc(candidate.cfCO2)}"></label>
          <div class="factor-input">
            <label for="candidate-${index}-cfCH4">CH4 因子 (gGHG/gFuel) *</label>
            <input id="candidate-${index}-cfCH4" data-field="cfCH4" type="number" step="any" value="${esc(candidate.cfCH4)}">
            <label class="inline-check"><input data-field="cfCH4ZeroEstimate" type="checkbox"${checked(candidate.cfCH4ZeroEstimate)}>按 0 估算</label>
          </div>
          <div class="factor-input">
            <label for="candidate-${index}-cfN2O">N2O 因子 (gGHG/gFuel) *</label>
            <input id="candidate-${index}-cfN2O" data-field="cfN2O" type="number" step="any" value="${esc(candidate.cfN2O)}">
            <label class="inline-check"><input data-field="cfN2OZeroEstimate" type="checkbox"${checked(candidate.cfN2OZeroEstimate)}>按 0 估算</label>
          </div>
          <label class="qualification-field">资格状态<select data-field="qualificationStatus">
            <option value="NOT_DEMONSTRATED"${selected(qualification, "NOT_DEMONSTRATED")}>未证明</option>
            <option value="ASSUMED_ELIGIBLE"${selected(qualification, "ASSUMED_ELIGIBLE")}>假设合格</option>
            <option value="VERIFIED_ELIGIBLE"${selected(qualification, "VERIFIED_ELIGIBLE")}>已核验合格</option>
          </select></label>
        </div>
        <div class="custom-grid qualification-details">
          <label data-custom-block="eligibleBiomassFraction">生物质质量分数<input data-field="eligibleBiomassFraction" type="number" min="0" max="1" step="any" value="${esc(candidate.eligibleBiomassFraction)}"></label>
          <label data-custom-block="rwd">RWD（规则）<input data-field="rwd" type="text" value="${esc(candidate.rwd || "1")}" readonly></label>
          <div class="gas-fields" hidden>
            <label>甲烷滑移适用<select data-field="methaneSlipApplicable">
              <option value="false"${selected(String(methaneSlip), "false")}>不适用</option>
              <option value="true"${selected(String(methaneSlip), "true")}>适用</option>
            </select></label>
            <label data-gas-field="cslip">Cslip (%) *<input data-field="cslip" type="number" min="0" max="100" step="any" value="${esc(candidate.cslip && candidate.cslip !== "NA" ? candidate.cslip : "")}"></label>
            <div class="slip-factor-fields" hidden>
              <label>滑移 CO2 因子<input data-field="csfCO2" type="number" step="any" value="${esc(candidate.csfCO2)}"></label>
              <label>滑移 CH4 因子<input data-field="csfCH4" type="number" step="any" value="${esc(candidate.csfCH4)}"></label>
              <label>滑移 N2O 因子<input data-field="csfN2O" type="number" step="any" value="${esc(candidate.csfN2O)}"></label>
            </div>
          </div>
        </div>
        <div class="custom-grid evidence-fields">
          <label>来源编号 *<input data-field="sourceId" value="${esc(candidate.sourceId)}" placeholder="例如 SUP-123"></label>
          <label>来源类型<select data-field="sourceType">
            <option value="SUPPLIER_SPEC"${selected(sourceType, "SUPPLIER_SPEC")}>供应商规格</option>
            <option value="LAB_CERTIFICATE"${selected(sourceType, "LAB_CERTIFICATE")}>实验室/认证</option>
            <option value="MASS_BALANCE_CERTIFICATE"${selected(sourceType, "MASS_BALANCE_CERTIFICATE")}>质量平衡证书</option>
            <option value="OTHER"${selected(sourceType, "OTHER")}>其他</option>
          </select></label>
          <label>证据状态<select data-field="verificationStatus">
            <option value="ESTIMATED"${selected(verification, "ESTIMATED")}>估算</option>
            <option value="VERIFIED"${selected(verification, "VERIFIED")}>已核验</option>
            <option value="ASSUMED"${selected(verification, "ASSUMED")}>假设</option>
            <option value="RC"${selected(verification, "RC")}>认可计算</option>
          </select></label>
        </div>
        <p class="custom-warning" data-field="rfnbo-warning" hidden>RFNBO 资格未确认：页面会按普通 WtT 输入，不使用 RFNBO 奖励。</p>
        <p class="custom-warning" data-field="certified-warning" hidden>认证 WtT 只有在证据状态为“已核验”时才可作为核验结果；当前仍按估算状态提交。</p>
        <p class="custom-warning" data-field="custom-evidence-note">缺少因子、单位或来源证据时，该候选会保留为阻断状态。</p>
      </div>
      <div class="candidate-options">
        <label><input data-field="candidateAllowsPureUse" type="checkbox"${checked(candidate.candidateAllowsPureUse)}>允许纯用 (B100)</label>
        <label class="compliance-value-field">合规改善价值<input data-field="complianceImprovementValue" type="number" min="0" step="any" value="${esc(candidate.complianceImprovementValue)}"></label>
        <span class="field-error" data-candidate-error></span>
      </div>
    </article>`;
  }

  function field(row, name) { return row.querySelector(`[data-field="${name}"]`); }
  function fieldValue(row, name, fallback = "") { const target = field(row, name); return target ? target.value : fallback; }
  function customPathId(seed, index) {
    const slug = String(seed || "").trim().toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    return `CUSTOM_${slug || `FUEL_${index + 1}`}`;
  }
  function isEligible(qualification) { return qualification === "ASSUMED_ELIGIBLE" || qualification === "VERIFIED_ELIGIBLE"; }

  function syncBaselineCustomEditor() {
    const custom = $("baseline-mode")?.value === "custom";
    const editor = $("baseline-custom-editor");
    const builtin = $("baseline-fuel-label");
    if (editor) editor.hidden = !custom;
    if (builtin) builtin.hidden = custom;
    if (!editor || !custom) return;
    const profile = fieldValue(editor, "baselineCustomProfile", "ordinary");
    const qualification = fieldValue(editor, "baselineQualificationStatus", "NOT_DEMONSTRATED");
    const eligible = isEligible(qualification);
    const modeField = field(editor, "baselineWtTMode");
    let mode = fieldValue(editor, "baselineWtTMode", "STATIC");
    const blockedFormula = (mode === "BIO_E" && profile !== "biofuel") || (mode === "RFNBO_E" && (profile !== "rfnbo" || !eligible));
    if (blockedFormula) {
      mode = "STATIC";
      if (modeField) modeField.value = mode;
    }
    const warning = field(editor, "baseline-rfnbo-warning");
    if (warning) warning.hidden = !(profile === "rfnbo" && blockedFormula);
    const qualificationLabel = editor.querySelector(".baseline-qualification-field");
    if (qualificationLabel) qualificationLabel.hidden = profile === "ordinary";
    editor.querySelectorAll("[data-baseline-block=wtT]").forEach((label) => { label.hidden = mode === "BIO_E" || mode === "RFNBO_E"; });
    editor.querySelectorAll("[data-baseline-block=E]").forEach((label) => { label.hidden = mode !== "BIO_E" && mode !== "RFNBO_E"; });
    editor.querySelectorAll("[data-baseline-block=eu]").forEach((label) => { label.hidden = mode !== "RFNBO_E"; });
    editor.querySelectorAll("[data-baseline-block=eligibleBiomassFraction]").forEach((label) => { label.hidden = profile !== "biofuel" || !eligible; });
    const methanePath = fieldValue(editor, "baselineCustomFuelType", "non_methane") === "gas";
    const methaneField = field(editor, "baselineMethaneSlipApplicable");
    if (methaneField && !methanePath) methaneField.value = "false";
    const methane = methanePath && fieldValue(editor, "baselineMethaneSlipApplicable", "false") === "true";
    const gasFields = editor.querySelector(".baseline-gas-fields");
    if (gasFields) gasFields.hidden = !methanePath;
    const cslip = field(editor, "baselineCslip");
    if (cslip) cslip.required = methane;
    ["baselineCsfCO2", "baselineCsfCH4", "baselineCsfN2O"].forEach((name) => { const input = field(editor, name); if (input) input.required = methane && cslip && Number(cslip.value || 0) > 0; });
    const rwd = field(editor, "baselineRwd");
    if (rwd) rwd.value = profile === "rfnbo" && eligible ? "2" : "1";
    const wtT = field(editor, "baselineWtT");
    const e = field(editor, "baselineE");
    const eu = field(editor, "baselineEu");
    if (wtT) wtT.required = mode === "STATIC" || mode === "CERTIFIED";
    if (e) e.required = mode === "BIO_E" || mode === "RFNBO_E";
    if (eu) eu.required = mode === "RFNBO_E";
    const fraction = field(editor, "baselineEligibleBiomassFraction");
    if (fraction) fraction.required = profile === "biofuel" && eligible;
    syncZeroEstimate(editor, "baselineCfCH4", "baselineCfCH4ZeroEstimate");
    syncZeroEstimate(editor, "baselineCfN2O", "baselineCfN2OZeroEstimate");
  }

  function baselineCustomPayload() {
    const editor = $("baseline-custom-editor");
    const profile = fieldValue(editor, "baselineCustomProfile", "ordinary");
    const qualification = fieldValue(editor, "baselineQualificationStatus", "NOT_DEMONSTRATED");
    const eligible = isEligible(qualification);
    const requestedMode = fieldValue(editor, "baselineWtTMode", "STATIC");
    const wtTMode = requestedMode === "BIO_E" && profile === "biofuel"
      ? "BIO_E" : requestedMode === "RFNBO_E" && profile === "rfnbo" && eligible
        ? "RFNBO_E" : requestedMode === "CERTIFIED" ? "CERTIFIED" : "STATIC";
    const gas = fieldValue(editor, "baselineCustomFuelType", "non_methane") === "gas";
    const methane = gas && fieldValue(editor, "baselineMethaneSlipApplicable", "false") === "true";
    const cslip = methane ? fieldValue(editor, "baselineCslip") || "" : "NA";
    const requiredFields = ["lcv", wtTMode === "BIO_E" || wtTMode === "RFNBO_E" ? "E" : "wtT", ...(wtTMode === "RFNBO_E" ? ["eu"] : []), "cfCO2", "cfCH4", "cfN2O", "cslip", "methaneSlipApplicable", "rwd", "eligibleBiomassFraction"];
    if (methane && Number(cslip) > 0) requiredFields.push("csfCO2", "csfCH4", "csfN2O");
    const baseline = {
      custom: true,
      pathId: "CUSTOM_BASELINE",
      customPathId: "CUSTOM_BASELINE",
      equipmentId: gas ? "CUSTOM_GAS" : "CUSTOM_NON_METHANE",
      customFuelName: fieldValue(editor, "baselineCustomFuelName").trim(),
      lcv: fieldValue(editor, "baselineLcv"),
      wtTMode,
      wtT: fieldValue(editor, "baselineWtT"),
      E: fieldValue(editor, "baselineE"),
      eu: fieldValue(editor, "baselineEu"),
      cfCO2: fieldValue(editor, "baselineCfCO2"),
      cfCH4: field(editor, "baselineCfCH4ZeroEstimate")?.checked ? "0" : fieldValue(editor, "baselineCfCH4"),
      cfN2O: field(editor, "baselineCfN2OZeroEstimate")?.checked ? "0" : fieldValue(editor, "baselineCfN2O"),
      cslip,
      methaneSlipApplicable: methane,
      csfCO2: fieldValue(editor, "baselineCsfCO2"),
      csfCH4: fieldValue(editor, "baselineCsfCH4"),
      csfN2O: fieldValue(editor, "baselineCsfN2O"),
      rwd: profile === "rfnbo" && eligible ? "2" : "1",
      eligibleBiomassFraction: profile === "biofuel" && eligible ? fieldValue(editor, "baselineEligibleBiomassFraction") : "0",
      qualificationStatus: qualification,
      sourceId: fieldValue(editor, "baselineSourceId").trim(),
      sourceType: fieldValue(editor, "baselineSourceType", "SUPPLIER_SPEC"),
      verificationStatus: fieldValue(editor, "baselineVerificationStatus", "ESTIMATED"),
    };
    baseline.sourceEvidence = evidenceRecords(baseline, [...new Set(requiredFields)]);
    return baseline;
  }

  function readBaseline() {
    const custom = $("baseline-mode")?.value === "custom";
    return custom ? { ...baselineCustomPayload(), massTonnes: $("baseline-mass").value, pricePerTonne: $("baseline-price").value || null } : { pathId: $("baseline-fuel").value, massTonnes: $("baseline-mass").value, pricePerTonne: $("baseline-price").value || null };
  }

  function syncZeroEstimate(row, factorName, checkboxName) {
    const input = field(row, factorName);
    const checkbox = field(row, checkboxName);
    if (!input || !checkbox) return;
    input.disabled = checkbox.checked;
    input.required = !checkbox.checked;
    if (checkbox.checked) input.value = "0";
  }

  function syncCustomRow(row) {
    const custom = fieldValue(row, "candidateMode") === "custom";
    const editor = row.querySelector(".custom-editor");
    const builtinPath = row.querySelector(".builtin-path-field");
    if (editor) editor.hidden = !custom;
    if (builtinPath) builtinPath.hidden = custom;
    if (!custom) return;

    const profile = fieldValue(row, "customProfile", "ordinary");
    const qualification = fieldValue(row, "qualificationStatus", "NOT_DEMONSTRATED");
    const eligible = isEligible(qualification);
    const wtTModeField = field(row, "wtTMode");
    let mode = fieldValue(row, "wtTMode", "STATIC");
    const profileMatches = mode === "BIO_E" && profile === "biofuel" || mode === "RFNBO_E" && profile === "rfnbo";
    const blockedFormula = (mode === "BIO_E" && profile !== "biofuel") || (mode === "RFNBO_E" && (!profileMatches || !eligible));
    if (blockedFormula) {
      if (wtTModeField) wtTModeField.value = "STATIC";
      mode = "STATIC";
    }
    const warning = row.querySelector('[data-field="rfnbo-warning"]');
    if (warning) warning.hidden = !(profile === "rfnbo" && blockedFormula);
    const verification = fieldValue(row, "verificationStatus", "ESTIMATED").toUpperCase();
    const certifiedWarning = row.querySelector('[data-field="certified-warning"]');
    if (certifiedWarning) certifiedWarning.hidden = !(mode === "CERTIFIED" && verification !== "VERIFIED");

    const qualificationLabel = row.querySelector(".qualification-field");
    if (qualificationLabel) qualificationLabel.hidden = profile === "ordinary";
    const customName = field(row, "customFuelName");
    if (customName) customName.required = custom;
    const wtTLabel = row.querySelector('[data-custom-block="wtT"]');
    const eLabel = row.querySelector('[data-custom-block="E"]');
    const euLabel = row.querySelector('[data-custom-block="eu"]');
    if (wtTLabel) wtTLabel.hidden = mode === "BIO_E" || mode === "RFNBO_E";
    if (eLabel) eLabel.hidden = mode !== "BIO_E" && mode !== "RFNBO_E";
    if (euLabel) euLabel.hidden = mode !== "RFNBO_E";
    const biomass = row.querySelector('[data-custom-block="eligibleBiomassFraction"]');
    if (biomass) biomass.hidden = profile !== "biofuel" || !eligible;
    const rwdLabel = row.querySelector('[data-custom-block="rwd"]');
    if (rwdLabel) rwdLabel.hidden = profile !== "rfnbo" || !eligible;

    const rwd = field(row, "rwd");
    if (rwd) rwd.value = profile === "rfnbo" && eligible ? "2" : "1";

    const gas = fieldValue(row, "customFuelType", "non_methane") === "gas";
    const methane = gas && fieldValue(row, "methaneSlipApplicable", "false") === "true";
    const gasFields = row.querySelector(".gas-fields");
    if (gasFields) gasFields.hidden = !gas;
    const cslipLabel = row.querySelector('[data-gas-field="cslip"]');
    if (cslipLabel) cslipLabel.hidden = !methane;
    const methaneField = field(row, "methaneSlipApplicable");
    if (methaneField) methaneField.required = gas;
    const cslip = field(row, "cslip");
    if (cslip) cslip.required = methane;
    const slipFactors = row.querySelector(".slip-factor-fields");
    const slipValue = cslip && cslip.value !== "" ? Number(cslip.value) : 0;
    const hasSlip = methane && Number.isFinite(slipValue) && slipValue > 0;
    if (slipFactors) slipFactors.hidden = !hasSlip;
    ["csfCO2", "csfCH4", "csfN2O"].forEach((name) => {
      const input = field(row, name);
      if (input) input.required = hasSlip;
    });

    syncZeroEstimate(row, "cfCH4", "cfCH4ZeroEstimate");
    syncZeroEstimate(row, "cfN2O", "cfN2OZeroEstimate");
    const wtT = field(row, "wtT");
    const e = field(row, "e");
    const eu = field(row, "eu");
    if (wtT) wtT.required = mode === "STATIC" || mode === "CERTIFIED";
    if (e) e.required = mode === "BIO_E" || mode === "RFNBO_E";
    if (eu) eu.required = mode === "RFNBO_E";
    const fraction = field(row, "eligibleBiomassFraction");
    if (fraction) fraction.required = profile === "biofuel" && eligible;
  }

  function evidenceRecords(candidate, requiredFields) {
    const sourceId = String(candidate.sourceId || "").trim();
    const sourceType = String(candidate.sourceType || "SUPPLIER_SPEC").trim();
    const verification = String(candidate.verificationStatus || "ESTIMATED").trim().toUpperCase();
    const records = {};
    requiredFields.forEach((fieldName) => {
      const estimated = fieldName === "cfCH4" && candidate.cfCH4ZeroEstimate || fieldName === "cfN2O" && candidate.cfN2OZeroEstimate;
      records[fieldName] = [{ sourceId, sourceType, unit: EVIDENCE_UNITS[fieldName], verificationStatus: estimated ? "ESTIMATED" : verification }];
    });
    return records;
  }

  function readCandidates() {
    return [...document.querySelectorAll(".candidate-row")].map((row, index) => {
      const common = {
        candidateId: fieldValue(row, "candidateId").trim(),
        candidateMode: fieldValue(row, "candidateMode", "builtin"),
        customPathId: row.dataset.customPathId || "",
        pricePerTonne: fieldValue(row, "pricePerTonne") || null,
        specifiedBlendRatios: fieldValue(row, "specifiedBlendRatios").split(",").map((value) => value.trim()).filter(Boolean),
        maxBlendRatio: fieldValue(row, "maxBlendRatio") || "1",
        candidateAllowsPureUse: Boolean(field(row, "candidateAllowsPureUse")?.checked),
        candidateSupplyTonnes: fieldValue(row, "candidateSupplyTonnes") || null,
        incrementalBudget: fieldValue(row, "incrementalBudget") || null,
        complianceImprovementValue: fieldValue(row, "complianceImprovementValue") || null,
      };
      if (fieldValue(row, "candidateMode") !== "custom") return { ...common, pathId: fieldValue(row, "pathId") };

      const profile = fieldValue(row, "customProfile", "ordinary");
      const qualification = fieldValue(row, "qualificationStatus", "NOT_DEMONSTRATED");
      const eligible = isEligible(qualification);
      const requestedMode = fieldValue(row, "wtTMode", "STATIC");
      const safeMode = requestedMode === "BIO_E" && profile === "biofuel"
        ? "BIO_E"
        : requestedMode === "RFNBO_E" && profile === "rfnbo" && eligible
          ? "RFNBO_E"
          : requestedMode === "CERTIFIED" ? "CERTIFIED" : "STATIC";
      const methanePath = fieldValue(row, "customFuelType", "non_methane") === "gas";
      const methane = methanePath && fieldValue(row, "methaneSlipApplicable", "false") === "true";
      const cslip = methane ? fieldValue(row, "cslip") || "" : "NA";
      const requiredFields = [
        "lcv",
        safeMode === "RFNBO_E" || safeMode === "BIO_E" ? "E" : "wtT",
        ...(safeMode === "RFNBO_E" ? ["eu"] : []),
        "cfCO2", "cfCH4", "cfN2O", "cslip", "methaneSlipApplicable", "rwd", "eligibleBiomassFraction",
      ];
      if (methane && Number(cslip) > 0) requiredFields.push("csfCO2", "csfCH4", "csfN2O");
      const stablePathId = row.dataset.customPathId || customPathId(fieldValue(row, "candidateId"), index);
      row.dataset.customPathId = stablePathId;
      const custom = {
        ...common,
        custom: true,
        customFuelName: fieldValue(row, "customFuelName").trim(),
        customProfile: profile,
        customFuelType: fieldValue(row, "customFuelType", "non_methane"),
        cfCH4ZeroEstimate: Boolean(field(row, "cfCH4ZeroEstimate")?.checked),
        cfN2OZeroEstimate: Boolean(field(row, "cfN2OZeroEstimate")?.checked),
        pathId: stablePathId,
        customPathId: stablePathId,
        equipmentId: methanePath ? "CUSTOM_GAS" : "CUSTOM_NON_METHANE",
        lcv: fieldValue(row, "lcv"),
        wtTMode: safeMode,
        wtT: fieldValue(row, "wtT"),
        E: fieldValue(row, "e"),
        eu: fieldValue(row, "eu"),
        cfCO2: fieldValue(row, "cfCO2"),
        cfCH4: field(row, "cfCH4ZeroEstimate")?.checked ? "0" : fieldValue(row, "cfCH4"),
        cfN2O: field(row, "cfN2OZeroEstimate")?.checked ? "0" : fieldValue(row, "cfN2O"),
        cslip,
        methaneSlipApplicable: methane,
        csfCO2: fieldValue(row, "csfCO2"),
        csfCH4: fieldValue(row, "csfCH4"),
        csfN2O: fieldValue(row, "csfN2O"),
        rwd: profile === "rfnbo" && eligible ? fieldValue(row, "rwd") || "1" : "1",
        eligibleBiomassFraction: profile === "biofuel" && eligible ? fieldValue(row, "eligibleBiomassFraction") : "0",
        qualificationStatus: qualification,
        sourceId: fieldValue(row, "sourceId").trim(),
        sourceType: fieldValue(row, "sourceType", "SUPPLIER_SPEC"),
        verificationStatus: fieldValue(row, "verificationStatus", "ESTIMATED"),
      };
      custom.sourceEvidence = evidenceRecords(custom, [...new Set(requiredFields)]);
      return custom;
    });
  }

  async function loadFuels() {
    const data = await fetchJson("/api/fuels");
    document.querySelectorAll("select.candidate-fuel, #baseline-fuel").forEach((select) => {
      const current = select.value || select.dataset.desiredPath || (select.id === "baseline-fuel" ? "MDO" : "UCO_FAME");
      select.innerHTML = data.pathIds.map((id) => `<option value="${esc(id)}">${esc(id)}</option>`).join("");
      if (data.pathIds.includes(current)) select.value = current;
    });
    document.querySelectorAll(".candidate-row").forEach(syncCustomRow);
  }
  function renderCandidates() {
    $("candidate-collection").innerHTML = state.candidates.map(candidateTemplate).join("");
    document.querySelectorAll(".candidate-row").forEach(syncCustomRow);
    loadFuels().catch(() => {});
  }
  function addCandidate() {
    if (document.querySelectorAll(".candidate-row").length) state.candidates = readCandidates();
    const existingIds = new Set(state.candidates.map((candidate) => candidate.candidateId));
    let serial = state.nextCandidateSerial;
    while (existingIds.has(`candidate-${serial}`)) serial += 1;
    state.nextCandidateSerial = serial + 1;
    state.candidates.push({
      candidateId: `candidate-${serial}`,
      customPathId: `CUSTOM_FUEL_${serial}`,
      candidateMode: "builtin",
      pathId: "UCO_FAME",
      pricePerTonne: "",
      maxBlendRatio: "1",
      specifiedBlendRatios: "0.2",
      candidateSupplyTonnes: "",
      incrementalBudget: "",
      complianceImprovementValue: "",
      candidateAllowsPureUse: false,
      customFuelName: `自定义燃料 ${serial}`,
      customProfile: "ordinary",
      customFuelType: "non_methane",
      methaneSlipApplicable: false,
      wtTMode: "STATIC",
      lcv: "0.040",
      wtT: "100",
      e: "",
      eu: "",
      cfCO2: "3.000",
      cfCH4: "0",
      cfN2O: "0",
      cfCH4ZeroEstimate: false,
      cfN2OZeroEstimate: false,
      qualificationStatus: "NOT_DEMONSTRATED",
      eligibleBiomassFraction: "0",
      rwd: "1",
      cslip: "NA",
      csfCO2: "",
      csfCH4: "",
      csfN2O: "",
      sourceId: "UI_DEFAULT_ESTIMATE",
      sourceType: "SUPPLIER_SPEC",
      verificationStatus: "ESTIMATED",
    });
    renderCandidates();
  }

  function payload() {
    return {
      reportYear: Number($("report-year").value),
      departurePort: state.ports.departure || $("departure-port-search").value.trim(),
      arrivalPort: state.ports.arrival || $("arrival-port-search").value.trim(),
      adjacentValidPortOfCallConfirmed: $("adjacent-port-confirmation").checked,
      currency: $("case-currency").value,
      baseline: readBaseline(),
      euaPricePerTCO2e: $("eua-price").value || null,
      candidates: readCandidates(),
    };
  }

  function issueIdentity(issue) { return [issue.code, issue.scope, issue.field, issue.candidate_id, issue.scenario_id, issue.component, issue.blocking].map((value) => String(value ?? "")).join("\u001f"); }
  function uniqueIssues(issues = []) { const seen = new Set(); return issues.filter((issue) => { const identity = issueIdentity(issue); if (seen.has(identity)) return false; seen.add(identity); return true; }); }
  function issueMarkup(issue) { const scope = issue.scope === "CANDIDATE" ? "candidate" : "case"; return `<div class="issue ${scope}"><strong>${esc(issue.code)}</strong> <span>${esc(issue.message)}</span><small>字段: ${esc(issue.field)}${issue.candidate_id ? ` · 候选: ${esc(issue.candidate_id)}` : ""}${issue.blocking ? " · 阻断" : ""}</small></div>`; }
  function renderIssues(issues = []) {
    const normalized = uniqueIssues(issues);
    $("case-errors").innerHTML = normalized.filter((issue) => issue.scope === "CASE").map(issueMarkup).join("");
    $("result-issues").innerHTML = normalized.filter((issue) => issue.scope !== "CASE").map(issueMarkup).join("");
    document.querySelectorAll("[data-candidate-error]").forEach((el) => { el.textContent = ""; });
    normalized.filter((issue) => issue.scope === "CANDIDATE").forEach((issue) => {
      const index = (issue.field.match(/^candidates\[(\d+)\]/) || [])[1];
      let target = index === undefined ? null : document.querySelectorAll("[data-candidate-error]")[Number(index)];
      if (!target && issue.candidate_id) target = [...document.querySelectorAll(".candidate-row")].find((row) => row.querySelector('[data-field="candidateId"]')?.value.trim() === issue.candidate_id)?.querySelector("[data-candidate-error]") || null;
      if (target) target.textContent = `${issue.code}: ${issue.message}`;
    });
  }
  function clearResults() {
    state.result = null;
    $("result-run-status").textContent = "计算失败 · 未生成结果";
    $("result-run-status").classList.add("muted");
    $("result-boundary-summary").textContent = "本次计算未生成结果，请先处理问题后重新提交。";
    $("overview-metrics").innerHTML = "<p class=\"empty-state\">没有可呈现的基准结果。</p>";
    $("port-identity-details").innerHTML = "<h3>港口范围与制度身份</h3><p class=\"empty-state\">暂无港口结果。</p>";
    $("ets-fueleu-detail").innerHTML = "<h3>基准排放与 FuelEU</h3><p class=\"empty-state\">暂无排放结果。</p>";
    $("new-energy-decision-summary").innerHTML = "<h3>新能源决策摘要</h3><p class=\"empty-state\">暂无新能源决策结果。</p>";
    $("economics-summary").innerHTML = "<h3>案例经济结果</h3><p class=\"empty-state\">暂无案例经济结果。</p>";
    $("conditional-recommendations").innerHTML = "<h3>条件式建议</h3><p class=\"empty-state\">暂无建议。</p>";
    $("scenario-comparison-table").querySelector("tbody").innerHTML = '<tr><td colspan="26" class="empty-state">暂无场景。</td></tr>';
    $("scenario-detail-table").innerHTML = "";
    $("thresholds-content").innerHTML = '<p class="empty-state">暂无约束阈值。</p>';
    $("calculation-basis").innerHTML = '<p class="empty-state">暂无计算依据。</p>';
  }
  function scenarioMap(result) {
    return new Map((result.scenarios || []).map((row) => [row.scenario_id, row]));
  }
  function deltaValue(row, metric) {
    return row?.deltas?.[metric]?.delta ?? null;
  }
  function renderNewEnergyDecisionSummary(result) {
    const summary = result.decision_summary;
    if (!summary) {
      $("new-energy-decision-summary").innerHTML = "<h3>新能源决策摘要</h3><p class=\"empty-state\">暂无新能源决策结果。</p>";
      return;
    }
    const scenarioDeltas = summary.scenario_deltas || {};
    const rows = scenarioMap(result);
    const recommendations = [
      ["当前模型最低成本", summary.cost_min_scenario_id, "CURRENT_MODEL_COST_MIN"],
      ["FuelEU 目标下最低成本", summary.target_min_cost_scenario_id, "TARGET_MIN_COST"],
      ["最大合规改善", summary.max_improvement_scenario_id, "MAX_COMPLIANCE_IMPROVEMENT"],
    ];
    const recommendationByScenario = new Map((result.recommendations || []).filter((item) => item.scenario_id).map((item) => [item.scenario_id, item]));
    const blocks = recommendations.map(([label, scenarioId, type]) => {
      const row = scenarioId ? rows.get(scenarioId) : null;
      const recommendation = scenarioId ? recommendationByScenario.get(scenarioId) : (result.recommendations || []).find((item) => item.recommendation_id.startsWith(`${type}:`));
      if (!row) {
        return `<div class="decision-item unavailable"><strong>${label}</strong><span>暂无可用方案 · ${esc(recommendation?.reason || "后端未提供可用场景")}</span><small>假设: ${esc((recommendation?.assumptions || []).join(", ") || "-")}</small></div>`;
      }
      const scenario = row.result || {};
      const deltas = scenarioDeltas[row.scenario_id] || row.deltas || {};
      const fuelCostDelta = deltas.fuel_cost?.delta ?? deltaValue(row, "fuel_cost");
      const euaCostDelta = deltas.eua_cost?.delta ?? deltaValue(row, "eua_cost");
      const modelCostDelta = deltas.model_cost?.delta ?? deltaValue(row, "model_cost");
      return `<div class="decision-item">
        <strong>${label}</strong><span>场景 ${esc(row.scenario_id)} · ${esc(row.candidate_id || "基准")}</span>
        <div class="decision-metrics">
          <dl><dt>推荐新能源用量</dt><dd>${formatField(scenario.candidate_mass_tonnes, "mass")}</dd></dl>
          <dl><dt>推荐混兑比例</dt><dd>${percent(scenario.ratio)}</dd></dl>
          <dl><dt>新增燃料成本</dt><dd>${number(fuelCostDelta, state.display.price)}</dd></dl>
          <dl><dt>EU ETS 成本节省</dt><dd>${number(negateDecimalString(euaCostDelta), state.display.price)}</dd></dl>
          <dl><dt>净成本变化</dt><dd>${number(modelCostDelta, state.display.price)}</dd></dl>
          <dl><dt>FuelEU GHGI 变化</dt><dd>${formatField(deltas.fueleu_ghgi_actual_g_per_mj?.delta ?? deltaValue(row, "fueleu_ghgi_actual_g_per_mj"), "intensity")}</dd></dl>
          <dl><dt>FuelEU 余额变化</dt><dd>${formatField(deltas.fueleu_compliance_balance_t?.delta ?? deltaValue(row, "fueleu_compliance_balance_t"), "gas")}</dd></dl>
        </div>
        <small>执行状态: EXECUTION_CONDITIONS_PENDING</small>
      </div>`;
    }).join("");
    $("new-energy-decision-summary").innerHTML = `<h3>新能源决策摘要</h3><p class="boundary-note">以下结果复用现有场景计算，FuelEU 金额为航次级指示性估算，不构成年度罚款或采购结论。</p><div class="decision-list">${blocks}</div>`;
  }
  function factorEvidenceValue(factor, trace, fieldName) {
    const values = {
      lcv: factor.lcv_mj_per_g,
      wtT: factor.wt_t_g_per_mj,
      E: factor.e_g_per_mj,
      eu: factor.eu_g_per_mj,
      cfCO2: factor.cf_co2_g_per_g,
      cfCH4: factor.cf_ch4_g_per_g,
      cfN2O: factor.cf_n2o_g_per_g,
      cslip: factor.cslip_percent,
      methaneSlipApplicable: factor.methane_slip_applicable,
      rwd: factor.rwd,
      eligibleBiomassFraction: trace.eligible_biomass_fraction,
      csfCO2: factor.csf_co2_g_per_g,
      csfCH4: factor.csf_ch4_g_per_g,
      csfN2O: factor.csf_n2o_g_per_g,
    };
    return text(values[fieldName]);
  }

  function renderResults(result) {
    const baseline = result.baseline_scenario;
    $("result-run-status").textContent = baseline ? "已完成 · 原始结果保留" : "存在阻断问题";
    $("result-run-status").classList.toggle("muted", !baseline);
    $("result-boundary-summary").textContent = baseline ? `${result.report_year} · ${result.departure_port} → ${result.arrival_port} · ${result.currency} · 结果为航次级 FuelEU / EU ETS 估算，不构成年度罚款或采购建议。` : "案例未完成计算，请先处理阻断问题。";
    if (!baseline) {
      $("overview-metrics").innerHTML = "<p class=\"empty-state\">没有可呈现的基准结果。</p>";
      return;
    }
    const ets = baseline.eu_ets || {};
    const fuelEu = baseline.fuel_eu || {};
    $("overview-metrics").innerHTML = [
      ["基准物理能量 (GJ)", formatField(baseline.physical_energy_mj, "energy")],
      ["基准燃料成本", number(baseline.fuel_cost, state.display.price)],
      ["EU ETS CO2e (t)", formatField(ets.ets_co2e_pre_scope_t, "gas")],
      ["FuelEU GHGI (g/MJ)", formatField(fuelEu.ghgi_actual_g_per_mj, "intensity")],
      ["FuelEU 合规余额 (t)", formatField(fuelEu.compliance_balance_t, "gas")],
      ["模型成本", number(baseline.model_cost, state.display.price)],
    ].map(([label, value]) => `<div class="metric"><span class="metric-label">${label}</span><strong class="metric-value">${value}</strong></div>`).join("");
    const voyageBasis = (result.candidate_results || []).find((item) => item.voyage_result)?.voyage_result || {};
    const scope = voyageBasis.scope_rates || {};
    const departure = scope.departure_port || {};
    const arrival = scope.arrival_port || {};
    $("port-identity-details").innerHTML = `<h3>港口范围与制度身份</h3><div class="detail-grid"><dl class="evidence-item"><dt>出发港</dt><dd>${esc(departure.port_name || result.departure_port)} · EU ETS ${esc(departure.eu_ets_identity)} · FuelEU ${esc(departure.fuel_eu_identity)}</dd></dl><dl class="evidence-item"><dt>到达港</dt><dd>${esc(arrival.port_name || result.arrival_port)} · EU ETS ${esc(arrival.eu_ets_identity)} · FuelEU ${esc(arrival.fuel_eu_identity)}</dd></dl><dl class="evidence-item"><dt>范围比例</dt><dd>EU ETS ${formatField(scope.eu_ets_effective_rate, "scope")} · FuelEU ${formatField(scope.fuel_eu_scope_rate, "scope")}</dd></dl><dl class="evidence-item"><dt>判断理由</dt><dd>EU ETS ${esc(scope.eu_ets_reason)} · FuelEU ${esc(scope.fuel_eu_reason)}</dd></dl></div>`;
    const gases = ets.mrv_raw_by_gas || {};
    const excluded = Object.entries(ets.excluded_from_ets_surrender || {}).filter(([, value]) => value).map(([gasName]) => gasName).join(", ") || "无";
    $("ets-fueleu-detail").innerHTML = `<h3>基准排放与 FuelEU</h3><div class="detail-grid"><dl class="evidence-item"><dt>EU ETS 气体</dt><dd>CO2 ${formatField(gases.CO2, "gas")} · CH4 ${formatField(gases.CH4, "gas")} · N2O ${formatField(gases.N2O, "gas")}</dd></dl><dl class="evidence-item"><dt>纳入 / 排除气体</dt><dd>${esc((ets.included_gases || []).join(", "))} / ${esc(excluded)}</dd></dl><dl class="evidence-item"><dt>EUAs / EUA 成本</dt><dd>${formatField(ets.euas_required, "gas")} / ${number(ets.eua_cost, state.display.price)}</dd></dl><dl class="evidence-item"><dt>FuelEU WtT / TtW / GHGI</dt><dd>WtT ${formatField(fuelEu.wt_t_intensity_g_per_mj, "intensity")} · TtW ${formatField(fuelEu.tt_w_intensity_g_per_mj, "intensity")} · GHGI ${formatField(fuelEu.ghgi_actual_g_per_mj, "intensity")} · 目标 ${formatField(fuelEu.target_g_per_mj, "intensity")} · 余额 ${formatField(fuelEu.compliance_balance_t, "gas")} · 指示性罚款 ${number(fuelEu.indicative_penalty_eur, state.display.price)}</dd></dl></div>`;
    const economics = result.economics || {};
    $("economics-summary").innerHTML = `<h3>案例经济结果</h3><div class="detail-grid"><dl class="evidence-item"><dt>当前模型成本最低</dt><dd>${esc(economics.cost_min_scenario_id)}</dd></dl><dl class="evidence-item"><dt>目标最低成本</dt><dd>${esc(economics.target_min_cost_scenario_id)}</dd></dl><dl class="evidence-item"><dt>最大合规改善</dt><dd>${esc(economics.max_improvement_scenario_id)}</dd></dl><dl class="evidence-item"><dt>比较状态</dt><dd>${esc(economics.comparison_status)}</dd></dl></div><p>相对 B0 的合规改善和成本变化见场景表。</p><div id="switch-points">${(economics.switch_points || []).map((point) => `<p>切换 ${esc(point.from_scenario_id)} → ${esc(point.to_scenario_id)} · value* ${number(point.value_star, state.display.price)}</p>`).join("") || "<p>暂无切换点。</p>"}</div>`;
    renderNewEnergyDecisionSummary(result);
    const rows = result.scenarios || [];
    $("scenario-comparison-table").querySelector("tbody").innerHTML = rows.map((row) => {
      const scenario = row.result || {};
      const fuelEuResult = scenario.fuel_eu || {};
      const scenarioEts = scenario.eu_ets || {};
      const scenarioGases = scenarioEts.mrv_raw_by_gas || {};
      const scenarioExcluded = Object.entries(scenario.eu_ets?.excluded_from_ets_surrender || {}).filter(([, value]) => value).map(([gasName]) => gasName).join(", ") || "-";
      return `<tr><td>${esc(row.scenario_id)}</td><td>${esc(row.candidate_id || "基准")}</td><td>${esc(row.calculation_status || "")} / ${esc(scenario.execution_status || "")}</td><td class="numeric">${percent(scenario.ratio)}</td><td class="numeric">${number(scenario.model_cost, state.display.price)}</td><td class="numeric">${number(deltaValue(row, "fuel_cost"), state.display.price)}</td><td class="numeric">${number(negateDecimalString(deltaValue(row, "eua_cost")), state.display.price)}</td><td class="numeric">${number(deltaValue(row, "model_cost"), state.display.price)}</td><td class="numeric">${formatField(fuelEuResult.ghgi_actual_g_per_mj, "intensity")}</td><td class="numeric">${formatField(fuelEuResult.compliance_balance_t, "gas")}</td><td class="numeric">${text(row.current_model_cost_rank)}</td><td class="numeric">B0 ${formatField(scenario.baseline_mass_tonnes, "mass")} + 候选 ${formatField(scenario.candidate_mass_tonnes, "mass")}</td><td class="numeric">${formatField(scenario.physical_energy_mj, "energy")}</td><td class="numeric">${number(scenario.fuel_cost, state.display.price)}</td><td class="numeric">${formatField(scenarioGases.CO2 || scenarioEts.raw_co2_t, "gas")}</td><td class="numeric">${formatField(scenarioGases.CH4 || scenarioEts.raw_ch4_t, "gas")}</td><td class="numeric">${formatField(scenarioGases.N2O || scenarioEts.raw_n2o_t, "gas")}</td><td>${esc((scenarioEts.included_gases || []).join(", "))}</td><td>${esc(scenarioExcluded)}</td><td class="numeric">${formatField(scenarioEts.euas_required, "gas")}</td><td class="numeric">${number(scenarioEts.eua_cost, state.display.price)}</td><td class="numeric">${formatField(fuelEuResult.wt_t_intensity_g_per_mj, "intensity")}</td><td class="numeric">${formatField(fuelEuResult.tt_w_intensity_g_per_mj, "intensity")}</td><td class="numeric">${formatField(fuelEuResult.target_g_per_mj, "intensity")}</td><td class="numeric">${number(fuelEuResult.indicative_penalty_eur, state.display.price)}</td><td class="numeric">${formatField(scenario.compliance_improvement_tco2e, "gas")}</td></tr>`;
    }).join("") || '<tr><td colspan="26" class="empty-state">暂无场景。</td></tr>';
    $("scenario-detail-table").innerHTML = "<p>执行状态：EXECUTION_CONDITIONS_PENDING。相对 B0 合规改善以 tCO2e 表示。</p>";
    $("conditional-recommendations").innerHTML = `<h3>条件式建议</h3>${(result.recommendations || []).map((rec) => `<div class="recommendation ${rec.status === "UNAVAILABLE" ? "unavailable" : ""}"><strong>${esc(rec.status)}</strong><span>${esc(rec.condition)} · ${esc(rec.reason)}${rec.scenario_id ? ` · 场景 ${esc(rec.scenario_id)}` : ""}</span><small>假设: ${esc((rec.assumptions || []).join(", "))}</small></div>`).join("") || '<p class="empty-state">暂无建议。</p>'}`;
    const provenance = result.provenance || {};
    const evidence = [["计算规范版本", provenance.calculation_spec_version], ["燃料因子版本", provenance.fuel_factor_version], ["港口规则版本", provenance.port_rule_version], ["EU ETS 边界理由", provenance.eu_ets_reason], ["FuelEU 边界理由", provenance.fuel_eu_reason], ["ETS effective rate", provenance.eu_ets_effective_rate], ["来源 ID", (provenance.source_ids || []).join("; ")]];
    (provenance.factor_resolutions || []).forEach((trace) => { const factor = trace.factor || {}; const evidenceText = (factor.source_evidence || []).map((item) => `${item.field_name}:${item.source_id}/${item.source_type}/${item.unit}/${item.verification_status}/${factorEvidenceValue(factor, trace, item.field_name)}`).join("; "); evidence.push([`因子回溯 · ${trace.requested_path_id}`, `${trace.resolved_path_id} · ${trace.resolution_reason} · 因子模式 ${factor.wt_t_mode} · 因子状态 ${trace.factor_status} · 资格 ${factor.qualification_status} · 设备 ${factor.equipment_id} · ${evidenceText}`]); });
    $("calculation-basis").innerHTML = evidence.map(([label, value]) => `<dl class="evidence-item"><dt>${label}</dt><dd>${esc(text(value))}</dd></dl>`).join("");
    const candidateThresholds = (result.candidate_results || []).map((candidate) => {
      const constraints = candidate.voyage_result && candidate.voyage_result.constraints;
      return constraints ? `<tr><td>${esc(candidate.candidate_id)}</td><td>${esc(constraints.target_status)}</td><td>${percent(constraints.x_budget)}</td><td>${percent(constraints.x_supply)}</td><td>${percent(constraints.x_cap)}</td><td>${percent(constraints.x_target_min_cost)}</td><td>${percent(constraints.x_max_improvement)}</td><td>${esc((constraints.warning_codes || []).join(", ") || "-")}</td></tr>` : `<tr><td>${esc(candidate.candidate_id)}</td><td colspan="7">BLOCKED · ${esc((candidate.issues || []).map((issue) => issue.code).join(", ") || "无约束结果")}</td></tr>`;
    }).join("");
    $("thresholds-content").innerHTML = `<table><thead><tr><th>候选</th><th>目标状态</th><th>预算边界</th><th>供应量边界</th><th>最大混合比例</th><th>目标最低成本比例</th><th>最大改善比例</th><th>警告</th></tr></thead><tbody>${candidateThresholds || '<tr><td colspan="8">暂无约束阈值。</td></tr>'}</tbody></table>`;
  }

  async function calculate(event) {
    event.preventDefault();
    clearResults();
    renderIssues([]);
    try {
      state.result = await fetchJson("/api/calculate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) });
      renderResults(state.result);
      const issues = [...(state.result.issues || []), ...(state.result.candidate_results || []).flatMap((candidate) => candidate.issues || [])];
      renderIssues(issues);
    } catch (error) { clearResults(); renderIssues((error.body && error.body.issues) || [{ code: "NETWORK_ERROR", scope: "CASE", field: "case", blocking: true, message: "无法连接计算服务" }]); }
  }
  async function exportResult(format) {
    if (!state.result) {
      renderIssues([{ code: "NO_RESULT", scope: "CASE", field: "case", blocking: true, message: "请先完成一次计算。" }]);
      return;
    }
    try {
      const response = await fetch(`/api/export/${format}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...payload(), displayConfig: { fuel_mass_decimals: state.display.mass, energy_decimals: state.display.energy, ratio_decimals: state.display.ratio, price_decimals: state.display.price } }) });
      if (!response.ok) {
        let body = {};
        try { body = await response.json(); } catch (_) { body = {}; }
        renderIssues(body.issues || [{ code: "EXPORT_ERROR", scope: "CASE", field: "export", blocking: true, message: "导出失败，请稍后重试。" }]);
        return;
      }
      const blob = await response.blob();
      const anchor = document.createElement("a");
      anchor.href = URL.createObjectURL(blob);
      anchor.download = `voyage-fuel-decision.${format}`;
      anchor.click();
      URL.revokeObjectURL(anchor.href);
    } catch (_) {
      renderIssues([{ code: "EXPORT_ERROR", scope: "CASE", field: "export", blocking: true, message: "导出失败，请检查网络连接后重试。" }]);
    }
  }
  function setupLookup(role) {
    const input = $(`${role}-port-search`);
    const list = $(`${role}-port-options`);
    let timer;
    input.addEventListener("input", () => {
      state.ports[role] = null;
      clearTimeout(timer);
      const query = input.value.trim();
      if (!query) { list.innerHTML = ""; return; }
      timer = setTimeout(async () => {
        try {
          const data = await fetchJson(`/api/ports?q=${encodeURIComponent(query)}`);
          list.innerHTML = data.ports.map((port) => `<button type="button" class="lookup-option" data-code="${esc(port.unlocode)}"><strong>${esc(port.unlocode)}</strong> · ${esc(port.portName)} · ${esc(port.countryCode)}</button>`).join("");
          list.querySelectorAll(".lookup-option").forEach((button) => button.addEventListener("click", () => { state.ports[role] = button.dataset.code; input.value = button.dataset.code; list.innerHTML = ""; }));
        } catch (_) { list.innerHTML = ""; }
      }, 160);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    addCandidate();
    loadFuels().catch(() => {});
    setupLookup("departure");
    setupLookup("arrival");
    $("baseline-mode").addEventListener("change", syncBaselineCustomEditor);
    $("baseline-custom-editor").addEventListener("change", syncBaselineCustomEditor);
    $("baseline-custom-editor").addEventListener("input", syncBaselineCustomEditor);
    syncBaselineCustomEditor();
    $("add-candidate").addEventListener("click", addCandidate);
    $("candidate-collection").addEventListener("click", (event) => {
      if (event.target.closest(".remove-candidate")) {
        const row = event.target.closest(".candidate-row");
        state.candidates = readCandidates();
        const index = [...document.querySelectorAll(".candidate-row")].indexOf(row);
        if (index >= 0) state.candidates.splice(index, 1);
        renderCandidates();
      }
    });
    $("candidate-collection").addEventListener("change", (event) => {
      const row = event.target.closest(".candidate-row");
      if (!row) return;
      if (event.target.matches('[data-field="customFuelType"]')) {
        const methaneField = field(row, "methaneSlipApplicable");
        if (methaneField) methaneField.value = event.target.value === "gas" ? "true" : "false";
      }
      syncCustomRow(row);
    });
    $("candidate-collection").addEventListener("input", (event) => { const row = event.target.closest(".candidate-row"); if (row && (event.target.matches('[data-field="cslip"]') || event.target.matches('[data-field="cfCH4"]') || event.target.matches('[data-field="cfN2O"]'))) syncCustomRow(row); });
    $("case-form").addEventListener("submit", calculate);
    $("export-csv").addEventListener("click", () => exportResult("csv"));
    $("export-pdf").addEventListener("click", () => exportResult("pdf"));
    document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => { document.querySelectorAll(".tab").forEach((item) => { item.classList.toggle("active", item === tab); item.setAttribute("aria-selected", item === tab); }); document.querySelectorAll(".tab-panel").forEach((panel) => { panel.hidden = panel.id !== tab.dataset.tab; panel.classList.toggle("active", panel.id === tab.dataset.tab); }); }));
    ["mass", "energy", "ratio", "price"].forEach((kind) => { $(`precision-${kind}`).addEventListener("input", (event) => { state.display[kind] = Math.max(0, Math.min(9, Number(event.target.value) || 0)); if (state.result) renderResults(state.result); }); });
  });
})();
