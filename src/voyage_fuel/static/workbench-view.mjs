import {
  attachResult,
  buildChartData,
  buildWorkbenchDisplayModel,
  selectGoal,
  selectScenario,
} from "./workbench-model.mjs";
import {
  buildSvgGhgi,
  buildSvgScatter,
  buildSvgSwitchRail,
  buildSvgThresholdLanes,
  buildSvgWaterfall,
  renderCharts,
} from "./workbench-charts.mjs";
import { formatDecimalStringScaled } from "./display-values.mjs";
import { fuelLabel, reasonLabel, statusLabel, warningLabel } from "./workbench-labels.mjs";

const DEFAULT_DISPLAY = Object.freeze({ mass: 3, energy: 3, ratio: 4, price: 2 });

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
  }[character]));
}

function rawText(value, fallback = "未提供") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function formatValue(value, kind, display = DEFAULT_DISPLAY) {
  if (value === null || value === undefined || value === "") return "未提供";
  const places = {
    mass: display.mass ?? 3,
    energy: display.energy ?? 3,
    ratio: display.ratio ?? 4,
    intensity: 4,
    gas: 6,
    price: display.price ?? 2,
    eur: display.price ?? 2,
  };
  const decimals = places[kind] ?? 4;
  const power10 = kind === "ratio" ? 2 : 0;
  const rendered = formatDecimalStringScaled(value, decimals, power10);
  if (kind === "ratio") return `${rendered}%`;
  return rendered;
}

function unitFor(kind, currency) {
  return {
    ratio: "",
    mass: "t",
    energy: "GJ",
    price: currency || "",
    eur: "EUR",
    intensity: "gCO2eq/MJ",
    gas: "tCO2e",
  }[kind] || "";
}

function displayWithUnit(value, kind, display, currency) {
  const rendered = formatValue(value, kind, display);
  const unit = unitFor(kind, currency);
  return unit && rendered !== "未提供" ? `${rendered} ${unit}` : rendered;
}

function changeText(value, kind, display, currency) {
  if (value === null || value === undefined || value === "") {
    return '<span class="change change-missing">无法判断</span>';
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return `<span class="change change-missing">${escapeHtml(String(value))}</span>`;
  }
  if (numeric === 0) {
    return `<span class="change change-neutral">不变 · ${escapeHtml(displayWithUnit("0", kind, display, currency))}</span>`;
  }
  const direction = numeric > 0 ? "增加" : "减少";
  const className = numeric > 0 ? "change-up" : "change-down";
  const magnitude = formatValue(Math.abs(numeric).toString(), kind, display);
  const unit = unitFor(kind, currency);
  return `<span class="change ${className}">${direction} ${escapeHtml(magnitude)}${unit ? ` ${escapeHtml(unit)}` : ""}</span>`;
}

function modelPath(state, candidateId) {
  const candidate = (state.submittedInput?.candidates || []).find((item) => item.candidateId === candidateId);
  return candidate?.pathId || candidateId;
}

function scenarioTitle(state, row) {
  if (!row || row.scenario_id === "B0") {
    return fuelLabel(state.submittedInput?.baseline?.pathId || "MDO");
  }
  return fuelLabel(modelPath(state, row.candidate_id));
}

function scenarioRoleLabel(role) {
  return role || "报告方案";
}

function renderStatus(status, extraClass = "") {
  return `<span class="status-label ${extraClass}">${escapeHtml(statusLabel(status))}</span>`;
}

function humanCode(value) {
  const raw = String(value || "");
  if (!raw) return "";
  const status = statusLabel(raw);
  if (status !== "状态待核对") return status;
  const reason = reasonLabel(raw);
  if (reason !== "结果依据待核对") return reason;
  return raw;
}

function renderGoalCards(state, display) {
  return display.goalCards.map((card) => {
    const active = state.activeGoal === card.key;
    const unavailable = card.availability !== "available";
    const row = card.scenarioId ? state.scenarioById.get(card.scenarioId) : null;
    const result = row?.result || {};
    const label = row ? scenarioTitle(state, row) : "暂无可用方案";
    return `<button type="button" class="workbench-goal-card${active ? " active" : ""}${unavailable ? " unavailable" : ""}" data-goal="${escapeHtml(card.key)}" aria-pressed="${active}">
      <span class="goal-card-top"><span class="goal-card-label">${escapeHtml(card.label)}</span>${unavailable ? '<span class="goal-card-state">暂无</span>' : '<span class="goal-card-state">可查看</span>'}</span>
      <strong>${escapeHtml(label)}</strong>
      <span class="goal-card-id">${escapeHtml(card.scenarioId || (card.reason ? reasonLabel(card.reason) : "当前结果未提供"))}</span>
      <span class="goal-card-metrics">${row
        ? `${escapeHtml(displayWithUnit(result.model_cost, "price", state.display, state.result.currency))} · ${escapeHtml(displayWithUnit(result.ratio, "ratio", state.display, state.result.currency))}`
        : escapeHtml(reasonLabel(card.reason))}</span>
      <small>${escapeHtml(card.reason ? reasonLabel(card.reason) : "服务端结果未提供该目标方案")}</small>
    </button>`;
  }).join("");
}

function renderScenarioCard(state, row) {
  const raw = state.scenarioById.get(row.scenarioId);
  const selected = row.scenarioId === state.selectedScenarioId;
  const recommended = row.recommendedGoals.length > 0;
  const title = row.label === row.candidateId ? scenarioTitle(state, raw) : row.label;
  return `<button type="button" class="workbench-scenario-card${selected ? " selected" : ""}" data-scenario-id="${escapeHtml(row.scenarioId)}" aria-pressed="${selected}">
    <span class="scenario-card-heading"><span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(scenarioTitle(state, raw))} · ${escapeHtml(row.scenarioId)}</small></span><span class="scenario-card-badges">${recommended ? '<span class="mini-badge recommendation">系统推荐</span>' : ""}${selected ? '<span class="mini-badge selected">当前查看</span>' : ""}</span></span>
    <span class="scenario-card-meta"><span><small>角色</small><strong>${escapeHtml(scenarioRoleLabel(row.role))}</strong></span><span><small>质量占比</small><strong>${escapeHtml(formatValue(row.ratio, "ratio", state.display))}</strong></span><span><small>候选用量</small><strong>${escapeHtml(displayWithUnit(row.candidateMassTonnes, "mass", state.display, state.result.currency))}</strong></span></span>
    <span class="scenario-card-values"><span><small>模型成本</small><strong>${escapeHtml(displayWithUnit(row.modelCost, "price", state.display, state.result.currency))}</strong></span><span><small>相对 B0</small><strong>${changeText(row.costDelta, "price", state.display, state.result.currency)}</strong></span></span>
    <span class="scenario-card-values"><span><small>GHGI</small><strong>${escapeHtml(displayWithUnit(row.ghgi, "intensity", state.display, state.result.currency))}</strong></span><span><small>合规余额</small><strong>${escapeHtml(displayWithUnit(row.complianceBalance, "gas", state.display, state.result.currency))}</strong></span></span>
    <span class="scenario-card-status">${renderStatus(row.constraintStatus || row.calculationStatus)} ${renderStatus(row.calculationStatus)}</span>
  </button>`;
}

function renderScenarioTable(state, display) {
  const rows = display.scenarioRows;
  if (!rows.length) return '<p class="empty-state">暂无可呈现方案。</p>';
  const body = rows.map((row) => {
    const raw = state.scenarioById.get(row.scenarioId);
    const selected = row.scenarioId === state.selectedScenarioId;
    const recommended = row.recommendedGoals.length > 0;
    const badges = [
      recommended ? '<span class="mini-badge recommendation">系统推荐</span>' : "",
      selected ? '<span class="mini-badge selected">当前查看</span>' : "",
    ].join("");
    return `<tr class="workbench-scenario-row${selected ? " selected" : ""}" data-scenario-id="${escapeHtml(row.scenarioId)}" tabindex="0" role="button" aria-selected="${selected}">
      <td><strong>${escapeHtml(row.label === row.candidateId ? scenarioTitle(state, raw) : row.label)}</strong><small>${escapeHtml(scenarioTitle(state, raw))} · ${escapeHtml(row.scenarioId)}</small>${badges}</td>
      <td>${escapeHtml(scenarioRoleLabel(row.role))}</td>
      <td class="numeric">${escapeHtml(formatValue(row.ratio, "ratio", state.display))}</td>
      <td class="numeric">${escapeHtml(displayWithUnit(row.candidateMassTonnes, "mass", state.display, state.result.currency))}</td>
      <td class="numeric">${escapeHtml(displayWithUnit(row.modelCost, "price", state.display, state.result.currency))}</td>
      <td class="numeric">${changeText(row.costDelta, "price", state.display, state.result.currency)}</td>
      <td class="numeric">${escapeHtml(displayWithUnit(row.ghgi, "intensity", state.display, state.result.currency))}</td>
      <td class="numeric">${escapeHtml(displayWithUnit(row.complianceBalance, "gas", state.display, state.result.currency))}</td>
      <td>${renderStatus(row.constraintStatus || row.calculationStatus)} ${renderStatus(row.calculationStatus)}</td>
    </tr>`;
  }).join("");
  const cards = rows.map((row) => renderScenarioCard(state, row)).join("");
  return `<div class="table-scroll workbench-table-scroll">
    <table class="workbench-scenario-table">
      <caption>全部 2.5 级报告方案。点击行查看相对 B0 的投入产出变化。</caption>
      <thead><tr><th>方案</th><th>报告点角色</th><th>候选燃料质量占比</th><th>候选燃料用量</th><th>模型成本</th><th>相对 B0 净变化</th><th>GHGI</th><th>合规余额</th><th>状态</th></tr></thead>
      <tbody>${body}</tbody>
    </table>
  </div><div class="workbench-scenario-cards" aria-label="移动端方案列表">${cards}</div>`;
}

function renderDeltaCards(state, detail) {
  return `<div class="workbench-delta-cards" aria-label="移动端 B0 对比">
    ${detail.changes.map((change) => `<article class="workbench-delta-card"${change.key === "fueleu_compliance_balance_t" ? ' data-guide-anchor="fueleu-balance"' : ""}>
      <strong>${escapeHtml(change.label)}</strong>
      <dl><div><dt>B0</dt><dd>${escapeHtml(displayWithUnit(change.baseline, change.unit, state.display, state.result.currency))}</dd></div><div><dt>当前方案</dt><dd>${escapeHtml(displayWithUnit(change.selected, change.unit, state.display, state.result.currency))}</dd></div><div><dt>变化</dt><dd>${changeText(change.delta, change.unit, state.display, change.unit === "eur" ? "EUR" : state.result.currency)}</dd></div></dl>
    </article>`).join("")}
  </div>`;
}

function renderDeltaTable(state, detail) {
  const rows = detail.changes.map((change) => `<tr>
    <th scope="row">${escapeHtml(change.label)}</th>
    <td class="numeric">${escapeHtml(displayWithUnit(change.baseline, change.unit, state.display, state.result.currency))}</td>
    <td class="numeric">${escapeHtml(displayWithUnit(change.selected, change.unit, state.display, state.result.currency))}</td>
    <td class="numeric">${changeText(change.delta, change.unit, state.display, change.unit === "eur" ? "EUR" : state.result.currency)}</td>
  </tr>`).join("");
  return `<div class="table-scroll workbench-delta-table-wrap" data-guide-anchor="cost-breakdown fueleu-balance">
    <table class="workbench-delta-table">
      <caption>B0 基准方案与当前查看方案的绝对值和变化值</caption>
      <thead><tr><th>指标</th><th>B0</th><th>当前方案</th><th>变化</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>${renderDeltaCards(state, detail)}`;
}

function priceDecisionText(current, threshold, kind, status = "") {
  const normalizedStatus = String(status || "");
  if (normalizedStatus && !["AVAILABLE", "FINITE_NON_NEGATIVE"].includes(normalizedStatus)) {
    return "当前比较条件不足，暂不能判断成本优势";
  }
  if (current === null || current === undefined || current === "" || threshold === null || threshold === undefined || threshold === "") {
    return "当前比较条件不足，暂不能判断成本优势";
  }
  const currentNumber = Number(current);
  const thresholdNumber = Number(threshold);
  if (!Number.isFinite(currentNumber) || !Number.isFinite(thresholdNumber)) {
    return "当前比较条件不足，暂不能判断成本优势";
  }
  if (currentNumber === thresholdNumber) return "当前价格处于成本平衡点附近";
  if (kind === "eua") {
    return currentNumber > thresholdNumber
      ? "当前碳价已高于成本持平碳价，按当前比较条件具备成本优势"
      : "当前碳价低于成本持平碳价，按当前比较条件暂无成本优势";
  }
  return currentNumber > thresholdNumber
    ? "当前报价高于成本持平价，按当前比较条件暂无成本优势"
    : "当前报价低于成本持平价，按当前比较条件具备成本优势";
}

function renderSelectedDetail(state, display, charts) {
  const raw = state.scenarioById.get(state.selectedScenarioId);
  if (!raw) return '<p class="empty-state">暂无可查看方案。</p>';
  const title = scenarioTitle(state, raw);
  const sourceLabel = state.selectionSource === "goal" ? "目标方案" : "手动查看";
  const recommendation = display.selectedDetail.recommendation;
  const reason = recommendation?.reason ? reasonLabel(recommendation.reason) : "当前方案由你从完整报告方案中选择，用于与 B0 比较";
  const assumptions = (recommendation?.assumptions || []).map(humanCode).join("、")
    || (sourceLabel === "手动查看" ? "具体约束状态见方案表；本区只展示投入产出变化" : "服务端未提供额外假设");
  return `<div class="selected-detail-header">
    <div><span class="eyebrow">当前查看 · ${escapeHtml(sourceLabel)}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(raw.scenario_id)}</p></div>
    <div class="selected-detail-badges">${state.selectedScenarioId === state.recommendedScenarioId ? '<span class="mini-badge recommendation">系统推荐</span>' : '<span class="mini-badge selected">手动查看</span>'}${renderStatus(raw.result?.execution_status || "EXECUTION_CONDITIONS_PENDING")}</div>
  </div>
  <div class="detail-explanation">
    <div><strong>为什么显示这个方案</strong><p>${escapeHtml(reason)}</p></div>
    <div><strong>适用假设</strong><p>${escapeHtml(assumptions)}</p></div>
  </div>
  ${renderDeltaTable(state, display.selectedDetail)}
  <div class="detail-charts" data-guide-anchor="detail-charts">
    <section class="chart-block"><div class="subsection-heading"><h4>成本变化</h4><span>不含 FuelEU 指示性金额</span></div>${charts.waterfall || '<p class="empty-state">缺少成本所需价格，暂不绘图。</p>'}</section>
    <section class="chart-block" data-guide-anchor="ghgi"><div class="subsection-heading"><h4>GHGI 与参考线</h4><span>本航次情景</span></div>${charts.ghgi || '<p class="empty-state">暂无完整 GHGI 或参考线数据。</p>'}</section>
  </div>
  <div class="detail-status-grid">
    <div><span>计算状态</span>${renderStatus(raw.calculation_status)}</div>
    <div><span>约束状态</span>${renderStatus(raw.result?.constraint_status)}</div>
    <div><span>执行状态</span>${renderStatus(raw.result?.execution_status || "EXECUTION_CONDITIONS_PENDING")}</div>
    <div><span>FuelEU 金额边界</span><strong>EUR 独立显示</strong><small>不计入模型成本或预算</small></div>
  </div>`;
}

function renderSensitivity(state, display) {
  if (!display.sensitivity.candidates.length && !display.sensitivity.switchPoints.length) {
    const hasCandidates = Boolean(state.submittedInput?.candidates?.length);
    return hasCandidates
      ? '<div class="empty-state"><strong>替代燃料暂时无法参与比较</strong><p>尚未生成用量限制和价格比较结果，请检查候选燃料的输入及计算提示。</p></div>'
      : '<div class="empty-state"><strong>本次仅计算了原燃料方案</strong><p>尚未添加替代燃料，暂无用量限制和价格比较结果。</p></div>';
  }
  const candidates = display.sensitivity.candidates.map((candidate) => {
    const rawCandidate = (state.result.candidate_results || []).find((item) => item.candidate_id === candidate.candidateId);
    if (!rawCandidate?.voyage_result) {
      const reasons = (rawCandidate?.issues || []).map((issue) => `<li>${escapeHtml(issue.message || issue.code)}</li>`).join("");
      return `<section class="sensitivity-candidate"><h4>${escapeHtml(fuelLabel(candidate.label))}</h4><strong>替代燃料暂时无法参与比较</strong>${reasons ? `<ul>${reasons}</ul>` : '<p>尚未生成计算结果，请检查该候选燃料的输入及计算提示。</p>'}</section>`;
    }
    const rail = buildSvgThresholdLanes(candidate, undefined, state.display.ratio);
    const thresholdRows = candidate.thresholds.map((threshold) => {
      const value = threshold.unavailableBecause ? "未设置" : formatValue(threshold.value, "ratio", state.display);
      const note = threshold.unavailableBecause || (threshold.value === null ? "当前条件下无法确定" : "根据当前输入计算");
      return `<tr><th scope="row">${escapeHtml(threshold.label)}</th><td class="numeric">${escapeHtml(value)}</td><td>${escapeHtml(note)}</td></tr>`;
    }).join("");
    const guideAnchor = candidate.candidateId === "uco-limited"
      ? ` data-guide-anchor="supply-uco-limited" data-guide-candidate-id="${escapeHtml(candidate.candidateId)}"`
      : "";
    return `<section class="sensitivity-candidate"${guideAnchor}>
      <div class="subsection-heading"><div><h4>${escapeHtml(fuelLabel(candidate.label))}</h4><p>${escapeHtml(candidate.candidateId)} · ${escapeHtml(statusLabel(candidate.targetStatus))}</p></div><span>本次已计算 ${candidate.reportPoints.length} 个比例方案</span></div>
      <div class="sensitivity-legend"><span><i class="legend-dot boundary"></i>计算得到的比例限制</span><span><i class="legend-dot report"></i>本次已计算的方案</span><span>图中位置表示候选燃料质量占比，右侧为精确值</span></div>
      <div class="sensitivity-chart-scroll">${rail || '<p class="empty-state">暂无可绘制比例边界。</p>'}</div>
      <div class="sensitivity-two-col">
        <div><h4>最多能用多少</h4><p>这些比例各自回答不同问题：是否受限、能否达到 GHGI 目标，以及成本最低时应使用多少。</p><div class="table-scroll"><table class="compact-table"><caption>候选燃料质量占比</caption><thead><tr><th>要判断的问题</th><th>比例</th><th>说明</th></tr></thead><tbody>${thresholdRows || '<tr><td colspan="3">暂无约束结果</td></tr>'}</tbody></table></div></div>
        <div class="price-break-even">
          <div><h4>什么价格更划算</h4><p>“成本持平价”是替代方案与原燃料方案成本相同的价格。燃料价格和碳价分开计算，其他输入保持不变。</p></div>
          <div>
            <span>当前替代燃料报价</span>
            <strong>${escapeHtml(displayWithUnit(candidate.currentPrice, "price", state.display, state.result.currency))}</strong>
            <small>碳价不变时，燃料成本持平价 ${escapeHtml(displayWithUnit(candidate.pcBreakEven, "price", state.display, state.result.currency))}</small>
            <p class="break-even-explanation">${escapeHtml(priceDecisionText(candidate.currentPrice, candidate.pcBreakEven, "candidate"))}</p>
          </div>
          <div>
            <span>当前 EUA 碳价</span>
            <strong>${escapeHtml(displayWithUnit(candidate.currentEuaPrice, "price", state.display, state.result.currency))}</strong>
            <small>燃料报价不变时，碳价成本持平价 ${escapeHtml(displayWithUnit(candidate.peBreakEven, "price", state.display, state.result.currency))} · ${escapeHtml(statusLabel(candidate.peBreakEvenStatus))}</small>
            <p class="break-even-explanation">${escapeHtml(priceDecisionText(candidate.currentEuaPrice, candidate.peBreakEven, "eua", candidate.peBreakEvenStatus))}</p>
          </div>
        </div>
      </div>
      ${candidate.warnings.length ? `<p class="warning-note">约束提示：${escapeHtml(candidate.warnings.map(warningLabel).join("、"))}</p>` : ""}
    </section>`;
  }).join("");
  const switches = display.sensitivity.switchPoints;
  return `
    ${candidates}
    <section class="switch-point-section">
      <div class="subsection-heading"><div><h4>合规改善估值变化时，优势方案何时改变</h4><p>这里假设你给每吨 FuelEU 合规改善赋予一个参考价值。该价值变化到分界点后，成本更低的方案可能改变；它不代表实际收入。</p></div></div>
      ${buildSvgSwitchRail(switches, undefined, undefined, state.display.price) || '<p class="empty-state">暂无可用切换点。</p>'}
      <div class="table-scroll"><table class="compact-table"><caption>方案变化的合规改善参考价值</caption><thead><tr><th>原先成本更低</th><th>之后成本更低</th><th>参考价值分界点</th><th>说明</th></tr></thead><tbody>${switches.map((point) => `<tr><td>${escapeHtml(point.fromScenarioId)}</td><td>${escapeHtml(point.toScenarioId)}</td><td class="numeric">${escapeHtml(displayWithUnit(point.valueStar, "price", state.display, state.result.currency))} / tCO2e</td><td>参考价值高于此分界点后，后一个方案的调整后成本更低</td></tr>`).join("") || '<tr><td colspan="4">暂无切换点</td></tr>'}</tbody></table></div>
    </section>`;
}

function renderEvidence(state, display) {
  const raw = state.scenarioById.get(state.selectedScenarioId);
  const result = state.result;
  const rows = [
    ["结果快照", result.result_snapshot_id],
    ["当前方案 ID", state.selectedScenarioId],
    ["候选燃料路径", raw?.candidate_id ? modelPath(state, raw.candidate_id) : state.submittedInput?.baseline?.pathId],
    ["原始比例", raw?.result?.ratio],
    ["当前目标", state.activeGoal],
    ["推荐与查看", state.selectionSource === "goal" ? "目标方案" : "手动查看"],
    ["建议原因", display.selectedDetail.recommendation?.reason],
  ];
  return `<summary>查看完整数值、状态与依据</summary><p>这里保留原始编号和状态码，便于与 CSV/PDF 同一结果快照核对。</p><dl class="workbench-raw">${rows.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(rawText(value))}</dd>`).join("")}</dl>`;
}

export function createWorkbenchView(root, callbacks = {}) {
  let chartCleanup = () => {};
  let state = null;

  function renderModel() {
    if (!state?.result) return;
    const result = state.result;
    const display = buildWorkbenchDisplayModel(
      result,
      state.submittedInput,
      state.selectedScenarioId,
      { activeGoal: state.activeGoal, recommendedScenarioId: state.recommendedScenarioId },
    );
    const chartData = buildChartData(result, state.selectedScenarioId, state.display);
    const content = root.querySelector("#workbench-content");
    if (!content) return;
    const rawSelected = state.scenarioById.get(state.selectedScenarioId);
    const charts = {
      waterfall: buildSvgWaterfall(chartData.cost),
      ghgi: buildSvgGhgi(chartData.ghgi),
    };
    content.innerHTML = `
      <div class="workbench-toolbar">
        <div><span class="eyebrow">决策目标</span><p class="toolbar-note">先选关注目标，再查看全部报告方案和当前方案变化。</p><nav class="workbench-result-nav" aria-label="结果区域导航"><a href="#workbench-goal-cards">核心结论</a><a href="#workbench-scenario-table">方案比较</a><a href="#workbench-sensitivity">用量限制与价格影响</a></nav></div>
        <button type="button" class="button secondary" data-edit-inputs>编辑输入</button>
      </div>
      <section id="workbench-goal-cards" class="workbench-section goal-section" aria-labelledby="goal-heading" data-guide-anchor="goals">
        <div class="section-heading compact"><div><h3 id="goal-heading">三类核心决策结论</h3><p class="section-note">三类结论是入口，完整方案仍在下方保留。</p></div><span class="section-count">${display.goalCards.length} 个目标</span></div>
        <div class="workbench-goal-cards">${renderGoalCards(state, display)}</div>
      </section>
      <div class="workbench-results-flow">
        <section id="workbench-scenario-table" class="workbench-section scenario-section" aria-labelledby="scenario-heading">
          <div class="section-heading compact"><div><h3 id="scenario-heading">全部 2.5 级报告方案</h3><p class="section-note">方案表负责选择；点击任意方案后，在下方查看 B0 → 当前方案变化。</p></div><span class="section-count">${display.scenarioRows.length} 个报告点</span></div>
          ${renderScenarioTable(state, display)}
        </section>
        <section id="workbench-selected-detail" class="workbench-section selected-section" aria-labelledby="selected-heading">
          <div class="section-heading compact"><div><h3 id="selected-heading">当前方案投入产出</h3><p class="section-note">系统推荐和手动查看保持区分。</p></div><span class="section-count">${escapeHtml(rawSelected?.scenario_id || "暂无")}</span></div>
          ${renderSelectedDetail(state, display, charts)}
        </section>
      </div>
      <section class="workbench-section comparison-section" aria-labelledby="comparison-heading">
        <div class="section-heading compact"><div><h3 id="comparison-heading">方案成本与合规改善决策地图</h3><p class="section-note">以 B0 为原点；横轴是相对 B0 净成本变化，纵轴是相对 B0 合规改善。虚线点表示约束尚未验证，不等于满足约束。</p></div></div>
        ${buildSvgScatter(chartData) || '<p class="empty-state">暂无完整坐标可绘制。缺失价格或合规改善值的方案仍保留在上方列表。</p>'}
        <div class="scatter-legend" aria-label="决策地图图例">
          <span><i class="scatter-key b0"></i>B0 基准</span>
          <span><i class="scatter-key cost-min"></i>成本最低</span>
          <span><i class="scatter-key target-min-cost"></i>达标最低成本</span>
          <span><i class="scatter-key max-improvement"></i>报告方案最大改善</span>
          <span><i class="scatter-key selected"></i>当前查看</span>
          <span><i class="scatter-key unverified"></i>约束未验证</span>
        </div>
      </section>
      <details id="workbench-sensitivity" class="workbench-section sensitivity-section">
        <summary class="section-heading compact"><div><h3 id="sensitivity-heading">用量限制与价格影响</h3><p class="section-note">根据你填写的预算、供应量和使用比例限制，查看替代燃料最多能用多少；结合价格分析，判断什么条件下使用它更省钱。</p></div></summary>
        ${renderSensitivity(state, display)}
      </details>
      <details id="workbench-evidence" class="workbench-section workbench-details">
        ${renderEvidence(state, display)}
      </details>`;

    content.querySelectorAll("[data-goal]").forEach((button) => {
      button.addEventListener("click", () => {
        state = selectGoal(state, button.dataset.goal);
        renderModel();
      });
    });
    content.querySelectorAll("[data-scenario-id]").forEach((element) => {
      const select = () => {
        state = selectScenario(state, element.dataset.scenarioId);
        renderModel();
      };
      element.addEventListener("click", select);
      element.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select();
        }
      });
    });
    content.querySelector("[data-edit-inputs]")?.addEventListener("click", () => callbacks.onEditInputs?.());
    chartCleanup();
    chartCleanup = renderCharts(content, chartData, (scenarioId) => {
      state = selectScenario(state, scenarioId);
      renderModel();
    });
    try {
      callbacks.onRendered?.({
        display,
        displayConfig: { ...state.display },
        selectedScenarioId: state.selectedScenarioId,
      });
    } catch (error) {
      console.error("teaching guide render callback failed", error);
    }
  }

  return {
    render(result, submittedInput, display) {
      state = {
        ...attachResult({ submittedInput: submittedInput || null }, result),
        display: { ...DEFAULT_DISPLAY, ...(display || {}) },
      };
      root.hidden = false;
      const status = document.getElementById("workbench-status");
      const boundary = document.getElementById("workbench-boundary");
      if (status) {
        status.textContent = "已完成 · 原始结果保留";
        status.classList.remove("muted");
      }
      if (boundary) {
        boundary.textContent = `${result.report_year} · ${result.departure_port} → ${result.arrival_port} · ${result.currency} · 航次级 FuelEU / EU ETS 估算，不构成年度罚款或采购建议。`;
      }
      renderModel();
    },
    clear(status = "尚未计算") {
      chartCleanup();
      chartCleanup = () => {};
      state = null;
      root.hidden = true;
      const content = root.querySelector("#workbench-content");
      if (content) content.innerHTML = `<div class="workbench-empty"><strong>${escapeHtml(status)}</strong><p>修改输入后需要重新计算。</p></div>`;
      const statusElement = document.getElementById("workbench-status");
      const boundary = document.getElementById("workbench-boundary");
      if (statusElement) {
        statusElement.textContent = status;
        statusElement.classList.add("muted");
      }
      if (boundary) boundary.textContent = "当前输入尚未生成可用结果。";
    },
    setDisplay(display) {
      if (state) {
        state.display = { ...state.display, ...(display || {}) };
        renderModel();
      }
    },
    destroy() {
      chartCleanup();
      chartCleanup = () => {};
      state = null;
    },
  };
}
