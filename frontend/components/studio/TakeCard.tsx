"use client"

/**
 * TakeCard — one recorded take and every version made from it (tuned, lined up, music taken out). The original is
 * always first and always kept. Actions are named in plain words (sing-it spec 06).
 */

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { PitchDisplay } from "@/components/audio/PitchDisplay"
import type { VocalTake } from "@/lib/api/voice"
import { Play, Pause, Check, Sparkles, AlignCenter, Eraser, Wand2, Music2 } from "lucide-react"
import { cn } from "@/lib/utils"

const KIND_WORDS: Record<string, string> = {
  tuned: "tuned",
  lined_up: "lined up with the beat",
  cleaned: "music taken out",
}

export type TakeAction =
  | { kind: "tune"; mode: "light" | "moderate" | "full" }
  | { kind: "line_up" }
  | { kind: "remove_bleed" }
  | { kind: "use_as_melody" }
  | { kind: "harmony"; type: "above" | "below" | "both"; sections: string[] | null }

interface TakeCardProps {
  take: VocalTake
  versions: VocalTake[]
  activeId: string | null
  playingUrl: string | null
  busy: boolean
  picked: boolean
  canUseAsMelody: boolean
  onPlay: (url: string) => void
  onUse: (take: VocalTake) => void
  onPick: (takeId: string) => void
  onAction: (take: VocalTake, action: TakeAction) => void
}

const HARMONY_PLACES: { label: string; sections: string[] | null }[] = [
  { label: "everywhere", sections: null },
  { label: "only the choruses", sections: ["chorus"] },
  { label: "only the verses", sections: ["verse"] },
]

export function TakeCard({ take, versions, activeId, playingUrl, busy, picked, canUseAsMelody, onPlay, onUse, onPick, onAction }: TakeCardProps) {
  const [harmonyType, setHarmonyType] = useState<"above" | "below" | "both">("above")
  const [harmonyPlace, setHarmonyPlace] = useState(0)
  const [showHarmony, setShowHarmony] = useState(false)
  const facts = take.facts ?? {}
  const beatInMic = (facts.bleed ?? 0) > 0.12
  const all = [take, ...versions]
  const target = versions.find((v) => v.id === activeId) ?? take           // actions work on the version in use

  return (
    <div className={cn("rounded-xl border p-4 transition-colors", all.some((v) => v.id === activeId) ? "border-primary/40 bg-primary/5" : "border-border bg-card")}>
      {all.map((v, i) => (
        <div key={v.id} className={cn("flex items-center gap-3", i > 0 && "mt-2 border-t border-border/50 pt-2 pl-6")}>
          <button
            onClick={() => onPlay(v.audio_url)}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary hover:bg-primary/25"
            aria-label={playingUrl === v.audio_url ? `Pause ${v.label ?? "take"}` : `Play ${v.label ?? "take"}`}
          >
            {playingUrl === v.audio_url ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 translate-x-px" />}
          </button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-foreground">{i === 0 ? v.label : KIND_WORDS[v.kind] ?? v.label}</p>
            {i === 0 && (
              <p className="text-[11px] text-muted-foreground">
                {facts.seconds ? `${Math.round(facts.seconds)} seconds` : "listening…"}
                {take.params?.song_time ? " · lined up with the beat" : ""}
              </p>
            )}
          </div>
          {i === 0 && (
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
              <input type="checkbox" checked={picked} onChange={() => onPick(take.id)} className="accent-amber-500" />
              pick for the best-of version
            </label>
          )}
          {v.id === activeId ? (
            <span className="flex items-center gap-1 text-xs text-primary">
              <Check className="h-3.5 w-3.5" /> using
            </span>
          ) : (
            <button onClick={() => onUse(v)} className="text-xs text-muted-foreground hover:text-primary">
              use this
            </button>
          )}
        </div>
      ))}

      <div className="mt-3">
        <PitchDisplay pitchData={take.pitch_data} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label={`What Frank can do with ${take.label ?? "this take"}`}>
        <Button variant="outline" size="sm" className="h-7 text-xs" disabled={busy} onClick={() => onAction(target, { kind: "tune", mode: "light" })}>
          <Sparkles className="h-3 w-3" /> Tune the obvious bits
        </Button>
        <Button variant="outline" size="sm" className="h-7 text-xs" disabled={busy} onClick={() => onAction(target, { kind: "tune", mode: "moderate" })}>
          Tighten it up
        </Button>
        <Button variant="outline" size="sm" className="h-7 text-xs" disabled={busy} onClick={() => onAction(target, { kind: "tune", mode: "full" })}>
          Lock it in
        </Button>
        {Boolean(take.params?.song_time) && (
          <Button variant="outline" size="sm" className="h-7 text-xs" disabled={busy} onClick={() => onAction(target, { kind: "line_up" })}>
            <AlignCenter className="h-3 w-3" /> Line it up with the beat
          </Button>
        )}
        {beatInMic && take.kind !== "cleaned" && (
          <Button variant="outline" size="sm" className="h-7 text-xs" disabled={busy} onClick={() => onAction(target, { kind: "remove_bleed" })}>
            <Eraser className="h-3 w-3" /> Take the music out of my vocal
          </Button>
        )}
        <Button variant="outline" size="sm" className="h-7 text-xs" disabled={busy} onClick={() => setShowHarmony((x) => !x)} aria-expanded={showHarmony}>
          <Wand2 className="h-3 w-3" /> Add a harmony
        </Button>
        {canUseAsMelody && (
          <Button variant="outline" size="sm" className="h-7 text-xs" disabled={busy} onClick={() => onAction(target, { kind: "use_as_melody" })}>
            <Music2 className="h-3 w-3" /> Make this the song&apos;s tune
          </Button>
        )}
      </div>

      {showHarmony && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>A second voice</span>
          <select value={harmonyType} onChange={(e) => setHarmonyType(e.target.value as "above" | "below" | "both")} aria-label="Above or below"
                  className="rounded-md border border-border bg-background px-2 py-1">
            <option value="above">above mine</option>
            <option value="below">below mine</option>
            <option value="both">above and below</option>
          </select>
          <select value={harmonyPlace} onChange={(e) => setHarmonyPlace(Number(e.target.value))} aria-label="Where in the song"
                  className="rounded-md border border-border bg-background px-2 py-1">
            {HARMONY_PLACES.map((p, i) => (
              <option key={p.label} value={i}>{p.label}</option>
            ))}
          </select>
          <Button size="sm" className="h-7 text-xs" disabled={busy}
                  onClick={() => onAction(target, { kind: "harmony", type: harmonyType, sections: HARMONY_PLACES[harmonyPlace].sections })}>
            Make it
          </Button>
        </div>
      )}
    </div>
  )
}
