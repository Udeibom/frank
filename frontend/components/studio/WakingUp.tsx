"use client"

/**
 * WakingUp — the free server sleeps after 15 minutes without visitors and takes up to a minute to wake
 * (ship-it spec 13, requirement 2.2; deployment rules). If the health check has not answered within 3 seconds,
 * say so kindly, so a slow first answer never looks like an error.
 */

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
const PATIENCE_MS = 3000
const RETRY_MS = 3000

export function WakingUp() {
  const [waking, setWaking] = useState(false)

  useEffect(() => {
    let done = false
    const slow = setTimeout(() => !done && setWaking(true), PATIENCE_MS)
    async function ping() {
      while (!done) {
        try {
          const r = await fetch(`${API_URL}/health`, { cache: "no-store" })
          if (r.ok) {
            done = true
            setWaking(false)
            return
          }
        } catch {
          // still asleep: try again
        }
        await new Promise((res) => setTimeout(res, RETRY_MS))
      }
    }
    ping()
    return () => {
      done = true
      clearTimeout(slow)
    }
  }, [])

  if (!waking) return null
  return (
    <div role="status" className="fixed inset-x-0 top-0 z-50 flex justify-center p-3">
      <p className="flex items-center gap-2 rounded-full border border-primary/30 bg-card px-4 py-2 text-sm text-foreground shadow-lg">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        Frank is waking up. The first visit after a quiet spell takes up to a minute; everything you made is safe.
      </p>
    </div>
  )
}
