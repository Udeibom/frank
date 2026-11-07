"use client"

/**
 * PitchDisplay — a gentle, color-coded view of how in-tune a take is.
 * Green = solid, amber = a little off, red = noticeably off. This is feedback,
 * never judgment — it just shows where the rough patches are. No note names,
 * no numbers. Purely a display of pitch data the backend already computed.
 */

import type { PitchPoint } from "@/types/audio"
import { pitchAccuracy } from "@/types/audio"
import { cn } from "@/lib/utils"

interface PitchDisplayProps {
  pitchData: PitchPoint[] | null
}

const ACCURACY_COLOR = {
  good: "bg-emerald-500/70",
  close: "bg-amber-400/70",
  off: "bg-red-500/60",
} as const

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

  // Map the contour to vertical bars; height reflects relative pitch, color
  // reflects confidence (how solidly the note landed).
  const notes = pitchData.map((p) => p.note)
  const min = Math.min(...notes)
  const max = Math.max(...notes)
  const range = Math.max(max - min, 1)

  // Downsample to keep the display light if there are many points
  const step = Math.max(1, Math.floor(pitchData.length / 120))
  const points = pitchData.filter((_, i) => i % step === 0)

  return (
    <div className="flex h-10 items-end gap-[1px] overflow-hidden rounded-md bg-muted/40 px-1 py-1">
      {points.map((p, i) => {
        const heightPct = 20 + ((p.note - min) / range) * 80
        const accuracy = pitchAccuracy(p.confidence)
        return (
          <div
            key={i}
            className={cn("flex-1 rounded-sm", ACCURACY_COLOR[accuracy])}
            style={{ height: `${heightPct}%` }}
          />
        )
      })}
    </div>
  )
}
