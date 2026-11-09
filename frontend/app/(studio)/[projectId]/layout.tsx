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
import { useParams, usePathname } from "next/navigation"
import { useProjectStore } from "@/store/project"
import { StudioNav } from "@/components/studio/StudioNav"

export default function ProjectLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const params = useParams()
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
        setError(true)
        setLoading(false)
      })
  }, [projectId, refresh])

  // Re-sync the shared state on every layer navigation (pathname change),
  // after the first load. This is what binds the rooms together.
  useEffect(() => {
    if (!projectId || !didInitialLoad.current) return
    refresh(projectId)
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
          Something went wrong loading this project. Try refreshing.
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
