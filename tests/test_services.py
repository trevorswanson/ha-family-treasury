"""Tests for service registration and handlers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import voluptuous as vol

HA_AVAILABLE = True
try:
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.family_treasury.const import (
        CONF_ACCOUNT_ID,
        CONF_AMOUNT,
        CONF_DESCRIPTION,
        CONF_TYPE,
        DATA_RUNTIME,
        DOMAIN,
        SERVICE_ADJUST_BALANCE,
        SERVICE_CREATE_ACCOUNT,
        SERVICE_DEPOSIT,
        SERVICE_GET_TRANSACTIONS,
        SERVICE_UPDATE_ACCOUNT,
        SERVICE_WITHDRAW,
    )
    from custom_components.family_treasury.services import (
        _default_coordinator,
        async_register_services,
    )
except ModuleNotFoundError:
    HA_AVAILABLE = False


class _ServiceRegistry:
    def __init__(self) -> None:
        self._handlers = {}

    def async_register(self, domain, service, handler, schema=None, supports_response=None):
        self._handlers[(domain, service)] = {
            "handler": handler,
            "schema": schema,
            "supports_response": supports_response,
        }

    def has_service(self, domain, service):
        return (domain, service) in self._handlers

    def async_remove(self, domain, service):
        self._handlers.pop((domain, service), None)


@unittest.skipUnless(HA_AVAILABLE, "homeassistant is not installed in this environment")
class TestServices(unittest.IsolatedAsyncioTestCase):
    """Service registration tests."""

    def _build_hass(self):
        coordinator = SimpleNamespace(
            async_create_account=AsyncMock(),
            async_update_account=AsyncMock(),
            async_deposit=AsyncMock(),
            async_withdraw=AsyncMock(),
            async_adjust_balance=AsyncMock(),
            async_get_transactions=AsyncMock(return_value={"transactions": []}),
        )
        registry = _ServiceRegistry()
        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    DATA_RUNTIME: {"entry-1": SimpleNamespace(coordinator=coordinator)}
                }
            },
            services=registry,
        )
        return hass, coordinator, registry

    async def test_register_and_unregister_services(self) -> None:
        hass, _coordinator, registry = self._build_hass()

        unregister = async_register_services(hass)

        for service in (
            SERVICE_CREATE_ACCOUNT,
            SERVICE_UPDATE_ACCOUNT,
            SERVICE_DEPOSIT,
            SERVICE_WITHDRAW,
            SERVICE_ADJUST_BALANCE,
            SERVICE_GET_TRANSACTIONS,
        ):
            self.assertTrue(registry.has_service(DOMAIN, service))

        unregister()

        for service in (
            SERVICE_CREATE_ACCOUNT,
            SERVICE_UPDATE_ACCOUNT,
            SERVICE_DEPOSIT,
            SERVICE_WITHDRAW,
            SERVICE_ADJUST_BALANCE,
            SERVICE_GET_TRANSACTIONS,
        ):
            self.assertFalse(registry.has_service(DOMAIN, service))

    async def test_handlers_call_coordinator(self) -> None:
        hass, coordinator, registry = self._build_hass()
        async_register_services(hass)

        await registry._handlers[(DOMAIN, SERVICE_DEPOSIT)]["handler"](
            SimpleNamespace(
                data={
                    CONF_ACCOUNT_ID: "emma",
                    CONF_AMOUNT: "1.00",
                    CONF_DESCRIPTION: "reward",
                }
            )
        )
        coordinator.async_deposit.assert_awaited_once_with(
            account_id="emma",
            amount="1.00",
            description="reward",
        )

        await registry._handlers[(DOMAIN, SERVICE_WITHDRAW)]["handler"](
            SimpleNamespace(data={CONF_ACCOUNT_ID: "emma", CONF_AMOUNT: "0.25"})
        )
        coordinator.async_withdraw.assert_awaited_once()

        await registry._handlers[(DOMAIN, SERVICE_ADJUST_BALANCE)]["handler"](
            SimpleNamespace(data={CONF_ACCOUNT_ID: "emma", CONF_AMOUNT: "-0.10"})
        )
        coordinator.async_adjust_balance.assert_awaited_once()

        await registry._handlers[(DOMAIN, SERVICE_CREATE_ACCOUNT)]["handler"](
            SimpleNamespace(data={"account_id": "emma", "display_name": "Emma"})
        )
        coordinator.async_create_account.assert_awaited_once()

    async def test_update_account_requires_fields(self) -> None:
        hass, _coordinator, registry = self._build_hass()
        async_register_services(hass)

        with self.assertRaises(HomeAssistantError):
            await registry._handlers[(DOMAIN, SERVICE_UPDATE_ACCOUNT)]["handler"](
                SimpleNamespace(data={"account_id": "emma"})
            )

    async def test_get_transactions_returns_payload(self) -> None:
        hass, coordinator, registry = self._build_hass()
        coordinator.async_get_transactions = AsyncMock(
            return_value={"transactions": [{"tx_id": 1}]}
        )
        async_register_services(hass)

        response = await registry._handlers[(DOMAIN, SERVICE_GET_TRANSACTIONS)][
            "handler"
        ](SimpleNamespace(data={CONF_ACCOUNT_ID: "emma"}))

        self.assertEqual(response, {"transactions": [{"tx_id": 1}]})

    async def test_get_transactions_schema_accepts_multi_type(self) -> None:
        hass, _coordinator, registry = self._build_hass()
        async_register_services(hass)

        schema = registry._handlers[(DOMAIN, SERVICE_GET_TRANSACTIONS)]["schema"]
        validated_single = schema({CONF_TYPE: "deposit"})
        self.assertEqual(validated_single[CONF_TYPE], "deposit")

        validated_multi = schema({CONF_TYPE: ["deposit", "withdraw"]})
        self.assertEqual(validated_multi[CONF_TYPE], ["deposit", "withdraw"])

        with self.assertRaises(vol.Invalid):
            schema({CONF_TYPE: ["deposit", "unknown"]})

    async def test_value_error_is_wrapped_as_homeassistant_error(self) -> None:
        hass, coordinator, registry = self._build_hass()
        coordinator.async_deposit = AsyncMock(side_effect=ValueError("bad amount"))
        async_register_services(hass)

        with self.assertRaises(HomeAssistantError):
            await registry._handlers[(DOMAIN, SERVICE_DEPOSIT)]["handler"](
                SimpleNamespace(data={CONF_ACCOUNT_ID: "emma", CONF_AMOUNT: "1.00"})
            )

    async def test_default_coordinator_missing_runtime_raises(self) -> None:
        hass = SimpleNamespace(data={DOMAIN: {DATA_RUNTIME: {}}})

        with self.assertRaises(HomeAssistantError):
            _default_coordinator(hass)


if __name__ == "__main__":
    unittest.main()
