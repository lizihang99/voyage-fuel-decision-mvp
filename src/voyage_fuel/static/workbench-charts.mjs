import { formatDecimalStringScaled } from "./display-values.mjs";

export function renderCharts(root, chartData, onScenarioSelect) {
  const cleanup = [];
  if (!root) return () => {};
  const chartButtons = root.querySelectorAll("[data-chart-scenario]");
  chartButtons.forEach((button) => {
    const listener = () => onScenarioSelect?.(button.dataset.chartScenario);
    button.addEventListener("click", listener);
    const keyListener = (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onScenarioSelect?.(button.dataset.chartScenario);
      }
    };
    button.addEventListener("keydown", keyListener);
    cleanup.push(() => {
      button.removeEventListener("click", listener);
      button.removeEventListener("keydown", keyListener);
    });
  });
  root.dataset.chartState = chartData?.cost?.status || "unavailable";
  return () => cleanup.forEach((dispose) => dispose());
}

function finite(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function escapeSvg(value) {
  return String(value ?? "").replace(/[&<>"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
  }[character]));
}

function formatChartValue(value, decimals = 2, power10 = 0) {
  if (value === null || value === undefined || value === "") return "未提供";
  return formatDecimalStringScaled(String(value), decimals, power10);
}

function formatPercent(value, decimals = 4) {
  return `${formatChartValue(value, decimals, 2)}%`;
}

export function buildSvgWaterfall(costData, width = 560, height = 220) {
  if (costData?.status !== "available" || !Array.isArray(costData.items) || costData.items.length < 4) return "";
  const values = new Map(costData.items.map((item) => [item.key, finite(item.rawValue)]));
  if ([...values.values()].some((value) => value === null)) return "";
  const items = [
    { key: "baseline_total", label: "B0 模型成本", kind: "total" },
    { key: "fuel_delta", label: "燃料成本变化", kind: "delta" },
    { key: "ets_delta", label: "EU ETS 成本变化", kind: "delta" },
    { key: "selected_total", label: "当前方案模型成本", kind: "total" },
  ];
  const baseline = values.get("baseline_total");
  const fuelDelta = values.get("fuel_delta");
  const etsDelta = values.get("ets_delta");
  const selectedTotal = values.get("selected_total");
  const runningValues = [0, baseline, baseline + fuelDelta, baseline + fuelDelta + etsDelta, selectedTotal];
  const min = Math.min(...runningValues);
  const max = Math.max(...runningValues, min + 1);
  const chartTop = 20;
  const chartBottom = height - 44;
  const slot = (width - 70) / items.length;
  const barWidth = Math.min(84, slot - 20);
  const y = (value) => chartBottom - ((value - min) / (max - min)) * (chartBottom - chartTop);
  const steps = [
    { start: 0, end: baseline },
    { start: baseline, end: baseline + fuelDelta },
    { start: baseline + fuelDelta, end: baseline + fuelDelta + etsDelta },
    { start: 0, end: selectedTotal },
  ];
  const labelLines = [
    ["B0", "模型成本"],
    ["燃料成本", "变化"],
    ["EU ETS", "成本变化"],
    ["当前方案", "模型成本"],
  ];
  const bars = items.map((item, index) => {
    const { start, end } = steps[index];
    const x = 45 + index * slot + (slot - barWidth) / 2;
    const top = y(Math.max(start, end));
    const bottom = y(Math.min(start, end));
    const h = Math.max(2, bottom - top);
    const rawValue = values.get(item.key);
    const className = item.kind === "delta" ? (end >= start ? "bar-negative" : "bar-positive") : "bar-total";
    const valueLabel = formatChartValue(rawValue, costData.displayDecimals ?? 2);
    const labelSvg = labelLines[index].map((line, lineIndex) =>
      `<tspan x="${(x + barWidth / 2).toFixed(2)}" dy="${lineIndex === 0 ? 0 : 12}">${escapeSvg(line)}</tspan>`
    ).join("");
    return `<rect class="${className}" x="${x.toFixed(2)}" y="${top.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${h.toFixed(2)}" rx="2"><title>${escapeSvg(item.label)}: ${escapeSvg(costData.currency)} ${escapeSvg(valueLabel)}</title></rect>
      <text class="value" x="${(x + barWidth / 2).toFixed(2)}" y="${Math.max(13, top - 5).toFixed(2)}" text-anchor="middle">${escapeSvg(valueLabel)}</text>
      <text class="label" x="${(x + barWidth / 2).toFixed(2)}" y="${height - 28}" text-anchor="middle">${labelSvg}</text>`;
  }).join("");
  const connectors = steps.slice(0, -1).map((step, index) => {
    const fromX = 45 + index * slot + (slot + barWidth) / 2;
    const toX = 45 + (index + 1) * slot + (slot - barWidth) / 2;
    return `<line class="connector" x1="${fromX.toFixed(2)}" y1="${y(step.end).toFixed(2)}" x2="${toX.toFixed(2)}" y2="${y(step.end).toFixed(2)}"></line>`;
  }).join("");
  return `<svg class="workbench-waterfall" viewBox="0 0 ${width} ${height}" role="img" aria-label="模型成本变化瀑布图">
    <line class="axis" x1="35" y1="${y(0).toFixed(2)}" x2="${width - 12}" y2="${y(0).toFixed(2)}"></line>
    ${connectors}
    ${bars}
    <text class="unit" x="${width - 12}" y="14" text-anchor="end">${escapeSvg(costData.currency || "")} · 累计变化</text>
  </svg>`;
}

export function buildSvgGhgi(ghgiData, width = 560, height = 190) {
  if (ghgiData?.status !== "available") return "";
  const baseline = finite(ghgiData.baseline);
  const selected = finite(ghgiData.selected);
  const target = finite(ghgiData.target);
  if (baseline === null || selected === null || target === null) return "";
  const max = Math.max(baseline, selected, target, 1);
  const left = 110;
  const right = width - 24;
  const scale = (value) => left + (value / max) * (right - left);
  const rows = [
    ["B0", baseline, "bar-baseline"],
    ["当前方案", selected, "bar-selected"],
  ];
  const bars = rows.map(([label, value, className], index) => {
    const y = 44 + index * 48;
    return `<text class="label" x="12" y="${y + 14}">${label}</text>
      <rect class="${className}" x="${left}" y="${y}" width="${Math.max(2, scale(value) - left).toFixed(2)}" height="22" rx="2"></rect>
      <text class="value" x="${Math.min(right, scale(value) + 8).toFixed(2)}" y="${y + 15}">${formatChartValue(value, ghgiData.displayDecimals ?? 4)}</text>`;
  }).join("");
  const targetX = scale(target);
  return `<svg class="workbench-ghgi" viewBox="0 0 ${width} ${height}" role="img" aria-label="FuelEU GHGI 与参考线对比图">
    <line class="target-line" x1="${targetX.toFixed(2)}" y1="24" x2="${targetX.toFixed(2)}" y2="${height - 24}"></line>
    <text class="target-label" x="${Math.min(right - 4, targetX + 6).toFixed(2)}" y="18">参考线 ${formatChartValue(target, ghgiData.displayDecimals ?? 4)} ${escapeSvg(ghgiData.unit || "gCO2eq/MJ")}</text>
    ${bars}
    <text class="unit" x="${width - 12}" y="${height - 8}" text-anchor="end">${escapeSvg(ghgiData.unit || "gCO2eq/MJ")}</text>
  </svg>`;
}

export function buildSvgRatioRail(candidate, width = 640, height = 190, ratioDecimals = 4) {
  const thresholds = (candidate?.thresholds || []).filter((item) => finite(item.value) !== null);
  const reportPoints = (candidate?.reportPoints || []).filter((item) => finite(item.ratio) !== null);
  if (!thresholds.length && !reportPoints.length) return "";
  const left = 30;
  const right = width - 24;
  const axisY = 110;
  const x = (value) => left + Math.max(0, Math.min(1, value)) * (right - left);
  const thresholdMarks = thresholds.map((item, index) => {
    const px = x(finite(item.value));
    const y = 18 + index * 12;
    const shortLabel = item.shortLabel || item.label;
    const anchor = px < width / 2 ? "start" : "end";
    return `<line class="threshold-line" x1="${px.toFixed(2)}" y1="${axisY - 8}" x2="${px.toFixed(2)}" y2="${axisY + 8}"></line>
      <text class="marker-label" x="${px.toFixed(2)}" y="${y}" text-anchor="${anchor}"><title>${escapeSvg(item.label)}: ${escapeSvg(formatPercent(item.value, ratioDecimals))}</title>T${index + 1}</text>`;
  }).join("");
  const reportMarks = reportPoints.map((item, index) => {
    const px = x(finite(item.ratio));
    const py = axisY + (index % 2 === 0 ? -8 : 8);
    const ratioLabel = formatPercent(item.ratio, ratioDecimals);
    return `<circle class="report-point" cx="${px.toFixed(2)}" cy="${py}" r="6" tabindex="0" role="img" aria-label="${escapeSvg(item.role)} ${escapeSvg(ratioLabel)}"><title>${escapeSvg(item.role)} ${escapeSvg(ratioLabel)}</title></circle>
      <text class="report-label" x="${px.toFixed(2)}" y="${py + (index % 2 === 0 ? -11 : 19)}" text-anchor="middle">R${index + 1}</text>`;
  }).join("");
  return `<svg class="workbench-ratio-rail" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeSvg(candidate?.candidateId || "候选燃料")} 比例边界轨道">
    <line class="rail" x1="${left}" y1="${axisY}" x2="${right}" y2="${axisY}"></line>
    <text class="legend-label" x="${left}" y="12">T = 连续边界</text>
    <text class="legend-label" x="${left + 88}" y="12">R = 实际报告点</text>
    <text class="axis-label" x="${left}" y="${height - 12}">0%</text>
    <text class="axis-label" x="${right}" y="${height - 12}" text-anchor="end">100%</text>
    ${thresholdMarks}
    ${reportMarks}
  </svg>`;
}

export function buildSvgThresholdLanes(candidate, width = 640, ratioDecimals = 4) {
  const thresholds = (candidate?.thresholds || []).filter((item) => finite(item.value) !== null);
  const reportPoints = (candidate?.reportPoints || []).filter((item) => finite(item.ratio) !== null);
  if (!thresholds.length && !reportPoints.length) return "";
  const left = 178;
  const right = width - 92;
  const rowHeight = 28;
  const headerHeight = 30;
  const laneCount = thresholds.length + (reportPoints.length ? 1 : 0);
  const height = headerHeight + laneCount * rowHeight + 28;
  const x = (value) => left + Math.max(0, Math.min(1, value)) * (right - left);
  const thresholdRows = thresholds.map((item, index) => {
    const y = headerHeight + index * rowHeight + 15;
    const value = finite(item.value);
    const markerX = x(value);
    return `<text class="lane-label" x="12" y="${y + 4}">${escapeSvg(item.label)}</text>
      <line class="lane-track" x1="${left}" y1="${y}" x2="${right}" y2="${y}"></line>
      <line class="lane-tick" x1="${left}" y1="${y - 5}" x2="${left}" y2="${y + 5}"></line>
      <line class="lane-tick" x1="${right}" y1="${y - 5}" x2="${right}" y2="${y + 5}"></line>
      <circle class="lane-threshold-point" cx="${markerX.toFixed(2)}" cy="${y}" r="5"><title>${escapeSvg(item.label)}: ${escapeSvg(formatPercent(item.value, ratioDecimals))}</title></circle>
      <text class="lane-value" x="${width - 12}" y="${y + 4}" text-anchor="end">${escapeSvg(formatPercent(item.value, ratioDecimals))}</text>`;
  }).join("");
  const reportY = headerHeight + thresholds.length * rowHeight + 15;
  const reportRows = reportPoints.length
    ? `<text class="lane-label" x="12" y="${reportY + 4}">实际报告点</text>
      <line class="lane-track report-track" x1="${left}" y1="${reportY}" x2="${right}" y2="${reportY}"></line>
      ${reportPoints.map((item, index) => {
        const markerX = x(finite(item.ratio));
        return `<circle class="lane-report-point" cx="${markerX.toFixed(2)}" cy="${reportY}" r="5"><title>${escapeSvg(item.role)}: ${escapeSvg(formatPercent(item.ratio, ratioDecimals))}</title></circle>
          <text class="lane-report-label" x="${markerX.toFixed(2)}" y="${reportY - 9 - (index % 2) * 10}" text-anchor="middle">R${index + 1}</text>`;
      }).join("")}`
    : "";
  return `<svg class="workbench-threshold-lanes" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeSvg(candidate?.candidateId || "候选燃料")} 分层比例边界图">
    <text class="lane-axis-label" x="${left}" y="16">0%</text>
    <text class="lane-axis-label" x="${right}" y="16" text-anchor="end">100%</text>
    ${thresholdRows}
    ${reportRows}
  </svg>`;
}

export function buildSvgSwitchRail(switchPoints, width = 640, height = 150, priceDecimals = 2) {
  const points = (switchPoints || []).filter((point) => finite(point.valueStar) !== null);
  if (!points.length) return "";
  const max = Math.max(...points.map((point) => finite(point.valueStar)), 1);
  const left = 30;
  const right = width - 24;
  const axisY = 74;
  const x = (value) => left + (value / max) * (right - left);
  const marks = points.map((point, index) => {
    const value = finite(point.valueStar);
    const px = x(value);
    return `<line class="switch-line" x1="${px.toFixed(2)}" y1="${axisY - 18}" x2="${px.toFixed(2)}" y2="${axisY + 18}"></line>
      <circle class="switch-point" cx="${px.toFixed(2)}" cy="${axisY}" r="6"></circle>
      <text class="switch-label" x="${px.toFixed(2)}" y="${index % 2 === 0 ? 30 : 48}" text-anchor="middle">${escapeSvg(formatChartValue(point.valueStar, priceDecimals))}</text>
      <text class="switch-caption" x="${px.toFixed(2)}" y="${height - 22}" text-anchor="middle">${escapeSvg(point.fromScenarioId)} → ${escapeSvg(point.toScenarioId)}</text>`;
  }).join("");
  return `<svg class="workbench-switch-rail" viewBox="0 0 ${width} ${height}" role="img" aria-label="方案切换点价值轴">
    <line class="rail" x1="${left}" y1="${axisY}" x2="${right}" y2="${axisY}"></line>
    <text class="axis-label" x="${left}" y="${height - 6}">0</text>
    <text class="axis-label" x="${right}" y="${height - 6}" text-anchor="end">${escapeSvg(formatChartValue(max, priceDecimals))}</text>
    ${marks}
  </svg>`;
}

export function buildSvgScatter(chartData, width = 420, height = 220) {
  const points = (chartData?.comparison || []).filter((point) => point.plottable);
  if (!points.length) return "";
  const costs = points.map((point) => Number(point.costDelta));
  const improvements = points.map((point) => Number(point.improvement));
  if ([...costs, ...improvements].some((value) => !Number.isFinite(value))) return "";
  const rawMinCost = Math.min(...costs, 0);
  const rawMaxCost = Math.max(...costs, 0);
  const rawMinImprovement = Math.min(...improvements, 0);
  const rawMaxImprovement = Math.max(...improvements, 0);
  const costSpan = Math.max(Math.abs(rawMinCost), Math.abs(rawMaxCost), 1);
  const improvementSpan = Math.max(Math.abs(rawMinImprovement), Math.abs(rawMaxImprovement), 1);
  const minCost = rawMinCost < 0 ? rawMinCost : -costSpan * 0.12;
  const maxCost = rawMaxCost > 0 ? rawMaxCost : costSpan * 0.12;
  const minImprovement = rawMinImprovement < 0 ? rawMinImprovement : -improvementSpan * 0.12;
  const maxImprovement = rawMaxImprovement > 0 ? rawMaxImprovement : improvementSpan * 0.12;
  const plotLeft = 42;
  const plotRight = width - 16;
  const plotTop = 24;
  const plotBottom = height - 38;
  const x = (value) => plotLeft + ((value - minCost) / (maxCost - minCost || 1)) * (plotRight - plotLeft);
  const y = (value) => plotBottom - ((value - minImprovement) / (maxImprovement - minImprovement || 1)) * (plotBottom - plotTop);
  const xZeroValue = x(0);
  const yZeroValue = y(0);
  const quadrantRects = [
    `<rect class="quadrant quadrant-favorable" x="${plotLeft}" y="${plotTop}" width="${Math.max(0, xZeroValue - plotLeft).toFixed(2)}" height="${Math.max(0, yZeroValue - plotTop).toFixed(2)}"></rect>`,
    `<rect class="quadrant quadrant-tradeoff" x="${xZeroValue.toFixed(2)}" y="${plotTop}" width="${Math.max(0, plotRight - xZeroValue).toFixed(2)}" height="${Math.max(0, yZeroValue - plotTop).toFixed(2)}"></rect>`,
    `<rect class="quadrant quadrant-cost-saving" x="${plotLeft}" y="${yZeroValue.toFixed(2)}" width="${Math.max(0, xZeroValue - plotLeft).toFixed(2)}" height="${Math.max(0, plotBottom - yZeroValue).toFixed(2)}"></rect>`,
    `<rect class="quadrant quadrant-worse" x="${xZeroValue.toFixed(2)}" y="${yZeroValue.toFixed(2)}" width="${Math.max(0, plotRight - xZeroValue).toFixed(2)}" height="${Math.max(0, plotBottom - yZeroValue).toFixed(2)}"></rect>`,
  ].join("");
  const circles = points.map((point, index) => {
    const px = x(Number(point.costDelta));
    const py = y(Number(point.improvement));
    const classes = ["plot-point", ...(point.roleKeys || [])];
    if (point.selected) classes.push("selected");
    const selectedLabel = point.selected ? " · 当前查看" : "";
    const label = point.scenarioId === "B0" ? "B0" : `P${index}`;
    const labelX = point.scenarioId === "B0" ? px + 10 : px;
    const labelY = point.scenarioId === "B0" ? py + 14 : py - 9;
    return `<circle class="${classes.join(" ")}" cx="${px.toFixed(2)}" cy="${py.toFixed(2)}" r="${point.selected ? 7 : 5}" data-chart-scenario="${point.scenarioId}" tabindex="0" role="button" aria-label="${point.scenarioId}${selectedLabel}"><title>${point.scenarioId}${selectedLabel} · ${point.costDelta} / ${point.improvement}</title></circle>
      <text class="point-label" x="${labelX.toFixed(2)}" y="${labelY.toFixed(2)}" text-anchor="middle">${escapeSvg(label)}</text>`;
  }).join("");
  const xZero = xZeroValue.toFixed(2);
  const yZero = yZeroValue.toFixed(2);
  return `<svg class="workbench-scatter" viewBox="0 0 ${width} ${height}" role="img" aria-label="成本变化与合规改善散点图">
    ${quadrantRects}
    <line class="axis" x1="${plotLeft}" y1="${plotBottom}" x2="${plotRight}" y2="${plotBottom}"></line>
    <line class="axis" x1="${plotLeft}" y1="${plotTop}" x2="${plotLeft}" y2="${plotBottom}"></line>
    <line class="zero" x1="${xZero}" y1="${plotTop}" x2="${xZero}" y2="${plotBottom}"></line>
    <line class="zero" x1="${plotLeft}" y1="${yZero}" x2="${plotRight}" y2="${yZero}"></line>
    <text class="quadrant-label" x="${plotLeft + 8}" y="${plotTop + 16}">成本更低 · 改善更多</text>
    <text class="quadrant-label" x="${plotRight - 8}" y="${plotTop + 16}" text-anchor="end">成本更高 · 改善更多</text>
    <text class="quadrant-label" x="${plotLeft + 8}" y="${plotBottom - 8}">成本更低 · 改善减少</text>
    <text class="quadrant-label" x="${plotRight - 8}" y="${plotBottom - 8}" text-anchor="end">成本更高 · 改善减少</text>
    <text class="tick-label" x="${plotLeft}" y="${height - 18}">${escapeSvg(formatChartValue(minCost, 0))}</text>
    <text class="tick-label" x="${xZero}" y="${height - 18}" text-anchor="middle">0</text>
    <text class="tick-label" x="${plotRight}" y="${height - 18}" text-anchor="end">${escapeSvg(formatChartValue(maxCost, 0))}</text>
    <text class="tick-label" x="34" y="${plotTop + 4}" text-anchor="end">${escapeSvg(formatChartValue(maxImprovement, 0))}</text>
    <text class="tick-label" x="34" y="${yZero + 4}" text-anchor="end">0</text>
    <text class="tick-label" x="34" y="${plotBottom + 4}" text-anchor="end">${escapeSvg(formatChartValue(minImprovement, 0))}</text>
    <text x="${plotRight}" y="${height - 4}" text-anchor="end">相对 B0 净成本变化（案例币种）</text>
    <text x="8" y="14">相对 B0 合规改善（tCO2e）</text>
    <text class="legend-label" x="${plotRight}" y="14" text-anchor="end">B0 基准 · 黑圈当前查看 · 虚线约束未验证</text>
    ${circles}
  </svg>`;
}
