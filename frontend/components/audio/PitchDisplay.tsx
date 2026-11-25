"use client"

/**
 * PitchDisplay: a gentle view of how steady a take is. Feedback, never judgment: it shows where the rough
 * patches are. No note names, no numbers, no Hz or cents.
 *
 * Visual (Stitch spec): a horizontal track with a centred target zone. Each recorded moment is shown as a
 * small bead positioned relative to the target. Steadiness has three states:
 *   • good  → green bead, centred (Steady)
 *   • close → amber bead, slightly offset (A little wobbly)
 *   • off   → coral bead, at the edge (Worth another try)
 *
 * Colour is never the only signal: each state also has a distinct shape (filled, half-strength, outline-only)
 * and a plain-language legend + screen-reader summary.
 */

import type { PitchPoint } from "@/types/audio"
import { pitchAccuracy } from "@/types/audio"
import { cn } from "@/lib/utils"

interface PitchDisplayProps {
  pitchData: PitchPoint[] | null
}

type Accuracy = ReturnType<typeof pitchAccuracy>

// Vertical offset of each bead from the centre rail, in px (SVG units)
const Y_OFFSET: Record<Accuracy, number> = {
  good:  0,   // centred on the rail
  close: 5,   // slightly off
  off:   11,  // at the edge
}

// Colour class for each bead (never colour-only: shape also differs)
const BEAD_CLASS: Record<Accuracy, string> = {
  good:  "fill-ok",
  close: "fill-caution",
  off:   "fill-problem",
}

// Bead radius differs by state so shape is a secondary signal (not colour-only).
const BEAD_R: Record<Accuracy, number> = {
  good:  3.5,
  close: 3,
  off:   2.5,
}

// Bead opacity (adds a third dimension of feedback)
const BEAD_OPACITY: Record<Accuracy, number> = {
  good:  1,
  close: 0.65,
  off:   0.45,
}

const LEGEND: Record<Accuracy, string> = {
  good:  "Steady",
  close: "A little wobbly",
  off:   "Worth another try",
}

const LEGEND_SHAPE: Record<Accuracy, string> = {
  good:  "h-2.5 w-2.5 rounded-full bg-ok",
  close: "h-2.5 w-2.5 rounded-full bg-caution/65",
  off:   "h-2.5 w-2.5 rounded-full bg-problem/45",
}

const SVG_W = 600
const SVG_H = 40
const RAIL_Y = SVG_H / 2  // centre of the track

export function PitchDisplay({ pitchData }: PitchDisplayProps) {
  if (!pitchData || pitchData.length === 0) {
    return (
      <div className="sweep flex h-10 items-center justify-center rounded-md [--sweep:var(--voice)]">
        <span className="text-sm text-ink-2">Frank is checking your notes…</span>
      </div>
    )
  }

  // Downsample for performance
  const step = Math.max(1, Math.floor(pitchData.length / 150))
  const points = pitchData.filter((_, i) => i % step === 0)

  const counts: Record<Accuracy, number> = { good: 0, close: 0, off: 0 }
  for (const p of points) counts[pitchAccuracy(p.confidence)] += 1
  const pct = (n: number) => Math.round((n / points.length) * 100)
  const summary = `${pct(counts.good)}% steady, ${pct(counts.close)}% a little wobbly, ${pct(counts.off)}% worth another try`

  const colStep = SVG_W / Math.max(points.length, 1)

  return (
    <div>
      {/* The horizontal bead-on-track */}
      <svg
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        preserveAspectRatio="none"
        className="h-10 w-full"
        role="img"
        aria-label={`How steady this recording is: ${summary}`}
      >
        {/* Centre rail (the target zone) */}
        <rect
          x={0}
          y={RAIL_Y - 1}
          width={SVG_W}
          height={2}
          rx={1}
          className="fill-line"
          opacity={0.8}
        />
        {/* Target zone highlight — the "in tune" band */}
        <rect
          x={0}
          y={RAIL_Y - 4}
          width={SVG_W}
          height={8}
          rx={4}
          className="fill-ok"
          opacity={0.08}
        />

        {/* One bead per point */}
        {points.map((p, i) => {
          const acc = pitchAccuracy(p.confidence)
          const cx = i * colStep + colStep / 2
          // Alternate above/below so nearby off-beads don't stack
          const sign = i % 2 === 0 ? 1 : -1
          const cy = RAIL_Y + sign * Y_OFFSET[acc]
          return (
            <circle
              key={i}
              cx={cx}
              cy={cy}
              r={BEAD_R[acc]}
              className={BEAD_CLASS[acc]}
              opacity={BEAD_OPACITY[acc]}
            />
          )
        })}
      </svg>

      {/* Legend — shape + colour + word so it's never colour-only */}
      <ul className="mt-2 flex gap-4 text-sm text-ink-2">
        {(Object.keys(LEGEND) as Accuracy[]).map((level) => (
          <li key={level} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={cn("inline-block shrink-0", LEGEND_SHAPE[level])} />
            {LEGEND[level]}
          </li>
        ))}
      </ul>
    </div>
  )
}
