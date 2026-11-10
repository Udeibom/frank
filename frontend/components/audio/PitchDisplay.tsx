"use client"

/**
 * PitchDisplay — a gentle view of how steady a take is. Feedback, never
 * judgment: it just shows where the rough patches are. No note names, no
 * numbers.
 *
 * Steadiness is NOT conveyed by color alone (design-and-ui.md): each level also
 * has its own bar shape (solid / dotted edge / dashed outline), a text legend,
 * and a plain-language summary for screen readers.
 */

import type { PitchPoint } from "@/types/audio"
import { pitchAccuracy } from "@/types/audio"
import { cn } from "@/lib/utils"

interface PitchDisplayProps {
  pitchData: PitchPoint[] | null
}

type Accuracy = ReturnType<typeof pitchAccuracy>

// Warm palette on purpose: no alarm-red on someone's own singing.
const BAR_STYLE: Record<Accuracy, string> = {
  good: "bg-emerald-500/70",
  close: "bg-amber-400/70 border-t-2 border-dotted border-amber-200",
  off: "bg-orange-500/50 border border-dashed border-orange-300",
}

const LEGEND: Record<Accuracy, string> = {
  good: "Steady",
  close: "A little wobbly",
  off: "Worth another try",
}

export function PitchDisplay({ pitchData }: PitchDisplayProps) {
  if (!pitchData || pitchData.length === 0) {
    return (
      <div className="flex h-10 items-center justify-center rounded-md bg-muted/40">
        <span className="text-[11px] text-muted-foreground/50">
          Listening to your take…
        </span>
      </div>
    )
  }

  // Map the contour to vertical bars; height reflects relative pitch, the
  // style reflects how solidly the note landed.
  const notes = pitchData.map((p) => p.note)
  const min = Math.min(...notes)
  const max = Math.max(...notes)
  const range = Math.max(max - min, 1)

  // Downsample to keep the display light if there are many points
  const step = Math.max(1, Math.floor(pitchData.length / 120))
  const points = pitchData.filter((_, i) => i % step === 0)

  const counts: Record<Accuracy, number> = { good: 0, close: 0, off: 0 }
  for (const p of points) counts[pitchAccuracy(p.confidence)] += 1
  const pct = (n: number) => Math.round((n / points.length) * 100)
  const summary =
    `${pct(counts.good)}% steady, ${pct(counts.close)}% a little wobbly, ` +
    `${pct(counts.off)}% worth another try`

  return (
    <div>
      <div
        role="img"
        aria-label={`How steady this take is: ${summary}`}
        className="flex h-10 items-end gap-[1px] overflow-hidden rounded-md bg-muted/40 px-1 py-1"
      >
        {points.map((p, i) => {
          const heightPct = 20 + ((p.note - min) / range) * 80
          const accuracy = pitchAccuracy(p.confidence)
          return (
            <div
              key={i}
              className={cn("flex-1 rounded-sm", BAR_STYLE[accuracy])}
              style={{ height: `${heightPct}%` }}
            />
          )
        })}
      </div>
      <ul className="mt-1.5 flex gap-4 text-[11px] text-muted-foreground">
        {(Object.keys(LEGEND) as Accuracy[]).map((level) => (
          <li key={level} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className={cn("inline-block h-2.5 w-2.5 rounded-sm", BAR_STYLE[level])}
            />
            {LEGEND[level]}
          </li>
        ))}
      </ul>
    </div>
  )
}
