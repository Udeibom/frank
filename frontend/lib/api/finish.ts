import { api } from "./client"
import { pollJob } from "./jobs"

/** Finishing a song (finish-and-intent spec 11). */

export interface SongParts {
  parts: string[]
  sections: { index: number; name: string }[]
  ready: boolean
}

export interface IntentState {
  intent: string | null
  question: string
  answered: "yes" | "not_yet" | null
}

export interface IntentReply {
  next: "export" | "refine"
  concern?: string
  message: string
}

export interface SurpriseResult {
  title: string
  plain: string
  beat_version_id: string
  label: string | null
  render_url: string
  message: string
}

/** What each part is called on screen. */
export const PART_NAMES: Record<string, string> = {
  drums: "Drums",
  bass: "Bass",
  keys: "Keys",
  melody: "The tune",
  accompaniment: "Around your tune",
  pad: "Soft background",
  strings: "Strings",
  arp: "Running pattern",
  extras: "Little touches",
}

export function getParts(projectId: string): Promise<SongParts> {
  return api.get<SongParts>(`/projects/${projectId}/finish/parts`)
}

export function getIntent(projectId: string): Promise<IntentState> {
  return api.get<IntentState>(`/projects/${projectId}/finish/intent`)
}

export function answerIntent(projectId: string, yes: boolean, said?: string): Promise<IntentReply> {
  return api.post<IntentReply>(`/projects/${projectId}/finish/intent`, { yes, said: said ?? null })
}

export function surpriseOffered(projectId: string): Promise<{ offered: boolean }> {
  return api.get(`/projects/${projectId}/finish/surprise`)
}

export async function makeSurprise(projectId: string, onProgress?: (t: string) => void): Promise<SurpriseResult> {
  const { job_id } = await api.post<{ job_id: string }>(`/projects/${projectId}/finish/surprise`)
  const done = await pollJob(job_id, (s) => {
    const t = (s.result as { progress?: string } | null)?.progress
    if (t && onProgress) onProgress(t)
  })
  return done.result as unknown as SurpriseResult
}

export async function separatePartsZip(projectId: string): Promise<{ zip_url: string; parts: string[] }> {
  const { job_id } = await api.post<{ job_id: string }>(`/projects/${projectId}/finish/parts.zip`)
  const done = await pollJob(job_id)
  return done.result as unknown as { zip_url: string; parts: string[] }
}

export async function skipSurprise(projectId: string): Promise<void> {
  await api.post(`/projects/${projectId}/finish/surprise/skip`)
}
