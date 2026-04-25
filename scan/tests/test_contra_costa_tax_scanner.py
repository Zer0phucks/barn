from __future__ import annotations

import unittest

import contra_costa_tax_scanner


PAID_RESPONSE = {
    "assessment": {"assessmentYear": "2025-2026"},
    "details": {
        "address": "1636 4TH ST, RICHMOND CA",
        "apn": "409-171-017-0",
        "budContainsDelinquentTaxes": False,
        "containsPriorYear": False,
        "delinquent": False,
        "owesPriorYear": False,
    },
    "installments": [
        {
            "billNumber": "2025-312868",
            "dateDue": "12/10/2025",
            "installmentNumber": 1,
            "isDelinquent": False,
            "paidDate": "12/08/2025",
            "priorYear": False,
            "status": "PAID",
            "type": "SECURED",
        },
        {
            "billNumber": "2025-312868",
            "dateDue": "04/10/2026",
            "installmentNumber": 2,
            "isDelinquent": False,
            "paidDate": "04/08/2026",
            "priorYear": False,
            "status": "PAID",
            "type": "SECURED",
        },
    ],
}

DELINQUENT_RESPONSE = {
    "assessment": {"assessmentYear": "2025-2026"},
    "details": {
        "address": "3668 SILVER OAK PL, DANVILLE CA",
        "apn": "203-750-005-1",
        "budContainsDelinquentTaxes": False,
        "containsPriorYear": True,
        "delinquent": False,
        "owesPriorYear": False,
    },
    "installments": [
        {
            "billNumber": "2425-215920",
            "dateDue": "04/10/2025",
            "installmentNumber": 2,
            "isDelinquent": True,
            "paidDate": None,
            "priorYear": True,
            "priorYearDelinquentPenalty": "326.31",
            "priorYearTaxYear": "2425",
            "status": "TRANSFER",
            "type": "SECURED",
        }
    ],
}

HISTORICAL_DELINQUENT_RESPONSE = {
    "assessment": {"assessmentYear": "2025-2026"},
    "details": {
        "address": "1636 4TH ST, RICHMOND CA",
        "apn": "409-171-017-0",
        "budContainsDelinquentTaxes": False,
        "containsPriorYear": False,
        "delinquent": False,
        "owesPriorYear": False,
    },
    "installments": [
        {
            "billNumber": "1516-299675",
            "dateDue": "04/10/2016",
            "installmentNumber": 2,
            "isDelinquent": True,
            "paidDate": None,
            "priorYear": True,
            "priorYearDelinquentPenalty": "168.83",
            "priorYearTaxYear": "1516",
            "status": "TRANSFER",
            "type": "SECURED",
        },
        {
            "billNumber": "2025-312868",
            "dateDue": "04/10/2026",
            "installmentNumber": 2,
            "isDelinquent": False,
            "paidDate": "04/08/2026",
            "priorYear": False,
            "status": "PAID",
            "type": "SECURED",
        },
    ],
}


class ContraCostaTaxScannerTests(unittest.TestCase):
    def test_normalizes_contra_costa_apn(self) -> None:
        self.assertEqual("4091710170", contra_costa_tax_scanner.normalize_contra_costa_apn("409-171-17-0"))
        self.assertEqual("0852150036", contra_costa_tax_scanner.normalize_contra_costa_apn("85-215-3-6"))

    def test_parses_paid_response_as_not_delinquent(self) -> None:
        result = contra_costa_tax_scanner.parse_api_response("409-171-17-0", PAID_RESPONSE)

        self.assertTrue(result.found)
        self.assertFalse(result.is_delinquent)
        self.assertEqual("2025-2026", result.tax_year)
        self.assertEqual("04/08/2026", result.last_payment)
        self.assertEqual("https://taxcolp.cccttc.us/lookup/?apn=4091710170&verify=true", result.bill_url)

    def test_parses_delinquent_installment(self) -> None:
        result = contra_costa_tax_scanner.parse_api_response("203-750-5-1", DELINQUENT_RESPONSE)

        self.assertTrue(result.found)
        self.assertTrue(result.is_delinquent)

    def test_ignores_historical_delinquency_when_no_prior_year_balance_owed(self) -> None:
        result = contra_costa_tax_scanner.parse_api_response("409-171-17-0", HISTORICAL_DELINQUENT_RESPONSE)

        self.assertTrue(result.found)
        self.assertFalse(result.is_delinquent)


if __name__ == "__main__":
    unittest.main()
