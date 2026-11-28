"use client"

/**
 * TakeCard: one recorded take and every version made from it (tuned, lined up, music taken out). The original is
 * always first and always kept. What Frank can do with a take is one plain menu ("Make it sound…") rather than a
 * row of seven buttons; the harmony asks its two questions only when chosen. Plays through the shared AudioEngine.
 */

import { recordingName } from "@/lib/recordingName"
import { useState } from "react"
import { Check, ChevronDown } from "lucide-react"
import { PitchDisplay } from "@/components/audio/PitchDisplay"
import { Waveform, type WaveRegion } from "@/components/audio/Waveform"
import { PlayButton } from "@/components/audio/PlayButton"
import { ChoiceMenu, type Choice } from "@/components/ui/choice-menu"
import type { VocalTake } from "@/lib/api/voice"
import type { Track } from "@/store/audio"
import { cn } from "@/lib/utils"

const KIND_WORDS: Record<string, string> = {
  tuned: "Tuned",
  lined_up: "Lined up with the music",
  cleaned: "Music taken out",
  quiet: "Background noise taken out",
  instrument: "Played as an instrument",
}

export const INSTRUMENTS: { id: string; label: string }[] = [
  { id: "violin", label: "a violin" },
  { id: "flute", label: "a flute" },
  { id: "flute2", label: "a soft flute" },
  { id: "trumpet", label: "a trumpet" },
  { id: "tenor_saxophone", label: "a saxophone" },
]

export type TakeAction =
  | { kind: "tune"; mode: "light" | "moderate" | "full" }
  | { kind: "line_up" }
  | { kind: "remove_bleed" }
  | { kind: "use_as_melody" }
  | { kind: "quiet" }
  | { kind: "instrument"; instrument: string }
  | { kind: "harmony"; type: "above" | "below" | "both"; sections: string[] | null }

interface TakeCardProps {
  projectId: string
  take: VocalTake
  versions: VocalTake[]
  activeId: string | null
  busy: boolean
  picked: boolean
  canUseAsMelody: boolean
  /** How many recordings the song has: a best-of version needs at least two. */
  recordings: number
  onUse: (take: VocalTake) => void
  onPick: (takeId: string) => void
  onAction: (take: VocalTake, action: TakeAction) => void
}

const HARMONY_PLACES: { label: string; sections: string[] | null }[] = [
  { label: "everywhere", sections: null },
  { label: "only the choruses", sections: ["chorus"] },
  { label: "only the verses", sections: ["verse"] },
]

/** The lines of the person's words, where Frank heard them in this take (frankenstein spec 14, 4.4). */
export function lineRegions(v: VocalTake): WaveRegion[] {
  return (v.words?.lines ?? [])
    .filter((l): l is typeof l & { start: number; end: number } => l.start !== null && l.end !== null)
    .map((l) => ({ start: l.start, end: l.end, label: l.text }))
}

export function takeTrack(v: VocalTake, name: string): Track {
  return { id: `take:${v.id}`, url: v.audio_url, label: name, material: "voice" }
}

export function TakeCard({ projectId, take, versions, activeId, busy, picked, canUseAsMelody, recordings, onUse, onPick, onAction }: TakeCardProps) {
  const [harmonyType, setHarmonyType] = useState<"above" | "below" | "both">("above")
  const [harmonyPlace, setHarmonyPlace] = useState(0)
  const [showHarmony, setShowHarmony] = useState(false)
  const facts = take.facts ?? {}
  const beatInMic = (facts.bleed ?? 0) > 0.12
  const all = [take, ...versions]
  const target = versions.find((v) => v.id === activeId) ?? take // actions work on the version in use
  const inSong = all.some((v) => v.id === activeId)
  const takeName = recordingName(take.label)

  const choices: Choice[] = [
    { label: "Fix the obvious notes", hint: "Only the ones that are well off", onSelect: () => onAction(target, { kind: "tune", mode: "light" }) },
    { label: "Tighten it up", hint: "Nudge every note a little closer", onSelect: () => onAction(target, { kind: "tune", mode: "moderate" }) },
    { label: "Lock it in", hint: "Right on every note: the tuned sound", onSelect: () => onAction(target, { kind: "tune", mode: "full" }) },
    ...(take.params?.song_time
      ? [{ label: "Line it up with the music", onSelect: () => onAction(target, { kind: "line_up" }) }]
      : []),
    ...(beatInMic && take.kind !== "cleaned"
      ? [{ label: "Take the music out of my voice", hint: "The music got into the mic", onSelect: () => onAction(target, { kind: "remove_bleed" }) }]
      : []),
    ...(take.kind !== "quiet"
      ? [{ label: "Take the background noise out", hint: "Fans, hiss, the room", onSelect: () => onAction(target, { kind: "quiet" }) }]
      : []),
    ...INSTRUMENTS.map((ins) => ({
      label: `Play it as ${ins.label}`,
      hint: "Keeps the way you sang it",
      onSelect: () => onAction(target, { kind: "instrument", instrument: ins.id }),
    })),
    { label: "Add a second voice…", hint: "A harmony made from this recording", onSelect: () => setShowHarmony(true) },
    ...(canUseAsMelody ? [{ label: "Make this the song's tune", onSelect: () => onAction(target, { kind: "use_as_melody" }) }] : []),
  ]

  return (
    <article
      aria-label={takeName}
      className={cn("rounded-md border bg-surface p-4", inSong ? "border-voice/70" : "border-transparent")}
    >
      <ul className="flex flex-col">
        {all.map((v, i) => {
          const name = i === 0 ? takeName : KIND_WORDS[v.kind] ?? v.label ?? "A version"
          return (
            <li key={v.id} className={cn("flex items-center gap-3", i > 0 && "mt-2 border-t border-line pl-6 pt-2")}>
              <PlayButton track={takeTrack(v, i === 0 ? takeName : `${takeName}: ${name.toLowerCase()}`)} size={i === 0 ? "card" : "row"} />
              <div className="min-w-0 flex-1">
                <p className={cn("truncate", i === 0 ? "font-written text-xl text-ink" : "text-base text-ink")}>{name}</p>
                {i === 0 && (
                  <p className="text-sm text-ink-2">
                    {facts.seconds ? `${Math.round(facts.seconds)} seconds` : "Frank is checking this recording…"}
                    {take.params?.song_time ? " · sung with the music" : ""}
                  </p>
                )}
              </div>
              {v.id === activeId ? (
                <span className="flex shrink-0 items-center gap-1 text-sm text-voice">
                  <Check className="h-3.5 w-3.5" aria-hidden="true" /> In the song
                </span>
              ) : (
                <button onClick={() => onUse(v)} className="shrink-0 rounded-md border border-line px-2.5 py-1 text-sm text-ink hover:border-ink-3">
                  Use this
                </button>
              )}
            </li>
          )
        })}
      </ul>

      <div className="mt-3">
        <Waveform projectId={projectId} track={takeTrack(target, takeName)} regions={lineRegions(target === take ? take : target)} />
      </div>
      {lineRegions(take).length > 0 && (
        <p className="mt-1 text-xs text-ink-3">Each line you sang is marked. Click one to hear just that line.</p>
      )}

      <div className="mt-3">
        <PitchDisplay pitchData={take.pitch_data} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-4">
        <ChoiceMenu
          label={`What Frank can do with ${takeName}`}
          choices={choices.map((c) => ({ ...c, disabled: busy }))}
          trigger={({ toggle, ref, ...aria }) => (
            <button
              ref={ref}
              {...aria}
              onClick={toggle}
              disabled={busy}
              className="flex min-h-11 items-center gap-1.5 rounded-md border border-line bg-raised px-3 py-1.5 text-base text-ink hover:border-ink-3 disabled:text-ink-3"
            >
              Change this recording… <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        />
        {recordings >= 2 ? (
          <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-2">
            <input type="checkbox" checked={picked} onChange={() => onPick(take.id)} className="h-4 w-4 accent-[rgb(var(--voice))]" />
            Pick for a best-of version
          </label>
        ) : null}
      </div>
      <p className="mt-1.5 text-xs text-ink-3">
        Tune it, clean it up, add a second voice or play it on an instrument. Your original is always kept.
        {recordings >= 2
          ? " Pick two or more recordings and Frank joins the best line from each into one version."
          : " Record it again any time: with two recordings, Frank can join the best line from each."}
      </p>

      {showHarmony && (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md bg-raised p-3 text-sm text-ink-2" role="group" aria-label="A second voice">
          <span>A second voice</span>
          <select
            value={harmonyType}
            onChange={(e) => setHarmonyType(e.target.value as "above" | "below" | "both")}
            aria-label="Above or below"
            className="min-h-11 rounded-md border border-line bg-surface px-2 py-1 text-ink"
          >
            <option value="above">above mine</option>
            <option value="below">below mine</option>
            <option value="both">above and below</option>
          </select>
          <select
            value={harmonyPlace}
            onChange={(e) => setHarmonyPlace(Number(e.target.value))}
            aria-label="Where in the song"
            className="min-h-11 rounded-md border border-line bg-surface px-2 py-1 text-ink"
          >
            {HARMONY_PLACES.map((p, i) => (
              <option key={p.label} value={i}>
                {p.label}
              </option>
            ))}
          </select>
          <button
            disabled={busy}
            onClick={() => {
              setShowHarmony(false)
              onAction(target, { kind: "harmony", type: harmonyType, sections: HARMONY_PLACES[harmonyPlace].sections })
            }}
            className="flex min-h-11 items-center rounded-md border border-line bg-surface px-3 py-1 text-ink hover:border-ink-3 disabled:text-ink-3"
          >
            Make it
          </button>
          <button onClick={() => setShowHarmony(false)} className="flex min-h-11 items-center text-ink-2 hover:text-ink">
            Not now
          </button>
        </div>
      )}
    </article>
  )
}
