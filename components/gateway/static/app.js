async function loadMe() {
  const res = await fetch("/api/me");
  if (res.ok) {
    document.getElementById("meBox").textContent = await res.text();
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

    chatLog.textContent += `You: ${message}\n`;
    chatInput.value = "";

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        selected_tools: [...selectedTools],
        chat_session_id: CHAT_SESSION_ID,
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
