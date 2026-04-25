from __future__ import annotations

import unittest

import marin_tax_scanner


SEARCH_RESULTS_PAID = """
<html><body>
<h2>Tax Bills for Parcel # / Property ID 018-062-51</h2>
<p>Situs Address: 16 BELLAM BLVD, SAN RAFAEL, CA 94901</p>
<table>
  <thead><tr><th>Tax Year</th><th>Bill Number</th><th>Bill Type</th><th>Install 1</th><th>Install 2</th></tr></thead>
  <tbody>
    <tr><td>2025/26</td><td>25-1037045</td><td>Secured</td><td>Paid</td><td>Paid</td></tr>
    <tr><td>2024/25</td><td>24-1037384</td><td>Secured</td><td>Paid</td><td>Paid</td></tr>
  </tbody>
</table>
</body></html>
"""


SEARCH_RESULTS_DELINQUENT = """
<html><body>
<h2>Tax Bills for Parcel # / Property ID 018-062-51</h2>
<p>Situs Address: 16 BELLAM BLVD, SAN RAFAEL, CA 94901</p>
<table>
  <thead><tr><th>Tax Year</th><th>Bill Number</th><th>Bill Type</th><th>Install 1</th><th>Install 2</th></tr></thead>
  <tbody>
    <tr><td>2025/26</td><td>25-1037045</td><td>Secured</td><td>Paid</td><td>Delinquent</td></tr>
  </tbody>
</table>
</body></html>
"""


class MarinTaxScannerTests(unittest.TestCase):
    def test_normalizes_segmented_marin_apn(self) -> None:
        self.assertEqual("01806251", marin_tax_scanner.normalize_marin_property_id("18-62-51"))
        self.assertEqual("14341112", marin_tax_scanner.normalize_marin_property_id("143-411-12"))

    def test_parses_paid_search_results_as_not_delinquent(self) -> None:
        result = marin_tax_scanner.parse_search_results("18-62-51", SEARCH_RESULTS_PAID)

        self.assertTrue(result.found)
        self.assertFalse(result.is_delinquent)
        self.assertEqual("2025/26", result.tax_year)
        self.assertEqual("https://apps.marincounty.gov/TaxBillOnline/Bill?BillNumber=25-1037045", result.bill_url)
        self.assertEqual(2, len(result.bills))

    def test_parses_explicit_delinquent_installment(self) -> None:
        result = marin_tax_scanner.parse_search_results("18-62-51", SEARCH_RESULTS_DELINQUENT)

        self.assertTrue(result.found)
        self.assertTrue(result.is_delinquent)
        self.assertEqual("18-62-51", result.apn)


if __name__ == "__main__":
    unittest.main()
