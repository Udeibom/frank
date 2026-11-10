import { create } from "zustand"

/**
 * Who is signed in. The real session lives in Supabase's cookies (managed by
 * @supabase/ssr and checked in middleware.ts); this store is just a convenient
 * client-side copy for components that want to show it.
 */
interface SessionState {
  userId: string | null
  email: string | null
  isAuthenticated: boolean
  setSession: (user: { id: string; email: string | null } | null) => void
}

export const useSessionStore = create<SessionState>()((set) => ({
  userId: null,
  email: null,
  isAuthenticated: false,
  setSession: (user) =>
    set(
      user
        ? { userId: user.id, email: user.email, isAuthenticated: true }
        : { userId: null, email: null, isAuthenticated: false },
    ),
}))
