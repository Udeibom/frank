/**
 * songShape: what the Song Strip draws, worked out from the shared song record (and nothing else).
 * Pure functions, so the rules for "what is lit where" are in one place and can be checked.
 */

import type { SongRecord, StructureFacet } from "@/types/song"

export type LaneState = "in_use" | "tried" | "none"

export interface StripSection {
  key: string
  /** As the user would say it: "Verse", "Chorus". */
  name: string
  /** Relative length (bars when the music exists). */
  weight: number
  /** Whether the user's words cover this section. */
  words: boolean
}

export interface PreviewSection {
  name: string
  weight: number
}

export interface StripModel {
  sections: StripSection[]
  /** True when the sections come from real music (so a playhead across them means something). */
  fromMusic: boolean
  feel: LaneState
  music: LaneState
  voice: LaneState
  /** One line about what is in the song, for the strip and for screen readers. */
  summary: string
  empty: boolean
}

interface BeatSummary {
  label?: string
  sections?: { index?: number; name?: string; bars?: number }[]
}

const HEADING = /^\s*[\[(]?\s*(intro|verse|pre[\s-]?chorus|chorus|hook|refrain|bridge|outro)\b[^\])]*[\])]?\s*:?\s*$/i

/** The kinds of section the person has written under a heading, in order ("verse", "chorus", ...). Words with no headings give []. */
export function lyricHeadings(lyrics: string | null): string[] {
  if (!lyrics) return []
  const found: string[] = []
  for (const line of lyrics.split("\n")) {
    const m = HEADING.exec(line)
    if (m) found.push(m[1].toLowerCase().replace(/[\s-]/g, ""))
  }
  return found
}

function kindOf(name: string): string {
  const n = name.toLowerCase().replace(/[\s-]/g, "")
  for (const k of ["intro", "verse", "prechorus", "chorus", "hook", "refrain", "bridge", "outro"]) {
    if (n.startsWith(k)) return k === "hook" || k === "refrain" ? "chorus" : k
  }
  return n
}

function prettyName(kind: string): string {
  if (kind === "prechorus") return "Pre-chorus"
  return kind.charAt(0).toUpperCase() + kind.slice(1)
}

export function previewSections(record: SongRecord | null): PreviewSection[] {
  const structure = record?.facets?.structure as StructureFacet | null | undefined
  if (structure?.sections?.length) {
    return structure.sections.map((s) => ({ name: prettyName(kindOf(s.name)), weight: 1 }))
  }
  return lyricHeadings(record?.lyrics ?? null).map((h) => ({ name: prettyName(h), weight: 1 }))
}

export function buildStripModel(record: SongRecord | null, directionsTried: boolean): StripModel {
  const beat = (record?.beat ?? null) as BeatSummary | null
  const hasWords = Boolean(record?.lyrics && record.lyrics.trim())
  const hasMusic = Boolean(beat)
  const hasVoice = Boolean(record?.vocal)
  const keptFeeling = Boolean(record?.fingerprint)

  const preview = previewSections(record)
  const headings = preview.map((s) => kindOf(s.name))
  const wordsCover = (name: string) => hasWords && (headings.length === 0 || headings.includes(kindOf(name)))

  let sections: StripSection[] = []
  let fromMusic = false
  if (beat?.sections && beat.sections.length > 0) {
    fromMusic = true
    sections = beat.sections.map((s, i) => ({
      key: `m${s.index ?? i}`,
      name: s.name ?? "",
      weight: Math.max(1, s.bars ?? 1),
      words: wordsCover(s.name ?? ""),
    }))
  } else if (hasWords && preview.length > 0) {
    sections = preview.map((s, i) => ({
      key: `w${i}`,
      name: s.name,
      weight: s.weight,
      words: true,
    }))
  }

  const parts: string[] = []
  if (keptFeeling) parts.push("the feeling is kept")
  if (hasWords) parts.push("your words")
  if (hasMusic) parts.push(beat?.label ?? "the music")
  if (hasVoice) parts.push("your voice")
  else if (hasMusic) parts.push("no voice yet")

  return {
    sections,
    fromMusic,
    feel: keptFeeling ? "in_use" : directionsTried ? "tried" : "none",
    music: hasMusic ? "in_use" : "none",
    voice: hasVoice ? "in_use" : "none",
    summary: parts.length ? capitalise(parts.join(" · ")) : "Nothing in the song yet",
    empty: !hasWords && !hasMusic && !hasVoice && !keptFeeling && !directionsTried,
  }
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

/** The fraction through the whole song at which a section starts (0..1). */
export function sectionStart(sections: StripSection[], index: number): number {
  const total = sections.reduce((a, s) => a + s.weight, 0) || 1
  let before = 0
  for (let i = 0; i < index; i++) before += sections[i].weight
  return before / total
}

/** Which section a position (0..1 through the song) falls in. */
export function sectionAt(sections: StripSection[], fraction: number): number {
  const total = sections.reduce((a, s) => a + s.weight, 0) || 1
  // Compare in whole weights, not summed fractions: summing rounded fractions put the exact start of a section
  // into the section before it (found by the fast-check property "the start of a section is found in it").
  const at = fraction * total + 1e-9 * total
  let acc = 0
  for (let i = 0; i < sections.length; i++) {
    acc += sections[i].weight
    if (at < acc) return i
  }
  return Math.max(0, sections.length - 1)
}
