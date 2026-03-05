"""Unit tests for coordinator behavior without full HA runtime."""

from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

HA_AVAILABLE = True
try:
    from custom_components.family_treasury.const import (
        ACCOUNT_TYPE_LOAN,
        ACCOUNT_TYPE_PRIMARY,
        BALANCE_MODE_ERASE,
        CONF_ACCOUNT_ID,
        CONF_ACCOUNT_TYPE,
        CONF_APR_PERCENT,
        CONF_CURRENCY_CODE,
        CONF_DEFAULT_APR_PERCENT,
        CONF_DESTINATION_ACCOUNT_ID,
        CONF_DISPLAY_NAME,
        CONF_END,
        CONF_INITIAL_BALANCE,
        CONF_INTEREST_CALC_FREQUENCY,
        CONF_INTEREST_PAYOUT_FREQUENCY,
        CONF_LIMIT,
        CONF_LOCALE,
        CONF_OFFSET,
        CONF_PARENT_ACCOUNT_ID,
        CONF_SOURCE_ACCOUNT_ID,
        CONF_START,
        CONF_TYPE,
        TX_ADJUSTMENT,
        TX_DEPOSIT,
        TX_INTEREST_PAYOUT,
        TX_TRANSFER_IN,
        TX_TRANSFER_OUT,
        TX_WITHDRAW,
    )
    from custom_components.family_treasury.coordinator import FamilyTreasuryCoordinator
    from custom_components.family_treasury.models import AccountRecord, TransactionRecord
except ModuleNotFoundError:
    HA_AVAILABLE = False


class _StorageStub:
    def __init__(self) -> None:
        self.last_tx_id = 0
        self._next_tx_id = 1
        self.async_replace_accounts = AsyncMock()
        self.async_create_monthly_snapshot = AsyncMock()
        self.async_append_transaction = AsyncMock()
        self.async_reserve_tx_id = AsyncMock(side_effect=self._reserve_tx_id)
        self.async_list_transactions = AsyncMock(
            return_value={
                "transactions": [],
                "total": 0,
                "limit": 100,
                "offset": 0,
                "next_offset": None,
            }
        )
        self.async_delete_snapshots_for_accounts = AsyncMock()
        self.async_purge_transactions_for_accounts = AsyncMock()

    async def _reserve_tx_id(self) -> int:
        tx_id = self._next_tx_id
        self._next_tx_id += 1
        self.last_tx_id = tx_id
        return tx_id


def _build_coordinator() -> FamilyTreasuryCoordinator:
    coordinator = object.__new__(FamilyTreasuryCoordinator)
    coordinator.hass = SimpleNamespace(
        config=SimpleNamespace(time_zone="UTC"),
        data={},
        verify_event_loop_thread=lambda *_args, **_kwargs: None,
    )
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
        self.assertIsNone(state["loan_original_principal_major"])
        self.assertIsNone(state["loan_payoff_progress_percent"])

        required = coordinator._require_account("emma")
        self.assertEqual(required.account_id, "emma")

        with self.assertRaises(ValueError):
            coordinator._require_account("missing")

    async def test_loan_account_state_includes_original_principal_and_progress(self) -> None:
        coordinator = _build_coordinator()
        loan = AccountRecord(
            account_id="emma_loan_1",
            display_name="Emma Loan #1",
            account_type=ACCOUNT_TYPE_LOAN,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=-800,
            original_loan_principal_minor=2000,
            pending_interest_micro_minor=12_000_000,
        )
        coordinator._accounts["emma_loan_1"] = loan

        state = coordinator.account_state("emma_loan_1")
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state["loan_original_principal_major"], Decimal("20"))
        self.assertEqual(state["loan_total_balance_major"], Decimal("8.12"))
        self.assertEqual(state["loan_payoff_progress_percent"], Decimal("59.40"))

    async def test_loan_account_state_falls_back_when_original_principal_missing(self) -> None:
        coordinator = _build_coordinator()
        loan = AccountRecord(
            account_id="legacy_loan",
            display_name="Legacy Loan",
            account_type=ACCOUNT_TYPE_LOAN,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=-800,
            original_loan_principal_minor=None,
            pending_interest_micro_minor=0,
        )
        coordinator._accounts["legacy_loan"] = loan

        state = coordinator.account_state("legacy_loan")
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state["loan_original_principal_major"], Decimal("8"))
        self.assertEqual(state["loan_payoff_progress_percent"], Decimal("0"))

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

        with self.assertRaises(ValueError):
            await coordinator.async_get_transactions({CONF_TYPE: ["deposit", "bad_type"]})

    async def test_async_get_transactions_accepts_multiple_types(self) -> None:
        coordinator = _build_coordinator()
        coordinator._accounts = {
            "emma": AccountRecord(account_id="emma", display_name="Emma")
        }
        coordinator._async_prime_formatter_cache = AsyncMock()
        coordinator.storage.async_list_transactions = AsyncMock(
            return_value={
                "transactions": [],
                "total": 0,
                "limit": 10,
                "offset": 0,
                "next_offset": None,
            }
        )

        await coordinator.async_get_transactions(
            {
                CONF_ACCOUNT_ID: "emma",
                CONF_TYPE: ["deposit", "withdraw", "deposit"],
                CONF_LIMIT: 10,
                CONF_OFFSET: 0,
            }
        )

        called_kwargs = coordinator.storage.async_list_transactions.await_args.kwargs
        self.assertEqual(called_kwargs["tx_types"], {"deposit", "withdraw"})

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

    async def test_create_loan_account_disburses_principal_and_logs_transfer(self) -> None:
        coordinator = _build_coordinator()
        parent = AccountRecord(
            account_id="emma",
            display_name="Emma",
            account_type=ACCOUNT_TYPE_PRIMARY,
            currency_code="USD",
            balance_minor=500,
        )
        coordinator._accounts = {"emma": parent}
        coordinator._async_refresh_state = AsyncMock()

        await coordinator.async_create_account(
            {
                CONF_ACCOUNT_ID: "emma_loan_1",
                CONF_DISPLAY_NAME: "Emma Loan #1",
                CONF_ACCOUNT_TYPE: ACCOUNT_TYPE_LOAN,
                CONF_PARENT_ACCOUNT_ID: "emma",
                CONF_INITIAL_BALANCE: "20.00",
            }
        )

        loan = coordinator._accounts["emma_loan_1"]
        self.assertEqual(loan.parent_account_id, "emma")
        self.assertEqual(loan.account_type, ACCOUNT_TYPE_LOAN)
        self.assertEqual(loan.balance_minor, -2000)
        self.assertEqual(loan.original_loan_principal_minor, 2000)
        self.assertEqual(parent.balance_minor, 2500)

        loan_recent = coordinator._recent_transactions["emma_loan_1"]
        parent_recent = coordinator._recent_transactions["emma"]
        self.assertEqual(loan_recent[0]["type"], TX_TRANSFER_OUT)
        self.assertEqual(parent_recent[0]["type"], TX_TRANSFER_IN)

        state = coordinator.account_state("emma_loan_1")
        assert state is not None
        self.assertEqual(str(state["loan_principal_major"]), "20")
        self.assertEqual(str(state["loan_total_balance_major"]), "20")
        self.assertEqual(str(state["loan_original_principal_major"]), "20")
        self.assertEqual(str(state["loan_payoff_progress_percent"]), "0")
        self.assertEqual(str(state["loan_total_accrued_interest_major"]), "0")

    async def test_create_loan_account_validates_required_fields(self) -> None:
        coordinator = _build_coordinator()
        parent = AccountRecord(
            account_id="emma",
            display_name="Emma",
            account_type=ACCOUNT_TYPE_PRIMARY,
            currency_code="USD",
        )
        coordinator._accounts = {"emma": parent}

        with self.assertRaises(ValueError):
            await coordinator.async_create_account(
                {
                    CONF_ACCOUNT_ID: "loan_missing_parent",
                    CONF_DISPLAY_NAME: "Missing Parent",
                    CONF_ACCOUNT_TYPE: ACCOUNT_TYPE_LOAN,
                    CONF_INITIAL_BALANCE: "10.00",
                }
            )

        with self.assertRaises(ValueError):
            await coordinator.async_create_account(
                {
                    CONF_ACCOUNT_ID: "loan_missing_principal",
                    CONF_DISPLAY_NAME: "Missing Principal",
                    CONF_ACCOUNT_TYPE: ACCOUNT_TYPE_LOAN,
                    CONF_PARENT_ACCOUNT_ID: "emma",
                }
            )

        with self.assertRaises(ValueError):
            await coordinator.async_create_account(
                {
                    CONF_ACCOUNT_ID: "loan_with_legacy_principal_field",
                    CONF_DISPLAY_NAME: "Legacy Loan Payload",
                    CONF_ACCOUNT_TYPE: ACCOUNT_TYPE_LOAN,
                    CONF_PARENT_ACCOUNT_ID: "emma",
                    CONF_INITIAL_BALANCE: "1.00",
                    "loan_principal": "10.00",
                }
            )

        with self.assertRaises(ValueError):
            await coordinator.async_create_account(
                {
                    CONF_ACCOUNT_ID: "loan_unknown_parent",
                    CONF_DISPLAY_NAME: "Unknown Parent",
                    CONF_ACCOUNT_TYPE: ACCOUNT_TYPE_LOAN,
                    CONF_PARENT_ACCOUNT_ID: "missing",
                    CONF_INITIAL_BALANCE: "10.00",
                }
            )

    async def test_transfer_validates_relationship_direction_and_funds(self) -> None:
        coordinator = _build_coordinator()
        emma = AccountRecord(
            account_id="emma",
            display_name="Emma",
            account_type=ACCOUNT_TYPE_PRIMARY,
            currency_code="USD",
            balance_minor=1000,
        )
        emma_bucket = AccountRecord(
            account_id="emma_bucket",
            display_name="Emma Bucket",
            account_type=ACCOUNT_TYPE_PRIMARY,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=200,
        )
        emma_loan = AccountRecord(
            account_id="emma_loan_1",
            display_name="Emma Loan #1",
            account_type=ACCOUNT_TYPE_LOAN,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=-500,
        )
        sam = AccountRecord(
            account_id="sam",
            display_name="Sam",
            account_type=ACCOUNT_TYPE_PRIMARY,
            currency_code="USD",
            balance_minor=1000,
        )
        coordinator._accounts = {
            "emma": emma,
            "emma_bucket": emma_bucket,
            "emma_loan_1": emma_loan,
            "sam": sam,
        }
        coordinator._async_refresh_state = AsyncMock()

        await coordinator.async_transfer(
            source_account_id="emma",
            destination_account_id="emma_loan_1",
            amount="1.00",
            description="repay",
        )
        self.assertEqual(emma.balance_minor, 900)
        self.assertEqual(emma_loan.balance_minor, -400)

        with self.assertRaises(ValueError):
            await coordinator.async_transfer(
                source_account_id="emma_loan_1",
                destination_account_id="emma",
                amount="1.00",
                description="invalid",
            )

        with self.assertRaises(ValueError):
            await coordinator.async_transfer(
                source_account_id="emma",
                destination_account_id="sam",
                amount="1.00",
                description="cross child",
            )

        with self.assertRaises(ValueError):
            await coordinator.async_transfer(
                source_account_id="emma_bucket",
                destination_account_id="emma_loan_1",
                amount="1.00",
                description="non-parent repayment",
            )

        with self.assertRaises(ValueError):
            await coordinator.async_transfer(
                source_account_id="emma",
                destination_account_id="emma_loan_1",
                amount="1000.00",
                description="insufficient",
            )

    async def test_deposit_withdraw_reject_loan_accounts(self) -> None:
        coordinator = _build_coordinator()
        loan = AccountRecord(
            account_id="emma_loan_1",
            display_name="Emma Loan #1",
            account_type=ACCOUNT_TYPE_LOAN,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=-1000,
        )
        coordinator._accounts = {"emma_loan_1": loan}

        with self.assertRaises(ValueError):
            await coordinator.async_deposit(
                account_id="emma_loan_1",
                amount="1.00",
                description="nope",
            )

        with self.assertRaises(ValueError):
            await coordinator.async_withdraw(
                account_id="emma_loan_1",
                amount="1.00",
                description="nope",
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

    async def test_delete_sub_account_disburse_preserves_history_and_credits_parent(self) -> None:
        coordinator = _build_coordinator()
        parent = AccountRecord(
            account_id="emma",
            display_name="Emma",
            currency_code="USD",
            balance_minor=1000,
        )
        child = AccountRecord(
            account_id="emma_bucket",
            display_name="Emma Bucket",
            account_type=ACCOUNT_TYPE_PRIMARY,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=300,
        )
        coordinator._accounts = {"emma": parent, "emma_bucket": child}
        coordinator._async_remove_deleted_entities = AsyncMock()
        coordinator._async_refresh_state = AsyncMock()

        await coordinator.async_delete_account(account_id="emma_bucket", balance_mode=None)

        self.assertEqual(parent.balance_minor, 1300)
        self.assertIn("emma", coordinator._accounts)
        self.assertNotIn("emma_bucket", coordinator._accounts)
        coordinator.storage.async_purge_transactions_for_accounts.assert_not_awaited()

    async def test_delete_sub_account_erase_does_not_credit_parent(self) -> None:
        coordinator = _build_coordinator()
        parent = AccountRecord(
            account_id="emma",
            display_name="Emma",
            currency_code="USD",
            balance_minor=1000,
        )
        child = AccountRecord(
            account_id="emma_bucket",
            display_name="Emma Bucket",
            account_type=ACCOUNT_TYPE_PRIMARY,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=300,
        )
        coordinator._accounts = {"emma": parent, "emma_bucket": child}
        coordinator._async_remove_deleted_entities = AsyncMock()
        coordinator._async_refresh_state = AsyncMock()

        await coordinator.async_delete_account(
            account_id="emma_bucket",
            balance_mode=BALANCE_MODE_ERASE,
        )

        self.assertEqual(parent.balance_minor, 1000)
        self.assertNotIn("emma_bucket", coordinator._accounts)
        coordinator.storage.async_purge_transactions_for_accounts.assert_not_awaited()

    async def test_delete_settles_pending_interest_before_disburse(self) -> None:
        coordinator = _build_coordinator()
        parent = AccountRecord(
            account_id="emma",
            display_name="Emma",
            currency_code="USD",
            balance_minor=1000,
        )
        child = AccountRecord(
            account_id="emma_bucket",
            display_name="Emma Bucket",
            account_type=ACCOUNT_TYPE_PRIMARY,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=100,
            pending_interest_micro_minor=1_500_000,
        )
        coordinator._accounts = {"emma": parent, "emma_bucket": child}
        coordinator._async_remove_deleted_entities = AsyncMock()
        coordinator._async_refresh_state = AsyncMock()

        await coordinator.async_delete_account(account_id="emma_bucket", balance_mode=None)

        self.assertEqual(parent.balance_minor, 1101)
        self.assertNotIn("emma_bucket", coordinator._accounts)

    async def test_delete_loan_with_outstanding_debt_is_allowed(self) -> None:
        coordinator = _build_coordinator()
        parent = AccountRecord(
            account_id="emma",
            display_name="Emma",
            currency_code="USD",
            balance_minor=1000,
        )
        loan = AccountRecord(
            account_id="emma_loan_1",
            display_name="Emma Loan",
            account_type=ACCOUNT_TYPE_LOAN,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=-500,
        )
        coordinator._accounts = {"emma": parent, "emma_loan_1": loan}
        coordinator._async_remove_deleted_entities = AsyncMock()
        coordinator._async_refresh_state = AsyncMock()

        await coordinator.async_delete_account(account_id="emma_loan_1", balance_mode=None)

        self.assertEqual(parent.balance_minor, 1000)
        self.assertNotIn("emma_loan_1", coordinator._accounts)

    async def test_delete_parent_cascades_and_purges_subtree_history(self) -> None:
        coordinator = _build_coordinator()
        root = AccountRecord(
            account_id="emma",
            display_name="Emma",
            currency_code="USD",
            balance_minor=1000,
        )
        child = AccountRecord(
            account_id="emma_bucket",
            display_name="Emma Bucket",
            account_type=ACCOUNT_TYPE_PRIMARY,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=200,
        )
        loan = AccountRecord(
            account_id="emma_loan_1",
            display_name="Emma Loan",
            account_type=ACCOUNT_TYPE_LOAN,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=-50,
        )
        coordinator._accounts = {
            "emma": root,
            "emma_bucket": child,
            "emma_loan_1": loan,
        }
        coordinator._async_remove_deleted_entities = AsyncMock()
        coordinator._async_refresh_state = AsyncMock()

        await coordinator.async_delete_account(account_id="emma", balance_mode=None)

        self.assertEqual(coordinator._accounts, {})
        coordinator.storage.async_purge_transactions_for_accounts.assert_awaited_once_with(
            {"emma", "emma_bucket", "emma_loan_1"}
        )

    async def test_delete_subtree_disburse_uses_net_positive_amount(self) -> None:
        coordinator = _build_coordinator()
        parent = AccountRecord(
            account_id="root",
            display_name="Root",
            currency_code="USD",
            balance_minor=1000,
        )
        subtree_root = AccountRecord(
            account_id="emma",
            display_name="Emma",
            account_type=ACCOUNT_TYPE_PRIMARY,
            parent_account_id="root",
            currency_code="USD",
            balance_minor=300,
        )
        child = AccountRecord(
            account_id="emma_bucket",
            display_name="Emma Bucket",
            account_type=ACCOUNT_TYPE_PRIMARY,
            parent_account_id="emma",
            currency_code="USD",
            balance_minor=-100,
        )
        coordinator._accounts = {
            "root": parent,
            "emma": subtree_root,
            "emma_bucket": child,
        }
        coordinator._async_remove_deleted_entities = AsyncMock()
        coordinator._async_refresh_state = AsyncMock()

        await coordinator.async_delete_account(account_id="emma", balance_mode=None)

        self.assertEqual(parent.balance_minor, 1200)
        self.assertNotIn("emma", coordinator._accounts)
        self.assertNotIn("emma_bucket", coordinator._accounts)

    async def test_delete_disburse_fails_when_subtree_currency_mismatch(self) -> None:
        coordinator = _build_coordinator()
        parent = AccountRecord(
            account_id="root",
            display_name="Root",
            currency_code="USD",
            balance_minor=1000,
        )
        subtree_root = AccountRecord(
            account_id="emma",
            display_name="Emma",
            account_type=ACCOUNT_TYPE_PRIMARY,
            parent_account_id="root",
            currency_code="USD",
            balance_minor=300,
        )
        child = AccountRecord(
            account_id="emma_bucket",
            display_name="Emma Bucket",
            account_type=ACCOUNT_TYPE_PRIMARY,
            parent_account_id="emma",
            currency_code="ISK",
            balance_minor=100,
        )
        coordinator._accounts = {
            "root": parent,
            "emma": subtree_root,
            "emma_bucket": child,
        }
        coordinator._async_remove_deleted_entities = AsyncMock()
        coordinator._async_refresh_state = AsyncMock()

        with self.assertRaises(ValueError):
            await coordinator.async_delete_account(account_id="emma", balance_mode=None)

        self.assertIn("emma", coordinator._accounts)
        self.assertIn("emma_bucket", coordinator._accounts)
        coordinator.storage.async_purge_transactions_for_accounts.assert_not_awaited()

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

    async def test_process_interest_for_loan_reduces_balance_on_payout(self) -> None:
        coordinator = _build_coordinator()
        loan = AccountRecord(
            account_id="emma_loan_1",
            display_name="Emma Loan #1",
            account_type=ACCOUNT_TYPE_LOAN,
            parent_account_id="emma",
            currency_code="USD",
            apr_bps=1000,
            calc_frequency="daily",
            payout_frequency="daily",
            balance_minor=-10_000,
            pending_interest_micro_minor=2_000_000,
            created_at="2026-01-01T00:00:00+00:00",
            last_calc_at="2026-01-01T00:00:00+00:00",
            last_payout_at="2026-01-01T00:00:00+00:00",
        )
        coordinator._append_transaction = AsyncMock()

        changed = await coordinator._process_interest_for_account(
            loan,
            datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
        )

        self.assertTrue(changed)
        self.assertLess(loan.balance_minor, -10_000)
        self.assertGreater(loan.total_accrued_interest_micro_minor, 0)
        payout_call = coordinator._append_transaction.await_args_list[1]
        self.assertEqual(payout_call.kwargs["tx_type"], TX_INTEREST_PAYOUT)
        self.assertLess(payout_call.kwargs["amount_minor"], 0)

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
