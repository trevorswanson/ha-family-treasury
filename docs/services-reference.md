# Services Reference

Service field definitions and selectors are maintained in:

- [services.yaml](../custom_components/family_treasury/services.yaml)

Runtime schemas/validation are implemented in:

- `custom_components/family_treasury/services.py`

## `family_treasury.create_account`

**Purpose:** Create a new account with optional per-account settings.

**Parameters:**

| Parameter | Required | Description | Example |
| - | - | - | - |
| `account_id` | Yes | Unique account slug. | `"emma"` |
| `display_name` | Yes | Friendly name shown in UI. | `"Emma"` |
| `account_type` | No | Account type (`primary`, `bucket`, `loan`). | `"loan"` |
| `parent_account_id` | No | Parent primary account slug. | `"emma"` |
| `initial_balance` | No | Starting balance for non-loan accounts. | `10.00` |
| `loan_principal` | No | Required when `account_type` is `loan`. | `20.00` |
| `apr_percent` | No | Account-specific APR override. | `3.5` |
| `interest_calc_frequency` | No | Accrual interval. | `"daily"` |
| `interest_payout_frequency` | No | Payout interval. | `"monthly"` |
| `currency_code` | No | ISO 4217 currency code override. | `"USD"` |
| `locale` | No | Locale override for formatting. | `"en_US"` |

**Example:**

```yaml
action: family_treasury.create_account
data:
  account_id: "emma"
  display_name: "Emma"
  initial_balance: 10.00
  apr_percent: 3.5
  interest_calc_frequency: "daily"
  interest_payout_frequency: "monthly"
  currency_code: "USD"
  locale: "en_US"
```

**Use Cases:**

- Initial onboarding for a new child account.
- Creating an account with its own APR/currency settings.
- Seeding an account with an opening balance.
- Creating a loan account that disburses principal into the child primary account.

**Loan Rules (MVP):**

- `account_type: loan` requires `parent_account_id` and `loan_principal`.
- Loan accounts do not allow `initial_balance`.
- Parent account must exist and be a primary account.
- `loan_principal` becomes `original_loan_principal` for payoff-progress tracking.

## `family_treasury.update_account`

**Purpose:** Update mutable settings on an existing account.

**Parameters:**

| Parameter | Required | Description | Example |
| - | - | - | - |
| `account_id` | Yes | Existing account slug to update. | `"emma"` |
| `display_name` | No | New friendly account name. | `"Emma Savings"` |
| `active` | No | Set `false` to deactivate/archive account. | `true` |
| `apr_percent` | No | Updated APR percentage. | `4.0` |
| `interest_calc_frequency` | No | New accrual interval. | `"weekly"` |
| `interest_payout_frequency` | No | New payout interval. | `"monthly"` |
| `currency_code` | No | Updated ISO 4217 currency code. | `"USD"` |
| `locale` | No | Updated formatting locale. | `"en_US"` |

**Example:**

```yaml
action: family_treasury.update_account
data:
  account_id: "emma"
  display_name: "Emma Savings"
  active: true
  apr_percent: 4.0
```

**Use Cases:**

- Renaming an account after setup.
- Enabling/disabling an account from automations.
- Tuning APR and interest schedule settings.

## `family_treasury.deposit`

**Purpose:** Add funds to an account and record a deposit transaction.

**Parameters:**

| Parameter | Required | Description | Example |
| - | - | - | - |
| `account_id` | Yes | Target account slug. | `"emma"` |
| `amount` | Yes | Positive deposit amount. | `5.00` |
| `description` | No | Optional note in `meta.description`. | `"Allowance"` |

**Example:**

```yaml
action: family_treasury.deposit
data:
  account_id: "emma"
  amount: 5.00
  description: "Weekly allowance"
```

**Use Cases:**

- Weekly allowance credit.
- Chore reward automation.
- Gift or bonus deposit.

## `family_treasury.withdraw`

**Purpose:** Remove funds from an account and record a withdrawal transaction.

**Parameters:**

| Parameter | Required | Description | Example |
| - | - | - | - |
| `account_id` | Yes | Target account slug. | `"emma"` |
| `amount` | Yes | Positive withdrawal amount. | `2.25` |
| `description` | No | Optional note stored in `meta.description`. | `"Book"` |

**Example:**

```yaml
action: family_treasury.withdraw
data:
  account_id: "emma"
  amount: 2.25
  description: "Sticker pack"
```

**Use Cases:**

- Purchase deduction.
- Spending tied to another integration event.
- Parent-approved debit.

## `family_treasury.adjust_balance`

**Purpose:** Apply a signed administrative adjustment with audit trail.

**Parameters:**

| Parameter | Required | Description | Example |
| - | - | - | - |
| `account_id` | Yes | Target account slug. | `"emma"` |
| `amount` | Yes | Signed adjustment amount (non-zero). | `-0.75` |
| `description` | No | Adjustment reason in `meta.description`. | `"Fix"` |

**Example:**

```yaml
action: family_treasury.adjust_balance
data:
  account_id: "emma"
  amount: -0.75
  description: "Correction"
```

**Use Cases:**

- Correcting duplicate or missed entries.
- Administrative reconciliation.
- One-time balance fix during migration.

## `family_treasury.transfer`

**Purpose:** Move funds between two accounts in the same primary-account tree.

**Parameters:**

| Parameter | Required | Description | Example |
| - | - | - | - |
| `source_account_id` | Yes | Source account slug to debit. | `"emma"` |
| `destination_account_id` | Yes | Destination account slug. | `"emma_loan_1"` |
| `amount` | Yes | Positive transfer amount. | `2.50` |
| `description` | No | Optional note in `meta.description`. | `"Loan payment"` |

**Example:**

```yaml
action: family_treasury.transfer
data:
  source_account_id: "emma"
  destination_account_id: "emma_loan_1"
  amount: 2.50
  description: "Weekly loan payment"
```

**Transfer Rules (MVP):**

- Source and destination must be active, distinct, same-currency accounts.
- Transfers are only allowed inside the same ownership tree.
- Loan accounts cannot be transfer sources.
- Loan repayments must be `parent_primary -> loan`.

## `family_treasury.get_transactions`

**Purpose:** Query transaction history with optional filters and pagination.

**Parameters:**

| Parameter | Required | Description | Example |
| - | - | - | - |
| `account_id` | No | Optional account slug filter. | `"emma"` |
| `start` | No | ISO datetime start (inclusive). | `"2026-02-01T00:00Z"` |
| `end` | No | ISO datetime upper bound (inclusive). | `"2026-02-29T23:59:59Z"` |
| `type` | No | Type filter string or list. | `["deposit", "withdraw"]` |
| `limit` | No | Max rows to return (1-500). | `25` |
| `offset` | No | Rows to skip before returning results. | `0` |

**Example:**

```yaml
action: family_treasury.get_transactions
data:
  account_id: "emma"
  type:
    - "deposit"
    - "withdraw"
    - "adjustment"
    - "interest_payout"
    - "transfer_out"
    - "transfer_in"
  limit: 25
  offset: 0
```

**Use Cases:**

- Build paginated transaction views in Lovelace.
- Exclude `interest_accrual` from child-facing lists.
- Pull filtered history in scripts/automations.

**Expected Response (with `return_response: true`):**

- `transactions`: matching transaction rows.
- `total`: total number of matches for the query.
- `limit`: effective page size used.
- `offset`: current query offset.
- `next_offset`: next page offset, or `null` if no next page.

**Transaction Row Shape:**

- `tx_id`
- `account_id`
- `occurred_at`
- `type`
- `amount_minor`
- `balance_after_minor`
- `meta`

Description is stored in `meta.description`.
