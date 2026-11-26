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
    <div className="min-h-screen bg-ground text-ink">
      {/* Top bar — matches Stitch songs/screen.png header */}
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line/60 bg-ground/95 px-6 py-3 backdrop-blur">
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
            <h1 className="text-3xl font-bold text-ink">Your Songs</h1>
            <p className="mt-1 text-sm text-ink-2">Pick up where you left off, or start something new.</p>
          </div>
          <button
            onClick={handleNewProject}
            disabled={creating}
            id="new-song-btn"
            className="flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-semibold transition-all disabled:opacity-60 hover:text-ground"
            style={{ borderColor: "rgb(var(--frank))", color: "rgb(var(--frank))" }}
            onMouseEnter={(e) => {
              const b = e.currentTarget
              b.style.background = "rgb(var(--frank))"
              b.style.color = "rgb(var(--ground))"
            }}
            onMouseLeave={(e) => {
              const b = e.currentTarget
              b.style.background = ""
              b.style.color = "rgb(var(--frank))"
            }}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            {creating ? "Opening…" : "New Song"}
          </button>
        </div>

        {/* Song list */}
        {loading ? (
          <div className="flex flex-col gap-2" role="status" aria-label="Loading your songs">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 rounded-md border border-line bg-surface animate-pulse" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          /* Empty state */
          <div className="flex flex-col items-center gap-5 rounded-md border border-dashed border-line py-20 text-center">
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
              className="flex items-center gap-2 rounded-md px-6 py-3 text-sm font-semibold text-ground transition-all disabled:opacity-60"
              style={{ background: "rgb(var(--frank))", boxShadow: "0 0 20px rgba(245,158,11,0.3)" }}
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
            <div className="flex flex-col gap-0.5">
              {projects.map((project) => {
                const statusLabel = STATUS_LABELS[project.status] ?? "In progress"
                const statusColor = STATUS_COLORS[project.status] ?? "rgb(var(--music))"
                return (
                  <button
                    key={project.id}
                    onClick={() => router.push(`/${project.id}/idea`)}
                    className="group flex w-full items-center gap-4 rounded-md border border-line/60 bg-surface px-5 py-4 text-left transition-all hover:border-line hover:bg-raised"
                  >
                    {/* Amber play icon */}
                    <div
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md transition-all"
                      style={{
                        background: "rgb(var(--frank) / 0.12)",
                        border: "1px solid rgb(var(--frank) / 0.2)",
                      }}
                    >
                      <span className="text-xs" style={{ color: "rgb(var(--frank))" }}>▶</span>
                    </div>
                    {/* Title + date */}
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-written italic text-base font-medium text-ink">
                        {project.title}
                      </p>
                      <p className="mt-0.5 font-mono text-[10px] text-ink-3">
                        {formatRelativeDate(project.updated_at)}
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
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-line text-sm text-ink-3 transition-all group-hover:border-frank/40 group-hover:text-frank">
                      ›
                    </div>
                  </button>
                )
              })}
            </div>
          </>
        )}

        {/* Taste drawer — persistent memory section */}
        <section className="mt-16 rounded-md border border-line bg-surface p-6">
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
              { label: "Vocal Arrangement", color: "rgb(var(--words))", text: "Prefers intimate, near-mic vocal delivery with gentle lower-octave harmonies in choruses." },
              { label: "Sonic Atmosphere", color: "rgb(var(--music))", text: "Gravitates toward analog warmth, subtle vinyl dust, upright felt piano, and sparse midnight pulse rhythms." },
              { label: "Tempo & Groove", color: "rgb(var(--feel))", text: "Comfortable with relaxed walking paces between 76 and 84 BPM, favoring unhurried cadences." },
              { label: "Mastering Target", color: "rgb(var(--ok))", text: "Balanced streaming loudness with healthy -1.4dB true peak ceiling to avoid digital clipping." },
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
