import { api } from "./client"
import { pollJob } from "./jobs"
import type {
  JobStatusResponse,
  RefineChooseResponse,
  RefinePreview,
  RefineProposal,
} from "@/types/api"

type Progress = (text: string) => void

function progressOf(onProgress?: Progress) {
  return (s: JobStatusResponse) => {
    const text = (s.result as { progress?: string } | null)?.progress
    if (text && onProgress) onProgress(text)
  }
}

/** Frank listens to the song and comes back with two or three directions to hear. */
export async function askForDirections(
  projectId: string,
  concern: string | null,
  room: "beat" | "mix" | "voice",
  onProgress?: Progress,
  onJob?: (jobId: string) => void,
  signal?: AbortSignal,
): Promise<RefineProposal> {
  const { job_id } = await api.post<{ job_id: string }>(`/projects/${projectId}/refine`, { concern, room })
  onJob?.(job_id)
  const done = await pollJob(job_id, progressOf(onProgress), signal)
  return done.result as unknown as RefineProposal
}

/** A short render of one direction. Changes nothing that's saved. */
export async function previewDirection(
  projectId: string,
  proposalId: string,
  n: number,
  onProgress?: Progress,
  onJob?: (jobId: string) => void,
  signal?: AbortSignal,
): Promise<RefinePreview> {
  const { job_id } = await api.post<{ job_id: string }>(`/projects/${projectId}/refine/${proposalId}/preview/${n}`)
  onJob?.(job_id)
  const done = await pollJob(job_id, progressOf(onProgress), signal)
  return done.result as unknown as RefinePreview
}

/** Put the chosen direction into the song as a new version. Returns the job to wait for. */
export function chooseDirection(projectId: string, proposalId: string, n: number): Promise<RefineChooseResponse> {
  return api.post<RefineChooseResponse>(`/projects/${projectId}/refine/${proposalId}/choose/${n}`)
}

/** "That's not it": the person's ears win; Frank asks what their word means. */
export function disagree(projectId: string, proposalId: string, said: string): Promise<{ message: string }> {
  return api.post<{ message: string }>(`/projects/${projectId}/refine/${proposalId}/disagree`, { said })
}

export function renameVersion(
  projectId: string,
  layer: "beat" | "mix",
  versionId: string,
  label: string,
): Promise<{ id: string; label: string }> {
  return api.patch(`/projects/${projectId}/versions/${layer}/${versionId}`, { label })
}
