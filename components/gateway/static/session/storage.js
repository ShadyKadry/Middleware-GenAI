const SELECTED_TOOLS_STORAGE_KEY = "enabled_tools_v1";
const SELECTED_SERVERS_STORAGE_KEY = "enabled_servers_v1";
const SELECTED_CORPORA_AUTO_SEARCH_STORAGE_KEY = "enabled_corpora_auto_search_v1";
const SELECTED_CORPORA_USER_CREATION_STORAGE_KEY = "enabled_corpora_user_creation_v1"
const SELECTED_AUTO_SEARCH_ENABLED_KEY = "enabled_auto_search_v1"
const SELECTED_AUTO_SEARCH_K_KEY = "enabled_auto_search_k_results_v1"


/**
 *
 * This class provides getters/setters from/to local storage. This enables session-persistence of selected
 * tools/corpora for a logged-in user. LocalStorage is cleared on logout, meaning selections are invalidated.
 *
 * **/


/*** - - - - - - - - - - - - - - - - - ***/
/*** - - - LocalStorage: LOADERS - - - ***/
/*** - - - - - - - - - - - - - - - - - ***/

function loadSetFromLocalStorage(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return new Set();

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();

    return new Set(parsed);
  } catch {
    return new Set();
  }
}

export function loadSelectedTools() {
  return loadSetFromLocalStorage(SELECTED_TOOLS_STORAGE_KEY);
}

export function loadSelectedServers() {
  return loadSetFromLocalStorage(SELECTED_SERVERS_STORAGE_KEY);
}

export function loadSelectedCorpusIdsForAutoSearch() {
  return loadSetFromLocalStorage(SELECTED_CORPORA_AUTO_SEARCH_STORAGE_KEY);
}

export function loadSelectedCorpusIdsForUserCreation() {
  return loadSetFromLocalStorage(SELECTED_CORPORA_USER_CREATION_STORAGE_KEY);
}

export function loadSelectedAutoSearchEnabled() {
  try {
    const raw = localStorage.getItem(SELECTED_AUTO_SEARCH_ENABLED_KEY);
    if (raw == null) return null;
    const data = JSON.parse(raw);
    return typeof data === "boolean" ? data : null;
  } catch (_) {
    return null;
  }
}

export function loadSelectedAutoSearchK() {
  try {
    const raw = localStorage.getItem(SELECTED_AUTO_SEARCH_K_KEY);
    if (raw == null) return null;
    const data = JSON.parse(raw);
    return typeof data === "number" && Number.isFinite(data) ? data : null;
  } catch (_) {
    return null;
  }
}


/*** - - - - - - - - - - - - - - - - - ***/
/*** - - - LocalStorage: SAVERS  - - - ***/
/*** - - - - - - - - - - - - - - - - - ***/

export function saveSelectedTools(selectedToolsToBeSaved) {
  try {
    localStorage.setItem(SELECTED_TOOLS_STORAGE_KEY, JSON.stringify([...selectedToolsToBeSaved]));
  } catch (_) {}
}


export function saveSelectedServers(selectedServersToBeSaved) {
  try {
    localStorage.setItem(SELECTED_SERVERS_STORAGE_KEY, JSON.stringify([...selectedServersToBeSaved]));
  } catch (_) {}
}


export function saveSelectedCorpusIdsForAutoSearch(selectedCorpusIdsForAutoSearchToBeSaved) {
  try {
    localStorage.setItem(SELECTED_CORPORA_AUTO_SEARCH_STORAGE_KEY, JSON.stringify([...selectedCorpusIdsForAutoSearchToBeSaved]));
  } catch (_) {}
}


export function saveSelectedCorpusIdsForUserCreation(selectedCorpusIdsForUserCreationToBeSaved) {
  try {
    localStorage.setItem(SELECTED_CORPORA_USER_CREATION_STORAGE_KEY, JSON.stringify([...selectedCorpusIdsForUserCreationToBeSaved]));
  } catch (_) {}
}


export function saveSelectedAutoSearchEnabled(enabled) {
  try {
    localStorage.setItem(SELECTED_AUTO_SEARCH_ENABLED_KEY, JSON.stringify(enabled));
  } catch (_) {}
}


export function saveSelectedAutoSearchK(k) {
  try {
    localStorage.setItem(SELECTED_AUTO_SEARCH_K_KEY, JSON.stringify(k));
  } catch (_) {}
}


export function resetLocalStorage() {
  localStorage.clear();
}
