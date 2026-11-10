import { api, ApiError } from "./client"
import type { JobStatusResponse } from "@/types/api"

// Poll quickly at first (most jobs finish in seconds), then ease off.
const FAST_POLL_MS = 2000
const SLOW_POLL_MS = 5000
const FAST_PHASE_MS = 60_000
// Longer than the server's 10-minute stale limit (job-reliability spec 4.1), so
// a stuck job is reported as failed by the server rather than timed out here.
const MAX_WAIT_MS = 12 * 60_000
// How many polls in a row may fail for transient reasons (network blip, 5xx)
// before we give up. A job keeps running on the server while a poll fails, so
// one bad poll must never be reported as a failed job.
const MAX_CONSECUTIVE_POLL_ERRORS = 8

/** Errors worth retrying: no response at all, or a server-side 5xx. */
export function isTransientPollError(err: unknown): boolean {
  if (err instanceof ApiError) return err.status >= 500
  return true // fetch threw (offline, DNS, TLS): the server never answered
}

/**
 * Poll a job until it completes or fails.
 * Returns the final job result when complete.
 * Throws if the job fails, can't be found, the session ended, or it times out.
 */
export async function pollJob(
  jobId: string,
  onProgress?: (status: JobStatusResponse) => void,
): Promise<JobStatusResponse> {
  const started = Date.now()
  let consecutiveErrors = 0

  while (Date.now() - started < MAX_WAIT_MS) {
    await sleep(pollDelay(Date.now() - started))

    let status: JobStatusResponse
    try {
      status = await api.get<JobStatusResponse>(`/jobs/${jobId}/status`)
      consecutiveErrors = 0
    } catch (err) {
      // 401 (logged out) and 404 (job gone) are final; anything else may pass.
      if (!isTransientPollError(err)) throw err
      consecutiveErrors++
      if (consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS) {
        throw new Error("Frank lost touch with the studio for a bit — want to try again?")
      }
      continue
    }

    onProgress?.(status)

    if (status.status === "complete") return status
    if (status.status === "failed") {
      throw new Error(status.error ?? "That didn't work out — want to try again?")
    }
  }

  throw new Error("This is taking longer than usual — give it another go in a moment.")
}

/** How long to wait before the next poll, given how long we've been waiting. */
export function pollDelay(elapsedMs: number): number {
  return elapsedMs < FAST_PHASE_MS ? FAST_POLL_MS : SLOW_POLL_MS
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
