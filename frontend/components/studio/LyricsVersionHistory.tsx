"use client"

/**
 * LyricsVersionHistory: every draft of the words, in the margin of the page, newest first. Nothing is ever lost.
 * The person can look at any draft, bring it back, or give it a name ("before I changed the chorus").
 */

import { useState } from "react"
import type { LyricsVersion } from "@/types/project"
import { updateLyricsLabel } from "@/lib/api/lyrics"
import { lyricHeadings } from "@/lib/songShape"
import { Check, Pencil } from "lucide-react"
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
    <section aria-labelledby="drafts-heading" className="flex flex-col gap-2">
      <h2 id="drafts-heading" className="text-xs font-semibold uppercase tracking-[0.06em] text-ink-3">
        Drafts
      </h2>
      {versions.length === 0 ? (
        <p className="text-sm text-ink-2">Each time you pause, what you wrote is kept here as a draft.</p>
      ) : (
        <ol className="flex flex-col">
          {versions.map((v) => {
            const current = v.id === activeVersionId
            const open = openId === v.id
            return (
              <li key={v.id} className="border-b border-line py-2.5 last:border-b-0">
                <button
                  onClick={() => setOpenId(open ? null : v.id)}
                  aria-expanded={open}
                  className="w-full rounded-sm text-left"
                >
                  <span className="line-clamp-1 font-written text-[17px] leading-[25px] text-words">{firstLine(v.content)}</span>
                  <span className="text-sm text-ink-3">{v.label ? v.label : when(v.created_at)}</span>
                </button>
                <div className="mt-1 flex items-center gap-3">
                  {current ? (
                    <span className="flex items-center gap-1 text-sm text-words">
                      <Check className="h-3.5 w-3.5" aria-hidden="true" /> On the page
                    </span>
                  ) : (
                    <button onClick={() => onRestore(v)} className="text-sm text-ink underline underline-offset-4 hover:text-frank">
                      Bring this back
                    </button>
                  )}
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
                      className="min-w-0 flex-1 rounded-sm bg-raised px-2 py-0.5 text-sm text-ink placeholder:text-ink-3"
                    />
                  ) : (
                    <button
                      onClick={() => {
                        setDraft(v.label ?? "")
                        setEditingId(v.id)
                      }}
                      className="flex items-center gap-1 text-sm text-ink-2 hover:text-ink"
                    >
                      <Pencil className="h-3 w-3" aria-hidden="true" /> Name it
                    </button>
                  )}
                </div>
                {open && (
                  <pre className={cn("mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-sm bg-raised p-3 font-written text-[17px] leading-[25px] text-words")}>
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
