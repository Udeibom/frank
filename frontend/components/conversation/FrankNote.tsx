"use client"

/**
 * FrankNote: what Frank is saying or asking right now, on the stage, next to the thing it is about, with the
 * answers as buttons. The stage never tells the person to look at the conversation panel.
 * The rule on its left is the colour of the material the room works on (amber is kept for what is sounding
 * and the one action Frank wants).
 *
 * Busy state: a glowing amber filament bar sweeps across the top to show Frank is working.
 * Problem state: the rule turns to the problem colour. Always say what is safe in the text.
 */

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import type { Material } from "@/store/audio"

const RULE: Record<Material, string> = {
  words: "border-words",
  feel:  "border-feel",
  music: "border-music",
  voice: "border-voice",
}

interface FrankNoteProps {
  children: ReactNode
  /** A line under the main sentence, e.g. what the person said ("You said: ..."). */
  aside?: ReactNode
  /** `primary` marks the one action Frank wants next (amber). At most one per screen. */
  answers?: { label: string; onClick: () => void; disabled?: boolean; primary?: boolean }[]
  material?: Material
  /** Something went wrong: the rule turns to the problem colour. Always say what is safe in the text. */
  problem?: boolean
  busy?: boolean
  className?: string
  appearance?: "compact" | "room"
  roleLabel?: string
}

export function FrankNote({ children, aside, answers = [], material, problem, busy, className, appearance = "compact", roleLabel }: FrankNoteProps) {
  const borderColor = problem ? "border-problem" : material ? RULE[material] : "border-frank/50"
  const room = appearance === "room"
  return (
    <section
      aria-label="Frank"
      aria-live="polite"
      aria-busy={busy}
      className={cn(
        "relative flex items-start justify-between gap-5 overflow-hidden",
        room ? "w-full rounded-xl border border-line/40 bg-surface-low p-4 shadow-[0_4px_20px_rgba(0,0,0,0.3)]" : "rounded-r-lg border-l-[3px] bg-surface px-5 py-4 shadow-l2",
        room ? "border border-line/40" : cn("border border-line/40", borderColor),
        !problem && !busy && "frank-note-border",
        className,
      )}
    >
      {/* Amber filament bar sweeps the top edge when Frank is working */}
      {busy && (
        <div
          aria-hidden="true"
          className="frank-filament pointer-events-none absolute inset-x-0 top-0 h-0.5 rounded-t"
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col gap-1 max-w-xl">
        <div className={room ? "flex items-center gap-3" : "flex items-center gap-2 mb-1"}>
          <span
            className={room ? "flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-frank-container text-xl font-bold italic text-on-primary shadow-[0_0_12px_rgba(245,158,11,0.25)] select-none" : "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold italic select-none"}
            style={room ? undefined : { background: "rgb(var(--frank) / 0.15)", color: "rgb(var(--frank))" }}
            aria-hidden="true"
          >
            f
          </span>
          <div className={room ? "flex items-center gap-2" : undefined}>
            <span className={room ? "text-label-md font-semibold text-frank-text" : "text-label-md font-semibold uppercase tracking-[0.1em] text-ink-3"}>Frank</span>
            {room && <span className="h-1 w-1 rounded-full bg-frank-container" />}
            {room && roleLabel && <span className="text-code text-on-surface-variant">{roleLabel}</span>}
          </div>
        </div>
        <p className={room ? "mt-0.5 text-base leading-[21px] text-on-surface" : "text-base leading-[21px] font-[500] text-ink"}>{children}</p>
        {aside && <p className={room ? "mt-1 text-sm text-on-surface-variant" : "mt-1 text-sm text-ink-2"}>{aside}</p>}
      </div>
      {answers.length > 0 && (
        <div className={room ? "flex shrink-0 flex-wrap items-center gap-2 self-center" : "flex shrink-0 flex-wrap gap-2 pt-1"}>
          {answers.map((a) => (
            <button
              key={a.label}
              onClick={a.onClick}
              disabled={a.disabled}
              className={cn(
                room ? "whitespace-nowrap rounded-lg px-4 py-1.5 text-label-md font-semibold transition-all duration-150 disabled:opacity-60" : "whitespace-nowrap rounded-full border px-5 py-2 text-sm font-medium transition-all duration-150 disabled:opacity-60",
                a.primary
                  ? room
                    ? "bg-frank text-on-primary hover:bg-frank-shade hover:shadow-[0_0_16px_rgba(245,158,11,0.25)]"
                    : "border-frank bg-frank text-ground hover:bg-frank-shade hover:-translate-y-px"
                  : room
                    ? "bg-surface-high text-on-surface hover:bg-surface-highest"
                    : "border-line bg-raised text-ink hover:border-ink-3 hover:bg-raised/70",
              )}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </section>
  )
}
