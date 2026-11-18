"use client"

/**
 * StemBalance — what's in the mix: your voice, every part of the music (spec 11), and (if it exists) a harmony.
 * No sliders or numbers ("no technical controls"): each part can be made a bit softer or louder, or turned off,
 * and the harmony turned on or off.
 */

import { Mic2, Drum, Users, Minus, Plus } from "lucide-react"
import { PART_NAMES } from "@/lib/api/finish"
import { cn } from "@/lib/utils"

interface StemBalanceProps {
  hasVocal: boolean
  hasBeat: boolean
  hasHarmony: boolean
  harmonyEnabled: boolean
  onToggleHarmony: (on: boolean) => void
  /** The parts the music plays; when given, the beat is shown part by part. */
  parts?: string[]
  partSettings?: Record<string, { level_db?: number; muted?: boolean }>
  busy?: boolean
  onPart?: (part: string, change: { level_delta_db?: number; muted?: boolean }) => void
}

export function StemBalance({
  hasVocal,
  hasBeat,
  hasHarmony,
  harmonyEnabled,
  onToggleHarmony,
  parts,
  partSettings,
  busy,
  onPart,
}: StemBalanceProps) {
  const byPart = Boolean(hasBeat && parts && parts.length > 0 && onPart)
  return (
    <div className="flex flex-col gap-2">
      <p className="px-1 text-xs font-medium text-muted-foreground">What&apos;s in your song</p>
      {hasVocal && <StemRow icon={<Mic2 className="h-4 w-4" />} label="Your voice" active />}
      {hasBeat && !byPart && <StemRow icon={<Drum className="h-4 w-4" />} label="The beat" active />}
      {byPart &&
        parts!.map((part) => {
          const st = partSettings?.[part] ?? {}
          const name = PART_NAMES[part] ?? part
          const lvl = st.level_db ?? 0
          return (
            <div key={part} className={cn("flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2", st.muted && "opacity-50")}>
              <span className="text-primary">
                <Drum className="h-4 w-4" />
              </span>
              <span className="flex-1 text-sm text-foreground">
                {name}
                {!st.muted && lvl !== 0 && <span className="ml-2 text-[11px] text-muted-foreground">{lvl > 0 ? "louder" : "softer"}</span>}
                {st.muted && <span className="ml-2 text-[11px] text-muted-foreground">off</span>}
              </span>
              <button
                disabled={busy || st.muted}
                onClick={() => onPart!(part, { level_delta_db: -3 })}
                aria-label={`${name} a bit softer`}
                className="rounded-full p-1 text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-40"
              >
                <Minus className="h-3.5 w-3.5" />
              </button>
              <button
                disabled={busy || st.muted}
                onClick={() => onPart!(part, { level_delta_db: 3 })}
                aria-label={`${name} a bit louder`}
                className="rounded-full p-1 text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-40"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
              <button
                disabled={busy}
                onClick={() => onPart!(part, { muted: !st.muted })}
                role="switch"
                aria-checked={!st.muted}
                aria-label={st.muted ? `Turn ${name} back on` : `Turn ${name} off`}
                className="rounded px-1.5 text-[11px] text-muted-foreground hover:text-foreground"
              >
                {st.muted ? "on" : "off"}
              </button>
            </div>
          )
        })}
      {hasHarmony && (
        <StemRow
          icon={<Users className="h-4 w-4" />}
          label="Harmony"
          active={harmonyEnabled}
          toggle={{ on: harmonyEnabled, onChange: onToggleHarmony }}
        />
      )}
    </div>
  )
}

function StemRow({
  icon,
  label,
  active,
  toggle,
}: {
  icon: React.ReactNode
  label: string
  active: boolean
  toggle?: { on: boolean; onChange: (on: boolean) => void }
}) {
  return (
    <div className={cn("flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2.5", !active && "opacity-50")}>
      <span className="text-primary">{icon}</span>
      <span className="flex-1 text-sm text-foreground">{label}</span>
      {toggle ? (
        <button
          onClick={() => toggle.onChange(!toggle.on)}
          className={cn("relative h-5 w-9 rounded-full transition-colors", toggle.on ? "bg-primary" : "bg-muted")}
          aria-label={toggle.on ? "Turn harmony off" : "Turn harmony on"}
          role="switch"
          aria-checked={toggle.on}
        >
          <span className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform", toggle.on ? "translate-x-4" : "translate-x-0.5")} />
        </button>
      ) : (
        <span className="h-2 w-2 rounded-full bg-primary" />
      )}
    </div>
  )
}
