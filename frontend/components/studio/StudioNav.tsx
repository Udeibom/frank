"use client"

/**
 * StudioNav — persistent sidebar present on every layer page.
 * Shows project title (editable), all six layers with status indicators,
 * and a back link to the project dashboard.
 */

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useState, useRef, useEffect } from "react"
import { cn } from "@/lib/utils"
import { useProjectStore } from "@/store/project"
import { updateProject } from "@/lib/api/projects"
import { createClient } from "@/lib/supabase/client"
import {
  LogOut,
  PenLine,
  Waves,
  Sparkles,
  Drum,
  Mic2,
  SlidersHorizontal,
  Download,
  ChevronLeft,
  Circle,
  CircleDot,
  CheckCircle2,
} from "lucide-react"

const LAYERS = [
  {
    id: "idea",
    label: "Idea",
    description: "Words & lyrics",
    icon: PenLine,
    activeStateKey: "active_lyrics_id",
  },
  {
    id: "feel",
    label: "Feel",
    description: "The mood",
    icon: Sparkles,
    activeStateKey: "active_fingerprint_id",
  },
  {
    id: "beat",
    label: "Beat",
    description: "The instrumental",
    icon: Drum,
    activeStateKey: "active_beat_version_id",
  },
  {
    id: "voice",
    label: "Voice",
    description: "Your recording",
    icon: Mic2,
    activeStateKey: "active_vocal_id",
  },
  {
    id: "mix",
    label: "Mix",
    description: "Put it together",
    icon: SlidersHorizontal,
    activeStateKey: "active_mix_id",
  },
  {
    id: "export",
    label: "Export",
    description: "Take it with you",
    icon: Download,
    activeStateKey: null,
  },
] as const

type LayerStatus = "empty" | "in_progress" | "has_content"

function LayerStatusIcon({ status }: { status: LayerStatus }) {
  // Icon shape differs per state; the label gives screen readers the same
  // information (design-and-ui.md: colour is never the only signal).
  if (status === "has_content")
    return <CheckCircle2 role="img" aria-label="has something" className="h-3.5 w-3.5 text-primary" />
  if (status === "in_progress")
    return <CircleDot role="img" aria-label="in progress" className="h-3.5 w-3.5 text-primary/60" />
  return <Circle role="img" aria-label="not started" className="h-3.5 w-3.5 text-muted-foreground/30" />
}

export function StudioNav({ projectId }: { projectId: string }) {
  const pathname = usePathname()
  const router = useRouter()
  const { currentProject, activeState, updateProjectTitle } = useProjectStore()

  const [editingTitle, setEditingTitle] = useState(false)
  const [titleValue, setTitleValue] = useState(
    currentProject?.title ?? "Untitled Song",
  )
  const titleInputRef = useRef<HTMLInputElement>(null)

  // Keep local title in sync with store
  useEffect(() => {
    if (currentProject?.title) setTitleValue(currentProject.title)
  }, [currentProject?.title])

  useEffect(() => {
    if (editingTitle) titleInputRef.current?.select()
  }, [editingTitle])

  async function handleTitleSave() {
    setEditingTitle(false)
    const trimmed = titleValue.trim() || "Untitled Song"
    setTitleValue(trimmed)
    if (trimmed === currentProject?.title) return
    updateProjectTitle(trimmed)
    try {
      await updateProject(projectId, { title: trimmed })
    } catch {
      // Revert on failure
      updateProjectTitle(currentProject?.title ?? "Untitled Song")
      setTitleValue(currentProject?.title ?? "Untitled Song")
    }
  }

  async function handleLogout() {
    await createClient().auth.signOut()
    router.push("/login")
    router.refresh()
  }

  function getLayerStatus(activeStateKey: string | null): LayerStatus {
    if (!activeStateKey || !activeState) return "empty"
    const value = activeState[activeStateKey as keyof typeof activeState]
    if (value) return "has_content"
    return "empty"
  }

  function isActiveLayer(layerId: string) {
    return pathname.includes(`/${layerId}`)
  }

  return (
    <nav className="flex h-full w-56 flex-col border-r border-border bg-card px-3 py-4">
      {/* Back to all songs */}
      <Link
        href="/songs"
        className="mb-6 flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronLeft className="h-3.5 w-3.5" />
        All Songs
      </Link>

      {/* Project title — inline editable */}
      <div className="mb-6 px-1">
        {editingTitle ? (
          <input
            ref={titleInputRef}
            value={titleValue}
            onChange={(e) => setTitleValue(e.target.value)}
            onBlur={handleTitleSave}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleTitleSave()
              if (e.key === "Escape") {
                setTitleValue(currentProject?.title ?? "Untitled Song")
                setEditingTitle(false)
              }
            }}
            className="w-full rounded bg-transparent text-sm font-semibold text-foreground outline-none ring-1 ring-primary/50 px-1 py-0.5"
            aria-label="Edit song title"
          />
        ) : (
          <button
            onClick={() => setEditingTitle(true)}
            className="w-full text-left text-sm font-semibold text-foreground hover:text-primary transition-colors truncate"
            title="Click to rename"
          >
            {titleValue}
          </button>
        )}
        <p className="mt-0.5 text-xs text-muted-foreground px-1">
          {currentProject?.status ?? "draft"}
        </p>
      </div>

      {/* Layer navigation */}
      <div className="flex flex-col gap-0.5">
        {LAYERS.map(({ id, label, description, icon: Icon, activeStateKey }) => {
          const active = isActiveLayer(id)
          const status = getLayerStatus(activeStateKey)

          return (
            <Link
              key={id}
              href={`/${projectId}/${id}`}
              className={cn(
                "group flex items-center gap-3 rounded-md px-3 py-2.5 transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground",
              )}
              aria-current={active ? "page" : undefined}
            >
              <Icon className={cn("h-4 w-4 shrink-0", active && "text-primary")} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium leading-none">{label}</p>
                <p className="mt-0.5 text-xs text-muted-foreground/60 truncate">
                  {description}
                </p>
              </div>
              <LayerStatusIcon status={status} />
            </Link>
          )
        })}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Log out — small and out of the way */}
      <button
        onClick={handleLogout}
        className="mb-3 flex items-center gap-1.5 px-1 text-xs text-muted-foreground/60 transition-colors hover:text-foreground"
      >
        <LogOut className="h-3.5 w-3.5" />
        Log out
      </button>

      {/* Frank wordmark at bottom */}
      <p className="px-1 text-xs text-muted-foreground/30 font-semibold tracking-widest uppercase">
        Frank
      </p>
    </nav>
  )
}
