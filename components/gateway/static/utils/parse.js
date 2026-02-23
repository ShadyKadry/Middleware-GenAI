export function parseMultiValue(value) {
  if (!value) return [];
  return value
    .split(/[;,]/)
    .map((v) => v.trim())
    .filter(Boolean);
}

export function parseArgs(value) {
  if (!value) return [];
  return value
    .split(/\r?\n/)
    .map((v) => v.trim())
    .filter(Boolean);
}

export function parseHeaders(value) {
  const trimmed = (value || "").trim();
  if (!trimmed) return { headers: {}, error: null };

  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return { headers: {}, error: "Headers JSON must be an object." };
      }
      return { headers: parsed, error: null };
    } catch (err) {
      return { headers: {}, error: "Headers JSON is invalid." };
    }
  }

  const headers = {};
  const lines = trimmed.split(/\r?\n/);
  for (const line of lines) {
    if (!line.trim()) continue;
    const idx = line.indexOf(":");
    if (idx === -1) {
      return { headers: {}, error: "Headers must be in 'Key: Value' format." };
    }
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    if (!key || !value) {
      return { headers: {}, error: "Headers must be in 'Key: Value' format." };
    }
    headers[key] = value;
  }

  return { headers, error: null };
}