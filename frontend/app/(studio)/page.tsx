"use client"

/**
 * Project dashboard — lists all songs, lets the user create a new one.
 */

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { createProject, listProjects } from "@/lib/api/projects"
import type { Project } from "@/types/project"
import { Plus, Music2, Clock } from "lucide-react"
import { cn } from "@/lib/utils"

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return "Today"
  if (diffDays === 1) return "Yesterday"
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

const STATUS_LABELS: Record<string, string> = {
  draft: "Just started",
  in_progress: "In progress",
  exported: "Finished",
}

export default function DashboardPage() {
  const router = useRouter()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .finally(() => setLoading(false))
  }, [])

  async function handleNewProject() {
    setCreating(true)
    try {
      const project = await createProject({ title: "Untitled Song" })
      router.push(`/${project.id}/idea`)
    } catch {
      setCreating(false)
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      {/* Header */}
      <div className="mb-10 flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Your Songs</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Pick up where you left off, or start something new.
          </p>
        </div>
        <button
          onClick={handleNewProject}
          disabled={creating}
          className="flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-60"
        >
          <Plus className="h-4 w-4" />
          {creating ? "Opening…" : "New Song"}
        </button>
      </div>

      {/* Project list */}
      {loading ? (
        <div className="flex flex-col gap-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 rounded-xl bg-card animate-pulse border border-border"
            />
          ))}
        </div>
      ) : projects.length === 0 ? (
        /* Empty state */
        <div className="flex flex-col items-center gap-4 rounded-2xl border border-dashed border-border py-20 text-center">
          <div className="rounded-full bg-muted p-4">
            <Music2 className="h-8 w-8 text-muted-foreground" />
          </div>
          <div>
            <p className="font-medium text-foreground">No songs yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              You have a song in your head. Let&apos;s get it out.
            </p>
          </div>
          <button
            onClick={handleNewProject}
            disabled={creating}
            className="mt-2 rounded-full bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            {creating ? "Opening…" : "Start a Song"}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {projects.map((project) => (
            <button
              key={project.id}
              onClick={() => router.push(`/${project.id}/idea`)}
              className={cn(
                "group flex w-full items-center gap-4 rounded-xl border border-border bg-card px-5 py-4",
                "text-left transition-all hover:border-primary/30 hover:bg-secondary",
              )}
            >
              {/* Icon */}
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted group-hover:bg-primary/10">
                <Music2 className="h-5 w-5 text-muted-foreground group-hover:text-primary" />
              </div>

              {/* Info */}
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-foreground">
                  {project.title}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {STATUS_LABELS[project.status] ?? project.status}
                </p>
              </div>

              {/* Last worked on */}
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground/60 shrink-0">
                <Clock className="h-3 w-3" />
                {formatRelativeDate(project.updated_at)}
              </div>
            </button>
          ))}
        </div>
      )}
    </main>
  )
}
