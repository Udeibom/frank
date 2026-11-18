"use client"

/**
 * CompView — the best-of version, line by line (sing-it spec 06, requirement 5.3). Each line shows which take it
 * came from; any line can be swapped for the same line from another take. A swap makes a new version.
 */

import { useState } from "react"
import { Button } from "@/components/ui/button"
import type { ActiveComp, VocalTake } from "@/lib/api/voice"
import { Play, Pause, Check } from "lucide-react"
import { cn } from "@/lib/utils"

const COLOURS = ["bg-amber-500/70", "bg-sky-500/70", "bg-emerald-500/70", "bg-rose-500/70", "bg-violet-500/70", "bg-lime-500/70"]

interface CompViewProps {
  comp: ActiveComp
  takes: VocalTake[]
  busy: boolean
  playingUrl: string | null
  inUse: boolean
  onPlay: (url: string) => void
  onUse: () => void
  onSwap: (phraseIndex: number, takeId: string) => void
}

export function CompView({ comp, takes, busy, playingUrl, inUse, onPlay, onUse, onSwap }: CompViewProps) {
  const [open, setOpen] = useState<number | null>(null)
  const used = Array.from(new Set(comp.segments.map((s) => s.take_id)))
  const candidates = Array.from(new Set([...used, ...Object.keys(comp.segments[0]?.scores ?? {})]))
  const name = (id: string) => takes.find((t) => t.id === id)?.label ?? "a take"
  const colour = (id: string) => COLOURS[Math.max(0, candidates.indexOf(id)) % COLOURS.length]
  const total = comp.segments.at(-1)?.end_time ?? 1

  return (
    <section aria-label="Best-of version" className="mb-6 rounded-xl border border-primary/30 bg-card p-4">
      <div className="mb-3 flex items-center gap-3">
        <button
          onClick={() => onPlay(comp.audio_url)}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/15 text-primary hover:bg-primary/25"
          aria-label={playingUrl === comp.audio_url ? "Pause the best-of version" : "Play the best-of version"}
        >
          {playingUrl === comp.audio_url ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 translate-x-px" />}
        </button>
        <p className="flex-1 text-sm text-foreground">Best-of version</p>
        {inUse ? (
          <span className="flex items-center gap-1 text-xs text-primary"><Check className="h-3.5 w-3.5" /> using</span>
        ) : (
          <button onClick={onUse} className="text-xs text-muted-foreground hover:text-primary">use this</button>
        )}
      </div>
      <div className="flex h-6 w-full overflow-hidden rounded" role="list" aria-label="Which take each line comes from">
        {comp.segments.map((s, i) => (
          <button
            key={i}
            role="listitem"
            title={`Line ${i + 1}: from ${name(s.take_id)}`}
            aria-label={`Line ${i + 1}, from ${name(s.take_id)}. Choose another take for this line.`}
            onClick={() => setOpen(open === i ? null : i)}
            style={{ width: `${((s.end_time - s.start_time) / total) * 100}%` }}
            className={cn("h-full border-r border-background/60", colour(s.take_id), open === i && "ring-2 ring-primary")}
          />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
        {used.map((id) => (
          <span key={id} className="flex items-center gap-1">
            <span className={cn("inline-block h-2 w-2 rounded-full", colour(id))} /> {name(id)}
          </span>
        ))}
      </div>
      {open !== null && comp.segments[open] && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>Line {open + 1} from:</span>
          {candidates.map((id) => (
            <Button
              key={id}
              size="sm"
              variant={comp.segments[open].take_id === id ? "default" : "outline"}
              className="h-7 text-xs"
              disabled={busy || comp.segments[open].take_id === id}
              onClick={() => onSwap(comp.segments[open].phrase_index ?? open, id)}
            >
              {name(id)}
            </Button>
          ))}
        </div>
      )}
    </section>
  )
}
