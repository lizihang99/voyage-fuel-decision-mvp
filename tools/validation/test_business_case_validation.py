"""Contract and tamper tests for frozen synthetic business cases."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from business_case_schema import fingerprint, load_case, validate_case, write_case


def minimal_case():
    factor = {"path_id": "MDO", "lcv": ".0427", "wtt": "14.4", "co2": "3.206",
              "ch4": ".00005", "n2o": ".00018", "slip": None, "methane": False,
              "rwd": "1", "biomass": "0", "factor_status": "FIXED",
              "qualification": "NOT_DEMONSTRATED", "mode": "STATIC", "equipment_id": "MDO"}
    return {
        "id": "A-contract", "family": "A", "name": "Contract",
        "purpose": "Independent verification", "compact": True,
        "synthetic": True, "assumptions": ["All prices are synthetic"],
        "coverage": ["baseline"], "expected_issues": [], "expected_http_status": 200,
        "request": {"reportYear": 2025, "baseline": {"massTonnes": "100"},
                    "departurePort": "NLRTM", "arrivalPort": "DEHAM", "candidates": []},
        "snapshot": {"scope": {"geo": "1", "surrender": ".7", "fueleu": "1"},
                     "baseline": factor, "candidates": {}},
    }


class CaseContractTests(unittest.TestCase):
    def test_round_trip_and_fingerprint(self):
        case = minimal_case()
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(Path(directory), case, {"baseline": {"mass": "100"}})
            self.assertEqual(load_case(path), case)
            expected = json.loads((path / "expected.json").read_text(encoding="utf-8"))
            self.assertEqual(expected["input_sha256"], fingerprint(case))

    def test_tampered_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(Path(directory), minimal_case(), {})
            request = json.loads((path / "request.json").read_text(encoding="utf-8"))
            request["baseline"]["massTonnes"] = "101"
            (path / "request.json").write_text(json.dumps(request), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                load_case(path)

    def test_unsafe_id_float_missing_metadata_and_real_data_rejected(self):
        for key, value in (("id", "../escape"), ("synthetic", False),
                           ("coverage", []), ("purpose", "")):
            with self.subTest(key=key):
                case = minimal_case()
                case[key] = value
                with self.assertRaises(ValueError):
                    validate_case(case)
        case = minimal_case()
        case["request"]["baseline"]["massTonnes"] = 0.1
        with self.assertRaisesRegex(ValueError, "float"):
            validate_case(case)

    def test_canonical_digest_is_order_independent(self):
        self.assertEqual(fingerprint({"a": 1, "b": 2}), fingerprint({"b": 2, "a": 1}))

    def test_invalid_metadata_and_factor_numbers(self):
        for key, value in (("family", "D"), ("name", ["bad"]), ("coverage", "baseline"),
                           ("expected_issues", [{}]), ("request", {})):
            case = minimal_case()
            case[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_case(case)
        for field, value in (("lcv", "NaN"), ("lcv", "0"), ("co2", "-1"),
                             ("biomass", "2"), ("slip", "101")):
            case = minimal_case()
            case["snapshot"]["baseline"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_case(case)

    def test_case_import_blocker(self):
        from business_case_worker import ProductImportBlocker
        for name in ("voyage_fuel", "voyage_fuel.factors", "voyage_fuel.case_comparison"):
            with self.assertRaises(ImportError):
                ProductImportBlocker().find_spec(name)


class ComparisonMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Independent results must exist before even importing the product.
        from business_case_inputs import cases
        from business_case_reference import calculate_reference
        cls.case = next(c for c in cases() if c["id"] == "B-default")
        cls.expected = calculate_reference(cls.case)
        from voyage_fuel.json_io import parse_decision_case, decision_case_result_to_dict
        from voyage_fuel.case_calculator import calculate_parsed_decision_case
        cls.actual = decision_case_result_to_dict(
            calculate_parsed_decision_case(parse_decision_case(cls.case["request"])))

    def validate(self, actual):
        from business_case_assertions import validate_product_result
        return validate_product_result(self.case, self.expected, actual)

    def test_valid_product(self):
        result = self.validate(self.actual)
        self.assertEqual(result["differences"], [])
        self.assertGreater(result["assertions"], 300)

    def test_wrong_cost_winner_ratio_omitted_point_and_switch_are_detected(self):
        for mutation in ("cost", "winner", "ratio", "point", "switch", "factor", "null_reason", "rank"):
            with self.subTest(mutation=mutation):
                actual = copy.deepcopy(self.actual)
                if mutation == "cost":
                    actual["scenarios"][1]["result"]["model_cost"] = "0"
                elif mutation == "winner":
                    actual["economics"]["cost_min_scenario_id"] = "missing"
                elif mutation == "ratio":
                    actual["candidate_results"][0]["voyage_result"]["scenarios"][1]["ratio"] = ".9"
                elif mutation == "point":
                    actual["candidate_results"][0]["voyage_result"]["scenarios"].pop()
                elif mutation == "switch":
                    actual["economics"]["switch_points"] = []
                elif mutation == "factor":
                    actual["provenance"]["factor_resolutions"][0]["factor"]["lcv_mj_per_g"] = "1"
                elif mutation == "null_reason":
                    actual["field_reasons"] = {}
                elif mutation == "rank":
                    actual["scenarios"][0]["current_model_cost_rank"] = 999
                self.assertTrue(self.validate(actual)["differences"], mutation)


if __name__ == "__main__":
    unittest.main()
