"use client"

/**
 * MixVersions: every blend of the song, newest first, each with a plain summary of what it leans towards. Any one
 * can be heard (in step with what is playing, to compare) and put back. Nothing is lost. Plays through the engine.
 */

import { useState } from "react"
import { Check, Pencil } from "lucide-react"
import { PlayButton } from "@/components/audio/PlayButton"
import type { MixVersion } from "@/lib/api/mix"
import type { Track } from "@/store/audio"
import { cn } from "@/lib/utils"

interface MixVersionsProps {
  versions: MixVersion[]
  activeVersionId: string | null
  onSetActive: (versionId: string) => void
  onRename?: (versionId: string, label: string) => Promise<void> | void
}

export function mixTrack(v: MixVersion): Track {
  return { id: `mix:${v.id}`, url: v.render_url ?? "", label: v.label ?? "The blend", material: "voice", onSong: true }
}

export function summarize(v: MixVersion): string {
  const p = v.mix_params || {}
  const bits: string[] = []
  const vocal = p.vocal_gain_db ?? 0
  const beat = p.beat_gain_db ?? -6
  if (vocal - beat > 7) bits.push("voice forward")
  else if (vocal - beat < 4) bits.push("music forward")
  for (const e of p.vocal_effects ?? []) bits.push({ warm: "warmer voice", space: "more space", smooth: "smoother" }[e] ?? e)
  for (const e of p.beat_effects ?? []) if (e === "clean_low") bits.push("cleaner low end")
  for (const [part, st] of Object.entries(p.parts ?? {})) {
    if (st.muted) bits.push(`no ${part}`)
    else if (st.level_db && st.level_db > 0) bits.push(`${part} louder`)
    else if (st.level_db && st.level_db < 0) bits.push(`${part} softer`)
  }
  if (p.harmony_enabled === false) bits.push("no second voice")
  return bits.length ? bits.join(", ") : "Balanced"
}

export function MixVersions({ versions, activeVersionId, onSetActive, onRename }: MixVersionsProps) {
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState("")

  async function saveName(id: string) {
    const label = draft.trim()
    setEditing(null)
    if (label && onRename) await onRename(id, label)
  }

  if (versions.length === 0) return null

  return (
    <section aria-labelledby="blends-heading" className="flex flex-col gap-2">
      <h2 id="blends-heading" className="text-label-md font-semibold uppercase tracking-[0.06em] text-ink-3">
        Every blend so far
      </h2>
      <ol className="flex flex-col">
        {versions.map((v, i) => (
          <li key={v.id} className={cn("flex items-center gap-3 py-2.5", i < versions.length - 1 && "border-b border-line")}>
            {v.render_url ? <PlayButton track={mixTrack(v)} size="row" keepPosition where="in the list of blends" /> : <span className="h-7 w-7" />}
            <div className="min-w-0 flex-1">
              {editing === v.id ? (
                <input
                  value={draft}
                  autoFocus
                  maxLength={80}
                  aria-label="Name this blend"
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={() => saveName(v.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void saveName(v.id)
                    if (e.key === "Escape") setEditing(null)
                  }}
                  className="w-full rounded-sm bg-raised px-2 py-0.5 text-base text-ink"
                />
              ) : (
                <p className="flex items-center gap-1.5 text-base text-ink">
                  <span className="truncate">{v.label}</span>
                  {onRename && (
                    <button
                      onClick={() => {
                        setDraft(v.label ?? "")
                        setEditing(v.id)
                      }}
                      aria-label={`Rename ${v.label ?? "this blend"}`}
                      className="rounded-sm p-0.5 text-ink-3 hover:text-ink"
                    >
                      <Pencil className="h-3 w-3" aria-hidden="true" />
                    </button>
                  )}
                </p>
              )}
              <p className="truncate font-mono text-code text-ink-3">{summarize(v)}</p>
            </div>
            {v.id === activeVersionId ? (
              <span className="flex shrink-0 items-center gap-1 text-sm text-voice">
                <Check className="h-3.5 w-3.5" aria-hidden="true" /> In the song
              </span>
            ) : (
              <button onClick={() => onSetActive(v.id)} className="shrink-0 rounded-md border border-line px-2.5 py-1 text-sm text-ink hover:border-frank/50 hover:text-frank transition-colors">
                Use this
              </button>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
