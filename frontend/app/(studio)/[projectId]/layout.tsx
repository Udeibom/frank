"use client"

/**
 * Per-project layout — loads the project into the store and renders
 * the persistent StudioNav sidebar alongside all layer pages.
 */

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { getProject } from "@/lib/api/projects"
import { useProjectStore } from "@/store/project"
import { StudioNav } from "@/components/studio/StudioNav"

export default function ProjectLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const params = useParams()
  const projectId = params.projectId as string
  const { setCurrentProject, setActiveState } = useProjectStore()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!projectId) return
    getProject(projectId)
      .then(({ project, active_state }) => {
        setCurrentProject(project)
        if (active_state) setActiveState(active_state)
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [projectId, setCurrentProject, setActiveState])

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
