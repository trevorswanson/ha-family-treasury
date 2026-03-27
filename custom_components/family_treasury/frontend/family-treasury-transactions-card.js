const CARD_TYPE = "custom:family-treasury-transactions";
const CARD_ELEMENT_NAME = "family-treasury-transactions";
const CARD_EDITOR_ELEMENT_NAME = "family-treasury-transactions-editor";
const DEFAULT_PAGE_SIZE = 10;
const DEFAULT_PAGE_SIZE_OPTIONS = [5, 10, 25, 50];
const TRANSACTION_TYPES = [
  "deposit",
  "withdraw",
  "adjustment",
  "interest_accrual",
  "interest_payout",
  "transfer_out",
  "transfer_in",
];
const TRANSACTION_TYPE_FILTER_LABELS = {
  deposit: "Deposit",
  withdraw: "Withdrawal",
  adjustment: "Adjustment",
  interest_accrual: "Interest Accrual",
  interest_payout: "Interest Payout",
  transfer_out: "Transfer Out",
  transfer_in: "Transfer In",
};
const TRANSACTION_TYPE_FILTER_LABEL_KEYS = {
  deposit: "transaction_type_filter.deposit",
  withdraw: "transaction_type_filter.withdraw",
  adjustment: "transaction_type_filter.adjustment",
  interest_accrual: "transaction_type_filter.interest_accrual",
  interest_payout: "transaction_type_filter.interest_payout",
  transfer_out: "transaction_type_filter.transfer_out",
  transfer_in: "transaction_type_filter.transfer_in",
};
const TRANSACTION_TYPE_ROW_LABELS = {
  deposit: "Deposit",
  withdraw: "Withdrawal",
  adjustment: "Adjustment",
  interest_accrual: "Interest Accrual",
  interest_payout: "Interest Payout",
  transfer_out: "Transfer",
  transfer_in: "Transfer",
};
const TRANSACTION_TYPE_ROW_LABEL_KEYS = {
  deposit: "transaction_type_row.deposit",
  withdraw: "transaction_type_row.withdraw",
  adjustment: "transaction_type_row.adjustment",
  interest_accrual: "transaction_type_row.interest_accrual",
  interest_payout: "transaction_type_row.interest_payout",
  transfer_out: "transaction_type_row.transfer_out",
  transfer_in: "transaction_type_row.transfer_in",
};
const DEFAULT_EDITOR_TYPES = TRANSACTION_TYPES.filter(
  (type) => type !== "interest_accrual",
);

function normalizeTypes(rawTypes) {
  if (rawTypes === null || rawTypes === undefined) {
    return null;
  }

  const values = Array.isArray(rawTypes) ? rawTypes : [rawTypes];
  const normalized = values
    .map((value) => String(value).trim())
    .filter(
      (value, index, all) =>
        value.length > 0 && all.indexOf(value) === index,
    );

  if (normalized.length === 0) {
    return null;
  }

  const invalid = normalized.filter((value) => !TRANSACTION_TYPES.includes(value));
  if (invalid.length > 0) {
    throw new Error(
      `\`types\` contains unsupported values: ${invalid.join(", ")}. Valid \`types\` are: ${TRANSACTION_TYPES.join(", ")}`,
    );
  }

  return normalized;
}

function sanitizePageSizeOptions(rawOptions, fallback) {
  const options = Array.isArray(rawOptions)
    ? rawOptions
    : DEFAULT_PAGE_SIZE_OPTIONS;
  const sanitized = options
    .map((value) => Number.parseInt(value, 10))
    .filter(
      (value, index, all) =>
        Number.isFinite(value) && value > 0 && all.indexOf(value) === index,
    )
    .sort((a, b) => a - b);

  if (!sanitized.includes(fallback)) {
    sanitized.push(fallback);
    sanitized.sort((a, b) => a - b);
  }

  return sanitized;
}

function collectAccountOptions(states) {
  const options = new Map();

  Object.entries(states ?? {}).forEach(([entityId, stateObj]) => {
    if (
      !entityId.startsWith("sensor.") ||
      !entityId.endsWith("_balance") ||
      entityId.endsWith("_loan_total_balance")
    ) {
      return;
    }

    const accountId = stateObj?.attributes?.account_id;
    if (typeof accountId !== "string" || !accountId.trim()) {
      return;
    }

    if (options.has(accountId)) {
      return;
    }

    const displayName = stateObj.attributes.display_name;
    const friendlyName = stateObj.attributes.friendly_name;
    const label =
      typeof displayName === "string" && displayName.trim()
        ? displayName.trim()
        : typeof friendlyName === "string" && friendlyName.trim()
          ? friendlyName.replace(/\s+Balance$/, "").trim()
          : accountId;

    options.set(accountId, { account_id: accountId, label });
  });

  return Array.from(options.values()).sort((left, right) =>
    left.label.localeCompare(right.label),
  );
}

function accountOptionsSignature(options) {
  return options
    .map((option) => `${option.account_id}:${option.label}`)
    .join("|");
}

function resolveConfiguredAccountIds(config) {
  const selected = new Set();

  if (typeof config?.account_id === "string" && config.account_id.trim()) {
    selected.add(config.account_id.trim());
  }

  if (Array.isArray(config?.account_ids)) {
    config.account_ids
      .map((value) => String(value).trim())
      .filter((value) => value.length > 0)
      .forEach((value) => selected.add(value));
  }

  return Array.from(selected);
}

function applySelectedAccounts(config, accountIds) {
  const deduped = accountIds.filter(
    (value, index, all) => value.length > 0 && all.indexOf(value) === index,
  );
  const nextConfig = { ...config };

  delete nextConfig.account_id;
  delete nextConfig.account_ids;

  if (deduped.length === 1) {
    nextConfig.account_id = deduped[0];
  } else if (deduped.length > 1) {
    nextConfig.account_ids = deduped;
  }

  return nextConfig;
}

function transactionTypeLabel(type, labels) {
  const normalized = String(type ?? "").trim();
  if (!normalized) {
    return "";
  }
  return labels[normalized] ?? normalized;
}

function localizedLabel(hass, translationKey, fallback) {
  if (typeof hass?.localize === "function") {
    const localized = hass.localize(
      `component.family_treasury.common.${translationKey}`,
    );
    if (localized && localized !== `component.family_treasury.common.${translationKey}`) {
      return localized;
    }
  }
  return fallback;
}

function localizedTransactionTypeLabel(hass, type, keyMap, fallbackMap) {
  const normalized = String(type ?? "").trim();
  if (!normalized) {
    return "";
  }

  const fallback = transactionTypeLabel(normalized, fallbackMap);
  const translationKey = keyMap[normalized];
  if (!translationKey) {
    return fallback;
  }

  return localizedLabel(hass, translationKey, fallback);
}

class FamilyTreasuryTransactionsCard extends HTMLElement {
  static async getConfigElement() {
    return document.createElement(CARD_EDITOR_ELEMENT_NAME);
  }

  static async getStubConfig(hass) {
    const accounts = collectAccountOptions(hass?.states ?? {});

    return {
      type: CARD_TYPE,
      title: "Recent Transactions",
      account_id: accounts[0]?.account_id ?? "",
      show_account_name: true,
      page_size: DEFAULT_PAGE_SIZE,
      enable_pagination: true,
      allow_page_size_override: false,
      page_size_options: [...DEFAULT_PAGE_SIZE_OPTIONS],
      types: [...DEFAULT_EDITOR_TYPES],
    };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._configError = null;
    this._transactions = [];
    this._loading = false;
    this._error = null;
    this._offset = 0;
    this._nextOffset = null;
    this._total = 0;
    this._requestId = 0;
    this._lastFetchAt = 0;
    this._pageSize = DEFAULT_PAGE_SIZE;
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Card configuration is required");
    }

    const accountId =
      typeof config.account_id === "string" ? config.account_id.trim() : "";
    const accountIds = resolveConfiguredAccountIds(config);
    const pageSize = Number.parseInt(
      config.page_size ?? DEFAULT_PAGE_SIZE,
      10,
    );
    if (!Number.isFinite(pageSize) || pageSize < 1) {
      throw new Error("`page_size` must be a positive integer");
    }

    const enablePagination = config.enable_pagination !== false;
    const showAccountName = config.show_account_name !== false;
    const allowPageSizeOverride =
      enablePagination && config.allow_page_size_override === true;
    const pageSizeOptions = sanitizePageSizeOptions(
      config.page_size_options,
      pageSize,
    );
    const types = normalizeTypes(config.types ?? null);

    this._config = {
      title: config.title ?? "Recent Transactions",
      account_id: accountIds.length === 1 ? accountIds[0] : accountId,
      account_ids: accountIds,
      show_account_name: showAccountName,
      page_size: pageSize,
      enable_pagination: enablePagination,
      allow_page_size_override: allowPageSizeOverride,
      page_size_options: pageSizeOptions,
      types,
    };
    this._configError =
      accountIds.length > 0 ? null : "Select at least one account";

    this._pageSize = pageSize;
    this._offset = 0;
    this._nextOffset = null;
    this._error = null;
    this._transactions = [];
    this._total = 0;
    this._render();

    if (this._hass && !this._configError) {
      void this._fetchTransactions({ offset: 0, allowClamp: true });
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) {
      return;
    }

    if (this._configError) {
      this._render();
      return;
    }

    if (this._lastFetchAt === 0) {
      void this._fetchTransactions({ offset: this._offset, allowClamp: true });
      return;
    }

    const now = Date.now();
    if (!this._loading && now - this._lastFetchAt >= 15000) {
      void this._fetchTransactions({ offset: this._offset, allowClamp: true });
    }
  }

  getCardSize() {
    return 5;
  }

  _effectivePageSize() {
    if (!this._config.allow_page_size_override) {
      return this._config.page_size;
    }
    return this._pageSize;
  }

  async _fetchTransactions({ offset, allowClamp }) {
    if (
      !this._hass ||
      !this._config ||
      !Array.isArray(this._config.account_ids) ||
      this._config.account_ids.length === 0
    ) {
      return;
    }

    const pageSize = this._effectivePageSize();
    const requestOffset = this._config.enable_pagination ? Math.max(0, offset) : 0;
    const requestId = ++this._requestId;
    this._loading = true;
    this._error = null;
    this._render();

    try {
      const serviceData = {
        account_id: this._config.account_id,
        limit: pageSize,
        offset: requestOffset,
      };
      if (this._config.account_ids.length > 1) {
        delete serviceData.account_id;
        serviceData.account_ids = this._config.account_ids;
      }
      if (this._config.types !== null) {
        serviceData.type = this._config.types;
      }

      const result = await this._hass.callWS({
        type: "call_service",
        domain: "family_treasury",
        service: "get_transactions",
        service_data: serviceData,
        return_response: true,
      });

      if (requestId !== this._requestId) {
        return;
      }

      const response = this._extractResponse(result);
      const transactions = Array.isArray(response.transactions)
        ? response.transactions
        : [];
      const total = Number.isInteger(response.total)
        ? response.total
        : transactions.length;
      const normalizedOffset = Number.isInteger(response.offset)
        ? response.offset
        : requestOffset;
      const nextOffset =
        response.next_offset === null || response.next_offset === undefined
          ? null
          : Number.parseInt(response.next_offset, 10);

      if (
        allowClamp &&
        this._config.enable_pagination &&
        total > 0 &&
        normalizedOffset >= total
      ) {
        const lastOffset = Math.floor((total - 1) / pageSize) * pageSize;
        if (lastOffset !== normalizedOffset) {
          this._loading = false;
          await this._fetchTransactions({
            offset: lastOffset,
            allowClamp: false,
          });
          return;
        }
      }

      this._transactions = transactions;
      this._total = total;
      this._offset = normalizedOffset;
      this._nextOffset = Number.isFinite(nextOffset) ? nextOffset : null;
      this._lastFetchAt = Date.now();
    } catch (err) {
      if (requestId !== this._requestId) {
        return;
      }
      this._error = err?.message ?? "Unable to load transactions";
    } finally {
      if (requestId === this._requestId) {
        this._loading = false;
        this._render();
      }
    }
  }

  _extractResponse(result) {
    if (result && typeof result === "object") {
      if (result.response && typeof result.response === "object") {
        return result.response;
      }
      if (result.service_response && typeof result.service_response === "object") {
        return result.service_response;
      }
      return result;
    }
    return {};
  }

  _handlePrev = () => {
    if (!this._config.enable_pagination || this._loading || this._offset <= 0) {
      return;
    }
    const previousOffset = Math.max(0, this._offset - this._effectivePageSize());
    void this._fetchTransactions({ offset: previousOffset, allowClamp: false });
  };

  _handleNext = () => {
    if (!this._config.enable_pagination || this._loading || this._nextOffset === null) {
      return;
    }
    void this._fetchTransactions({ offset: this._nextOffset, allowClamp: false });
  };

  _handleRefresh = () => {
    void this._fetchTransactions({ offset: this._offset, allowClamp: true });
  };

  _handlePageSizeChange = (event) => {
    const nextSize = Number.parseInt(event.target.value, 10);
    if (!Number.isFinite(nextSize) || nextSize < 1) {
      return;
    }
    this._pageSize = nextSize;
    this._offset = 0;
    this._nextOffset = null;
    void this._fetchTransactions({ offset: 0, allowClamp: true });
  };

  _render() {
    if (!this._config) {
      return;
    }

    const errorMessage = this._configError ?? this._error;
    const isMultiAccount = this._config.account_ids.length > 1;
    const showControls = this._config.enable_pagination;
    const showPageSizeSelector =
      showControls && this._config.allow_page_size_override;
    const canPrev = showControls && this._offset > 0 && !this._loading;
    const canNext = showControls && this._nextOffset !== null && !this._loading;
    const rowStart = this._transactions.length === 0 ? 0 : this._offset + 1;
    const rowEnd = this._offset + this._transactions.length;

    const rows = this._transactions
      .map((tx) => {
        const occurredAt = this._formatDate(tx.occurred_at);
        const accountId = this._escapeHtml(String(tx.account_id ?? ""));
        const type = this._escapeHtml(
          localizedTransactionTypeLabel(
            this._hass,
            tx.type,
            TRANSACTION_TYPE_ROW_LABEL_KEYS,
            TRANSACTION_TYPE_ROW_LABELS,
          ),
        );
        const description = this._escapeHtml(String(tx.meta?.description ?? ""));
        const amount = this._escapeHtml(
          String(tx.formatted_amount ?? tx.amount_major ?? tx.amount_minor ?? ""),
        );
        const balance = this._escapeHtml(
          String(
            tx.formatted_balance_after ??
              tx.balance_after_major ??
              tx.balance_after_minor ??
              "",
          ),
        );
        return `<tr>
          <td>${occurredAt}</td>
          ${isMultiAccount ? `<td>${accountId || "-"}</td>` : ""}
          <td>${type}</td>
          <td>${description || "-"}</td>
          <td class="amount">${amount}</td>
          ${isMultiAccount ? "" : `<td class="amount">${balance}</td>`}
        </tr>`;
      })
      .join("");

    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 0; }
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 16px 16px 8px 16px;
        }
        .title { font-size: 1.1rem; font-weight: 600; }
        .meta { color: var(--secondary-text-color); font-size: 0.88rem; }
        .content { padding: 0 16px 12px 16px; }
        table {
          width: 100%;
          border-collapse: collapse;
          font-size: 0.92rem;
        }
        th, td {
          padding: 8px 6px;
          border-bottom: 1px solid var(--divider-color);
          text-align: left;
          vertical-align: top;
        }
        th { color: var(--secondary-text-color); font-weight: 600; }
        td.amount { text-align: right; font-variant-numeric: tabular-nums; }
        .controls {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          padding: 8px 16px 16px 16px;
        }
        .controls-left,
        .controls-right {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .status {
          color: var(--secondary-text-color);
          font-size: 0.88rem;
        }
        .error {
          margin: 0 16px 12px 16px;
          color: var(--error-color);
          font-size: 0.92rem;
        }
        .empty {
          padding: 16px;
          color: var(--secondary-text-color);
          font-size: 0.92rem;
        }
        select {
          min-width: 70px;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          padding: 6px;
        }
        button {
          border: 1px solid var(--divider-color);
          border-radius: 10px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          padding: 6px 10px;
          cursor: pointer;
        }
        button[disabled] {
          opacity: 0.6;
          cursor: default;
        }
      </style>
      <ha-card>
        <div class="header">
          <div>
            <div class="title">${this._escapeHtml(this._config.title)}</div>
            ${
              this._config.show_account_name
                ? `<div class="meta">
                     ${
                       isMultiAccount
                         ? `Accounts:
              <code>${this._escapeHtml(this._config.account_ids.join(", "))}</code>`
                         : `Account:
              <code>${this._escapeHtml(this._config.account_id || "Not selected")}</code>`
                     }
                   </div>`
                : ""
            }
          </div>
          <button id="refresh" type="button">Refresh</button>
        </div>
        ${
          errorMessage
            ? `<div class="error">${this._escapeHtml(errorMessage)}</div>`
            : ""
        }
        ${
          this._transactions.length === 0 && !this._loading && !errorMessage
            ? `<div class="empty">No transactions found.</div>`
            : errorMessage
              ? `<div class="empty">Choose an account in the card editor to load transactions.</div>`
              : `<div class="content">
                  <table>
                    <thead>
                      <tr>
                        <th>Occurred</th>
                        ${isMultiAccount ? "<th>Account</th>" : ""}
                        <th>Type</th>
                        <th>Description</th>
                        <th style="text-align:right;">Amount</th>
                        ${isMultiAccount ? "" : '<th style="text-align:right;">Balance</th>'}
                      </tr>
                    </thead>
                  <tbody>${rows}</tbody>
                  </table>
                </div>`
        }
        <div class="controls">
          <div class="controls-left">
            ${
              showPageSizeSelector
                ? `<label class="status" for="page-size">Rows:</label>
                   <select id="page-size">
                     ${this._config.page_size_options
                       .map(
                         (option) =>
                           `<option value="${option}" ${
                             option === this._effectivePageSize() ? "selected" : ""
                           }>${option}</option>`,
                       )
                       .join("")}
                   </select>`
                : ""
            }
            <div class="status">
              ${this._loading ? "Loading..." : `${rowStart}-${rowEnd} of ${this._total}`}
            </div>
          </div>
          <div class="controls-right">
            ${
              showControls
                ? `<button id="prev" type="button">Prev</button>
                   <button id="next" type="button">Next</button>`
                : ""
            }
          </div>
        </div>
      </ha-card>
    `;

    const refreshButton = this.shadowRoot.getElementById("refresh");
    if (refreshButton) {
      refreshButton.addEventListener("click", this._handleRefresh);
      if (this._loading || this._configError) {
        refreshButton.setAttribute("disabled", "disabled");
      } else {
        refreshButton.removeAttribute("disabled");
      }
    }

    const prevButton = this.shadowRoot.getElementById("prev");
    if (prevButton) {
      prevButton.addEventListener("click", this._handlePrev);
      if (!canPrev) {
        prevButton.setAttribute("disabled", "disabled");
      } else {
        prevButton.removeAttribute("disabled");
      }
    }

    const nextButton = this.shadowRoot.getElementById("next");
    if (nextButton) {
      nextButton.addEventListener("click", this._handleNext);
      if (!canNext) {
        nextButton.setAttribute("disabled", "disabled");
      } else {
        nextButton.removeAttribute("disabled");
      }
    }

    const pageSizeSelect = this.shadowRoot.getElementById("page-size");
    if (pageSizeSelect) {
      pageSizeSelect.addEventListener("change", this._handlePageSizeChange);
    }
  }

  _formatDate(raw) {
    if (!raw) {
      return "-";
    }
    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) {
      return this._escapeHtml(String(raw));
    }
    return this._escapeHtml(parsed.toLocaleString());
  }

  _escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
}

class FamilyTreasuryTransactionsCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = { type: CARD_TYPE };
    this._accountOptionsCache = [];
    this._accountOptionsSignature = null;
  }

  set hass(hass) {
    this._hass = hass;
    const nextOptions = collectAccountOptions(hass?.states ?? {});
    const nextSignature = accountOptionsSignature(nextOptions);

    if (
      this._accountOptionsSignature === nextSignature &&
      this.shadowRoot.innerHTML !== ""
    ) {
      return;
    }

    this._accountOptionsCache = nextOptions;
    this._accountOptionsSignature = nextSignature;
    this._render();
  }

  setConfig(config) {
    this._config = {
      type: CARD_TYPE,
      ...config,
    };
    this._render();
  }

  _accountOptions() {
    return this._accountOptionsCache;
  }

  _selectedAccountIds() {
    return resolveConfiguredAccountIds(this._config);
  }

  _selectedTypes() {
    const normalized = normalizeTypes(this._config.types ?? null);
    return normalized ?? [...TRANSACTION_TYPES];
  }

  _emitConfig(nextConfig) {
    this._config = nextConfig;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: nextConfig },
        bubbles: true,
        composed: true,
      }),
    );
    this._render();
  }

  _handleInputChange = (event) => {
    const field = event.target.name;
    if (!field) {
      return;
    }

    const nextConfig = { ...this._config };

    if (field === "title" || field === "account_id") {
      nextConfig[field] = event.target.value;
    } else if (field === "page_size") {
      const value = Number.parseInt(event.target.value, 10);
      nextConfig.page_size =
        Number.isFinite(value) && value > 0 ? value : DEFAULT_PAGE_SIZE;
    } else if (field === "show_account_name") {
      nextConfig.show_account_name = event.target.checked;
    } else if (field === "enable_pagination") {
      nextConfig.enable_pagination = event.target.checked;
      if (!event.target.checked) {
        nextConfig.allow_page_size_override = false;
      }
    } else if (field === "allow_page_size_override") {
      nextConfig.allow_page_size_override = event.target.checked;
    } else if (field === "page_size_options") {
      const parsed = String(event.target.value)
        .split(",")
        .map((value) => Number.parseInt(value.trim(), 10))
        .filter(
          (value, index, all) =>
            Number.isFinite(value) && value > 0 && all.indexOf(value) === index,
        )
        .sort((left, right) => left - right);

      nextConfig.page_size_options =
        parsed.length > 0 ? parsed : [...DEFAULT_PAGE_SIZE_OPTIONS];
    }

    this._emitConfig(nextConfig);
  };

  _handleTypeChange = (event) => {
    const type = event.target.value;
    const checked = event.target.checked;
    const selected = this._selectedTypes();
    const nextTypes = checked
      ? [...selected, type]
      : selected.filter((value) => value !== type);
    const deduped = nextTypes.filter(
      (value, index, all) => all.indexOf(value) === index,
    );

    this._emitConfig({
      ...this._config,
      types: deduped.length > 0 ? deduped : [...TRANSACTION_TYPES],
    });
  };

  _handleAccountChange = (event) => {
    const accountId = event.target.value;
    const checked = event.target.checked;
    const selected = this._selectedAccountIds();
    const nextSelected = checked
      ? [...selected, accountId]
      : selected.filter((value) => value !== accountId);

    this._emitConfig(applySelectedAccounts(this._config, nextSelected));
  };

  _render() {
    const accounts = this._accountOptions();
    const selectedAccounts = this._selectedAccountIds();
    const selectedTypes = this._selectedTypes();
    const enablePagination = this._config.enable_pagination !== false;
    const allowPageSizeOverride =
      enablePagination && this._config.allow_page_size_override === true;
    const pageSize = Number.parseInt(
      this._config.page_size ?? DEFAULT_PAGE_SIZE,
      10,
    );
    const effectivePageSize =
      Number.isFinite(pageSize) && pageSize > 0 ? pageSize : DEFAULT_PAGE_SIZE;
    const pageSizeOptions = sanitizePageSizeOptions(
      this._config.page_size_options,
      effectivePageSize,
    );

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        .form {
          display: grid;
          gap: 16px;
          padding: 16px 0;
        }
        .field {
          display: grid;
          gap: 6px;
        }
        .field label,
        .group-title {
          color: var(--primary-text-color);
          font-size: 0.95rem;
          font-weight: 600;
        }
        .hint {
          color: var(--secondary-text-color);
          font-size: 0.84rem;
          line-height: 1.4;
        }
        input,
        select {
          border: 1px solid var(--divider-color);
          border-radius: 10px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          padding: 10px 12px;
          font: inherit;
        }
        input[type="checkbox"] {
          margin: 0;
          width: 16px;
          height: 16px;
          padding: 0;
        }
        .toggle {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .types-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 10px 14px;
          padding: 12px;
          border: 1px solid var(--divider-color);
          border-radius: 12px;
        }
        .type-option {
          display: flex;
          align-items: center;
          gap: 8px;
          color: var(--primary-text-color);
        }
      </style>
      <div class="form">
        <div class="field">
          <label for="title">Title</label>
          <input
            id="title"
            name="title"
            type="text"
            value="${this._escapeHtml(String(this._config.title ?? "Recent Transactions"))}"
          />
        </div>
        <label class="toggle" for="show_account_name">
          <input
            id="show_account_name"
            name="show_account_name"
            type="checkbox"
            ${this._config.show_account_name !== false ? "checked" : ""}
          />
          <span>Show account name under title</span>
        </label>
        <div class="field">
          <div class="group-title">Accounts</div>
          <div class="types-grid">
            ${accounts
              .map(
                (account) => `<label class="type-option" for="account-${account.account_id}">
                  <input
                    id="account-${account.account_id}"
                    type="checkbox"
                    value="${this._escapeHtml(account.account_id)}"
                    ${selectedAccounts.includes(account.account_id) ? "checked" : ""}
                  />
                  <span>${this._escapeHtml(account.label)} (${this._escapeHtml(account.account_id)})</span>
                </label>`,
              )
              .join("")}
          </div>
          <div class="hint">
            ${
              accounts.length > 0
                ? "Choose one or more Family Treasury accounts whose transactions should be shown."
                : "No Family Treasury balance sensors were found yet. Create an account first."
            }
          </div>
        </div>
        <div class="field">
          <label for="page_size">Transactions per page</label>
          <input
            id="page_size"
            name="page_size"
            type="number"
            min="1"
            value="${effectivePageSize}"
          />
        </div>
        <label class="toggle" for="enable_pagination">
          <input
            id="enable_pagination"
            name="enable_pagination"
            type="checkbox"
            ${enablePagination ? "checked" : ""}
          />
          <span>Enable pagination controls</span>
        </label>
        ${
          enablePagination
            ? `<label class="toggle" for="allow_page_size_override">
                 <input
                   id="allow_page_size_override"
                   name="allow_page_size_override"
                   type="checkbox"
                   ${allowPageSizeOverride ? "checked" : ""}
                 />
                 <span>Allow viewers to change page size</span>
               </label>`
            : ""
        }
        ${
          allowPageSizeOverride
            ? `<div class="field">
                 <label for="page_size_options">Page size options</label>
                 <input
                   id="page_size_options"
                   name="page_size_options"
                   type="text"
                   value="${this._escapeHtml(pageSizeOptions.join(", "))}"
                 />
                 <div class="hint">Comma-separated values, for example 5, 10, 25, 50.</div>
               </div>`
            : ""
        }
        <div class="field">
          <div class="group-title">Transaction types</div>
          <div class="hint">
            New cards default to all transaction types except interest accrual.
          </div>
          <div class="types-grid">
            ${TRANSACTION_TYPES.map(
              (type) => `<label class="type-option" for="type-${type}">
                <input
                  id="type-${type}"
                  type="checkbox"
                  value="${type}"
                  ${selectedTypes.includes(type) ? "checked" : ""}
                />
                <span>${this._escapeHtml(
                  localizedTransactionTypeLabel(
                    this._hass,
                    type,
                    TRANSACTION_TYPE_FILTER_LABEL_KEYS,
                    TRANSACTION_TYPE_FILTER_LABELS,
                  ),
                )}</span>
              </label>`,
            ).join("")}
          </div>
        </div>
      </div>
    `;

    this.shadowRoot.querySelectorAll("input, select").forEach((element) => {
      if (
        element.type === "checkbox" &&
        element.value &&
        element.id.startsWith("account-")
      ) {
        element.addEventListener("change", this._handleAccountChange);
        return;
      }

      if (
        element.type === "checkbox" &&
        element.value &&
        TRANSACTION_TYPES.includes(element.value)
      ) {
        element.addEventListener("change", this._handleTypeChange);
        return;
      }

      element.addEventListener("change", this._handleInputChange);
    });
  }

  _escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
}

if (!customElements.get(CARD_ELEMENT_NAME)) {
  customElements.define(CARD_ELEMENT_NAME, FamilyTreasuryTransactionsCard);
}

if (!customElements.get(CARD_EDITOR_ELEMENT_NAME)) {
  customElements.define(
    CARD_EDITOR_ELEMENT_NAME,
    FamilyTreasuryTransactionsCardEditor,
  );
}

window.customCards = window.customCards || [];
if (
  !window.customCards.find(
    (card) => card.type === "family-treasury-transactions",
  )
) {
  window.customCards.push({
    type: "family-treasury-transactions",
    name: "Family Treasury Transactions",
    description:
      "Shows paged recent transactions for a Family Treasury account_id.",
    preview: true,
  });
}
