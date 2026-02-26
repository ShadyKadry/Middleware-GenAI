import {
  ADMIN_PANELS,
  renderChatMessage,
  renderCorporaCheckboxesAutoSearch,
  renderMCPToolCheckboxesForChatForm,
  renderMcpTransportFields,
  renderPanels
} from "./render.js";
import {parseArgs, parseHeaders, parseMultiValue} from "../utils/parse.js";
import {
  getAvailableCorporaList,
  getAvailableToolsList,
  getChatSessionID,
  getCurrentRole,
  getCurrentUser,
  getSelectedAutoSearchEnabled,
  getSelectedAutoSearchK,
  getSelectedCorpusIdsForAutoSearch,
  getSelectedTools,
  setSelectedAutoSearchEnabled,
  setSelectedAutoSearchK,
  setSelectedCorpusIdsForAutoSearch,
  setSelectedTools,
  resetStateToDefault
} from "../session/state.js";


/**
 * Handles sidebar button clicks: marks the clicked button active,
 * blocks access to admin panels for non-admins, and shows the
 * target panels.
 */
export function wireSidebarNavigation() {
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-target]");
    if (!btn) return;

    const targets = btn.dataset.target;
    const isAdmin = ["admin", "super-admin"].includes(getCurrentRole());
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

    renderPanels(btn.dataset.target);
  });
}


/**
 * Wires the chat form: tracks auto-search settings, prevents double binding, attaches an event handler
 * which submits incoming messages with selected tools and options, and renders user/bot messages.
 */
export function wireChatForm() {
  const chatForm = document.getElementById("chatForm");
  if (!chatForm) return;

  // prevent accidental double-binding
  if (chatForm.dataset.wired === "1") return;
  chatForm.dataset.wired = "1";

  const autoSearchToggle = document.getElementById("autoSearchToggle");
  const autoSearchK = document.getElementById("chatSearchK");
  const chatInput = document.getElementById("chatInput");
  const chatErr = document.getElementById("chatErr");

  if (autoSearchK) {
    autoSearchK.addEventListener("input", (e) => {
      setSelectedAutoSearchK(Number(e.target.value || 5));
    });
  }

  if (autoSearchToggle) {
    autoSearchToggle.addEventListener("change", (e) => {
      setSelectedAutoSearchEnabled(e.target.checked);
    });
  }

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    chatErr.textContent = "";

    const message = chatInput.value.trim();
    if (!message) return;

    // todo how we make the vars are not empty or stale? through event listeners. are they guaranteed set before?
    const autoSearchEnabled = getSelectedAutoSearchEnabled();
    const searchK = getSelectedAutoSearchK();
    const selectedCorpusIdsForAutoSearch = getSelectedCorpusIdsForAutoSearch();

    if (autoSearchEnabled && selectedCorpusIdsForAutoSearch.size===0) {
      chatErr.textContent = "Auto pre-search requires a corpus ID.";
      return;
    }

    renderChatMessage("user", message);
    chatInput.value = "";

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        selected_tools: [...getSelectedTools()],
        chat_session_id: getChatSessionID(),
        auto_search: autoSearchEnabled,
        corpora: [...selectedCorpusIdsForAutoSearch],
        search_k: searchK,
      }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      chatErr.textContent = data.detail || "Chat failed";
      return;
    }

    const data = await res.json();
    renderChatMessage("bot", data.text);
  });
}


/**
 * Attaches a submit handler to the user creation form that collects selected
 * tools and corpora, sends them to the admin API, and displays the final status message.
 */
export function wireUserCreationForm() {
  const createUserForm = document.getElementById("createUserForm");
  const createUserMsg  = document.getElementById("createUserMsg");

  if (!(createUserForm && createUserMsg)) return;

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
      tools: tools,
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

/**
 * Attaches a submit handler to the document upload form that validates input,
 * sends the file and session data to the upload API, and displays the result status.
 */
export function wireDocumentUploadForm() {
  const uploadForm = document.getElementById("uploadForm");
  if (!uploadForm) return;

  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const status = document.getElementById("uploadStatus");
    if (status) {
      status.textContent = "";
      status.className = "upload-status";
    }

    const chatSessionID = getChatSessionID();
    const currentUser = getCurrentUser();

    if (!chatSessionID) {
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
    formData.append("chat_session_id", chatSessionID);
    if (!formData.get("user_id") && currentUser) {
      formData.set("user_id", currentUser);
    }

    const res = await fetch("/api/admin/documents/upload", {
      method: "POST",
      body: formData,
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      if (status) {
        status.textContent = "Upload failed without response.";
        status.className = "upload-status err";
      }
    }
    else if (!data.ok) {
      if (status) {
        status.className = "upload-status err"; // fixme data.database_model || - - - - - - - - - - - - - - - - - - - -

        if (data.status === "Corpus already exists.") {
          status.innerHTML = `
            <strong>Corpus already exists.</strong><br>
            If you want to add this document to the existing corpus, please match its specified attributes:
            <ul class="status-attrs">
              <li><b>Corpus ID:</b> ${data.corpus_id}</li>
              <li><b>Database model:</b> ${"SomeDB"}</li>
              <li><b>Embedding model:</b> ${data.embedding_model}</li>
              <li><b>Chunk size:</b> ${data.chunk_size}</li>
              <li><b>Chunk overlap:</b> ${data.chunk_overlap}</li>
            </ul>
            <p class="status-note">
              Specified users or roles will <strong>NOT</strong> have any effect and remain as originally set for this corpus.
            </p>
          `;
        } else if (data.status === "Upload to new failed!"){
          status.innerHTML = `Upload to new corpus ${data.corpus_id} failed! Failed IDs: ${data.payload.failed_ids}`
        } else if (data.status === "Upload to existing failed!"){
          status.innerHTML = `Upload to existing corpus ${data.corpus_id} failed! Failed IDs: ${data.payload.failed_ids}`
        } else {
          status.textContent = data.status || "Upload failed.";
        }
      }
    }
    else {
      if (status) {
        status.className = "upload-status ok";

        if (data.status === "Upload to existing succeeded!") {
          status.innerHTML = `
            Uploaded ${data.chunks} chunk(s) to existing corpus ${data.corpus_id} using ${data.embedding_model}.
            <p class="status-note">
              Please note that allowed users/roles were <strong>NOT</strong> overwritten and remain as originally set.
            </p>
          `;
        } else {
          status.textContent = `Uploaded ${data.chunks} chunk(s) to ${data.corpus_id} using ${data.embedding_model}.`;
        }
      }
    }
  });
}


/**
 * Attaches a click handler to the logout button that logs the user out,
 * redirects to the home page, and resets client-side state.
 */
export function wireLogoutButton() {
  const logoutBtn = document.getElementById("logoutBtn");
  if (!logoutBtn) return;

  logoutBtn.addEventListener("click", async () => {
    await fetch("/api/logout", { method: "POST" });
    window.location.href = "/";
  });

  resetStateToDefault(); // todo: might be desired to save selections past logout. (low priority)
}


/**
 * Attaches a submit handler to the login form that sends credentials to the
 * login API and redirects on success or shows an error message on failure.
 */
export function wireLoginForm() {
  const form = document.getElementById("loginForm");
  if (!form) return;

  // prevent double-binding if init runs twice
  if (form.dataset.wired === "1") return;
  form.dataset.wired = "1";

  const msg = document.getElementById("msg");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const res = await fetch("/api/login", {
      method: "POST",
      body: new FormData(form),
    });

    if (res.ok) {
      window.location.href = "/app";
    } else {
      if (msg) {
        msg.textContent = "Login failed! Wrong username or password.";
      }
    }
  });
}


/**
 * Attaches handlers for the MCP server registration form and transport selector,
 * validates inputs, submits the registration to the admin API, and shows status messages.
 */
export function wireMcpRegistrationForm() {
  const registerForm = document.getElementById("registerNewMCPServer");
  const transportSelect = document.getElementById("mcpTransport");

  // This UI is admin-only, so it's normal for it to be absent on most pages.
  if (!registerForm && !transportSelect) return;

  // If the form exists, wire it once.
  if (registerForm) {
    if (registerForm.dataset.wired === "1") return;
    registerForm.dataset.wired = "1";
  }

  // Wire transport switching (and initialize field visibility)
  if (transportSelect) {
    if (transportSelect.dataset.wired !== "1") {
      transportSelect.dataset.wired = "1";
      transportSelect.addEventListener("change", renderMcpTransportFields);
    }
    renderMcpTransportFields();
  } else if (registerForm) {
    console.warn("[ui.events] #mcpTransport not found; MCP transport fields won't toggle.");
  }

  if (!registerForm) return;

  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const status = document.getElementById("mcpRegisterStatus");
    const setStatus = (text, kind) => {
      if (!status) return;
      status.textContent = text || "";
      status.className = kind ? `upload-status ${kind}` : "upload-status";
    };

    setStatus("", ""); // clear

    const name = document.getElementById("mcpName")?.value.trim();
    const transport = document.getElementById("mcpTransport")?.value || "stdio";
    const command = document.getElementById("mcpCommand")?.value.trim();
    const args = parseArgs(document.getElementById("mcpArgs")?.value || "");
    const serverUrl = document.getElementById("mcpServerUrl")?.value.trim();

    const { headers, error: headersError } = parseHeaders(
      document.getElementById("mcpHeaders")?.value || ""
    );

    const allowedUsers = parseMultiValue(
      document.getElementById("mcpAllowedUsers")?.value || ""
    );
    const requiredRoles = parseMultiValue(
      document.getElementById("mcpRequiredRoles")?.value || ""
    );

    const enabled = !!document.getElementById("mcpEnabled")?.checked;

    if (!name) {
      setStatus("Name is required.", "err");
      return;
    }

    if (headersError) {
      setStatus(headersError, "err");
      return;
    }

    const payload = {
      name,
      enabled,
      allowed_users: allowedUsers,
      required_roles: requiredRoles,
      transport,
    };

    if (transport === "stdio") {
      if (!command) {
        setStatus("Command is required for stdio transport.", "err");
        return;
      }
      payload.command = command;
      payload.args = args;
    } else {
      if (!serverUrl) {
        setStatus("Server URL is required for sse/http transport.", "err");
        return;
      }
      payload.server_url = serverUrl;
      if (headers && Object.keys(headers).length) payload.headers = headers;
    }

    const res = await fetch("/api/admin/mcp-servers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      credentials: "include",
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      setStatus(data.detail || "Registration failed", "err");
      return;
    }

    setStatus(
      `Registered ${data.backend?.name || name}. Restart or re-bootstrap chat to load new tools.`,
      "ok"
    );

    registerForm.reset();
    // Reset defaults after reset
    const enabledCb = document.getElementById("mcpEnabled");
    if (enabledCb) enabledCb.checked = true;

    renderMcpTransportFields();
  });
}


/**
 * Chat handler: Wires "select all" and "select none" buttons to update the MCP tool
 * selections and re-render the tool checkbox list.
 */
export function wireMCPServerSelectionButtons() {
    const allBtn = document.getElementById("toolsSelectAllBtn");
    const noneBtn = document.getElementById("toolsSelectNoneBtn");

    if (allBtn) {
      allBtn.onclick = () => {
        const selectedTools = new Set(getAvailableToolsList().map((t) => t.name));
        setSelectedTools(selectedTools);
        renderMCPToolCheckboxesForChatForm();
      };
    }

    if (noneBtn) {
      noneBtn.onclick = () => {
        setSelectedTools(new Set());
        renderMCPToolCheckboxesForChatForm();
      };
    }
}

/**
 * Chat handler: Wires "select all" and "select none" buttons to update the document corpus
 * selections and re-render the corpora checkbox list.
 */
export function wireCorpusSelectionButtonsAutoSearch() {
  const allBtn = document.getElementById("corpusAllBtn");
  const noneBtn = document.getElementById("corpusNoneBtn");

  if (allBtn) allBtn.onclick = () => {
    const selectedCorpusIdsForAutoSearch = new Set(getAvailableCorporaList().map(c => String(c.id)));
    setSelectedCorpusIdsForAutoSearch(selectedCorpusIdsForAutoSearch);
    renderCorporaCheckboxesAutoSearch();
  };

  if (noneBtn) noneBtn.onclick = () => {
    setSelectedCorpusIdsForAutoSearch(new Set());
    renderCorporaCheckboxesAutoSearch();
  };
}
