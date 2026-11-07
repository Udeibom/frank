"use client"

/**
 * BeatTimeline — the visual heart of the Beat Room. Shows the song's sections
 * as warm colored blocks sized by length, highlights the playing section, and
 * lets the user rename sections. Playback position maps across the whole beat.
 */

import { useState } from "react"
import type { BeatSection } from "@/lib/api/beat"
import { cn } from "@/lib/utils"

interface BeatTimelineProps {
  sections: BeatSection[]
  /** 0..1 playback progress across the whole beat */
  progress: number
  onSeek: (fraction: number) => void
  onRenameSection: (sectionIndex: number, label: string) => void
}

// Warm palette — section color by type, consistent with Frank's identity
const SECTION_TINT: Record<string, string> = {
  intro: "bg-amber-900/40 border-amber-700/40",
  verse: "bg-amber-800/40 border-amber-600/40",
  chorus: "bg-amber-500/50 border-amber-400/50",
  bridge: "bg-orange-900/40 border-orange-700/40",
  outro: "bg-amber-950/50 border-amber-800/40",
}

export function BeatTimeline({
  sections,
  progress,
  onSeek,
  onRenameSection,
}: BeatTimelineProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [labelDraft, setLabelDraft] = useState("")

  const totalBars = sections.reduce((sum, s) => sum + s.bars, 0) || 1

  // Which section is currently playing, by progress across total bars
  let acc = 0
  const playingBar = progress * totalBars
  const playingIndex = sections.findIndex((s) => {
    const within = playingBar >= acc && playingBar < acc + s.bars
    acc += s.bars
    return within
  })

  function handleBarClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const fraction = (e.clientX - rect.left) / rect.width
    onSeek(Math.max(0, Math.min(1, fraction)))
  }

  return (
    <div className="w-full">
      {/* The timeline bar */}
      <div
        className="relative flex h-20 w-full gap-1 overflow-hidden rounded-lg"
        onClick={handleBarClick}
      >
        {sections.map((section, i) => (
          <div
            key={`${section.index}-${i}`}
            className={cn(
              "relative flex cursor-pointer flex-col justify-center overflow-hidden rounded-md border px-2 transition-all",
              SECTION_TINT[section.name] ?? "bg-muted border-border",
              playingIndex === i && "ring-2 ring-primary ring-offset-1 ring-offset-background",
            )}
            style={{ flexGrow: section.bars, flexBasis: 0 }}
            onClick={(e) => {
              e.stopPropagation()
              // Seek to this section's start
              let start = 0
              for (let j = 0; j < i; j++) start += sections[j].bars
              onSeek(start / totalBars)
            }}
            onDoubleClick={(e) => {
              e.stopPropagation()
              setEditingIndex(section.index)
              setLabelDraft(section.label)
            }}
          >
            {editingIndex === section.index ? (
              <input
                autoFocus
                value={labelDraft}
                onChange={(e) => setLabelDraft(e.target.value)}
                onClick={(e) => e.stopPropagation()}
                onBlur={() => {
                  onRenameSection(section.index, labelDraft.trim() || section.label)
                  setEditingIndex(null)
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    onRenameSection(section.index, labelDraft.trim() || section.label)
                    setEditingIndex(null)
                  }
                  if (e.key === "Escape") setEditingIndex(null)
                }}
                className="w-full bg-transparent text-xs font-medium text-foreground outline-none"
              />
            ) : (
              <span className="truncate text-xs font-medium text-foreground/90">
                {section.label}
              </span>
            )}
            <span className="truncate text-[10px] text-foreground/50">
              {section.layers.length} layer{section.layers.length === 1 ? "" : "s"}
            </span>
          </div>
        ))}

        {/* Playhead */}
        <div
          className="pointer-events-none absolute top-0 h-full w-0.5 bg-primary"
          style={{ left: `${progress * 100}%` }}
        />
      </div>

      <p className="mt-2 text-center text-[11px] text-muted-foreground/50">
        Click to jump around · double-click a section to rename it
      </p>
    </div>
  )
}
