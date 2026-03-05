"""Tests for Family Treasury money helpers."""

from __future__ import annotations

import unittest
from decimal import Decimal

HA_AVAILABLE = True
try:
    from custom_components.family_treasury.models import (
        apr_percent_to_bps,
        currency_minor_exponent,
        minor_to_major_decimal,
        parse_major_to_minor,
        pending_micro_to_major_decimal,
        warm_currency_formatters,
    )
except ModuleNotFoundError:
    HA_AVAILABLE = False


@unittest.skipUnless(HA_AVAILABLE, "homeassistant is not installed in this environment")
class TestModels(unittest.TestCase):
    """Money helper tests."""

    def test_currency_exponents(self) -> None:
        self.assertEqual(currency_minor_exponent("USD"), 2)
        self.assertEqual(currency_minor_exponent("ISK"), 0)

    def test_parse_major_to_minor_usd(self) -> None:
        self.assertEqual(parse_major_to_minor("12.34", "USD"), 1234)

    def test_parse_major_to_minor_isk_disallows_decimals(self) -> None:
        with self.assertRaises(ValueError):
            parse_major_to_minor("12.5", "ISK")

    def test_parse_major_to_minor_signed_adjustment(self) -> None:
        self.assertEqual(parse_major_to_minor("-1.25", "USD", signed=True), -125)

    def test_apr_percent_to_bps(self) -> None:
        self.assertEqual(apr_percent_to_bps("3.75"), 375)

    def test_minor_and_pending_conversions(self) -> None:
        self.assertEqual(minor_to_major_decimal(1234, "USD"), Decimal("12.34"))
        self.assertEqual(
            pending_micro_to_major_decimal(1_500_000, "USD"),
            Decimal("0.015"),
        )

    def test_warm_currency_formatters_is_noop_safe(self) -> None:
        warm_currency_formatters({("USD", "en_US"), ("ISK", "is_IS")})


if __name__ == "__main__":
    unittest.main()
