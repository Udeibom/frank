"use client"

/**
 * SoundShape: the shape of a sound, drawn from loudness points the backend measured (the browser never
 * analyses audio). Thin marks in the colour of the material the sound belongs to; the part already heard is
 * at full strength, the rest quieter; a 2px playhead shows where you are. Click or use the arrow keys to move.
 *
 * `points` null = still being measured (a quiet sweep), `[]` = could not be measured (a flat line).
 */

import { cn } from "@/lib/utils"
import type { Material } from "@/store/audio"

const FILL: Record<Material, string> = {
  words: "fill-words",
  feel: "fill-feel",
  music: "fill-music",
  voice: "fill-voice",
}

interface SoundShapeProps {
  points: number[] | null
  /** 0..1 */
  progress: number
  material: Material
  /** True when this is the sound being heard (shows the playhead). */
  live?: boolean
  onSeek?: (fraction: number) => void
  /** What this is the shape of, for screen readers: "Direction 2". */
  label: string
  className?: string
}

const W = 600
const H = 64

export function SoundShape({ points, progress, material, live, onSeek, label, className }: SoundShapeProps) {
  if (points === null) {
    return <div aria-hidden="true" className={cn("sweep h-16 w-full rounded-sm", className)} />
  }
  if (points.length === 0) {
    return (
      <svg viewBox={`0 0 ${W} ${H}`} className={cn("h-16 w-full", className)} role="img" aria-label={`${label}: no picture available`} preserveAspectRatio="none">
        <rect x="0" y={H / 2 - 1} width={W} height="2" className="fill-line" />
      </svg>
    )
  }

  const step = W / points.length
  const bar = Math.max(1.5, step * 0.55)
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={cn("h-16 w-full", onSeek && "cursor-pointer", className)}
      role={onSeek ? "slider" : "img"}
      aria-label={`${label}: the shape of the sound`}
      aria-valuemin={onSeek ? 0 : undefined}
      aria-valuemax={onSeek ? 100 : undefined}
      aria-valuenow={onSeek ? Math.round(progress * 100) : undefined}
      aria-valuetext={onSeek ? `${Math.round(progress * 100)} percent through` : undefined}
      tabIndex={onSeek ? 0 : undefined}
      onKeyDown={(e) => {
        if (!onSeek) return
        if (e.key === "ArrowRight") {
          e.preventDefault()
          onSeek(Math.min(1, progress + 0.05))
        }
        if (e.key === "ArrowLeft") {
          e.preventDefault()
          onSeek(Math.max(0, progress - 0.05))
        }
      }}
      onClick={(e) => {
        if (!onSeek) return
        const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
        onSeek(Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)))
      }}
    >
      {points.map((p, i) => {
        const h = Math.max(3, p * (H - 6))
        const heard = live && i / points.length < progress
        return (
          <rect
            key={i}
            x={i * step + (step - bar) / 2}
            y={(H - h) / 2}
            width={bar}
            height={h}
            rx="1"
            className={FILL[material]}
            opacity={heard ? 1 : live ? 0.5 : 0.7}
          />
        )
      })}
      {live && <rect x={Math.min(W - 2, progress * W)} y="0" width="2" height={H} className="fill-frank" />}
    </svg>
  )
}
