"use client"

/**
 * WakingUp — the free server sleeps after 15 minutes without visitors and takes up to a minute to wake
 * (ship-it spec 13, requirement 2.2; deployment rules). If the health check has not answered within 3 seconds,
 * say so kindly, so a slow first answer never looks like an error.
 *
 * Visual (Stitch spec): a centred warm card with a glowing filament animation — not a toast banner.
 * The card dims the studio lightly so the person knows to wait, without blocking the UI.
 */

import { useEffect, useState } from "react"
import { SERVER_ANSWERED } from "@/lib/api/client"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
const PATIENCE_MS = 3000
const RETRY_MS = 3000
// A check that hangs (the server busy or restarting) is given up on and tried again, so the banner can never
// stay up after the server is back (core-path spec 15, 6.1: on 22 Nov it stayed up through a whole session).
const CHECK_TIMEOUT_MS = 8000

export function WakingUp() {
  const [waking, setWaking] = useState(false)

  useEffect(() => {
    let done = false
    const slow = setTimeout(() => !done && setWaking(true), PATIENCE_MS)
    function answered() {
      done = true
      setWaking(false)
    }
    window.addEventListener(SERVER_ANSWERED, answered)
    async function ping() {
      while (!done) {
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), CHECK_TIMEOUT_MS)
        try {
          const r = await fetch(`${API_URL}/health`, { cache: "no-store", signal: controller.signal })
          if (r.ok) {
            answered()
            return
          }
        } catch {
          // still asleep, or the check hung: try again
        } finally {
          clearTimeout(timer)
        }
        await new Promise((res) => setTimeout(res, RETRY_MS))
      }
    }
    ping()
    return () => {
      done = true
      clearTimeout(slow)
      window.removeEventListener(SERVER_ANSWERED, answered)
    }
  }, [])

  if (!waking) return null

  return (
    // Overlay: dims the studio, centres the warm card
    <div
      role="status"
      className="fixed inset-0 z-50 flex items-center justify-center bg-ground/70 backdrop-blur-sm"
    >
      <div className="relative mx-4 max-w-sm overflow-hidden rounded-xl border border-frank/20 bg-surface px-8 py-7 shadow-l3 text-center">
        {/* Glowing amber filament strip along the top */}
        <div
          aria-hidden="true"
          className="frank-filament pointer-events-none absolute inset-x-0 top-0 h-0.5 rounded-t"
        />

        {/* Warm filament icon — a simple glowing dot */}
        <div className="mb-4 flex justify-center">
          <span
            aria-hidden="true"
            className="filament-glow inline-block h-3 w-3 rounded-full bg-frank"
            style={{ boxShadow: "0 0 12px 4px rgb(var(--frank) / 0.5)" }}
          />
        </div>

        <p className="font-written italic text-xl text-ink leading-7">
          Frank is waking up the studio.
        </p>
        <p className="mt-2 text-sm text-ink-2">
          The first visit after a quiet spell takes up to a minute. Everything you made is safe.
        </p>
      </div>
    </div>
  )
}
