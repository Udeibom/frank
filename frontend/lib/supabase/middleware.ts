import { createServerClient } from "@supabase/ssr"
import { isAuthRetryableFetchError } from "@supabase/supabase-js"
import { NextResponse, type NextRequest } from "next/server"

// Pages anyone can open without an account.
const PUBLIC_PATHS = ["/", "/login", "/signup"]
// Logged-in users have no reason to see these.
const AUTH_PATHS = ["/login", "/signup"]

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.includes(pathname)
}

/**
 * Refreshes the Supabase session on every navigation (required for cookie-based
 * auth) and redirects:
 *   - signed-out visitors on a studio page  -> /login?next=<where they were going>
 *   - signed-in users on /login or /signup  -> /songs
 *
 * getUser() asks Supabase Auth to confirm the session; it is not trusting the
 * cookie alone.
 */
export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          // Cookies must be set on BOTH the request and the response.
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
          response = NextResponse.next({ request })
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          )
        },
      },
    },
  )

  const {
    data: { user },
    error,
  } = await supabase.auth.getUser()

  const { pathname, search } = request.nextUrl

  // A dropped connection to Supabase is not the same as being signed out. Treating it as signed out sent people
  // to /login (and from there to /songs) in the middle of a session whenever the network blinked, including on
  // background prefetches, which Next.js then followed as a full page change (found Nov 20, studio redesign).
  // When we simply couldn't ask, let the page through: the backend still checks the token on every API call, and
  // a session that has really ended is caught there (lib/api/client.ts sends the person to log in).
  if (!user && error && isAuthRetryableFetchError(error)) {
    return response
  }

  const redirectTo = (url: URL) => {
    const redirect = NextResponse.redirect(url)
    // Carry over any refreshed session cookies.
    response.cookies.getAll().forEach((c) => redirect.cookies.set(c))
    return redirect
  }

  if (!user && !isPublicPath(pathname)) {
    const url = request.nextUrl.clone()
    url.pathname = "/login"
    url.search = ""
    url.searchParams.set("next", pathname + search)
    return redirectTo(url)
  }

  if (user && AUTH_PATHS.includes(pathname)) {
    const url = request.nextUrl.clone()
    url.pathname = "/songs"
    url.search = ""
    return redirectTo(url)
  }

  return response
}
