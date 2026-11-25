"use client"

/**
 * BeatVersions: every version of the music, newest first, each with what changed to make it (so the person
 * can see how the song got here, the way Endlesss keeps each riff as a step from the last). Nothing is ever
 * lost: any version can be heard and put back in the song. Plays through the shared AudioEngine.
 */

import { useState } from "react"
import { Check, Pencil } from "lucide-react"
import { cn } from "@/lib/utils"
import { PlayButton } from "@/components/audio/PlayButton"
import type { BeatVersion } from "@/lib/api/beat"
import type { Track } from "@/store/audio"

interface BeatVersionsProps {
  versions: BeatVersion[]
  activeVersionId: string | null
  onSetActive: (versionId: string) => void
  /** Give a version the person's own name, e.g. "before I changed the chorus". */
  onRename?: (versionId: string, label: string) => Promise<void> | void
}

export function beatTrack(v: BeatVersion): Track {
  return { id: `beat:${v.id}`, url: v.render_url ?? "", label: v.label ?? "The music", material: "music", onSong: true }
}

/** What made this version, in the words the backend already wrote. */
function whatChanged(v: BeatVersion, isFirst: boolean): string {
  const changes = v.params.changes ?? []
  if (changes.length) return changes.join(" ")
  return isFirst ? "Built from the feeling" : "A new version"
}

export function BeatVersions({ versions, activeVersionId, onSetActive, onRename }: BeatVersionsProps) {
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState("")

  async function saveName(id: string) {
    const label = draft.trim()
    setEditing(null)
    if (label && onRename) await onRename(id, label)
  }

  if (versions.length === 0) return null
  const oldest = versions[versions.length - 1]?.id

  return (
    <section aria-labelledby="versions-heading" className="flex flex-col gap-2">
      <h2 id="versions-heading" className="text-label-md font-semibold uppercase tracking-[0.06em] text-ink-3">
        How the music got here
      </h2>
      <ol className="flex flex-col">
        {versions.map((v, i) => {
          const inUse = v.id === activeVersionId
          return (
            <li
              key={v.id}
              className={cn(
                "relative flex gap-3 py-2.5 pl-1",
                i < versions.length - 1 && "border-b border-line",
              )}
            >
              {v.render_url ? <PlayButton track={beatTrack(v)} size="row" className="mt-0.5" where="in the version history" /> : <span className="h-7 w-7" />}
              <div className="min-w-0 flex-1">
                {editing === v.id ? (
                  <input
                    value={draft}
                    autoFocus
                    maxLength={80}
                    aria-label="Name this version"
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
                        aria-label={`Rename ${v.label ?? "this version"}`}
                        className="rounded-sm p-0.5 text-ink-3 hover:text-ink"
                      >
                        <Pencil className="h-3 w-3" aria-hidden="true" />
                      </button>
                    )}
                  </p>
                )}
                <p className="line-clamp-2 text-sm text-ink-3 font-mono text-code">{whatChanged(v, v.id === oldest)}</p>
              </div>
              {inUse ? (
                <span className="flex shrink-0 items-center gap-1 self-start pt-1 text-sm text-music">
                  <Check className="h-3.5 w-3.5" aria-hidden="true" /> In the song
                </span>
              ) : (
                <button
                  onClick={() => onSetActive(v.id)}
                  className="shrink-0 self-start rounded-md border border-line px-2.5 py-1 text-sm text-ink hover:border-frank/50 hover:text-frank transition-colors"
                >
                  Use this
                </button>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
