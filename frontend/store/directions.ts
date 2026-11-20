import { create } from "zustand"
import { getTextureWaveform, listTextures } from "@/lib/api/feel"

/**
 * Directions: the sounds Frank has played to find the song's feeling (the Feeling room's bench).
 * Shared, because the Song Strip shows whether a feeling has been tried or kept from every room.
 * Nothing is ever dropped from this list (project-layer.md: if in doubt, keep it).
 */
export interface Direction {
  id: string
  url: string
  /** "Direction 1", "Direction 2": named in the order they were made. */
  number: number
  createdAt: string | null
  status: "ready" | "making" | "failed"
  /** null = still being measured; [] = could not be measured. */
  waveform: number[] | null
  /** One line about how it sounds, in plain words (this visit only; not stored). */
  note?: string
  /** The person said "not this" (this visit only). */
  setAside?: boolean
}

interface DirectionsState {
  projectId: string | null
  directions: Direction[]
  loaded: boolean
  load: (projectId: string) => Promise<void>
  /** A ghost card while a direction is being made. Returns its temporary id. */
  startMaking: () => string
  finishMaking: (tempId: string, made: { id: string; url: string; waveform: number[] | null; note?: string }) => void
  failMaking: (tempId: string) => void
  setAside: (id: string) => void
  setWaveform: (id: string, points: number[]) => void
  /** Only for cards that never became a direction (a failed attempt the person dismissed). */
  remove: (id: string) => void
  clear: () => void
}

type Set = (fn: Partial<DirectionsState> | ((s: DirectionsState) => Partial<DirectionsState>)) => void
type Get = () => DirectionsState

let inflight: { projectId: string; promise: Promise<void> } | null = null

function renumber(list: Direction[]): Direction[] {
  let n = 0
  return list.map((d) => (d.status === "ready" ? { ...d, number: ++n } : d))
}

async function fetchAll(projectId: string, set: Set, get: Get): Promise<void> {
  if (get().projectId !== projectId) set({ projectId, directions: [], loaded: false })
  let records
  try {
    records = await listTextures(projectId)
  } catch {
    // Transient: keep what we have rather than emptying the bench.
    set({ loaded: true })
    return
  }
  if (get().projectId !== projectId) return
  set((s) => {
    const known = new Map(s.directions.map((d) => [d.id, d]))
    const fromServer: Direction[] = records.map((r) => ({
      id: r.id,
      url: r.audio_url,
      number: 0,
      createdAt: r.created_at,
      status: "ready" as const,
      waveform: known.get(r.id)?.waveform ?? null,
      note: known.get(r.id)?.note,
      setAside: known.get(r.id)?.setAside,
    }))
    const inFlight = s.directions.filter((d) => d.status !== "ready")
    return { directions: renumber([...fromServer, ...inFlight]), loaded: true }
  })

  // Measure each shape, two at a time, so the bench fills in without stampeding a small server.
  const queue = get().directions.filter((d) => d.status === "ready" && d.waveform === null)
  const worker = async () => {
    for (let d = queue.shift(); d; d = queue.shift()) {
      let points: number[] = []
      try {
        points = await getTextureWaveform(projectId, d.id)
      } catch {
        points = []
      }
      if (get().projectId !== projectId) return
      set((s) => ({ directions: s.directions.map((x) => (x.id === d.id ? { ...x, waveform: points } : x)) }))
    }
  }
  await Promise.all([worker(), worker()])
}

export const useDirections = create<DirectionsState>()((set, get) => ({
  projectId: null,
  directions: [],
  loaded: false,

  // Asking twice for the same song (the strip and the Feeling room both do) shares one request, and a song
  // that is already loaded is not fetched again: directions only change through this store.
  load: (projectId) => {
    if (get().projectId === projectId && get().loaded) return Promise.resolve()
    if (inflight && inflight.projectId === projectId) return inflight.promise
    const promise: Promise<void> = fetchAll(projectId, set, get).finally(() => {
      if (inflight?.promise === promise) inflight = null
    })
    inflight = { projectId, promise }
    return promise
  },

  startMaking: () => {
    const tempId = `making-${crypto.randomUUID()}`
    set((s) => ({
      directions: [
        ...s.directions,
        { id: tempId, url: "", number: 0, createdAt: null, status: "making", waveform: null },
      ],
    }))
    return tempId
  },

  finishMaking: (tempId, made) =>
    set((s) => {
      // The same direction can come back (identical parameters reuse a stored one): do not show it twice.
      const already = s.directions.some((d) => d.id === made.id && d.id !== tempId)
      const directions = already
        ? s.directions.filter((d) => d.id !== tempId)
        : s.directions.map((d) =>
            d.id === tempId
              ? { ...d, id: made.id, url: made.url, status: "ready" as const, waveform: made.waveform, note: made.note, createdAt: new Date().toISOString() }
              : d,
          )
      return { directions: renumber(directions) }
    }),

  failMaking: (tempId) =>
    set((s) => ({ directions: s.directions.map((d) => (d.id === tempId ? { ...d, status: "failed" as const } : d)) })),

  setAside: (id) => set((s) => ({ directions: s.directions.map((d) => (d.id === id ? { ...d, setAside: true } : d)) })),

  setWaveform: (id, points) =>
    set((s) => ({ directions: s.directions.map((d) => (d.id === id ? { ...d, waveform: points } : d)) })),

  remove: (id) => set((s) => ({ directions: renumber(s.directions.filter((d) => d.id !== id || d.status === "ready")) })),

  clear: () => set({ projectId: null, directions: [], loaded: false }),
}))
