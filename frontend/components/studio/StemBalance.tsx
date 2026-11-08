"use client"

/**
 * StemBalance — a simple, read-only view of what's in the mix: your voice, the
 * beat, and (if it exists) a harmony. No gain sliders — the numbers stay hidden,
 * matching Frank's "no technical controls" principle. The only direct control is
 * turning the harmony on or off.
 */

import { Mic2, Drum, Users } from "lucide-react"
import { cn } from "@/lib/utils"

interface StemBalanceProps {
  hasVocal: boolean
  hasBeat: boolean
  hasHarmony: boolean
  harmonyEnabled: boolean
  onToggleHarmony: (on: boolean) => void
}

export function StemBalance({
  hasVocal,
  hasBeat,
  hasHarmony,
  harmonyEnabled,
  onToggleHarmony,
}: StemBalanceProps) {
  return (
    <div className="flex flex-col gap-2">
      <p className="px-1 text-xs font-medium text-muted-foreground">
        What&apos;s in your song
      </p>

      {hasVocal && (
        <StemRow icon={<Mic2 className="h-4 w-4" />} label="Your voice" active />
      )}
      {hasBeat && (
        <StemRow icon={<Drum className="h-4 w-4" />} label="The beat" active />
      )}
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
    <div
      className={cn(
        "flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2.5",
        !active && "opacity-50",
      )}
    >
      <span className="text-primary">{icon}</span>
      <span className="flex-1 text-sm text-foreground">{label}</span>
      {toggle ? (
        <button
          onClick={() => toggle.onChange(!toggle.on)}
          className={cn(
            "relative h-5 w-9 rounded-full transition-colors",
            toggle.on ? "bg-primary" : "bg-muted",
          )}
          aria-label={toggle.on ? "Turn harmony off" : "Turn harmony on"}
          role="switch"
          aria-checked={toggle.on}
        >
          <span
            className={cn(
              "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform",
              toggle.on ? "translate-x-4" : "translate-x-0.5",
            )}
          />
        </button>
      ) : (
        <span className="h-2 w-2 rounded-full bg-primary" />
      )}
    </div>
  )
}
