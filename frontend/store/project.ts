import { create } from "zustand"
import type { Project, ProjectActiveState } from "@/types/project"

interface ProjectState {
  // Current project loaded in the studio
  currentProject: Project | null
  activeState: ProjectActiveState | null

  // Actions
  setCurrentProject: (project: Project) => void
  setActiveState: (state: ProjectActiveState) => void
  updateProjectTitle: (title: string) => void
  updateActiveState: (updates: Partial<ProjectActiveState>) => void
  clearProject: () => void
}

export const useProjectStore = create<ProjectState>()((set) => ({
  currentProject: null,
  activeState: null,

  setCurrentProject: (project) => set({ currentProject: project }),

  setActiveState: (state) => set({ activeState: state }),

  updateProjectTitle: (title) =>
    set((s) => ({
      currentProject: s.currentProject
        ? { ...s.currentProject, title }
        : null,
    })),

  updateActiveState: (updates) =>
    set((s) => ({
      activeState: s.activeState
        ? { ...s.activeState, ...updates }
        : null,
    })),

  clearProject: () => set({ currentProject: null, activeState: null }),
}))
