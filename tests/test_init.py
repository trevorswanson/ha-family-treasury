"""Tests for integration setup, frontend loading, and teardown."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

HA_AVAILABLE = True
try:
    from homeassistant.components.lovelace.const import LOVELACE_DATA

    import custom_components.family_treasury as integration
    from custom_components.family_treasury.const import (
        DATA_FRONTEND_STATIC_REGISTERED,
        DATA_RUNTIME,
        DATA_SERVICES_UNSUB,
        DOMAIN,
        FRONTEND_ACCOUNT_SUMMARY_CARD_URL,
        FRONTEND_CARD_MODULES,
        FRONTEND_TRANSACTIONS_CARD_URL,
    )
except ModuleNotFoundError:
    HA_AVAILABLE = False


@unittest.skipUnless(HA_AVAILABLE, "homeassistant is not installed in this environment")
class TestInit(unittest.IsolatedAsyncioTestCase):
    """Setup and unload behavior tests."""

    def _build_hass(self) -> SimpleNamespace:
        config_entries = SimpleNamespace(
            async_forward_entry_setups=AsyncMock(),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(),
        )
        bus = SimpleNamespace(
            async_listen=MagicMock(return_value=lambda: None),
        )
        hass = SimpleNamespace(
            data={
                LOVELACE_DATA: SimpleNamespace(),
            },
            http=SimpleNamespace(async_register_static_paths=MagicMock()),
            config_entries=config_entries,
            bus=bus,
            async_create_task=MagicMock(),
        )
        return hass

    def _build_entry(self, entry_id: str = "entry-1") -> SimpleNamespace:
        return SimpleNamespace(
            entry_id=entry_id,
            data={},
            options={},
            runtime_data=None,
            async_on_unload=MagicMock(),
            add_update_listener=MagicMock(return_value=lambda: None),
        )

    async def test_setup_and_unload_registers_frontend(self) -> None:
        hass = self._build_hass()
        entry = self._build_entry()

        coordinator = SimpleNamespace(
            async_initialize=AsyncMock(),
            async_shutdown=AsyncMock(),
        )
        storage = object()
        unregister = MagicMock()

        with patch(
            "custom_components.family_treasury.FamilyTreasuryStorage",
            return_value=storage,
        ), patch(
            "custom_components.family_treasury.FamilyTreasuryCoordinator",
            return_value=coordinator,
        ), patch(
            "custom_components.family_treasury.async_register_services",
            return_value=unregister,
        ), patch(
            "custom_components.family_treasury.add_extra_js_url",
        ) as add_js, patch(
            "custom_components.family_treasury.remove_extra_js_url",
        ) as remove_js:
            setup_ok = await integration.async_setup_entry(hass, entry)
            self.assertTrue(setup_ok)

            self.assertEqual(
                add_js.call_args_list,
                [
                    call(hass, FRONTEND_TRANSACTIONS_CARD_URL),
                    call(hass, FRONTEND_ACCOUNT_SUMMARY_CARD_URL),
                ],
            )

            domain_data = hass.data[DOMAIN]
            self.assertTrue(domain_data[DATA_FRONTEND_STATIC_REGISTERED])
            self.assertIn(DATA_RUNTIME, domain_data)
            self.assertIn(DATA_SERVICES_UNSUB, domain_data)

            unload_ok = await integration.async_unload_entry(hass, entry)
            self.assertTrue(unload_ok)
            remove_js.assert_has_calls(
                [
                    call(hass, FRONTEND_TRANSACTIONS_CARD_URL),
                    call(hass, FRONTEND_ACCOUNT_SUMMARY_CARD_URL),
                ],
                any_order=True,
            )
            unregister.assert_called_once()
            self.assertNotIn(DOMAIN, hass.data)

    async def test_setup_only_adds_script_once(self) -> None:
        hass = self._build_hass()
        domain_data: dict = {}

        with patch("custom_components.family_treasury.add_extra_js_url") as add_js:
            await integration._async_setup_card_frontend(hass, domain_data)
            await integration._async_setup_card_frontend(hass, domain_data)

        self.assertEqual(add_js.call_count, len(FRONTEND_CARD_MODULES))
        self.assertEqual(hass.http.async_register_static_paths.call_count, 1)

    async def test_setup_supports_async_static_path_registration(self) -> None:
        hass = self._build_hass()
        hass.http.async_register_static_paths = AsyncMock()
        domain_data: dict = {}

        with patch("custom_components.family_treasury.add_extra_js_url"):
            await integration._async_setup_card_frontend(hass, domain_data)

        hass.http.async_register_static_paths.assert_awaited_once()
        self.assertTrue(domain_data[DATA_FRONTEND_STATIC_REGISTERED])

    async def test_setup_adds_retry_listener_when_frontend_not_ready(self) -> None:
        hass = self._build_hass()
        hass.data.pop(LOVELACE_DATA)
        domain_data: dict = {}

        with patch(
            "custom_components.family_treasury.add_extra_js_url",
            side_effect=KeyError("frontend"),
        ):
            await integration._async_setup_card_frontend(hass, domain_data)

        hass.bus.async_listen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
