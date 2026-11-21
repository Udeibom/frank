/**
 * Live job updates (frankenstein spec 14, requirement 7.2): Supabase Realtime tells the page the moment a job's
 * row changes, so progress and results show without waiting for the next poll. The page then asks Frank's API for
 * the job (that is where audio addresses are signed). If Realtime is unavailable, polling carries on as before.
 */
import { createClient } from "@/lib/supabase/client"

export interface JobWatch {
  /** Resolves the next time the job changes (or never, if Realtime is off). */
  next(): Promise<void>
  close(): void
  /** True once the live connection is up; polling can then slow down. */
  live(): boolean
}

export function watchJob(jobId: string): JobWatch {
  let waiting: (() => void) | null = null
  let changed = false
  let isLive = false
  const supabase = createClient()
  let channel: ReturnType<typeof supabase.channel> | null = null
  try {
    channel = supabase
      .channel(`job-${jobId}`)
      .on("postgres_changes", { event: "UPDATE", schema: "public", table: "async_jobs", filter: `id=eq.${jobId}` }, () => {
        changed = true
        waiting?.()
      })
      .subscribe((status) => {
        isLive = status === "SUBSCRIBED"
      })
  } catch {
    channel = null
  }
  return {
    next() {
      if (changed) {
        changed = false
        return Promise.resolve()
      }
      return new Promise<void>((resolve) => {
        waiting = () => {
          waiting = null
          changed = false
          resolve()
        }
      })
    },
    close() {
      if (channel) void supabase.removeChannel(channel)
    },
    live: () => isLive,
  }
}
