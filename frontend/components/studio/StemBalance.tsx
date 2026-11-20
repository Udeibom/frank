"use client"

/**
 * StemBalance: the Blend room's lanes. Each thing in the song (your voice, each part of the music, a second
 * voice) is one lane with plain controls: a bit softer, a bit louder, on/off. No sliders or numbers. Each change
 * makes a new blend. The on/off switch shows the state ("On" means you can hear it), never the action.
 */

import { Minus, Plus } from "lucide-react"
import { PART_NAMES } from "@/lib/api/finish"
import { cn } from "@/lib/utils"

interface StemBalanceProps {
  hasVocal: boolean
  hasBeat: boolean
  hasHarmony: boolean
  harmonyEnabled: boolean
  onToggleHarmony: (on: boolean) => void
  /** The parts the music plays; when given, the music is shown part by part. */
  parts?: string[]
  partSettings?: Record<string, { level_db?: number; muted?: boolean }>
  busy?: boolean
  onPart?: (part: string, change: { level_delta_db?: number; muted?: boolean }) => void
}

function levelWords(db: number): string {
  if (db >= 6) return "much louder"
  if (db > 0) return "a bit louder"
  if (db <= -6) return "much softer"
  if (db < 0) return "a bit softer"
  return "as made"
}

function Switch({ on, label, disabled, onChange }: { on: boolean; label: string; disabled?: boolean; onChange: (on: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={cn(
        "w-14 shrink-0 rounded-md border px-2 py-1 text-sm font-medium transition-colors disabled:opacity-60",
        on ? "border-voice/60 bg-raised text-ink" : "border-dashed border-ink-3 text-ink-3",
      )}
    >
      {on ? "On" : "Off"}
    </button>
  )
}

function Lane({
  name,
  state,
  on,
  busy,
  material,
  onSofter,
  onLouder,
  onSwitch,
}: {
  name: string
  state: string
  on: boolean
  busy?: boolean
  material: "voice" | "music"
  onSofter?: () => void
  onLouder?: () => void
  onSwitch?: (on: boolean) => void
}) {
  return (
    <li className={cn("flex items-center gap-3 rounded-md bg-surface px-3 py-2.5", !on && "bg-transparent outline outline-1 outline-dashed outline-ink-3/50")}>
      <span aria-hidden="true" className={cn("h-8 w-1 shrink-0 rounded-[2px]", material === "voice" ? "bg-voice" : "bg-music", !on && "opacity-30")} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-base text-ink">{name}</span>
        <span className="block text-sm text-ink-2">{on ? state : "Turned off"}</span>
      </span>
      {onSofter && (
        <button
          disabled={busy || !on}
          onClick={onSofter}
          aria-label={`${name} a bit softer`}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-line text-ink hover:border-ink-3 disabled:text-ink-3"
        >
          <Minus className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
      {onLouder && (
        <button
          disabled={busy || !on}
          onClick={onLouder}
          aria-label={`${name} a bit louder`}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-line text-ink hover:border-ink-3 disabled:text-ink-3"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
      {onSwitch && <Switch on={on} label={name} disabled={busy} onChange={onSwitch} />}
    </li>
  )
}

export function StemBalance({ hasVocal, hasBeat, hasHarmony, harmonyEnabled, onToggleHarmony, parts, partSettings, busy, onPart }: StemBalanceProps) {
  const byPart = Boolean(hasBeat && parts && parts.length > 0 && onPart)
  return (
    <section aria-labelledby="lanes-heading" className="flex flex-col gap-2">
      <h2 id="lanes-heading" className="text-xs font-semibold uppercase tracking-[0.06em] text-ink-3">
        What's in your song
      </h2>
      <ul className="flex flex-col gap-1.5">
        {hasVocal && <Lane name="Your voice" state="In front" on material="voice" />}
        {hasHarmony && (
          <Lane name="Second voice" state="With your voice" on={harmonyEnabled} busy={busy} material="voice" onSwitch={onToggleHarmony} />
        )}
        {hasBeat && !byPart && <Lane name="The music" state="All its parts together" on material="music" />}
        {byPart &&
          parts!.map((part) => {
            const st = partSettings?.[part] ?? {}
            const name = PART_NAMES[part] ?? part
            return (
              <Lane
                key={part}
                name={name}
                state={levelWords(st.level_db ?? 0)}
                on={!st.muted}
                busy={busy}
                material="music"
                onSofter={() => onPart!(part, { level_delta_db: -3 })}
                onLouder={() => onPart!(part, { level_delta_db: 3 })}
                onSwitch={(on) => onPart!(part, { muted: !on })}
              />
            )
          })}
      </ul>
    </section>
  )
}
