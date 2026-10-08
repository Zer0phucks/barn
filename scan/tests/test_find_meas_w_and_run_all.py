import unittest
from pathlib import Path
import find_meas_w_addresses as scanner
import run_all


class TestFindMeasWAndRunAll(unittest.TestCase):
    def test_get_input_csv_path_by_city(self):
        oakland_path = scanner.get_input_csv_path(city="OAKLAND")
        self.assertTrue(oakland_path.exists())
        self.assertEqual(oakland_path.name, "oakland.csv")

        berkeley_path = scanner.get_input_csv_path(city="BERKELEY")
        self.assertTrue(berkeley_path.exists())
        self.assertEqual(berkeley_path.name, "berkeley.csv")

    def test_get_cities_from_csv(self):
        cities = run_all.get_cities_from_csv()
        self.assertIn("OAKLAND", cities)
        self.assertIn("BERKELEY", cities)
        self.assertNotIn("CITY", cities)

    def test_check_bill_vpt_markers(self):
        # Oakland Measure W
        oakland_html = "<tr><td>MEAS-W OAKLAND VPT</td><td>$6,000.00</td></tr>"
        has_vpt, marker = scanner.check_bill_vpt(oakland_html, city="OAKLAND")
        self.assertTrue(has_vpt)
        self.assertEqual(marker, "MEAS-W OAKLAND VPT")

        # Berkeley Measure M marker
        berkeley_html = "<tr><td>MEAS-M BERKELEY</td><td>$6,000.00</td></tr>"
        has_vpt, marker = scanner.check_bill_vpt(berkeley_html, city="BERKELEY")
        self.assertTrue(has_vpt)
        self.assertEqual(marker, "MEAS-M BERKELEY")

        # Berkeley fixed charges $6,000.00
        berkeley_fc = '<table class="fixed-charges"><tr><td>BERKELEY VACANT TAX</td><td>$6,000.00</td></tr></table>'
        has_vpt, marker = scanner.check_bill_vpt(berkeley_fc, city="BERKELEY")
        self.assertTrue(has_vpt)

        # Non-VPT bill with $756,000.00 valuation should NOT match
        non_vpt_html = '<tr><td>IMPROVEMENTS</td><td> $756,000.00 </td></tr>'
        has_vpt, marker = scanner.check_bill_vpt(non_vpt_html, city="BERKELEY")
        self.assertFalse(has_vpt)
        self.assertIsNone(marker)

    def test_extract_bill_fields_from_html(self):
        html = '''
        Parcel Number:</strong> <span class="no-link">054 174201000</span>
        Location of Property:</strong> 1234 SHATTUCK AVE
        Tax Year: 2024-2025
        PAID DEC 10, 2024
        <table class="fixed-charges">
            <tr><td>MEAS-M BERKELEY</td><td>$3,000.00</td></tr>
        </table>
        '''
        fields = scanner.extract_bill_fields_from_html(html, city="BERKELEY")
        self.assertEqual(fields["parcel_number"], "054 174201000")
        self.assertEqual(fields["location_of_property"], "1234 SHATTUCK AVE")
        self.assertEqual(fields["tax_year"], "2024-2025")
        self.assertEqual(fields["last_payment"], "DEC 10, 2024")
        self.assertEqual(fields["has_vpt"], "1")
        self.assertEqual(fields["vpt_marker"], "MEAS-M BERKELEY")


    def test_zip_from_row_json(self):
        self.assertEqual(scanner._zip_from_row_json('{"ZIPCODE": "94606"}'), "94606")
        self.assertEqual(scanner._zip_from_row_json('{"SitusZip": "94607"}'), "94607")
        self.assertIsNone(scanner._zip_from_row_json('{"CITY": "Oakland"}'))
        self.assertIsNone(scanner._zip_from_row_json(""))
        self.assertIsNone(scanner._zip_from_row_json(None))
        self.assertIsNone(scanner._zip_from_row_json("not json"))

    def test_safe_url(self):
        url_with_spaces = "https://propertytax.alamedacountyca.gov/account-summary?apn=036 244200400"
        safe = scanner._safe_url(url_with_spaces)
        self.assertNotIn(" ", safe)
        self.assertIn("036%20244200400", safe)

    def test_stop_scan(self):
        scanner._stop_requested = False
        run_all.scan_state["is_running"] = True
        run_all.scan_state["continuous_mode"] = True

        stopped = run_all.stop_scan()
        self.assertTrue(stopped)
        self.assertFalse(run_all.scan_state["continuous_mode"])
        self.assertTrue(scanner.is_stop_requested())

        # Cleanup
        scanner._stop_requested = False
        run_all.scan_state["is_running"] = False

    def test_is_within_days_and_format_added_at(self):
        from datetime import datetime, timezone, timedelta
        from webgui.app import _is_within_days, _format_added_at

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).isoformat()
        old = (now - timedelta(days=35)).isoformat()

        self.assertTrue(_is_within_days(recent, 30))
        self.assertFalse(_is_within_days(old, 30))
        self.assertFalse(_is_within_days(None))
        self.assertFalse(_is_within_days(""))

        formatted = _format_added_at("2026-03-27T18:08:59.491086+00:00")
        self.assertEqual(formatted, "2026-03-27")
        thirty_one_ago = (now - timedelta(days=31)).strftime("%Y-%m-%d")
        self.assertEqual(_format_added_at(None), thirty_one_ago)


if __name__ == "__main__":
    unittest.main()
