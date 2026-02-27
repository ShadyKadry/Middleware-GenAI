import {
  getAvailableCorpora,
  getAvailableServers,
  getAvailableToolsList,
  getSelectedCorpusIdsForAutoSearch,
  getSelectedCorpusIdsForUserCreation,
  getSelectedServers,
  getSelectedTools,
  setSelectedCorpusIdsForAutoSearch,
  setSelectedCorpusIdsForUserCreation,
  setSelectedServers,
  setSelectedTools
} from "../session/state.js";

export const ADMIN_PANELS = [
  "panelDataUpload",
  "panelUserCreation",
  "panelServerRegistration",
];


export function updateEnabledMCPToolsCount() {
  const el = document.getElementById("toolsEnabledCount");
  if (el) el.textContent = String(getSelectedTools().size);
}


/**
 * Toggles the loading state for the auto-search corpora UI.
 * Shows a status message and hides the corpora container while loading.
 * @param {boolean} isLoading - Whether loading is in progress
 * @param {string} [msg="Loading…"] - Optional loading message
 */
export function setAutoSearchCorporaLoading(isLoading, msg = "Loading…") {
  const statusEl = document.getElementById("asCheckboxesStatus");
  const containerEl = document.getElementById("asCorporaContainer");

  if (statusEl) statusEl.textContent = isLoading ? msg : "";
  if (containerEl) containerEl.style.display = isLoading ? "none" : "";
}


/**
 * Shows the specified panel elements and hides all others.
 * @param {string} targets - Comma-separated list of element IDs to display
 */
export function renderPanels(targets) {
  document.querySelectorAll(".panel").forEach(p => p.classList.add("hidden"));

  targets.split(",").forEach(id => {
    const el = document.getElementById(id.trim());
    if (el) el.classList.remove("hidden");
  });
}


/**
 * Renders the auto-search corpora checkbox list.
 * Loads available corpora, creates a checkbox for each, syncs the selected
 * IDs with a hidden input, and updates selection state on change.
 */
export function renderCorporaCheckboxesAutoSearch() {
  const statusEl = document.getElementById("asCheckboxesStatus");
  const containerEl = document.getElementById("asCorporaContainer");
  const listEl = document.getElementById("asCorporaList");
  const hiddenEl = document.getElementById("asCorpora");
  if (!listEl || !hiddenEl) return;

  if (statusEl) statusEl.textContent = "Loading…";
  if (containerEl) containerEl.style.display = "none";


  listEl.innerHTML = "";
  const selectedCorpusIdsForAutoSearch = getSelectedCorpusIdsForAutoSearch();

  const corpora = [...getAvailableCorpora()].map(String).sort((a, b) => a.localeCompare(b));

  if (corpora.length === 0) {
    listEl.innerHTML = `<div class="muted">No collections available.</div>`;
    hiddenEl.value = "[]";
    return;
  }

  // show UI now that we have corpora
  if (statusEl) statusEl.textContent = "";
  if (containerEl) containerEl.style.display = "";

  for (const corpusId of corpora) {
    const id = `asCorpus_${cssSafeId(corpusId)}`;

    const row = document.createElement("label");
    row.className = "asCorpus-item"; // TODO replace. but why?
    row.htmlFor = id;

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.value = corpusId;

    // checked = selected-for-user-creation
    cb.checked = selectedCorpusIdsForAutoSearch.has(corpusId);

    cb.addEventListener("change", () => { // todo: move to events.js ?
      // mutate selected set, not available
      if (cb.checked) selectedCorpusIdsForAutoSearch.add(corpusId);
      else selectedCorpusIdsForAutoSearch.delete(corpusId);

      hiddenEl.value = JSON.stringify([...selectedCorpusIdsForAutoSearch]);
      setSelectedCorpusIdsForAutoSearch(selectedCorpusIdsForAutoSearch);
    });

    const text = document.createElement("span");
    text.textContent = corpusId;

    row.appendChild(cb);
    row.appendChild(text);
    listEl.appendChild(row);
  }

  // initialize hidden field
  hiddenEl.value = JSON.stringify([...selectedCorpusIdsForAutoSearch]);
}


/**
 * Renders the corpora checkbox list in the user creation panel.
 * Loads available corpora, creates a checkbox for each, syncs the selected
 * IDs with a hidden input, and updates selection state on change.
 */
export function renderCorporaCheckboxesUserCreation() {
  const listEl = document.getElementById("cuCorporaList");
  const hiddenEl = document.getElementById("cuCorpora");
  if (!listEl || !hiddenEl) return;

  listEl.innerHTML = "";
  const selectedCorpusIdsForUserCreation = getSelectedCorpusIdsForUserCreation();

  const corpora = [...getAvailableCorpora()].map(String).sort((a, b) => a.localeCompare(b));

  if (corpora.length === 0) {
    listEl.innerHTML = `<div class="muted">No collections available.</div>`;
    hiddenEl.value = "[]";
    return;
  }

  for (const corpusId of corpora) {
    const id = `cuCorpus_${cssSafeId(corpusId)}`;

    const row = document.createElement("label");
    row.className = "cutool-item"; // TODO replace. but why?
    row.htmlFor = id;

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.value = corpusId;

    // checked = selected-for-user-creation
    cb.checked = selectedCorpusIdsForUserCreation.has(corpusId);

    cb.addEventListener("change", () => {
      // mutate selected set, not available
      if (cb.checked) selectedCorpusIdsForUserCreation.add(corpusId);
      else selectedCorpusIdsForUserCreation.delete(corpusId);

      hiddenEl.value = JSON.stringify([...selectedCorpusIdsForUserCreation]);
      setSelectedCorpusIdsForUserCreation(selectedCorpusIdsForUserCreation);
    });

    const text = document.createElement("span");
    text.textContent = corpusId;

    row.appendChild(cb);
    row.appendChild(text);
    listEl.appendChild(row);
  }

  // initialize hidden field
  hiddenEl.value = JSON.stringify([...selectedCorpusIdsForUserCreation]);
}


/**
 * Converts a value into a DOM-safe ID by replacing invalid characters with "_".
 */
function cssSafeId(value) {
  return String(value).replace(/[^a-zA-Z0-9_-]/g, "_");
}


/**
 * Renders the MCP tool checkboxes for the chat form and updates
 * the selected tools set and enabled tools count on change.
 */
export function renderMCPToolCheckboxesForChatForm() {
  const toolsList = document.getElementById("toolsList");
  if (!toolsList) return;

  toolsList.innerHTML = "";
  const selectedTools = getSelectedTools();

  for (const t of getAvailableToolsList()) {
    const li = document.createElement("li");
    li.className = "tools-item";

    const label = document.createElement("label");
    label.className = "tools-label";

    const cb = document.createElement("input");
    cb.type = "checkbox";

    cb.checked = selectedTools.has(t.name);
    cb.addEventListener("change", () => {
      if (cb.checked) selectedTools.add(t.name);
      else selectedTools.delete(t.name);
      setSelectedTools(selectedTools);
      updateEnabledMCPToolsCount();
    });

    const meta = document.createElement("div");
    meta.className = "tools-meta";

    const name = document.createElement("div");
    name.className = "tools-name";
    name.textContent = t.name;

    const desc = document.createElement("div");
    desc.className = "tools-desc";
    desc.textContent = t.description || "";

    meta.appendChild(name);
    if (t.description) meta.appendChild(desc);

    label.appendChild(cb);
    label.appendChild(meta);
    li.appendChild(label);
    toolsList.appendChild(li);
  }

  updateEnabledMCPToolsCount();
}


/**
 * Appends a chat message to #chatLog and scrolls to the bottom.
 * Bot messages support sanitized Markdown; others are plain text.
 * @param {string} role - Message sender (e.g., "bot", "user")
 * @param {string} text - Message content
 */
export function renderChatMessage(role, text) {
  const chatLog = document.getElementById("chatLog");
  if (!chatLog) return;

  const row = document.createElement("div");
  row.className = `chat-msg ${role}`;

  if (role === "bot") {
    const html = DOMPurify.sanitize(marked.parse(text || ""));
    row.innerHTML = html;
  } else {
    row.textContent = text || "";
  }

  chatLog.appendChild(row);
  chatLog.scrollTop = chatLog.scrollHeight;
}


export function renderDatabaseModels(payload) {
  const databaseEl = document.getElementById("uploadDatabaseModel")
  if (!databaseEl) return;

  // fallback UI if payload missing
  if (!payload) {
    databaseEl.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "Database models unavailable";
    databaseEl.appendChild(opt);
  }

  const models = Array.isArray(payload.models) ? payload.models : [];
  const defaultId = typeof payload.defaultId === "string" ? payload.defaultId : "";

  databaseEl.innerHTML = "";

  for (const model of models) {
    const opt = document.createElement("option");
    opt.value = String(model.id ?? "");
    opt.textContent = String(model.label || model.id || "");
    databaseEl.appendChild(opt);
  }

  // Apply default (only if it exists in the options)
  if (defaultId) {
    const has = [...databaseEl.options].some(o => o.value === defaultId);
    if (has) databaseEl.value = defaultId;
  }
}


// private access
function getEmbeddingModelSelects() {
  return [
    document.getElementById("uploadEmbeddingModel"),
    document.getElementById("chatEmbeddingModel"),
  ].filter(Boolean);
}

export function renderEmbeddingModels(payload) {
  const selects = getEmbeddingModelSelects();
  if (selects.length === 0) return;

  // fallback UI if payload missing
  if (!payload) {
    for (const select of selects) {
      select.innerHTML = "";
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "Embedding models unavailable";
      select.appendChild(opt);
    }
    return;
  }

  const models = Array.isArray(payload.models) ? payload.models : [];
  const defaultId = typeof payload.defaultId === "string" ? payload.defaultId : "";

  for (const select of selects) {
    select.innerHTML = "";

    for (const model of models) {
      const opt = document.createElement("option");
      opt.value = String(model.id ?? "");
      opt.textContent = String(model.label || model.id || "");
      select.appendChild(opt);
    }
  }

  // Apply default (only if it exists in the options)
  if (defaultId) {
    for (const select of selects) {
      const has = [...select.options].some(o => o.value === defaultId);
      if (has) select.value = defaultId;
    }
  }
}


/**
 * Renders user-specific UI state (role label, sidebar visibility,
 * and admin-only elements) based on the current user and permissions.
 */
export function renderMe({ user, role, isAdmin }) {
  // sidebar role label
  const sidebarRole = document.getElementById("sidebarRole");
  if (sidebarRole) sidebarRole.textContent = `Role: ${role || ""}`;

  // show sidebar
  const sidebar = document.getElementById("showSidebar");
  if (sidebar) sidebar.classList.remove("hidden");

  // hide/show admin-only buttons
  document.querySelectorAll(".admin-only").forEach(el => {
    el.classList.toggle("hidden", !isAdmin);
  });

  // defense-in-depth: hide admin-only panels for non-admin
  if (!isAdmin) {
    for (const id of ADMIN_PANELS) {
      const el = document.getElementById(id);
      if (el) el.classList.add("hidden");
    }
  }
}


/**
 * Renders the MCP server checkboxes for user creation and keeps the
 * selected servers synced with the hidden input field.
 */
export function renderMCPServerCheckboxesForUserCreation() {
  const listEl = document.getElementById("cuToolsList");
  const hiddenEl = document.getElementById("cuTools");
  if (!listEl || !hiddenEl) return;

  listEl.innerHTML = "";

  // derive servers (logic layer)
  const servers = [...getAvailableServers()].sort((a, b) => a.localeCompare(b));

  if (servers.length === 0) {
    listEl.innerHTML = `<div class="muted">No servers available.</div>`;
    hiddenEl.value = "[]";
    return;
  }

  for (const server of servers) {
    const id = `cuServer_${cssSafeId(server)}`;
    let selectedServers = getSelectedServers();

    const row = document.createElement("label");
    row.className = "cutool-item";
    row.htmlFor = id;

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.value = server;
    cb.checked = selectedServers.has(server);

    cb.addEventListener("change", () => {
      if (cb.checked) selectedServers.add(server);
      else selectedServers.delete(server);

      hiddenEl.value = JSON.stringify([...selectedServers]);
    });
    setSelectedServers(selectedServers);

    const text = document.createElement("span");
    text.textContent = server;

    row.appendChild(cb);
    row.appendChild(text);
    listEl.appendChild(row);
  }
}


/**
 * Toggles MCP transport-specific form fields based on the selected transport type.
 */
export function renderMcpTransportFields() {
  const transport = document.getElementById("mcpTransport")?.value || "stdio";
  const stdioFields = document.getElementById("mcpStdioFields");
  const remoteFields = document.getElementById("mcpRemoteFields");
  const isStdio = transport === "stdio";
  if (stdioFields) stdioFields.classList.toggle("hidden", !isStdio);
  if (remoteFields) remoteFields.classList.toggle("hidden", isStdio);
}
