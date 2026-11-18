"use client"

/**
 * Waveform — the shape of the song, drawn from loudness points the backend measured (the browser never
 * analyses audio). Click anywhere to jump there.
 */

interface WaveformProps {
  points: number[]
  progress: number
  onSeek?: (fraction: number) => void
  label?: string
}

export function Waveform({ points, progress, onSeek, label = "The shape of your song" }: WaveformProps) {
  if (!points.length) return null
  const w = 600
  const h = 64
  const bar = w / points.length
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-16 w-full cursor-pointer"
      role="slider"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(progress * 100)}
      tabIndex={0}
      onKeyDown={(e) => {
        if (!onSeek) return
        if (e.key === "ArrowRight") onSeek(Math.min(1, progress + 0.05))
        if (e.key === "ArrowLeft") onSeek(Math.max(0, progress - 0.05))
      }}
      onClick={(e) => {
        if (!onSeek) return
        const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
        onSeek(Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)))
      }}
    >
      {points.map((p, i) => {
        const bh = Math.max(2, p * (h - 4))
        return (
          <rect
            key={i}
            x={i * bar + bar * 0.15}
            y={(h - bh) / 2}
            width={bar * 0.7}
            height={bh}
            rx={bar * 0.3}
            className={i / points.length <= progress ? "fill-primary" : "fill-muted-foreground/40"}
          />
        )
      })}
    </svg>
  )
}
