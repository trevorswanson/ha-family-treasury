"""Tests for sensor entities and setup wiring."""

from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

HA_AVAILABLE = True
try:
    from homeassistant.components.sensor import SensorDeviceClass

    from custom_components.family_treasury.models import AccountRecord
    from custom_components.family_treasury.sensor import (
        FamilyTreasuryBalanceSensor,
        FamilyTreasuryPendingInterestSensor,
        async_setup_entry,
    )
except ModuleNotFoundError:
    HA_AVAILABLE = False


class _CoordinatorStub:
    def __init__(self) -> None:
        self._accounts = {
            "emma": AccountRecord(
                account_id="emma",
                display_name="Emma",
                active=True,
                currency_code="USD",
            )
        }
        self._states = {
            "emma": {
                "account_id": "emma",
                "display_name": "Emma",
                "currency_code": "USD",
                "locale": "en_US",
                "last_interest_calc_at": "2026-02-01T00:00:00+00:00",
                "last_interest_payout_at": "2026-02-01T00:00:00+00:00",
                "recent_transactions": [{"tx_id": 1}],
                "formatted_balance": "$10.00",
                "formatted_pending_interest": "$0.05",
                "balance_major": Decimal("10.00"),
                "pending_interest_major": Decimal("0.05"),
            }
        }

    def account(self, account_id):
        return self._accounts.get(account_id)

    def account_state(self, account_id):
        return self._states.get(account_id)

    def list_account_ids(self):
        return sorted(self._accounts)


@unittest.skipUnless(HA_AVAILABLE, "homeassistant is not installed in this environment")
class TestSensors(unittest.IsolatedAsyncioTestCase):
    """Sensor behavior tests."""

    async def test_balance_sensor_properties(self) -> None:
        coordinator = _CoordinatorStub()
        sensor = object.__new__(FamilyTreasuryBalanceSensor)
        sensor.coordinator = coordinator
        sensor._account_id = "emma"
        sensor._entry = SimpleNamespace(entry_id="entry-1")

        self.assertTrue(sensor.available)
        self.assertEqual(sensor.name, "Emma Balance")
        self.assertEqual(sensor.native_value, Decimal("10.00"))
        self.assertEqual(sensor.native_unit_of_measurement, "USD")
        self.assertEqual(sensor.device_class, SensorDeviceClass.MONETARY)
        self.assertEqual(sensor.suggested_display_precision, 2)
        self.assertIn("formatted_balance", sensor.extra_state_attributes)

    async def test_pending_interest_sensor_properties(self) -> None:
        coordinator = _CoordinatorStub()
        sensor = object.__new__(FamilyTreasuryPendingInterestSensor)
        sensor.coordinator = coordinator
        sensor._account_id = "emma"
        sensor._entry = SimpleNamespace(entry_id="entry-1")

        self.assertEqual(sensor.name, "Emma Pending Interest")
        self.assertEqual(sensor.native_value, Decimal("0.05"))

    async def test_sensor_unavailable_when_account_missing_or_inactive(self) -> None:
        coordinator = _CoordinatorStub()
        coordinator._accounts["emma"].active = False

        sensor = object.__new__(FamilyTreasuryBalanceSensor)
        sensor.coordinator = coordinator
        sensor._account_id = "emma"
        sensor._entry = SimpleNamespace(entry_id="entry-1")

        self.assertFalse(sensor.available)

        sensor_missing = object.__new__(FamilyTreasuryBalanceSensor)
        sensor_missing.coordinator = coordinator
        sensor_missing._account_id = "missing"
        sensor_missing._entry = SimpleNamespace(entry_id="entry-1")

        self.assertFalse(sensor_missing.available)
        self.assertIsNone(sensor_missing.native_value)
        self.assertIsNone(sensor_missing.native_unit_of_measurement)
        self.assertIsNone(sensor_missing.suggested_display_precision)
        self.assertIsNone(sensor_missing.extra_state_attributes)

    async def test_precision_matches_currency_exponent(self) -> None:
        coordinator = _CoordinatorStub()
        coordinator._accounts["emma"].currency_code = "ISK"

        sensor = object.__new__(FamilyTreasuryBalanceSensor)
        sensor.coordinator = coordinator
        sensor._account_id = "emma"
        sensor._entry = SimpleNamespace(entry_id="entry-1")

        self.assertEqual(sensor.suggested_display_precision, 0)

    async def test_async_setup_entry_adds_new_entities_on_signal(self) -> None:
        coordinator = _CoordinatorStub()
        runtime = SimpleNamespace(coordinator=coordinator)
        entry = SimpleNamespace(runtime_data=runtime)
        entry.async_on_unload = MagicMock()

        added_entities = []

        def add_entities(entities):
            added_entities.extend(entities)

        captured_callback = {"fn": None}

        def fake_dispatcher_connect(_hass, _signal, fn):
            captured_callback["fn"] = fn
            return lambda: None

        with patch(
            "custom_components.family_treasury.sensor.async_dispatcher_connect",
            side_effect=fake_dispatcher_connect,
        ), patch(
            "custom_components.family_treasury.sensor.FamilyTreasuryBalanceSensor",
            side_effect=lambda _c, _e, account_id: f"balance:{account_id}",
        ), patch(
            "custom_components.family_treasury.sensor.FamilyTreasuryPendingInterestSensor",
            side_effect=lambda _c, _e, account_id: f"pending:{account_id}",
        ):
            await async_setup_entry(SimpleNamespace(), entry, add_entities)

            self.assertEqual(added_entities, ["balance:emma", "pending:emma"])

            coordinator._accounts["sam"] = AccountRecord(
                account_id="sam",
                display_name="Sam",
                currency_code="USD",
            )
            coordinator._states["sam"] = {
                "account_id": "sam",
                "display_name": "Sam",
                "currency_code": "USD",
                "locale": "en_US",
                "last_interest_calc_at": None,
                "last_interest_payout_at": None,
                "recent_transactions": [],
                "formatted_balance": "$0.00",
                "formatted_pending_interest": "$0.00",
                "balance_major": Decimal("0"),
                "pending_interest_major": Decimal("0"),
            }

            captured_callback["fn"]()

            self.assertEqual(
                added_entities,
                [
                    "balance:emma",
                    "pending:emma",
                    "balance:sam",
                    "pending:sam",
                ],
            )

        entry.async_on_unload.assert_called_once()


if __name__ == "__main__":
    unittest.main()
