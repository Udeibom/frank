"use client"

/**
 * Project dashboard — lists all songs, lets the user create a new one.
 */

import Link from "next/link"
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
    fetch("/api/wake").catch(() => {})
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
          <h1 className="font-written italic text-4xl text-ink leading-tight">Your Songs</h1>
          <p className="mt-1.5 text-sm text-ink-2">
            Pick up where you left off, or start something new.
          </p>
          <Link href="/taste" className="mt-2 inline-block text-xs text-ink-3 underline underline-offset-4 hover:text-ink transition-colors">
            What Frank knows about your taste
          </Link>
        </div>
        <button
          onClick={handleNewProject}
          disabled={creating}
          id="new-song-btn"
          className="cta-glow flex items-center gap-2 rounded-full bg-frank px-5 py-2.5 text-sm font-semibold text-ground transition-all hover:bg-frank-shade disabled:opacity-60 disabled:animate-none"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          {creating ? "Opening…" : "New Song"}
        </button>
      </div>

      {/* Project list */}
      {loading ? (
        <div className="flex flex-col gap-3" role="status" aria-label="Loading your songs">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 rounded-xl border border-line bg-surface animate-pulse"
            />
          ))}
        </div>
      ) : projects.length === 0 ? (
        /* Empty state */
        <div className="flex flex-col items-center gap-5 rounded-2xl border border-dashed border-line py-20 text-center">
          <div className="rounded-full bg-raised border border-line p-5">
            <Music2 className="h-8 w-8 text-ink-3" aria-hidden="true" />
          </div>
          <div>
            <p className="font-medium text-ink">No songs yet</p>
            <p className="mt-1 text-sm text-ink-2">
              You have a song in your head. Let&apos;s get it out.
            </p>
          </div>
          <button
            onClick={handleNewProject}
            disabled={creating}
            className="mt-2 rounded-full bg-frank px-6 py-2.5 text-sm font-semibold text-ground hover:bg-frank-shade disabled:opacity-60 transition-colors"
          >
            {creating ? "Opening…" : "Start a Song"}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {projects.map((project) => (
            <button
              key={project.id}
              onClick={() => router.push(`/${project.id}/idea`)}
              className={cn(
                "group flex w-full items-center gap-4 rounded-xl border border-line/70 bg-surface px-5 py-4",
                "text-left transition-all duration-150 hover:border-frank/25 hover:bg-raised hover:shadow-l2",
              )}
            >
              {/* Icon */}
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-raised border border-line group-hover:border-frank/30 group-hover:bg-frank/10 transition-colors">
                <Music2 className="h-5 w-5 text-ink-3 group-hover:text-frank transition-colors" aria-hidden="true" />
              </div>

              {/* Info */}
              <div className="min-w-0 flex-1">
                <p className="truncate font-written italic text-[17px] leading-[25px] text-ink">
                  {project.title}
                </p>
                <p className="mt-0.5 font-mono text-code text-ink-3">
                  {STATUS_LABELS[project.status] ?? project.status}
                </p>
              </div>

              {/* Last worked on */}
              <div className="flex items-center gap-1.5 font-mono text-code text-ink-3 shrink-0">
                <Clock className="h-3 w-3" aria-hidden="true" />
                {formatRelativeDate(project.updated_at)}
              </div>
            </button>
          ))}
        </div>
      )}
    </main>
  )
}
