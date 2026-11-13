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
