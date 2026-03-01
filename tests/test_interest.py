"""Tests for Family Treasury interest scheduling and accrual."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

HA_AVAILABLE = True
try:
    from custom_components.family_treasury.const import (
        FREQUENCY_DAILY,
        FREQUENCY_MONTHLY,
        FREQUENCY_WEEKLY,
    )
    from custom_components.family_treasury.interest import (
        accrue_interest_micro_minor,
        advance_boundary,
        ensure_aware_utc,
        iter_due_windows,
        month_partition_key,
        next_boundary,
        payoutable_minor_from_pending_micro,
        period_fraction_of_year,
    )
except ModuleNotFoundError:
    HA_AVAILABLE = False


@unittest.skipUnless(HA_AVAILABLE, "homeassistant is not installed in this environment")
class TestInterest(unittest.TestCase):
    """Interest helper tests."""

    def test_next_boundary_daily(self) -> None:
        tz = ZoneInfo("America/New_York")
        current = datetime(2026, 2, 3, 10, 0, tzinfo=tz)
        self.assertEqual(
            next_boundary(current, FREQUENCY_DAILY),
            datetime(2026, 2, 4, 0, 0, tzinfo=tz),
        )

    def test_next_boundary_weekly_is_monday_midnight(self) -> None:
        tz = ZoneInfo("America/New_York")
        current = datetime(2026, 2, 3, 10, 0, tzinfo=tz)
        self.assertEqual(
            next_boundary(current, FREQUENCY_WEEKLY),
            datetime(2026, 2, 9, 0, 0, tzinfo=tz),
        )

    def test_next_boundary_monthly_is_first_of_next_month(self) -> None:
        tz = ZoneInfo("America/New_York")
        current = datetime(2026, 2, 14, 10, 0, tzinfo=tz)
        self.assertEqual(
            next_boundary(current, FREQUENCY_MONTHLY),
            datetime(2026, 3, 1, 0, 0, tzinfo=tz),
        )

    def test_next_boundary_rejects_unknown_frequency(self) -> None:
        tz = ZoneInfo("America/New_York")
        with self.assertRaises(ValueError):
            next_boundary(datetime(2026, 2, 14, 10, 0, tzinfo=tz), "hourly")

    def test_advance_boundary_rejects_unknown_frequency(self) -> None:
        tz = ZoneInfo("America/New_York")
        with self.assertRaises(ValueError):
            advance_boundary(datetime(2026, 2, 14, 10, 0, tzinfo=tz), "hourly")

    def test_daily_interest_accrual_micro_minor(self) -> None:
        tz = ZoneInfo("America/New_York")
        period_start = datetime(2026, 2, 1, 0, 0, tzinfo=tz)
        period_end = datetime(2026, 2, 2, 0, 0, tzinfo=tz)

        accrued = accrue_interest_micro_minor(
            balance_minor=10_000,
            apr_bps=500,
            period_start_local=period_start,
            period_end_local=period_end,
        )

        self.assertEqual(accrued, 1_369_863)

    def test_payoutable_minor_uses_floor(self) -> None:
        self.assertEqual(payoutable_minor_from_pending_micro(999_999), 0)
        self.assertEqual(payoutable_minor_from_pending_micro(1_000_000), 1)
        self.assertEqual(payoutable_minor_from_pending_micro(2_750_000), 2)

    def test_zero_balance_or_zero_apr_no_accrual(self) -> None:
        tz = ZoneInfo("UTC")
        period_start = datetime(2026, 2, 1, 0, 0, tzinfo=tz)
        period_end = datetime(2026, 2, 2, 0, 0, tzinfo=tz)

        self.assertEqual(
            accrue_interest_micro_minor(
                balance_minor=0,
                apr_bps=500,
                period_start_local=period_start,
                period_end_local=period_end,
            ),
            0,
        )
        self.assertEqual(
            accrue_interest_micro_minor(
                balance_minor=10_000,
                apr_bps=0,
                period_start_local=period_start,
                period_end_local=period_end,
            ),
            0,
        )

    def test_ensure_aware_utc_handles_naive_and_aware(self) -> None:
        naive = datetime(2026, 2, 1, 10, 0, 0)
        aware = datetime(2026, 2, 1, 10, 0, 0, tzinfo=ZoneInfo("America/New_York"))

        self.assertEqual(ensure_aware_utc(naive).tzinfo, UTC)
        self.assertEqual(ensure_aware_utc(aware).tzinfo, UTC)

    def test_month_partition_key_uses_utc_conversion(self) -> None:
        value = datetime(2026, 2, 1, 0, 30, tzinfo=ZoneInfo("Asia/Tokyo"))
        self.assertEqual(month_partition_key(value), "2026-01")

    def test_iter_due_windows_yields_expected_daily_windows(self) -> None:
        tz = ZoneInfo("America/New_York")
        last_event = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
        now = datetime(2026, 2, 3, 0, 0, tzinfo=UTC)

        windows = list(
            iter_due_windows(
                last_event_utc=last_event,
                now_utc=now,
                frequency=FREQUENCY_DAILY,
                tz=tz,
            )
        )

        self.assertEqual(len(windows), 1)
        self.assertLess(windows[0][0], windows[0][1])

    def test_iter_due_windows_returns_empty_when_not_due(self) -> None:
        tz = ZoneInfo("America/New_York")
        last_event = datetime(2026, 2, 1, 23, 0, tzinfo=UTC)
        now = datetime(2026, 2, 1, 23, 30, tzinfo=UTC)

        windows = list(
            iter_due_windows(
                last_event_utc=last_event,
                now_utc=now,
                frequency=FREQUENCY_DAILY,
                tz=tz,
            )
        )

        self.assertEqual(windows, [])

    def test_period_fraction_of_year_covers_day_and_subday(self) -> None:
        tz = ZoneInfo("UTC")
        full_day_fraction = period_fraction_of_year(
            datetime(2026, 2, 1, 0, 0, tzinfo=tz),
            datetime(2026, 2, 2, 0, 0, tzinfo=tz),
        )
        half_day_fraction = period_fraction_of_year(
            datetime(2026, 2, 1, 0, 0, tzinfo=tz),
            datetime(2026, 2, 1, 12, 0, tzinfo=tz),
        )

        self.assertEqual(full_day_fraction, Decimal(1) / Decimal(365))
        self.assertEqual(half_day_fraction, Decimal("0.5") / Decimal(365))


if __name__ == "__main__":
    unittest.main()
