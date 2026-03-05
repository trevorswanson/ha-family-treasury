class FamilyTreasuryTransactionsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._transactions = [];
    this._loading = false;
    this._error = null;
    this._offset = 0;
    this._nextOffset = null;
    this._total = 0;
    this._requestId = 0;
    this._lastFetchAt = 0;
    this._pageSize = 10;
  }

  setConfig(config) {
    if (!config || typeof config.account_id !== "string" || !config.account_id.trim()) {
      throw new Error("`account_id` is required");
    }

    const pageSize = Number.parseInt(config.page_size ?? 10, 10);
    if (!Number.isFinite(pageSize) || pageSize < 1) {
      throw new Error("`page_size` must be a positive integer");
    }

    const enablePagination = config.enable_pagination !== false;
    const allowPageSizeOverride =
      enablePagination && config.allow_page_size_override === true;
    const pageSizeOptions = this._sanitizePageSizeOptions(
      config.page_size_options,
      pageSize,
    );
    const types = this._normalizeTypes(config.types ?? null);

    this._config = {
      title: config.title ?? "Recent Transactions",
      account_id: config.account_id.trim(),
      page_size: pageSize,
      enable_pagination: enablePagination,
      allow_page_size_override: allowPageSizeOverride,
      page_size_options: pageSizeOptions,
      types,
    };

    this._pageSize = pageSize;

    this._offset = 0;
    this._nextOffset = null;
    this._error = null;
    this._transactions = [];
    this._total = 0;
    this._render();

    if (this._hass) {
      void this._fetchTransactions({ offset: 0, allowClamp: true });
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) {
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

  _sanitizePageSizeOptions(rawOptions, fallback) {
    const defaults = [5, 10, 25, 50];
    const options = Array.isArray(rawOptions) ? rawOptions : defaults;
    const sanitized = options
      .map((value) => Number.parseInt(value, 10))
      .filter((value, index, all) => Number.isFinite(value) && value > 0 && all.indexOf(value) === index)
      .sort((a, b) => a - b);

    if (!sanitized.includes(fallback)) {
      sanitized.push(fallback);
      sanitized.sort((a, b) => a - b);
    }

    return sanitized;
  }

  _effectivePageSize() {
    if (!this._config.allow_page_size_override) {
      return this._config.page_size;
    }
    return this._pageSize;
  }

  _normalizeTypes(rawTypes) {
    if (rawTypes === null || rawTypes === undefined) {
      return null;
    }

    const allowed = [
      "deposit",
      "withdraw",
      "adjustment",
      "interest_accrual",
      "interest_payout",
      "transfer_out",
      "transfer_in",
    ];
    const values = Array.isArray(rawTypes) ? rawTypes : [rawTypes];
    const normalized = values
      .map((value) => String(value).trim())
      .filter((value, index, all) => value.length > 0 && all.indexOf(value) === index);
    if (normalized.length === 0) {
      return null;
    }

    const invalid = normalized.filter((value) => !allowed.includes(value));
    if (invalid.length > 0) {
      throw new Error(
        `\`types\` contains unsupported values: ${invalid.join(", ")}. Valid \`types\` are: ${allowed.join(", ")}`,
      );
    }

    return normalized;
  }

  async _fetchTransactions({ offset, allowClamp }) {
    if (!this._hass || !this._config) {
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
      const transactions = Array.isArray(response.transactions) ? response.transactions : [];
      const total = Number.isInteger(response.total) ? response.total : transactions.length;
      const normalizedOffset = Number.isInteger(response.offset) ? response.offset : requestOffset;
      const nextOffset =
        response.next_offset === null || response.next_offset === undefined
          ? null
          : Number.parseInt(response.next_offset, 10);

      if (allowClamp && this._config.enable_pagination && total > 0 && normalizedOffset >= total) {
        const lastOffset = Math.floor((total - 1) / pageSize) * pageSize;
        if (lastOffset !== normalizedOffset) {
          this._loading = false;
          await this._fetchTransactions({ offset: lastOffset, allowClamp: false });
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
        const type = this._escapeHtml(String(tx.type ?? ""));
        const description = this._escapeHtml(String(tx.meta?.description ?? ""));
        const amount = this._escapeHtml(
          String(tx.formatted_amount ?? tx.amount_major ?? tx.amount_minor ?? ""),
        );
        return `<tr>
          <td>${occurredAt}</td>
          <td>${type}</td>
          <td>${description || "-"}</td>
          <td class="amount">${amount}</td>
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
            <div class="meta">
              Account: <code>${this._escapeHtml(this._config.account_id)}</code>
            </div>
          </div>
          <button id="refresh" type="button">Refresh</button>
        </div>
        ${
          this._error
            ? `<div class="error">${this._escapeHtml(this._error)}</div>`
            : ""
        }
        ${
          this._transactions.length === 0 && !this._loading && !this._error
            ? `<div class="empty">No transactions found.</div>`
            : `<div class="content">
                <table>
                  <thead>
                    <tr>
                      <th>Occurred</th>
                      <th>Type</th>
                      <th>Description</th>
                      <th style="text-align:right;">Amount</th>
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
      if (this._loading) {
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
    return value
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
}

if (!customElements.get("family-treasury-transactions")) {
  customElements.define(
    "family-treasury-transactions",
    FamilyTreasuryTransactionsCard,
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
