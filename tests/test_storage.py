"""Unit tests for storage helper behaviors."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

HA_AVAILABLE = True
try:
    from custom_components.family_treasury.storage import FamilyTreasuryStorage
except ModuleNotFoundError:
    HA_AVAILABLE = False


def _build_storage() -> FamilyTreasuryStorage:
    storage = object.__new__(FamilyTreasuryStorage)
    storage._metadata = {"ledger_partitions": []}
    storage._snapshots = {"snapshots": {}}
    storage.async_save_snapshots = AsyncMock()
    return storage


@unittest.skipUnless(HA_AVAILABLE, "homeassistant is not installed in this environment")
class TestStorageHelpers(unittest.IsolatedAsyncioTestCase):
    """Storage helper method tests."""

    async def test_delete_snapshots_for_accounts_saves_on_change(self) -> None:
        storage = _build_storage()
        storage._snapshots = {
            "snapshots": {
                "emma": [{"snapshot_month": "2026-03"}],
                "sam": [{"snapshot_month": "2026-03"}],
            }
        }

        await storage.async_delete_snapshots_for_accounts({"emma", "missing"})

        self.assertNotIn("emma", storage._snapshots["snapshots"])
        self.assertIn("sam", storage._snapshots["snapshots"])
        storage.async_save_snapshots.assert_awaited_once()

    async def test_purge_transactions_for_accounts_filters_and_skips(self) -> None:
        storage = _build_storage()
        storage._metadata = {"ledger_partitions": ["2026-03", "2026-02"]}

        march_rows = {
            "transactions": [
                {"account_id": "emma", "tx_id": 1},
                {"account_id": "sam", "tx_id": 2},
            ]
        }
        feb_rows = {"transactions": [{"account_id": "sam", "tx_id": 3}]}

        async def load_partition(month_key: str):
            return march_rows if month_key == "2026-03" else feb_rows

        march_store = SimpleNamespace(async_save=AsyncMock())
        feb_store = SimpleNamespace(async_save=AsyncMock())

        storage._async_load_partition = AsyncMock(side_effect=load_partition)
        storage._async_partition_store = (
            lambda month_key: march_store if month_key == "2026-03" else feb_store
        )

        await storage.async_purge_transactions_for_accounts({"emma"})

        march_store.async_save.assert_awaited_once_with(
            {"transactions": [{"account_id": "sam", "tx_id": 2}]}
        )
        feb_store.async_save.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
