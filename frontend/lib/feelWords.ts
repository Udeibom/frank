/**
 * feelWords: a direction described in plain words, from what Frank knew when he made it.
 * No numbers, no music terms (design-and-ui.md, "No music jargon"); the fingerprint itself is never shown.
 * Returns an empty string when there is nothing honest to say, so the card falls back to when it was made.
 */

import type { MusicalFingerprint } from "@/types/project"

export function plainSound(fp: Partial<MusicalFingerprint>): string {
  const feel: string[] = []

  if (typeof fp.tempo_bpm === "number") {
    feel.push(fp.tempo_bpm < 80 ? "slow" : fp.tempo_bpm <= 110 ? "easy" : "moving")
  }
  if (typeof fp.warmth === "number" && fp.warmth >= 0.6) feel.push("warm")
  if (typeof fp.brightness === "number") {
    if (fp.brightness <= 0.35) feel.push("dark")
    else if (fp.brightness >= 0.65) feel.push("bright")
  }
  if (typeof fp.energy_level === "number") {
    if (fp.energy_level <= 0.35) feel.push("quiet")
    else if (fp.energy_level >= 0.65) feel.push("strong")
  }

  const words = feel.slice(0, 3).join(", ")
  const with_ = (fp.instrumentation_hints ?? []).slice(0, 2).join(" and ")
  if (words && with_) return `${capital(words)}, with ${with_}`
  if (words) return capital(words)
  if (with_) return `With ${with_}`
  return ""
}

function capital(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}
