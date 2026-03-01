"""Tests for storage helper behavior."""

from __future__ import annotations

import unittest
from datetime import timezone

HA_AVAILABLE = True
try:
    from custom_components.family_treasury.storage import FamilyTreasuryStorage
except ModuleNotFoundError:
    HA_AVAILABLE = False


@unittest.skipUnless(HA_AVAILABLE, "homeassistant is not installed in this environment")
class TestStorageHelpers(unittest.TestCase):
    """Test static helper behavior in storage module."""

    def test_parse_row_datetime_returns_none_for_invalid_types(self) -> None:
        self.assertIsNone(FamilyTreasuryStorage._parse_row_datetime({}))
        self.assertIsNone(FamilyTreasuryStorage._parse_row_datetime({"occurred_at": 123}))

    def test_parse_row_datetime_returns_none_for_invalid_string(self) -> None:
        self.assertIsNone(
            FamilyTreasuryStorage._parse_row_datetime({"occurred_at": "not-a-date"})
        )

    def test_parse_row_datetime_converts_naive_to_utc(self) -> None:
        parsed = FamilyTreasuryStorage._parse_row_datetime(
            {"occurred_at": "2026-02-01T10:00:00"}
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_parse_row_datetime_normalizes_aware_to_utc(self) -> None:
        parsed = FamilyTreasuryStorage._parse_row_datetime(
            {"occurred_at": "2026-02-01T10:00:00+02:00"}
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.hour, 8)


if __name__ == "__main__":
    unittest.main()
