"use client"

/**
 * PitchDisplay: a gentle view of how steady a take is. Feedback, never judgment: it shows where the rough
 * patches are. No note names, no numbers.
 *
 * Steadiness is never shown by colour alone (design-and-ui.md): each level has its own bar shape (solid,
 * half-strength with a dotted top, an outline only), a text legend, and a plain-language summary for screen
 * readers. All in the voice's own colour: no alarm-red on someone's singing.
 */

import type { PitchPoint } from "@/types/audio"
import { pitchAccuracy } from "@/types/audio"
import { cn } from "@/lib/utils"

interface PitchDisplayProps {
  pitchData: PitchPoint[] | null
}

type Accuracy = ReturnType<typeof pitchAccuracy>

const BAR_STYLE: Record<Accuracy, string> = {
  good: "bg-voice",
  close: "bg-voice/50 border-t-2 border-dotted border-voice",
  off: "border border-dashed border-voice/80",
}

const LEGEND: Record<Accuracy, string> = {
  good: "Steady",
  close: "A little wobbly",
  off: "Worth another try",
}

export function PitchDisplay({ pitchData }: PitchDisplayProps) {
  if (!pitchData || pitchData.length === 0) {
    return (
      <div className="sweep flex h-10 items-center justify-center rounded-sm [--sweep:var(--voice)]">
        <span className="text-sm text-ink-2">Frank is checking your notes…</span>
      </div>
    )
  }

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
  const summary = `${pct(counts.good)}% steady, ${pct(counts.close)}% a little wobbly, ${pct(counts.off)}% worth another try`

  return (
    <div>
      <div role="img" aria-label={`How steady this recording is: ${summary}`} className="flex h-10 items-end gap-[1px] overflow-hidden rounded-sm px-0.5 py-1">
        {points.map((p, i) => {
          const heightPct = 20 + ((p.note - min) / range) * 80
          return <div key={i} className={cn("flex-1 rounded-[1px]", BAR_STYLE[pitchAccuracy(p.confidence)])} style={{ height: `${heightPct}%` }} />
        })}
      </div>
      <ul className="mt-1.5 flex gap-4 text-xs text-ink-2">
        {(Object.keys(LEGEND) as Accuracy[]).map((level) => (
          <li key={level} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={cn("inline-block h-2.5 w-2.5 rounded-[1px]", BAR_STYLE[level])} />
            {LEGEND[level]}
          </li>
        ))}
      </ul>
    </div>
  )
}
