"use client"

/**
 * LyricsVersionHistory: every draft of the words, in the margin of the page, newest first. Nothing is ever lost.
 * The person can look at any draft, bring it back, or give it a name ("before I changed the chorus").
 */

import { useState } from "react"
import type { LyricsVersion } from "@/types/project"
import { updateLyricsLabel } from "@/lib/api/lyrics"
import { lyricHeadings } from "@/lib/songShape"
import { Check, History, Pencil } from "lucide-react"
import { cn } from "@/lib/utils"

interface LyricsVersionHistoryProps {
  versions: LyricsVersion[]
  activeVersionId: string | null
  onRestore: (version: LyricsVersion) => void
  onLabelUpdated: (versionId: string, label: string) => void
}

/** The first line of words, skipping section headings ("Verse"), so each draft is recognisable. */
function firstLine(content: string): string {
  const line = content.split("\n").find((l) => l.trim() && lyricHeadings(l).length === 0)
  return line?.trim() || "An empty page"
}

function when(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
}

export function LyricsVersionHistory({ versions, activeVersionId, onRestore, onLabelUpdated }: LyricsVersionHistoryProps) {
  const [openId, setOpenId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState("")

  async function saveLabel(version: LyricsVersion) {
    setEditingId(null)
    const label = draft.trim()
    if (!label || label === version.label) return
    onLabelUpdated(version.id, label)
    try {
      await updateLyricsLabel(version.project_id, version.id, label)
    } catch {
      onLabelUpdated(version.id, version.label ?? "")
    }
  }

  return (
    <section aria-labelledby="drafts-heading" className="flex flex-col gap-3 rounded-xl bg-surface-low p-4 shadow-[0_4px_16px_rgba(0,0,0,0.25)]">
      <div className="flex items-center justify-between pb-1">
        <h2 id="drafts-heading" className="text-label-sm font-semibold uppercase tracking-[0.06em] text-on-surface-variant">
          Earlier Drafts
        </h2>
        <History className="h-4 w-4 text-on-surface-variant" aria-hidden="true" />
      </div>
      {versions.length === 0 ? (
        <p className="text-sm text-on-surface-variant">Each time you pause, what you wrote is kept here as a draft.</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {versions.map((v, index) => {
            const current = v.id === activeVersionId
            const open = openId === v.id
            return (
              <li
                key={v.id}
                className={`rounded-lg p-2 ${current ? "bg-surface-high" : "bg-surface-container hover:bg-surface-high"}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`text-label-md font-bold ${current ? "text-frank-text" : "text-on-surface"}`}>Draft {versions.length - index}</span>
                    {current && <span className="text-code text-frank-text">Active</span>}
                  </div>
                  {current ? (
                    <Check className="h-3.5 w-3.5 text-frank-text" aria-label="On the page" />
                  ) : (
                    <button onClick={() => onRestore(v)} className="text-code text-frank-text hover:underline">
                      Restore
                    </button>
                  )}
                </div>
                <button onClick={() => setOpenId(open ? null : v.id)} aria-expanded={open} className="mt-1 w-full rounded-sm text-left">
                  <span className="block text-sm text-on-surface-variant">{v.label ? `${when(v.created_at)} · ${v.label}` : when(v.created_at)}</span>
                  <span className="line-clamp-1 font-written italic text-sm text-on-surface-variant/80">{firstLine(v.content)}</span>
                </button>
                <div className="mt-1 flex items-center gap-3">
                  {editingId === v.id ? (
                    <input
                      autoFocus
                      value={draft}
                      maxLength={80}
                      onChange={(e) => setDraft(e.target.value)}
                      onBlur={() => saveLabel(v)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void saveLabel(v)
                        if (e.key === "Escape") setEditingId(null)
                      }}
                      aria-label="Name this draft"
                      placeholder="Name this draft"
                      className="min-w-0 flex-1 rounded-md border border-line bg-surface-container px-2 py-0.5 text-sm text-on-surface placeholder:text-on-surface-variant focus-visible:border-frank/60"
                    />
                  ) : (
                    <button
                      onClick={() => {
                        setDraft(v.label ?? "")
                        setEditingId(v.id)
                      }}
                      aria-label="Name this draft"
                      className="flex items-center gap-1 text-xs text-on-surface-variant hover:text-on-surface"
                    >
                      <Pencil className="h-3 w-3" aria-hidden="true" /> Name it
                    </button>
                  )}
                </div>
                {open && (
                  <pre className={cn("mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-sm bg-surface-lowest p-3 font-written text-[17px] leading-[25px] text-words")}>
                    {v.content}
                  </pre>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
