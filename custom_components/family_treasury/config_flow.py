"""Config flow for Family Treasury."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_APPLY_DEFAULTS_TO_EXISTING,
    CONF_CURRENCY_CODE,
    CONF_DEFAULT_APR_PERCENT,
    CONF_INTEREST_CALC_FREQUENCY,
    CONF_INTEREST_PAYOUT_FREQUENCY,
    CONF_LOCALE,
    DEFAULT_APR_PERCENT,
    DEFAULT_CURRENCY_CODE,
    DEFAULT_INTEREST_CALC_FREQUENCY,
    DEFAULT_INTEREST_PAYOUT_FREQUENCY,
    DEFAULT_LOCALE,
    DOMAIN,
    FREQUENCIES,
)


def _validate_input(data: dict[str, Any]) -> dict[str, Any]:
    default_apr = str(data[CONF_DEFAULT_APR_PERCENT])
    if float(default_apr) < 0:
        raise ValueError("APR must be non-negative")

    calc_frequency = data[CONF_INTEREST_CALC_FREQUENCY]
    payout_frequency = data[CONF_INTEREST_PAYOUT_FREQUENCY]
    if calc_frequency not in FREQUENCIES or payout_frequency not in FREQUENCIES:
        raise ValueError("Invalid compounding frequency")

    currency_code = str(data[CONF_CURRENCY_CODE]).upper()
    if len(currency_code) != 3:
        raise ValueError("Currency code must be a 3-character ISO code")

    locale = str(data[CONF_LOCALE]).strip()
    if not locale:
        raise ValueError("Locale is required")

    return {
        CONF_DEFAULT_APR_PERCENT: default_apr,
        CONF_INTEREST_CALC_FREQUENCY: calc_frequency,
        CONF_INTEREST_PAYOUT_FREQUENCY: payout_frequency,
        CONF_CURRENCY_CODE: currency_code,
        CONF_LOCALE: locale,
    }


def _schema(values: dict[str, Any], *, include_apply_defaults: bool) -> vol.Schema:
    base: dict[Any, Any] = {
        vol.Required(
            CONF_DEFAULT_APR_PERCENT,
            default=str(values.get(CONF_DEFAULT_APR_PERCENT, DEFAULT_APR_PERCENT)),
        ): str,
        vol.Required(
            CONF_INTEREST_CALC_FREQUENCY,
            default=values.get(
                CONF_INTEREST_CALC_FREQUENCY,
                DEFAULT_INTEREST_CALC_FREQUENCY,
            ),
        ): vol.In(sorted(FREQUENCIES)),
        vol.Required(
            CONF_INTEREST_PAYOUT_FREQUENCY,
            default=values.get(
                CONF_INTEREST_PAYOUT_FREQUENCY,
                DEFAULT_INTEREST_PAYOUT_FREQUENCY,
            ),
        ): vol.In(sorted(FREQUENCIES)),
        vol.Required(
            CONF_CURRENCY_CODE,
            default=values.get(CONF_CURRENCY_CODE, DEFAULT_CURRENCY_CODE),
        ): str,
        vol.Required(
            CONF_LOCALE,
            default=values.get(CONF_LOCALE, DEFAULT_LOCALE),
        ): str,
    }

    if include_apply_defaults:
        base[
            vol.Required(
                CONF_APPLY_DEFAULTS_TO_EXISTING,
                default=values.get(CONF_APPLY_DEFAULTS_TO_EXISTING, False),
            )
        ] = bool

    return vol.Schema(base)


class FamilyTreasuryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Family Treasury."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle first setup step."""

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                validated = _validate_input(user_input)
            except ValueError:
                errors["base"] = "invalid_config"
            else:
                return self.async_create_entry(title="Family Treasury", data=validated)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema({}, include_apply_defaults=False),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "FamilyTreasuryOptionsFlow":
        """Get options flow."""

        return FamilyTreasuryOptionsFlow(config_entry)


class FamilyTreasuryOptionsFlow(config_entries.OptionsFlow):
    """Family Treasury options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""

        merged = dict(self._config_entry.data)
        merged.update(self._config_entry.options)

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                validated = _validate_input(user_input)
            except ValueError:
                errors["base"] = "invalid_config"
            else:
                apply_defaults = bool(user_input.get(CONF_APPLY_DEFAULTS_TO_EXISTING))
                if apply_defaults:
                    domain_data = self.hass.data.get(DOMAIN, {})
                    runtime_map = domain_data.get("runtime", {})
                    runtime = runtime_map.get(self._config_entry.entry_id)
                    if runtime is not None:
                        await runtime.coordinator.async_apply_defaults_to_existing_accounts(
                            default_apr_percent=validated[CONF_DEFAULT_APR_PERCENT],
                            calc_frequency=validated[CONF_INTEREST_CALC_FREQUENCY],
                            payout_frequency=validated[
                                CONF_INTEREST_PAYOUT_FREQUENCY
                            ],
                            currency_code=validated[CONF_CURRENCY_CODE],
                            locale=validated[CONF_LOCALE],
                        )

                return self.async_create_entry(title="", data=validated)

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(merged, include_apply_defaults=True),
            errors=errors,
        )
