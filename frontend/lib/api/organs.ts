/**
 * Calls for Frank's new organs (frankenstein spec 14). Each returns plain data or a job to poll; the rooms decide
 * how to show it. Nothing here processes audio: files go up to the backend, sounds come back as addresses.
 */
import { api, uploadFile } from "./client"
import type {
  CreditLine,
  JamendoTrack,
  JobResponse,
  LyricEmotions,
  LyricsAnalysis,
  RankedDirection,
  RhymeSuggestions,
  SongReference,
  StartReply,
} from "@/types/api"

const p = (projectId: string) => `/projects/${projectId}`

// words
export const analyseLyrics = (projectId: string, text: string) =>
  api.post<LyricsAnalysis>(`${p(projectId)}/lyrics/analyse`, { text })
export const findRhymes = (projectId: string, word: string) =>
  api.post<RhymeSuggestions>(`${p(projectId)}/lyrics/rhymes`, { word })
export const lyricEmotions = (projectId: string, text: string) =>
  api.post<LyricEmotions>(`${p(projectId)}/lyrics/emotions`, { text })

// starting points in the world
export function startFromPicture(projectId: string, file: File): Promise<StartReply> {
  const form = new FormData()
  form.append("file", file)
  return uploadFile<StartReply>(`${p(projectId)}/intake/picture`, form)
}
export const startFromMoment = (projectId: string, latitude: number, longitude: number, hour: number) =>
  api.post<StartReply>(`${p(projectId)}/intake/moment`, { latitude, longitude, hour })

// references
export const listReferences = (projectId: string) => api.get<{ references: SongReference[] }>(`${p(projectId)}/references`)
export const searchFreeMusic = (projectId: string, q: string) =>
  api.get<{ tracks: JamendoTrack[]; message?: string }>(`${p(projectId)}/references/jamendo?q=${encodeURIComponent(q)}`)
export const pickFreeMusic = (projectId: string, trackId: string) =>
  api.post<JobResponse>(`${p(projectId)}/references/jamendo`, { track_id: trackId })
export const nameASong = (projectId: string, text: string) => api.post<JobResponse>(`${p(projectId)}/references/named`, { text })
export function uploadReference(projectId: string, file: File): Promise<JobResponse> {
  const form = new FormData()
  form.append("file", file)
  form.append("rights_confirmed", "true")
  return uploadFile<JobResponse>(`${p(projectId)}/references/upload`, form)
}
export const forgetReference = (projectId: string, id: string) => api.post<{ ok: boolean }>(`${p(projectId)}/references/${id}/forget`, {})

// feeling
export const rankedDirections = (projectId: string) =>
  api.get<{ ranked: RankedDirection[]; words: string[]; note: string | null }>(`${p(projectId)}/feel/ranked`)

// music and blend
export const accompanyTune = (projectId: string) => api.post<JobResponse>(`${p(projectId)}/beat/accompany`, {})
export const addAtmosphere = (projectId: string, source: "recorded" | "generated" = "recorded", words?: string[]) =>
  api.post<JobResponse>(`${p(projectId)}/mix/atmosphere`, { source, words })
export const switchAtmosphere = (projectId: string, enabled: boolean, level_db?: number) =>
  api.post<JobResponse>(`${p(projectId)}/mix/atmosphere/switch`, { enabled, level_db })
export const listenToSong = (projectId: string, concern?: string) =>
  api.post<JobResponse>(`${p(projectId)}/listen`, { concern: concern || null })

// voice
export const quietTake = (projectId: string, takeId: string) => api.post<JobResponse>(`${p(projectId)}/voice/takes/${takeId}/quiet`, {})
export const takeAsInstrument = (projectId: string, takeId: string, instrument: string) =>
  api.post<JobResponse>(`${p(projectId)}/voice/takes/${takeId}/instrument`, { instrument })
export const sungGuide = (projectId: string) => api.post<JobResponse>(`${p(projectId)}/voice/guide/sung`, {})

// finish
export const downloadNotes = (projectId: string) => api.post<{ url: string; filename: string }>(`${p(projectId)}/finish/notes`, {})
export const songCredits = (projectId: string) => api.get<{ credits: CreditLine[]; made_with: string }>(`${p(projectId)}/finish/credits`)
export function matchToReference(projectId: string, mixVersionId: string, source: { file?: File; jamendoTrackId?: string }): Promise<JobResponse> {
  const form = new FormData()
  form.append("mix_version_id", mixVersionId)
  if (source.file) {
    form.append("file", source.file)
    form.append("rights_confirmed", "true")
  }
  if (source.jamendoTrackId) form.append("jamendo_track_id", source.jamendoTrackId)
  return uploadFile<JobResponse>(`${p(projectId)}/export/match`, form)
}

// everywhere
export const speakNote = (projectId: string, text: string) =>
  api.post<{ audio_url: string | null; message?: string }>(`${p(projectId)}/conversation/speak`, { text })
export const soundPeaks = (projectId: string, url: string, points = 600) =>
  api.get<{ peaks: number[]; seconds: number }>(`${p(projectId)}/song/peaks?url=${encodeURIComponent(url)}&points=${points}`)
