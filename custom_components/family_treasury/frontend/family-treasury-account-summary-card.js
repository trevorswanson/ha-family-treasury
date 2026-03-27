const SUMMARY_CARD_TYPE = "custom:family-treasury-account-summary";
const SUMMARY_CARD_ELEMENT_NAME = "family-treasury-account-summary";
const SUMMARY_CARD_EDITOR_ELEMENT_NAME =
  "family-treasury-account-summary-editor";

function summaryLocalizedLabel(hass, key, fallback) {
  if (typeof hass?.localize === "function") {
    const localized = hass.localize(
      `component.family_treasury.common.account_summary.${key}`,
    );
    if (
      localized &&
      localized !== `component.family_treasury.common.account_summary.${key}`
    ) {
      return localized;
    }
  }
  return fallback;
}

function collectSummaryAccounts(states) {
  const accounts = [];

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

    const displayName = stateObj.attributes.display_name;
    const friendlyName = stateObj.attributes.friendly_name;
    const label =
      typeof displayName === "string" && displayName.trim()
        ? displayName.trim()
        : typeof friendlyName === "string" && friendlyName.trim()
          ? friendlyName.replace(/\s+Balance$/, "").trim()
          : accountId;

    accounts.push({
      account_id: accountId,
      label,
      parent_account_id: stateObj.attributes.parent_account_id ?? null,
      active: stateObj.attributes.active !== false,
      formatted_balance: stateObj.attributes.formatted_balance ?? String(stateObj.state ?? ""),
      formatted_pending_interest:
        stateObj.attributes.formatted_pending_interest ?? "",
      next_interest_payout_at:
        stateObj.attributes.next_interest_payout_at ?? null,
    });
  });

  return accounts.sort((left, right) => left.label.localeCompare(right.label));
}

function summaryParentCandidates(accounts) {
  const childCounts = new Map();
  accounts.forEach((account) => {
    if (!account.active || !account.parent_account_id) {
      return;
    }
    childCounts.set(
      account.parent_account_id,
      (childCounts.get(account.parent_account_id) ?? 0) + 1,
    );
  });

  const candidates = accounts.filter(
    (account) => account.active && childCounts.has(account.account_id),
  );
  if (candidates.length > 0) {
    return candidates;
  }

  return accounts.filter(
    (account) => account.active && account.parent_account_id === null,
  );
}

function summaryOptionsSignature(options) {
  return options
    .map((option) => `${option.account_id}:${option.label}`)
    .join("|");
}

class FamilyTreasuryAccountSummaryCard extends HTMLElement {
  static async getConfigElement() {
    return document.createElement(SUMMARY_CARD_EDITOR_ELEMENT_NAME);
  }

  static async getStubConfig(hass) {
    const parentCandidates = summaryParentCandidates(
      collectSummaryAccounts(hass?.states ?? {}),
    );

    return {
      type: SUMMARY_CARD_TYPE,
      title: "Account Summary",
      parent_account_id: parentCandidates[0]?.account_id ?? "",
      show_pending_interest: true,
      show_next_interest_payout: true,
    };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._configError = null;
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Card configuration is required");
    }

    const parentAccountId =
      typeof config.parent_account_id === "string"
        ? config.parent_account_id.trim()
        : "";

    this._config = {
      title: config.title ?? "Account Summary",
      parent_account_id: parentAccountId,
      show_pending_interest: config.show_pending_interest !== false,
      show_next_interest_payout: config.show_next_interest_payout !== false,
    };
    this._configError = parentAccountId ? null : "`parent_account_id` is required";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config) {
      this._render();
    }
  }

  getCardSize() {
    return 4;
  }

  _accounts() {
    return collectSummaryAccounts(this._hass?.states ?? {});
  }

  _rows() {
    const accounts = this._accounts();
    const parent = accounts.find(
      (account) => account.account_id === this._config.parent_account_id,
    );
    if (!parent) {
      return { parent: null, rows: [] };
    }

    const children = accounts
      .filter(
        (account) =>
          account.active && account.parent_account_id === parent.account_id,
      )
      .sort((left, right) => left.label.localeCompare(right.label));

    return { parent, rows: [parent, ...children] };
  }

  _formatDate(raw) {
    if (!raw) {
      return "-";
    }

    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) {
      return this._escapeHtml(String(raw));
    }

    return this._escapeHtml(parsed.toLocaleDateString());
  }

  _escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _render() {
    if (!this._config) {
      return;
    }

    const accounts = this._accounts();
    const parentCandidates = summaryParentCandidates(accounts);
    const { parent, rows } = this._rows();
    const errorMessage =
      this._configError ??
      (this._config.parent_account_id && !parent
        ? "Selected parent account was not found."
        : null);
    const showPendingInterest = this._config.show_pending_interest;
    const showNextInterestPayout = this._config.show_next_interest_payout;

    const accountLabel = summaryLocalizedLabel(
      this._hass,
      "account",
      "Account",
    );
    const balanceLabel = summaryLocalizedLabel(
      this._hass,
      "balance",
      "Balance",
    );
    const pendingInterestLabel = summaryLocalizedLabel(
      this._hass,
      "pending_interest",
      "Pending Interest",
    );
    const nextPayoutLabel = summaryLocalizedLabel(
      this._hass,
      "next_interest_payout",
      "Next Interest Payout",
    );

    const renderedRows = rows
      .map((account) => {
        const slugSuffix =
          account.label === account.account_id
            ? ""
            : `<div class="account-meta"><code>${this._escapeHtml(
                account.account_id,
              )}</code></div>`;
        return `<tr>
          <td>
            <div class="account-name">${this._escapeHtml(account.label)}</div>
            ${slugSuffix}
          </td>
          <td class="amount">${this._escapeHtml(account.formatted_balance || "-")}</td>
          ${
            showPendingInterest
              ? `<td class="amount">${this._escapeHtml(
                  account.formatted_pending_interest || "-",
                )}</td>`
              : ""
          }
          ${
            showNextInterestPayout
              ? `<td>${this._formatDate(account.next_interest_payout_at)}</td>`
              : ""
          }
        </tr>`;
      })
      .join("");

    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 0; }
        .header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          padding: 16px 16px 8px 16px;
        }
        .title { font-size: 1.1rem; font-weight: 600; }
        .meta { color: var(--secondary-text-color); font-size: 0.88rem; }
        .content { padding: 0 16px 16px 16px; }
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
        table {
          width: 100%;
          border-collapse: collapse;
          font-size: 0.92rem;
        }
        th, td {
          padding: 10px 6px;
          border-bottom: 1px solid var(--divider-color);
          text-align: left;
          vertical-align: top;
        }
        th {
          color: var(--secondary-text-color);
          font-weight: 600;
        }
        td.amount {
          text-align: right;
          font-variant-numeric: tabular-nums;
          white-space: nowrap;
        }
        .account-name {
          font-weight: 600;
        }
        .account-meta {
          margin-top: 2px;
          color: var(--secondary-text-color);
          font-size: 0.8rem;
        }
      </style>
      <ha-card>
        <div class="header">
          <div>
            <div class="title">${this._escapeHtml(this._config.title)}</div>
          </div>
        </div>
        ${errorMessage ? `<div class="error">${this._escapeHtml(errorMessage)}</div>` : ""}
        ${
          !errorMessage && rows.length === 0
            ? `<div class="empty">No active child accounts found for this parent.</div>`
            : !errorMessage
              ? `<div class="content">
                   <table>
                     <thead>
                       <tr>
                         <th>${this._escapeHtml(accountLabel)}</th>
                         <th style="text-align:right;">${this._escapeHtml(balanceLabel)}</th>
                         ${
                           showPendingInterest
                             ? `<th style="text-align:right;">${this._escapeHtml(
                                 pendingInterestLabel,
                               )}</th>`
                             : ""
                         }
                         ${
                           showNextInterestPayout
                             ? `<th>${this._escapeHtml(nextPayoutLabel)}</th>`
                             : ""
                         }
                       </tr>
                     </thead>
                     <tbody>${renderedRows}</tbody>
                   </table>
                 </div>`
              : ""
        }
      </ha-card>
    `;
  }
}

class FamilyTreasuryAccountSummaryCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = { type: SUMMARY_CARD_TYPE };
    this._parentOptionsCache = [];
    this._parentOptionsSignature = null;
  }

  set hass(hass) {
    this._hass = hass;
    const nextOptions = summaryParentCandidates(
      collectSummaryAccounts(hass?.states ?? {}),
    );
    const nextSignature = summaryOptionsSignature(nextOptions);

    if (
      this._parentOptionsSignature === nextSignature &&
      this.shadowRoot.innerHTML !== ""
    ) {
      return;
    }

    this._parentOptionsCache = nextOptions;
    this._parentOptionsSignature = nextSignature;
    this._render();
  }

  setConfig(config) {
    this._config = {
      type: SUMMARY_CARD_TYPE,
      ...config,
    };
    this._render();
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

    this._emitConfig({
      ...this._config,
      [field]:
        event.target.type === "checkbox"
          ? event.target.checked
          : event.target.value,
    });
  };

  _render() {
    const options = this._parentOptionsCache;

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
        .field label {
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
        .toggle {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .toggle input[type="checkbox"] {
          margin: 0;
          width: 16px;
          height: 16px;
          padding: 0;
        }
      </style>
      <div class="form">
        <div class="field">
          <label for="title">Title</label>
          <input
            id="title"
            name="title"
            type="text"
            value="${this._escapeHtml(String(this._config.title ?? "Account Summary"))}"
          />
        </div>
        <div class="field">
          <label for="parent_account_id">Parent account</label>
          <select id="parent_account_id" name="parent_account_id">
            <option value="">Select a parent account</option>
            ${options
              .map(
                (account) =>
                  `<option value="${this._escapeHtml(account.account_id)}" ${
                    account.account_id === this._config.parent_account_id
                      ? "selected"
                      : ""
                  }>${this._escapeHtml(account.label)} (${this._escapeHtml(
                    account.account_id,
                  )})</option>`,
              )
              .join("")}
          </select>
          <div class="hint">
            ${
              options.length > 0
                ? "Shows the selected parent account plus all active direct child accounts."
                : "No eligible parent accounts were found yet."
            }
          </div>
        </div>
        <label class="toggle" for="show_pending_interest">
          <input
            id="show_pending_interest"
            name="show_pending_interest"
            type="checkbox"
            ${this._config.show_pending_interest !== false ? "checked" : ""}
          />
          <span>Show pending interest</span>
        </label>
        <label class="toggle" for="show_next_interest_payout">
          <input
            id="show_next_interest_payout"
            name="show_next_interest_payout"
            type="checkbox"
            ${this._config.show_next_interest_payout !== false ? "checked" : ""}
          />
          <span>Show next interest payout date</span>
        </label>
      </div>
    `;

    this.shadowRoot.querySelectorAll("input, select").forEach((element) => {
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

if (!customElements.get(SUMMARY_CARD_ELEMENT_NAME)) {
  customElements.define(
    SUMMARY_CARD_ELEMENT_NAME,
    FamilyTreasuryAccountSummaryCard,
  );
}

if (!customElements.get(SUMMARY_CARD_EDITOR_ELEMENT_NAME)) {
  customElements.define(
    SUMMARY_CARD_EDITOR_ELEMENT_NAME,
    FamilyTreasuryAccountSummaryCardEditor,
  );
}

window.customCards = window.customCards || [];
if (
  !window.customCards.find(
    (card) => card.type === "family-treasury-account-summary",
  )
) {
  window.customCards.push({
    type: "family-treasury-account-summary",
    name: "Family Treasury Account Summary",
    description:
      "Shows a parent account and its active child accounts with balances and interest details.",
    preview: true,
  });
}
