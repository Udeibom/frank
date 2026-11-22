"use client"

/**
 * DirectionCard: one sound Frank played to find the song's feeling. A cell on the listening bench: a name, a
 * line about it, its shape, a play control, and the two things a person can say about it.
 * Cards that are being made or that failed are shown as ghosts in the same place, so nothing jumps around.
 */

import { Check, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { PlayButton } from "@/components/audio/PlayButton"
import { SoundShape } from "@/components/audio/SoundShape"
import { formatTime, useAudio, usePlayback, type Track } from "@/store/audio"
import type { Direction } from "@/store/directions"

interface DirectionCardProps {
  direction: Direction
  /** This is the feeling the song has kept. */
  kept: boolean
  /** This card gets the one amber action on the screen. */
  primary: boolean
  onKeep: (d: Direction) => void
  onNotThis: (d: Direction) => void
  onRetry: (d: Direction) => void
  /** Frank's ears found this one sounds closest to the person's own words (frankenstein spec 14, 2.1). */
  closest?: boolean
}

export function directionTrack(d: Direction): Track {
  // Plays through, goes round once more, then stops (feel-lab requirement 2.2).
  return { id: d.id, url: d.url, label: `Direction ${d.number}`, material: "feel", playsTwice: true }
}

function madeAt(iso: string | null): string {
  if (!iso) return ""
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
}

export function DirectionCard({ direction: d, kept, primary, onKeep, onNotThis, onRetry, closest }: DirectionCardProps) {
  const track = directionTrack(d)
  const { isCurrent, playing, progress, position, duration } = usePlayback(d.status === "ready" ? d.id : null)
  const seekFraction = useAudio((s) => s.seekFraction)
  const play = useAudio((s) => s.play)

  if (d.status === "making") {
    return (
      <article
        aria-label="A direction is being made"
        aria-busy="true"
        className="relative flex min-h-[236px] flex-col justify-between overflow-hidden rounded-xl border border-frank/20 bg-raised p-5"
      >
        <div className="sweep absolute inset-0 opacity-50" aria-hidden="true" />
        <div className="relative z-10">
          <h3 className="font-written italic text-xl text-ink">Finding a sound…</h3>
          <p className="text-sm text-ink-2">This usually takes about 20 seconds. Keep talking to Frank while you wait.</p>
        </div>
        <div className="relative z-10 flex items-center gap-2 text-sm text-ink-3" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Making it from what you said
        </div>
      </article>
    )
  }

  if (d.status === "failed") {
    return (
      <article aria-label="A direction that didn't come out" className="flex min-h-[236px] flex-col justify-between rounded-md border border-problem/70 bg-surface p-4">
        <div>
          <h3 className="font-written text-xl text-ink">That one didn&apos;t come out</h3>
          <p className="text-sm text-ink-2">Nothing you made is lost. Frank can try that sound again.</p>
        </div>
        <button
          onClick={() => onRetry(d)}
          className="w-fit rounded-md border border-line bg-raised px-4 py-2 text-base text-ink hover:border-ink-3"
        >
          Try again
        </button>
      </article>
    )
  }

  return (
    <article
      aria-label={`Direction ${d.number}`}
      className={cn(
        "flex flex-col gap-3 rounded-xl border bg-raised p-5 transition-all duration-200",
        isCurrent
          ? "border-feel shadow-[0_0_0_1px_rgb(var(--feel)/0.3),0_4px_24px_rgb(var(--feel)/0.12)]"
          : kept
            ? "border-feel/50"
            : d.setAside
              ? "border-dashed border-ink-3/40 opacity-70"
              : "border-line/60 hover:border-line",
      )}
    >
      <div>
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="font-written italic text-xl text-ink">Direction {d.number}</h3>
          {closest && <span className="ml-2 rounded-full bg-feel/10 border border-feel/40 px-2.5 py-0.5 text-xs text-ink-2">Closest to your words</span>}
          {kept && (
            <span className="flex items-center gap-1 text-sm text-feel">
              <Check className="h-3.5 w-3.5" aria-hidden="true" /> Kept
            </span>
          )}
          {!kept && d.setAside && <span className="text-sm text-ink-3">Set aside</span>}
        </div>
        <p className="line-clamp-2 text-sm text-ink-2">{d.note ?? (madeAt(d.createdAt) ? `Made at ${madeAt(d.createdAt)}` : "Made earlier")}</p>
      </div>

      <SoundShape
        points={d.waveform}
        progress={progress}
        material="feel"
        live={isCurrent}
        label={`Direction ${d.number}`}
        onSeek={(f) => {
          if (isCurrent) seekFraction(f)
          else void play(track, { keepPosition: false }).then(() => seekFraction(f))
        }}
      />

      <div className="flex items-center gap-3">
        <PlayButton track={track} size="card" keepPosition />
        <span className="ml-auto text-sm tabular-nums text-ink-3">
          {isCurrent && duration > 0 ? `${formatTime(position)} / ${formatTime(duration)}` : playing ? "" : "Plays twice"}
        </span>
      </div>

      {!kept && (
        <div className="flex gap-2">
          <button
            onClick={() => onKeep(d)}
            className={cn(
              "flex-1 rounded-full border px-3 py-2 text-sm font-medium transition-all duration-150",
              primary
                ? "border-frank bg-frank text-ground hover:bg-frank/90 hover:-translate-y-px"
                : "border-line bg-surface text-ink hover:border-ink-3",
            )}
          >
            This is it
          </button>
          {!d.setAside && (
            <button
              onClick={() => onNotThis(d)}
              className="flex-1 rounded-full border border-line bg-surface px-3 py-2 text-sm text-ink hover:border-ink-3"
            >
              Not this
            </button>
          )}
        </div>
      )}
    </article>
  )
}
