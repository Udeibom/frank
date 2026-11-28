"use client"

/**
 * Arrangement: the Music room's stage. The song's sections across, the parts that play down, like a band's
 * running order (Logic's session players each have a part and a style per section; Ableton's arrangement shows
 * sections you can jump to). Every cell is a real decision you can change in plain words; nothing here is a
 * fader or a number. Changes go through the same typed beat operations Frank uses.
 */

import { useState } from "react"
import { Pencil } from "lucide-react"
import { cn } from "@/lib/utils"
import { ChoiceMenu, type Choice } from "@/components/ui/choice-menu"
import { PART_NAMES } from "@/lib/api/finish"
import { isBeatCellStaged, isBeatSectionStaged, stagedSectionLabel, type StagedBeatEdit } from "@/lib/beatEdits"
import type { BeatOperation, BeatSection } from "@/lib/api/beat"

/** The order parts are listed in (backend generation/ops.py PARTS). */
const PART_ORDER = ["drums", "bass", "keys", "melody", "accompaniment", "pad", "strings", "arp"] as const

const PLAYS_PLURAL = new Set(["drums", "keys", "strings"])

interface ArrangementProps {
  sections: BeatSection[]
  /** 0..1 through the beat while it is the thing playing, else null. */
  progress: number | null
  busy: boolean
  /** The cell or section being changed right now, to show where the work is. */
  working: { section: number; part?: string } | null
  onPlayFrom: (sectionPosition: number) => void
  stagedEdits: StagedBeatEdit[]
  onStageEdit: (ops: BeatOperation[], where: { section: number; part?: string }, saying: string) => void
  onStageRename: (sectionIndex: number, label: string, saying: string) => void
}

/** "the first verse", "the chorus": how a person would say which section. */
export function sectionWords(sections: BeatSection[], i: number): string {
  const s = sections[i]
  const same = sections.filter((x) => x.name === s.name)
  const word = (s.label || s.name).toLowerCase()
  if (same.length === 1) return `the ${word}`
  const n = same.indexOf(s)
  return `the ${["first", "second", "third", "fourth", "fifth", "sixth"][Math.min(n, 5)]} ${s.name}`
}

export function Arrangement({ sections, progress, busy, working, onPlayFrom, stagedEdits, onStageEdit, onStageRename }: ArrangementProps) {
  const [renaming, setRenaming] = useState<number | null>(null)
  const [draft, setDraft] = useState("")

  const parts = PART_ORDER.filter((p) => sections.some((s) => s.layers.includes(p)))
  const total = sections.reduce((a, s) => a + s.bars, 0) || 1
  let acc = 0
  const starts = sections.map((s) => {
    const at = acc / total
    acc += s.bars
    return at
  })
  const playingIndex =
    progress === null ? -1 : sections.findIndex((_, i) => progress >= starts[i] && (i === sections.length - 1 || progress < starts[i + 1]))

  function cellChoices(part: string, i: number, plays: boolean): Choice[] {
    const name = PART_NAMES[part] ?? part
    const where = sectionWords(sections, i)
    const verb = PLAYS_PLURAL.has(part) ? "play" : "plays"
    if (!plays) {
      return [
        {
          label: `Add ${name.toLowerCase()} here`,
          onSelect: () => onStageEdit([{ op: "add_part", part, section: i }], { section: i, part }, `Adding ${name.toLowerCase()} to ${where}…`),
        },
      ]
    }
    return [
      {
        label: "Busier",
        hint: "More going on",
        onSelect: () => onStageEdit([{ op: "busier", part, section: i }], { section: i, part }, `Making ${name.toLowerCase()} busier in ${where}…`),
      },
      {
        label: "Simpler",
        hint: "More space around it",
        onSelect: () => onStageEdit([{ op: "sparser", part, section: i }], { section: i, part }, `Making ${name.toLowerCase()} simpler in ${where}…`),
      },
      ...(part === "drums"
        ? [
            {
              label: "Looser",
              hint: "Leans and pushes, like a person playing",
              onSelect: () => onStageEdit([{ op: "looser", section: i }], { section: i, part }, `Loosening the drums in ${where}…`),
            },
            {
              label: "Tighter",
              hint: "Right on the beat",
              onSelect: () => onStageEdit([{ op: "tighter", section: i }], { section: i, part }, `Tightening the drums in ${where}…`),
            },
          ]
        : []),
      {
        label: "Try another idea",
        hint: `A different way it ${verb}`,
        onSelect: () => onStageEdit([{ op: "try_another", part, section: i }], { section: i, part }, `Trying another idea for ${name.toLowerCase()} in ${where}…`),
      },
      {
        label: "Leave it out here",
        onSelect: () => onStageEdit([{ op: "remove_part", part, section: i }], { section: i, part }, `Taking ${name.toLowerCase()} out of ${where}…`),
      },
    ]
  }

  function sectionChoices(i: number): Choice[] {
    const where = sectionWords(sections, i)
    return [
      { label: "Play from here", onSelect: () => onPlayFrom(i) },
      { label: "Fuller", hint: "Hits harder", onSelect: () => onStageEdit([{ op: "bigger", section: i }], { section: i }, `Making ${where} fuller…`) },
      { label: "Calmer", hint: "Sits back", onSelect: () => onStageEdit([{ op: "smaller", section: i }], { section: i }, `Calming ${where} down…`) },
      { label: "Add a drum fill at the end", onSelect: () => onStageEdit([{ op: "add_fill", section: i }], { section: i }, `Adding a fill at the end of ${where}…`) },
      {
        label: "Rename",
        onSelect: () => {
          setDraft(stagedSectionLabel(sections, stagedEdits, i))
          setRenaming(i)
        },
      },
    ]
  }

  const columns = sections.map((s) => `minmax(80px, ${s.bars}fr)`).join(" ")

  return (
    <div role="group" aria-label="The music, section by section" aria-busy={busy} className="relative min-w-[640px]">
      <div
        className="grid gap-x-1 gap-y-1.5"
        style={{ gridTemplateColumns: `112px ${columns}`, gridTemplateRows: `auto repeat(${parts.length}, 36px)` }}
      >
        {/* Section names */}
        <div />
        {sections.map((s, i) => {
          const label = stagedSectionLabel(sections, stagedEdits, i)
          const staged = isBeatSectionStaged(stagedEdits, i)
          return (
            <div key={`h${s.index}-${i}`} className={cn("min-w-0 rounded-[2px]", i === playingIndex && "bg-raised", staged && "ring-1 ring-frank/60")}>
              {renaming === i ? (
                <input
                  autoFocus
                  value={draft}
                  maxLength={40}
                  aria-label={`New name for ${sectionWords(sections, i)}`}
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={() => {
                    const name = draft.trim() || label
                    onStageRename(s.index, name, `Rename ${sectionWords(sections, i)} to “${name}”`)
                    setRenaming(null)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") e.currentTarget.blur()
                    if (e.key === "Escape") setRenaming(null)
                  }}
                  className="min-h-11 w-full rounded-sm bg-raised px-2 py-1.5 text-sm text-ink"
                />
              ) : (
                <ChoiceMenu
                  label={label}
                  choices={sectionChoices(i)}
                  trigger={({ toggle, ref, ...aria }) => (
                    <button
                      ref={ref}
                      {...aria}
                      onClick={toggle}
                      disabled={busy}
                      aria-label={`${label}: choices`}
                      className="group relative flex min-h-11 w-full min-w-0 items-center rounded-sm px-2 py-1.5 text-left text-sm font-medium text-ink hover:bg-raised disabled:cursor-default"
                    >
                      <span className="truncate">{label}</span>
                      <Pencil aria-hidden="true" className="absolute right-1.5 h-3 w-3 text-ink-3 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100" />
                    </button>
                  )}
                />
              )}
            </div>
          )
        })}

        {/* One row per part */}
        {parts.map((part) => (
          <PartRow
            key={part}
            part={part}
            sections={sections}
            playingIndex={playingIndex}
            busy={busy}
            working={working}
            stagedEdits={stagedEdits}
            choices={cellChoices}
          />
        ))}

      </div>

      {/* The playhead, on its own overlay grid with the same columns, drawn inside the section that is playing,
          so it is right however wide each column is and never disturbs where the cells are placed. */}
      {progress !== null && playingIndex >= 0 && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 grid gap-x-1"
          style={{ gridTemplateColumns: `112px ${columns}` }}
        >
          <div className="relative" style={{ gridColumn: playingIndex + 2 }}>
            <span
              className="absolute -bottom-1 -top-1 w-0.5 bg-frank"
              style={{ left: `${Math.min(100, Math.max(0, ((progress - starts[playingIndex]) / (sections[playingIndex].bars / total)) * 100))}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

function PartRow({
  part,
  sections,
  playingIndex,
  busy,
  working,
  stagedEdits,
  choices,
}: {
  part: string
  sections: BeatSection[]
  playingIndex: number
  busy: boolean
  working: { section: number; part?: string } | null
  stagedEdits: StagedBeatEdit[]
  choices: (part: string, i: number, plays: boolean) => Choice[]
}) {
  const name = PART_NAMES[part] ?? part
  return (
    <>
      <div className="flex items-center pr-2 text-sm text-ink-2">{name}</div>
      {sections.map((s, i) => {
        const plays = s.layers.includes(part)
        const here = working && working.section === i && (!working.part || working.part === part)
        const staged = isBeatCellStaged(stagedEdits, i, part)
        return (
          <ChoiceMenu
            key={`${part}-${s.index}-${i}`}
            label={`${name} in ${sectionWords(sections, i)}`}
            choices={choices(part, i, plays)}
            trigger={({ toggle, ref, ...aria }) => (
              <button
                ref={ref}
                {...aria}
                onClick={toggle}
                disabled={busy}
                aria-label={`${name} in ${sectionWords(sections, i)}: ${plays ? "plays" : "doesn't play"}${staged ? ", change waiting" : ""}. Choices`}
                className={cn(
                  "h-9 w-full rounded-[2px] transition-colors disabled:cursor-default",
                  plays ? "bg-music/70 hover:bg-music" : "border border-dashed border-ink-3/60 hover:border-ink-2",
                  i === playingIndex && plays && "bg-music",
                  here && "sweep",
                  staged && "ring-1 ring-frank/70",
                )}
              />
            )}
          />
        )
      })}
    </>
  )
}
