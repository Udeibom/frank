"use client"

/**
 * PlayButton: the one play control in Frank, in three sizes. It never makes sound itself; it asks the
 * AudioEngine, so starting one sound stops any other. The accessible name always says what it plays.
 *
 * Visual: amber fill + active radial bloom when playing; ghost ring at rest. Stage size is 64px.
 */

import { Loader2, Pause, Play } from "lucide-react"
import { cn } from "@/lib/utils"
import { usePlayback, useAudio, type Track } from "@/store/audio"

type Size = "stage" | "card" | "row"

const SIZE: Record<Size, { box: string; icon: string }> = {
  stage: { box: "h-16 w-16", icon: "h-6 w-6" },   // 64px — Stitch stage large
  card:  { box: "h-11 w-11 sm:h-10 sm:w-10", icon: "h-4 w-4" },   // 40px — card medium
  row:   { box: "h-11 w-11 sm:h-7 sm:w-7", icon: "h-4 w-4 sm:h-3.5 sm:w-3.5" }, // 28px — row small
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
        "play-bloom flex shrink-0 items-center justify-center rounded-full border transition-all duration-150",
        dims.box,
        // Amber fill + bloom when playing; ghost ring at rest
        playing
          ? "border-frank bg-frank text-ground shadow-play-bloom"
          : size === "stage"
            ? "border-line bg-raised text-ink hover:border-frank/60 hover:bg-raised"
            : "border-line bg-transparent text-ink hover:border-frank/50 hover:bg-raised",
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
