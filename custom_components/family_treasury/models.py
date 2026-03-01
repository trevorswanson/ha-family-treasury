"""Domain models and money helpers for Family Treasury."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

try:
    from babel.numbers import format_currency as babel_format_currency
except ImportError:  # pragma: no cover
    babel_format_currency = None

from .const import (
    ACCOUNT_TYPE_PRIMARY,
    MICRO_MINOR_PER_MINOR,
)

UTC = timezone.utc

ZERO_DECIMAL_CURRENCIES = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "ISK",
    "JPY",
    "KMF",
    "KRW",
    "PYG",
    "RWF",
    "UGX",
    "UYI",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}
THREE_DECIMAL_CURRENCIES = {"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"}


@dataclass(slots=True)
class AccountRecord:
    """Persisted account state."""

    account_id: str
    display_name: str
    active: bool = True
    account_type: str = ACCOUNT_TYPE_PRIMARY
    parent_account_id: str | None = None
    currency_code: str = "USD"
    locale: str = "en_US"
    apr_bps: int = 100
    calc_frequency: str = "daily"
    payout_frequency: str = "monthly"
    balance_minor: int = 0
    pending_interest_micro_minor: int = 0
    last_calc_at: str | None = None
    last_payout_at: str | None = None
    created_at: str = field(default_factory=lambda: utcnow_iso())
    updated_at: str = field(default_factory=lambda: utcnow_iso())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccountRecord":
        """Build account from storage data."""

        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""

        return asdict(self)


@dataclass(slots=True)
class TransactionRecord:
    """Persisted transaction row."""

    tx_id: int
    account_id: str
    occurred_at: str
    type: str
    amount_minor: int
    balance_after_minor: int
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransactionRecord":
        """Build transaction from storage data."""

        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""

        return asdict(self)


def utcnow_iso() -> str:
    """Get current UTC timestamp in ISO format."""

    return datetime.now(UTC).isoformat()


def parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime from storage."""

    if not value:
        return None

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def apr_percent_to_bps(value: Any) -> int:
    """Convert APR percent into integer basis points."""

    apr_percent = Decimal(str(value))
    if apr_percent < 0:
        raise ValueError("APR percent cannot be negative")

    return int((apr_percent * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))


def bps_to_percent_string(value: int) -> str:
    """Convert basis points to string percent representation."""

    return f"{(Decimal(value) / Decimal('100')):.2f}"


def currency_minor_exponent(currency_code: str) -> int:
    """Return the decimal precision for a currency."""

    code = currency_code.upper()
    if code in ZERO_DECIMAL_CURRENCIES:
        return 0
    if code in THREE_DECIMAL_CURRENCIES:
        return 3
    return 2


def minor_to_major_decimal(minor_value: int, currency_code: str) -> Decimal:
    """Convert integer minor units to major currency units."""

    exponent = currency_minor_exponent(currency_code)
    scale = Decimal(10) ** exponent
    return Decimal(minor_value) / scale


def parse_major_to_minor(value: Any, currency_code: str, *, signed: bool = False) -> int:
    """Parse major currency amount into integer minor units."""

    amount = Decimal(str(value))
    if not signed and amount < 0:
        raise ValueError("Amount must be non-negative")

    exponent = currency_minor_exponent(currency_code)
    quant = Decimal("1") if exponent == 0 else Decimal(f"1e-{exponent}")
    normalized = amount.quantize(quant)
    if normalized != amount:
        raise ValueError(
            f"Amount has too many fractional digits for {currency_code}: max {exponent}"
        )

    scale = Decimal(10) ** exponent
    return int((normalized * scale).to_integral_value(rounding=ROUND_HALF_UP))


def pending_micro_to_major_decimal(pending_micro_minor: int, currency_code: str) -> Decimal:
    """Convert micro-minor pending value to major currency units."""

    exponent = currency_minor_exponent(currency_code)
    scale = Decimal(10) ** exponent
    return Decimal(pending_micro_minor) / (scale * Decimal(MICRO_MINOR_PER_MINOR))


def format_amount_major(
    value: Decimal,
    currency_code: str,
    locale: str,
) -> str:
    """Format a major amount using locale-aware currency rules when possible."""

    if babel_format_currency is not None:
        try:
            return babel_format_currency(value, currency_code, locale=locale)
        except Exception:  # pragma: no cover
            pass

    exponent = currency_minor_exponent(currency_code)
    if exponent == 0:
        numeric = f"{int(value):,}"
    else:
        numeric = f"{value:,.{exponent}f}"
    return f"{currency_code} {numeric}"


def format_minor_amount(minor_value: int, currency_code: str, locale: str) -> str:
    """Format a minor-unit amount."""

    return format_amount_major(minor_to_major_decimal(minor_value, currency_code), currency_code, locale)


def format_pending_micro_amount(
    pending_micro_minor: int,
    currency_code: str,
    locale: str,
) -> str:
    """Format a pending micro-minor amount."""

    return format_amount_major(
        pending_micro_to_major_decimal(pending_micro_minor, currency_code),
        currency_code,
        locale,
    )


def account_defaults_from_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Build account defaults from global settings."""

    return {
        "apr_bps": apr_percent_to_bps(settings["default_apr_percent"]),
        "calc_frequency": settings["interest_calc_frequency"],
        "payout_frequency": settings["interest_payout_frequency"],
        "currency_code": settings["currency_code"].upper(),
        "locale": settings["locale"],
    }
