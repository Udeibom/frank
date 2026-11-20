"use client"

/**
 * StartDrawer: "Start with whatever you have". The same front door as before (type, hum, tap, paste words),
 * opened on purpose by the person instead of opening over the room by itself the first time.
 */

import { useEffect, useRef } from "react"
import { StartSurface } from "@/components/studio/StartSurface"

export function StartDrawer({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    closeRef.current?.focus()
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-ground/70"
      role="dialog"
      aria-modal="true"
      aria-label="Start your song from anything"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      onKeyDown={(e) => e.key === "Escape" && onClose()}
    >
      <div className="h-full w-full max-w-md overflow-y-auto border-l border-line bg-surface p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-medium text-ink">Start with whatever you have</h2>
          <button
            ref={closeRef}
            onClick={onClose}
            className="rounded-sm px-2 py-1 text-sm text-ink-2 hover:text-ink"
          >
            Close
          </button>
        </div>
        <StartSurface projectId={projectId} />
      </div>
    </div>
  )
}
