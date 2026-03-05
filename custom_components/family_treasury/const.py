"""Constants for Family Treasury."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "family_treasury"
PLATFORMS: list[str] = ["sensor"]

DATA_RUNTIME = "runtime"
DATA_SERVICES_UNSUB = "services_unsub"
DATA_UPDATE_LISTENER = "update_listener"
DATA_FRONTEND_STATIC_REGISTERED = "frontend_static_registered"
DATA_FRONTEND_JS_ADDED = "frontend_js_added"
DATA_FRONTEND_RESOURCE_ID = "frontend_resource_id"
DATA_FRONTEND_RESOURCE_MANAGED = "frontend_resource_managed"
DATA_FRONTEND_RETRY_UNSUB = "frontend_retry_unsub"

STORE_VERSION = 1
STORE_METADATA_KEY = f"{DOMAIN}.metadata"
STORE_SNAPSHOTS_KEY = f"{DOMAIN}.snapshots"
STORE_LEDGER_PREFIX = f"{DOMAIN}.ledger"

FREQUENCY_DAILY = "daily"
FREQUENCY_WEEKLY = "weekly"
FREQUENCY_MONTHLY = "monthly"
FREQUENCIES = {FREQUENCY_DAILY, FREQUENCY_WEEKLY, FREQUENCY_MONTHLY}

DEFAULT_APR_PERCENT = "1.00"
DEFAULT_INTEREST_CALC_FREQUENCY = FREQUENCY_DAILY
DEFAULT_INTEREST_PAYOUT_FREQUENCY = FREQUENCY_MONTHLY
DEFAULT_CURRENCY_CODE = "USD"
DEFAULT_LOCALE = "en_US"

MICRO_MINOR_PER_MINOR = 1_000_000
RECENT_TRANSACTIONS_LIMIT = 10
MAX_TRANSACTION_QUERY_LIMIT = 500

TX_DEPOSIT = "deposit"
TX_WITHDRAW = "withdraw"
TX_ADJUSTMENT = "adjustment"
TX_INTEREST_ACCRUAL = "interest_accrual"
TX_INTEREST_PAYOUT = "interest_payout"
TX_TRANSFER_OUT = "transfer_out"
TX_TRANSFER_IN = "transfer_in"
TX_TYPES = {
    TX_DEPOSIT,
    TX_WITHDRAW,
    TX_ADJUSTMENT,
    TX_INTEREST_ACCRUAL,
    TX_INTEREST_PAYOUT,
    TX_TRANSFER_OUT,
    TX_TRANSFER_IN,
}

ACCOUNT_TYPE_PRIMARY = "primary"
ACCOUNT_TYPE_BUCKET = "bucket"
ACCOUNT_TYPE_LOAN = "loan"
ACCOUNT_TYPES = {
    ACCOUNT_TYPE_PRIMARY,
    ACCOUNT_TYPE_BUCKET,
    ACCOUNT_TYPE_LOAN,
}

CONF_DEFAULT_APR_PERCENT = "default_apr_percent"
CONF_APR_PERCENT = "apr_percent"
CONF_INTEREST_CALC_FREQUENCY = "interest_calc_frequency"
CONF_INTEREST_PAYOUT_FREQUENCY = "interest_payout_frequency"
CONF_CURRENCY_CODE = "currency_code"
CONF_LOCALE = "locale"
CONF_APPLY_DEFAULTS_TO_EXISTING = "apply_defaults_to_existing"

CONF_ACCOUNT_ID = "account_id"
CONF_ACCOUNT_TYPE = "account_type"
CONF_PARENT_ACCOUNT_ID = "parent_account_id"
CONF_LOAN_PRINCIPAL = "loan_principal"
CONF_DISPLAY_NAME = "display_name"
CONF_AMOUNT = "amount"
CONF_DESCRIPTION = "description"
CONF_SOURCE_ACCOUNT_ID = "source_account_id"
CONF_DESTINATION_ACCOUNT_ID = "destination_account_id"
CONF_ACTIVE = "active"
CONF_START = "start"
CONF_END = "end"
CONF_TYPE = "type"
CONF_LIMIT = "limit"
CONF_OFFSET = "offset"
CONF_INITIAL_BALANCE = "initial_balance"

ATTR_ACCOUNT_ID = "account_id"
ATTR_ACCOUNT_TYPE = "account_type"
ATTR_PARENT_ACCOUNT_ID = "parent_account_id"
ATTR_DISPLAY_NAME = "display_name"
ATTR_CURRENCY_CODE = "currency_code"
ATTR_LOCALE = "locale"
ATTR_FORMATTED_BALANCE = "formatted_balance"
ATTR_FORMATTED_PENDING_INTEREST = "formatted_pending_interest"
ATTR_LAST_INTEREST_CALC_AT = "last_interest_calc_at"
ATTR_LAST_INTEREST_PAYOUT_AT = "last_interest_payout_at"
ATTR_RECENT_TRANSACTIONS = "recent_transactions"

SERVICE_CREATE_ACCOUNT = "create_account"
SERVICE_UPDATE_ACCOUNT = "update_account"
SERVICE_DEPOSIT = "deposit"
SERVICE_WITHDRAW = "withdraw"
SERVICE_ADJUST_BALANCE = "adjust_balance"
SERVICE_TRANSFER = "transfer"
SERVICE_GET_TRANSACTIONS = "get_transactions"

SCHEDULER_INTERVAL = timedelta(hours=1)
SIGNAL_ACCOUNTS_UPDATED = f"{DOMAIN}_accounts_updated"

FRONTEND_DIR = "frontend"
FRONTEND_TRANSACTIONS_CARD_FILENAME = "family-treasury-transactions-card.js"
FRONTEND_TRANSACTIONS_CARD_URL = (
    f"/{DOMAIN}/{FRONTEND_TRANSACTIONS_CARD_FILENAME}"
)
