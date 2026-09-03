import csv
import io
import json
import unittest
from decimal import Decimal
from dataclasses import replace
from pathlib import Path

from voyage_fuel.case_calculator import calculate_decision_case
from voyage_fuel.contracts import CandidateInput, DecisionCaseInput, Issue
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.json_io import decision_case_result_to_dict, parse_decision_case
from voyage_fuel.models import FuelComponent
from voyage_fuel.formatting import DisplayConfig, format_for_display
from voyage_fuel.reports import decision_case_to_csv, write_decision_case_csv
from voyage_fuel.reports import decision_case_to_pdf, write_decision_case_pdf


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

    def make_multi_candidate_result(self):
        fixture = Path(__file__).parent / "fixtures" / "multi_candidate_case.json"
        return calculate_decision_case(parse_decision_case(json.loads(fixture.read_text(encoding="utf-8"))).request)

    def test_complete_pdf_contains_all_auditable_sections_and_scenarios(self):
        result = self.make_multi_candidate_result()
        pdf = decision_case_to_pdf(result)
        self.assertTrue(pdf.startswith(b"%PDF"))
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)
        expected = (
            "2026", "CNSHG", "NLRTM", "EUR", "voyage-level", "EU ETS", "FuelEU", "ONE_IN_SCOPE",
            "B0", "uco-quote-1@0.2", "lng-quote-1@0.1", "Fuel mass", "Energy", "Fuel cost",
            "CO2", "CH4", "N2O", "EUAs", "EUA cost", "Model cost", "WtT", "TtW", "GHGI",
            "Target", "Balance", "Indicative penalty", "annual", "relative-to-B0", "factor status",
            "Qualification", "Requested path", "Resolved path", "Evidence", "BLOCKED", "FEASIBLE",
            "Conditional", "switch", "2026-08-07", "2026-08-31-audit", "2026-07-23",
            "independent physical lifecycle WtW reduction", "ETS effective rate",
            "Excluded gases", "Zero-rating status", "Equipment ID", "Target-min-cost scenario",
        )
        for fragment in expected:
            self.assertIn(fragment.casefold(), text.casefold(), fragment)

    def test_pdf_uses_port_identities_and_lists_full_change_metric_set(self):
        result = self.make_multi_candidate_result()
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(decision_case_to_pdf(result))).pages)
        for fragment in (
            "Departure EU ETS identity", "Arrival EU ETS identity", "Departure FuelEU identity",
            "Arrival FuelEU identity", "EU ETS reason", "FuelEU reason", "THIRD_COUNTRY", "IN_SCOPE",
            "Baseline fuel mass", "Candidate fuel mass", "Physical energy", "CO2", "CH4", "N2O",
            "WtT", "TtW", "GHGI", "Target", "Compliance balance", "Indicative penalty equivalent",
            "Reference-adjusted cost", "Delta", "Relative-to-B0",
        ):
            self.assertIn(fragment.casefold(), text.casefold(), fragment)

    def test_csv_issue_rows_preserve_scenario_and_component_location(self):
        payload = {
            "reportYear": 2026, "departurePort": "CNSHG", "arrivalPort": "NLRTM",
            "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
            "baseline": {"pathId": "MGO", "massTonnes": "100"},
            "candidates": [{"candidateId": "bad", "pathId": "UNKNOWN_PATH", "maxBlendRatio": "invalid"}],
        }
        parsed = parse_decision_case(payload)
        result = calculate_decision_case(parsed.request, parsed.issues)
        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(result))))
        issue = next(row for row in rows if row["record_type"] == "issue" and row["issue_code"])
        self.assertEqual(issue["candidate_id"], "bad")
        self.assertEqual(issue["issue_component"], "UNKNOWN_PATH")
        self.assertEqual(issue["component"], "UNKNOWN_PATH")
        self.assertTrue(issue["issue_field"])
        self.assertIn("scenario_id", issue)

    def test_pdf_issue_dedup_keeps_same_issue_fields_with_different_components(self):
        result = self.make_result()
        result = replace(result, issues=(
            Issue(code="FACTOR_EVIDENCE_REQUIRED", scope="CANDIDATE", field="factor", blocking=True,
                  message="evidence required", candidate_id="uco", scenario_id="uco@0.2", component="UCO_FAME"),
            Issue(code="FACTOR_EVIDENCE_REQUIRED", scope="CANDIDATE", field="factor", blocking=True,
                  message="evidence required", candidate_id="uco", scenario_id="uco@0.2", component="MGO"),
        ))
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(decision_case_to_pdf(result))).pages)
        self.assertGreaterEqual(text.count("UCO_FAME"), 1)
        self.assertGreaterEqual(text.count("MGO"), 1)

    def test_pdf_display_config_changes_rendered_precision_only(self):
        result = self.make_multi_candidate_result()
        before = json.dumps(decision_case_result_to_dict(result), sort_keys=True)
        csv_before = decision_case_to_csv(result, DisplayConfig(ratio_decimals=1))
        pdf_default = decision_case_to_pdf(result, DisplayConfig(ratio_decimals=1, gas_decimals=2))
        pdf_precise = decision_case_to_pdf(result, DisplayConfig(ratio_decimals=6, gas_decimals=8))
        self.assertNotEqual(pdf_default, pdf_precise)
        self.assertEqual(csv_before, decision_case_to_csv(result, DisplayConfig(ratio_decimals=6, gas_decimals=8)))
        self.assertEqual(before, json.dumps(decision_case_result_to_dict(result), sort_keys=True))

    def test_write_case_pdf(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = write_decision_case_pdf(self.make_multi_candidate_result(), f"{directory}/case.pdf")
            self.assertTrue(path.exists())
            self.assertTrue(path.read_bytes().startswith(b"%PDF"))

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
        self.assertEqual(format_for_display(Decimal("12345.6789"), "energy_gj", config), "12.346")
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

    def test_case_csv_contains_case_constraints_economics_and_ets_states(self):
        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(self.make_result()))))
        self.assertIn("constraints", {row["record_type"] for row in rows})
        economics = next(row for row in rows if row["record_type"] == "economics")
        self.assertTrue(economics["comparison_status"])
        self.assertTrue(economics["cost_min_scenario_id"])
        self.assertIn("x_budget", next(row for row in rows if row["record_type"] == "constraints"))
        scenario_rows = [row for row in rows if row["record_type"] == "scenario"]
        self.assertTrue(any(row["ets_effective_rate"] for row in scenario_rows))
        self.assertTrue(any(row["ets_excluded_gases"] for row in scenario_rows))
        self.assertTrue(any(row["zero_rating_status"] for row in scenario_rows))

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

    def test_custom_factor_evidence_is_complete_in_csv_and_pdf(self):
        units = {
            "lcv": "MJ/gFuel", "wtT": "gCO2eq/MJ", "cfCO2": "gGHG/gFuel",
            "cfCH4": "gGHG/gFuel", "cfN2O": "gGHG/gFuel", "cslip": "%",
            "methaneSlipApplicable": "boolean", "rwd": "ratio", "eligibleBiomassFraction": "fraction",
        }
        evidence = {
            field: [{"sourceId": f"SRC-{field}", "sourceType": "TEST", "unit": unit, "verificationStatus": "VERIFIED"}]
            for field, unit in units.items()
        }
        payload = {
            "reportYear": 2026, "departurePort": "CNSHG", "arrivalPort": "NLRTM",
            "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
            "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
            "euaPricePerTCO2e": "80",
            "candidates": [{
                "candidateId": "custom", "pricePerTonne": "900", "specifiedBlendRatios": ["0.2"],
                "pathId": "CUSTOM_FACTOR", "custom": True, "equipmentId": "CUSTOM_ENGINE",
                "lcv": "0.04", "wtTMode": "STATIC", "wtT": "10", "cfCO2": "3", "cfCH4": "0", "cfN2O": "0",
                "cslip": "NA", "methaneSlipApplicable": False, "rwd": "1", "eligibleBiomassFraction": "0",
                "sourceEvidence": evidence,
            }],
        }
        result = calculate_decision_case(parse_decision_case(payload).request)
        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(result))))
        factor_rows = [row for row in rows if row["record_type"] == "factor_evidence"]
        fields = {row["evidence_field"] for row in factor_rows}
        self.assertIn("methaneSlipApplicable", fields)
        self.assertIn("eligibleBiomassFraction", fields)
        for row in factor_rows:
            self.assertTrue(row["factor_source_id"])
            self.assertTrue(row["unit"])
            self.assertTrue(row["verification_status"])
        from pypdf import PdfReader
        pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(decision_case_to_pdf(result))).pages)
        for fragment in ("methaneSlipApplicable", "eligibleBiomassFraction", "SRC-methaneSlipApplicable", "VERIFIED", "boolean", "fraction"):
            self.assertIn(fragment.casefold(), pdf_text.casefold())

    def test_custom_bio_e_report_preserves_e_evidence_value(self):
        units = {
            "lcv": "MJ/gFuel", "E": "gCO2eq/MJ", "cfCO2": "gGHG/gFuel",
            "cfCH4": "gGHG/gFuel", "cfN2O": "gGHG/gFuel", "cslip": "%",
            "methaneSlipApplicable": "boolean", "rwd": "ratio", "eligibleBiomassFraction": "fraction",
        }
        values = {"lcv": "0.037", "E": "14.9", "cfCO2": "2.834", "cfCH4": "0.00005", "cfN2O": "0.00018", "cslip": "NA", "methaneSlipApplicable": False, "rwd": "1", "eligibleBiomassFraction": "0"}
        evidence = {
            field: [{"sourceId": f"SRC-{field}", "sourceType": "TEST", "unit": unit, "verificationStatus": "VERIFIED"}]
            for field, unit in units.items()
        }
        payload = {
            "reportYear": 2026, "departurePort": "CNSHG", "arrivalPort": "NLRTM",
            "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
            "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
            "euaPricePerTCO2e": "80",
            "candidates": [{
                "candidateId": "bio-e", "pricePerTonne": "900", "specifiedBlendRatios": ["0.2"],
                "pathId": "CUSTOM_BIO_E", "custom": True, "equipmentId": "BIO_ENGINE",
                "lcv": values["lcv"], "wtTMode": "BIO_E", "E": values["E"],
                "cfCO2": values["cfCO2"], "cfCH4": values["cfCH4"], "cfN2O": values["cfN2O"],
                "cslip": values["cslip"], "methaneSlipApplicable": values["methaneSlipApplicable"],
                "rwd": values["rwd"], "eligibleBiomassFraction": values["eligibleBiomassFraction"],
                "qualificationStatus": "ASSUMED_ELIGIBLE", "sourceEvidence": evidence,
            }],
        }
        result = calculate_decision_case(parse_decision_case(payload).request)
        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(result))))
        e_rows = [row for row in rows if row["record_type"] == "factor_evidence" and row["requested_path_id"] == "CUSTOM_BIO_E" and row["evidence_field"] == "E"]
        self.assertEqual(len(e_rows), 1)
        self.assertEqual(e_rows[0]["factor_value"], "14.9")
        from pypdf import PdfReader
        pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(decision_case_to_pdf(result))).pages)
        self.assertIn("SRC-E", pdf_text)
        self.assertIn("14.9", pdf_text)

    def test_custom_rfnbo_e_report_preserves_e_and_eu_evidence_values(self):
        units = {
            "lcv": "MJ/gFuel", "E": "gCO2eq/MJ", "eu": "gCO2eq/MJ",
            "cfCO2": "gGHG/gFuel", "cfCH4": "gGHG/gFuel", "cfN2O": "gGHG/gFuel",
            "cslip": "%", "methaneSlipApplicable": "boolean", "rwd": "ratio",
            "eligibleBiomassFraction": "fraction",
        }
        evidence = {
            field: [{"sourceId": f"SRC-{field}", "sourceType": "TEST", "unit": unit, "verificationStatus": "VERIFIED"}]
            for field, unit in units.items()
        }
        payload = {
            "reportYear": 2026, "departurePort": "CNSHG", "arrivalPort": "NLRTM",
            "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
            "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
            "euaPricePerTCO2e": "80",
            "candidates": [{
                "candidateId": "rfnbo-e", "pricePerTonne": "900", "specifiedBlendRatios": ["0.2"],
                "pathId": "CUSTOM_RFNBO_E", "custom": True, "equipmentId": "RFNBO_ENGINE",
                "lcv": "0.04", "wtTMode": "RFNBO_E", "E": "28.2", "eu": "20",
                "cfCO2": "3", "cfCH4": "0", "cfN2O": "0", "cslip": "NA",
                "methaneSlipApplicable": False, "rwd": "2", "eligibleBiomassFraction": "0",
                "qualificationStatus": "ASSUMED_ELIGIBLE", "sourceEvidence": evidence,
            }],
        }
        result = calculate_decision_case(parse_decision_case(payload).request)
        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(result))))
        factor_rows = [row for row in rows if row["record_type"] == "factor_evidence" and row["requested_path_id"] == "CUSTOM_RFNBO_E"]
        values = {row["evidence_field"]: row["factor_value"] for row in factor_rows}
        self.assertEqual(values.get("E"), "28.2")
        self.assertEqual(values.get("eu"), "20")
        from pypdf import PdfReader
        pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(decision_case_to_pdf(result))).pages)
        self.assertIn("SRC-eu", pdf_text)
        self.assertIn("20", pdf_text)

    def test_report_uses_actual_component_biomass_fraction(self):
        request = DecisionCaseInput(
            report_year=2026,
            departure_port="CNSHG",
            arrival_port="NLRTM",
            adjacent_valid_port_of_call_confirmed=True,
            currency="EUR",
            baseline_component=FuelComponent(get_builtin_factor("MGO"), Decimal("700")),
            baseline_mass_tonnes=Decimal("100"),
            eua_price_per_tco2e=Decimal("80"),
            candidates=(CandidateInput(
                candidate_id="uco-default",
                component=FuelComponent(get_builtin_factor("UCO_FAME"), Decimal("1000")),
                specified_blend_ratios=(Decimal("0.2"),),
            ),),
        )
        result = calculate_decision_case(request)
        rows = list(csv.DictReader(io.StringIO(decision_case_to_csv(result))))
        uco_rows = [row for row in rows if row["record_type"] == "factor_evidence" and row["requested_path_id"] == "UCO_FAME" and row["evidence_field"] == "eligibleBiomassFraction"]
        self.assertEqual(len(uco_rows), 1)
        self.assertEqual(uco_rows[0]["factor_value"], "0")
        from pypdf import PdfReader
        pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(decision_case_to_pdf(result))).pages)
        self.assertIn("eligibleBiomassFraction", pdf_text)

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
