import unittest

try:
    from .test_mvp_flow import BrowserAppMixin
except ImportError:  # Direct execution of this module remains supported.
    from test_mvp_flow import BrowserAppMixin


class DisplayPrecisionTests(BrowserAppMixin, unittest.TestCase):
    def test_precision_changes_visible_values_only(self):
        context, page = self.new_page()
        try:
            self.fill_case(page, include_rfnbo=False)
            raw = self.calculate(page)
            before = page.locator("#scenario-comparison-table").inner_text()
            page.locator("#precision-price").fill("0")
            page.locator("#precision-ratio").fill("0")
            page.wait_for_timeout(100)
            after = page.locator("#scenario-comparison-table").inner_text()
            self.assertNotEqual(before, after)
            self.assertEqual([row["scenario_id"] for row in raw["scenarios"][:3]], ["B0", "uco-quote-1@0.2", "uco-quote-1@0.3"])
            self.assertEqual(raw["baseline_scenario"]["physical_energy_mj"], "4270000.0000")
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
