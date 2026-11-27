"use client"

/**
 * Project dashboard — lists all songs, lets the user create a new one.
 */

import Link from "next/link"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { createProject, listProjects } from "@/lib/api/projects"
import { createClient } from "@/lib/supabase/client"
import type { Project } from "@/types/project"
import { Plus } from "lucide-react"

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

const STATUS_COLORS: Record<string, string> = {
  draft: "rgb(var(--frank))",
  in_progress: "rgb(var(--music))",
  exported: "rgb(var(--ok))",
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

  async function handleSignOut() {
    await createClient().auth.signOut()
    router.push("/login")
  }

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
    <div className="songs-design min-h-screen text-ink">
      {/* Top bar — matches Stitch songs/screen.png header */}
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line/70 bg-ground/95 px-6 py-3 backdrop-blur">
        <div className="flex items-center gap-2">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-md"
            style={{ background: "rgb(var(--frank))", boxShadow: "0 0 10px rgba(245,158,11,0.3)" }}
          >
            <span className="font-written italic text-sm leading-none text-ground select-none">f</span>
          </div>
          <span className="text-sm font-semibold text-ink">Frank</span>
          <span className="ml-0.5 font-mono text-[10px] uppercase tracking-widest text-ink-3">Studio</span>
        </div>
        <Link
          href="/taste"
          className="font-mono text-[10px] uppercase tracking-wider text-ink-3 transition-colors hover:text-frank"
        >
          ✦ What Frank knows about your taste
        </Link>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSignOut}
            title="Sign out"
            className="flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold text-ground transition-opacity hover:opacity-80"
            style={{ background: "rgb(var(--frank))" }}
          >
            JD
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-10">
        {/* Page heading */}
        <div className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="stitch-title text-ink">Your Songs</h1>
            <p className="mt-2 text-sm text-ink-2">Pick up where you left off, or start something new.</p>
          </div>
          <button
            onClick={handleNewProject}
            disabled={creating}
            id="new-song-btn"
            className="stitch-primary flex items-center gap-2 px-5 py-3 text-sm disabled:bg-surface-high disabled:text-ink-3 disabled:shadow-none"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            {creating ? "Opening…" : "New Song"}
          </button>
        </div>

        {/* Song list */}
        {loading ? (
          <div className="flex flex-col gap-3" role="status" aria-label="Loading your songs">
            {[1, 2, 3].map((i) => (
              <div key={i} className="stitch-panel h-20 animate-pulse" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          /* Empty state */
          <div className="stitch-panel flex flex-col items-center gap-5 rounded-2xl border-dashed py-20 text-center">
            <div
              className="flex h-16 w-16 items-center justify-center rounded-xl"
              style={{
                background: "rgb(var(--frank) / 0.1)",
                border: "1px solid rgb(var(--frank) / 0.2)",
              }}
            >
              <span
                className="font-written italic text-3xl select-none"
                style={{ color: "rgb(var(--frank) / 0.6)" }}
              >
                f
              </span>
            </div>
            <div>
              <p className="font-written italic text-2xl text-ink">
                &ldquo;You have a song in your head. Let&apos;s get it out.&rdquo;
              </p>
              <p className="mx-auto mt-2 max-w-md text-sm text-ink-2">
                Whether you have a full verse, a single hummed melody, or just a feeling you want to
                capture, Frank will help you craft it into a finished master.
              </p>
            </div>
            <button
              onClick={handleNewProject}
              disabled={creating}
              className="stitch-primary flex items-center gap-2 px-6 py-3 text-sm disabled:bg-surface-high disabled:text-ink-3 disabled:shadow-none"
            >
              <Plus className="h-4 w-4" />
              {creating ? "Opening…" : "Start a Song"}
            </button>
          </div>
        ) : (
          <>
            {/* Column headers */}
            <div className="mb-2 flex items-center justify-between px-1">
              <span className="font-mono text-[10px] uppercase tracking-widest text-ink-3">
                Recent Projects ({projects.length})
              </span>
              <span className="font-mono text-[10px] uppercase tracking-widest text-ink-3">
                Status &amp; Activity
              </span>
            </div>
            {/* Song rows */}
            <div className="flex flex-col gap-3">
              {projects.map((project) => {
                const statusLabel = STATUS_LABELS[project.status] ?? "In progress"
                const statusColor = STATUS_COLORS[project.status] ?? "rgb(var(--music))"
                return (
                  <button
                    key={project.id}
                    onClick={() => router.push(`/${project.id}/idea`)}
                    className="stitch-panel group flex w-full items-center gap-5 rounded-2xl px-6 py-5 text-left transition-all hover:border-frank/40 hover:bg-surface-highest"
                  >
                    <div
                      className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl transition-all"
                      style={{
                        background: "rgb(var(--frank) / 0.12)",
                        border: "1px solid rgb(var(--frank) / 0.25)",
                        boxShadow: "inset 0 0 16px rgba(245,158,11,0.08)",
                      }}
                    >
                      <span className="text-xs" style={{ color: "rgb(var(--frank))" }}>▶</span>
                    </div>
                    {/* Title + date */}
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-written italic text-xl text-on-surface">
                        {project.title}
                      </p>
                      <p className="mt-1 font-mono text-[11px] uppercase tracking-wider text-ink-3">
                        Last worked on {formatRelativeDate(project.updated_at)}
                      </p>
                    </div>
                    {/* Status pill */}
                    <div
                      className="shrink-0 rounded-full px-3 py-1 font-mono text-[10px] uppercase tracking-wide"
                      style={{
                        color: statusColor,
                        background: `color-mix(in srgb, ${statusColor} 10%, transparent)`,
                        border: `1px solid color-mix(in srgb, ${statusColor} 30%, transparent)`,
                      }}
                    >
                      ● {statusLabel}
                    </div>
                    {/* Arrow */}
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line text-lg text-ink-3 transition-all group-hover:border-frank/60 group-hover:text-frank">
                      ›
                    </div>
                  </button>
                )
              })}
            </div>
          </>
        )}

        {/* Taste drawer — persistent memory section */}
        <section className="stitch-panel mt-16 rounded-2xl p-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="flex h-8 w-8 items-center justify-center rounded-md"
                style={{
                  background: "rgb(var(--frank) / 0.1)",
                  border: "1px solid rgb(var(--frank) / 0.3)",
                }}
              >
                <span className="text-sm" style={{ color: "rgb(var(--frank))" }}>✦</span>
              </div>
              <div>
                <h3 className="font-written italic text-base text-ink">What Frank knows about your taste</h3>
                <p className="font-mono text-[10px] text-ink-3">
                  Persistent musical memories compiled across your songwriting sessions
                </p>
              </div>
            </div>
            <span
              className="rounded border px-2 py-1 font-mono text-[10px]"
              style={{
                color: "rgb(var(--frank))",
                borderColor: "rgb(var(--frank) / 0.3)",
                background: "rgb(var(--frank) / 0.08)",
              }}
            >
              4 stylistic preferences learned
            </span>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {[
              { label: "Vocal feel", color: "rgb(var(--words))", text: "Likes close, intimate singing with gentle lower harmonies in the choruses." },
              { label: "Overall feel", color: "rgb(var(--music))", text: "Likes analog warmth, a little vinyl dust, soft piano, and a quiet late-night pulse." },
              { label: "Song speed", color: "rgb(var(--feel))", text: "Comfortable with relaxed walking paces, favoring unhurried movement." },
              { label: "Final sound", color: "rgb(var(--ok))", text: "Balanced so it sounds even in music apps, without harsh peaks." },
            ].map(({ label, color, text }) => (
              <div key={label} className="rounded-md border border-line bg-ground p-4">
                <p className="mb-1 font-mono text-[10px] uppercase tracking-wider" style={{ color }}>{label}</p>
                <p className="text-sm text-ink-2">{text}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}
