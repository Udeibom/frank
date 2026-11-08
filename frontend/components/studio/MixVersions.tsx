"use client"

/**
 * MixVersions — every mix the user has made, with a plain-language summary of
 * what each emphasizes. They can play any past mix and bring it back. Nothing
 * is ever lost.
 */

import { useState } from "react"
import type { MixVersion } from "@/lib/api/mix"
import { Play, Pause, Check, Layers } from "lucide-react"
import { cn } from "@/lib/utils"

interface MixVersionsProps {
  versions: MixVersion[]
  activeVersionId: string | null
  onSetActive: (versionId: string) => void
}

function summarize(v: MixVersion): string {
  const p = v.mix_params || {}
  const bits: string[] = []
  const vocal = p.vocal_gain_db ?? 0
  const beat = p.beat_gain_db ?? -6
  if (vocal - beat > 7) bits.push("voice forward")
  else if (vocal - beat < 4) bits.push("beat forward")
  for (const e of p.vocal_effects ?? []) {
    bits.push({ warm: "warmer", space: "more space", smooth: "smoother" }[e] ?? e)
  }
  for (const e of p.beat_effects ?? []) {
    if (e === "clean_low") bits.push("cleaner low end")
  }
  if (p.harmony_enabled === false) bits.push("no harmony")
  return bits.length ? bits.join(", ") : "balanced"
}

export function MixVersions({
  versions,
  activeVersionId,
  onSetActive,
}: MixVersionsProps) {
  const [playingId, setPlayingId] = useState<string | null>(null)
  const [audio, setAudio] = useState<HTMLAudioElement | null>(null)

  function togglePlay(v: MixVersion) {
    if (!v.render_url) return
    if (playingId === v.id) {
      audio?.pause()
      setPlayingId(null)
      return
    }
    audio?.pause()
    const next = new Audio(v.render_url)
    next.onended = () => setPlayingId(null)
    next.play().then(() => {
      setAudio(next)
      setPlayingId(v.id)
    }).catch(() => setPlayingId(null))
  }

  if (versions.length === 0) return null

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2 px-1 text-xs font-medium text-muted-foreground">
        <Layers className="h-3.5 w-3.5" />
        Your mixes ({versions.length})
      </div>
      {versions.map((v) => (
        <div
          key={v.id}
          className={cn(
            "flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors",
            v.id === activeVersionId
              ? "border-primary/40 bg-primary/5"
              : "border-border bg-card hover:bg-secondary",
          )}
        >
          <button
            onClick={() => togglePlay(v)}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary hover:bg-primary/25"
            aria-label={playingId === v.id ? "Pause" : "Play"}
            disabled={!v.render_url}
          >
            {playingId === v.id ? (
              <Pause className="h-3.5 w-3.5" />
            ) : (
              <Play className="h-3.5 w-3.5 translate-x-px" />
            )}
          </button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-foreground">{v.label}</p>
            <p className="truncate text-[11px] text-muted-foreground/60">
              {summarize(v)}
            </p>
          </div>
          {v.id === activeVersionId ? (
            <span className="flex items-center gap-1 text-xs text-primary">
              <Check className="h-3.5 w-3.5" /> current
            </span>
          ) : (
            <button
              onClick={() => onSetActive(v.id)}
              className="text-xs text-muted-foreground hover:text-primary"
            >
              use this
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
