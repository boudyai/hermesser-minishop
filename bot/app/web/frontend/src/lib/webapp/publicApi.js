import { readCookie } from "./session.js";

export function createApiClient({
  apiBase = "",
  csrfCookieName = "rw_webapp_csrf",
  getCsrfToken = () => "",
  onUnauthorized = () => {},
  mockApi = null,
  getMockContext = () => ({}),
} = {}) {
  const isFormDataBody = (body) => typeof FormData !== "undefined" && body instanceof FormData;

  async function api(path, options = {}) {
    if (mockApi) return mockApi(path, options, getMockContext());

    const method = String(options.method || "GET").toUpperCase();
    const headers = { ...(options.headers || {}) };

    const csrf = getCsrfToken() || readCookie(csrfCookieName) || "";
    if (csrf && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      headers["X-CSRF-Token"] = csrf;
    }
    if (options.body && !headers["Content-Type"] && !isFormDataBody(options.body)) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(`${apiBase}${path}`, {
      ...options,
      headers,
      credentials: "same-origin",
    });
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) onUnauthorized();
    return payload;
  }

  async function publicApi(path, payload = {}, options = {}) {
    if (mockApi) {
      return mockApi(path, { method: "POST", body: JSON.stringify(payload) }, getMockContext());
    }
    const response = await fetch(`${apiBase}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: options.signal,
      credentials: "same-origin",
    });
    return response.json();
  }

  return { api, publicApi };
}
