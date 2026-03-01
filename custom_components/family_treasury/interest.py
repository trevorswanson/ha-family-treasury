"""Interest scheduling and accrual helpers."""

from __future__ import annotations

import calendar
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterator

from .const import (
    FREQUENCY_DAILY,
    FREQUENCY_MONTHLY,
    FREQUENCY_WEEKLY,
    MICRO_MINOR_PER_MINOR,
)

UTC = timezone.utc


def ensure_aware_utc(value: datetime) -> datetime:
    """Normalize datetime to timezone-aware UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def month_partition_key(value: datetime) -> str:
    """Build YYYY-MM ledger partition key."""

    return ensure_aware_utc(value).strftime("%Y-%m")


def _month_start(local_value: datetime) -> datetime:
    return local_value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_start(local_value: datetime) -> datetime:
    return datetime.combine(local_value.date(), time.min, tzinfo=local_value.tzinfo)


def next_boundary(local_value: datetime, frequency: str) -> datetime:
    """Get the next anchored boundary strictly after local_value."""

    day_start = _day_start(local_value)
    if frequency == FREQUENCY_DAILY:
        return day_start + timedelta(days=1)

    if frequency == FREQUENCY_WEEKLY:
        week_start = day_start - timedelta(days=day_start.weekday())
        return week_start + timedelta(days=7)

    if frequency == FREQUENCY_MONTHLY:
        month_start = _month_start(local_value)
        if month_start.month == 12:
            return month_start.replace(year=month_start.year + 1, month=1)
        return month_start.replace(month=month_start.month + 1)

    raise ValueError(f"Unsupported frequency: {frequency}")


def advance_boundary(boundary: datetime, frequency: str) -> datetime:
    """Advance one frequency period from a boundary."""

    if frequency == FREQUENCY_DAILY:
        return boundary + timedelta(days=1)
    if frequency == FREQUENCY_WEEKLY:
        return boundary + timedelta(days=7)
    if frequency == FREQUENCY_MONTHLY:
        if boundary.month == 12:
            return boundary.replace(year=boundary.year + 1, month=1)
        return boundary.replace(month=boundary.month + 1)
    raise ValueError(f"Unsupported frequency: {frequency}")


def iter_due_windows(
    *,
    last_event_utc: datetime,
    now_utc: datetime,
    frequency: str,
    tz,
) -> Iterator[tuple[datetime, datetime]]:
    """Yield local [start, end] windows due between last_event and now."""

    normalized_last = ensure_aware_utc(last_event_utc).astimezone(tz)
    normalized_now = ensure_aware_utc(now_utc).astimezone(tz)

    boundary = next_boundary(normalized_last, frequency)
    start = normalized_last

    while boundary <= normalized_now:
        yield start, boundary
        start = boundary
        boundary = advance_boundary(boundary, frequency)


def period_fraction_of_year(period_start_local: datetime, period_end_local: datetime) -> Decimal:
    """Compute year fraction for an elapsed local period."""

    day_delta = (period_end_local.date() - period_start_local.date()).days
    if day_delta <= 0:
        elapsed_days = Decimal(
            (period_end_local - period_start_local).total_seconds() / 86400
        )
    else:
        elapsed_days = Decimal(day_delta)

    year_days = Decimal(366 if calendar.isleap(period_start_local.year) else 365)
    return elapsed_days / year_days


def accrue_interest_micro_minor(
    *,
    balance_minor: int,
    apr_bps: int,
    period_start_local: datetime,
    period_end_local: datetime,
) -> int:
    """Accrue pending interest in micro-minor units for a period."""

    if balance_minor <= 0 or apr_bps <= 0:
        return 0

    apr_fraction = Decimal(apr_bps) / Decimal(10_000)
    period_fraction = period_fraction_of_year(period_start_local, period_end_local)
    interest_minor = Decimal(balance_minor) * apr_fraction * period_fraction
    interest_micro_minor = (
        interest_minor * Decimal(MICRO_MINOR_PER_MINOR)
    ).to_integral_value(rounding=ROUND_HALF_UP)
    return int(interest_micro_minor)


def payoutable_minor_from_pending_micro(pending_micro_minor: int) -> int:
    """Convert pending micro-minor into payable whole minor units."""

    if pending_micro_minor <= 0:
        return 0
    return pending_micro_minor // MICRO_MINOR_PER_MINOR
