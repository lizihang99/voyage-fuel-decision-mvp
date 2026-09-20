import test from "node:test";
import assert from "node:assert/strict";

import {
  buildGuideNotes,
  createGuideState,
  reduceGuide,
  sameExampleRequest,
} from "../../src/voyage_fuel/static/teaching-guide.mjs";
import { buildWorkbenchDisplayModel } from "../../src/voyage_fuel/static/workbench-model.mjs";


test("a late response cannot restore invalidated guidance", () => {
  let state = reduceGuide(createGuideState(), {
    type: "APPLIED",
    caseId: "A-2025",
    requestId: 1,
  });

  state = reduceGuide(state, { type: "INVALIDATED" });
  const next = reduceGuide(state, {
    type: "RESOLVED",
    requestId: 1,
    matched: true,
  });

  assert.equal(next.phase, "modified");
  assert.equal(next.requestId, null);
});


test("closing guidance survives a different example", () => {
  let state = reduceGuide(createGuideState(), {
    type: "VISIBILITY",
    visible: false,
  });

  state = reduceGuide(state, {
    type: "APPLIED",
    caseId: "B-default",
    requestId: 2,
  });

  assert.equal(state.phase, "loading");
  assert.equal(state.caseId, "B-default");
  assert.equal(state.visible, false);
});


test("matching ignores object key order but preserves exact inputs", () => {
  assert.equal(sameExampleRequest(
    { baseline: { massTonnes: "1000", pathId: "MDO" }, candidates: [] },
    { candidates: [], baseline: { pathId: "MDO", massTonnes: "1000" } },
  ), true);
  assert.equal(sameExampleRequest({ mass: "1000" }, { mass: "1001" }), false);
  assert.equal(sameExampleRequest({ mass: null }, { mass: "0" }), false);
});


test("state reductions do not mutate the previous state or event", () => {
  const initial = createGuideState();
  const event = { type: "APPLIED", caseId: "A-2025", requestId: 7 };

  const next = reduceGuide(initial, event);

  assert.deepEqual(initial, {
    phase: "idle",
    caseId: null,
    visible: true,
    requestId: null,
    matched: false,
  });
  assert.deepEqual(event, { type: "APPLIED", caseId: "A-2025", requestId: 7 });
  assert.notStrictEqual(next, initial);
});


test("nonmatching or failed responses do not enter ready", () => {
  const loading = reduceGuide(createGuideState(), {
    type: "APPLIED",
    caseId: "A-2025",
    requestId: 4,
  });

  assert.equal(reduceGuide(loading, {
    type: "RESOLVED",
    requestId: 3,
    matched: true,
  }).phase, "loading");
  assert.equal(reduceGuide(loading, {
    type: "RESOLVED",
    requestId: 4,
    matched: false,
  }).phase, "modified");
  assert.equal(reduceGuide(loading, {
    type: "FAILED",
    requestId: 4,
  }).phase, "error");
});


test("matching keeps candidate order and decimal string types exact", () => {
  const submitted = {
    candidates: [
      { candidateId: "first", pricePerTonne: "950" },
      { candidateId: "second", pricePerTonne: "1150" },
    ],
  };
  const frozen = {
    candidates: [
      { pricePerTonne: "950", candidateId: "first" },
      { pricePerTonne: "1150", candidateId: "second" },
    ],
  };

  assert.equal(sameExampleRequest(submitted, frozen), true);
  assert.equal(sameExampleRequest(submitted, {
    candidates: [...frozen.candidates].reverse(),
  }), false);
  assert.equal(sameExampleRequest({ value: "950" }, { value: 950 }), false);
});


function basicResult() {
  return {
    currency: "EUR",
    baseline_scenario: {
      model_cost: "789768",
      fuel_eu: {
        ghgi_actual_g_per_mj: "90.7674473068",
        target_g_per_mj: "89.3368",
        compliance_balance_t: "-30.54432",
        indicative_penalty_eur: "19700",
      },
    },
    decision_summary: null,
    recommendations: [],
    candidate_results: [],
    baseline: {},
    scenarios: [{
      scenario_id: "B0",
      candidate_id: null,
      calculation_status: "COMPARABLE",
      result: {
        ratio: "0",
        candidate_mass_tonnes: "0",
        fuel_cost: "700000",
        eu_ets: { eua_cost: "89768" },
        model_cost: "789768",
        constraint_status: "FEASIBLE",
        fuel_eu: {
          ghgi_actual_g_per_mj: "90.7674473068",
          target_g_per_mj: "89.3368",
          compliance_balance_t: "-30.54432",
          indicative_penalty_eur: "19700",
          status: "DEFICIT_ESTIMATE",
        },
      },
      deltas: {
        fuel_cost: { delta: "0" },
        eua_cost: { delta: "0" },
        model_cost: { delta: "0" },
      },
    }],
  };
}


function comparisonResult() {
  return {
    currency: "EUR",
    baseline_scenario: {},
    decision_summary: {
      cost_min_scenario_id: "B0",
      target_min_cost_scenario_id: "hvo@0.071025",
      max_improvement_scenario_id: "e-diesel@0.7",
    },
    recommendations: [
      { recommendation_id: "CURRENT_MODEL_COST_MIN", scenario_id: "B0", reason: "MODEL_COST_MINIMUM" },
      { recommendation_id: "TARGET_MIN_COST:hvo", scenario_id: "hvo@0.071025", reason: "CONSTRAINT_RESULT" },
      { recommendation_id: "MAX_COMPLIANCE_IMPROVEMENT:e-diesel", scenario_id: "e-diesel@0.7", reason: "CONSTRAINT_RESULT" },
    ],
    candidate_results: [
      { candidate_id: "uco-limited", voyage_result: { constraints: { target_status: "TARGET_UNREACHABLE_UNDER_CONSTRAINTS" } } },
      { candidate_id: "uco-bulk", voyage_result: { constraints: { target_status: "TARGET_REACHABLE" } } },
      { candidate_id: "hvo", voyage_result: { constraints: { target_status: "TARGET_REACHABLE" } } },
      { candidate_id: "e-diesel", voyage_result: { constraints: { target_status: "TARGET_REACHABLE" } } },
    ],
    scenarios: [
      {
        scenario_id: "B0",
        candidate_id: null,
        calculation_status: "COMPARABLE",
        result: {
          ratio: "0",
          candidate_mass_tonnes: "0",
          model_cost: "960408",
          compliance_improvement_tco2e: "0",
          constraint_status: "FEASIBLE",
          fuel_eu: { ghgi_actual_g_per_mj: "90.7674", target_g_per_mj: "85.6904", status: "DEFICIT_ESTIMATE" },
        },
        deltas: { model_cost: { delta: "0" } },
      },
      {
        scenario_id: "hvo@0.071025",
        candidate_id: "hvo",
        calculation_status: "COMPARABLE",
        result: {
          ratio: "0.071025625481",
          candidate_mass_tonnes: "76.4",
          model_cost: "968507.324",
          compliance_improvement_tco2e: "216.79",
          constraint_status: "FEASIBLE",
          fuel_eu: { ghgi_actual_g_per_mj: "85.6904", target_g_per_mj: "85.6904", status: "ON_TARGET_ESTIMATE" },
        },
        deltas: { model_cost: { delta: "8099.324" }, fuel_cost: { delta: "8000" }, eua_cost: { delta: "99.324" } },
      },
      {
        scenario_id: "e-diesel@0.7",
        candidate_id: "e-diesel",
        calculation_status: "COMPARABLE",
        result: {
          ratio: "0.7",
          candidate_mass_tonnes: "810.6",
          model_cost: "1590408",
          compliance_improvement_tco2e: "2640.3",
          constraint_status: "FEASIBLE",
          fuel_eu: { ghgi_actual_g_per_mj: "55.4", target_g_per_mj: "85.6904", status: "SURPLUS_ESTIMATE" },
        },
        deltas: { model_cost: { delta: "630000" } },
      },
    ],
  };
}


function readyState(caseId = "A-2025") {
  const loading = reduceGuide(createGuideState(), {
    type: "APPLIED",
    caseId,
    requestId: 1,
  });
  return reduceGuide(loading, {
    type: "RESOLVED",
    requestId: 1,
    matched: true,
  });
}


function notesFor(result, submittedInput, state = readyState()) {
  const display = buildWorkbenchDisplayModel(result, submittedInput);
  return buildGuideNotes({
    state,
    display,
    displayConfig: { mass: 3, energy: 3, ratio: 4, price: 2 },
    submittedInput,
    frozenRequest: submittedInput,
  });
}


test("basic example notes use the display model and server status", () => {
  const submittedInput = {
    baseline: { pathId: "MDO" },
    candidates: [],
  };
  const notes = notesFor(basicResult(), submittedInput);

  assert.deepEqual(notes.map((note) => note.id), [
    "basic-cost",
    "basic-ghgi",
    "basic-balance",
  ]);
  assert.deepEqual(notes.map((note) => note.anchor), [
    "cost-breakdown",
    "ghgi",
    "fueleu-balance",
  ]);
  assert.match(notes[0].text, /700000\.00 EUR/);
  assert.match(notes[0].text, /89768\.00 EUR/);
  assert.match(notes[0].text, /789768\.00 EUR/);
  assert.match(notes[1].text, /90\.7674 gCO2eq\/MJ/);
  assert.match(notes[1].text, /89\.3368 gCO2eq\/MJ/);
  assert.match(notes[1].text, /缺口/);
  assert.match(notes[2].text, /-30\.544320 tCO2e/);
  assert.match(notes[2].text, /19700\.00 EUR/);
});


test("comparison notes explain each goal and the limited UCO condition", () => {
  const submittedInput = {
    baseline: { pathId: "MDO" },
    candidates: [
      { candidateId: "uco-limited", pathId: "UCO_FAME", pricePerTonne: "950", candidateSupplyTonnes: "30" },
      { candidateId: "uco-bulk", pathId: "UCO_FAME", pricePerTonne: "1150" },
      { candidateId: "hvo", pathId: "HVO", pricePerTonne: "1100" },
      { candidateId: "e-diesel", pathId: "E_DIESEL", pricePerTonne: "1600" },
    ],
  };
  const notes = notesFor(comparisonResult(), submittedInput, readyState("B-default"));
  const byId = new Map(notes.map((note) => [note.id, note]));

  assert.deepEqual(notes.map((note) => note.id), [
    "comparison-cost",
    "comparison-target",
    "comparison-improvement",
    "comparison-detail",
    "comparison-supply",
  ]);
  assert.equal(byId.get("comparison-cost").anchor, "goals");
  assert.equal(byId.get("comparison-target").anchor, "goals");
  assert.equal(byId.get("comparison-improvement").anchor, "goals");
  assert.match(byId.get("comparison-cost").text, /船用柴油/);
  assert.match(byId.get("comparison-cost").text, /未达到/);
  assert.match(byId.get("comparison-target").text, /HVO/);
  assert.match(byId.get("comparison-target").text, /7\.1026%/);
  assert.match(byId.get("comparison-target").text, /增加 8099\.32 EUR/);
  assert.match(byId.get("comparison-improvement").text, /电制柴油/);
  assert.match(byId.get("comparison-improvement").text, /70\.0000%/);
  assert.equal(byId.get("comparison-detail").anchor, "detail-charts");
  assert.match(byId.get("comparison-detail").text, /船用柴油/);
  assert.equal(byId.get("comparison-supply").anchor, "supply-uco-limited");
  assert.match(byId.get("comparison-supply").text, /950\.00 EUR\/吨/);
  assert.match(byId.get("comparison-supply").text, /30\.000 吨/);
  assert.match(byId.get("comparison-supply").text, /不可达/);
  assert.match(byId.get("comparison-supply").text, /大宗UCO未设置供应量上限/);
});


test("notes stay empty unless the exact example request is ready", () => {
  const submittedInput = { baseline: { pathId: "MDO" }, candidates: [] };
  const display = buildWorkbenchDisplayModel(basicResult(), submittedInput);

  assert.deepEqual(buildGuideNotes({
    state: createGuideState(),
    display,
    displayConfig: {},
    submittedInput,
    frozenRequest: submittedInput,
  }), []);
  assert.deepEqual(buildGuideNotes({
    state: readyState(),
    display,
    displayConfig: {},
    submittedInput,
    frozenRequest: { baseline: { pathId: "HFO" }, candidates: [] },
  }), []);
});


test("note values follow display precision and missing values stay neutral", () => {
  const source = basicResult();
  delete source.scenarios[0].result.fuel_eu.compliance_balance_t;
  delete source.scenarios[0].result.fuel_eu.indicative_penalty_eur;
  const submittedInput = { baseline: { pathId: "MDO" }, candidates: [] };
  const display = buildWorkbenchDisplayModel(source, submittedInput);
  const notes = buildGuideNotes({
    state: readyState(),
    display,
    displayConfig: { mass: 3, energy: 3, ratio: 4, price: 0 },
    submittedInput,
    frozenRequest: submittedInput,
  });
  const byId = new Map(notes.map((note) => [note.id, note]));

  assert.match(byId.get("basic-cost").text, /700000 EUR/);
  assert.match(byId.get("basic-cost").text, /789768 EUR/);
  assert.match(byId.get("basic-balance").text, /合规余额未提供/);
  assert.match(byId.get("basic-balance").text, /指示性金额未提供/);
});
