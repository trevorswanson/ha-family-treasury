"""Tests for integration setup, frontend resource registration, and teardown."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

HA_AVAILABLE = True
try:
    from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
    from homeassistant.const import CONF_ID, CONF_TYPE, CONF_URL

    import custom_components.family_treasury as integration
    from custom_components.family_treasury.const import (
        DATA_FRONTEND_RESOURCE_MANAGED,
        DATA_FRONTEND_STATIC_REGISTERED,
        DATA_RUNTIME,
        DATA_SERVICES_UNSUB,
        DOMAIN,
        FRONTEND_TRANSACTIONS_CARD_URL,
    )
except ModuleNotFoundError:
    HA_AVAILABLE = False


class _ResourceCollectionStub:
    def __init__(self, items: list[dict] | None = None) -> None:
        self._items = items or []
        self.async_load = AsyncMock()
        self.async_create_item = AsyncMock(side_effect=self._create_item)
        self.async_update_item = AsyncMock(side_effect=self._update_item)
        self.async_delete_item = AsyncMock(side_effect=self._delete_item)

    def async_items(self) -> list[dict]:
        return [dict(item) for item in self._items]

    async def _create_item(self, data: dict) -> dict:
        item = {
            CONF_ID: f"resource-{len(self._items) + 1}",
            CONF_URL: data[CONF_URL],
            CONF_TYPE: data["res_type"],
        }
        self._items.append(item)
        return dict(item)

    async def _update_item(self, item_id: str, updates: dict) -> dict:
        for item in self._items:
            if item[CONF_ID] == item_id:
                if "res_type" in updates:
                    item[CONF_TYPE] = updates["res_type"]
                if CONF_URL in updates:
                    item[CONF_URL] = updates[CONF_URL]
                return dict(item)
        raise KeyError(item_id)

    async def _delete_item(self, item_id: str) -> None:
        before = len(self._items)
        self._items = [item for item in self._items if item[CONF_ID] != item_id]
        if len(self._items) == before:
            raise KeyError(item_id)


@unittest.skipUnless(HA_AVAILABLE, "homeassistant is not installed in this environment")
class TestInit(unittest.IsolatedAsyncioTestCase):
    """Setup and unload behavior tests."""

    def _build_hass(self, resources: _ResourceCollectionStub) -> SimpleNamespace:
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
                LOVELACE_DATA: SimpleNamespace(
                    resource_mode=MODE_STORAGE,
                    resources=resources,
                )
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

    async def test_setup_and_unload_registers_frontend_and_owned_resource(self) -> None:
        resources = _ResourceCollectionStub()
        hass = self._build_hass(resources)
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

            add_js.assert_called_once_with(hass, FRONTEND_TRANSACTIONS_CARD_URL)
            self.assertEqual(resources.async_create_item.await_count, 1)
            self.assertEqual(resources.async_delete_item.await_count, 0)

            domain_data = hass.data[DOMAIN]
            self.assertTrue(domain_data[DATA_FRONTEND_STATIC_REGISTERED])
            self.assertTrue(domain_data[DATA_FRONTEND_RESOURCE_MANAGED])
            self.assertIn(DATA_RUNTIME, domain_data)
            self.assertIn(DATA_SERVICES_UNSUB, domain_data)

            unload_ok = await integration.async_unload_entry(hass, entry)
            self.assertTrue(unload_ok)
            remove_js.assert_called_once_with(hass, FRONTEND_TRANSACTIONS_CARD_URL)
            self.assertEqual(resources.async_delete_item.await_count, 1)
            unregister.assert_called_once()
            self.assertNotIn(DOMAIN, hass.data)

    async def test_setup_reuses_existing_resource_and_updates_type(self) -> None:
        resources = _ResourceCollectionStub(
            items=[
                {
                    CONF_ID: "existing",
                    CONF_URL: FRONTEND_TRANSACTIONS_CARD_URL,
                    CONF_TYPE: "js",
                }
            ]
        )
        hass = self._build_hass(resources)
        domain_data: dict = {}

        with patch("custom_components.family_treasury.add_extra_js_url") as add_js:
            await integration._async_setup_card_frontend(hass, domain_data)
            await integration._async_setup_card_frontend(hass, domain_data)

        self.assertEqual(add_js.call_count, 1)
        self.assertEqual(hass.http.async_register_static_paths.call_count, 1)
        self.assertEqual(resources.async_create_item.await_count, 0)
        self.assertEqual(resources.async_update_item.await_count, 1)
        self.assertFalse(domain_data[DATA_FRONTEND_RESOURCE_MANAGED])

    async def test_setup_supports_async_static_path_registration(self) -> None:
        resources = _ResourceCollectionStub()
        hass = self._build_hass(resources)
        hass.http.async_register_static_paths = AsyncMock()
        domain_data: dict = {}

        with patch("custom_components.family_treasury.add_extra_js_url"):
            await integration._async_setup_card_frontend(hass, domain_data)

        hass.http.async_register_static_paths.assert_awaited_once()
        self.assertTrue(domain_data[DATA_FRONTEND_STATIC_REGISTERED])

    async def test_setup_adds_retry_listener_when_frontend_not_ready(self) -> None:
        resources = _ResourceCollectionStub()
        hass = self._build_hass(resources)
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
