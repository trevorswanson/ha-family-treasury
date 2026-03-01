"""Coordinator and domain runtime logic for Family Treasury."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ACCOUNT_ID,
    ATTR_CURRENCY_CODE,
    ATTR_DISPLAY_NAME,
    ATTR_FORMATTED_BALANCE,
    ATTR_FORMATTED_PENDING_INTEREST,
    ATTR_LAST_INTEREST_CALC_AT,
    ATTR_LAST_INTEREST_PAYOUT_AT,
    ATTR_LOCALE,
    ATTR_RECENT_TRANSACTIONS,
    CONF_APR_PERCENT,
    CONF_CURRENCY_CODE,
    CONF_DEFAULT_APR_PERCENT,
    CONF_DESCRIPTION,
    CONF_DISPLAY_NAME,
    CONF_END,
    CONF_INTEREST_CALC_FREQUENCY,
    CONF_INTEREST_PAYOUT_FREQUENCY,
    CONF_LIMIT,
    CONF_LOCALE,
    CONF_OFFSET,
    CONF_START,
    CONF_TYPE,
    DEFAULT_APR_PERCENT,
    DEFAULT_CURRENCY_CODE,
    DEFAULT_INTEREST_CALC_FREQUENCY,
    DEFAULT_INTEREST_PAYOUT_FREQUENCY,
    DEFAULT_LOCALE,
    DOMAIN,
    MICRO_MINOR_PER_MINOR,
    RECENT_TRANSACTIONS_LIMIT,
    SCHEDULER_INTERVAL,
    SIGNAL_ACCOUNTS_UPDATED,
    TX_ADJUSTMENT,
    TX_DEPOSIT,
    TX_INTEREST_ACCRUAL,
    TX_INTEREST_PAYOUT,
    TX_TYPES,
    TX_WITHDRAW,
)
from .interest import (
    accrue_interest_micro_minor,
    advance_boundary,
    next_boundary,
    payoutable_minor_from_pending_micro,
)
from .models import (
    AccountRecord,
    TransactionRecord,
    account_defaults_from_settings,
    format_minor_amount,
    format_pending_micro_amount,
    minor_to_major_decimal,
    parse_datetime,
    parse_major_to_minor,
    pending_micro_to_major_decimal,
    utcnow_iso,
    warm_currency_formatters,
)
from .storage import FamilyTreasuryStorage

_LOGGER = logging.getLogger(__name__)
UTC = timezone.utc


class FamilyTreasuryCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Domain runtime and coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        storage: FamilyTreasuryStorage,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.hass = hass
        self.entry = entry
        self.storage = storage
        self._lock = asyncio.Lock()
        self._accounts: dict[str, AccountRecord] = {}
        self._recent_transactions: dict[str, list[dict[str, Any]]] = {}
        self._formatter_pairs_warmed: set[tuple[str, str]] = set()
        self._unsub_scheduler = None

    @property
    def accounts(self) -> dict[str, AccountRecord]:
        """Return accounts by account_id."""

        return self._accounts

    def list_account_ids(self) -> list[str]:
        """Return all account IDs."""

        return sorted(self._accounts)

    def account(self, account_id: str) -> AccountRecord | None:
        """Get an account by ID."""

        return self._accounts.get(account_id)

    def account_state(self, account_id: str) -> dict[str, Any] | None:
        """Build sensor-facing account state."""

        account = self._accounts.get(account_id)
        if account is None:
            return None

        return {
            ATTR_ACCOUNT_ID: account.account_id,
            ATTR_DISPLAY_NAME: account.display_name,
            ATTR_CURRENCY_CODE: account.currency_code,
            ATTR_LOCALE: account.locale,
            ATTR_FORMATTED_BALANCE: format_minor_amount(
                account.balance_minor,
                account.currency_code,
                account.locale,
            ),
            ATTR_FORMATTED_PENDING_INTEREST: format_pending_micro_amount(
                account.pending_interest_micro_minor,
                account.currency_code,
                account.locale,
            ),
            ATTR_LAST_INTEREST_CALC_AT: account.last_calc_at,
            ATTR_LAST_INTEREST_PAYOUT_AT: account.last_payout_at,
            ATTR_RECENT_TRANSACTIONS: self._recent_transactions.get(account_id, []),
            "balance_major": minor_to_major_decimal(
                account.balance_minor,
                account.currency_code,
            ),
            "pending_interest_major": pending_micro_to_major_decimal(
                account.pending_interest_micro_minor,
                account.currency_code,
            ),
            "active": account.active,
        }

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Coordinator poll method."""

        return {
            account_id: self.account_state(account_id) or {}
            for account_id in self.list_account_ids()
        }

    async def async_initialize(self) -> None:
        """Load storage and start scheduler."""

        await self.storage.async_load()
        self._accounts = self.storage.list_accounts()

        for account_id in self._accounts:
            self._recent_transactions[account_id] = await self._load_recent_transactions(
                account_id
            )

        await self._async_prime_formatter_cache()
        await self.async_process_interest(snapshot_after_run=True)
        self.async_set_updated_data(await self._async_update_data())

        if self._unsub_scheduler is None:
            self._unsub_scheduler = async_track_time_interval(
                self.hass,
                self._async_scheduler_tick,
                SCHEDULER_INTERVAL,
            )

    async def async_shutdown(self) -> None:
        """Stop background tasks."""

        if self._unsub_scheduler is not None:
            self._unsub_scheduler()
            self._unsub_scheduler = None

    def global_settings(self) -> dict[str, Any]:
        """Return merged global settings from config entry."""

        merged = dict(self.entry.data)
        merged.update(self.entry.options)

        return {
            CONF_DEFAULT_APR_PERCENT: str(
                merged.get(CONF_DEFAULT_APR_PERCENT, DEFAULT_APR_PERCENT)
            ),
            CONF_INTEREST_CALC_FREQUENCY: merged.get(
                CONF_INTEREST_CALC_FREQUENCY,
                DEFAULT_INTEREST_CALC_FREQUENCY,
            ),
            CONF_INTEREST_PAYOUT_FREQUENCY: merged.get(
                CONF_INTEREST_PAYOUT_FREQUENCY,
                DEFAULT_INTEREST_PAYOUT_FREQUENCY,
            ),
            CONF_CURRENCY_CODE: str(
                merged.get(CONF_CURRENCY_CODE, DEFAULT_CURRENCY_CODE)
            ).upper(),
            CONF_LOCALE: str(merged.get(CONF_LOCALE, DEFAULT_LOCALE)),
        }

    async def async_apply_defaults_to_existing_accounts(
        self,
        *,
        default_apr_percent: str,
        calc_frequency: str,
        payout_frequency: str,
        currency_code: str,
        locale: str,
    ) -> None:
        """Apply global defaults to existing accounts."""

        async with self._lock:
            defaults = account_defaults_from_settings(
                {
                    CONF_DEFAULT_APR_PERCENT: default_apr_percent,
                    CONF_INTEREST_CALC_FREQUENCY: calc_frequency,
                    CONF_INTEREST_PAYOUT_FREQUENCY: payout_frequency,
                    CONF_CURRENCY_CODE: currency_code,
                    CONF_LOCALE: locale,
                }
            )
            changed = False
            for account in self._accounts.values():
                account.apr_bps = defaults["apr_bps"]
                account.calc_frequency = calc_frequency
                account.payout_frequency = payout_frequency
                account.locale = locale
                if (
                    account.currency_code == currency_code.upper()
                    or (
                        account.balance_minor == 0
                        and account.pending_interest_micro_minor == 0
                    )
                ):
                    account.currency_code = currency_code.upper()
                account.updated_at = utcnow_iso()
                changed = True

            if changed:
                await self.storage.async_replace_accounts(self._accounts)
                await self._async_refresh_state()

    async def async_create_account(self, payload: dict[str, Any]) -> None:
        """Create a new virtual account."""

        account_id = str(payload["account_id"])
        if account_id in self._accounts:
            raise ValueError(f"Account already exists: {account_id}")

        defaults = account_defaults_from_settings(self.global_settings())
        if CONF_APR_PERCENT in payload:
            defaults["apr_bps"] = account_defaults_from_settings(
                {
                    CONF_DEFAULT_APR_PERCENT: payload[CONF_APR_PERCENT],
                    CONF_INTEREST_CALC_FREQUENCY: defaults["calc_frequency"],
                    CONF_INTEREST_PAYOUT_FREQUENCY: defaults["payout_frequency"],
                    CONF_CURRENCY_CODE: defaults["currency_code"],
                    CONF_LOCALE: defaults["locale"],
                }
            )["apr_bps"]
        if CONF_INTEREST_CALC_FREQUENCY in payload:
            defaults["calc_frequency"] = payload[CONF_INTEREST_CALC_FREQUENCY]
        if CONF_INTEREST_PAYOUT_FREQUENCY in payload:
            defaults["payout_frequency"] = payload[CONF_INTEREST_PAYOUT_FREQUENCY]
        if CONF_CURRENCY_CODE in payload:
            defaults["currency_code"] = str(payload[CONF_CURRENCY_CODE]).upper()
        if CONF_LOCALE in payload:
            defaults["locale"] = str(payload[CONF_LOCALE])

        initial_balance_minor = 0
        if "initial_balance" in payload:
            initial_balance_minor = parse_major_to_minor(
                payload["initial_balance"],
                defaults["currency_code"],
            )

        now_iso = utcnow_iso()
        account = AccountRecord(
            account_id=account_id,
            display_name=str(payload[CONF_DISPLAY_NAME]),
            currency_code=defaults["currency_code"],
            locale=defaults["locale"],
            apr_bps=defaults["apr_bps"],
            calc_frequency=defaults["calc_frequency"],
            payout_frequency=defaults["payout_frequency"],
            balance_minor=initial_balance_minor,
            last_calc_at=now_iso,
            last_payout_at=now_iso,
            created_at=now_iso,
            updated_at=now_iso,
        )

        async with self._lock:
            self._accounts[account_id] = account
            await self.storage.async_replace_accounts(self._accounts)

            if initial_balance_minor > 0:
                await self._append_transaction(
                    account,
                    tx_type=TX_DEPOSIT,
                    amount_minor=initial_balance_minor,
                    description="Initial balance",
                    balance_after_minor=account.balance_minor,
                )
            await self._maybe_snapshot(account)

        async_dispatcher_send(self.hass, SIGNAL_ACCOUNTS_UPDATED)
        await self._async_refresh_state()

    async def async_update_account(self, payload: dict[str, Any]) -> None:
        """Update mutable account fields."""

        account_id = str(payload["account_id"])
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError(f"Unknown account: {account_id}")

        async with self._lock:
            if CONF_DISPLAY_NAME in payload:
                account.display_name = str(payload[CONF_DISPLAY_NAME])

            if "active" in payload:
                account.active = bool(payload["active"])

            if CONF_APR_PERCENT in payload:
                account.apr_bps = account_defaults_from_settings(
                    {
                        CONF_DEFAULT_APR_PERCENT: payload[CONF_APR_PERCENT],
                        CONF_INTEREST_CALC_FREQUENCY: account.calc_frequency,
                        CONF_INTEREST_PAYOUT_FREQUENCY: account.payout_frequency,
                        CONF_CURRENCY_CODE: account.currency_code,
                        CONF_LOCALE: account.locale,
                    }
                )["apr_bps"]

            if CONF_INTEREST_CALC_FREQUENCY in payload:
                account.calc_frequency = payload[CONF_INTEREST_CALC_FREQUENCY]
            if CONF_INTEREST_PAYOUT_FREQUENCY in payload:
                account.payout_frequency = payload[CONF_INTEREST_PAYOUT_FREQUENCY]

            if CONF_CURRENCY_CODE in payload:
                currency_code = str(payload[CONF_CURRENCY_CODE]).upper()
                if currency_code != account.currency_code and (
                    account.balance_minor != 0 or account.pending_interest_micro_minor != 0
                ):
                    raise ValueError(
                        "Cannot change currency on non-empty account; set balances to zero first"
                    )
                account.currency_code = currency_code

            if CONF_LOCALE in payload:
                account.locale = str(payload[CONF_LOCALE])

            account.updated_at = utcnow_iso()
            await self.storage.async_replace_accounts(self._accounts)
            await self._maybe_snapshot(account)

        async_dispatcher_send(self.hass, SIGNAL_ACCOUNTS_UPDATED)
        await self._async_refresh_state()

    async def async_deposit(
        self,
        *,
        account_id: str,
        amount: Any,
        description: str,
    ) -> None:
        """Deposit funds into an account."""

        await self._async_apply_balance_change(
            account_id=account_id,
            tx_type=TX_DEPOSIT,
            amount=amount,
            description=description,
            allow_signed=False,
        )

    async def async_withdraw(
        self,
        *,
        account_id: str,
        amount: Any,
        description: str,
    ) -> None:
        """Withdraw funds from an account."""

        account = self._require_account(account_id)
        amount_minor = parse_major_to_minor(amount, account.currency_code)
        if amount_minor <= 0:
            raise ValueError("Withdrawal amount must be greater than zero")

        async with self._lock:
            if account.balance_minor - amount_minor < 0:
                raise ValueError("Insufficient funds")
            account.balance_minor -= amount_minor
            account.updated_at = utcnow_iso()
            await self._append_transaction(
                account,
                tx_type=TX_WITHDRAW,
                amount_minor=-amount_minor,
                description=description,
                balance_after_minor=account.balance_minor,
            )
            await self.storage.async_replace_accounts(self._accounts)
            await self._maybe_snapshot(account)

        await self._async_refresh_state()

    async def async_adjust_balance(
        self,
        *,
        account_id: str,
        amount: Any,
        description: str,
    ) -> None:
        """Apply a signed admin adjustment to balance."""

        await self._async_apply_balance_change(
            account_id=account_id,
            tx_type=TX_ADJUSTMENT,
            amount=amount,
            description=description,
            allow_signed=True,
        )

    async def async_get_transactions(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return filtered transaction history."""

        account_id = payload.get("account_id")
        if account_id and account_id not in self._accounts:
            raise ValueError(f"Unknown account: {account_id}")

        start = self._parse_service_datetime(payload.get(CONF_START))
        end = self._parse_service_datetime(payload.get(CONF_END))
        if start and end and start > end:
            raise ValueError("Start datetime must be before end datetime")
        raw_type_filter = payload.get(CONF_TYPE)
        tx_types: set[str] | None
        if raw_type_filter is None:
            tx_types = None
        elif isinstance(raw_type_filter, str):
            tx_types = {raw_type_filter}
        elif isinstance(raw_type_filter, list):
            tx_types = {
                str(item).strip() for item in raw_type_filter if str(item).strip()
            }
            if not tx_types:
                tx_types = None
        else:
            raise ValueError("Type filter must be a string or a list of strings")

        if tx_types:
            invalid_types = sorted(tx_types - TX_TYPES)
            if invalid_types:
                invalid_label = ", ".join(invalid_types)
                raise ValueError(f"Invalid transaction type filter(s): {invalid_label}")

        await self._async_prime_formatter_cache()
        result = await self.storage.async_list_transactions(
            account_id=account_id,
            start=start,
            end=end,
            tx_types=tx_types,
            limit=int(payload.get(CONF_LIMIT, 100)),
            offset=int(payload.get(CONF_OFFSET, 0)),
        )

        decorated: list[dict[str, Any]] = []
        for row in result["transactions"]:
            account = self._accounts.get(row["account_id"])
            if account is None:
                decorated.append(row)
                continue

            decorated.append(
                {
                    **row,
                    "amount_major": str(
                        minor_to_major_decimal(row["amount_minor"], account.currency_code)
                    ),
                    "formatted_amount": format_minor_amount(
                        row["amount_minor"],
                        account.currency_code,
                        account.locale,
                    ),
                }
            )

        return {
            "transactions": decorated,
            "total": result["total"],
            "limit": result["limit"],
            "offset": result["offset"],
            "next_offset": result["next_offset"],
        }

    async def async_process_interest(self, *, snapshot_after_run: bool = False) -> None:
        """Process due interest accrual and payout events."""

        now_utc = dt_util.utcnow().astimezone(UTC)
        changed_accounts: set[str] = set()

        async with self._lock:
            for account in self._accounts.values():
                if not account.active:
                    continue
                changed = await self._process_interest_for_account(account, now_utc)
                if changed:
                    changed_accounts.add(account.account_id)

            if changed_accounts:
                await self.storage.async_replace_accounts(self._accounts)

            if snapshot_after_run:
                for account in self._accounts.values():
                    await self._maybe_snapshot(account, snapshot_at=now_utc)

        if changed_accounts:
            await self._async_refresh_state()

    async def _process_interest_for_account(
        self,
        account: AccountRecord,
        now_utc: datetime,
    ) -> bool:
        tz = dt_util.get_time_zone(self.hass.config.time_zone)
        now_local = now_utc.astimezone(tz)

        last_calc_utc = parse_datetime(account.last_calc_at) or parse_datetime(account.created_at)
        last_payout_utc = parse_datetime(account.last_payout_at) or parse_datetime(
            account.created_at
        )

        if last_calc_utc is None or last_payout_utc is None:
            return False

        calc_cursor = last_calc_utc.astimezone(tz)
        payout_cursor = last_payout_utc.astimezone(tz)

        calc_next = next_boundary(calc_cursor, account.calc_frequency)
        payout_next = next_boundary(payout_cursor, account.payout_frequency)

        changed = False

        while True:
            calc_due = calc_next <= now_local
            payout_due = payout_next <= now_local
            if not calc_due and not payout_due:
                break

            if calc_due and (not payout_due or calc_next <= payout_next):
                accrued_micro = accrue_interest_micro_minor(
                    balance_minor=account.balance_minor,
                    apr_bps=account.apr_bps,
                    period_start_local=calc_cursor,
                    period_end_local=calc_next,
                )
                if accrued_micro > 0:
                    account.pending_interest_micro_minor += accrued_micro
                    await self._append_transaction(
                        account,
                        tx_type=TX_INTEREST_ACCRUAL,
                        amount_minor=0,
                        description="Interest accrued",
                        balance_after_minor=account.balance_minor,
                        occurred_at=calc_next.astimezone(UTC),
                        meta={
                            "accrued_micro_minor": accrued_micro,
                            "period_start": calc_cursor.astimezone(UTC).isoformat(),
                            "period_end": calc_next.astimezone(UTC).isoformat(),
                        },
                    )
                    changed = True

                calc_cursor = calc_next
                account.last_calc_at = calc_cursor.astimezone(UTC).isoformat()
                account.updated_at = utcnow_iso()
                changed = True
                calc_next = advance_boundary(calc_next, account.calc_frequency)

            if payout_due and (not calc_due or payout_next <= calc_next):
                payout_minor = payoutable_minor_from_pending_micro(
                    account.pending_interest_micro_minor
                )
                if payout_minor > 0:
                    account.balance_minor += payout_minor
                    account.pending_interest_micro_minor -= (
                        payout_minor * MICRO_MINOR_PER_MINOR
                    )
                    await self._append_transaction(
                        account,
                        tx_type=TX_INTEREST_PAYOUT,
                        amount_minor=payout_minor,
                        description="Interest payout",
                        balance_after_minor=account.balance_minor,
                        occurred_at=payout_next.astimezone(UTC),
                    )
                    changed = True

                payout_cursor = payout_next
                account.last_payout_at = payout_cursor.astimezone(UTC).isoformat()
                account.updated_at = utcnow_iso()
                changed = True
                payout_next = advance_boundary(payout_next, account.payout_frequency)

        return changed

    async def _async_scheduler_tick(self, now: datetime) -> None:
        """Run periodic interest processing."""

        await self.async_process_interest(snapshot_after_run=False)

    async def _async_apply_balance_change(
        self,
        *,
        account_id: str,
        tx_type: str,
        amount: Any,
        description: str,
        allow_signed: bool,
    ) -> None:
        account = self._require_account(account_id)
        amount_minor = parse_major_to_minor(
            amount,
            account.currency_code,
            signed=allow_signed,
        )

        if tx_type == TX_DEPOSIT:
            if amount_minor <= 0:
                raise ValueError("Deposit amount must be greater than zero")
            delta = amount_minor
        elif tx_type == TX_ADJUSTMENT:
            if amount_minor == 0:
                raise ValueError("Adjustment amount must not be zero")
            delta = amount_minor
        else:
            raise ValueError(f"Unsupported balance change transaction type: {tx_type}")

        async with self._lock:
            if account.balance_minor + delta < 0:
                raise ValueError("Insufficient funds")

            account.balance_minor += delta
            account.updated_at = utcnow_iso()

            await self._append_transaction(
                account,
                tx_type=tx_type,
                amount_minor=delta,
                description=description,
                balance_after_minor=account.balance_minor,
            )
            await self.storage.async_replace_accounts(self._accounts)
            await self._maybe_snapshot(account)

        await self._async_refresh_state()

    async def _append_transaction(
        self,
        account: AccountRecord,
        *,
        tx_type: str,
        amount_minor: int,
        description: str,
        balance_after_minor: int,
        occurred_at: datetime | None = None,
        meta: dict[str, Any] | None = None,
    ) -> TransactionRecord:
        tx_id = await self.storage.async_reserve_tx_id()
        occurred_at_iso = (
            (occurred_at or dt_util.utcnow().astimezone(UTC)).astimezone(UTC).isoformat()
        )
        transaction = TransactionRecord(
            tx_id=tx_id,
            account_id=account.account_id,
            occurred_at=occurred_at_iso,
            type=tx_type,
            amount_minor=amount_minor,
            balance_after_minor=balance_after_minor,
            meta={
                CONF_DESCRIPTION: description,
                **(meta or {}),
            },
        )

        await self.storage.async_append_transaction(transaction)
        self._prepend_recent_transaction(transaction)
        return transaction

    async def _load_recent_transactions(self, account_id: str) -> list[dict[str, Any]]:
        result = await self.storage.async_list_transactions(
            account_id=account_id,
            start=None,
            end=None,
            tx_types=None,
            limit=RECENT_TRANSACTIONS_LIMIT,
            offset=0,
        )
        return result["transactions"]

    def _prepend_recent_transaction(self, transaction: TransactionRecord) -> None:
        current = list(self._recent_transactions.get(transaction.account_id, []))
        current.insert(0, transaction.to_dict())
        self._recent_transactions[transaction.account_id] = current[
            :RECENT_TRANSACTIONS_LIMIT
        ]

    async def _async_refresh_state(self) -> None:
        await self._async_prime_formatter_cache()
        self.async_set_updated_data(await self._async_update_data())

    async def _async_prime_formatter_cache(self) -> None:
        warmed = getattr(self, "_formatter_pairs_warmed", set())
        pairs = {
            (account.currency_code, account.locale) for account in self._accounts.values()
        }
        missing = pairs - warmed
        if not missing:
            return

        async_add_executor_job = getattr(self.hass, "async_add_executor_job", None)
        if async_add_executor_job is not None:
            await async_add_executor_job(warm_currency_formatters, missing)
        else:
            warm_currency_formatters(missing)
        warmed.update(missing)
        self._formatter_pairs_warmed = warmed

    async def _maybe_snapshot(
        self,
        account: AccountRecord,
        *,
        snapshot_at: datetime | None = None,
    ) -> None:
        when = (snapshot_at or dt_util.utcnow().astimezone(UTC)).astimezone(UTC)
        await self.storage.async_create_monthly_snapshot(
            account=account,
            last_tx_id=self.storage.last_tx_id,
            snapshot_at=when,
        )

    def _require_account(self, account_id: str) -> AccountRecord:
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError(f"Unknown account: {account_id}")
        return account

    @staticmethod
    def _parse_service_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)

        parsed = dt_util.parse_datetime(str(value))
        if parsed is None:
            raise ValueError(f"Invalid datetime: {value}")
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
