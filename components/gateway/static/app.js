const CHAT_SEARCH_STORAGE_KEY = "chat_presearch_v1";
const SELECTED_TOOLS_STORAGE_KEY = "enabled_tools_v1";
const AVAILABLE_TOOLS_STORAGE_KEY = "available_tools_v1";
const AVAILABLE_CORPORA_STORAGE_KEY = "available_corpora_v1"
const SELECTED_CORPORA_FOR_USER_KEY   = "selected_corpora_for_user";
const SELECTED_CORPORA_FOR_SEARCH_KEY = "selected_corpora_for_search";

let selectedTools = new Set();
let selectedCorpusIdsForAutoSearch = new Set();
let selectedCorpusIdsForUserCreation = new Set();
let availableTools = new Set();
let availableCorpora = new Set();
let availableCorporaList = [];

let CURRENT_USER = null;
let CURRENT_ROLE = null;
let CHAT_SESSION_ID = null;

/*
  --- # HELPER FUNCTIONS # ---
 */

const ADMIN_PANELS = [
  "panelDataUpload",
  "panelUserCreation",
  "panelServerRegistration",
];

/*** - - - SHOW SIDEBAR DYNAMICALLY BASED ON USER-ROLE - - - ***/
function showPanel(targets) {
  document.querySelectorAll(".panel").forEach(p => p.classList.add("hidden"));

  targets.split(",").forEach(id => {
    const el = document.getElementById(id.trim());
    if (el) el.classList.remove("hidden");
  });
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-target]");
  if (!btn) return;

  const targets = btn.dataset.target;
  const isAdmin = ["admin", "super-admin"].includes(CURRENT_ROLE);
  if (!isAdmin) {
    const wantsAdminPanel = targets
      .split(",")
      .map(s => s.trim())
      .some(id => ADMIN_PANELS.includes(id));
    if (wantsAdminPanel) return;
  }

  document.querySelectorAll("#sidebar-actions button")
    .forEach(b => b.classList.remove("active"));
  btn.classList.add("active");

  showPanel(targets);
});


/** LOAD_ME **/

async function loadMe() {
  const res = await fetch("/api/me");
  if (!res.ok) return;

  const data = await res.json().catch(() => null);
  if (!data) return;

  CURRENT_USER = data.user.toLowerCase();
  CURRENT_ROLE = data.role.toLowerCase();
  const isAdmin = CURRENT_ROLE === "admin" || CURRENT_ROLE === "super-admin";

  const sidebar = document.getElementById("showSidebar");
  if (sidebar) sidebar.classList.remove("hidden");

  // hide/show admin-only BUTTONS
  document.querySelectorAll(".admin-only").forEach(el =>
    el.classList.toggle("hidden", !isAdmin)
  );

  // hide admin-only PANELS too (defense in depth)
  if (!isAdmin) {
    ADMIN_PANELS.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.classList.add("hidden");
    });
  } else {
    renderMCPServerCheckboxes();
    setAutoSearchCorporaLoading(true);
  }
  // everyone starts here
  showPanel("panelAutoSearch,panelChat,panelTools");

  if (isAdmin) {
    await loadEmbeddingModels();
  }
}


/*** - - - LOGIN - - - ***/

const form = document.getElementById("loginForm");
if (form) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await fetch("/api/login", {
      method: "POST",
      body: new FormData(form),
    });
    if (res.ok) window.location.href = "/app";
    else document.getElementById("msg").textContent = "Login failed! Wrong username or password.";
  });
}

const logoutBtn = document.getElementById("logoutBtn");
if (logoutBtn) {
  logoutBtn.addEventListener("click", async () => {
    await fetch("/api/logout", { method: "POST" });
    window.location.href = "/";
  });
}

// ---- tool selection state ---- TODO persisted, but only in memory not in DB
function loadSelectedTools() {
  try {
    const raw = localStorage.getItem(SELECTED_TOOLS_STORAGE_KEY);
    if (!raw) return;
    const arr = JSON.parse(raw);
    if (Array.isArray(arr)) selectedTools = new Set(arr);
  } catch (_) {}
}
function loadAvailableTools() {
  try {
    const raw = localStorage.getItem(AVAILABLE_TOOLS_STORAGE_KEY);
    if (!raw) return;
    const arr = JSON.parse(raw);
    if (Array.isArray(arr)) availableTools = new Set(arr);
  } catch (_) {}
}

function getAvailableServers() {
  return new Set(
    [...availableTools].map(t => t.split(".")[0])
  );
}

function loadAvailableCorpora() {
    try {
    const raw = localStorage.getItem(AVAILABLE_CORPORA_STORAGE_KEY);
    if (!raw) return;
    const arr = JSON.parse(raw);
    if (Array.isArray(arr)) availableCorpora = new Set(arr);
  } catch (_) {}
}


function saveSelectedCorpusIdsForAutoSearch() {
  localStorage.setItem("selectedCorpusIdsForAutoSearch", JSON.stringify([...selectedCorpusIdsForAutoSearch]));
}

function saveSelectedCorpusIdsForUserCreation() {
  localStorage.setItem("selectedCorpusIdsForUserCreation", JSON.stringify([...selectedCorpusIdsForUserCreation]));
}

function loadSelectedCorpusIdsForAutoSearch() {
  try {
    const raw = localStorage.getItem("selectedCorpusIdsForAutoSearch");
    selectedCorpusIdsForAutoSearch = new Set(raw ? JSON.parse(raw) : []);
  } catch {
    selectedCorpusIdsForAutoSearch = new Set();
  }
}
function loadSelectedCorpusIdsForUserCreation() {
  try {
    const raw = localStorage.getItem("selectedCorpusIdsForUserCreation");
    selectedCorpusIdsForUserCreation = new Set(raw ? JSON.parse(raw) : []);
  } catch {
    selectedCorpusIdsForUserCreation = new Set();
  }
}


function saveSelectedTools() {
  try {
    localStorage.setItem(SELECTED_TOOLS_STORAGE_KEY, JSON.stringify([...selectedTools]));
  } catch (_) {}
}

function saveAvailableTools() {
  try {
    localStorage.setItem(AVAILABLE_TOOLS_STORAGE_KEY, JSON.stringify([...availableTools]));
  } catch (E) {console.log(E)}
}

function saveAvailableCorpora() {
  try {
    localStorage.setItem(AVAILABLE_CORPORA_STORAGE_KEY, JSON.stringify([...availableCorpora]))
  } catch (E) {console.log(E)}
}

function updateEnabledCount() {
  const el = document.getElementById("toolsEnabledCount");
  if (el) el.textContent = String(selectedTools.size);
}

function loadChatSearchSettings() {
  try {
    const raw = localStorage.getItem(CHAT_SEARCH_STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (!data || typeof data !== "object") return;

    const toggle = document.getElementById("autoSearchToggle");
    const corpus = document.getElementById("chatCorpusId");
    const model = document.getElementById("chatEmbeddingModel");
    const topk = document.getElementById("chatSearchK");

    if (toggle && typeof data.enabled === "boolean") toggle.checked = data.enabled;
    if (corpus && typeof data.corpus_id === "string") corpus.value = data.corpus_id;
    if (model && typeof data.embedding_model === "string") model.value = data.embedding_model;
    if (topk && typeof data.search_k === "number") topk.value = String(data.search_k);
  } catch (_) {}
}

function saveChatSearchSettings() {
  const toggle = document.getElementById("autoSearchToggle");
  const corpus = document.getElementById("chatCorpusId");
  const model = document.getElementById("chatEmbeddingModel");
  const topk = document.getElementById("chatSearchK");

  const payload = {
    enabled: !!(toggle && toggle.checked),
    corpus_id: corpus ? corpus.value : "",
    embedding_model: model ? model.value : "",
    search_k: topk ? Number(topk.value || 5) : 5,
  };

  try {
    localStorage.setItem(CHAT_SEARCH_STORAGE_KEY, JSON.stringify(payload));
  } catch (_) {}
}

function setMcpServersLoading(isLoading, msg = "Loading…") {
  const statusEl = document.getElementById("cuToolsStatus");
  const containerEl = document.getElementById("cuToolsContainer");

  if (statusEl) statusEl.textContent = isLoading ? msg : "";
  if (containerEl) containerEl.style.display = isLoading ? "none" : "";
}
function renderMCPServerCheckboxes() {
  const listEl = document.getElementById("cuToolsList");
  const hiddenEl = document.getElementById("cuTools");
  if (!listEl || !hiddenEl) return;

  listEl.innerHTML = "";

  // load once (I/O layer)
  loadAvailableTools();

  // derive servers (logic layer)
  const servers = [...getAvailableServers()]
    .sort((a, b) => a.localeCompare(b));

  if (servers.length === 0) {
    listEl.innerHTML = `<div class="muted">No servers available.</div>`;
    hiddenEl.value = "[]";
    return;
  }

  for (const server of servers) {
    const id = `cuServer_${cssSafeId(server)}`;

    const row = document.createElement("label");
    row.className = "cutool-item";
    row.htmlFor = id;

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.value = server;
    cb.checked = selectedTools.has(server); // or selectedServers if you rename later

    cb.addEventListener("change", () => {
      if (cb.checked) selectedTools.add(server);
      else selectedTools.delete(server);

      hiddenEl.value = JSON.stringify([...selectedTools]);
    });

    const text = document.createElement("span");
    text.textContent = server;

    row.appendChild(cb);
    row.appendChild(text);
    listEl.appendChild(row);
  }
}

/**
function renderCorporaCheckboxes() {
  const listEl = document.getElementById("cuCorporaList");
  const hiddenEl = document.getElementById("cuCorpora");
  if (!listEl || !hiddenEl) return;

  listEl.innerHTML = "";

  // load once (I/O layer)
  //loadAvailableTools();
  loadAvailableCorpora()
  loadSelectedCorpusIdsForUserCreation()

    // sort by name
  const corpora2 = [...selectedCorpusIdsForUserCreation].sort((a, b) =>
    (a.name ?? "").localeCompare(b.name ?? "")
  );
  const corpora = availableCorpora

  if (corpora.length === 0) {
    listEl.innerHTML = `<div class="muted">No collections available.</div>`;
    hiddenEl.value = "[]";
    return;
  }

  for (const c of corpora) {
    const id = `cuCorpus_${cssSafeId(c)}`;

    const row = document.createElement("label");
    row.className = "corpus-item";
    row.htmlFor = id;

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.value = c;
    cb.checked = corpora.has(c); // or selectedServers if you rename later

    cb.addEventListener("change", () => {
      if (cb.checked) corpora.add(c);
      else corpora.delete(c);

      hiddenEl.value = JSON.stringify([...corpora]);
    });

    const text = document.createElement("span");
    text.textContent = c;

    row.appendChild(cb);
    row.appendChild(text);
    listEl.appendChild(row);
  }
}**/
function setAutoSearchCorporaLoading(isLoading, msg = "Loading…") {
  const statusEl = document.getElementById("asCheckboxesStatus");
  const containerEl = document.getElementById("asCorporaContainer");

  if (statusEl) statusEl.textContent = isLoading ? msg : "";
  if (containerEl) containerEl.style.display = isLoading ? "none" : "";
}
function renderCorporaCheckboxesAutoSearch() {
/*  const listEl = document.getElementById("asCorporaList");
  const hiddenEl = document.getElementById("asCorpora");
  if (!listEl || !hiddenEl) return;*/

  const statusEl = document.getElementById("asCheckboxesStatus");
  const containerEl = document.getElementById("asCorporaContainer");
  const listEl = document.getElementById("asCorporaList");
  const hiddenEl = document.getElementById("asCorpora");
  if (!listEl || !hiddenEl) return;

  if (statusEl) statusEl.textContent = "Loading…";
  if (containerEl) containerEl.style.display = "none";


  listEl.innerHTML = "";

  //loadAvailableCorpora();                 // fills availableCorpora (Set of ids)
  loadSelectedCorpusIdsForAutoSearch(); // fills selectedCorpusIdsForUserCreation (Set of ids)

  const corpora = [...availableCorpora].map(String).sort((a, b) => a.localeCompare(b));

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
    row.className = "asCorpus-item"; // TODO replace
    row.htmlFor = id;

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.value = corpusId;

    // checked = selected-for-user-creation
    cb.checked = selectedCorpusIdsForAutoSearch.has(corpusId);

    cb.addEventListener("change", () => {
      // mutate selected set, not available
      if (cb.checked) selectedCorpusIdsForAutoSearch.add(corpusId);
      else selectedCorpusIdsForAutoSearch.delete(corpusId);

      hiddenEl.value = JSON.stringify([...selectedCorpusIdsForAutoSearch]);
      saveSelectedCorpusIdsForAutoSearch(); // if you have it
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

function renderCorporaCheckboxesUserCreation() {
  const listEl = document.getElementById("cuCorporaList");
  const hiddenEl = document.getElementById("cuCorpora");
  if (!listEl || !hiddenEl) return;

  listEl.innerHTML = "";

  loadAvailableCorpora();                 // fills availableCorpora (Set of ids)
  loadSelectedCorpusIdsForUserCreation(); // fills selectedCorpusIdsForUserCreation (Set of ids)

  const corpora = [...availableCorpora].map(String).sort((a, b) => a.localeCompare(b));

  if (corpora.length === 0) {
    listEl.innerHTML = `<div class="muted">No collections available.</div>`;
    hiddenEl.value = "[]";
    return;
  }

  for (const corpusId of corpora) {
    const id = `cuCorpus_${cssSafeId(corpusId)}`;

    const row = document.createElement("label");
    row.className = "cutool-item"; // TODO replace
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
      saveSelectedCorpusIdsForUserCreation?.(); // if you have it
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


/**function renderMCPServerCheckboxes() {
  const listEl = document.getElementById("cuToolsList");
  const hiddenEl = document.getElementById("cuTools");
  if (!listEl || !hiddenEl) return;

  // Clear old content
  listEl.innerHTML = "";

  // Render in stable sorted order (optional)
  loadAvailableTools()
  const tools = [...availableTools].sort((a, b) => String(a).localeCompare(String(b)));

  if (tools.length === 0) {
    listEl.innerHTML = `<div class="muted">No tools available.</div>`;
    hiddenEl.value = "[]";
    return;
  }

  for (const tool of tools) {
    const id = `cuTool_${cssSafeId(tool)}`;

    const row = document.createElement("label");
    row.className = "tool-item";
    row.htmlFor = id;

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.value = tool;
    cb.checked = selectedTools.has(tool);

    cb.addEventListener("change", () => {
      if (cb.checked) selectedTools.add(tool);
      else selectedTools.delete(tool);
      hiddenEl.value = JSON.stringify([...selectedTools]);
    });

    const text = document.createElement("span");
    text.textContent = tool;

    row.appendChild(cb);
    row.appendChild(text);
    listEl.appendChild(row);
  }

  // Initialize hidden field once after rendering
  hiddenEl.value = JSON.stringify([...selectedTools]);
}**/


// Small helper to make a safe-ish DOM id from tool names
function cssSafeId(value) {
  return String(value).replace(/[^a-zA-Z0-9_-]/g, "_");
}

function renderTools(toolsUi) {
  const toolsList = document.getElementById("toolsList");
  if (!toolsList) return;

  toolsList.innerHTML = "";

  for (const t of toolsUi) {
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
      saveSelectedTools();
      updateEnabledCount();
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

  updateEnabledCount();
}


/*** - - - - - - - - - - - ***/
/*** - - - BOOTSTRAP - - - ***/
/*** - - - - - - - - - - - ***/

async function bootstrap() {
  const toolsStatus = document.getElementById("toolsStatus");

  // restore prior tool selection early
  loadSelectedTools();
  updateEnabledCount();  // todo seems buggy in UI

  try {
    const res = await fetch("/api/chat/bootstrap", { method: "POST", credentials: "include" });
    if (!res.ok) {
      const text = await res.text();
      toolsStatus.textContent = `Bootstrapping MCP tools failed: ${text}`;
      return;
    }

    const data = await res.json();
    CHAT_SESSION_ID = data.chat_session_id;

    // save all available tools for this user
    const available = new Set(data.tools_ui.map(t => t.name));
    availableTools = new Set(available);
    saveAvailableTools();

    // if none are selected yet, default to "all selected"
    if (selectedTools.size === 0 && Array.isArray(data.tools_ui)) {
      selectedTools = new Set(available);
      saveSelectedTools();
    }

    if (toolsStatus) toolsStatus.textContent = `Loaded ${data.tools_ui.length} tool(s).`;
    renderTools(data.tools_ui);

    // wire buttons
    const allBtn = document.getElementById("toolsSelectAllBtn");
    const noneBtn = document.getElementById("toolsSelectNoneBtn");

    if (allBtn) {
      allBtn.onclick = () => {
        selectedTools = new Set(data.tools_ui.map((t) => t.name));
        saveSelectedTools();
        renderTools(data.tools_ui);
      };
    }

    if (noneBtn) {
      noneBtn.onclick = () => {
        selectedTools = new Set();
        saveSelectedTools();
        renderTools(data.tools_ui);
      };
    }
  } catch (e) {
    if (toolsStatus) toolsStatus.textContent = `Bootstrap error: ${e}`;
  }

  // bootstrap all available corpora
  try{
    const res = await fetch("/api/corpora/bootstrap", { method: "POST", credentials: "include" });
    if (!res.ok) {
      const text = await res.text();
      console.log(`Bootstrapping corpora failed: ${text}`);
      return;
    }
    const data = await res.json();
    availableCorporaList = Array.isArray(data.corpora) ? data.corpora : [];
    availableCorpora = new Set(availableCorporaList.map(c => String(c.id)));
    saveAvailableCorpora();
    loadSelectedCorpusIdsForAutoSearch();  // TODO cache?
    loadSelectedCorpusIdsForUserCreation();

    // save all available corpora for this user (if none -> empty)
    const allowed = new Set(availableCorporaList.map(c => String(c.id)));
    selectedCorpusIdsForAutoSearch = new Set(
      [...selectedCorpusIdsForAutoSearch].filter(id => allowed.has(id))
    );
    selectedCorpusIdsForUserCreation = new Set(
      [...selectedCorpusIdsForUserCreation].filter(id => allowed.has(id))
    );

    // default: select all if first visit
    if (selectedCorpusIdsForAutoSearch.size === 0 && availableCorporaList.length > 0) {
      selectedCorpusIdsForAutoSearch = new Set(availableCorporaList.map(c => String(c.id)));
    }
    if (selectedCorpusIdsForUserCreation.size === 0 && availableCorporaList.length > 0) {
      selectedCorpusIdsForUserCreation = new Set(availableCorporaList.map(c => String(c.id)));
    }

    saveSelectedCorpusIdsForAutoSearch();
    saveSelectedCorpusIdsForUserCreation();

    renderCorporaCheckboxesAutoSearch();
    renderCorporaCheckboxesUserCreation();

    setAutoSearchCorporaLoading(false);

    renderCorpusPicker();  // create checkboxes
    wireCorpusButtons();

  } catch (e) {
    console.log(e)
  }
}

// ---- display the available corpora
function updateHiddenCorpusInput() {
  const hidden = document.getElementById("chatCorpusId");
  const hint = document.getElementById("chatCorpusHint");
  const ids = [...selectedCorpusIdsForAutoSearch];
  const value = ids.join(";");

  if (hidden) hidden.value = value;

  if (hint) {
    hint.textContent = ids.length
      ? `Selected ${ids.length} corpus/corpora`
      : "No corpora selected (search will run with none unless you select).";
  }
}

function renderCorpusPicker() {
  const container = document.getElementById("chatCorpusPicker");
  if (!container) return;

  // sort by name
  const corpora = [...availableCorporaList].sort((a, b) =>
    (a.name ?? "").localeCompare(b.name ?? "")
  );

  container.innerHTML = "";

  if (corpora.length === 0) {
    container.textContent = "No corpora available.";
    selectedCorpusIdsForAutoSearch.clear();
    updateHiddenCorpusInput();
    return;
  }

  const frag = document.createDocumentFragment();

  for (const c of corpora) {
    const id = String(c.id);
    const name = String(c.name ?? c.id);

    const label = document.createElement("label");
    label.className = "corpus-option";
    label.style.display = "flex";
    label.style.alignItems = "center";
    label.style.gap = "0.5rem";

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = selectedCorpusIdsForAutoSearch.has(id);

    cb.addEventListener("change", () => {
      if (cb.checked) selectedCorpusIdsForAutoSearch.add(id);
      else selectedCorpusIdsForAutoSearch.delete(id);
      saveSelectedCorpusIdsForAutoSearch();
      updateHiddenCorpusInput();
    });

    const text = document.createElement("span");
    text.textContent = name;

    label.appendChild(cb);
    label.appendChild(text);
    frag.appendChild(label);
  }

  container.appendChild(frag);
  updateHiddenCorpusInput();
}

function wireCorpusButtons() {
  const allBtn = document.getElementById("corpusAllBtn");
  const noneBtn = document.getElementById("corpusNoneBtn");

  if (allBtn) allBtn.onclick = () => {
    selectedCorpusIdsForAutoSearch = new Set(availableCorporaList.map(c => String(c.id)));
    saveSelectedCorpusIdsForAutoSearch();
    renderCorpusPicker();
  };

  if (noneBtn) noneBtn.onclick = () => {
    selectedCorpusIdsForAutoSearch = new Set();
    saveSelectedCorpusIdsForAutoSearch();
    renderCorpusPicker();
  };
}


// ---- chat search (RAG) ----
async function loadEmbeddingModels() {
  const selects = [
    document.getElementById("uploadEmbeddingModel"),
    document.getElementById("chatEmbeddingModel"),
  ].filter(Boolean);
  if (selects.length === 0) return;

  const res = await fetch("/api/admin/embedding-models");

  if (!res.ok) {
    for (const select of selects) {
      select.innerHTML = "";
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "Embedding models unavailable";
      select.appendChild(opt);
    }
    return;
  }

  const data = await res.json().catch(() => ({}));
  const models = Array.isArray(data.models) ? data.models : [];

  for (const select of selects) {
    select.innerHTML = "";
    for (const model of models) {
      const opt = document.createElement("option");
      opt.value = model.id;
      opt.textContent = model.label || model.id;
      select.appendChild(opt);
    }
  }

  const defaultValue = data.default || (models.length > 0 ? models[0].id : "");
  for (const select of selects) {
    if (defaultValue) select.value = defaultValue;
  }

  loadChatSearchSettings();
}

const autoSearchToggle = document.getElementById("autoSearchToggle");
const chatCorpusId = document.getElementById("chatCorpusId");
const chatEmbeddingModel = document.getElementById("chatEmbeddingModel");
const chatSearchK = document.getElementById("chatSearchK");

if (autoSearchToggle) autoSearchToggle.addEventListener("change", saveChatSearchSettings);
if (chatCorpusId) chatCorpusId.addEventListener("input", saveChatSearchSettings);
if (chatEmbeddingModel) chatEmbeddingModel.addEventListener("change", saveChatSearchSettings);
if (chatSearchK) chatSearchK.addEventListener("input", saveChatSearchSettings);

// ---- upload documents (admin only) ----
const uploadForm = document.getElementById("uploadForm");
if (uploadForm) {
  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const status = document.getElementById("uploadStatus");
    if (status) {
      status.textContent = "";
      status.className = "upload-status";
    }

    if (!CHAT_SESSION_ID) {
      if (status) {
        status.textContent = "Chat session not ready yet. Try again in a moment.";
        status.className = "upload-status err";
      }
      return;
    }

    const fileInput = document.getElementById("uploadFile");
    const file = fileInput && fileInput.files ? fileInput.files[0] : null;
    if (!file) {
      if (status) {
        status.textContent = "Please choose a .txt file to upload.";
        status.className = "upload-status err";
      }
      return;
    }

    const formData = new FormData(uploadForm);
    formData.append("chat_session_id", CHAT_SESSION_ID);
    if (!formData.get("user_id") && CURRENT_USER) {
      formData.set("user_id", CURRENT_USER);
    }

    const res = await fetch("/api/admin/documents/upload", {
      method: "POST",
      body: formData,
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (status) {
        status.textContent = data.detail || "Upload failed";
        status.className = "upload-status err";
      }
      return;
    }

    if (status) {
      status.textContent = `Uploaded ${data.chunks} chunk(s) to ${data.corpus_id} using ${data.embedding_model}.`;
      status.className = "upload-status ok";
    }
  });
}

// ---- existing chat handler: include selected tools ----
const chatForm = document.getElementById("chatForm");
if (chatForm) {
  const chatInput = document.getElementById("chatInput");
  const chatLog = document.getElementById("chatLog");
  const chatErr = document.getElementById("chatErr");

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    chatErr.textContent = "";

    const message = chatInput.value.trim();
    if (!message) return;

    const autoSearch = autoSearchToggle ? autoSearchToggle.checked : false;
    //const corpusId = chatCorpusId ? chatCorpusId.value.trim() : "";
    const embeddingModel = chatEmbeddingModel ? chatEmbeddingModel.value : "";
    const searchK = chatSearchK ? Number(chatSearchK.value || 5) : 5;

    if (autoSearch && selectedCorpusIdsForAutoSearch.size===0) {
      chatErr.textContent = "Auto pre-search requires a corpus ID.";
      return;
    }

    chatLog.textContent += `You: ${message}\n`;
    chatInput.value = "";

    console.log([...selectedCorpusIdsForAutoSearch])

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        selected_tools: [...selectedTools],
        chat_session_id: CHAT_SESSION_ID,
        auto_search: autoSearch,
        corpora: [...selectedCorpusIdsForAutoSearch],
        embedding_model: embeddingModel,
        search_k: searchK,
      }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      chatErr.textContent = data.detail || "Chat failed";
      return;
    }

    const data = await res.json();
    chatLog.textContent += `Bot: ${data.text}\n`;
  });
}

if (document.getElementById("toolsList")) {
  bootstrap();
}
loadMe()

/*** USER CREATION ***/
const createUserForm = document.getElementById("createUserForm");
const createUserMsg  = document.getElementById("createUserMsg");

if (createUserForm && createUserMsg) {
  createUserForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const tools = [
      ...document.querySelectorAll("#cuToolsList input[type='checkbox']:checked")
    ].map(cb => cb.value);

    const corpora = [
      ...document.querySelectorAll("#cuCorporaList input[type='checkbox']:checked")
    ].map(cb => cb.value);


    const data = {
      username: document.getElementById("cuUsername")?.value ?? "",
      password: document.getElementById("cuPassword")?.value ?? "",
      role: document.getElementById("cuRole")?.value ?? "user",
      tools: tools, // JSON.parse(document.getElementById("cuTools").value || "[]")
      corpora: corpora
    };

    try {
      const res = await fetch("/api/admin/user/creation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });

      const result = await res.json().catch(() => ({}));

      if (!res.ok) {
        createUserMsg.textContent = result.detail || result.message || "Error! User could not be created.";
        return;
      }

      createUserMsg.textContent = result.message || "User successfully created!";
      createUserForm.reset();
    } catch (err) {
      createUserMsg.textContent = "Error! User could not be created.";
      console.error(err);
    }
  });
}
