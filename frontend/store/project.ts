import { create } from "zustand"
import type { Project, ProjectActiveState } from "@/types/project"
import { getProject } from "@/lib/api/projects"
import { ApiError } from "@/lib/api/client"

interface ProjectState {
  // Current project loaded in the studio
  currentProject: Project | null
  activeState: ProjectActiveState | null
  // Bumped every time the shared state is refreshed. Layer pages can depend on
  // this to re-read their own content when they come into focus, so the rooms
  // stay coherent as the user moves between them.
  revision: number

  // Actions
  setCurrentProject: (project: Project) => void
  setActiveState: (state: ProjectActiveState) => void
  updateProjectTitle: (title: string) => void
  updateActiveState: (updates: Partial<ProjectActiveState>) => void
  /** Re-pull the project + active pointers from the backend (the shared truth). */
  refresh: (projectId: string) => Promise<void>
  clearProject: () => void
}

export const useProjectStore = create<ProjectState>()((set, get) => ({
  currentProject: null,
  activeState: null,
  revision: 0,

  setCurrentProject: (project) => set({ currentProject: project }),

  setActiveState: (state) =>
    set((s) => ({ activeState: state, revision: s.revision + 1 })),

  updateProjectTitle: (title) =>
    set((s) => ({
      currentProject: s.currentProject
        ? { ...s.currentProject, title }
        : null,
    })),

  updateActiveState: (updates) =>
    set((s) => ({
      // Merge onto whatever we have; if we had nothing yet, seed from the
      // updates so a pointer is never silently dropped.
      activeState: { ...(s.activeState ?? ({} as ProjectActiveState)), ...updates },
      revision: s.revision + 1,
    })),

  refresh: async (projectId: string) => {
    try {
      const { project, active_state } = await getProject(projectId)
      set((s) => ({
        currentProject: project,
        activeState: active_state ?? s.activeState,
        revision: s.revision + 1,
      }))
    } catch (err) {
      // A 404 is permanent (the song doesn't exist or isn't yours): drop any
      // stale song from the store and let the caller redirect. Anything else is
      // treated as transient, so we keep the existing state.
      if (err instanceof ApiError && err.status === 404) {
        set({ currentProject: null, activeState: null })
        throw err
      }
    }
  },

  clearProject: () => set({ currentProject: null, activeState: null, revision: 0 }),
}))
