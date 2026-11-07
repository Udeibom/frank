"use client"

/**
 * BeatVersions — a collapsible list of every beat the user has made. Nothing is
 * ever lost; they can play any past version and bring it back as the current one.
 */

import { useState } from "react"
import type { BeatVersion } from "@/lib/api/beat"
import { Play, Pause, Check, Layers } from "lucide-react"
import { cn } from "@/lib/utils"

interface BeatVersionsProps {
  versions: BeatVersion[]
  activeVersionId: string | null
  onSetActive: (versionId: string) => void
}

export function BeatVersions({
  versions,
  activeVersionId,
  onSetActive,
}: BeatVersionsProps) {
  const [playingId, setPlayingId] = useState<string | null>(null)
  const [audio, setAudio] = useState<HTMLAudioElement | null>(null)

  function togglePlay(version: BeatVersion) {
    if (!version.render_url) return
    if (playingId === version.id) {
      audio?.pause()
      setPlayingId(null)
      return
    }
    audio?.pause()
    const next = new Audio(version.render_url)
    next.onended = () => setPlayingId(null)
    next.play().then(() => {
      setAudio(next)
      setPlayingId(version.id)
    }).catch(() => setPlayingId(null))
  }

  if (versions.length === 0) return null

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2 px-1 text-xs font-medium text-muted-foreground">
        <Layers className="h-3.5 w-3.5" />
        Your beats ({versions.length})
      </div>
      {versions.map((version) => (
        <div
          key={version.id}
          className={cn(
            "flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors",
            version.id === activeVersionId
              ? "border-primary/40 bg-primary/5"
              : "border-border bg-card hover:bg-secondary",
          )}
        >
          <button
            onClick={() => togglePlay(version)}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary hover:bg-primary/25"
            aria-label={playingId === version.id ? "Pause" : "Play"}
            disabled={!version.render_url}
          >
            {playingId === version.id ? (
              <Pause className="h-3.5 w-3.5" />
            ) : (
              <Play className="h-3.5 w-3.5 translate-x-px" />
            )}
          </button>

          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-foreground">{version.label}</p>
            <p className="text-[11px] text-muted-foreground/60">
              {version.params.sections?.length ?? 0} sections
            </p>
          </div>

          {version.id === activeVersionId ? (
            <span className="flex items-center gap-1 text-xs text-primary">
              <Check className="h-3.5 w-3.5" />
              Current
            </span>
          ) : (
            <button
              onClick={() => onSetActive(version.id)}
              className="text-xs text-muted-foreground hover:text-primary"
            >
              Use this
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
