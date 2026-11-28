"use client"

/**
 * How the words feel, section by section (frankenstein spec 14, requirement 5.3): read by an emotion model on
 * Frank's ears, shown as a small shape (how much each section lifts) and one plain suggestion.
 */

import { useState } from "react"
import { Sparkles } from "lucide-react"
import { lyricEmotions } from "@/lib/api/organs"
import type { LyricEmotions } from "@/types/api"

const CHIPS = [
  "border border-frank/30 bg-surface-high text-frank-text",
  "border border-feel/30 bg-surface-high text-feel",
  "border border-tertiary/30 bg-surface-high text-tertiary",
]

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

  const feelings = Array.from(new Set(result?.sections.flatMap((s) => s.feels) ?? [])).slice(0, 3)

  return (
    <section className="flex flex-col gap-4 rounded-xl bg-surface-low p-6 shadow-[0_4px_16px_rgba(0,0,0,0.3)]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-frank-text" aria-hidden="true" />
          <h2 className="text-label-md font-semibold uppercase tracking-[0.06em] text-on-surface">What my words feel like</h2>
        </div>
        <span className="text-code text-tertiary">Real-time Reading</span>
      </div>
      {result ? (
        <p className="font-written text-base italic leading-relaxed text-on-surface">“{result.message}”</p>
      ) : (
        <p className="text-sm italic text-on-surface-variant">No words read yet. Write a few lines and Frank will tell you how they feel.</p>
      )}
      {feelings.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {feelings.map((feeling, i) => (
            <span key={feeling} className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-sm ${CHIPS[i % CHIPS.length]}`}>
              <span className="h-1.5 w-1.5 rounded-full bg-current" />
              {feeling}
            </span>
          ))}
        </div>
      )}
      {result && result.sections.length > 0 && (
        <ol className="flex items-end gap-3" aria-label="How each section feels">
          {result.sections.map((s, i) => (
            <li key={`${s.section}-${i}`} className="flex w-20 flex-col items-center gap-1 text-center">
              <span aria-hidden="true" className="w-6 rounded-sm bg-words/70" style={{ height: `${12 + s.energy * 60}px` }} />
              <span className="text-xs text-on-surface">{s.section}</span>
              <span className="text-xs text-on-surface-variant">{s.feels.join(", ")}</span>
            </li>
          ))}
        </ol>
      )}
      <button
        onClick={() => void read()}
        disabled={working}
        className="flex min-h-11 items-center self-start rounded-lg bg-surface-high px-3 py-1.5 text-label-md text-on-surface hover:bg-surface-highest disabled:text-on-surface-variant"
      >
        {working ? "Reading how it feels…" : "How do my words feel?"}
      </button>
    </section>
  )
}
