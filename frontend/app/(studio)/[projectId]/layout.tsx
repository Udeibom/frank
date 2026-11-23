"use client"

/**
 * Per-project layout: the studio shell (design-and-ui.md).
 *
 * The Song Strip and the Rail never unmount: not while the project loads, not while the user moves between
 * rooms. Each room fills the stage and lays it out however its work needs.
 *
 * It also re-syncs the shared state every time the user moves between rooms (the pathname changes but this
 * layout does NOT remount across sibling routes). That keeps all six rooms looking at one live view of the
 * song, so a vocal recorded in the Voice room is immediately known to the Music and Blend rooms.
 */

import { useEffect, useState, useRef } from "react"
import { useParams, usePathname, useRouter } from "next/navigation"
import { useProjectStore } from "@/store/project"
import { SongStrip } from "@/components/shell/SongStrip"
import { Rail } from "@/components/shell/Rail"
import { StartDrawer } from "@/components/shell/StartDrawer"
import { NextStepBar } from "@/components/shell/NextStepBar"
import type { Room } from "@/lib/nextStep"

const ROOMS: Room[] = ["idea", "feel", "beat", "voice", "mix", "export", "yours"]

export default function ProjectLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const params = useParams()
  const router = useRouter()
  const pathname = usePathname()
  const projectId = params.projectId as string
  const { refresh } = useProjectStore()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [showStart, setShowStart] = useState(false)
  const didInitialLoad = useRef(false)

  // Initial load: the shell is already on screen; only the stage waits.
  useEffect(() => {
    if (!projectId || didInitialLoad.current) return
    didInitialLoad.current = true
    refresh(projectId)
      .then(() => setLoading(false))
      .catch(() => {
        // Not found, or not this user's song: don't show a broken studio.
        setError(true)
        setLoading(false)
        setTimeout(() => router.replace("/songs"), 1800)
      })
  }, [projectId, refresh, router])

  // Re-sync the shared state on every room change, after the first load.
  useEffect(() => {
    if (!projectId || !didInitialLoad.current) return
    // A 404 here is handled by the initial-load path; ignore it on re-syncs.
    refresh(projectId).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname])

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-ground">
      <a
        href="#stage"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-frank focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-ground"
      >
        Skip to the room
      </a>
      <SongStrip projectId={projectId} onStart={() => setShowStart(true)} />
      {!loading && !error && (
        <NextStepBar projectId={projectId} room={ROOMS.find((r) => pathname?.endsWith(`/${r}`)) ?? "feel"} />
      )}
      <div className="flex min-h-0 flex-1">
        <Rail projectId={projectId} onStart={() => setShowStart(true)} />
        <main id="stage" tabIndex={-1} className="min-h-0 min-w-0 flex-1 overflow-auto outline-none">
          {loading ? (
            <div className="flex h-full items-center justify-center" role="status">
              <p className="text-sm text-ink-2">Opening your studio…</p>
            </div>
          ) : error ? (
            <div className="flex h-full items-center justify-center px-8 text-center" role="status">
              <p className="text-sm text-ink-2">
                We couldn&apos;t find that song in your studio. Taking you back to your songs…
              </p>
            </div>
          ) : (
            children
          )}
        </main>
      </div>
      {showStart && <StartDrawer projectId={projectId} onClose={() => setShowStart(false)} />}
    </div>
  )
}
