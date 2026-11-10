// Base API client — all requests go through here
// API keys never live in frontend code — all sensitive calls are made server-side
import { createClient } from "@/lib/supabase/client"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail)
    this.name = "ApiError"
  }
}

/** The signed-in user's access token, or null when signed out. */
async function authHeader(): Promise<Record<string, string>> {
  const { data } = await createClient().auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
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
  const url = `${API_URL}${path}`

  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(await authHeader()),
      ...options.headers,
    },
    ...options,
  })

  if (!res.ok) {
    return fail(res, "Something went wrong — want to try again?")
  }

  return res.json() as Promise<T>
}

export async function uploadFile<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const url = `${API_URL}${path}`

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
