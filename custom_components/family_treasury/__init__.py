"""The Family Treasury integration."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from inspect import isawaitable
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url, remove_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry

from .const import (
    DATA_FRONTEND_JS_ADDED,
    DATA_FRONTEND_RETRY_UNSUB,
    DATA_FRONTEND_STATIC_REGISTERED,
    DATA_RUNTIME,
    DATA_SERVICES_UNSUB,
    DOMAIN,
    FRONTEND_DIR,
    FRONTEND_TRANSACTIONS_CARD_FILENAME,
    FRONTEND_TRANSACTIONS_CARD_URL,
    PLATFORMS,
)
from .coordinator import FamilyTreasuryCoordinator
from .services import async_register_services
from .storage import FamilyTreasuryStorage


@dataclass(slots=True)
class FamilyTreasuryRuntime:
    """Runtime objects for a config entry."""

    storage: FamilyTreasuryStorage
    coordinator: FamilyTreasuryCoordinator


FamilyTreasuryConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: FamilyTreasuryConfigEntry) -> bool:
    """Set up Family Treasury from a config entry."""

    domain_data = hass.data.setdefault(DOMAIN, {})
    runtime_map: dict[str, FamilyTreasuryRuntime] = domain_data.setdefault(DATA_RUNTIME, {})

    storage = FamilyTreasuryStorage(hass)
    coordinator = FamilyTreasuryCoordinator(hass, entry, storage)
    await coordinator.async_initialize()

    runtime = FamilyTreasuryRuntime(storage=storage, coordinator=coordinator)
    runtime_map[entry.entry_id] = runtime
    entry.runtime_data = runtime

    await _async_setup_card_frontend(hass, domain_data)

    if DATA_SERVICES_UNSUB not in domain_data:
        domain_data[DATA_SERVICES_UNSUB] = async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FamilyTreasuryConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    domain_data = hass.data.get(DOMAIN, {})
    runtime_map: dict[str, FamilyTreasuryRuntime] = domain_data.get(DATA_RUNTIME, {})
    runtime = runtime_map.pop(entry.entry_id, None)
    if runtime is not None:
        await runtime.coordinator.async_shutdown()

    if not runtime_map:
        await _async_unload_card_frontend(hass, domain_data)

    if not runtime_map and DATA_SERVICES_UNSUB in domain_data:
        unsub = domain_data.pop(DATA_SERVICES_UNSUB)
        unsub()

    if not runtime_map:
        hass.data.pop(DOMAIN, None)

    return True


async def _async_update_listener(
    hass: HomeAssistant,
    entry: FamilyTreasuryConfigEntry,
) -> None:
    """Reload the integration when options change."""

    await hass.config_entries.async_reload(entry.entry_id)


async def _async_setup_card_frontend(
    hass: HomeAssistant, domain_data: dict[str, Any]
) -> None:
    await _async_ensure_card_static_path(hass, domain_data)

    needs_retry = False
    if not domain_data.get(DATA_FRONTEND_JS_ADDED):
        try:
            add_extra_js_url(hass, FRONTEND_TRANSACTIONS_CARD_URL)
        except KeyError:
            needs_retry = True
        else:
            domain_data[DATA_FRONTEND_JS_ADDED] = True

    if hass.data.get(LOVELACE_DATA) is None:
        needs_retry = True

    if needs_retry:
        _ensure_frontend_retry_listener(hass, domain_data)
    else:
        _clear_frontend_retry_listener(domain_data)


async def _async_unload_card_frontend(
    hass: HomeAssistant, domain_data: dict[str, Any]
) -> None:
    _clear_frontend_retry_listener(domain_data)

    if domain_data.pop(DATA_FRONTEND_JS_ADDED, False):
        with suppress(KeyError):
            remove_extra_js_url(hass, FRONTEND_TRANSACTIONS_CARD_URL)


async def _async_ensure_card_static_path(
    hass: HomeAssistant, domain_data: dict[str, Any]
) -> None:
    if domain_data.get(DATA_FRONTEND_STATIC_REGISTERED):
        return

    module_path = (
        Path(__file__).resolve().parent / FRONTEND_DIR / FRONTEND_TRANSACTIONS_CARD_FILENAME
    )
    result = hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                FRONTEND_TRANSACTIONS_CARD_URL,
                str(module_path),
                cache_headers=False,
            )
        ]
    )
    if isawaitable(result):
        await result
    domain_data[DATA_FRONTEND_STATIC_REGISTERED] = True


def _ensure_frontend_retry_listener(
    hass: HomeAssistant, domain_data: dict[str, Any]
) -> None:
    if DATA_FRONTEND_RETRY_UNSUB in domain_data:
        return

    @callback
    def _component_loaded(event: Event) -> None:
        component = event.data.get("component")
        if component not in {"frontend", "lovelace"}:
            return
        domain_data_now = hass.data.get(DOMAIN)
        if domain_data_now is None:
            return
        hass.async_create_task(_async_setup_card_frontend(hass, domain_data_now))

    domain_data[DATA_FRONTEND_RETRY_UNSUB] = hass.bus.async_listen(
        EVENT_COMPONENT_LOADED,
        _component_loaded,
    )


def _clear_frontend_retry_listener(domain_data: dict[str, Any]) -> None:
    unsub = domain_data.pop(DATA_FRONTEND_RETRY_UNSUB, None)
    if unsub is not None:
        unsub()
