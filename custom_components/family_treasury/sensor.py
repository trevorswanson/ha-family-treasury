"""Sensor platform for Family Treasury."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ACCOUNT_TYPE_LOAN,
    ATTR_ACCOUNT_ID,
    ATTR_ACCOUNT_TYPE,
    ATTR_CURRENCY_CODE,
    ATTR_DISPLAY_NAME,
    ATTR_FORMATTED_BALANCE,
    ATTR_FORMATTED_PENDING_INTEREST,
    ATTR_LAST_INTEREST_CALC_AT,
    ATTR_LAST_INTEREST_PAYOUT_AT,
    ATTR_LOCALE,
    ATTR_NEXT_INTEREST_PAYOUT_AT,
    ATTR_PARENT_ACCOUNT_ID,
    ATTR_RECENT_TRANSACTIONS,
    SIGNAL_ACCOUNTS_UPDATED,
)
from .coordinator import FamilyTreasuryCoordinator
from .models import currency_minor_exponent


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Family Treasury sensors for a config entry."""

    runtime = entry.runtime_data
    coordinator: FamilyTreasuryCoordinator = runtime.coordinator

    known_accounts: set[str] = set()

    @callback
    def _async_add_missing_entities() -> None:
        new_entities: list[SensorEntity] = []
        for account_id in coordinator.list_account_ids():
            if account_id in known_accounts:
                continue
            known_accounts.add(account_id)
            account = coordinator.account(account_id)
            new_entities.append(FamilyTreasuryBalanceSensor(coordinator, entry, account_id))
            new_entities.append(
                FamilyTreasuryPendingInterestSensor(coordinator, entry, account_id)
            )
            if account is not None and account.account_type == ACCOUNT_TYPE_LOAN:
                new_entities.append(
                    FamilyTreasuryLoanPrincipalSensor(coordinator, entry, account_id)
                )
                new_entities.append(
                    FamilyTreasuryLoanOriginalPrincipalSensor(
                        coordinator, entry, account_id
                    )
                )
                new_entities.append(
                    FamilyTreasuryLoanTotalAccruedInterestSensor(
                        coordinator, entry, account_id
                    )
                )
                new_entities.append(
                    FamilyTreasuryLoanTotalBalanceSensor(coordinator, entry, account_id)
                )
                new_entities.append(
                    FamilyTreasuryLoanPayoffProgressSensor(coordinator, entry, account_id)
                )

        if new_entities:
            async_add_entities(new_entities)

    _async_add_missing_entities()

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_ACCOUNTS_UPDATED, _async_add_missing_entities)
    )


class FamilyTreasuryBaseSensor(CoordinatorEntity[FamilyTreasuryCoordinator], SensorEntity):
    """Base sensor for account-related state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FamilyTreasuryCoordinator,
        entry: ConfigEntry,
        account_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._account_id = account_id

    @property
    def available(self) -> bool:
        account = self.coordinator.account(self._account_id)
        return account is not None and account.active

    @property
    def suggested_display_precision(self) -> int | None:
        account = self.coordinator.account(self._account_id)
        if account is None:
            return None
        return currency_minor_exponent(account.currency_code)

    @property
    def native_unit_of_measurement(self) -> str | None:
        account = self.coordinator.account(self._account_id)
        if account is None:
            return None
        return account.currency_code

    @property
    def device_class(self) -> SensorDeviceClass | None:
        return SensorDeviceClass.MONETARY

    def _state_data(self) -> dict[str, Any] | None:
        return self.coordinator.account_state(self._account_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        state = self._state_data()
        if state is None:
            return None

        return {
            ATTR_ACCOUNT_ID: state[ATTR_ACCOUNT_ID],
            ATTR_ACCOUNT_TYPE: state[ATTR_ACCOUNT_TYPE],
            ATTR_PARENT_ACCOUNT_ID: state[ATTR_PARENT_ACCOUNT_ID],
            ATTR_DISPLAY_NAME: state[ATTR_DISPLAY_NAME],
            ATTR_CURRENCY_CODE: state[ATTR_CURRENCY_CODE],
            ATTR_LOCALE: state[ATTR_LOCALE],
            ATTR_LAST_INTEREST_CALC_AT: state[ATTR_LAST_INTEREST_CALC_AT],
            ATTR_LAST_INTEREST_PAYOUT_AT: state[ATTR_LAST_INTEREST_PAYOUT_AT],
            ATTR_NEXT_INTEREST_PAYOUT_AT: state[ATTR_NEXT_INTEREST_PAYOUT_AT],
            ATTR_RECENT_TRANSACTIONS: state[ATTR_RECENT_TRANSACTIONS],
            ATTR_FORMATTED_BALANCE: state[ATTR_FORMATTED_BALANCE],
            ATTR_FORMATTED_PENDING_INTEREST: state[ATTR_FORMATTED_PENDING_INTEREST],
        }


class FamilyTreasuryBalanceSensor(FamilyTreasuryBaseSensor):
    """Account balance sensor."""

    def __init__(
        self,
        coordinator: FamilyTreasuryCoordinator,
        entry: ConfigEntry,
        account_id: str,
    ) -> None:
        super().__init__(coordinator, entry, account_id)
        self._attr_unique_id = f"{entry.entry_id}_{account_id}_balance"

    @property
    def name(self) -> str:
        account = self.coordinator.account(self._account_id)
        if account is None:
            return f"{self._account_id} Balance"
        return f"{account.display_name} Balance"

    @property
    def native_value(self) -> Decimal | None:
        state = self._state_data()
        if state is None:
            return None
        return state["balance_major"]


class FamilyTreasuryPendingInterestSensor(FamilyTreasuryBaseSensor):
    """Pending interest sensor."""

    def __init__(
        self,
        coordinator: FamilyTreasuryCoordinator,
        entry: ConfigEntry,
        account_id: str,
    ) -> None:
        super().__init__(coordinator, entry, account_id)
        self._attr_unique_id = f"{entry.entry_id}_{account_id}_pending_interest"

    @property
    def name(self) -> str:
        account = self.coordinator.account(self._account_id)
        if account is None:
            return f"{self._account_id} Pending Interest"
        return f"{account.display_name} Pending Interest"

    @property
    def native_value(self) -> Decimal | None:
        state = self._state_data()
        if state is None:
            return None
        return state["pending_interest_major"]


class FamilyTreasuryLoanPrincipalSensor(FamilyTreasuryBaseSensor):
    """Outstanding loan principal sensor."""

    def __init__(
        self,
        coordinator: FamilyTreasuryCoordinator,
        entry: ConfigEntry,
        account_id: str,
    ) -> None:
        super().__init__(coordinator, entry, account_id)
        self._attr_unique_id = f"{entry.entry_id}_{account_id}_loan_principal"

    @property
    def name(self) -> str:
        account = self.coordinator.account(self._account_id)
        if account is None:
            return f"{self._account_id} Loan Principal"
        return f"{account.display_name} Loan Principal"

    @property
    def native_value(self) -> Decimal | None:
        state = self._state_data()
        if state is None:
            return None
        return state["loan_principal_major"]


class FamilyTreasuryLoanTotalAccruedInterestSensor(FamilyTreasuryBaseSensor):
    """Lifetime total accrued interest for a loan."""

    def __init__(
        self,
        coordinator: FamilyTreasuryCoordinator,
        entry: ConfigEntry,
        account_id: str,
    ) -> None:
        super().__init__(coordinator, entry, account_id)
        self._attr_unique_id = (
            f"{entry.entry_id}_{account_id}_loan_total_accrued_interest"
        )

    @property
    def name(self) -> str:
        account = self.coordinator.account(self._account_id)
        if account is None:
            return f"{self._account_id} Loan Total Accrued Interest"
        return f"{account.display_name} Loan Total Accrued Interest"

    @property
    def native_value(self) -> Decimal | None:
        state = self._state_data()
        if state is None:
            return None
        return state["loan_total_accrued_interest_major"]


class FamilyTreasuryLoanOriginalPrincipalSensor(FamilyTreasuryBaseSensor):
    """Original principal captured at loan creation."""

    def __init__(
        self,
        coordinator: FamilyTreasuryCoordinator,
        entry: ConfigEntry,
        account_id: str,
    ) -> None:
        super().__init__(coordinator, entry, account_id)
        self._attr_unique_id = f"{entry.entry_id}_{account_id}_loan_original_principal"

    @property
    def name(self) -> str:
        account = self.coordinator.account(self._account_id)
        if account is None:
            return f"{self._account_id} Loan Original Principal"
        return f"{account.display_name} Loan Original Principal"

    @property
    def native_value(self) -> Decimal | None:
        state = self._state_data()
        if state is None:
            return None
        return state["loan_original_principal_major"]


class FamilyTreasuryLoanTotalBalanceSensor(FamilyTreasuryBaseSensor):
    """Total loan debt including pending interest."""

    def __init__(
        self,
        coordinator: FamilyTreasuryCoordinator,
        entry: ConfigEntry,
        account_id: str,
    ) -> None:
        super().__init__(coordinator, entry, account_id)
        self._attr_unique_id = f"{entry.entry_id}_{account_id}_loan_total_balance"

    @property
    def name(self) -> str:
        account = self.coordinator.account(self._account_id)
        if account is None:
            return f"{self._account_id} Loan Total Balance"
        return f"{account.display_name} Loan Total Balance"

    @property
    def native_value(self) -> Decimal | None:
        state = self._state_data()
        if state is None:
            return None
        return state["loan_total_balance_major"]


class FamilyTreasuryLoanPayoffProgressSensor(FamilyTreasuryBaseSensor):
    """Percent progress toward full loan payoff."""

    def __init__(
        self,
        coordinator: FamilyTreasuryCoordinator,
        entry: ConfigEntry,
        account_id: str,
    ) -> None:
        super().__init__(coordinator, entry, account_id)
        self._attr_unique_id = f"{entry.entry_id}_{account_id}_loan_payoff_progress"

    @property
    def name(self) -> str:
        account = self.coordinator.account(self._account_id)
        if account is None:
            return f"{self._account_id} Loan Payoff Progress"
        return f"{account.display_name} Loan Payoff Progress"

    @property
    def native_value(self) -> Decimal | None:
        state = self._state_data()
        if state is None:
            return None
        return state["loan_payoff_progress_percent"]

    @property
    def native_unit_of_measurement(self) -> str | None:
        return "%"

    @property
    def device_class(self) -> SensorDeviceClass | None:
        return None

    @property
    def suggested_display_precision(self) -> int | None:
        return 2
