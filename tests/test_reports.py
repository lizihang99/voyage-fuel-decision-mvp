import csv
import io
import unittest
from decimal import Decimal

from voyage_fuel.calculator import calculate_voyage
from voyage_fuel.factors import get_builtin_factor
from voyage_fuel.models import FuelComponent, VoyageInput
from voyage_fuel.reports import voyage_result_to_csv


class ReportTests(unittest.TestCase):
    def test_csv_preserves_raw_decimal_values_and_summary_records(self):
        result = calculate_voyage(VoyageInput(
            report_year=2026,
            departure_port="CNSHG",
            arrival_port="NLRTM",
            baseline_component=FuelComponent(get_builtin_factor("MGO"), Decimal("600")),
            baseline_mass_tonnes=Decimal("100"),
            candidate_component=FuelComponent(
                get_builtin_factor("UCO_FAME"), Decimal("1000"),
                eligible_biomass_fraction=Decimal("1"), qualification_status="ASSUMED_ELIGIBLE",
            ),
            eua_price_per_tco2e=Decimal("80"),
            specified_blend_ratios=(Decimal("0.20"),),
            max_blend_ratio=Decimal("0.30"),
            candidate_allows_pure_use=True,
            candidate_supply_tonnes=Decimal("10"),
            incremental_budget=Decimal("5000"),
            compliance_improvement_value=Decimal("268.31901315986921862"),
        ))
        text = voyage_result_to_csv(result)
        self.assertNotIn("E-", text)
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertTrue(any(row["record_type"] == "scenario" for row in rows))
        constraint = next(row for row in rows if row["record_type"] == "constraints")
        self.assertEqual(constraint["x_cap"], "0.098682690085509590940605500346660503813265541945921")
        economics = next(row for row in rows if row["record_type"] == "economics")
        self.assertEqual(economics["pc_break_even"], "630.76546135831381733021077283372365339578454332552")
        switch = next(row for row in rows if row["record_type"] == "switch_point")
        self.assertEqual(switch["from_ratio"], "0")


if __name__ == "__main__":
    unittest.main()
