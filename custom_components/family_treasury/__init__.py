"""The Family Treasury integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_RUNTIME, DATA_SERVICES_UNSUB, DOMAIN, PLATFORMS
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
