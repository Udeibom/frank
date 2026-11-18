import { api, uploadFile } from "./client"
import { isTransientPollError, pollJob } from "./jobs"
import type { MusicalFingerprint } from "@/types/project"

/** What the hum job reports when it finishes. A turned-away recording is `ok: false`, not an error. */
export type HumIntakeResult =
  | {
      ok: true
      version_id: string
      hum_url: string
      preview_url: string
      description: string
      unsure_about: string[]
    }
  | { ok: false; reason: string; hum_url: string }

export interface ConfirmMelodyResult {
  fingerprint_hints: Partial<MusicalFingerprint>
  /** One question when the tune disagrees with what is settled (which should lead?). */
  question?: string | null
}

/** Send a recorded hum, wait for Frank to work out the tune, and return what it found. */
export async function humToTune(
  projectId: string,
  audioBlob: Blob,
  fileExtension: string = "webm",
): Promise<HumIntakeResult> {
  const formData = new FormData()
  formData.append("file", audioBlob, `hum.${fileExtension}`)
  const send = () =>
    uploadFile<{ job_id: string }>(`/projects/${projectId}/intake/hum`, formData)
  let job_id: string
  try {
    ;({ job_id } = await send())
  } catch (err) {
    // A dropped connection says nothing about the hum. Try once more before giving up.
    if (!isTransientPollError(err)) throw err
    await new Promise((resolve) => setTimeout(resolve, 1500))
    ;({ job_id } = await send())
  }
  const done = await pollJob(job_id)
  return done.result as unknown as HumIntakeResult
}

export async function confirmTune(
  projectId: string,
  versionId: string,
): Promise<ConfirmMelodyResult> {
  return api.post<ConfirmMelodyResult>(
    `/projects/${projectId}/intake/melody/${versionId}/confirm`,
  )
}

export async function rejectTune(projectId: string, versionId: string): Promise<void> {
  await api.post(`/projects/${projectId}/intake/melody/${versionId}/reject`)
}

export interface ReadWordsResult {
  ok: boolean
  /** What Frank says: what the words feel like, and one question if it is unsure. */
  message: string
  /** Parts of the song's direction the words filled in (never anything already settled). */
  filled: string[]
  asked: string | null
}

/** Ask Frank to read the words for their feeling and shape. Sends what is on screen. */
export async function readWords(projectId: string, content: string): Promise<ReadWordsResult> {
  return api.post<ReadWordsResult>(`/projects/${projectId}/intake/lyrics`, { content })
}

/** What the rhythm job reports. A turned-away recording is `ok: false` with a kind reason. */
export type RhythmIntakeResult =
  | {
      ok: true
      preview_url: string
      groove: { tempo_bpm: number; tempo_confidence: number; kick: string; hat: string; confidence: number }
    }
  | { ok: false; reason: string }

/** Send a tapped or spoken rhythm and wait for Frank to work out the pattern. */
export async function rhythmToGroove(
  projectId: string,
  audioBlob: Blob,
  fileExtension: string = "webm",
): Promise<RhythmIntakeResult> {
  const formData = new FormData()
  formData.append("file", audioBlob, `rhythm.${fileExtension}`)
  const send = () =>
    uploadFile<{ job_id: string }>(`/projects/${projectId}/intake/rhythm`, formData)
  let job_id: string
  try {
    ;({ job_id } = await send())
  } catch (err) {
    if (!isTransientPollError(err)) throw err
    await new Promise((resolve) => setTimeout(resolve, 1500))
    ;({ job_id } = await send())
  }
  const done = await pollJob(job_id)
  return done.result as unknown as RhythmIntakeResult
}

export interface DescriptionResult {
  ok: boolean
  message: string
  heard?: string | null
  asked?: string | null
  filled: string[]
}

/** Start from how it should feel, in the person's own typed words. */
export function describeSong(projectId: string, text: string): Promise<DescriptionResult> {
  return api.post<DescriptionResult>(`/projects/${projectId}/intake/description`, { text })
}

/** Start from a spoken description: Frank keeps the recording, writes down the words, and reads them. */
export function describeByVoice(projectId: string, blob: Blob, ext: string): Promise<DescriptionResult> {
  const formData = new FormData()
  formData.append("file", blob, `described.${ext}`)
  return uploadFile<DescriptionResult>(`/projects/${projectId}/intake/voice-memo`, formData)
}

export interface RecordingResult {
  kind: "description" | "hum"
  description?: DescriptionResult | null
  job_id?: string | null
}

/** Hum it, sing it or say it: the backend works out which path a recording takes. */
export function startFromRecording(projectId: string, blob: Blob, ext: string): Promise<RecordingResult> {
  const formData = new FormData()
  formData.append("file", blob, `start.${ext}`)
  return uploadFile<RecordingResult>(`/projects/${projectId}/intake/recording`, formData)
}
