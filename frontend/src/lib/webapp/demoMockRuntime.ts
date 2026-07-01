export const DEMO_LANGUAGE_STORAGE_KEY = "rw_minishop_demo_language";

export type DemoRecord = Record<string, unknown>;

type DemoRequestOptions =
  | {
      body?: unknown;
    }
  | null
  | undefined;

export function readStoredDemoLanguage(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage?.getItem(DEMO_LANGUAGE_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function writeDemoLanguage(language: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage?.setItem(DEMO_LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Demo storage can be unavailable in private contexts; the in-memory mock still updates.
  }
}

export function queryParams(path: unknown): URLSearchParams {
  return new URLSearchParams(String(path || "").split("?")[1] || "");
}

export function jsonBody(options: DemoRequestOptions): DemoRecord {
  try {
    const body = options?.body;
    if (!body) return {};
    const payload = JSON.parse(String(body));
    return payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as DemoRecord)
      : {};
  } catch {
    return {};
  }
}

export function paged<T>(
  items: readonly T[] | null | undefined,
  params: URLSearchParams,
  fallbackSize = 25
): { items: T[]; page: number; pageSize: number; total: number } {
  const source = Array.isArray(items) ? items : [];
  const total = source.length;
  if (params.has("limit") || params.has("offset")) {
    const limit = Math.max(1, Number(params.get("limit") || fallbackSize));
    const offset = Math.max(0, Number(params.get("offset") || 0));
    return {
      items: source.slice(offset, offset + limit),
      total,
      page: Math.floor(offset / limit),
      pageSize: limit,
    };
  }
  const page = Math.max(0, Number(params.get("page") || 0));
  const pageSize = Math.max(1, Number(params.get("page_size") || fallbackSize));
  const start = page * pageSize;
  return { items: source.slice(start, start + pageSize), total, page, pageSize };
}

export function stringDate(value: unknown): number {
  const time = Date.parse(String(value || ""));
  return Number.isFinite(time) ? time : 0;
}

export function compareNullableDate(
  a: unknown,
  b: unknown,
  direction: "asc" | "desc" = "asc"
): number {
  const at = stringDate(a);
  const bt = stringDate(b);
  if (!at && !bt) return 0;
  if (!at) return 1;
  if (!bt) return -1;
  return direction === "desc" ? bt - at : at - bt;
}
