import { api } from "./client"
import type { JobStatusResponse } from "@/types/api"

const POLL_INTERVAL_MS = 2000
const MAX_POLL_ATTEMPTS = 150 // 5 minutes max

/**
 * Poll a job until it completes or fails.
 * Returns the final job result when complete.
 * Throws if the job fails or times out.
 */
export async function pollJob(
  jobId: string,
  onProgress?: (status: JobStatusResponse) => void,
): Promise<JobStatusResponse> {
  let attempts = 0

  while (attempts < MAX_POLL_ATTEMPTS) {
    await sleep(POLL_INTERVAL_MS)

    const status = await api.get<JobStatusResponse>(`/jobs/${jobId}/status`)

    onProgress?.(status)

    if (status.status === "complete") return status
    if (status.status === "failed") {
      throw new Error(status.error ?? "Job failed without an error message")
    }

    attempts++
  }

  throw new Error("Job timed out — it's taking longer than expected")
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
