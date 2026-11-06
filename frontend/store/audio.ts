import { create } from "zustand"
import type { PlaybackState } from "@/types/audio"

interface AudioStore {
  // Currently loaded audio
  currentUrl: string | null
  currentLabel: string | null
  playbackState: PlaybackState
  currentPositionSeconds: number
  durationSeconds: number

  // Actions — playback control only, no processing
  setCurrentAudio: (url: string, label?: string) => void
  setPlaybackState: (state: PlaybackState) => void
  setPosition: (seconds: number) => void
  setDuration: (seconds: number) => void
  clearAudio: () => void
}

export const useAudioStore = create<AudioStore>()((set) => ({
  currentUrl: null,
  currentLabel: null,
  playbackState: "idle",
  currentPositionSeconds: 0,
  durationSeconds: 0,

  setCurrentAudio: (url, label) =>
    set({
      currentUrl: url,
      currentLabel: label ?? null,
      playbackState: "loading",
      currentPositionSeconds: 0,
    }),

  setPlaybackState: (state) => set({ playbackState: state }),

  setPosition: (seconds) => set({ currentPositionSeconds: seconds }),

  setDuration: (seconds) => set({ durationSeconds: seconds }),

  clearAudio: () =>
    set({
      currentUrl: null,
      currentLabel: null,
      playbackState: "idle",
      currentPositionSeconds: 0,
      durationSeconds: 0,
    }),
}))
