import { createBrowserClient } from "@supabase/ssr"

/**
 * Browser-side Supabase client. Uses only the PUBLIC anon key. It is used for
 * signing in/out and reading the session token to send to Frank's backend; it
 * never reads tables directly (Row Level Security would return nothing).
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  )
}
