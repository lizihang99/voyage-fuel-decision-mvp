from decimal import Decimal
import unittest

from voyage_fuel.issues import issue_from_exception
from voyage_fuel.json_io import calculate_voyage_json, parse_decision_case


def minimum_payload():
    return {
        "reportYear": 2026,
        "departurePort": "CNSHG",
        "arrivalPort": "NLRTM",
        "adjacentValidPortOfCallConfirmed": True,
        "currency": "EUR",
        "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
        "euaPricePerTCO2e": "80",
        "candidates": [
            {
                "candidateId": "uco-quote-1",
                "pathId": "UCO_FAME",
                "pricePerTonne": "1000",
                "specifiedBlendRatios": ["0.2"],
                "maxBlendRatio": "0.3",
                "candidateSupplyTonnes": "20",
            },
            {
                "candidateId": "lng-quote-1",
                "pathId": "LNG_OTTO_MEDIUM_SPEED",
                "pricePerTonne": "850",
                "specifiedBlendRatios": ["0.1"],
            },
        ],
    }


def _custom_evidence(fields):
    return {
        field: [{
            "sourceId": f"SRC-{field}",
            "sourceType": "LAB_CERTIFICATE",
            "unit": unit,
            "verificationStatus": "VERIFIED",
        }]
        for field, unit in fields.items()
    }


def custom_factor_payload(*, mode="STATIC", qualification="NOT_DEMONSTRATED",
                          rwd="1", cslip="NA", cf_co2="3", e="20", eu="10"):
    fields = {
        "lcv": "MJ/gFuel",
        "wtT": "gCO2eq/MJ",
        "E": "gCO2eq/MJ",
        "eu": "gCO2eq/MJ",
        "cfCO2": "gGHG/gFuel",
        "cfCH4": "gGHG/gFuel",
        "cfN2O": "gGHG/gFuel",
        "cslip": "%",
        "methaneSlipApplicable": "boolean",
        "rwd": "ratio",
        "eligibleBiomassFraction": "fraction",
    }
    payload = {
        "pathId": "CUSTOM_PATH",
        "custom": True,
        "equipmentId": "CUSTOM_ENGINE",
        "lcv": "0.04",
        "wtTMode": mode,
        "wtT": "10",
        "E": e,
        "eu": eu,
        "cfCO2": cf_co2,
        "cfCH4": "0",
        "cfN2O": "0",
        "cslip": cslip,
        "methaneSlipApplicable": False,
        "rwd": rwd,
        "eligibleBiomassFraction": "0",
        "qualificationStatus": qualification,
        "sourceEvidence": _custom_evidence(fields),
    }
    return payload


def case_with_custom_candidate(candidate, *, report_year=2026):
    return {
        "reportYear": report_year,
        "departurePort": "CNSHG",
        "arrivalPort": "NLRTM",
        "adjacentValidPortOfCallConfirmed": True,
        "currency": "EUR",
        "baseline": {"pathId": "MDO", "massTonnes": "100", "pricePerTonne": "700"},
        "euaPricePerTCO2e": "80",
        "candidates": [{
            **candidate,
            "candidateId": "custom-1",
            "pricePerTonne": "1000",
        }, {
            "candidateId": "valid-1",
            "pathId": "MDO",
            "pricePerTonne": "700",
        }],
    }


class CaseJsonIoTests(unittest.TestCase):
    def test_component_qualification_status_is_normalized(self):
        payload = case_with_custom_candidate(custom_factor_payload(qualification="assumed_eligible"))

        parsed = parse_decision_case(payload)

        self.assertIsNotNone(parsed.request)
        assert parsed.request is not None
        self.assertEqual(parsed.request.candidates[0].component.qualification_status,
                         "ASSUMED_ELIGIBLE")

    def test_parses_case_candidates_with_decimal_values(self):
        parsed = parse_decision_case(minimum_payload())

        self.assertEqual(parsed.issues, ())
        self.assertIsNotNone(parsed.request)
        assert parsed.request is not None
        self.assertEqual(
            [candidate.candidate_id for candidate in parsed.request.candidates],
            ["uco-quote-1", "lng-quote-1"],
        )
        self.assertEqual(parsed.request.baseline_mass_tonnes, Decimal("100"))
        self.assertEqual(parsed.request.candidates[0].specified_blend_ratios, (Decimal("0.2"),))
        self.assertEqual(parsed.request.candidates[0].supply_tonnes, Decimal("20"))

    def test_missing_or_false_port_confirmation_is_case_blocking(self):
        for confirmation in (False, None):
            with self.subTest(confirmation=confirmation):
                payload = minimum_payload()
                if confirmation is None:
                    del payload["adjacentValidPortOfCallConfirmed"]
                else:
                    payload["adjacentValidPortOfCallConfirmed"] = confirmation
                parsed = parse_decision_case(payload)

                self.assertIsNone(parsed.request)
                self.assertEqual(parsed.issues[0].code, "PORT_OF_CALL_CONFIRMATION_REQUIRED")
                self.assertEqual(parsed.issues[0].scope, "CASE")
                self.assertTrue(parsed.issues[0].blocking)

    def test_duplicate_candidate_ids_are_case_blocking(self):
        payload = minimum_payload()
        payload["candidates"][1]["candidateId"] = "uco-quote-1"

        parsed = parse_decision_case(payload)

        self.assertIsNone(parsed.request)
        self.assertEqual(parsed.issues[0].code, "DUPLICATE_CANDIDATE_ID")
        self.assertEqual(parsed.issues[0].scope, "CASE")
        self.assertTrue(parsed.issues[0].blocking)

    def test_invalid_candidate_is_reported_without_discarding_valid_candidates(self):
        payload = minimum_payload()
        payload["candidates"][1]["specifiedBlendRatios"] = ["1.1"]

        parsed = parse_decision_case(payload)

        self.assertIsNotNone(parsed.request)
        assert parsed.request is not None
        self.assertEqual([candidate.candidate_id for candidate in parsed.request.candidates], ["uco-quote-1"])
        self.assertEqual(parsed.issues[0].code, "INVALID_BLEND_RATIO")
        self.assertEqual(parsed.issues[0].scope, "CANDIDATE")
        self.assertEqual(parsed.issues[0].candidate_id, "lng-quote-1")
        self.assertEqual(parsed.issues[0].field, "candidates[1].specifiedBlendRatios[0]")

    def test_candidate_constraint_and_component_failures_keep_exact_fields(self):
        payload = minimum_payload()
        payload["candidates"][1]["candidateSupplyTonnes"] = "-1"

        parsed = parse_decision_case(payload)

        self.assertEqual(parsed.issues[0].field, "candidates[1].candidateSupplyTonnes")

        payload = minimum_payload()
        payload["candidates"][1]["pathId"] = "UNKNOWN_PATH"
        parsed = parse_decision_case(payload)

        self.assertEqual(parsed.issues[0].field, "candidates[1].pathId")

    def test_case_failures_keep_exact_fields(self):
        cases = (
            ("reportYear", 2031, "reportYear"),
            ("currency", "", "currency"),
        )
        for key, value, expected_field in cases:
            with self.subTest(key=key):
                payload = minimum_payload()
                payload[key] = value

                parsed = parse_decision_case(payload)

                self.assertIsNone(parsed.request)
                self.assertEqual(parsed.issues[0].field, expected_field)

        payload = minimum_payload()
        payload["baseline"]["massTonnes"] = "0"
        parsed = parse_decision_case(payload)
        self.assertIsNone(parsed.request)
        self.assertEqual(parsed.issues[0].field, "baseline.massTonnes")

    def test_case_parser_rejects_string_boolean_without_truthiness_conversion(self):
        payload = minimum_payload()
        payload["adjacentValidPortOfCallConfirmed"] = "false"

        parsed = parse_decision_case(payload)

        self.assertIsNone(parsed.request)
        self.assertEqual(parsed.issues[0].code, "PORT_OF_CALL_CONFIRMATION_REQUIRED")

    def test_missing_candidate_id_is_candidate_scoped_not_duplicate(self):
        payload = minimum_payload()
        del payload["candidates"][1]["candidateId"]

        parsed = parse_decision_case(payload)

        self.assertIsNotNone(parsed.request)
        assert parsed.request is not None
        self.assertEqual([candidate.candidate_id for candidate in parsed.request.candidates], ["uco-quote-1"])
        self.assertEqual(parsed.issues[0].code, "INVALID_CANDIDATE_ID")
        self.assertEqual(parsed.issues[0].scope, "CANDIDATE")

    def test_issue_mapper_keeps_known_contract_code(self):
        issue = issue_from_exception(
            ValueError("INVALID_BLEND_RATIO: ratio must be between zero and one"),
            scope="CANDIDATE",
            field="specifiedBlendRatios[0]",
            candidate_id="uco-quote-1",
        )

        self.assertEqual(issue.code, "INVALID_BLEND_RATIO")
        self.assertTrue(issue.blocking)
        self.assertEqual(issue.candidate_id, "uco-quote-1")

    def test_legacy_single_candidate_entry_point_remains_available(self):
        payload = {
            "reportYear": 2026,
            "departurePort": "CNSHG",
            "arrivalPort": "NLRTM",
            "baseline": {"pathId": "MDO", "massTonnes": "1", "pricePerTonne": "700"},
            "candidate": {"pathId": "UCO_FAME", "pricePerTonne": "1000"},
        }
        self.assertIsInstance(calculate_voyage_json(payload), str)

    def test_custom_rfnbo_without_qualification_is_blocked(self):
        payload = case_with_custom_candidate(
            custom_factor_payload(mode="RFNBO_E", qualification="NOT_DEMONSTRATED", rwd="2")
        )

        parsed = parse_decision_case(payload)

        self.assertIsNotNone(parsed.request)
        self.assertEqual(parsed.issues[0].code, "MISSING_REQUIRED_FACTOR")
        self.assertEqual(parsed.issues[0].scope, "CANDIDATE")

    def test_custom_rfnbo_rwd_two_is_blocked_before_2025(self):
        payload = case_with_custom_candidate(
            custom_factor_payload(mode="RFNBO_E", qualification="ASSUMED_ELIGIBLE", rwd="2"),
            report_year=2024,
        )

        parsed = parse_decision_case(payload)

        self.assertIsNotNone(parsed.request)
        self.assertEqual(parsed.issues[0].code, "MISSING_REQUIRED_FACTOR")

    def test_custom_rfnbo_rwd_two_is_allowed_from_2025(self):
        payload = case_with_custom_candidate(
            custom_factor_payload(mode="RFNBO_E", qualification="ASSUMED_ELIGIBLE", rwd="2"),
            report_year=2025,
        )

        parsed = parse_decision_case(payload)

        self.assertEqual(parsed.issues, ())
        assert parsed.request is not None
        factor = parsed.request.candidates[0].component.factor
        self.assertEqual(factor.rwd, Decimal("2"))
        self.assertEqual(factor.qualification_status, "ASSUMED_ELIGIBLE")

    def test_invalid_cslip_preserves_structured_error_code(self):
        payload = case_with_custom_candidate(custom_factor_payload(cslip="101"))

        parsed = parse_decision_case(payload)

        self.assertEqual(parsed.issues[0].code, "INVALID_CSLIP")

    def test_rfnbo_e_exceeds_limit_preserves_structured_error_code(self):
        payload = case_with_custom_candidate(
            custom_factor_payload(mode="RFNBO_E", qualification="ASSUMED_ELIGIBLE", e="28.3")
        )

        parsed = parse_decision_case(payload)

        self.assertEqual(parsed.issues[0].code, "RFNBO_E_EXCEEDS_LIMIT")

    def test_bio_e_missing_cf_co2_returns_issue_instead_of_assertion_error(self):
        payload = case_with_custom_candidate(
            custom_factor_payload(mode="BIO_E", qualification="ASSUMED_ELIGIBLE", cf_co2="NA")
        )

        parsed = parse_decision_case(payload)

        self.assertEqual(parsed.issues[0].code, "MISSING_REQUIRED_FACTOR")

    def test_empty_candidates_creates_b0_only_request(self):
        payload = minimum_payload()
        payload["candidates"] = []

        parsed = parse_decision_case(payload)

        self.assertIsNotNone(parsed.request)
        self.assertEqual(parsed.request.candidates, ())
        self.assertEqual(parsed.issues, ())


if __name__ == "__main__":
    unittest.main()
