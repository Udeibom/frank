"use client"

/**
 * CompView: the best-of version, line by line (sing-it spec 06, requirement 5.3). Each line shows which take it
 * came from by number (not by six unrelated colours); any line can be swapped for the same line from another
 * take. A swap makes a new version. Plays through the shared AudioEngine.
 */

import { useState } from "react"
import { Check } from "lucide-react"
import { PlayButton } from "@/components/audio/PlayButton"
import type { ActiveComp, VocalTake } from "@/lib/api/voice"
import { cn } from "@/lib/utils"

/** The voice's colour at steps of strength, so takes read apart without borrowing other materials' colours. */
const SHADES = ["bg-voice", "bg-voice/65", "bg-voice/40", "bg-voice/25"]

interface CompViewProps {
  comp: ActiveComp
  takes: VocalTake[]
  busy: boolean
  inUse: boolean
  onUse: () => void
  onSwap: (phraseIndex: number, takeId: string) => void
}

export function CompView({ comp, takes, busy, inUse, onUse, onSwap }: CompViewProps) {
  const [open, setOpen] = useState<number | null>(null)
  const used = Array.from(new Set(comp.segments.map((s) => s.take_id)))
  const candidates = Array.from(new Set([...used, ...Object.keys(comp.segments[0]?.scores ?? {})]))
  const name = (id: string) => takes.find((t) => t.id === id)?.label ?? "a take"
  const number = (id: string) => Math.max(0, candidates.indexOf(id)) + 1
  const shade = (id: string) => SHADES[(number(id) - 1) % SHADES.length]
  const total = comp.segments.at(-1)?.end_time ?? 1

  return (
    <section aria-label="Best-of version" className={cn("rounded-md border bg-surface p-4", inUse ? "border-voice/70" : "border-line")}>
      <div className="mb-3 flex items-center gap-3">
        <PlayButton track={{ id: `comp:${comp.id}`, url: comp.audio_url, label: "The best-of version", material: "voice" }} size="card" />
        <div className="min-w-0 flex-1">
          <p className="font-written text-xl text-ink">The best-of version</p>
          <p className="text-sm text-ink-2">Frank's suggestion: the best of each line from your takes.</p>
        </div>
        {inUse ? (
          <span className="flex items-center gap-1 text-sm text-voice">
            <Check className="h-3.5 w-3.5" aria-hidden="true" /> In the song
          </span>
        ) : (
          <button onClick={onUse} className="rounded-md border border-line px-2.5 py-1 text-sm text-ink hover:border-ink-3">
            Use this
          </button>
        )}
      </div>
      <div className="flex h-7 w-full gap-px overflow-hidden rounded-sm" role="list" aria-label="Which take each line comes from">
        {comp.segments.map((s, i) => (
          <button
            key={i}
            role="listitem"
            aria-label={`Line ${i + 1}, from ${name(s.take_id)}. Choose another take for this line.`}
            aria-expanded={open === i}
            onClick={() => setOpen(open === i ? null : i)}
            style={{ width: `${((s.end_time - s.start_time) / total) * 100}%` }}
            className={cn("flex h-full items-center justify-center text-xs font-semibold text-ground", shade(s.take_id), open === i && "outline outline-2 outline-frank")}
          >
            {number(s.take_id)}
          </button>
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-4 text-sm text-ink-2">
        {used.map((id) => (
          <li key={id} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={cn("inline-flex h-4 w-4 items-center justify-center rounded-[2px] text-[12px] font-semibold text-ground", shade(id))}>
              {number(id)}
            </span>
            {name(id)}
          </li>
        ))}
      </ul>
      {open !== null && comp.segments[open] && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-ink-2" role="group" aria-label={`Line ${open + 1} from which take`}>
          <span>Line {open + 1} from:</span>
          {candidates.map((id) => {
            const current = comp.segments[open].take_id === id
            return (
              <button
                key={id}
                disabled={busy || current}
                aria-pressed={current}
                onClick={() => onSwap(comp.segments[open].phrase_index ?? open, id)}
                className={cn("rounded-md border px-2.5 py-1", current ? "border-voice text-ink" : "border-line text-ink hover:border-ink-3", "disabled:cursor-default")}
              >
                {number(id)}. {name(id)}
              </button>
            )
          })}
        </div>
      )}
    </section>
  )
}
