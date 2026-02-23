import {
  renderCorporaCheckboxesAutoSearch,
  renderCorporaCheckboxesUserCreation,
  renderEmbeddingModels,
  renderMCPServerCheckboxesForUserCreation,
  renderMCPToolCheckboxesForChatForm,
  renderMe,
  setAutoSearchCorporaLoading,
  renderPanels,
} from "./ui/render.js";
import {bootstrapCorpora, bootstrapMCPTools, getEmbeddingModels, getMe} from "./api.js";
import {
  wireChatForm,
  wireCorpusSelectionButtonsAutoSearch,
  wireDocumentUploadForm,
  wireLoginForm,
  wireLogoutButton,
  wireMcpRegistrationForm,
  wireMCPServerSelectionButtons,
  wireSidebarNavigation,
  wireUserCreationForm
} from "./ui/events.js";
import {
  getSelectedCorpusIdsForAutoSearch,
  getSelectedCorpusIdsForUserCreation,
  getSelectedTools,
  initStateFromLocalStorage,
  setAvailableCorpora,
  setAvailableCorporaList,
  setAvailableTools,
  setAvailableToolsList,
  setChatSessionID,
  setCurrentUser,
  setSelectedCorpusIdsForAutoSearch,
  setSelectedCorpusIdsForUserCreation,
  setSelectedTools
} from "./session/state.js";


/**
 * Loads current user info, initializes user/admin UI state,
 * shows default panels, and triggers admin UI setup if applicable.
 */
async function loadMe() {
  const data = await getMe().catch(() => null);
  if (!data) return;

  const user = String(data.user || "").toLowerCase();
  const role = String(data.role || "").toLowerCase();
  setCurrentUser(user, role);

  const isAdmin = role === "admin" || role === "super-admin";
  renderMe({ user, role, isAdmin });

  renderPanels("panelAutoSearch,panelChat,panelTools");

  setAutoSearchCorporaLoading(true);

  if (isAdmin) {
    const payload = await getEmbeddingModels().catch(() => null);
    renderEmbeddingModels(payload);
  }
}


/**
 * Bootstraps the app by loading available MCP tools and corpora from the API,
 * restoring and validating selections, initializing defaults, and rendering
 * the related UI elements and selection controls.
 */
async function bootstrap() {
  const toolsStatus = document.getElementById("toolsStatus");

  // bootstrap all available MCP server & tools
  try {
    const data = await bootstrapMCPTools();
    if (!data) throw new Error("Bootstrap returned null.");

    setChatSessionID(data.chat_session_id);

    // save all available tools for this user
    const availableToolsList = data.tools_ui
    setAvailableToolsList(availableToolsList);
    const available = new Set(availableToolsList.map(t => t.name));
    setAvailableTools(new Set(available));  // todo is used?

    // if none are selected yet, default to "all selected"
    let selectedTools = getSelectedTools();  // restore prior tool selection
    if (selectedTools.size === 0 && Array.isArray(availableToolsList)) {
      setSelectedTools(new Set(available));
    }

    if (toolsStatus) toolsStatus.textContent = `Loaded ${availableToolsList.length} tool(s).`;
    renderMCPToolCheckboxesForChatForm(availableToolsList);
    renderMCPServerCheckboxesForUserCreation();

    wireMCPServerSelectionButtons()
  } catch (e) {
    if (toolsStatus) toolsStatus.textContent = `Error while bootstrapping MCP servers: ${e}`;
  }

  // bootstrap all available corpora
  try{
    const data = await bootstrapCorpora();
    if (!data) throw new Error("Bootstrap returned null.");

    // store all available corpora for this user in memory
    const availableCorporaList = Array.isArray(data.corpora) ? data.corpora : [];
    setAvailableCorporaList(availableCorporaList);

    const availableCorpora = new Set(availableCorporaList.map(c => String(c.id)));
    setAvailableCorpora(availableCorpora);

    // load previous selections from local storage
    let selectedCorpusIdsForAutoSearch = getSelectedCorpusIdsForAutoSearch();
    let selectedCorpusIdsForUserCreation = getSelectedCorpusIdsForUserCreation();

    // verify previous selection with granted access store (if previously none selected -> empty)
    const allowed = new Set(availableCorporaList.map(c => String(c.id)));
    selectedCorpusIdsForAutoSearch = new Set([...selectedCorpusIdsForAutoSearch].filter(id => allowed.has(id)));
    selectedCorpusIdsForUserCreation = new Set([...selectedCorpusIdsForUserCreation].filter(id => allowed.has(id)));

    // if none are selected yet, default to "all selected"
    if (selectedCorpusIdsForAutoSearch.size === 0 && availableCorporaList.length > 0) {
      selectedCorpusIdsForAutoSearch = new Set(availableCorporaList.map(c => String(c.id)));
    }
    if (selectedCorpusIdsForUserCreation.size === 0 && availableCorporaList.length > 0) {
      selectedCorpusIdsForUserCreation = new Set(availableCorporaList.map(c => String(c.id)));
    }

    // persist current selection in local storage
    setSelectedCorpusIdsForAutoSearch(selectedCorpusIdsForAutoSearch);
    setSelectedCorpusIdsForUserCreation(selectedCorpusIdsForUserCreation);

    // render corpus related elements
    renderCorporaCheckboxesAutoSearch();
    renderCorporaCheckboxesUserCreation();

    wireCorpusSelectionButtonsAutoSearch();
    setAutoSearchCorporaLoading(false);

  } catch (e) {
    if (toolsStatus) toolsStatus.textContent = `Error while bootstrapping document corpora: ${e}`;
  }
}


/**
 * Initializes the app: wires the login form, loads user and bootstrap data
 * on the main app page, then attaches all UI event handlers.
 */
async function init() {
  wireLoginForm();

  const isAppPage = !!document.getElementById("toolsList");

  if (isAppPage) {
    // retrieve stored tool/corpus/chat settings selections from local storage
    initStateFromLocalStorage()

    await loadMe();  // loads role-based UI for user
    await bootstrap();  // loads tools & corpora

    // state is ready -> wire handlers that depend on it
    wireSidebarNavigation()
    wireChatForm();
    wireUserCreationForm();
    wireDocumentUploadForm();
    wireMcpRegistrationForm();
    wireLogoutButton();
  }
}

init()
