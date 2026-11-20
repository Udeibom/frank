"use client"

/**
 * The AudioEngine: the one place sound plays from in Frank (design-and-ui.md, "Audio").
 *
 * - Exactly one thing plays at a time, by construction: there is one media element, and playing a new
 *   track replaces the old one.
 * - It lives outside any room, so a sound keeps playing while the user changes rooms, and the Song Strip
 *   can show what is playing and where.
 * - `keepPosition` switches to another sound at the same moment (and in time), so ideas that belong
 *   together can be compared without one being played over the other.
 * - The browser only plays; it never processes audio (audio-architecture.md).
 *
 * Nothing else in the app creates an `Audio` element. The recorder's sample-accurate player (Web Audio, in
 * lib/audio/sessionPlayer.ts) pauses this engine before it starts, so the mic never hears it.
 */

import { create } from "zustand"

/** The four materials of a song; each has a colour (design-and-ui.md). */
export type Material = "words" | "feel" | "music" | "voice"

export interface Track {
  /** Stable id: the same thing played twice must have the same id (a texture id, a version id, ...). */
  id: string
  url: string
  /** What the user would call it: "Direction 2", "Beat v1". Shown in the strip and used in accessible names. */
  label: string
  material: Material
  /** True when the sound is the song itself (or a stand-in for it), so the strip draws a playhead across the sections. */
  onSong?: boolean
  /** Keep going round until paused. */
  loop?: boolean
  /** Play through, go round once more, then stop (Feeling directions: feel-lab requirement 2.2). */
  playsTwice?: boolean
}

interface PlayOptions {
  /** Start here, in seconds. */
  at?: number
  /** Start where the current sound is (wrapped to the new sound's length), so switching stays in time. */
  keepPosition?: boolean
  /** Start this far through the sound (0..1), e.g. at the start of a section. */
  atFraction?: number
}

interface EngineState {
  track: Track | null
  playing: boolean
  loading: boolean
  position: number
  duration: number
  /** Plain-language reason the last sound could not play, or null. */
  problem: string | null

  play: (track: Track, options?: PlayOptions) => Promise<void>
  /** Play it, or pause it if it is the one already playing. */
  toggle: (track: Track, options?: PlayOptions) => Promise<void>
  pause: () => void
  resume: () => void
  /** Move to a point in seconds. */
  seek: (seconds: number) => void
  seekFraction: (fraction: number) => void
  stop: () => void
}

let el: HTMLAudioElement | null = null
let raf = 0
/** For `playsTwice`: whether the current sound has already gone round once. Reset whenever play is pressed. */
let wentRound = false

function element(): HTMLAudioElement {
  if (el) return el
  const audio = new Audio()
  audio.preload = "auto"
  audio.addEventListener("play", () => {
    useAudio.setState({ playing: true, loading: false, problem: null })
    startTicker()
  })
  audio.addEventListener("pause", () => {
    useAudio.setState({ playing: false })
    sync()
  })
  audio.addEventListener("ended", () => {
    if (useAudio.getState().track?.playsTwice && !wentRound) {
      wentRound = true
      audio.currentTime = 0
      audio.play().catch(() => useAudio.setState({ playing: false }))
      return
    }
    useAudio.setState({ playing: false, position: 0 })
  })
  audio.addEventListener("loadedmetadata", () => sync())
  audio.addEventListener("durationchange", () => sync())
  audio.addEventListener("waiting", () => useAudio.setState({ loading: true }))
  audio.addEventListener("playing", () => useAudio.setState({ loading: false }))
  audio.addEventListener("error", () =>
    useAudio.setState({
      playing: false,
      loading: false,
      problem: "That sound wouldn't play. Want to try it again?",
    }),
  )
  el = audio
  return audio
}

function sync() {
  if (!el) return
  const duration = Number.isFinite(el.duration) ? el.duration : 0
  useAudio.setState({ position: el.currentTime, duration })
}

function startTicker() {
  cancelAnimationFrame(raf)
  const tick = () => {
    if (!el || el.paused) return
    sync()
    raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)
}

function whenReady(audio: HTMLAudioElement): Promise<void> {
  if (audio.readyState >= 1) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const ok = () => {
      cleanup()
      resolve()
    }
    const bad = () => {
      cleanup()
      reject(new Error("load failed"))
    }
    const cleanup = () => {
      audio.removeEventListener("loadedmetadata", ok)
      audio.removeEventListener("error", bad)
    }
    audio.addEventListener("loadedmetadata", ok)
    audio.addEventListener("error", bad)
  })
}

export const useAudio = create<EngineState>()((set, get) => ({
  track: null,
  playing: false,
  loading: false,
  position: 0,
  duration: 0,
  problem: null,

  play: async (track, options = {}) => {
    const audio = element()
    wentRound = false
    const current = get().track
    const same = current?.id === track.id && audio.src !== "" && current.url === track.url

    if (!same) {
      // Where to start in the new sound.
      const carry = options.keepPosition ? audio.currentTime : null
      set({ track, loading: true, problem: null, position: 0, duration: 0 })
      audio.loop = Boolean(track.loop)
      audio.src = track.url
      audio.load()
      try {
        await whenReady(audio)
      } catch {
        set({ loading: false, problem: "That sound wouldn't play. Want to try it again?" })
        return
      }
      const length = Number.isFinite(audio.duration) ? audio.duration : 0
      const start =
        options.at !== undefined
          ? options.at
          : options.atFraction !== undefined
            ? options.atFraction * length
            : carry !== null && length > 0
              ? carry % length
              : 0
      audio.currentTime = Math.max(0, Math.min(start, Math.max(0, length - 0.05)))
    } else if (options.at !== undefined) {
      audio.currentTime = options.at
    } else if (options.atFraction !== undefined && Number.isFinite(audio.duration)) {
      audio.currentTime = options.atFraction * audio.duration
    }

    try {
      await audio.play()
    } catch {
      // The browser can refuse to start sound without a click; the user can press play.
      set({ loading: false })
    }
    sync()
  },

  toggle: async (track, options) => {
    const { track: current, playing } = get()
    if (current?.id === track.id && playing) {
      get().pause()
      return
    }
    await get().play(track, options)
  },

  pause: () => {
    el?.pause()
  },

  resume: () => {
    if (!el || !get().track) return
    el.play().catch(() => {})
  },

  seek: (seconds) => {
    if (!el) return
    const length = Number.isFinite(el.duration) ? el.duration : 0
    el.currentTime = Math.max(0, length ? Math.min(seconds, length) : seconds)
    sync()
  },

  seekFraction: (fraction) => {
    if (!el) return
    const length = Number.isFinite(el.duration) ? el.duration : 0
    if (!length) return
    get().seek(Math.max(0, Math.min(1, fraction)) * length)
  },

  stop: () => {
    if (el) {
      el.pause()
      el.removeAttribute("src")
      el.load()
    }
    set({ track: null, playing: false, loading: false, position: 0, duration: 0 })
  },
}))

/** What a control needs to know about one particular track. */
export function usePlayback(trackId: string | null | undefined) {
  const current = useAudio((s) => s.track?.id)
  const playing = useAudio((s) => s.playing)
  const loading = useAudio((s) => s.loading)
  const position = useAudio((s) => s.position)
  const duration = useAudio((s) => s.duration)
  const isCurrent = Boolean(trackId) && current === trackId
  return {
    isCurrent,
    playing: isCurrent && playing,
    loading: isCurrent && loading,
    position: isCurrent ? position : 0,
    duration: isCurrent ? duration : 0,
    progress: isCurrent && duration > 0 ? position / duration : 0,
  }
}

/** minutes:seconds. Frank never shows bars or beats unless the user asks. */
export function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds))
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`
}
