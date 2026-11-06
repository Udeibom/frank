import { create } from "zustand"

interface SessionState {
  // Dev stub — replaced with real Supabase auth session in Spec 08
  userId: string
  isAuthenticated: boolean
  setUserId: (id: string) => void
}

export const useSessionStore = create<SessionState>()((set) => ({
  userId: "00000000-0000-0000-0000-000000000001", // dev user ID
  isAuthenticated: true, // always true until auth is implemented
  setUserId: (id) => set({ userId: id }),
}))
