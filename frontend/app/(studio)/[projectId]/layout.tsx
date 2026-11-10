"use client"

/**
 * Per-project layout — loads the project into the shared store and renders the
 * persistent StudioNav sidebar alongside all layer pages.
 *
 * Crucially, it re-syncs the shared state every time the user moves between
 * layers (the pathname changes but this layout does NOT remount across sibling
 * routes). That keeps all six rooms looking at one live view of the song, so a
 * vocal recorded in the Voice Room is immediately known to the Beat and Mix
 * Rooms.
 */

import { useEffect, useState, useRef } from "react"
import { useParams, usePathname, useRouter } from "next/navigation"
import { useProjectStore } from "@/store/project"
import { StudioNav } from "@/components/studio/StudioNav"

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
  const didInitialLoad = useRef(false)

  // Initial load — show the opening state only the first time.
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

  // Re-sync the shared state on every layer navigation (pathname change),
  // after the first load. This is what binds the rooms together.
  useEffect(() => {
    if (!projectId || !didInitialLoad.current) return
    // A 404 here is handled by the initial-load path; ignore it on re-syncs.
    refresh(projectId).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground animate-pulse">
          Opening your studio…
        </p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">
          We couldn&apos;t find that song in your studio. Taking you back to your songs…
        </p>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen">
      <StudioNav projectId={projectId} />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  )
}
