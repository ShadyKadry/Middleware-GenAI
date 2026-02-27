
/**
 * API: Fetches available embedding models and default model ID.
 * @returns {{ models: Array, defaultId: string } | null}
 */
export async function getEmbeddingModels() {
  const res = await fetch("/api/admin/embedding-models", {
    credentials: "include",
  });

  if (!res.ok) return null;

  const data = await res.json().catch(() => null);
  if (!data || typeof data !== "object") return null;

  const models = Array.isArray(data.models) ? data.models : [];
  const defaultId = typeof data.default === "string" ? data.default : (models[0]?.id ?? "");

  return { models, defaultId };
}


/**
 * API: Fetches available database models and default model ID.
 * @returns {{ models: Array, defaultId: string } | null}
 */
export async function getDatabaseModels() {
  const res = await fetch("/api/admin/database-models", {
    credentials: "include",
  });

  if (!res.ok) return null;

  const data = await res.json().catch(() => null);
  if (!data || typeof data !== "object") return null;

  const models = Array.isArray(data.models) ? data.models : [];
  const defaultId = typeof data.default === "string" ? data.default : (models[0]?.id ?? "");

  return { models, defaultId };
}


/**
 * API: Fetches the current authenticated user info.
 * @returns {Object | null}
 */
export async function getMe() {
  const res = await fetch("/api/me");
  if (!res.ok) return null;

  return await res.json().catch(() => null);
}


/**
 * API: Bootstraps all available MCP servers/tools for this user.
 * @returns {Object}
 * @throws {Error} If bootstrapping fails
 */
export async function bootstrapMCPTools() {
  const res = await fetch("/api/chat/bootstrap", {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Bootstrapping MCP failed: ${text}`);
  }

  return await res.json().catch(() => {
    throw new Error("Bootstrapping MCP failed: invalid JSON response");
  });
}


/**
 * API: Bootstraps all available document corpora for this user.
 * @returns {Object}
 * @throws {Error} If bootstrapping fails
 */
export async function bootstrapCorpora() {
  const res = await fetch("/api/corpora/bootstrap", {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Bootstrapping corpora failed: ${text}`);
  }

  return await res.json().catch(() => {
    throw new Error("Bootstrapping corpora failed: invalid JSON response");
  });
}