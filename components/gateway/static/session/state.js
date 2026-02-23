import {
  loadSelectedAutoSearchEnabled,
  loadSelectedAutoSearchK,
  loadSelectedCorpusIdsForAutoSearch,
  loadSelectedCorpusIdsForUserCreation,
  loadSelectedServers,
  loadSelectedTools,
  resetLocalStorage,
  saveSelectedAutoSearchEnabled,
  saveSelectedAutoSearchK,
  saveSelectedCorpusIdsForAutoSearch,
  saveSelectedCorpusIdsForUserCreation,
  saveSelectedServers,
  saveSelectedTools
} from "./storage.js";


// persisted in local storage & in-memory
let selectedTools = new Set();  // chat
let selectedServers = new Set();  // user creation
let selectedCorpusIdsForAutoSearch = new Set();  // chat
let selectedCorpusIdsForUserCreation = new Set();  // user creation
let selectedAutoSearchEnabled = false;  // chat
let selectedAutoSearchK = 5;  // chat

// in memory only (underlying data comes from backend and should not be persisted in frontend to prevent stale usage)
let availableTools = new Set();
let availableToolsList = []
let availableCorpora = new Set();
let availableCorporaList = [];
let CURRENT_USER = null;
let CURRENT_ROLE = null;
let CHAT_SESSION_ID = null;


/**
 * This class provides getters/setters from/to IN-MEMORY variables. This enables fast retrival of tools/corpora
 * without having to load/save to local storage each time. In-memory state is invalidated & rebuild on page reload.
 * **/


/*** Retrieves/sets the 'name's of available MCP tools. ***/
export function getAvailableTools() {
  return new Set(availableTools);
}
export function setAvailableTools(tools) {
  availableTools = new Set(tools ?? []);
}


/*** Returns only the MCP server names. Tools follow the naming pattern: <servername>.<toolname>. ***/
export function getAvailableServers() {
  return new Set(
    [...getAvailableTools()].map(t => t.split(".")[0])
  );
}


/*** Retrieves/sets the variable storing all information (i.e. 'name' and 'description') on the available MCP tools. ***/
export function getAvailableToolsList() {
  return [...availableToolsList];
}
export function setAvailableToolsList(list) {
  availableToolsList = Array.isArray(list) ? [...list] : [];
}


/*** Retrieves/sets the 'name's of selected MCP tools.
 Updates in-memory as well as LocalStorage values. ***/
export function getSelectedTools() {
  return new Set(selectedTools);
}
export function setSelectedTools(tools) {
  selectedTools = new Set(tools ?? []);
  saveSelectedTools(selectedTools);
}

/*** Retrieves/sets the 'name's of selected MCP servers.
 Updates in-memory as well as LocalStorage values. ***/
export function getSelectedServers() {
  return new Set(selectedServers);
}
export function setSelectedServers(servers) {
  selectedTools = new Set(servers ?? []);
  saveSelectedServers(selectedServers);
}


/*** Retrieves/sets the selected corpus IDs in the auto-search panel.
 Updates in-memory as well as LocalStorage values. ***/
export function getSelectedCorpusIdsForAutoSearch() {
  return new Set(selectedCorpusIdsForAutoSearch);
}
export function setSelectedCorpusIdsForAutoSearch(ids) {
  selectedCorpusIdsForAutoSearch = new Set(ids ?? []);
  saveSelectedCorpusIdsForAutoSearch(selectedCorpusIdsForAutoSearch);
}


/*** Retrieves/sets the selected corpus IDs in the user creation panel.
 Updates in-memory as well as LocalStorage values. ***/
export function getSelectedCorpusIdsForUserCreation() {
  return new Set(selectedCorpusIdsForUserCreation);
}
export function setSelectedCorpusIdsForUserCreation(ids) {
  selectedCorpusIdsForUserCreation = new Set(ids ?? []);
  saveSelectedCorpusIdsForUserCreation(selectedCorpusIdsForUserCreation);
}


/*** Retrieves/sets the checkbox which enables auto-search.
 Updates in-memory as well as LocalStorage values. ***/
export function getSelectedAutoSearchEnabled() {
  return Boolean(selectedAutoSearchEnabled);
}
export function setSelectedAutoSearchEnabled(enabled) {
  selectedAutoSearchEnabled = enabled;
  saveSelectedAutoSearchEnabled(selectedAutoSearchEnabled);
}


/*** Retrieves/sets the amount of results (top K results) the auto-search should return.
 Updates in-memory as well as LocalStorage values. ***/
export function getSelectedAutoSearchK() {
  return Number(selectedAutoSearchK);
}
export function setSelectedAutoSearchK(k) {
  selectedAutoSearchK = k;
  saveSelectedAutoSearchK(selectedAutoSearchK);
}


/*** Retrieves/sets the variable storing only the 'name' of each available corpus. ***/
export function getAvailableCorpora() {
  return new Set(availableCorpora);
}
export function setAvailableCorpora(corpora) {
  availableCorpora = new Set(corpora ?? []);
}


/*** Retrieves/sets the variable storing all available information on the corpora i.e. 'id', 'name' and 'meta'  ***/
export function getAvailableCorporaList() {
  return [...availableCorporaList];
}
export function setAvailableCorporaList(list) {
  availableCorporaList = Array.isArray(list) ? [...list] : [];
}


/*** Retrieves/sets the current user and its role. ***/
export function setCurrentUser(user, role) {
  CURRENT_USER = user
  CURRENT_ROLE = role
}
export function getCurrentUser() {
  return CURRENT_USER;
}
export function getCurrentRole() {
  return CURRENT_ROLE;
}


/*** Retrieves/sets the session ID. ***/
export function getChatSessionID() {
  return CHAT_SESSION_ID;
}
export function setChatSessionID(sessionID) {
  CHAT_SESSION_ID = sessionID ?? null;
}


/*** Retrieves stored selections for this user and applies them to the current session.  ***/
export function initStateFromLocalStorage() {
  selectedTools = loadSelectedTools();
  selectedServers = loadSelectedServers();
  selectedCorpusIdsForAutoSearch = loadSelectedCorpusIdsForAutoSearch();
  selectedCorpusIdsForUserCreation = loadSelectedCorpusIdsForUserCreation();
  selectedAutoSearchEnabled = loadSelectedAutoSearchEnabled() ?? selectedAutoSearchEnabled;
  selectedAutoSearchK = loadSelectedAutoSearchK() ?? selectedAutoSearchK;
}


/*** Resets in-memory and LocalStorage values to default. ***/
export function resetStateToDefault() {
  // reset default values in-memory
  selectedTools = new Set();
  selectedServers = new Set();
  selectedCorpusIdsForAutoSearch = new Set();
  selectedCorpusIdsForUserCreation = new Set();
  selectedAutoSearchEnabled = false;
  selectedAutoSearchK = 5;

  resetLocalStorage()
}
