"""Tests for Family Treasury config flow helpers and flows."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

HA_AVAILABLE = True
try:
    from custom_components.family_treasury.config_flow import (
        FamilyTreasuryConfigFlow,
        FamilyTreasuryOptionsFlow,
        _schema,
        _validate_input,
    )
    from custom_components.family_treasury.const import (
        CONF_APPLY_DEFAULTS_TO_EXISTING,
        CONF_CURRENCY_CODE,
        CONF_DEFAULT_APR_PERCENT,
        CONF_INTEREST_CALC_FREQUENCY,
        CONF_INTEREST_PAYOUT_FREQUENCY,
        CONF_LOCALE,
        DOMAIN,
    )
except ModuleNotFoundError:
    HA_AVAILABLE = False


@unittest.skipUnless(HA_AVAILABLE, "homeassistant is not installed in this environment")
class TestConfigFlowHelpers(unittest.TestCase):
    """Tests for helper validation and schema behavior."""

    def test_validate_input_happy_path_normalizes_currency(self) -> None:
        validated = _validate_input(
            {
                CONF_DEFAULT_APR_PERCENT: "3.5",
                CONF_INTEREST_CALC_FREQUENCY: "daily",
                CONF_INTEREST_PAYOUT_FREQUENCY: "monthly",
                CONF_CURRENCY_CODE: "usd",
                CONF_LOCALE: "en_US",
            }
        )

        self.assertEqual(validated[CONF_CURRENCY_CODE], "USD")
        self.assertEqual(validated[CONF_DEFAULT_APR_PERCENT], "3.5")

    def test_validate_input_rejects_negative_apr(self) -> None:
        with self.assertRaises(ValueError):
            _validate_input(
                {
                    CONF_DEFAULT_APR_PERCENT: "-0.01",
                    CONF_INTEREST_CALC_FREQUENCY: "daily",
                    CONF_INTEREST_PAYOUT_FREQUENCY: "monthly",
                    CONF_CURRENCY_CODE: "USD",
                    CONF_LOCALE: "en_US",
                }
            )

    def test_validate_input_rejects_invalid_frequency(self) -> None:
        with self.assertRaises(ValueError):
            _validate_input(
                {
                    CONF_DEFAULT_APR_PERCENT: "1",
                    CONF_INTEREST_CALC_FREQUENCY: "hourly",
                    CONF_INTEREST_PAYOUT_FREQUENCY: "monthly",
                    CONF_CURRENCY_CODE: "USD",
                    CONF_LOCALE: "en_US",
                }
            )

    def test_validate_input_rejects_currency_length(self) -> None:
        with self.assertRaises(ValueError):
            _validate_input(
                {
                    CONF_DEFAULT_APR_PERCENT: "1",
                    CONF_INTEREST_CALC_FREQUENCY: "daily",
                    CONF_INTEREST_PAYOUT_FREQUENCY: "monthly",
                    CONF_CURRENCY_CODE: "US",
                    CONF_LOCALE: "en_US",
                }
            )

    def test_validate_input_rejects_blank_locale(self) -> None:
        with self.assertRaises(ValueError):
            _validate_input(
                {
                    CONF_DEFAULT_APR_PERCENT: "1",
                    CONF_INTEREST_CALC_FREQUENCY: "daily",
                    CONF_INTEREST_PAYOUT_FREQUENCY: "monthly",
                    CONF_CURRENCY_CODE: "USD",
                    CONF_LOCALE: "   ",
                }
            )

    def test_schema_includes_apply_defaults_when_requested(self) -> None:
        schema = _schema({}, include_apply_defaults=True)
        parsed = schema({})
        self.assertIn(CONF_APPLY_DEFAULTS_TO_EXISTING, parsed)

    def test_schema_excludes_apply_defaults_when_not_requested(self) -> None:
        schema = _schema({}, include_apply_defaults=False)
        parsed = schema({})
        self.assertNotIn(CONF_APPLY_DEFAULTS_TO_EXISTING, parsed)


@unittest.skipUnless(HA_AVAILABLE, "homeassistant is not installed in this environment")
class TestConfigFlowBehavior(unittest.IsolatedAsyncioTestCase):
    """Tests for config and options flow behavior."""

    async def test_user_step_aborts_when_entry_exists(self) -> None:
        flow = FamilyTreasuryConfigFlow()
        flow._async_current_entries = lambda: [object()]

        result = await flow.async_step_user()

        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["reason"], "single_instance_allowed")

    async def test_user_step_returns_error_on_invalid_input(self) -> None:
        flow = FamilyTreasuryConfigFlow()
        flow._async_current_entries = lambda: []

        result = await flow.async_step_user(
            {
                CONF_DEFAULT_APR_PERCENT: "-1",
                CONF_INTEREST_CALC_FREQUENCY: "daily",
                CONF_INTEREST_PAYOUT_FREQUENCY: "monthly",
                CONF_CURRENCY_CODE: "USD",
                CONF_LOCALE: "en_US",
            }
        )

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"].get("base"), "invalid_config")

    async def test_user_step_creates_entry_on_valid_input(self) -> None:
        flow = FamilyTreasuryConfigFlow()
        flow._async_current_entries = lambda: []

        result = await flow.async_step_user(
            {
                CONF_DEFAULT_APR_PERCENT: "1.2",
                CONF_INTEREST_CALC_FREQUENCY: "daily",
                CONF_INTEREST_PAYOUT_FREQUENCY: "monthly",
                CONF_CURRENCY_CODE: "usd",
                CONF_LOCALE: "en_US",
            }
        )

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"][CONF_CURRENCY_CODE], "USD")

    async def test_options_flow_init_shows_form(self) -> None:
        config_entry = SimpleNamespace(data={}, options={}, entry_id="entry-1")
        flow = FamilyTreasuryOptionsFlow(config_entry)

        result = await flow.async_step_init()

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "init")

    async def test_options_flow_create_entry_without_apply_defaults(self) -> None:
        config_entry = SimpleNamespace(data={}, options={}, entry_id="entry-1")
        flow = FamilyTreasuryOptionsFlow(config_entry)
        flow.hass = SimpleNamespace(data={DOMAIN: {"runtime": {}}})

        result = await flow.async_step_init(
            {
                CONF_DEFAULT_APR_PERCENT: "2.5",
                CONF_INTEREST_CALC_FREQUENCY: "daily",
                CONF_INTEREST_PAYOUT_FREQUENCY: "weekly",
                CONF_CURRENCY_CODE: "USD",
                CONF_LOCALE: "en_US",
                CONF_APPLY_DEFAULTS_TO_EXISTING: False,
            }
        )

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"][CONF_INTEREST_PAYOUT_FREQUENCY], "weekly")

    async def test_options_flow_applies_defaults_when_requested(self) -> None:
        apply_mock = AsyncMock()
        runtime = SimpleNamespace(
            coordinator=SimpleNamespace(
                async_apply_defaults_to_existing_accounts=apply_mock,
            )
        )
        config_entry = SimpleNamespace(data={}, options={}, entry_id="entry-1")
        flow = FamilyTreasuryOptionsFlow(config_entry)
        flow.hass = SimpleNamespace(data={DOMAIN: {"runtime": {"entry-1": runtime}}})

        result = await flow.async_step_init(
            {
                CONF_DEFAULT_APR_PERCENT: "2.5",
                CONF_INTEREST_CALC_FREQUENCY: "daily",
                CONF_INTEREST_PAYOUT_FREQUENCY: "weekly",
                CONF_CURRENCY_CODE: "USD",
                CONF_LOCALE: "en_US",
                CONF_APPLY_DEFAULTS_TO_EXISTING: True,
            }
        )

        self.assertEqual(result["type"], "create_entry")
        apply_mock.assert_awaited_once()

    def test_get_options_flow_returns_expected_class(self) -> None:
        config_entry = SimpleNamespace(data={}, options={}, entry_id="entry-1")
        options_flow = FamilyTreasuryConfigFlow.async_get_options_flow(config_entry)

        self.assertIsInstance(options_flow, FamilyTreasuryOptionsFlow)


if __name__ == "__main__":
    unittest.main()
