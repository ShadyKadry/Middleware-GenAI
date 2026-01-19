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

const chatForm = document.getElementById("chatForm");
if (chatForm) {
  const chatInput = document.getElementById("chatInput");
  const chatLog = document.getElementById("chatLog");
  const chatErr = document.getElementById("chatErr");

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault(); // <-- prevents GET /app?message=...
    chatErr.textContent = "";

    const message = chatInput.value.trim();
    if (!message) return;

    // show user's message and keep it
    chatLog.textContent += `You: ${message}\n`;
    chatInput.value = "";

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
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

let CHAT_SESSION_ID = null;

async function bootstrap() {
  const toolsStatus = document.getElementById("toolsStatus");
  const toolsList = document.getElementById("toolsList");

  try {
    const res = await fetch("/api/chat/bootstrap", { method: "POST" });
    if (!res.ok) {
      const text = await res.text();
      toolsStatus.textContent = `Bootstrap failed: ${text}`;
      return;
    }

    const data = await res.json();
    CHAT_SESSION_ID = data.chat_session_id;

    toolsStatus.textContent = `Loaded ${data.tools_ui.length} tool(s).`;

    toolsList.innerHTML = "";
    for (const t of data.tools_ui) {
      const li = document.createElement("li");
      li.textContent = t.description ? `${t.name} — ${t.description}` : t.name;
      toolsList.appendChild(li);
    }
  } catch (e) {
    toolsStatus.textContent = `Bootstrap error: ${e}`;
  }
}

if (document.getElementById("toolsList")) {
  bootstrap();
}



loadMe();
