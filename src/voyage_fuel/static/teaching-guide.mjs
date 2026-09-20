import { formatDecimalStringScaled } from "./display-values.mjs";
import { fuelLabel } from "./workbench-labels.mjs";


const IDLE_STATE = Object.freeze({
  phase: "idle",
  caseId: null,
  visible: true,
  requestId: null,
  matched: false,
});


export function createGuideState() {
  return { ...IDLE_STATE };
}


export function reduceGuide(state, event) {
  if (event.type === "VISIBILITY") {
    return { ...state, visible: Boolean(event.visible) };
  }
  if (event.type === "APPLIED") {
    return {
      ...state,
      phase: "loading",
      caseId: event.caseId,
      requestId: event.requestId,
      matched: false,
    };
  }
  if (event.type === "INVALIDATED") {
    return {
      ...state,
      phase: "modified",
      requestId: null,
      matched: false,
    };
  }
  if (
    (event.type === "RESOLVED" || event.type === "FAILED")
    && event.requestId !== state.requestId
  ) {
    return state;
  }
  if (event.type === "RESOLVED") {
    return event.matched
      ? { ...state, phase: "ready", matched: true }
      : { ...state, phase: "modified", requestId: null, matched: false };
  }
  if (event.type === "FAILED") {
    return { ...state, phase: "error", requestId: null, matched: false };
  }
  return state;
}


function sameValue(left, right) {
  if (left === right) return true;
  if (left === null || right === null || typeof left !== typeof right) return false;
  if (Array.isArray(left) || Array.isArray(right)) {
    if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) {
      return false;
    }
    return left.every((value, index) => sameValue(value, right[index]));
  }
  if (typeof left !== "object") return false;
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  if (leftKeys.length !== rightKeys.length) return false;
  return leftKeys.every((key, index) =>
    key === rightKeys[index] && sameValue(left[key], right[key])
  );
}


export function sameExampleRequest(submitted, frozenRequest) {
  return sameValue(submitted, frozenRequest);
}


const DEFAULT_DISPLAY = Object.freeze({
  mass: 3,
  energy: 3,
  ratio: 4,
  price: 2,
});


function formatNumber(value, kind, displayConfig = DEFAULT_DISPLAY) {
  if (value === null || value === undefined || value === "") return null;
  const config = { ...DEFAULT_DISPLAY, ...(displayConfig || {}) };
  const decimals = kind === "ratio"
    ? config.ratio
    : kind === "mass"
      ? config.mass
      : kind === "intensity"
        ? 4
        : kind === "gas"
          ? 6
          : config.price;
  const power10 = kind === "ratio" ? 2 : 0;
  const rendered = formatDecimalStringScaled(value, decimals, power10);
  return kind === "ratio" ? `${rendered}%` : rendered;
}


function formatMoney(value, currency, displayConfig) {
  const rendered = formatNumber(value, "price", displayConfig);
  return rendered === null ? null : `${rendered} ${currency}`;
}


function formatMass(value, displayConfig) {
  const rendered = formatNumber(value, "mass", displayConfig);
  return rendered === null ? null : `${rendered} 吨`;
}


function formatIntensity(value) {
  const rendered = formatNumber(value, "intensity");
  return rendered === null ? null : `${rendered} gCO2eq/MJ`;
}


function formatBalance(value) {
  const rendered = formatNumber(value, "gas");
  return rendered === null ? null : `${rendered} tCO2e`;
}


function changeSummary(delta, currency, displayConfig) {
  if (delta === null || delta === undefined || delta === "") return "变化未提供";
  const raw = String(delta);
  const rendered = formatMoney(raw.startsWith("-") ? raw.slice(1) : raw, currency, displayConfig);
  if (rendered === null) return "变化未提供";
  if (String(delta).startsWith("-")) return `减少 ${rendered}`;
  if (Number(delta) === 0) return `不变 · ${rendered}`;
  return `增加 ${rendered}`;
}


function candidateInput(submittedInput, candidateId) {
  return (submittedInput?.candidates || [])
    .find((candidate) => candidate.candidateId === candidateId) || null;
}


function scenarioLabel(display, submittedInput, row) {
  if (!row || row.scenario_id === "B0") {
    return fuelLabel(submittedInput?.baseline?.pathId || "B0");
  }
  const candidate = candidateInput(submittedInput, row.candidate_id);
  return fuelLabel(candidate?.pathId || row.candidate_id);
}


function buildBasicNotes({ display, displayConfig, submittedInput }) {
  const baseline = display.scenarioById?.get("B0");
  if (!baseline?.result) return [];
  const currency = display.result?.currency || "";
  const changes = new Map(
    (display.selectedDetail?.changes || []).map((change) => [change.key, change]),
  );
  const fuelCost = formatMoney(changes.get("fuel_cost")?.selected, currency, displayConfig);
  const euaCost = formatMoney(changes.get("eua_cost")?.selected, currency, displayConfig);
  const modelCost = formatMoney(changes.get("model_cost")?.selected, currency, displayConfig);
  const fuelEu = baseline.result.fuel_eu || {};
  const ghgi = formatIntensity(fuelEu.ghgi_actual_g_per_mj);
  const target = formatIntensity(fuelEu.target_g_per_mj);
  const statusText = {
    DEFICIT_ESTIMATE: "当前状态为缺口",
    SURPLUS_ESTIMATE: "当前状态为盈余",
    ON_TARGET_ESTIMATE: "当前状态与参考线一致",
  }[fuelEu.status] || "当前状态未提供";
  const balance = formatBalance(changes.get("fueleu_compliance_balance_t")?.selected);
  const penalty = formatMoney(
    changes.get("fueleu_indicative_penalty_eur")?.selected,
    "EUR",
    displayConfig,
  );
  const notes = [];

  if (fuelCost && euaCost && modelCost) {
    notes.push({
      id: "basic-cost",
      anchor: "cost-breakdown",
      title: "这笔成本由什么组成？",
      text: `燃料成本${fuelCost}，EU ETS成本${euaCost}，模型成本合计${modelCost}。`,
    });
  }
  if (ghgi && target) {
    notes.push({
      id: "basic-ghgi",
      anchor: "ghgi",
      title: "达到参考线了吗？",
      text: `GHGI是每单位能源的温室气体排放强度。本例为${ghgi}，参考线为${target}；${statusText}。`,
    });
  }
  notes.push({
    id: "basic-balance",
    anchor: "fueleu-balance",
    title: "缺口和成本分开看",
    text: `${balance ? `合规余额为${balance}` : "合规余额未提供"}；${penalty ? `指示性金额为${penalty}` : "指示性金额未提供"}，不计入上面的模型成本，也不代表年度最终罚款。`,
  });
  return notes;
}


function goalNotes({ display, displayConfig, submittedInput }) {
  const currency = display.result?.currency || "";
  const cards = new Map((display.goalCards || []).map((card) => [card.key, card]));
  const rowFor = (key) => {
    const scenarioId = cards.get(key)?.scenarioId;
    return scenarioId ? display.scenarioById?.get(scenarioId) : null;
  };
  const notes = [];
  const costCard = cards.get("cost");
  const costRow = rowFor("cost");

  if (costRow?.result) {
    const label = scenarioLabel(display, submittedInput, costRow);
    const cost = formatMoney(costRow.result.model_cost, currency, displayConfig);
    const notOnTarget = costRow.result.fuel_eu?.status === "DEFICIT_ESTIMATE";
    notes.push({
      id: "comparison-cost",
      anchor: "goals",
      title: "当前模型成本最低",
      text: `当前模型成本最低方案是${label}，模型成本${cost || "未提供"}。${notOnTarget ? "但未达到本例参考线。" : ""}`,
    });
  } else {
    notes.push({
      id: "comparison-cost",
      anchor: "goals",
      title: "当前模型成本最低",
      text: costCard?.reason ? "当前没有可用的模型成本最低方案。" : "当前结果未提供模型成本最低方案。",
    });
  }

  const targetRow = rowFor("target");
  if (targetRow?.result) {
    const label = scenarioLabel(display, submittedInput, targetRow);
    const ratio = formatNumber(targetRow.result.ratio, "ratio", displayConfig);
    const cost = formatMoney(targetRow.result.model_cost, currency, displayConfig);
    const change = changeSummary(targetRow.deltas?.model_cost?.delta, currency, displayConfig);
    notes.push({
      id: "comparison-target",
      anchor: "goals",
      title: "达到 GHGI 参考线的最低成本",
      text: `当前推荐为${label}，质量占比${ratio || "未提供"}，模型成本${cost || "未提供"}，相对B0${change}。`,
    });
  } else {
    notes.push({
      id: "comparison-target",
      anchor: "goals",
      title: "达到 GHGI 参考线的最低成本",
      text: "当前没有达到参考线的最低成本方案。",
    });
  }

  const improvementRow = rowFor("improvement");
  if (improvementRow?.result) {
    const label = scenarioLabel(display, submittedInput, improvementRow);
    const ratio = formatNumber(improvementRow.result.ratio, "ratio", displayConfig);
    const cost = formatMoney(improvementRow.result.model_cost, currency, displayConfig);
    notes.push({
      id: "comparison-improvement",
      anchor: "goals",
      title: "报告方案中的最大合规改善",
      text: `当前推荐为${label}，质量占比${ratio || "未提供"}，模型成本${cost || "未提供"}。改善最大不等于成本最低。`,
    });
  } else {
    notes.push({
      id: "comparison-improvement",
      anchor: "goals",
      title: "报告方案中的最大合规改善",
      text: "当前没有可比较的最大合规改善方案。",
    });
  }
  return notes;
}


function buildComparisonDetailNote({ display, submittedInput }) {
  const row = display.scenarioById?.get(display.selectedDetail?.scenarioId);
  if (!row?.result) return null;
  const label = scenarioLabel(display, submittedInput, row);
  return {
    id: "comparison-detail",
    anchor: "detail-charts",
    title: "增加的投入换来了什么？",
    text: `左边看燃料成本与EU ETS成本的变化，右边看排放强度和参考线。这里对应当前查看的${label}方案。`,
  };
}


function buildSupplyNote({ display, displayConfig, submittedInput }) {
  const limited = (display.sensitivity?.candidates || [])
    .find((candidate) => candidate.candidateId === "uco-limited");
  if (!limited) return null;
  const limitedInput = candidateInput(submittedInput, "uco-limited");
  const bulkInput = candidateInput(submittedInput, "uco-bulk");
  const currency = display.result?.currency || "";
  const price = formatMoney(limited.currentPrice, currency, displayConfig);
  const supply = formatMass(limitedInput?.candidateSupplyTonnes, displayConfig);
  const statusText = {
    TARGET_REACHABLE: "当前结果显示在现有供应限制下可达",
    TARGET_UNREACHABLE_UNDER_CONSTRAINTS: "当前结果显示供应限制下不可达",
    TARGET_NO_SOLUTION: "当前结果显示没有可达目标",
    TARGET_NOT_APPLICABLE: "参考线不适用于该候选",
  }[limited.targetStatus] || "当前目标状态未提供";
  const bulkText = bulkInput && (
    bulkInput.candidateSupplyTonnes === null
    || bulkInput.candidateSupplyTonnes === undefined
    || bulkInput.candidateSupplyTonnes === ""
  ) ? "大宗UCO未设置供应量上限。" : "";
  return {
    id: "comparison-supply",
    anchor: "supply-uco-limited",
    title: "便宜的报价为什么仍不能达到参考线？",
    text: `这份UCO报价${price ? `${price}/吨` : "未提供"}，供应量${supply || "未提供"}。${statusText}。${bulkText}`,
  };
}


export function buildGuideNotes({
  state,
  display,
  displayConfig,
  submittedInput,
  frozenRequest,
}) {
  if (
    !state
    || state.phase !== "ready"
    || !state.matched
    || !display
    || !sameExampleRequest(submittedInput, frozenRequest)
  ) {
    return [];
  }
  if (state.caseId === "A-2025") {
    return buildBasicNotes({ display, displayConfig, submittedInput });
  }
  if (state.caseId === "B-default") {
    return [
      ...goalNotes({ display, displayConfig, submittedInput }),
      buildComparisonDetailNote({ display, submittedInput }),
      buildSupplyNote({ display, displayConfig, submittedInput }),
    ].filter(Boolean);
  }
  return [];
}
