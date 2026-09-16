"""Real API/browser/export checks against independently hand-derived literals."""
import csv
import io
import unittest
from decimal import Decimal

from pypdf import PdfReader

from new_energy_reference import custom_payload, hand_case
from tests.e2e.test_mvp_flow import BrowserAppMixin


# Seven displayed fields: quantity, ratio %, extra fuel cost, ETS savings,
# net cost change, GHGI change, compliance-balance change. Hand calculations
# are documented in docs/validation/new-energy-cross-validation.md.
ZERO = ("0.000", "0.0000%", "0.00", "0.00", "0.00", "0.0000", "0.000000")
TARGET = ("26.658", "26.6580%", "10663.20", "2132.64", "8530.56", "-10.6632", "21.326400")
MAXIMUM = ("60.000", "60.0000%", "24000.00", "4800.00", "19200.00", "-24.0000", "48.000000")
CHEAP = ("60.000", "60.0000%", "-6000.00", "4800.00", "-10800.00", "-24.0000", "48.000000")
LIMITED = ("10.000", "10.0000%", "4000.00", "800.00", "3200.00", "-4.0000", "8.000000")
NO_CARBON_TARGET = ("26.658", "26.6580%", "10663.20", "0.00", "10663.20", "-10.6632", "21.326400")
NO_CARBON_MAX = ("60.000", "60.0000%", "24000.00", "0.00", "24000.00", "-24.0000", "48.000000")
SURFACE_CASE_COUNT = 6


class NewEnergySurfaceTests(BrowserAppMixin, unittest.TestCase):
    def fill_hand_case(self, page, price, supply, eua="80", budget=None):
        self.choose_port(page, "#departure-port-search", "CNSHG")
        self.choose_port(page, "#arrival-port-search", "NLRTM")
        page.locator("#baseline-mode").select_option("custom")
        base = page.locator("#baseline-custom-editor")
        for field, value in (
            ("baselineCustomFuelName", "Cross Baseline"), ("baselineLcv", ".04"),
            ("baselineWtT", "25"), ("baselineCfCO2", "3"), ("baselineSourceId", "SYNTHETIC-CROSS-TEST"),
        ):
            base.locator(f'[data-field="{field}"]').fill(value)
        base.locator('[data-field="baselineCfCH4ZeroEstimate"]').check()
        base.locator('[data-field="baselineCfN2OZeroEstimate"]').check()
        page.locator("#baseline-mass").fill("100")
        page.locator("#baseline-price").fill("600")
        page.locator("#eua-price").fill(eua)
        page.locator("#case-currency").select_option("EUR")
        row = page.locator(".candidate-row").first
        row.locator('[data-field="candidateMode"]').select_option("custom")
        for field, value in (
            ("candidateId", "clean"), ("customFuelName", "Cross Clean"), ("lcv", ".04"),
            ("wtT", "35"), ("cfCO2", "1"), ("sourceId", "SYNTHETIC-CROSS-TEST"),
            ("pricePerTonne", price), ("maxBlendRatio", ".6"), ("specifiedBlendRatios", ""),
            ("candidateSupplyTonnes", supply or ""),
            ("incrementalBudget", budget or ""),
        ):
            row.locator(f'[data-field="{field}"]').fill(value)
        row.locator('[data-field="cfCH4ZeroEstimate"]').check()
        row.locator('[data-field="cfN2OZeroEstimate"]').check()

    def test_page_api_csv_and_pdf_match_hand_calculated_decisions(self):
        configurations = (
            ("1000", None, "80", None, (ZERO, TARGET, MAXIMUM)),
            ("500", None, "80", None, (CHEAP, CHEAP, CHEAP)),
            ("1000", "10", "80", None, (ZERO, None, LIMITED)),
            ("1000", "0", "80", None, (ZERO, None, ZERO)),
            ("1000", None, "80", "3200", (ZERO, None, LIMITED)),
            ("1000", None, "0", None, (ZERO, NO_CARBON_TARGET, NO_CARBON_MAX)),
        )
        self.assertEqual(len(configurations), SURFACE_CASE_COUNT)
        for width in (1440, 390):
            for price, supply, eua, budget, expected in configurations:
                with self.subTest(width=width, price=price, supply=supply, eua=eua, budget=budget):
                    context, page = self.new_page(width, 900)
                    try:
                        self.fill_hand_case(page, price, supply, eua, budget)
                        raw = self.calculate(page)
                        cards = page.locator("#new-energy-decision-summary .decision-item")
                        self.assertEqual(cards.count(), 3)
                        for index, wanted in enumerate(expected):
                            if wanted is None:
                                self.assertIn("TARGET_UNREACHABLE_UNDER_CONSTRAINTS", cards.nth(index).inner_text())
                            else:
                                shown = cards.nth(index).locator("dd").all_text_contents()
                                self.assertEqual(tuple(value.replace(",", "").strip() for value in shown), wanted)

                        case = hand_case(price, supply)
                        case.update(eua=eua, budget=budget)
                        payload = custom_payload([case])
                        response = page.request.post(self.base_url + "/api/calculate", data=payload)
                        self.assertEqual(response.status, 200)
                        api = response.json()
                        for field, wanted in zip(
                            ("cost_min_scenario_id", "target_min_cost_scenario_id", "max_improvement_scenario_id"),
                            expected,
                        ):
                            self.assertEqual(api["decision_summary"][field], raw["decision_summary"][field])
                            selected = api["decision_summary"][field]
                            if wanted is None:
                                self.assertIsNone(selected)
                                continue
                            ratio = Decimal(wanted[1][:-1]) / 100
                            expected_id = "B0" if ratio == 0 else "clean@" + format(ratio.normalize(), "f")
                            self.assertEqual(selected, expected_id)
                            scenario = next(row["result"] for row in api["scenarios"] if row["scenario_id"] == selected)
                            self.assertEqual(Decimal(scenario["candidate_mass_tonnes"]), Decimal(wanted[0]))
                            self.assertEqual(Decimal(scenario["ratio"]), ratio)
                            self.assertEqual(Decimal(scenario["fuel_cost"]), Decimal("60000") + Decimal(wanted[2]))
                            baseline_ets = Decimal("0") if eua == "0" else Decimal("12000")
                            self.assertEqual(Decimal(scenario["eu_ets"]["eua_cost"]), baseline_ets - Decimal(wanted[3]))
                            self.assertEqual(Decimal(scenario["model_cost"]), Decimal("60000") + baseline_ets + Decimal(wanted[4]))
                            self.assertEqual(Decimal(scenario["fuel_eu"]["ghgi_actual_g_per_mj"]), Decimal("100") + Decimal(wanted[5]))
                            self.assertEqual(Decimal(scenario["fuel_eu"]["compliance_balance_t"]), Decimal("-21.3264") + Decimal(wanted[6]))
                            deltas = api["decision_summary"]["scenario_deltas"][selected]
                            for metric, literal in zip(
                                ("fuel_cost", "eua_cost", "model_cost", "fueleu_ghgi_actual_g_per_mj", "fueleu_compliance_balance_t"),
                                wanted[2:],
                            ):
                                value = Decimal(literal) * (-1 if metric == "eua_cost" else 1)
                                self.assertEqual(Decimal(deltas[metric]["delta"]), value)
                        csv_response = page.request.post(self.base_url + "/api/export/csv", data=payload)
                        self.assertEqual(csv_response.status, 200)
                        records = list(csv.DictReader(io.StringIO(csv_response.text())))
                        roles = ("CURRENT_MODEL_COST_MIN", "TARGET_MIN_COST:clean", "MAX_COMPLIANCE_IMPROVEMENT:clean")
                        for role, wanted in zip(roles, expected):
                            rows = [r for r in records if r["record_type"] == "decision_summary" and r["decision_type"] == role]
                            if wanted is None:
                                self.assertEqual(rows, [])
                                continue
                            self.assertEqual(len(rows), 6)
                            self.assertEqual(Decimal(rows[0]["recommended_quantity_tonnes"]), Decimal(wanted[0]))
                            self.assertEqual(Decimal(rows[0]["recommended_blend_ratio"]) * 100, Decimal(wanted[1][:-1]))
                            for metric, value in zip(
                                ("fuel_cost_delta", "eua_cost_savings", "model_cost_delta", "fueleu_ghgi_delta", "fueleu_balance_delta"),
                                wanted[2:],
                            ):
                                record = next(r for r in rows if r["metric_name"] == metric)
                                self.assertEqual(Decimal(record["delta"]), Decimal(value))

                        pdf_response = page.request.post(self.base_url + "/api/export/pdf", data=payload)
                        self.assertEqual(pdf_response.status, 200)
                        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf_response.body())).pages)
                        section = text.split("New energy decision summary", 1)[1].split(
                            "Scenario comparison (fuel mass and energy)", 1
                        )[0]
                        compact = "".join(section.split())
                        for role, wanted in zip(roles, expected):
                            if wanted is None:
                                self.assertNotIn(role, compact)
                            else:
                                candidate = "B0" if wanted == ZERO else "clean"
                                numbers = "".join(v.replace("%", "") for v in wanted)
                                self.assertIn(role + candidate + numbers, compact)
                    finally:
                        context.close()


if __name__ == "__main__":
    unittest.main()
