"""Persistent storage backend for Family Treasury."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    MAX_TRANSACTION_QUERY_LIMIT,
    STORE_LEDGER_PREFIX,
    STORE_METADATA_KEY,
    STORE_SNAPSHOTS_KEY,
    STORE_VERSION,
)
from .interest import month_partition_key
from .models import AccountRecord, TransactionRecord

_LOGGER = logging.getLogger(__name__)
UTC = timezone.utc


class FamilyTreasuryStorage:
    """Wrap Home Assistant storage for account and transaction data."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._metadata_store = Store[dict[str, Any]](
            hass,
            STORE_VERSION,
            STORE_METADATA_KEY,
        )
        self._snapshots_store = Store[dict[str, Any]](
            hass,
            STORE_VERSION,
            STORE_SNAPSHOTS_KEY,
        )
        self._metadata: dict[str, Any] = {}
        self._snapshots: dict[str, Any] = {}
        self._ledger_stores: dict[str, Store[dict[str, Any]]] = {}

    async def async_load(self) -> None:
        """Load metadata and snapshots from disk."""

        metadata = await self._metadata_store.async_load()
        if not isinstance(metadata, dict):
            metadata = {}

        self._metadata = {
            "accounts": metadata.get("accounts", {}),
            "next_tx_id": int(metadata.get("next_tx_id", 1)),
            "ledger_partitions": list(metadata.get("ledger_partitions", [])),
            "schema_version": metadata.get("schema_version", STORE_VERSION),
        }

        snapshots = await self._snapshots_store.async_load()
        if not isinstance(snapshots, dict):
            snapshots = {}
        self._snapshots = {"snapshots": snapshots.get("snapshots", {})}

    @property
    def last_tx_id(self) -> int | None:
        """Return last allocated transaction ID."""

        next_tx_id = int(self._metadata.get("next_tx_id", 1))
        return None if next_tx_id <= 1 else next_tx_id - 1

    async def async_save_metadata(self) -> None:
        """Persist metadata payload."""

        await self._metadata_store.async_save(self._metadata)

    async def async_save_snapshots(self) -> None:
        """Persist snapshots payload."""

        await self._snapshots_store.async_save(self._snapshots)

    def list_accounts(self) -> dict[str, AccountRecord]:
        """Return all accounts."""

        accounts: dict[str, AccountRecord] = {}
        for account_id, payload in self._metadata["accounts"].items():
            try:
                accounts[account_id] = AccountRecord.from_dict(payload)
            except Exception:  # pragma: no cover
                _LOGGER.warning("Skipping malformed account payload for %s", account_id)
        return accounts

    async def async_replace_accounts(self, accounts: dict[str, AccountRecord]) -> None:
        """Persist the full account map."""

        self._metadata["accounts"] = {
            account_id: record.to_dict() for account_id, record in accounts.items()
        }
        await self.async_save_metadata()

    async def async_delete_snapshots_for_accounts(self, account_ids: set[str]) -> None:
        """Delete snapshots for account IDs."""

        changed = False
        snapshots = self._snapshots["snapshots"]
        for account_id in account_ids:
            if account_id in snapshots:
                snapshots.pop(account_id, None)
                changed = True
        if changed:
            await self.async_save_snapshots()

    async def async_reserve_tx_id(self) -> int:
        """Reserve and persist the next global transaction ID."""

        tx_id = int(self._metadata["next_tx_id"])
        self._metadata["next_tx_id"] = tx_id + 1
        await self.async_save_metadata()
        return tx_id

    async def async_append_transaction(self, transaction: TransactionRecord) -> None:
        """Append a transaction into the monthly ledger partition."""

        occurred_at = datetime.fromisoformat(transaction.occurred_at)
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        month_key = month_partition_key(occurred_at)

        partition = await self._async_load_partition(month_key)
        partition["transactions"].append(transaction.to_dict())
        await self._async_partition_store(month_key).async_save(partition)

        partitions = set(self._metadata.get("ledger_partitions", []))
        if month_key not in partitions:
            partitions.add(month_key)
            self._metadata["ledger_partitions"] = sorted(partitions)
            await self.async_save_metadata()

    async def async_list_transactions(
        self,
        *,
        account_id: str | None,
        start: datetime | None,
        end: datetime | None,
        tx_types: set[str] | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        """Query transactions with simple offset pagination."""

        capped_limit = max(1, min(limit, MAX_TRANSACTION_QUERY_LIMIT))
        capped_offset = max(0, offset)

        filtered: list[dict[str, Any]] = []

        for month_key in sorted(self._metadata.get("ledger_partitions", []), reverse=True):
            partition = await self._async_load_partition(month_key)
            for row in partition["transactions"]:
                if account_id and row.get("account_id") != account_id:
                    continue
                if tx_types and row.get("type") not in tx_types:
                    continue

                occurred_at = self._parse_row_datetime(row)
                if occurred_at is None:
                    continue
                if start and occurred_at < start:
                    continue
                if end and occurred_at > end:
                    continue

                filtered.append(row)

        filtered.sort(key=lambda row: row.get("tx_id", 0), reverse=True)
        total = len(filtered)
        page = filtered[capped_offset : capped_offset + capped_limit]
        next_offset = capped_offset + len(page)

        return {
            "transactions": page,
            "total": total,
            "limit": capped_limit,
            "offset": capped_offset,
            "next_offset": next_offset if next_offset < total else None,
        }

    async def async_purge_transactions_for_accounts(self, account_ids: set[str]) -> None:
        """Delete ledger rows for account IDs across all partitions."""

        for month_key in list(self._metadata.get("ledger_partitions", [])):
            partition = await self._async_load_partition(month_key)
            existing_rows = partition["transactions"]
            filtered_rows = [
                row for row in existing_rows if row.get("account_id") not in account_ids
            ]
            if len(filtered_rows) == len(existing_rows):
                continue

            await self._async_partition_store(month_key).async_save(
                {"transactions": filtered_rows}
            )

    async def async_create_monthly_snapshot(
        self,
        *,
        account: AccountRecord,
        last_tx_id: int | None,
        snapshot_at: datetime,
    ) -> None:
        """Persist at most one snapshot per account per month."""

        month_key = month_partition_key(snapshot_at)
        per_account: dict[str, list[dict[str, Any]]] = self._snapshots["snapshots"]
        records = per_account.setdefault(account.account_id, [])

        if records and records[-1].get("snapshot_month") == month_key:
            return

        records.append(
            {
                "account_id": account.account_id,
                "snapshot_at": snapshot_at.astimezone(UTC).isoformat(),
                "snapshot_month": month_key,
                "balance_minor": account.balance_minor,
                "pending_interest_micro_minor": account.pending_interest_micro_minor,
                "last_tx_id": last_tx_id,
            }
        )
        await self.async_save_snapshots()

    def recent_snapshot(self, account_id: str) -> dict[str, Any] | None:
        """Return the latest snapshot for an account."""

        snapshots = self._snapshots["snapshots"].get(account_id)
        if not snapshots:
            return None
        return snapshots[-1]

    def _async_partition_store(self, month_key: str) -> Store[dict[str, Any]]:
        if month_key not in self._ledger_stores:
            self._ledger_stores[month_key] = Store[dict[str, Any]](
                self._hass,
                STORE_VERSION,
                f"{STORE_LEDGER_PREFIX}.{month_key}",
            )
        return self._ledger_stores[month_key]

    async def _async_load_partition(self, month_key: str) -> dict[str, Any]:
        store = self._async_partition_store(month_key)
        payload = await store.async_load()
        if not isinstance(payload, dict):
            return {"transactions": []}

        transactions = payload.get("transactions")
        if not isinstance(transactions, list):
            _LOGGER.warning(
                "Corrupt ledger partition %s encountered; treating as empty.", month_key
            )
            return {"transactions": []}

        return {"transactions": transactions}

    @staticmethod
    def _parse_row_datetime(row: dict[str, Any]) -> datetime | None:
        occurred_at = row.get("occurred_at")
        if not isinstance(occurred_at, str):
            return None

        try:
            parsed = datetime.fromisoformat(occurred_at)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)
        return parsed
