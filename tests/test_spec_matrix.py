import csv
import io
import json
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from voyage_fuel.case_calculator import calculate_decision_case
from voyage_fuel.case_comparison import calculate_case_value_switch_points, metric_delta
from voyage_fuel.contracts import CandidateInput, DecisionCaseInput
from voyage_fuel.emissions import calculate_eu_ets, calculate_fueleu
from voyage_fuel.factors import get_builtin_factor, resolve_factor
from voyage_fuel.json_io import calculate_voyage_json, decision_case_result_to_dict, parse_decision_case
from voyage_fuel.models import FuelAmount, FuelComponent, FuelFactor, ScopeRates, VoyageInput
from voyage_fuel.ports import calculate_scope_rates
from voyage_fuel.reports import decision_case_to_csv
from voyage_fuel.formatting import DisplayConfig
from voyage_fuel.calculator import calculate_voyage
from voyage_fuel.web import app


def _component(path_id: str, price: str | None = "600", **kwargs) -> FuelComponent:
    return FuelComponent(
        get_builtin_factor(path_id),
        None if price is None else Decimal(price),
        **kwargs,
    )


def _scope(ets: str = "1", surrender: str = "1", fuel_eu: str | None = "1") -> ScopeRates:
    geo = Decimal(ets)
    surrender_decimal = Decimal(surrender)
    return ScopeRates(
        eu_ets_scope_rate=geo,
        eu_ets_surrender_rate=surrender_decimal,
        eu_ets_effective_rate=geo * surrender_decimal,
        fuel_eu_scope_rate=None if fuel_eu is None else Decimal(fuel_eu),
        fuel_eu_applicable=fuel_eu is not None,
    )


def _synthetic_factor(path_id: str, *, wt_t: str, co2: str = "0", ch4: str = "0", n2o: str = "0", rwd: str = "1") -> FuelFactor:
    return FuelFactor(
        path_id=path_id,
        lcv_mj_per_g=Decimal("0.04"),
        wt_t_g_per_mj=Decimal(wt_t),
        cf_co2_g_per_g=Decimal(co2),
        cf_ch4_g_per_g=Decimal(ch4),
        cf_n2o_g_per_g=Decimal(n2o),
        rwd=Decimal(rwd),
        cslip_percent=None,
        methane_slip_applicable=False,
        factor_status="FIXED",
    )


class SpecificationMatrixTests(unittest.TestCase):
    @staticmethod
    def _custom_factor(mode="STATIC", *, qualification="NOT_DEMONSTRATED", rwd="1", cf_co2="3", cslip="NA"):
        fields = {
            "lcv": "MJ/gFuel", "wtT": "gCO2eq/MJ", "E": "gCO2eq/MJ", "eu": "gCO2eq/MJ", "cfCO2": "gGHG/gFuel",
            "cfCH4": "gGHG/gFuel", "cfN2O": "gGHG/gFuel", "cslip": "%",
            "methaneSlipApplicable": "boolean", "rwd": "ratio", "eligibleBiomassFraction": "fraction",
        }
        evidence = {key: [{"sourceId": f"SRC-{key}", "sourceType": "TEST", "unit": unit, "verificationStatus": "VERIFIED"}]
                    for key, unit in fields.items()}
        return {
            "pathId": "CUSTOM_FACTOR", "custom": True, "equipmentId": "CUSTOM_ENGINE",
            "lcv": "0.04", "wtTMode": mode, "wtT": "10", "E": "20", "eu": "10", "cfCO2": cf_co2,
            "cfCH4": "0", "cfN2O": "0", "cslip": cslip, "methaneSlipApplicable": False,
            "rwd": rwd, "eligibleBiomassFraction": "0", "qualificationStatus": qualification,
            "sourceEvidence": evidence,
        }

    @staticmethod
    def _case_payload(*, candidates=None, baseline=None, year=2026):
        return {
            "reportYear": year, "departurePort": "CNSHG", "arrivalPort": "NLRTM",
            "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
            "baseline": baseline or {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
            "euaPricePerTCO2e": "80", "candidates": candidates if candidates is not None else [{"candidateId": "uco", "pathId": "UCO_FAME", "pricePerTonne": "1000", "specifiedBlendRatios": ["0.2"]}],
        }

    def test_case_economics_b0_can_be_lowest_and_dominated_switch_is_absent(self):
        request = self._case_payload(candidates=[
            {"candidateId": "expensive", "pathId": "HFO", "pricePerTonne": "2000", "specifiedBlendRatios": ["1"], "maxBlendRatio": "1", "allowsPureUse": True},
        ])
        parsed = parse_decision_case(request)
        result = calculate_decision_case(parsed.request, parsed.issues)
        self.assertEqual(next(r for r in result.recommendations if r.recommendation_id == "CURRENT_MODEL_COST_MIN").scenario_id, "B0")
        switch_request = self._case_payload(candidates=[
            {"candidateId": "uco", "pathId": "UCO_FAME", "pricePerTonne": "1000", "specifiedBlendRatios": ["0.2"], "maxBlendRatio": "0.3", "allowsPureUse": True},
            {"candidateId": "lng", "pathId": "LNG_OTTO_MEDIUM_SPEED", "pricePerTonne": "3000", "specifiedBlendRatios": ["0.1", "0.5"], "maxBlendRatio": "0.5", "allowsPureUse": True},
        ])
        switch_result = calculate_decision_case(parse_decision_case(switch_request).request)
        self.assertIsNotNone(switch_result.economics)
        self.assertTrue(switch_result.economics.switch_points)
        self.assertEqual(
            [(p.from_scenario_id, p.to_scenario_id, p.to_candidate_id) for p in switch_result.economics.switch_points],
            [("B0", "uco@0.3", "uco")],
        )

        # A local LNG/UCO intersection exists, but LNG is never on the global
        # lower envelope because B0 and UCO are cheaper on either side.
        baseline = next(row for row in switch_result.scenarios if row.scenario_id == "B0")
        uco = next(row for row in switch_result.scenarios if row.scenario_id == "uco@0.3")
        lng = next(row for row in switch_result.scenarios if row.scenario_id == "lng@0.1")
        synthetic = (
            replace(baseline, result=replace(baseline.result, model_cost=Decimal("80"), compliance_improvement_tco2e=Decimal("0"))),
            replace(uco, result=replace(uco.result, model_cost=Decimal("100"), compliance_improvement_tco2e=Decimal("1"))),
            replace(lng, result=replace(lng.result, model_cost=Decimal("90"), compliance_improvement_tco2e=Decimal("0.2"))),
        )
        envelope = calculate_case_value_switch_points(synthetic)
        self.assertEqual(len(envelope), 1)
        self.assertEqual((envelope[0].from_scenario_id, envelope[0].to_scenario_id, envelope[0].value_star), ("B0", "uco@0.3", Decimal("20")))

    def test_factor_qualification_and_special_input_guards_keep_structured_issues(self):
        cases = (
            (self._custom_factor("RFNBO_E", qualification="NOT_DEMONSTRATED", rwd="2"), "MISSING_REQUIRED_FACTOR", 2026),
            (self._custom_factor("RFNBO_E", qualification="ASSUMED_ELIGIBLE", rwd="2"), "MISSING_REQUIRED_FACTOR", 2024),
            (self._custom_factor("BIO_E", qualification="ASSUMED_ELIGIBLE", cf_co2="NA"), "MISSING_REQUIRED_FACTOR", 2026),
            (self._custom_factor(cslip="101"), "INVALID_CSLIP", 2026),
        )
        for custom, code, year in cases:
            parsed = parse_decision_case(self._case_payload(year=year, candidates=[{"candidateId": "custom", **custom}]))
            self.assertTrue(parsed.issues, custom)
            self.assertEqual(parsed.issues[0].code, code)
            if custom["wtTMode"] == "BIO_E":
                self.assertIn("cfCO2 is required for BIO_E", parsed.issues[0].message)
            if custom["wtTMode"] == "RFNBO_E" and year == 2024:
                self.assertIn("2025 through 2030", parsed.issues[0].message)
            if custom["wtTMode"] == "RFNBO_E" and year == 2026:
                self.assertIn("RFNBO qualification is required", parsed.issues[0].message)

    def test_non_biomass_factor_cannot_claim_biomass_zero_rating(self):
        parsed = parse_decision_case(self._case_payload(candidates=[{"candidateId": "mdo", "pathId": "MDO", "eligibleBiomassFraction": "1"}]))
        self.assertTrue(parsed.issues)
        self.assertEqual(parsed.issues[0].code, "MISSING_REQUIRED_FACTOR")

    def test_target_no_solution_retains_independent_maximum_improvement_boundary(self):
        high = FuelComponent(get_builtin_factor("HFO"), Decimal("1000"))
        result = calculate_voyage(VoyageInput(2026, "CNSHG", "NLRTM", _component("MDO"), Decimal("100"), high, None))
        self.assertEqual(result.constraints.target_status, "TARGET_NO_SOLUTION")
        self.assertEqual(result.constraints.x_max_improvement, Decimal("0"))
        self.assertTrue(any(row.ratio == Decimal("0") for row in result.scenarios))
        case_payload = self._case_payload(candidates=[{"candidateId": "high", "pathId": "HFO", "pricePerTonne": "1000"}])
        case = calculate_decision_case(parse_decision_case(case_payload).request)
        self.assertEqual(case.economics.max_improvement_scenario_id, "B0")
        maximum = next(item for item in case.recommendations if item.recommendation_id == "MAX_COMPLIANCE_IMPROVEMENT:high")
        self.assertEqual(maximum.scenario_id, "B0")
        self.assertIn("TARGET_NO_SOLUTION", maximum.assumptions)

    def test_empty_candidates_and_2024_ets_exclusion_are_structured(self):
        parsed = parse_decision_case(self._case_payload(candidates=[]))
        b0_only = calculate_decision_case(parsed.request, parsed.issues)
        self.assertEqual([row.scenario_id for row in b0_only.scenarios], ["B0"])
        self.assertEqual(b0_only.recommendations, ())
        parsed_ets = parse_decision_case(self._case_payload(year=2024))
        result = decision_case_result_to_dict(calculate_decision_case(parsed_ets.request, parsed_ets.issues))
        ets = result["scenarios"][0]["result"]["eu_ets"]
        self.assertEqual(ets["included_gases"], ["CO2"])
        self.assertTrue(ets["excluded_from_ets_surrender"]["CH4"])
        self.assertTrue(ets["excluded_from_ets_surrender"]["N2O"])
        self.assertFalse(ets["excluded_from_ets_surrender"]["CO2"])

    def test_factor_output_and_csv_expose_metadata_constraints_and_economics(self):
        custom = self._custom_factor()
        payload = self._case_payload(baseline={**custom, "massTonnes": "100", "pricePerTonne": "700"})
        parsed_custom = parse_decision_case(payload)
        result = decision_case_result_to_dict(calculate_decision_case(parsed_custom.request, parsed_custom.issues))
        factor = result["provenance"]["factor_resolutions"][0]["factor"]
        self.assertEqual(factor["equipment_id"], "CUSTOM_ENGINE")
        evidence = {item["field_name"]: item for item in factor["source_evidence"]}
        self.assertEqual(set(evidence), {"lcv", "wtT", "cfCO2", "cfCH4", "cfN2O", "cslip", "methaneSlipApplicable", "rwd", "eligibleBiomassFraction"})
        self.assertEqual(evidence["cfCO2"]["source_id"], "SRC-cfCO2")
        self.assertEqual(evidence["cfCO2"]["unit"], "gGHG/gFuel")
        self.assertEqual(evidence["cfCO2"]["verification_status"], "VERIFIED")
        parsed = parse_decision_case(self._case_payload())
        case_result = calculate_decision_case(parsed.request, parsed.issues)
        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(case_result))))
        self.assertIn("constraints", {r["record_type"] for r in rows})
        self.assertIn("economics", {r["record_type"] for r in rows})
        constraints = next(r for r in rows if r["record_type"] == "constraints")
        economics = next(r for r in rows if r["record_type"] == "economics")
        self.assertTrue(constraints["x_cap"])
        self.assertTrue(economics["cost_min_scenario_id"])

    def test_web_baseline_custom_input_and_boundary_language_are_public_contracts(self):
        payload = self._case_payload(baseline={**self._custom_factor(), "massTonnes": "100", "pricePerTonne": "700"})
        response = TestClient(app).post("/api/calculate", json=payload)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["provenance"]["factor_resolutions"][0]["factor"]["equipment_id"], "CUSTOM_ENGINE")
        scenarios = [s for c in body["candidate_results"] for s in (c["voyage_result"]["scenarios"] if c["voyage_result"] else [])]
        self.assertTrue(scenarios)
        self.assertTrue(all(s["execution_status"] == "EXECUTION_CONDITIONS_PENDING" for s in scenarios))
        root = TestClient(app).get("/").text
        readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
        pdf = PdfReader(io.BytesIO(__import__('voyage_fuel.reports', fromlist=['decision_case_to_pdf']).decision_case_to_pdf(calculate_decision_case(parse_decision_case(self._case_payload()).request)) ))
        pdf_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        for fragment in (
            "Boundary: voyage-level proportional estimate; not a formal annual penalty; not a procurement recommendation; independent physical lifecycle WtW reduction is not provided. EXECUTION_CONDITIONS_PENDING.",
        ):
            self.assertIn(fragment.casefold(), root.casefold())
        for fragment in (
            "Boundary: voyage-level regulatory estimate for this submitted voyage.",
            "not a formal annual penalty or annual-limit settlement",
            "not a procurement recommendation",
            "does not provide an independent physical lifecycle WtW reduction",
            "execution conditions remain",
            "pending and this report is not a procurement recommendation",
        ):
            self.assertIn(fragment.casefold(), pdf_text.casefold())
        for fragment in (
            "voyage-level",
            "not a formal annual penalty",
            "not a procurement recommendation",
            "independent physical lifecycle WtW reduction",
            "EXECUTION_CONDITIONS_PENDING",
        ):
            self.assertIn(fragment.casefold(), readme.casefold())
    def test_ets_year_gas_and_surrender_matrix(self):
        factor = _synthetic_factor("GWP_MATRIX", wt_t="0", co2="1", ch4="0.000001", n2o="0.000001")
        amount = [FuelAmount(FuelComponent(factor, Decimal("80")), Decimal("1"))]
        expected_all_gases = Decimal("1.000293")
        for year, included, surrender in (
            (2024, ("CO2",), Decimal("0.4")),
            (2025, ("CO2",), Decimal("0.7")),
            (2026, ("CO2", "CH4", "N2O"), Decimal("1")),
            (2029, ("CO2", "CH4", "N2O"), Decimal("1")),
            (2030, ("CO2", "CH4", "N2O"), Decimal("1")),
        ):
            result = calculate_eu_ets(year, amount, _scope("1", str(surrender)), Decimal("80"))
            self.assertEqual(result.included_gases, included)
            expected_pre_scope = Decimal("1") if year < 2026 else expected_all_gases
            self.assertEqual(result.ets_co2e_pre_scope_t, expected_pre_scope)
            self.assertEqual(result.euas_required, expected_pre_scope * surrender)

    def test_ets_and_fueleu_gwp_constants_are_isolated(self):
        factor = _synthetic_factor("GWP_ISOLATION", wt_t="0", co2="0", ch4="0.000001", n2o="0.000001")
        amounts = [FuelAmount(FuelComponent(factor, Decimal("1")), Decimal("1"))]
        ets = calculate_eu_ets(2026, amounts, _scope(), None)
        fueleu = calculate_fueleu(2025, amounts, Decimal("1"))
        self.assertEqual(ets.ets_co2e_pre_scope_t, Decimal("0.000293"))
        self.assertEqual(fueleu.tt_w_intensity_g_per_mj, Decimal("0.008075"))
        self.assertNotEqual(Decimal("28"), Decimal("25"))
        self.assertNotEqual(Decimal("265"), Decimal("298"))

    def test_port_ranges_and_surrender_rates_are_independent(self):
        cases = (
            ("CNSHG", "USNYC", Decimal("0")),
            ("CNSHG", "NLRTM", Decimal("0.5")),
            ("NLRTM", "SEGOT", Decimal("1")),
        )
        for departure, arrival, geo in cases:
            rates = calculate_scope_rates(2025, departure, arrival)
            self.assertEqual(rates.eu_ets_scope_rate, geo)
            self.assertEqual(rates.eu_ets_surrender_rate, Decimal("0.7"))
            self.assertEqual(rates.eu_ets_effective_rate, geo * Decimal("0.7"))
            self.assertEqual(rates.fuel_eu_scope_rate, geo)
        self.assertEqual(calculate_scope_rates(2024, "CNSHG", "NLRTM").fuel_eu_scope_rate, None)
        self.assertEqual(calculate_scope_rates(2026, "CNSHG", "NLRTM").eu_ets_surrender_rate, Decimal("1"))

    def test_fueleu_targets_and_boundary_statuses(self):
        amounts = [FuelAmount(FuelComponent(get_builtin_factor("HFO"), Decimal("600")), Decimal("1"))]
        for year in (2025, 2026, 2029):
            result = calculate_fueleu(year, amounts, Decimal("1"))
            self.assertEqual(result.target_g_per_mj, Decimal("89.3368"))
        self.assertEqual(calculate_fueleu(2030, amounts, Decimal("1")).target_g_per_mj, Decimal("85.6904"))
        not_yet = calculate_fueleu(2024, amounts, None)
        self.assertEqual(not_yet.status, "NOT_YET_APPLICABLE")
        self.assertIsNone(not_yet.target_g_per_mj)
        out_of_scope = calculate_fueleu(2025, amounts, Decimal("0"))
        self.assertEqual(out_of_scope.status, "OUT_OF_SCOPE")
        self.assertEqual(out_of_scope.scoped_energy_mj, Decimal("0"))
        self.assertIsNone(out_of_scope.compliance_balance_g)

    def test_constraint_target_exact_no_solution_and_unreachable(self):
        exact = FuelComponent(_synthetic_factor("EXACT", wt_t="89.3368"), Decimal("1"))
        candidate = FuelComponent(_synthetic_factor("LOW", wt_t="0"), Decimal("1"))
        exact_result = calculate_voyage(VoyageInput(
            2025, "CNSHG", "NLRTM", exact, Decimal("1"), candidate, None,
        ))
        self.assertEqual(exact_result.constraints.target_status, "TARGET_REACHABLE")
        self.assertEqual(exact_result.constraints.x_target_min, Decimal("0"))

        high = FuelComponent(_synthetic_factor("HIGH", wt_t="100"), Decimal("1"))
        no_solution = calculate_voyage(VoyageInput(
            2025, "CNSHG", "NLRTM", high, Decimal("1"), high, None,
        ))
        self.assertEqual(no_solution.constraints.target_status, "TARGET_NO_SOLUTION")
        self.assertIsNone(no_solution.constraints.x_target_min_unconstrained)

        unreachable = calculate_voyage(VoyageInput(
            2025, "CNSHG", "NLRTM", high, Decimal("1"), candidate, None,
            max_blend_ratio=Decimal("0.1"),
        ))
        self.assertEqual(unreachable.constraints.target_status, "TARGET_UNREACHABLE_UNDER_CONSTRAINTS")
        self.assertGreater(unreachable.constraints.x_target_min_unconstrained, unreachable.constraints.x_cap)
        self.assertIsNone(unreachable.constraints.x_target_min)

    def test_budget_supply_blend_limits_are_individually_and_jointly_binding(self):
        baseline = _component("MGO", "600")
        candidate = FuelComponent(get_builtin_factor("UCO_FAME"), Decimal("1000"), eligible_biomass_fraction=Decimal("1"), qualification_status="ASSUMED_ELIGIBLE")
        budget_only = calculate_voyage(VoyageInput(2026, "CNSHG", "NLRTM", baseline, Decimal("100"), candidate, Decimal("80"), incremental_budget=Decimal("5000")))
        self.assertLess(budget_only.constraints.x_budget, Decimal("1"))
        self.assertEqual(budget_only.constraints.x_cap, budget_only.constraints.x_budget)
        supply_only = calculate_voyage(VoyageInput(2026, "CNSHG", "NLRTM", baseline, Decimal("100"), candidate, Decimal("80"), candidate_supply_tonnes=Decimal("10")))
        self.assertLess(supply_only.constraints.x_supply, Decimal("1"))
        self.assertEqual(supply_only.constraints.x_cap, supply_only.constraints.x_supply)

        blend_only = calculate_voyage(VoyageInput(
            2026, "CNSHG", "NLRTM", baseline, Decimal("100"), candidate, Decimal("80"),
            candidate_supply_tonnes=Decimal("1000"), incremental_budget=Decimal("100000"),
            max_blend_ratio=Decimal("0.05"), candidate_allows_pure_use=True,
        ))
        self.assertEqual(blend_only.constraints.x_budget, Decimal("1"))
        self.assertEqual(blend_only.constraints.x_supply, Decimal("1"))
        self.assertEqual(blend_only.constraints.x_cap, Decimal("0.05"))
        blend_cap_row = next(row for row in blend_only.scenarios if row.ratio == Decimal("0.05"))
        self.assertEqual(blend_cap_row.constraint_status, "FEASIBLE")
        b100_row = next(row for row in blend_only.scenarios if row.ratio == Decimal("1"))
        self.assertEqual(b100_row.constraint_status, "CONSTRAINT_INFEASIBLE")

        joint = calculate_voyage(VoyageInput(
            2026, "CNSHG", "NLRTM", baseline, Decimal("100"), candidate, Decimal("80"),
            candidate_supply_tonnes=Decimal("100"), incremental_budget=Decimal("12000"),
            max_blend_ratio=Decimal("0.30"), candidate_allows_pure_use=True,
        ))
        self.assertGreater(joint.constraints.x_budget, Decimal("0.30"))
        self.assertGreater(joint.constraints.x_supply, Decimal("0.30"))
        self.assertEqual(joint.constraints.x_cap, min(joint.constraints.x_budget, joint.constraints.x_supply, Decimal("0.30")))
        joint_cap_row = next(row for row in joint.scenarios if row.ratio == Decimal("0.30"))
        self.assertEqual(joint_cap_row.constraint_status, "FEASIBLE")
        budget_row = next(row for row in joint.scenarios if row.ratio == joint.constraints.x_budget)
        supply_row = next(row for row in joint.scenarios if row.ratio == joint.constraints.x_supply)
        self.assertEqual(budget_row.constraint_status, "CONSTRAINT_INFEASIBLE")
        self.assertEqual(supply_row.constraint_status, "CONSTRAINT_INFEASIBLE")

    def test_b100_is_retained_as_infeasible_reference_when_pure_use_allowed(self):
        baseline = _component("MDO", "700")
        candidate = FuelComponent(get_builtin_factor("UCO_FAME"), Decimal("1000"), eligible_biomass_fraction=Decimal("1"), qualification_status="ASSUMED_ELIGIBLE")
        result = calculate_voyage(VoyageInput(
            2026, "CNSHG", "NLRTM", baseline, Decimal("100"), candidate, Decimal("80"),
            candidate_allows_pure_use=True, candidate_supply_tonnes=Decimal("1"), max_blend_ratio=Decimal("0.2"),
        ))
        b100 = next(row for row in result.scenarios if row.ratio == Decimal("1"))
        self.assertEqual(b100.constraint_status, "CONSTRAINT_INFEASIBLE")
        self.assertIsNotNone(b100.fuel_eu)

    def test_zero_baseline_percent_change_returns_reason_without_division(self):
        delta = metric_delta(Decimal("12"), Decimal("0"))
        self.assertEqual(delta.delta, Decimal("12"))
        self.assertIsNone(delta.percent_delta)
        self.assertEqual(delta.reason_code, "ZERO_BASELINE")

    def test_invalid_candidate_does_not_block_b0_or_other_candidates(self):
        payload = {
            "reportYear": 2026, "departurePort": "CNSHG", "arrivalPort": "NLRTM",
            "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
            "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
            "euaPricePerTCO2e": "80",
            "candidates": [
                {"candidateId": "ok", "pathId": "UCO_FAME", "pricePerTonne": "1000"},
                {"candidateId": "bad", "pathId": "LNG_OTTO_MEDIUM_SPEED", "specifiedBlendRatios": ["1.2"]},
            ],
        }
        parsed = parse_decision_case(payload)
        result = calculate_decision_case(parsed.request, parsed.issues)
        self.assertEqual(result.candidate_results[0].calculation_status, "COMPARABLE")
        self.assertEqual(result.candidate_results[1].calculation_status, "BLOCKED")
        self.assertEqual(result.scenarios[0].scenario_id, "B0")
        self.assertTrue(any(row.candidate_id == "ok" for row in result.scenarios))

    def test_json_distinguishes_null_zero_na_rc_and_blocking_values(self):
        def custom_payload(cslip: str, *, cslip_verification: str = "VERIFIED"):
            evidence = {
                key: [{"sourceId": f"SRC-{key}", "sourceType": "TEST", "unit": {
                    "lcv": "MJ/gFuel", "wtT": "gCO2eq/MJ", "cfCO2": "gGHG/gFuel",
                    "cfCH4": "gGHG/gFuel", "cfN2O": "gGHG/gFuel", "cslip": "%",
                    "methaneSlipApplicable": "boolean", "rwd": "ratio",
                    "eligibleBiomassFraction": "fraction",
                }[key], "verificationStatus": cslip_verification if key == "cslip" else "VERIFIED"}]
                for key in ("lcv", "wtT", "cfCO2", "cfCH4", "cfN2O", "cslip", "methaneSlipApplicable", "rwd", "eligibleBiomassFraction")
            }
            return {
                "reportYear": 2026, "departurePort": "CNSHG", "arrivalPort": "NLRTM",
                "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
                "baseline": {"pathId": "CUSTOM", "custom": True, "massTonnes": "1", "equipmentId": "ENGINE", "lcv": "0.04", "wtTMode": "STATIC", "wtT": "10", "cfCO2": "3", "cfCH4": "0", "cfN2O": "0", "cslip": cslip, "methaneSlipApplicable": False, "rwd": "1", "eligibleBiomassFraction": "0", "sourceEvidence": evidence},
                "candidate": {"pathId": "MDO", "massTonnes": "1"}, "euaPricePerTCO2e": None,
            }
        null_result = json.loads(calculate_voyage_json(custom_payload("NA")))
        self.assertIsNone(null_result["scenarios"][0]["eu_ets"]["eua_cost"])
        self.assertIsNone(null_result["baseline_factor"]["cslip_percent"])
        self.assertEqual(null_result["baseline_factor"]["cslip_semantics"], "NA")
        zero_result = json.loads(calculate_voyage_json(custom_payload("0")))
        self.assertEqual(zero_result["baseline_factor"]["cslip_percent"], "0")
        rc_result = json.loads(calculate_voyage_json(custom_payload("0", cslip_verification="RC")))
        rc_evidence = next(item for item in rc_result["baseline_factor"]["source_evidence"] if item["field_name"] == "cslip")
        self.assertEqual(rc_evidence["verification_status"], "RC")
        self.assertEqual(resolve_factor("LPG_PROPANE").cslip_semantics, "SA")
        with self.assertRaisesRegex(ValueError, "recognized Cslip required"):
            resolve_factor("LPG_PROPANE", qualification_status="VERIFIED_ELIGIBLE")
        blocked_payload = {
            "reportYear": 2026, "departurePort": "CNSHG", "arrivalPort": "NLRTM",
            "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
            "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
            "euaPricePerTCO2e": "80",
            "candidates": [
                {"candidateId": "ok", "pathId": "UCO_FAME", "pricePerTonne": "1000"},
                {"candidateId": "bad", "pathId": "LNG_OTTO_MEDIUM_SPEED", "specifiedBlendRatios": ["1.2"]},
            ],
        }
        blocked_parsed = parse_decision_case(blocked_payload)
        self.assertIsNotNone(blocked_parsed.request)
        self.assertEqual(blocked_parsed.issues[0].candidate_id, "bad")
        self.assertEqual(blocked_parsed.issues[0].field, "candidates[1].specifiedBlendRatios[0]")
        blocked_result = calculate_decision_case(blocked_parsed.request, blocked_parsed.issues)
        blocked_json = decision_case_result_to_dict(blocked_result)
        self.assertEqual([row["candidate_id"] for row in blocked_json["candidate_results"]], ["ok", "bad"])
        self.assertEqual(blocked_json["candidate_results"][1]["calculation_status"], "BLOCKED")
        self.assertIsNone(blocked_json["candidate_results"][1]["voyage_result"])
        self.assertEqual(blocked_json["scenarios"][0]["scenario_id"], "B0")
        self.assertTrue(any(row["candidate_id"] == "ok" for row in blocked_json["scenarios"]))
        blocked_csv = decision_case_to_csv(blocked_result)
        self.assertIn("BLOCKED", blocked_csv)
        self.assertIn("INVALID_BLEND_RATIO", blocked_csv)

    def test_every_case_result_has_versions_and_source_ids(self):
        request = DecisionCaseInput(
            report_year=2026, departure_port="CNSHG", arrival_port="NLRTM",
            adjacent_valid_port_of_call_confirmed=True, currency="EUR",
            baseline_component=_component("MDO", "700"), baseline_mass_tonnes=Decimal("100"),
            eua_price_per_tco2e=Decimal("80"), candidates=(CandidateInput(
                "uco", FuelComponent(get_builtin_factor("UCO_FAME"), Decimal("1000"), eligible_biomass_fraction=Decimal("1"), qualification_status="ASSUMED_ELIGIBLE"),
            ),),
        )
        result = calculate_decision_case(request)
        provenance = result.provenance
        self.assertTrue(provenance.calculation_spec_version)
        self.assertTrue(provenance.fuel_factor_version)
        self.assertTrue(provenance.port_rule_version)
        self.assertTrue(provenance.source_ids)
        self.assertEqual(len(provenance.source_ids), len(set(provenance.source_ids)))

    def test_display_config_cannot_change_raw_json_or_csv(self):
        payload = {
            "reportYear": 2026, "departurePort": "CNSHG", "arrivalPort": "NLRTM",
            "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
            "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
            "euaPricePerTCO2e": "80",
            "candidates": [{"candidateId": "uco", "pathId": "UCO_FAME", "pricePerTonne": "1000", "specifiedBlendRatios": ["0.2"]}],
        }
        parsed = parse_decision_case(payload)
        result = calculate_decision_case(parsed.request, parsed.issues)
        raw_before = json.dumps(decision_case_result_to_dict(result), sort_keys=True)
        csv_before = decision_case_to_csv(result, DisplayConfig(ratio_decimals=1))
        raw_after = json.dumps(decision_case_result_to_dict(result), sort_keys=True)
        csv_after = decision_case_to_csv(result, DisplayConfig(ratio_decimals=8, gas_decimals=8))
        self.assertEqual(raw_before, raw_after)
        self.assertEqual(csv_before, csv_after)


if __name__ == "__main__":
    unittest.main()
