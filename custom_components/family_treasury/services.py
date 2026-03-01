"""Service registration for Family Treasury."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ACCOUNT_ID,
    CONF_ACTIVE,
    CONF_AMOUNT,
    CONF_APR_PERCENT,
    CONF_CURRENCY_CODE,
    CONF_DESCRIPTION,
    CONF_DISPLAY_NAME,
    CONF_END,
    CONF_INITIAL_BALANCE,
    CONF_INTEREST_CALC_FREQUENCY,
    CONF_INTEREST_PAYOUT_FREQUENCY,
    CONF_LIMIT,
    CONF_LOCALE,
    CONF_OFFSET,
    CONF_START,
    CONF_TYPE,
    DATA_RUNTIME,
    DOMAIN,
    FREQUENCIES,
    MAX_TRANSACTION_QUERY_LIMIT,
    SERVICE_ADJUST_BALANCE,
    SERVICE_CREATE_ACCOUNT,
    SERVICE_DEPOSIT,
    SERVICE_GET_TRANSACTIONS,
    SERVICE_UPDATE_ACCOUNT,
    SERVICE_WITHDRAW,
    TX_TYPES,
)

AMOUNT_VALUE = vol.Any(str, int, float)

CREATE_ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT_ID): cv.slug,
        vol.Required(CONF_DISPLAY_NAME): cv.string,
        vol.Optional(CONF_INITIAL_BALANCE): AMOUNT_VALUE,
        vol.Optional(CONF_APR_PERCENT): AMOUNT_VALUE,
        vol.Optional(CONF_INTEREST_CALC_FREQUENCY): vol.In(sorted(FREQUENCIES)),
        vol.Optional(CONF_INTEREST_PAYOUT_FREQUENCY): vol.In(sorted(FREQUENCIES)),
        vol.Optional(CONF_CURRENCY_CODE): cv.string,
        vol.Optional(CONF_LOCALE): cv.string,
    }
)

UPDATE_ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT_ID): cv.slug,
        vol.Optional(CONF_DISPLAY_NAME): cv.string,
        vol.Optional(CONF_ACTIVE): cv.boolean,
        vol.Optional(CONF_APR_PERCENT): AMOUNT_VALUE,
        vol.Optional(CONF_INTEREST_CALC_FREQUENCY): vol.In(sorted(FREQUENCIES)),
        vol.Optional(CONF_INTEREST_PAYOUT_FREQUENCY): vol.In(sorted(FREQUENCIES)),
        vol.Optional(CONF_CURRENCY_CODE): cv.string,
        vol.Optional(CONF_LOCALE): cv.string,
    }
)

BALANCE_CHANGE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT_ID): cv.slug,
        vol.Required(CONF_AMOUNT): AMOUNT_VALUE,
        vol.Optional(CONF_DESCRIPTION, default=""): cv.string,
    }
)

GET_TRANSACTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ACCOUNT_ID): cv.slug,
        vol.Optional(CONF_START): vol.Any(cv.datetime, cv.string),
        vol.Optional(CONF_END): vol.Any(cv.datetime, cv.string),
        vol.Optional(CONF_TYPE): vol.In(sorted(TX_TYPES)),
        vol.Optional(CONF_LIMIT, default=100): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_TRANSACTION_QUERY_LIMIT)
        ),
        vol.Optional(CONF_OFFSET, default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)


def async_register_services(hass: HomeAssistant) -> Callable[[], None]:
    """Register all integration services."""

    async def handle_create_account(call: ServiceCall) -> None:
        coordinator = _default_coordinator(hass)
        payload = dict(call.data)

        try:
            await coordinator.async_create_account(payload)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_update_account(call: ServiceCall) -> None:
        coordinator = _default_coordinator(hass)
        payload = dict(call.data)

        if len(payload) <= 1:
            raise HomeAssistantError("No updates provided for account")

        try:
            await coordinator.async_update_account(payload)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_deposit(call: ServiceCall) -> None:
        coordinator = _default_coordinator(hass)
        try:
            await coordinator.async_deposit(
                account_id=call.data[CONF_ACCOUNT_ID],
                amount=call.data[CONF_AMOUNT],
                description=call.data.get(CONF_DESCRIPTION, ""),
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_withdraw(call: ServiceCall) -> None:
        coordinator = _default_coordinator(hass)
        try:
            await coordinator.async_withdraw(
                account_id=call.data[CONF_ACCOUNT_ID],
                amount=call.data[CONF_AMOUNT],
                description=call.data.get(CONF_DESCRIPTION, ""),
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_adjust(call: ServiceCall) -> None:
        coordinator = _default_coordinator(hass)
        try:
            await coordinator.async_adjust_balance(
                account_id=call.data[CONF_ACCOUNT_ID],
                amount=call.data[CONF_AMOUNT],
                description=call.data.get(CONF_DESCRIPTION, ""),
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_get_transactions(call: ServiceCall) -> ServiceResponse:
        coordinator = _default_coordinator(hass)
        payload: dict[str, Any] = dict(call.data)

        try:
            return await coordinator.async_get_transactions(payload)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_ACCOUNT,
        handle_create_account,
        schema=CREATE_ACCOUNT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_ACCOUNT,
        handle_update_account,
        schema=UPDATE_ACCOUNT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DEPOSIT,
        handle_deposit,
        schema=BALANCE_CHANGE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_WITHDRAW,
        handle_withdraw,
        schema=BALANCE_CHANGE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADJUST_BALANCE,
        handle_adjust,
        schema=BALANCE_CHANGE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TRANSACTIONS,
        handle_get_transactions,
        schema=GET_TRANSACTIONS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    def _async_unregister_services() -> None:
        for service in (
            SERVICE_CREATE_ACCOUNT,
            SERVICE_UPDATE_ACCOUNT,
            SERVICE_DEPOSIT,
            SERVICE_WITHDRAW,
            SERVICE_ADJUST_BALANCE,
            SERVICE_GET_TRANSACTIONS,
        ):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)

    return _async_unregister_services


def _default_coordinator(hass: HomeAssistant):
    domain_data = hass.data.get(DOMAIN, {})
    runtime_map = domain_data.get(DATA_RUNTIME, {})
    if not runtime_map:
        raise HomeAssistantError("Family Treasury is not initialized")

    first_runtime = next(iter(runtime_map.values()))
    return first_runtime.coordinator
