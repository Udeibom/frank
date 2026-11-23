// Base API client — all requests go through here
// API keys never live in frontend code — all sensitive calls are made server-side
import { createClient } from "@/lib/supabase/client"

// All backend calls go through the Vercel proxy at /api/frank/.
// Direct calls to the Render backend are dropped by Cloudflare's WAF for any
// request whose combined size exceeds 512 bytes — which every authenticated
// request does (Supabase JWTs are ~930 bytes). The proxy forwards from a
// server-side Vercel IP that the WAF does not rate-limit.
const PROXY_BASE = "/api/frank"

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail)
    this.name = "ApiError"
  }
}

let regionPromise: Promise<string | null> | null = null

/** The visitor's country (once per tab), so the backend can follow Google's regional terms. */
export function region(): Promise<string | null> {
  if (typeof window === "undefined") return Promise.resolve(null)
  if (!regionPromise) {
    const cached = window.sessionStorage.getItem("frank.region")
    regionPromise = cached !== null
      ? Promise.resolve(cached || null)
      : fetch("/api/region")
          .then((r) => r.json() as Promise<{ country: string | null }>)
          .then((d) => {
            window.sessionStorage.setItem("frank.region", d.country ?? "")
            return d.country
          })
          .catch(() => null)
  }
  return regionPromise
}

/** The signed-in user's access token, or null when signed out, plus the visitor's country. */
async function authHeader(): Promise<Record<string, string>> {
  const [{ data }, country] = await Promise.all([createClient().auth.getSession(), region()])
  const token = data.session?.access_token
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(country ? { "X-Frank-Region": country } : {}),
  }
}

/**
 * A 401 means the session ended. Send the user to log in and bring them back
 * to where they were. Skipped on the auth pages so it can't loop.
 */
function handleSessionEnded(status: number): void {
  if (status !== 401 || typeof window === "undefined") return
  const { pathname, search } = window.location
  if (pathname === "/login" || pathname === "/signup") return
  window.location.href = `/login?next=${encodeURIComponent(pathname + search)}`
}

async function fail(res: Response, fallback: string): Promise<never> {
  let detail = fallback
  try {
    const body = await res.json()
    detail = body.detail ?? detail
  } catch {
    // ignore parse errors
  }
  handleSessionEnded(res.status)
  throw new ApiError(res.status, detail)
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${PROXY_BASE}${path}`

  // 55-second timeout — the Vercel proxy has a 60s limit; leave 5s margin.
  // Long-running jobs (beat generation etc.) return a job_id immediately and
  // are polled separately, so this timeout only applies to auth + DB ops.
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 55_000)

  let res: Response
  try {
    res = await fetch(url, {
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(await authHeader()),
        ...options.headers,
      },
      ...options,
    })
  } finally {
    clearTimeout(timeoutId)
  }

  if (res.status < 500) serverAnswered()     // a 5xx from the proxy may mean the server is still asleep
  if (!res.ok) {
    return fail(res, "Something went wrong — want to try again?")
  }

  return res.json() as Promise<T>
}

/** Any answer from the server means it is awake: the waking banner listens for this (core-path spec 15, 6.1). */
export const SERVER_ANSWERED = "frank-server-answered"
function serverAnswered(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(SERVER_ANSWERED))
}

export async function uploadFile<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const url = `${PROXY_BASE}${path}`

  const res = await fetch(url, {
    method: "POST",
    body: formData,
    // Do NOT set Content-Type — browser sets it with boundary for multipart
    headers: await authHeader(),
  })

  if (!res.ok) {
    return fail(res, "That upload didn't go through — want to try again?")
  }

  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
}
