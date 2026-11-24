/**
 * Cliente HTTP da API. A sessão vive em cookie httpOnly (o JavaScript não
 * enxerga o token). Se a API responder 401, tentamos renovar a sessão uma vez
 * com /auth/refresh e repetimos a chamada.
 */

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(ApiError.messageFrom(detail) ?? `Erro ${status}`);
    this.status = status;
    this.detail = detail;
  }

  static messageFrom(detail: unknown): string | undefined {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // Erros de validação do FastAPI: [{loc, msg}, ...]
      const first = detail[0] as { msg?: string; loc?: unknown[] } | undefined;
      if (first?.msg) {
        const field = first.loc?.at(-1);
        const msg = first.msg.replace(/^Value error, /, "");
        return typeof field === "string" ? `${field}: ${msg}` : msg;
      }
    }
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message);
    }
    return undefined;
  }
}

const BASE = import.meta.env.VITE_API_URL ?? "";

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  refreshing ??= fetch(`${BASE}/api/v1/auth/refresh`, {
    method: "POST",
    credentials: "include",
  })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

type Options = { method?: string; body?: unknown; query?: Record<string, unknown> };

export async function api<T>(path: string, opts: Options = {}, retry = true): Promise<T> {
  const url = new URL(`${BASE}/api/v1${path}`, window.location.origin);
  for (const [key, value] of Object.entries(opts.query ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  const resp = await fetch(url, {
    method: opts.method ?? "GET",
    credentials: "include",
    headers: opts.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  const isAuthRoute = path.startsWith("/auth/");
  if (resp.status === 401 && retry && !isAuthRoute && (await tryRefresh())) {
    return api<T>(path, opts, false);
  }
  if (resp.status === 204) return undefined as T;

  const data = await resp.json().catch(() => null);
  if (!resp.ok) throw new ApiError(resp.status, data?.detail ?? data);
  return data as T;
}
