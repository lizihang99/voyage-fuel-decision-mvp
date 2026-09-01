import csv
import io
import json
import unittest
from decimal import Decimal

from voyage_fuel.case_calculator import calculate_decision_case
from voyage_fuel.contracts import CandidateInput, DecisionCaseInput
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.json_io import decision_case_result_to_dict, parse_decision_case
from voyage_fuel.models import FuelComponent
from voyage_fuel.formatting import DisplayConfig, format_for_display
from voyage_fuel.reports import decision_case_to_csv, write_decision_case_csv


class CaseReportTests(unittest.TestCase):
    def make_result(self):
        request = DecisionCaseInput(
            report_year=2026,
            departure_port="CNSHG",
            arrival_port="NLRTM",
            adjacent_valid_port_of_call_confirmed=True,
            currency="USD",
            baseline_component=FuelComponent(get_builtin_factor("MGO"), Decimal("600")),
            baseline_mass_tonnes=Decimal("100"),
            eua_price_per_tco2e=Decimal("80"),
            candidates=(CandidateInput(
                candidate_id="uco",
                component=FuelComponent(get_builtin_factor("UCO_FAME"), Decimal("1000"), eligible_biomass_fraction=Decimal("1"), qualification_status="ASSUMED_ELIGIBLE"),
                specified_blend_ratios=(Decimal("0.20"),),
                max_blend_ratio=Decimal("0.30"),
                allows_pure_use=True,
            ),),
        )
        return calculate_decision_case(request)

    def test_display_defaults_and_presentation_format(self):
        config = DisplayConfig()
        self.assertEqual(config.fuel_mass_decimals, 3)
        self.assertEqual(config.energy_decimals, 3)
        self.assertEqual(config.ratio_decimals, 4)
        self.assertEqual(config.scope_rate_decimals, 2)
        self.assertEqual(config.intensity_decimals, 4)
        self.assertEqual(config.gas_decimals, 6)
        self.assertEqual(config.price_decimals, 2)
        self.assertEqual(config.factor_decimals, 9)
        self.assertEqual(format_for_display(Decimal("12.34567"), "fuel_mass", config), "12.346")
        self.assertEqual(format_for_display(Decimal("0.123456"), "ratio", config), "12.3456")
        self.assertEqual(format_for_display(Decimal("1.2300000000"), "factor", config), "1.23")

    def test_case_csv_contains_auditable_record_types_and_raw_values(self):
        result = self.make_result()
        text = decision_case_to_csv(result)
        self.assertNotIn("E-", text)
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertTrue({"case", "port", "scenario", "recommendation", "switch_point", "factor_evidence", "issue"}.issubset({r["record_type"] for r in rows}))
        self.assertIn("calculation_spec_version", rows[0])
        self.assertIn("source_ids", rows[0])
        self.assertTrue(any(r["scenario_id"] == "B0" for r in rows if r["record_type"] == "scenario"))
        self.assertTrue(any(r["scenario_id"] == "uco@0.2" for r in rows if r["record_type"] == "scenario"))
        self.assertTrue(all("EUR" == r["penalty_currency"] for r in rows))
        self.assertTrue(any(r["metric_name"] == "model_cost" and r["absolute"] for r in rows if r["record_type"] == "scenario"))

    def test_display_config_does_not_change_raw_result_or_csv(self):
        result = self.make_result()
        before = json.dumps(decision_case_result_to_dict(result), sort_keys=True)
        csv_before = decision_case_to_csv(result, DisplayConfig(fuel_mass_decimals=1))
        csv_after = decision_case_to_csv(result, DisplayConfig(fuel_mass_decimals=8, ratio_decimals=1))
        self.assertEqual(csv_before, csv_after)
        self.assertEqual(before, json.dumps(decision_case_result_to_dict(result), sort_keys=True))

    def test_write_case_csv(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = write_decision_case_csv(self.make_result(), f"{directory}/case.csv")
            self.assertTrue(path.exists())
            self.assertIn("record_type", path.read_text(encoding="utf-8"))

    def test_csv_deduplicates_projected_candidate_issues(self):
        payload = {
            "reportYear": 2026, "departurePort": "CNSHG", "arrivalPort": "NLRTM",
            "adjacentValidPortOfCallConfirmed": True, "currency": "USD",
            "baseline": {"pathId": "MGO", "massTonnes": "100"},
            "candidates": [{"candidateId": "bad", "pathId": "MGO", "maxBlendRatio": "invalid"}],
        }
        result = calculate_decision_case(parse_decision_case(payload).request, parse_decision_case(payload).issues)
        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(result))))
        issues = [row for row in rows if row["record_type"] == "issue" and row["issue_code"]]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["candidate_id"], "bad")

    def test_factor_evidence_rows_include_numeric_factor_values(self):
        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(self.make_result()))))
        evidence = [row for row in rows if row["record_type"] == "factor_evidence"]
        self.assertTrue(any(row["factor_field"] == "lcv_mj_per_g" and row["factor_value"] for row in evidence))
        self.assertTrue(all("E-" not in row["factor_value"] for row in evidence))

    def test_currency_columns_for_penalty_and_recommendation_values(self):
        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(self.make_result()))))
        penalties = [row for row in rows if row["record_type"] == "scenario" and row["metric_name"] == "fueleu_indicative_penalty_eur"]
        self.assertTrue(penalties)
        self.assertTrue(all(row["value_currency"] == "EUR" and row["penalty_currency"] == "EUR" for row in penalties))
        priced_recommendations = [row for row in rows if row["record_type"] == "recommendation" and row["value_star"]]
        self.assertTrue(priced_recommendations)
        self.assertTrue(all(row["unit"] == "case_currency" and row["value_currency"] == "USD" for row in priced_recommendations))


if __name__ == "__main__":
    unittest.main()
