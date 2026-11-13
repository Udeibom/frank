import { create } from "zustand"
import type { SongPhase, SongRecord } from "@/types/song"
import { getSong, setSongPhase } from "@/lib/api/song"

interface SongState {
  record: SongRecord | null
  /** Pull the whole song from the server (the shared truth). Failures keep what we have. */
  load: (projectId: string) => Promise<void>
  /** Move between creating and refining; updates the screen first, reverts if the save fails. */
  setPhase: (projectId: string, phase: SongPhase) => Promise<void>
  clear: () => void
}

let latestLoad = 0

export const useSongStore = create<SongState>()((set, get) => ({
  record: null,

  load: async (projectId) => {
    // Switching songs: drop the old song's record straight away.
    if (get().record && get().record!.project_id !== projectId) set({ record: null })
    const ticket = ++latestLoad
    try {
      const record = await getSong(projectId)
      // A slower, older reply must not overwrite a newer one.
      if (ticket === latestLoad) set({ record })
    } catch {
      // Transient: keep the last known record rather than blanking the studio.
    }
  },

  setPhase: async (projectId, phase) => {
    const before = get().record
    if (!before) return
    set({ record: { ...before, phase } })
    try {
      await setSongPhase(projectId, phase)
    } catch {
      set({ record: before })
    }
  },

  clear: () => set({ record: null }),
}))
