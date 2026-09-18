import test from "node:test";
import assert from "node:assert/strict";

import {
  buildChartData,
  buildWorkbenchDisplayModel,
  buildWorkbenchModel,
  selectGoal,
  selectScenario,
} from "../../src/voyage_fuel/static/workbench-model.mjs";
import {
  buildSvgGhgi,
  buildSvgRatioRail,
  buildSvgScatter,
  buildSvgSwitchRail,
  buildSvgThresholdLanes,
  buildSvgWaterfall,
} from "../../src/voyage_fuel/static/workbench-charts.mjs";
import { reasonLabel, statusLabel, warningLabel } from "../../src/voyage_fuel/static/workbench-labels.mjs";


function result() {
  return {
    currency: "EUR",
    baseline_scenario: {
      model_cost: "83020.40",
      fuel_eu: { ghgi_actual_g_per_mj: "90.7674", target_g_per_mj: "89.3368" },
    },
    decision_summary: {
      cost_min_scenario_id: "B0",
      target_min_cost_scenario_id: "uco@0.02213",
      max_improvement_scenario_id: "uco@0.2",
    },
    recommendations: [
      { recommendation_id: "CURRENT_MODEL_COST_MIN", scenario_id: "B0", reason: "MODEL_COST_MINIMUM" },
      { recommendation_id: "TARGET_MIN_COST:uco", scenario_id: "uco@0.02213", reason: "CONSTRAINT_RESULT" },
      { recommendation_id: "MAX_COMPLIANCE_IMPROVEMENT:uco", scenario_id: "uco@0.2", reason: "CONSTRAINT_RESULT" },
    ],
    candidate_results: [{
      candidate_id: "uco",
      voyage_result: { constraints: { target_status: "TARGET_REACHABLE" } },
    }],
    scenarios: [
      {
        scenario_id: "B0", candidate_id: null, calculation_status: "COMPARABLE",
        result: {
          ratio: "0", candidate_mass_tonnes: "0", model_cost: "83020.40",
          compliance_improvement_tco2e: "0", constraint_status: "FEASIBLE",
          fuel_eu: { ghgi_actual_g_per_mj: "90.7674", target_g_per_mj: "89.3368" },
        },
        deltas: { model_cost: { delta: "0" }, fuel_cost: { delta: "0" }, eua_cost: { delta: "0" } },
      },
      {
        scenario_id: "uco@0.2", candidate_id: "uco", calculation_status: "COMPARABLE",
        result: {
          ratio: "0.2", candidate_mass_tonnes: "20.549", model_cost: "91156.49",
          compliance_improvement_tco2e: "28.276992", constraint_status: "FEASIBLE",
          fuel_eu: { ghgi_actual_g_per_mj: "77.5229", target_g_per_mj: "89.3368" },
        },
        deltas: {
          model_cost: { delta: "8136.09" },
          fuel_cost: { delta: "8084.70" },
          eua_cost: { delta: "51.39" },
        },
      },
    ],
  };
}


test("goal selection and manual browsing remain distinct", () => {
  const submittedInput = { baseline: { pathId: "MDO" }, candidates: [{ candidateId: "uco", pathId: "UCO_FAME" }] };
  const source = result();
  const before = JSON.stringify(source);
  const initial = buildWorkbenchModel(source, submittedInput);
  assert.equal(initial.recommendedScenarioId, "B0");

  const target = selectGoal(initial, "target");
  assert.equal(target.recommendedScenarioId, "uco@0.02213");
  assert.equal(target.selectedScenarioId, "uco@0.02213");

  const browsing = selectScenario(target, "uco@0.2");
  assert.equal(browsing.selectedScenarioId, "uco@0.2");
  assert.equal(browsing.recommendedScenarioId, "uco@0.02213");
  assert.equal(browsing.selectionSource, "manual");
  assert.equal(JSON.stringify(source), before);
});


test("chart data reads server deltas and excludes FuelEU money from cost series", () => {
  const data = buildChartData(result(), "uco@0.2");
  assert.equal(data.cost.status, "available");
  assert.equal(data.cost.displayDecimals, 2);
  assert.equal(data.cost.items.find((item) => item.key === "fuel_delta").rawValue, "8084.70");
  assert.equal(data.cost.items.find((item) => item.key === "selected_total").rawValue, "91156.49");
  assert.ok(!data.cost.items.some((item) => item.key.includes("penalty")));
  assert.equal(data.ghgi.target, "89.3368");
  assert.equal(data.comparison.find((row) => row.scenarioId === "uco@0.2").selected, true);
});


test("comparison chart excludes scenarios without finite coordinates", () => {
  const source = result();
  source.scenarios.push({
    scenario_id: "uco@missing",
    candidate_id: "uco",
    calculation_status: "CALCULABLE",
    result: {
      ratio: "0.1",
      constraint_status: "CONSTRAINT_UNVERIFIED",
      compliance_improvement_tco2e: "10",
      fuel_eu: {},
    },
    deltas: { model_cost: { delta: null } },
  });
  const data = buildChartData(source, "B0");
  const missing = data.comparison.find((row) => row.scenarioId === "uco@missing");
  assert.equal(missing.costDelta, null);
  assert.equal(missing.improvement, "10");
  assert.equal(missing.status, "CONSTRAINT_UNVERIFIED");
});


test("decision map renders finite report points and marks unverified constraints", () => {
  const data = buildChartData(result(), "uco@0.2");
  const svg = buildSvgScatter(data);
  assert.match(svg, /uco@0\.2/);
  assert.match(svg, /selected/);
  assert.match(svg, /quadrant-favorable/);
  assert.match(svg, /成本更低 · 改善更多/);
  assert.match(svg, /class="plot-point b0/);
  assert.match(svg, /cost-min/);

  const source = result();
  source.scenarios.push({
    scenario_id: "uco@unverified",
    candidate_id: "uco",
    calculation_status: "CALCULABLE",
    result: {
      ratio: "0.1",
      constraint_status: "CONSTRAINT_UNVERIFIED",
      compliance_improvement_tco2e: "10",
      fuel_eu: {},
    },
    deltas: { model_cost: { delta: "100" } },
  });
  const unverifiedSvg = buildSvgScatter(buildChartData(source, "B0"));
  assert.match(unverifiedSvg, /constraint-unverified/);
});

test("display model keeps all report scenarios and maps the selected B0 delta view", () => {
  const source = result();
  source.economics = {
    switch_points: [{
      from_scenario_id: "B0",
      to_scenario_id: "uco@0.2",
      from_candidate_id: null,
      to_candidate_id: "uco",
      value_star: "287.7281",
    }],
  };
  source.candidate_results[0].voyage_result.constraints = {
    target_status: "TARGET_REACHABLE",
    x_budget: "0.35",
    x_supply: "0.4",
    x_cap: "0.3",
    x_target_min: "0.041",
    x_target_min_cost: "0.02213",
    x_max_improvement: "0.3",
    x_cost_min: "0",
    warning_codes: [],
  };
  source.candidate_results[0].voyage_result.economics = {
    pc_break_even: "604.06",
    pe_break_even: "495.44",
    pe_break_even_status: "AVAILABLE",
  };

  const display = buildWorkbenchDisplayModel(source, {
    baseline: { pathId: "MDO" },
    euaPricePerTCO2e: "80",
    candidates: [{
      candidateId: "uco",
      pathId: "UCO_FAME",
      pricePerTonne: "1000",
      specifiedBlendRatios: ["0.2"],
    }],
  }, "uco@0.2");

  assert.deepEqual(display.goalCards.map((card) => card.key), ["cost", "target", "improvement"]);
  assert.deepEqual(display.scenarioRows.map((row) => row.scenarioId), ["B0", "uco@0.2"]);
  assert.equal(display.scenarioRows[1].role, "报告方案最大改善");
  assert.equal(display.selectedDetail.scenarioId, "uco@0.2");
  assert.equal(display.selectedDetail.compareToScenarioId, "B0");
  assert.equal(display.selectedDetail.changes.find((row) => row.key === "model_cost").delta, "8136.09");
  assert.equal(display.selectedDetail.recommendation, null);
  assert.equal(display.sensitivity.candidates[0].thresholds.find((row) => row.key === "x_max_improvement").value, "0.3");
  assert.equal(display.sensitivity.candidates[0].pcBreakEven, "604.06");
  assert.equal(display.sensitivity.candidates[0].currentPrice, "1000");
  assert.equal(display.sensitivity.candidates[0].currentEuaPrice, "80");
  assert.equal(display.sensitivity.switchPoints[0].valueStar, "287.7281");
});

test("display model preserves unavailable goals and missing values", () => {
  const source = result();
  source.decision_summary.target_min_cost_scenario_id = null;
  source.recommendations.push({
    recommendation_id: "TARGET_MIN_COST:uco",
    scenario_id: null,
    reason: "TARGET_NO_SOLUTION",
    assumptions: ["TARGET_NO_SOLUTION"],
    status: "UNAVAILABLE",
  });

  const display = buildWorkbenchDisplayModel(source, { candidates: [{ candidateId: "uco", pathId: "UCO_FAME" }] });
  const target = display.goalCards.find((card) => card.key === "target");
  assert.equal(target.availability, "unavailable");
  assert.equal(target.reason, "TARGET_NO_SOLUTION");
  assert.equal(display.selectedDetail.changes.find((row) => row.key === "fueleu_indicative_penalty_eur").selected, null);
});

test("workbench charts expose units, labels, and safe empty states", () => {
  const display = buildWorkbenchDisplayModel(result(), { candidates: [{ candidateId: "uco", pathId: "UCO_FAME" }] }, "uco@0.2");
  const chartData = buildChartData(result(), "uco@0.2");
  assert.match(buildSvgWaterfall(chartData.cost), /燃料成本变化/);
  assert.match(buildSvgWaterfall(chartData.cost), /connector/);
  assert.match(buildSvgGhgi(chartData.ghgi), /gCO2eq\/MJ/);
  const ratioRail = buildSvgRatioRail({
    candidateId: "uco",
    thresholds: [{ key: "x_target_min_cost", label: "达标最低成本比例", value: "0.2" }],
    reportPoints: [{ scenarioId: "uco@0.2", ratio: "0.2", role: "达标最低成本" }],
  });
  assert.match(ratioRail, /达标最低成本比例/);
  assert.match(ratioRail, /20\.0000%/);
  assert.match(buildSvgSwitchRail([{ fromScenarioId: "B0", toScenarioId: "uco@0.2", valueStar: "287.7281" }]), /287\.73/);
  assert.equal(buildSvgWaterfall({ status: "unavailable", items: [] }), "");
});

test("business labels hide technical status and reason codes", () => {
  assert.equal(statusLabel("TARGET_UNREACHABLE_UNDER_CONSTRAINTS"), "约束下不可达");
  assert.equal(statusLabel("NEGATIVE_THRESHOLD"), "临界值不适用");
  assert.equal(reasonLabel("MODEL_COST_MINIMUM"), "当前模型成本最低");
  assert.equal(reasonLabel("CONSTRAINT_RESULT"), "由约束条件筛选出的方案");
  assert.equal(warningLabel("BUDGET_UNAVAILABLE_WITHOUT_PRICES"), "缺少价格，预算边界暂无法验证");
  assert.equal(statusLabel("UNKNOWN_INTERNAL_STATUS"), "状态待核对");
});

test("ratio rail uses compact markers while preserving full labels in titles", () => {
  const svg = buildSvgRatioRail({
    candidateId: "uco",
    thresholds: [{ key: "x_target_min_cost", label: "达标最低成本比例", value: "0.2" }],
    reportPoints: [{ scenarioId: "uco@0.2", ratio: "0.2", role: "达标最低成本" }],
  });
  assert.match(svg, />T1</);
  assert.match(svg, />R1</);
  assert.match(svg, /达标最低成本比例/);
});

test("threshold lanes separate dense boundaries into readable rows", () => {
  const svg = buildSvgThresholdLanes({
    candidateId: "uco",
    thresholds: [
      { key: "x_budget", label: "预算边界", value: "0.003" },
      { key: "x_supply", label: "供应量边界", value: "0.003" },
    ],
    reportPoints: [{ scenarioId: "uco@0.003", ratio: "0.003", role: "报告方案" }],
  });
  assert.match(svg, /workbench-threshold-lanes/);
  assert.match(svg, /预算边界/);
  assert.match(svg, /供应量边界/);
  assert.match(svg, /实际报告点/);
  assert.match(svg, /0\.3000%/);
});
