"use client"

/**
 * How the words feel, section by section (frankenstein spec 14, requirement 5.3): read by an emotion model on
 * Frank's ears, shown as a small shape (how much each section lifts) and one plain suggestion.
 */

import { useState } from "react"
import { lyricEmotions } from "@/lib/api/organs"
import type { LyricEmotions } from "@/types/api"

export function WordsFeel({ projectId, getWords, onSay }: { projectId: string; getWords: () => string; onSay: (m: string) => void }) {
  const [working, setWorking] = useState(false)
  const [result, setResult] = useState<LyricEmotions | null>(null)

  async function read() {
    const text = getWords()
    if (!text.trim()) {
      onSay("Write a few lines first and I'll tell you how they feel.")
      return
    }
    setWorking(true)
    try {
      const r = await lyricEmotions(projectId, text)
      setResult(r)
      onSay(r.message)
    } catch {
      onSay("I couldn't read the feelings just now. Try again in a minute.")
    } finally {
      setWorking(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <button onClick={() => void read()} disabled={working} className="self-start rounded-md border border-line bg-raised px-3 py-1.5 text-base text-ink hover:border-ink-3 disabled:text-ink-3">
        {working ? "Reading how it feels…" : "How do my words feel?"}
      </button>
      {result && result.sections.length > 0 && (
        <ol className="flex items-end gap-3" aria-label="How each section feels">
          {result.sections.map((s, i) => (
            <li key={`${s.section}-${i}`} className="flex w-20 flex-col items-center gap-1 text-center">
              <span aria-hidden="true" className="w-6 rounded-sm bg-words/70" style={{ height: `${12 + s.energy * 60}px` }} />
              <span className="text-xs text-ink">{s.section}</span>
              <span className="text-xs text-ink-2">{s.feels.join(", ")}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
