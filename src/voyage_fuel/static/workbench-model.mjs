const GOALS = Object.freeze({
  cost: "cost_min_scenario_id",
  target: "target_min_cost_scenario_id",
  improvement: "max_improvement_scenario_id",
});

function scenarioRows(result) {
  return new Map((result?.scenarios || []).map((row) => [row.scenario_id, row]));
}

const GOAL_META = Object.freeze({
  cost: { label: "当前模型成本最低", role: "当前模型成本最低", summaryKey: "cost_min_scenario_id" },
  target: { label: "达到 GHGI 参考线的最低成本", role: "达标最低成本", summaryKey: "target_min_cost_scenario_id" },
  improvement: { label: "报告方案中的最大合规改善", role: "报告方案最大改善", summaryKey: "max_improvement_scenario_id" },
});

const THRESHOLD_META = Object.freeze([
  ["x_budget", "预算边界", "预算"],
  ["x_supply", "供应量边界", "供应"],
  ["x_cap", "最大混兑边界", "最大混兑"],
  ["x_target_min", "最低达标比例", "最低达标"],
  ["x_target_min_cost", "达标最低成本比例", "达标最低成本"],
  ["x_max_improvement", "最大改善边界", "最大改善"],
  ["x_cost_min", "当前成本最低比例", "成本最低"],
]);

function recommendationFor(result, goal, scenarioId) {
  const recommendations = result?.recommendations || [];
  if (goal === "cost") {
    return recommendations.find((row) => row.recommendation_id === "CURRENT_MODEL_COST_MIN") || null;
  }
  if (goal === "target") {
    return recommendations.find((row) =>
      row.recommendation_id.startsWith("TARGET_MIN_COST:") && row.scenario_id === scenarioId
    ) || null;
  }
  return recommendations.find((row) =>
    row.recommendation_id.startsWith("MAX_COMPLIANCE_IMPROVEMENT:") && row.scenario_id === scenarioId
  ) || null;
}

function recommendationForGoal(result, goal, scenarioId) {
  const exact = recommendationFor(result, goal, scenarioId);
  if (exact) return exact;
  if (goal === "cost") return null;
  const prefix = goal === "target" ? "TARGET_MIN_COST:" : "MAX_COMPLIANCE_IMPROVEMENT:";
  return (result?.recommendations || []).find((row) =>
    row.recommendation_id.startsWith(prefix) && (!scenarioId || row.scenario_id === scenarioId)
  ) || (result?.recommendations || []).find((row) => row.recommendation_id.startsWith(prefix)) || null;
}

function candidateInput(submittedInput, candidateId) {
  return (submittedInput?.candidates || []).find((candidate) => candidate.candidateId === candidateId) || null;
}

function ratioMatches(left, right) {
  if (left === null || left === undefined || right === null || right === undefined) return false;
  const leftNumber = Number(left);
  const rightNumber = Number(right);
  return Number.isFinite(leftNumber) && Number.isFinite(rightNumber) && leftNumber === rightNumber;
}

function scenarioRole(row, result, submittedInput) {
  if (row.scenario_id === "B0") return "基准方案";
  const summary = result?.decision_summary || {};
  if (row.scenario_id === summary.target_min_cost_scenario_id) return "达标最低成本";
  if (row.scenario_id === summary.max_improvement_scenario_id) return "报告方案最大改善";
  const input = candidateInput(submittedInput, row.candidate_id);
  if ((input?.specifiedBlendRatios || []).some((ratio) => ratioMatches(ratio, row.result?.ratio))) {
    return "用户指定比例";
  }
  return "报告方案";
}

function metricChange(key, label, unit, selected, baseline) {
  const delta = selected?.deltas?.[key]?.delta ?? null;
  return {
    key,
    label,
    unit,
    baseline: baseline?.result?.[key] ?? baseline?.[key] ?? null,
    selected: selected?.result?.[key] ?? selected?.[key] ?? null,
    delta,
  };
}

function fuelEuMetric(row, key) {
  return row?.result?.fuel_eu?.[key] ?? null;
}

function buildSelectedChanges(selected, baseline) {
  const selectedResult = selected?.result || {};
  const baselineResult = baseline?.result || {};
  const delta = (key) => selected?.deltas?.[key]?.delta ?? null;
  return [
    {
      key: "ratio",
      label: "候选燃料质量占比",
      unit: "ratio",
      baseline: baselineResult.ratio ?? null,
      selected: selectedResult.ratio ?? null,
      delta: delta("ratio"),
    },
    {
      key: "candidate_mass_tonnes",
      label: "候选燃料用量",
      unit: "mass",
      baseline: baselineResult.candidate_mass_tonnes ?? null,
      selected: selectedResult.candidate_mass_tonnes ?? null,
      delta: delta("candidate_mass_tonnes"),
    },
    {
      key: "fuel_cost",
      label: "燃料成本",
      unit: "price",
      baseline: baselineResult.fuel_cost ?? null,
      selected: selectedResult.fuel_cost ?? null,
      delta: delta("fuel_cost"),
    },
    {
      key: "eua_cost",
      label: "EU ETS 成本",
      unit: "price",
      baseline: baselineResult.eu_ets?.eua_cost ?? null,
      selected: selectedResult.eu_ets?.eua_cost ?? null,
      delta: delta("eua_cost"),
    },
    {
      key: "model_cost",
      label: "模型成本",
      unit: "price",
      baseline: baselineResult.model_cost ?? null,
      selected: selectedResult.model_cost ?? null,
      delta: delta("model_cost"),
    },
    {
      key: "fueleu_ghgi_actual_g_per_mj",
      label: "FuelEU GHGI",
      unit: "intensity",
      baseline: fuelEuMetric(baseline, "ghgi_actual_g_per_mj"),
      selected: fuelEuMetric(selected, "ghgi_actual_g_per_mj"),
      delta: delta("fueleu_ghgi_actual_g_per_mj"),
    },
    {
      key: "fueleu_compliance_balance_t",
      label: "FuelEU 合规余额",
      unit: "gas",
      baseline: fuelEuMetric(baseline, "compliance_balance_t"),
      selected: fuelEuMetric(selected, "compliance_balance_t"),
      delta: delta("fueleu_compliance_balance_t"),
    },
    {
      key: "fueleu_indicative_penalty_eur",
      label: "FuelEU 指示性金额",
      unit: "eur",
      baseline: fuelEuMetric(baseline, "indicative_penalty_eur"),
      selected: fuelEuMetric(selected, "indicative_penalty_eur"),
      delta: delta("fueleu_indicative_penalty_eur"),
    },
  ];
}

function buildGoalCards(result, scenarioById) {
  const summary = result?.decision_summary || {};
  const hasCandidates = (result?.candidate_results || []).length > 0;
  return Object.entries(GOAL_META).map(([key, meta]) => {
    const scenarioId = summary[meta.summaryKey] || null;
    const recommendation = recommendationForGoal(result, key, scenarioId);
    const available = Boolean(scenarioId && scenarioById.has(scenarioId));
    return {
      key,
      label: meta.label,
      role: meta.role,
      scenarioId,
      availability: available ? "available" : hasCandidates ? "unavailable" : "not_applicable",
      reason: recommendation?.reason || null,
      assumptions: recommendation?.assumptions || [],
      status: recommendation?.status || (available ? "CONDITIONAL" : "UNAVAILABLE"),
    };
  });
}

function buildScenarioDisplayRows(result, submittedInput, scenarioById) {
  const summary = result?.decision_summary || {};
  return [...scenarioById.values()].map((row) => {
    const scenarioResult = row.result || {};
    return {
      scenarioId: row.scenario_id,
      candidateId: row.candidate_id,
      label: row.scenario_id === "B0" ? "基准方案" : row.candidate_id || "候选方案",
      role: scenarioRole(row, result, submittedInput),
      ratio: scenarioResult.ratio ?? null,
      candidateMassTonnes: scenarioResult.candidate_mass_tonnes ?? null,
      modelCost: scenarioResult.model_cost ?? null,
      costDelta: row.deltas?.model_cost?.delta ?? null,
      ghgi: fuelEuMetric(row, "ghgi_actual_g_per_mj"),
      ghgiDelta: row.deltas?.fueleu_ghgi_actual_g_per_mj?.delta ?? null,
      complianceBalance: fuelEuMetric(row, "compliance_balance_t"),
      complianceImprovement: scenarioResult.compliance_improvement_tco2e ?? null,
      calculationStatus: row.calculation_status || null,
      constraintStatus: scenarioResult.constraint_status || null,
      executionStatus: scenarioResult.execution_status || null,
      recommendedGoals: Object.entries(GOAL_META)
        .filter(([, meta]) => summary[meta.summaryKey] === row.scenario_id)
        .map(([key]) => key),
    };
  });
}

function buildSensitivity(result, submittedInput, scenarioById) {
  const candidates = (result?.candidate_results || []).map((candidate) => {
    const voyage = candidate.voyage_result || {};
    const constraints = voyage.constraints || {};
    const economics = voyage.economics || {};
    return {
      candidateId: candidate.candidate_id,
      label: candidateInput(submittedInput, candidate.candidate_id)?.pathId || candidate.candidate_id,
      currentPrice: candidateInput(submittedInput, candidate.candidate_id)?.pricePerTonne ?? null,
      currentEuaPrice: submittedInput?.euaPricePerTCO2e ?? null,
      targetStatus: constraints.target_status || null,
      warnings: constraints.warning_codes || [],
      thresholds: THRESHOLD_META.map(([key, label, shortLabel]) => ({
        key,
        label,
        shortLabel,
        value: constraints[key] ?? null,
      })),
      pcBreakEven: economics.pc_break_even ?? null,
      peBreakEven: economics.pe_break_even ?? null,
      peBreakEvenStatus: economics.pe_break_even_status || null,
      reportPoints: [...scenarioById.values()]
        .filter((row) => row.candidate_id === candidate.candidate_id)
        .map((row) => ({
          scenarioId: row.scenario_id,
          ratio: row.result?.ratio ?? null,
          role: scenarioRole(row, result, submittedInput),
        })),
    };
  });
  return {
    candidates,
    switchPoints: (result?.economics?.switch_points || []).map((point) => ({
      fromScenarioId: point.from_scenario_id,
      toScenarioId: point.to_scenario_id,
      fromCandidateId: point.from_candidate_id,
      toCandidateId: point.to_candidate_id,
      valueStar: point.value_star ?? null,
    })),
  };
}

export function buildWorkbenchDisplayModel(result, submittedInput, selectedScenarioId = null, viewState = null) {
  const base = buildWorkbenchModel(result, submittedInput);
  const selectedId = selectedScenarioId && base.scenarioById.has(selectedScenarioId)
    ? selectedScenarioId : base.selectedScenarioId;
  const selected = base.scenarioById.get(selectedId) || null;
  const baseline = base.scenarioById.get("B0") || null;
  const activeGoal = viewState?.activeGoal || base.activeGoal;
  const recommendedScenarioId = viewState?.recommendedScenarioId ?? base.recommendedScenarioId;
  return {
    ...base,
    goalCards: buildGoalCards(result, base.scenarioById),
    scenarioRows: buildScenarioDisplayRows(result, submittedInput, base.scenarioById),
    selectedDetail: {
      scenarioId: selectedId,
      compareToScenarioId: "B0",
      source: selectedId === recommendedScenarioId ? "goal" : "manual",
      changes: buildSelectedChanges(selected, baseline),
      recommendation: selectedId === recommendedScenarioId && activeGoal
        ? recommendationForGoal(result, activeGoal, recommendedScenarioId)
        : null,
    },
    sensitivity: buildSensitivity(result, submittedInput, base.scenarioById),
  };
}

export function buildWorkbenchModel(result, submittedInput) {
  const rows = scenarioRows(result);
  const summary = result?.decision_summary || {};
  const hasCandidates = (result?.candidate_results || []).length > 0;
  const activeGoal = "cost";
  const recommendedScenarioId = summary[GOALS[activeGoal]] || null;
  const selectedScenarioId = recommendedScenarioId
    || (rows.has("B0") ? "B0" : null);
  const recommendation = recommendationFor(result, activeGoal, recommendedScenarioId);
  const goalAvailability = recommendedScenarioId
    ? "available"
    : hasCandidates ? "unavailable" : "not_applicable";
  return {
    result,
    activeGoal,
    recommendedScenarioId,
    selectedScenarioId,
    selectionSource: recommendedScenarioId ? "goal" : "manual",
    goalAvailability,
    goalReasonCodes: recommendation ? [recommendation.reason] : [],
    scenarioById: rows,
    submittedInput: submittedInput || null,
  };
}

export function selectGoal(model, goal) {
  if (!(goal in GOALS)) throw new Error("UNKNOWN_GOAL");
  const summary = model.result?.decision_summary || {};
  const recommendedScenarioId = summary[GOALS[goal]] || null;
  const recommendation = recommendationFor(model.result, goal, recommendedScenarioId);
  const hasCandidates = (model.result?.candidate_results || []).length > 0;
  return {
    ...model,
    activeGoal: goal,
    recommendedScenarioId,
    selectedScenarioId: recommendedScenarioId || (model.scenarioById.has("B0") ? "B0" : null),
    selectionSource: recommendedScenarioId ? "goal" : "manual",
    goalAvailability: recommendedScenarioId
      ? "available"
      : hasCandidates ? "unavailable" : "not_applicable",
    goalReasonCodes: recommendation ? [recommendation.reason] : [],
  };
}

export function selectScenario(model, scenarioId) {
  if (!model.scenarioById.has(scenarioId)) {
    return { ...model, selectionUnavailable: scenarioId };
  }
  return {
    ...model,
    selectedScenarioId: scenarioId,
    selectionSource: scenarioId === model.recommendedScenarioId ? "goal" : "manual",
    selectionUnavailable: null,
  };
}

export function attachResult(model, result) {
  return buildWorkbenchModel(result, model.submittedInput);
}

export function buildChartData(result, scenarioId, display = {}) {
  const rows = scenarioRows(result);
  const selected = rows.get(scenarioId);
  const baseline = result?.baseline_scenario;
  const summary = result?.decision_summary || {};
  return {
    cost: {
      status: selected && baseline && selected.result?.model_cost != null
        ? "available" : "unavailable",
      currency: result?.currency || "",
      displayDecimals: display.price ?? 2,
      items: selected ? [
        { key: "baseline_total", rawValue: baseline?.model_cost ?? null },
        { key: "fuel_delta", rawValue: selected.deltas?.fuel_cost?.delta ?? null },
        { key: "ets_delta", rawValue: selected.deltas?.eua_cost?.delta ?? null },
        { key: "selected_total", rawValue: selected.result?.model_cost ?? null },
      ] : [],
    },
    ghgi: {
      status: selected?.result?.fuel_eu?.target_g_per_mj != null ? "available" : "unavailable",
      unit: "gCO2eq/MJ",
      displayDecimals: display.intensity ?? 4,
      baseline: baseline?.fuel_eu?.ghgi_actual_g_per_mj ?? null,
      selected: selected?.result?.fuel_eu?.ghgi_actual_g_per_mj ?? null,
      target: selected?.result?.fuel_eu?.target_g_per_mj ?? null,
    },
    comparison: (result?.scenarios || []).map((row) => {
      const roleKeys = [];
      if (row.scenario_id === "B0") roleKeys.push("b0");
      if (row.scenario_id === summary.cost_min_scenario_id) roleKeys.push("cost-min");
      if (row.scenario_id === summary.target_min_cost_scenario_id) roleKeys.push("target-min-cost");
      if (row.scenario_id === summary.max_improvement_scenario_id) roleKeys.push("max-improvement");
      if (row.result?.constraint_status && row.result.constraint_status !== "FEASIBLE") {
        roleKeys.push("constraint-unverified");
      }
      return {
        scenarioId: row.scenario_id,
        costDelta: row.deltas?.model_cost?.delta ?? null,
        improvement: row.result?.compliance_improvement_tco2e ?? null,
        status: row.result?.constraint_status,
        selected: row.scenario_id === scenarioId,
        roleKeys,
        plottable: row.deltas?.model_cost?.delta != null
          && row.result?.compliance_improvement_tco2e != null,
        feasible: row.result?.constraint_status === "FEASIBLE"
          && row.deltas?.model_cost?.delta != null
          && row.result?.compliance_improvement_tco2e != null,
      };
    }),
  };
}
