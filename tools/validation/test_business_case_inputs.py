"""Contract tests for synthetic inputs, independent of the calculation kernel."""

import ast
from copy import deepcopy
from fractions import Fraction as F
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


BUILDER = Path(__file__).with_name("business_case_inputs.py")
SPEC = importlib.util.spec_from_file_location("business_case_inputs", BUILDER)
MODULE = importlib.util.module_from_spec(SPEC)
if BUILDER.exists():
    SPEC.loader.exec_module(MODULE)


class BusinessCaseInputsTests(unittest.TestCase):
    def cases(self):
        self.assertTrue(callable(getattr(MODULE, "cases", None)), "cases() builder is missing")
        return MODULE.cases()

    def by_id(self, case_id):
        return next(case for case in self.cases() if case["id"] == case_id)

    def test_metadata_ids_and_json_primitives(self):
        cases = self.cases()
        self.assertGreaterEqual(len(cases), 50)
        self.assertLessEqual(len(cases), 80)
        self.assertEqual(len(cases), len({case["id"] for case in cases}))
        self.assertEqual(json.loads(json.dumps(cases, ensure_ascii=False)), cases)
        self.assertEqual({case["family"] for case in cases}, set("ABCD"))
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(set(case), {
                    "id", "family", "name", "purpose", "compact", "synthetic",
                    "assumptions", "coverage", "request", "snapshot",
                    "expected_issues", "expected_http_status",
                })
                self.assertTrue(case["id"].startswith(case["family"] + "-"))
                self.assertIs(case["synthetic"], True)
                self.assertIs(type(case["compact"]), bool)
                for key in ("name", "purpose"):
                    self.assertRegex(case[key], r"[\u4e00-\u9fff]")
                for key in ("assumptions", "coverage"):
                    self.assertIsInstance(case[key], list)
                    self.assertTrue(case[key])
                    self.assertTrue(all(isinstance(x, str) and x for x in case[key]))
        compact = [case for case in cases if case["compact"]]
        self.assertEqual({case["family"] for case in compact}, set("ABCD"))
        self.assertLessEqual(len(compact), 12)

    def test_calls_and_cases_do_not_share_mutable_payloads(self):
        first = self.cases()
        pristine = deepcopy(first)
        first[0]["request"]["baseline"]["pricePerTonne"] = "999999"
        first[0]["snapshot"]["baseline"]["lcv"] = "99"
        first[0]["assumptions"].append("changed")
        self.assertEqual(self.cases(), pristine)
        b = next(case for case in first if case["id"] == "B-default")
        b["request"]["candidates"][0]["pricePerTonne"] = "1"
        reverse = next(case for case in first if case["id"] == "B-reverse")
        self.assertEqual(reverse["request"]["candidates"][-1]["pricePerTonne"], "950")

    def test_full_requests_scopes_and_normalized_snapshot_contract(self):
        factors_required = {
            "path_id", "lcv", "wtt", "co2", "ch4", "n2o", "slip", "methane",
            "rwd", "biomass", "factor_status", "qualification", "mode", "equipment_id",
        }
        pairs = {("CNSHG", "NLRTM"): "0.5", ("NLRTM", "DEHAM"): "1",
                 ("CNSHG", "SGSIN"): "0"}
        for case in self.cases():
            with self.subTest(case=case["id"]):
                request, snapshot = case["request"], case["snapshot"]
                self.assertTrue({
                    "reportYear", "departurePort", "arrivalPort",
                    "adjacentValidPortOfCallConfirmed", "currency", "baseline",
                    "euaPricePerTCO2e", "candidates",
                } <= request.keys())
                self.assertIs(type(request["reportYear"]), int)
                self.assertEqual(request["currency"], "EUR")
                self.assertGreater(F(request["baseline"]["massTonnes"]), 0)
                geo = pairs[(request["departurePort"], request["arrivalPort"])]
                self.assertEqual(snapshot["scope"], {
                    "geo": geo,
                    "surrender": {2024: "0.4", 2025: "0.7"}.get(request["reportYear"], "1"),
                    "fueleu": None if request["reportYear"] == 2024 else geo,
                })
                ids = [candidate["candidateId"] for candidate in request["candidates"]]
                self.assertEqual(len(ids), len(set(ids)))
                blocked = {
                    issue["candidate_id"] for issue in case["expected_issues"]
                    if issue["scope"] == "CANDIDATE" and issue["code"] not in {
                        "PRICE_REQUIRED_FOR_COMPARISON", "BUDGET_UNAVAILABLE_WITHOUT_PRICES",
                    }
                }
                self.assertEqual(set(snapshot["candidates"]), set(ids) - blocked)
                for factor in [snapshot["baseline"], *snapshot["candidates"].values()]:
                    self.assertTrue(factors_required <= factor.keys())
                    for key in ("lcv", "wtt", "co2", "ch4", "n2o", "rwd", "biomass"):
                        self.assertIsInstance(factor[key], str)
                        F(factor[key])
                    self.assertGreater(F(factor["lcv"]), 0)
                    self.assertTrue(0 <= F(factor["biomass"]) <= 1)
                    self.assertIs(type(factor["methane"]), bool)
                    self.assertTrue(factor["equipment_id"])
                    if factor["slip"] is not None:
                        self.assertIsInstance(factor["slip"], str)
                        self.assertTrue(0 <= F(factor["slip"]) <= 100)
                    if factor["methane"]:
                        self.assertEqual(
                            [factor[k] for k in ("csf_co2", "csf_ch4", "csf_n2o")],
                            ["0", "1", "0"],
                        )

    def test_a_baseline_boundaries_and_manual_zero_anchor(self):
        for case_id, year in (("A-2024", 2024), ("A-2025", 2025), ("A-2030", 2030)):
            case = self.by_id(case_id)
            self.assertEqual(case["request"]["reportYear"], year)
            self.assertEqual(case["request"]["candidates"], [])
        self.assertEqual(self.by_id("A-zero-scope")["snapshot"]["scope"]["geo"], "0")
        anchor = self.by_id("A-manual-zero")
        factor = anchor["snapshot"]["baseline"]
        self.assertEqual([F(factor[k]) for k in ("wtt", "co2", "ch4", "n2o")], [0]*4)
        self.assertEqual(F(factor["lcv"]), F("0.04"))
        self.assertEqual(anchor["request"]["baseline"]["massTonnes"], "1000")
        self.assertEqual(anchor["request"]["baseline"]["pricePerTonne"], "0")
        self.assertEqual(anchor["request"]["euaPricePerTCO2e"], "0")
        self.assertIn("manual_zero_anchor", anchor["coverage"])

    def test_b_six_quotes_and_exact_e_based_snapshots(self):
        case = self.by_id("B-default")
        req = case["request"]
        self.assertEqual((req["reportYear"], req["departurePort"], req["arrivalPort"]),
                         (2030, "NLRTM", "DEHAM"))
        self.assertEqual(req["baseline"], {
            "pathId": "MDO", "massTonnes": "1000", "pricePerTonne": "700",
        })
        self.assertEqual(req["euaPricePerTCO2e"], "80")
        self.assertEqual(
            [(c["candidateId"], c["pathId"], c["pricePerTonne"], c["maxBlendRatio"])
             for c in req["candidates"]],
            [("uco-limited", "UCO_FAME", "950", "0.5"),
             ("uco-bulk", "UCO_FAME", "1150", "0.5"),
             ("hvo", "HVO", "1100", "0.5"),
             ("bio", "BIODIESEL", "1200", "0.5"),
             ("e-diesel", "E_DIESEL", "1600", "0.7"),
             ("uco-high", "UCO_FAME", "1400", "0.5")],
        )
        self.assertEqual(req["candidates"][0]["candidateSupplyTonnes"], "30")
        self.assertTrue(all(c["specifiedBlendRatios"] == ["0.01", "0.05"] for c in req["candidates"]))
        normalized = case["snapshot"]["candidates"]
        self.assertEqual(F(normalized["uco-limited"]["wtt"]), F("-22827/370"))
        self.assertEqual(F(normalized["hvo"]["wtt"]), F("-2235/44"))
        self.assertEqual(F(normalized["bio"]["wtt"]), F("-1539/37"))
        self.assertEqual(F(normalized["e-diesel"]["wtt"]), -45)
        self.assertEqual(normalized["e-diesel"]["rwd"], "2")
        self.assertTrue(any("鹿特丹" in text and "合成" in text for text in case["assumptions"]))

    def test_b_prior_variants_and_constraint_extensions(self):
        variants = {
            "default", "eua0", "eua200", "hvo-budget0", "hvo-budget1000",
            "hvo-supply0", "hvo-supply50", "hvo-cap005", "rfnbo-unqualified",
            "all-budgets1000", "hvo-price600", "reverse", "reference-value100", "combined-constraints",
            "missing-price-budget", "b100-allowed", "b100-forbidden", "duplicate-ties",
        }
        self.assertTrue({"B-" + v for v in variants} <= {c["id"] for c in self.cases()})
        default = self.by_id("B-default")["request"]["candidates"]
        self.assertEqual(self.by_id("B-reverse")["request"]["candidates"], default[::-1])
        for suffix, field, value in (
            ("hvo-budget0", "incrementalBudget", "0"),
            ("hvo-budget1000", "incrementalBudget", "1000"),
            ("hvo-supply0", "candidateSupplyTonnes", "0"),
            ("hvo-supply50", "candidateSupplyTonnes", "50"),
            ("hvo-cap005", "maxBlendRatio", "0.05"),
            ("hvo-price600", "pricePerTonne", "600"),
        ):
            req = self.by_id("B-" + suffix)["request"]
            hvo = next(c for c in req["candidates"] if c["candidateId"] == "hvo")
            self.assertEqual(hvo[field], value)
        for suffix, value in (("eua0", "0"), ("eua200", "200")):
            self.assertEqual(self.by_id("B-" + suffix)["request"]["euaPricePerTCO2e"], value)
        unqualified = self.by_id("B-rfnbo-unqualified")["snapshot"]["candidates"]["e-diesel"]
        self.assertEqual((unqualified["path_id"], unqualified["wtt"], unqualified["rwd"]),
                         ("MDO", "14.4", "1"))
        tied = self.by_id("B-duplicate-ties")["request"]["candidates"]
        first, second = (deepcopy(c) for c in tied if c["candidateId"] in {"uco-bulk", "uco-bulk-twin"})
        first.pop("candidateId")
        second.pop("candidateId")
        self.assertEqual(first, second)

    def test_c_years_equipment_slip_and_qualification_matrix(self):
        cases = [case for case in self.cases() if case["family"] == "C"]
        expected_slip = {"OTTO_MS": "3.1", "OTTO_SS": "1.7", "DIESEL_SS": "0.2", "LBSI": "2.6"}
        self.assertEqual(len(cases), 8)
        for equipment, slip in expected_slip.items():
            for year in (2025, 2026):
                case = self.by_id(f"C-{equipment}-{year}")
                self.assertEqual(case["request"]["reportYear"], year)
                snapshot = case["snapshot"]
                for factor in [snapshot["baseline"], *snapshot["candidates"].values()]:
                    self.assertIn(factor["equipment_id"], {
                        "LNG_" + equipment, "BIOLNG_" + equipment, "E_LNG_" + equipment,
                    })
                    self.assertEqual(factor["slip"], slip)
                    self.assertIs(factor["methane"], True)
                qualified = {c["qualificationStatus"] for c in case["request"]["candidates"]}
                self.assertEqual(qualified, {
                    "NOT_DEMONSTRATED", "ASSUMED_ELIGIBLE", "VERIFIED_ELIGIBLE", "INELIGIBLE",
                })
                self.assertTrue(any("兼容" in text for text in case["assumptions"]))

    def test_c_normalizes_qualified_and_fallback_paths_without_mixing_lcvs(self):
        for case in [c for c in self.cases() if c["family"] == "C"]:
            factors = case["snapshot"]["candidates"]
            fossil = case["snapshot"]["baseline"]
            self.assertEqual(fossil["lcv"], "0.0491")
            for key, fraction, status in (
                ("bio-unqualified", "0", "ESTIMATED"),
                ("bio-assumed", "1", "ESTIMATED"),
                ("bio-verified", "1", "VERIFIED"),
            ):
                factor = factors[key]
                self.assertEqual((factor["lcv"], F(factor["wtt"])), ("0.050", -35))
                self.assertEqual((factor["biomass"], factor["factor_status"]), (fraction, status))
                self.assertEqual(factor["rwd"], "1")
            for key in ("e-unqualified", "e-ineligible"):
                factor = factors[key]
                for field in ("path_id", "lcv", "wtt", "co2", "ch4", "n2o", "slip",
                              "equipment_id", "rwd", "factor_status", "mode"):
                    self.assertEqual(factor[field], fossil[field], (case["id"], key, field))
            for key, e, wtt, status in (
                ("e-assumed", "28.2", "-28", "ESTIMATED"),
                ("e-verified", "20", "-36.2", "VERIFIED"),
            ):
                factor = factors[key]
                self.assertEqual((factor["lcv"], F(factor["wtt"])), ("0.0491", F(wtt)))
                self.assertEqual((factor["rwd"], factor["biomass"]), ("2", "0"))
                self.assertEqual((factor["e"], factor["eu"]), (e, "56.2"))
                self.assertEqual(factor["factor_status"], status)

    def test_extensions_actually_exercise_all_constraints_and_pure_use(self):
        combined = self.by_id("B-combined-constraints")["request"]["candidates"]
        hvo = next(c for c in combined if c["candidateId"] == "hvo")
        self.assertEqual(
            (hvo["incrementalBudget"], hvo["candidateSupplyTonnes"], hvo["maxBlendRatio"]),
            ("1000", "50", "0.05"),
        )
        budgeted = self.by_id("B-all-budgets1000")["request"]["candidates"]
        self.assertTrue(all(c["incrementalBudget"] == "1000" for c in budgeted))
        for suffix, permission in (("allowed", True), ("forbidden", False)):
            candidates = self.by_id("B-b100-" + suffix)["request"]["candidates"]
            hvo = next(c for c in candidates if c["candidateId"] == "hvo")
            self.assertIs(hvo["candidateAllowsPureUse"], permission)
            self.assertEqual(hvo["maxBlendRatio"], "1")
            self.assertIn("1", hvo["specifiedBlendRatios"])
        missing = next(c for c in self.by_id("B-missing-price-budget")["request"]["candidates"]
                       if c["candidateId"] == "hvo")
        self.assertIsNone(missing["pricePerTonne"])
        self.assertEqual(missing["incrementalBudget"], "1000")

    def test_built_in_qualification_inputs_have_effective_biomass_and_full_fallback(self):
        for label, fraction, status in (
            ("unqualified", "0", "ESTIMATED"), ("assumed", "0.5", "ESTIMATED"),
            ("verified", "1", "VERIFIED"),
        ):
            factor = self.by_id("D-bio-" + label)["snapshot"]["candidates"]["bio"]
            self.assertEqual(factor["biomass"], fraction)
            self.assertEqual(factor["factor_status"], status)
            self.assertEqual(F(factor["wtt"]), F("-22827/370"))
            self.assertEqual((factor["ch4"], factor["n2o"]), ("0.00005", "0.00018"))
        for label, path, wtt, rwd, status in (
            ("unqualified", "MDO", "14.4", "1", "FIXED"),
            ("ineligible", "MDO", "14.4", "1", "FIXED"),
            ("assumed", "E_DIESEL", "-45", "2", "ESTIMATED"),
            ("verified", "E_DIESEL", "-53.2", "2", "VERIFIED"),
        ):
            factor = self.by_id("D-rfnbo-" + label)["snapshot"]["candidates"]["renewable"]
            self.assertEqual((factor["path_id"], F(factor["wtt"]), factor["rwd"]),
                             (path, F(wtt), rwd))
            self.assertEqual(factor["factor_status"], status)
            self.assertEqual(factor["biomass"], "0")
            self.assertEqual(factor["co2"], "3.206")

    def test_invalid_inputs_contain_the_named_defect_not_a_valid_lookalike(self):
        for suffix, field in (("co2", "cfCO2"), ("ch4", "cfCH4"), ("n2o", "cfN2O")):
            invalid = self.by_id("D-negative-" + suffix)["request"]["candidates"][0]
            self.assertLess(F(invalid[field]), 0)
        invalid = self.by_id("D-missing-evidence")["request"]["candidates"][0]
        self.assertNotIn("cfCH4", invalid["sourceEvidence"])
        invalid = self.by_id("D-wrong-unit")["request"]["candidates"][0]
        self.assertEqual(invalid["sourceEvidence"]["lcv"]["unit"], "MJ/kg")
        invalid = self.by_id("D-nonmethane-slip")["request"]["candidates"][0]
        self.assertIs(invalid["methaneSlipApplicable"], False)
        self.assertGreater(F(invalid["cslip"]), 0)
        case = self.by_id("D-rwd2-2024")
        self.assertEqual(case["request"]["reportYear"], 2024)
        self.assertEqual(case["request"]["candidates"][0]["rwd"], "2")
        self.assertEqual(self.by_id("D-e283")["request"]["candidates"][0]["E"], "28.3")
        invalid = self.by_id("D-unknown-path")["request"]["candidates"][0]
        self.assertEqual(invalid["pathId"], "SYNTHETIC_UNKNOWN")
        self.assertNotIn("custom", invalid)
        self.assertNotIn("lcv", invalid)

    def test_custom_modes_have_explicit_field_evidence_and_independent_values(self):
        for mode, wtt in (("STATIC", "10"), ("BIO_E", "-50"),
                          ("RFNBO_E", "-50"), ("CERTIFIED", "12")):
            case = self.by_id("D-custom-" + mode.lower())
            candidate = case["request"]["candidates"][0]
            factor = case["snapshot"]["candidates"][candidate["candidateId"]]
            self.assertEqual(candidate["wtTMode"], mode)
            self.assertEqual(F(factor["wtt"]), F(wtt))
            evidence = candidate["sourceEvidence"]
            required = {"lcv", "cfCO2", "cfCH4", "cfN2O", "cslip",
                        "methaneSlipApplicable", "rwd", "eligibleBiomassFraction"}
            required |= ({"E", "eu"} if mode == "RFNBO_E" else {"E"} if mode == "BIO_E" else {"wtT"})
            self.assertEqual(set(evidence), required)
            for field, entry in evidence.items():
                self.assertEqual(set(entry), {"sourceId", "sourceType", "unit", "verificationStatus"})
                self.assertTrue(entry["sourceId"].startswith("SYNTHETIC:"))
                self.assertIn(field, entry["sourceId"])
                self.assertEqual(entry["sourceType"], "SA")
                self.assertEqual(entry["verificationStatus"], "ESTIMATED")
            self.assertEqual(factor["factor_status"], "ESTIMATED")
            self.assertEqual(set(factor["source_ids"]), {e["sourceId"] for e in evidence.values()})

    def test_independently_declared_errors_and_http_scope(self):
        errors = {
            "D-negative-co2": "INVALID_EMISSION_FACTOR",
            "D-negative-ch4": "INVALID_EMISSION_FACTOR",
            "D-negative-n2o": "INVALID_EMISSION_FACTOR",
            "D-missing-evidence": "MISSING_REQUIRED_FACTOR",
            "D-wrong-unit": "MISSING_REQUIRED_FACTOR",
            "D-nonmethane-slip": "INVALID_CSLIP",
            "D-rwd2-2024": "MISSING_REQUIRED_FACTOR",
            "D-e283": "RFNBO_E_EXCEEDS_LIMIT",
            "D-unknown-path": "MISSING_REQUIRED_FACTOR",
            "B-b100-forbidden": "INVALID_BLEND_RATIO",
        }
        for case_id, code in errors.items():
            case = self.by_id(case_id)
            self.assertEqual(case["expected_http_status"], 200)
            self.assertEqual(len(case["expected_issues"]), 1)
            issue = case["expected_issues"][0]
            self.assertEqual(issue["code"], code)
            self.assertEqual(issue["scope"], "CANDIDATE")
            self.assertIsInstance(issue["candidate_id"], str)
            self.assertGreaterEqual(len(case["snapshot"]["candidates"]), 1)
        invalid = self.by_id("D-confirmation-false")
        self.assertIs(invalid["request"]["adjacentValidPortOfCallConfirmed"], False)
        self.assertEqual(invalid["expected_http_status"], 422)
        self.assertEqual(invalid["expected_issues"], [{
            "code": "PORT_OF_CALL_CONFIRMATION_REQUIRED", "scope": "CASE", "candidate_id": None,
        }])
        for case in self.cases():
            for issue in case["expected_issues"]:
                self.assertEqual(set(issue), {"code", "scope", "candidate_id"})
                self.assertIn(issue["scope"], {"CASE", "CANDIDATE"})

    def test_missing_prices_remain_computable_warning_cases(self):
        for case_id in ("A-missing-fuel-price", "A-missing-eua-price", "D-missing-price"):
            case = self.by_id(case_id)
            self.assertEqual(case["expected_http_status"], 200)
            self.assertEqual(case["expected_issues"][0]["code"], "PRICE_REQUIRED_FOR_COMPARISON")
        case = self.by_id("B-missing-price-budget")
        self.assertEqual({i["code"] for i in case["expected_issues"]}, {
            "PRICE_REQUIRED_FOR_COMPARISON", "BUDGET_UNAVAILABLE_WITHOUT_PRICES",
        })
        self.assertIn("hvo", case["snapshot"]["candidates"])

    def test_smoke_covers_exactly_36_builtin_requested_paths_without_ops(self):
        expected = {
            "HFO", "LFO", "MDO", "MGO", "METHANOL_NG", "H2_NG_FC", "H2_NG_ICE",
            "LPG_PROPANE", "LPG_BUTANE", "NH3_NG_FC", "NH3_NG_ICE",
            "BIOETHANOL", "BIODIESEL", "HVO", "BIOMETHANOL", "BIOH2_FC", "BIOH2_ICE",
            "UCO_FAME", "E_DIESEL", "E_METHANOL", "E_H2_FC", "E_H2_ICE", "E_NH3_FC", "E_NH3_ICE",
            "LNG_OTTO_MEDIUM_SPEED", "LNG_OTTO_SLOW_SPEED", "LNG_DIESEL_SLOW_SPEED", "LNG_LBSI",
            "BIOLNG_OTTO_MS", "BIOLNG_OTTO_SS", "BIOLNG_DIESEL_SS", "BIOLNG_LBSI",
            "E_LNG_OTTO_MEDIUM_SPEED", "E_LNG_OTTO_SLOW_SPEED", "E_LNG_DIESEL_SLOW_SPEED", "E_LNG_LBSI",
        }
        smoke = [case for case in self.cases() if "builtin_smoke" in case["coverage"]]
        requested = [c["pathId"] for case in smoke for c in case["request"]["candidates"]]
        self.assertEqual(len(requested), 36)
        self.assertEqual(set(requested), expected)
        self.assertTrue(all(not case["expected_issues"] for case in smoke))
        factors = {c["pathId"]: case["snapshot"]["candidates"][c["candidateId"]]
                   for case in smoke for c in case["request"]["candidates"]}
        self.assertEqual(factors["BIOETHANOL"]["lcv"], "0.02685")
        self.assertEqual(factors["BIOETHANOL"]["wtt"], "20")
        self.assertEqual(factors["BIOH2_ICE"]["n2o"], "0.00002")
        self.assertEqual(factors["H2_NG_FC"]["n2o"], "0")
        self.assertIsNone(factors["H2_NG_FC"]["slip"])
        self.assertEqual(factors["LPG_PROPANE"]["factor_status"], "ESTIMATED")
        self.assertEqual(factors["E_DIESEL"]["path_id"], "MDO")
        self.assertEqual(factors["E_H2_FC"]["path_id"], "H2_NG_FC")

    def test_smoke_preserves_nonmethane_na_separately_from_rc_estimate_zero(self):
        # Factor spec table III C9 and rule 5.1; calculation spec 4.3.
        smoke = [case for case in self.cases() if "builtin_smoke" in case["coverage"]]
        factors = {candidate["pathId"]: case["snapshot"]["candidates"][candidate["candidateId"]]
                   for case in smoke for candidate in case["request"]["candidates"]}
        for path in ("BIOETHANOL", "BIODIESEL", "HVO", "BIOMETHANOL",
                     "BIOH2_FC", "BIOH2_ICE", "UCO_FAME"):
            with self.subTest(path=path):
                self.assertIsNone(factors[path]["slip"])
                self.assertIs(factors[path]["methane"], False)
        for path in ("LPG_PROPANE", "LPG_BUTANE", "NH3_NG_FC", "NH3_NG_ICE"):
            with self.subTest(path=path):
                self.assertEqual(factors[path]["slip"], "0")
                self.assertEqual(factors[path]["factor_status"], "ESTIMATED")
                self.assertIs(factors[path]["methane"], False)
        for short, full, slip in (
            ("OTTO_MS", "OTTO_MEDIUM_SPEED", "3.1"),
            ("OTTO_SS", "OTTO_SLOW_SPEED", "1.7"),
            ("DIESEL_SS", "DIESEL_SLOW_SPEED", "0.2"), ("LBSI", "LBSI", "2.6"),
        ):
            for path in ("LNG_" + full, "BIOLNG_" + short, "E_LNG_" + full):
                self.assertEqual(factors[path]["slip"], slip)
                self.assertIs(factors[path]["methane"], True)

    def test_uco_default_smoke_factor_is_estimated(self):
        smoke = next(case for case in self.cases() if case["id"] == "D-smoke-bio-liquid")
        uco = next(candidate for candidate in smoke["request"]["candidates"]
                   if candidate["pathId"] == "UCO_FAME")
        factor = smoke["snapshot"]["candidates"][uco["candidateId"]]
        self.assertEqual(factor["factor_status"], "ESTIMATED")
        self.assertEqual(factor["mode"], "BIO_E")
        self.assertEqual(factor["e"], "14.9")

    def test_nonzero_compliance_improvement_value_case_keeps_same_factor_snapshot(self):
        reference = self.by_id("B-reference-value100")
        baseline = self.by_id("B-default")
        hvo = next(candidate for candidate in reference["request"]["candidates"]
                   if candidate["candidateId"] == "hvo")
        self.assertEqual(hvo["complianceImprovementValue"], "100")
        self.assertEqual(reference["snapshot"], baseline["snapshot"])
        self.assertIsNot(reference["snapshot"], baseline["snapshot"])
        self.assertEqual(reference["coverage"][-1], "reference_value")

    def test_builder_only_imports_stdlib_and_runs_without_repository_dependencies(self):
        self.cases()
        tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
        imports = {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imports |= {alias.name.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, ast.Import) for alias in node.names}
        self.assertTrue(imports <= {"__future__", "copy", "fractions"}, imports)
        script = (
            "import runpy, sys\n"
            "m = runpy.run_path(sys.argv[1])\n"
            "def guard(event, args):\n"
            "    if event in ('open', 'os.listdir', 'os.scandir', 'socket.connect'):\n"
            "        raise AssertionError('fixture generation attempted external I/O')\n"
            "sys.addaudithook(guard)\n"
            "assert 50 <= len(m['cases']()) <= 80\n"
            "assert not any(k.startswith('voyage_fuel') for k in sys.modules)\n"
        )
        result = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(BUILDER)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
