"use client"

/**
 * PlayButton: the one play control in Frank, in three sizes. It never makes sound itself; it asks the
 * AudioEngine, so starting one sound stops any other. The accessible name always says what it plays.
 */

import { Loader2, Pause, Play } from "lucide-react"
import { cn } from "@/lib/utils"
import { usePlayback, useAudio, type Track } from "@/store/audio"

type Size = "stage" | "card" | "row"

const SIZE: Record<Size, { box: string; icon: string }> = {
  stage: { box: "h-12 w-12", icon: "h-5 w-5" },
  card: { box: "h-9 w-9", icon: "h-4 w-4" },
  row: { box: "h-7 w-7", icon: "h-3.5 w-3.5" },
}

interface PlayButtonProps {
  track: Track
  size?: Size
  /** Start in step with whatever is playing now (for comparing ideas). */
  keepPosition?: boolean
  className?: string
  /** Called after the user presses it, e.g. to note that they listened. */
  onPressed?: () => void
  /** Added to the accessible name when another control on the screen plays the same thing ("in the history"). */
  where?: string
}

export function PlayButton({ track, size = "card", keepPosition, className, onPressed, where }: PlayButtonProps) {
  const { playing, loading } = usePlayback(track.id)
  const toggle = useAudio((s) => s.toggle)
  const dims = SIZE[size]

  return (
    <button
      type="button"
      onClick={() => {
        void toggle(track, { keepPosition })
        onPressed?.()
      }}
      aria-label={`${playing ? "Pause" : "Play"} ${track.label}${where ? `, ${where}` : ""}`}
      aria-pressed={playing}
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full border transition-colors",
        dims.box,
        // The amber fill belongs to what is playing right now; at rest, a plain ring.
        playing
          ? "border-frank bg-frank text-ground"
          : "border-ink-3 bg-transparent text-ink hover:border-ink hover:bg-raised",
        className,
      )}
    >
      {loading ? (
        <Loader2 className={cn(dims.icon, "animate-spin")} aria-hidden="true" />
      ) : playing ? (
        <Pause className={dims.icon} aria-hidden="true" />
      ) : (
        <Play className={cn(dims.icon, "translate-x-px")} aria-hidden="true" />
      )}
    </button>
  )
}
