from copy import deepcopy
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


class CaseJsonIoTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
