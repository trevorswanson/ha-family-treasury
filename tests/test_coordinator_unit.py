"""Unit tests for coordinator behavior without full HA runtime."""

from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

HA_AVAILABLE = True
try:
    from custom_components.family_treasury.const import (
        CONF_ACCOUNT_ID,
        CONF_APR_PERCENT,
        CONF_CURRENCY_CODE,
        CONF_DEFAULT_APR_PERCENT,
        CONF_DISPLAY_NAME,
        CONF_END,
        CONF_INTEREST_CALC_FREQUENCY,
        CONF_INTEREST_PAYOUT_FREQUENCY,
        CONF_LIMIT,
        CONF_LOCALE,
        CONF_OFFSET,
        CONF_START,
        CONF_TYPE,
        TX_ADJUSTMENT,
        TX_DEPOSIT,
        TX_WITHDRAW,
    )
    from custom_components.family_treasury.coordinator import FamilyTreasuryCoordinator
    from custom_components.family_treasury.models import AccountRecord, TransactionRecord
except ModuleNotFoundError:
    HA_AVAILABLE = False


class _StorageStub:
    def __init__(self) -> None:
        self.last_tx_id = 0
        self.async_replace_accounts = AsyncMock()
        self.async_create_monthly_snapshot = AsyncMock()
        self.async_append_transaction = AsyncMock()
        self.async_reserve_tx_id = AsyncMock(side_effect=[1, 2, 3, 4, 5])
        self.async_list_transactions = AsyncMock(
            return_value={
                "transactions": [],
                "total": 0,
                "limit": 100,
                "offset": 0,
                "next_offset": None,
            }
        )


def _build_coordinator() -> FamilyTreasuryCoordinator:
    coordinator = object.__new__(FamilyTreasuryCoordinator)
    coordinator.hass = SimpleNamespace(config=SimpleNamespace(time_zone="UTC"))
    coordinator.entry = SimpleNamespace(data={}, options={})
    coordinator.storage = _StorageStub()
    coordinator._lock = asyncio.Lock()
    coordinator._accounts = {}
    coordinator._recent_transactions = {}
    coordinator._unsub_scheduler = None
    coordinator.async_set_updated_data = lambda data: setattr(
        coordinator,
        "_last_updated_data",
        data,
    )
    return coordinator


@unittest.skipUnless(HA_AVAILABLE, "homeassistant is not installed in this environment")
class TestCoordinatorUnit(unittest.IsolatedAsyncioTestCase):
    """Coordinator behavior tests."""

    async def test_global_settings_merge_options_over_data(self) -> None:
        coordinator = _build_coordinator()
        coordinator.entry = SimpleNamespace(
            data={
                CONF_DEFAULT_APR_PERCENT: "1.1",
                CONF_INTEREST_CALC_FREQUENCY: "daily",
                CONF_INTEREST_PAYOUT_FREQUENCY: "monthly",
                CONF_CURRENCY_CODE: "usd",
                CONF_LOCALE: "en_US",
            },
            options={
                CONF_DEFAULT_APR_PERCENT: "2.2",
                CONF_INTEREST_PAYOUT_FREQUENCY: "weekly",
            },
        )

        settings = coordinator.global_settings()

        self.assertEqual(settings[CONF_DEFAULT_APR_PERCENT], "2.2")
        self.assertEqual(settings[CONF_INTEREST_CALC_FREQUENCY], "daily")
        self.assertEqual(settings[CONF_INTEREST_PAYOUT_FREQUENCY], "weekly")
        self.assertEqual(settings[CONF_CURRENCY_CODE], "USD")

    async def test_account_state_and_require_account(self) -> None:
        coordinator = _build_coordinator()
        account = AccountRecord(
            account_id="emma",
            display_name="Emma",
            currency_code="USD",
            locale="en_US",
            balance_minor=1234,
            pending_interest_micro_minor=1_500_000,
            last_calc_at="2026-02-01T00:00:00+00:00",
            last_payout_at="2026-02-01T00:00:00+00:00",
        )
        coordinator._accounts["emma"] = account
        coordinator._recent_transactions["emma"] = [{"tx_id": 1}]

        state = coordinator.account_state("emma")
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state["active"], True)
        self.assertEqual(str(state["balance_major"]), "12.34")
        self.assertEqual(state["recent_transactions"], [{"tx_id": 1}])

        required = coordinator._require_account("emma")
        self.assertEqual(required.account_id, "emma")

        with self.assertRaises(ValueError):
            coordinator._require_account("missing")

    async def test_prepend_recent_transaction_caps_length(self) -> None:
        coordinator = _build_coordinator()
        coordinator._recent_transactions["emma"] = [
            {"tx_id": n} for n in range(2, 20)
        ]
        transaction = TransactionRecord(
            tx_id=1,
            account_id="emma",
            occurred_at="2026-02-01T00:00:00+00:00",
            type="deposit",
            amount_minor=100,
            balance_after_minor=100,
        )

        coordinator._prepend_recent_transaction(transaction)

        self.assertEqual(coordinator._recent_transactions["emma"][0]["tx_id"], 1)
        self.assertEqual(len(coordinator._recent_transactions["emma"]), 10)

    async def test_parse_service_datetime_variants(self) -> None:
        self.assertIsNone(FamilyTreasuryCoordinator._parse_service_datetime(None))

        naive = datetime(2026, 2, 1, 10, 0)
        parsed_naive = FamilyTreasuryCoordinator._parse_service_datetime(naive)
        self.assertEqual(parsed_naive.tzinfo, UTC)

        aware = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)
        parsed_aware = FamilyTreasuryCoordinator._parse_service_datetime(aware)
        self.assertEqual(parsed_aware.tzinfo, UTC)

        parsed_string = FamilyTreasuryCoordinator._parse_service_datetime(
            "2026-02-01T10:00:00+00:00"
        )
        self.assertEqual(parsed_string.tzinfo, UTC)

        with self.assertRaises(ValueError):
            FamilyTreasuryCoordinator._parse_service_datetime("not-a-date")

    async def test_apply_defaults_respects_non_empty_currency(self) -> None:
        coordinator = _build_coordinator()
        non_empty = AccountRecord(
            account_id="non_empty",
            display_name="Non Empty",
            currency_code="USD",
            locale="en_US",
            balance_minor=100,
        )
        empty = AccountRecord(
            account_id="empty",
            display_name="Empty",
            currency_code="USD",
            locale="en_US",
            balance_minor=0,
            pending_interest_micro_minor=0,
        )
        coordinator._accounts = {"non_empty": non_empty, "empty": empty}
        coordinator._async_refresh_state = AsyncMock()

        await coordinator.async_apply_defaults_to_existing_accounts(
            default_apr_percent="3.5",
            calc_frequency="weekly",
            payout_frequency="monthly",
            currency_code="ISK",
            locale="is_IS",
        )

        self.assertEqual(non_empty.currency_code, "USD")
        self.assertEqual(empty.currency_code, "ISK")
        self.assertEqual(non_empty.locale, "is_IS")
        coordinator.storage.async_replace_accounts.assert_awaited_once()

    async def test_async_get_transactions_decorates_known_accounts(self) -> None:
        coordinator = _build_coordinator()
        coordinator._accounts = {
            "emma": AccountRecord(
                account_id="emma",
                display_name="Emma",
                currency_code="USD",
                locale="en_US",
            )
        }
        coordinator.storage.async_list_transactions = AsyncMock(
            return_value={
                "transactions": [
                    {
                        "tx_id": 1,
                        "account_id": "emma",
                        "occurred_at": "2026-02-01T00:00:00+00:00",
                        "type": "deposit",
                        "amount_minor": 123,
                        "balance_after_minor": 123,
                        "meta": {"description": "Allowance"},
                    },
                    {
                        "tx_id": 2,
                        "account_id": "unknown",
                        "occurred_at": "2026-02-01T00:00:00+00:00",
                        "type": "deposit",
                        "amount_minor": 50,
                        "balance_after_minor": 50,
                        "meta": {},
                    },
                ],
                "total": 2,
                "limit": 10,
                "offset": 0,
                "next_offset": None,
            }
        )

        result = await coordinator.async_get_transactions(
            {
                CONF_START: "2026-01-01T00:00:00+00:00",
                CONF_END: "2026-12-31T00:00:00+00:00",
                CONF_LIMIT: 10,
                CONF_OFFSET: 0,
            }
        )

        self.assertEqual(result["total"], 2)
        self.assertIn("formatted_amount", result["transactions"][0])
        self.assertNotIn("formatted_amount", result["transactions"][1])
        self.assertNotIn("description", result["transactions"][0])
        self.assertNotIn("description", result["transactions"][1])
        self.assertEqual(result["transactions"][0]["meta"]["description"], "Allowance")

    async def test_async_get_transactions_validates_filters(self) -> None:
        coordinator = _build_coordinator()

        with self.assertRaises(ValueError):
            await coordinator.async_get_transactions(
                {
                    CONF_ACCOUNT_ID: "missing",
                }
            )

        coordinator._accounts = {
            "emma": AccountRecord(account_id="emma", display_name="Emma")
        }
        with self.assertRaises(ValueError):
            await coordinator.async_get_transactions(
                {
                    CONF_ACCOUNT_ID: "emma",
                    CONF_START: "2026-02-10T00:00:00+00:00",
                    CONF_END: "2026-02-01T00:00:00+00:00",
                }
            )

    async def test_apply_balance_change_and_withdraw(self) -> None:
        coordinator = _build_coordinator()
        account = AccountRecord(
            account_id="emma",
            display_name="Emma",
            currency_code="USD",
            balance_minor=500,
        )
        coordinator._accounts = {"emma": account}
        coordinator._append_transaction = AsyncMock()
        coordinator._maybe_snapshot = AsyncMock()
        coordinator._async_refresh_state = AsyncMock()

        await coordinator._async_apply_balance_change(
            account_id="emma",
            tx_type=TX_DEPOSIT,
            amount="1.00",
            description="deposit",
            allow_signed=False,
        )
        self.assertEqual(account.balance_minor, 600)

        await coordinator.async_withdraw(
            account_id="emma",
            amount="0.50",
            description="withdraw",
        )
        self.assertEqual(account.balance_minor, 550)

        with self.assertRaises(ValueError):
            await coordinator.async_withdraw(
                account_id="emma",
                amount="6.00",
                description="too much",
            )

    async def test_update_account_currency_restriction(self) -> None:
        coordinator = _build_coordinator()
        account = AccountRecord(
            account_id="emma",
            display_name="Emma",
            currency_code="USD",
            balance_minor=10,
        )
        coordinator._accounts = {"emma": account}

        with self.assertRaises(ValueError):
            await coordinator.async_update_account(
                {
                    CONF_ACCOUNT_ID: "emma",
                    CONF_CURRENCY_CODE: "ISK",
                }
            )

    async def test_process_interest_for_account_advances_state(self) -> None:
        coordinator = _build_coordinator()
        account = AccountRecord(
            account_id="emma",
            display_name="Emma",
            currency_code="USD",
            apr_bps=1000,
            calc_frequency="daily",
            payout_frequency="daily",
            balance_minor=10_000,
            pending_interest_micro_minor=2_000_000,
            created_at="2026-01-01T00:00:00+00:00",
            last_calc_at="2026-01-01T00:00:00+00:00",
            last_payout_at="2026-01-01T00:00:00+00:00",
        )
        coordinator._append_transaction = AsyncMock()

        changed = await coordinator._process_interest_for_account(
            account,
            datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
        )

        self.assertTrue(changed)
        self.assertIsNotNone(account.last_calc_at)
        self.assertIsNotNone(account.last_payout_at)
        self.assertGreaterEqual(account.balance_minor, 10_000)

    async def test_append_transaction_adds_recent_item(self) -> None:
        coordinator = _build_coordinator()
        account = AccountRecord(
            account_id="emma",
            display_name="Emma",
            currency_code="USD",
            balance_minor=0,
        )

        transaction = await coordinator._append_transaction(
            account,
            tx_type=TX_DEPOSIT,
            amount_minor=200,
            description="bonus",
            balance_after_minor=200,
        )

        self.assertEqual(transaction.tx_id, 1)
        self.assertEqual(coordinator._recent_transactions["emma"][0]["tx_id"], 1)
        coordinator.storage.async_append_transaction.assert_awaited_once()

    async def test_apply_balance_change_validation_errors(self) -> None:
        coordinator = _build_coordinator()
        account = AccountRecord(
            account_id="emma",
            display_name="Emma",
            currency_code="USD",
            balance_minor=100,
        )
        coordinator._accounts = {"emma": account}
        coordinator._append_transaction = AsyncMock()
        coordinator._maybe_snapshot = AsyncMock()
        coordinator._async_refresh_state = AsyncMock()

        with self.assertRaises(ValueError):
            await coordinator._async_apply_balance_change(
                account_id="emma",
                tx_type=TX_DEPOSIT,
                amount="0",
                description="bad",
                allow_signed=False,
            )

        with self.assertRaises(ValueError):
            await coordinator._async_apply_balance_change(
                account_id="emma",
                tx_type=TX_ADJUSTMENT,
                amount="0",
                description="bad",
                allow_signed=True,
            )

        with self.assertRaises(ValueError):
            await coordinator._async_apply_balance_change(
                account_id="emma",
                tx_type="other",
                amount="1",
                description="bad",
                allow_signed=True,
            )


if __name__ == "__main__":
    unittest.main()
