"use client"

/**
 * FrankNote: what Frank is saying or asking right now, on the stage, next to the thing it is about, with the
 * answers as buttons. The stage never tells the person to look at the conversation panel.
 * The rule on its left is the colour of the material the room works on (amber is kept for what is sounding
 * and the one action Frank wants).
 */

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import type { Material } from "@/store/audio"

const RULE: Record<Material, string> = {
  words: "border-words",
  feel: "border-feel",
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
}

export function FrankNote({ children, aside, answers = [], material, problem, busy, className }: FrankNoteProps) {
  return (
    <section
      aria-label="Frank"
      aria-live="polite"
      aria-busy={busy}
      className={cn(
        "flex items-center justify-between gap-5 rounded-r-md border-l-[3px] bg-surface px-5 py-4",
        problem ? "border-problem" : material ? RULE[material] : "border-ink-3",
        className,
      )}
    >
      <div className="min-w-0 max-w-xl">
        <p className="text-base text-ink">{children}</p>
        {aside && <p className="mt-0.5 text-sm text-ink-2">{aside}</p>}
      </div>
      {answers.length > 0 && (
        <div className="flex shrink-0 gap-2.5">
          {answers.map((a) => (
            <button
              key={a.label}
              onClick={a.onClick}
              disabled={a.disabled}
              className={cn(
                "whitespace-nowrap rounded-md border px-4 py-2 text-base transition-colors disabled:opacity-60",
                a.primary
                  ? "border-frank bg-frank font-medium text-ground hover:bg-frank/90"
                  : "border-line bg-raised text-ink hover:border-ink-3",
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
