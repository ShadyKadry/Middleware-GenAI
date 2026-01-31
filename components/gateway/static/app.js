let CURRENT_USER = null;
let CURRENT_ROLE = null;

async function loadMe() {
  const res = await fetch("/api/me");
  if (!res.ok) return;

  const data = await res.json().catch(() => null);
  if (!data) return;

  CURRENT_USER = data.user;
  CURRENT_ROLE = data.role;

  const meBox = document.getElementById("meBox");
  if (meBox) meBox.textContent = JSON.stringify(data, null, 2);

  const adminCard = document.getElementById("adminUploadCard");
  if (adminCard) {
    adminCard.style.display = data.role === "admin" ? "block" : "none";
  }

  if (data.role === "admin") {
    loadEmbeddingModels();
  }
}

const form = document.getElementById("loginForm");
if (form) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await fetch("/api/login", {
      method: "POST",
      body: new FormData(form),
    });
    if (res.ok) window.location.href = "/app";
    else document.getElementById("msg").textContent = "Login failed";
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
const TOOLS_STORAGE_KEY = "enabled_tools_v1";
const CHAT_SEARCH_STORAGE_KEY = "chat_presearch_v1";
let selectedTools = new Set();

function loadSelectedTools() {
  try {
    const raw = localStorage.getItem(TOOLS_STORAGE_KEY);
    if (!raw) return;
    const arr = JSON.parse(raw);
    if (Array.isArray(arr)) selectedTools = new Set(arr);
  } catch (_) {}
}

function saveSelectedTools() {
  try {
    localStorage.setItem(TOOLS_STORAGE_KEY, JSON.stringify([...selectedTools]));
  } catch (_) {}
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

let CHAT_SESSION_ID = null;

async function bootstrap() {
  const toolsStatus = document.getElementById("toolsStatus");

  // restore prior tool selection early
  loadSelectedTools();
  updateEnabledCount();

  try {
    const res = await fetch("/api/chat/bootstrap", { method: "POST" });
    if (!res.ok) {
      const text = await res.text();
      toolsStatus.textContent = `Bootstrap failed: ${text}`;
      return;
    }

    const data = await res.json();
    CHAT_SESSION_ID = data.chat_session_id;

    // if nothing selected yet, default to "all selected"
    if (selectedTools.size === 0 && Array.isArray(data.tools_ui)) {
      const allowed = new Set(data.tools_ui.map(t => t.name));
      selectedTools = new Set([...selectedTools].filter(n => allowed.has(n)));
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
}

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

const autoSearchToggle = document.getElementById("autoSearchToggle");
const chatCorpusId = document.getElementById("chatCorpusId");
const chatEmbeddingModel = document.getElementById("chatEmbeddingModel");
const chatSearchK = document.getElementById("chatSearchK");

if (autoSearchToggle) autoSearchToggle.addEventListener("change", saveChatSearchSettings);
if (chatCorpusId) chatCorpusId.addEventListener("input", saveChatSearchSettings);
if (chatEmbeddingModel) chatEmbeddingModel.addEventListener("change", saveChatSearchSettings);
if (chatSearchK) chatSearchK.addEventListener("input", saveChatSearchSettings);


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
    const corpusId = chatCorpusId ? chatCorpusId.value.trim() : "";
    const embeddingModel = chatEmbeddingModel ? chatEmbeddingModel.value : "";
    const searchK = chatSearchK ? Number(chatSearchK.value || 5) : 5;

    if (autoSearch && !corpusId) {
      chatErr.textContent = "Auto pre-search requires a corpus ID.";
      return;
    }

    chatLog.textContent += `You: ${message}\n`;
    chatInput.value = "";

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        selected_tools: [...selectedTools],
        chat_session_id: CHAT_SESSION_ID,
        auto_search: autoSearch,
        corpus_id: corpusId,
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

loadMe();
