/**
 * Property tests for the Song Strip model and job polling (kiro-craft spec 12, requirement 7.7).
 * The strip is what tells a non-musician where they are in their song, so its rules must hold for any song.
 */
import { describe, expect, it } from "vitest"
import fc from "fast-check"
import { buildStripModel, lyricHeadings, sectionAt, sectionStart, type StripSection } from "@/lib/songShape"
import { pollDelay } from "@/lib/api/jobs"
import { formatTime } from "@/store/audio"
import type { SongRecord } from "@/types/song"

const section = fc.record({
  key: fc.string(),
  name: fc.constantFrom("Intro", "Verse", "Chorus", "Bridge", "Outro"),
  weight: fc.integer({ min: 1, max: 32 }),
  words: fc.boolean(),
})
const sections = fc.array(section, { minLength: 1, maxLength: 16 })

describe("song strip", () => {
  it("every position in the song falls in exactly one real section", () => {
    fc.assert(
      fc.property(sections, fc.double({ min: 0, max: 1, noNaN: true }), (ss: StripSection[], f) => {
        const i = sectionAt(ss, f)
        expect(i).toBeGreaterThanOrEqual(0)
        expect(i).toBeLessThan(ss.length)
        // The section it lands in starts at or before the position.
        expect(sectionStart(ss, i)).toBeLessThanOrEqual(f + 1e-9)
      }),
    )
  })

  it("section starts run from 0, never go backwards, and stay below 1", () => {
    fc.assert(
      fc.property(sections, (ss) => {
        let last = -1
        ss.forEach((_, i) => {
          const s = sectionStart(ss, i)
          expect(s).toBeGreaterThan(last)
          expect(s).toBeLessThan(1)
          last = s
        })
        expect(sectionStart(ss, 0)).toBe(0)
      }),
    )
  })

  it("the start of a section is found in that section (play from here lands where it says)", () => {
    fc.assert(
      fc.property(sections, (ss) => {
        ss.forEach((_, i) => expect(sectionAt(ss, sectionStart(ss, i))).toBe(i))
      }),
    )
  })

  it("a song with music draws one strip section per music section, never losing one", () => {
    const beat = fc.array(fc.record({ name: fc.constantFrom("verse", "chorus", "bridge"), bars: fc.integer({ min: 1, max: 16 }) }), {
      minLength: 1,
      maxLength: 12,
    })
    fc.assert(
      fc.property(beat, fc.option(fc.string(), { nil: null }), (bs, lyrics) => {
        const record = { beat: { sections: bs }, lyrics } as unknown as SongRecord
        const m = buildStripModel(record, false)
        expect(m.fromMusic).toBe(true)
        expect(m.sections.length).toBe(bs.length)
        expect(m.music).toBe("in_use")
        expect(m.empty).toBe(false)
      }),
    )
  })

  it("an empty song is empty and says so in plain words", () => {
    const m = buildStripModel(null, false)
    expect(m.empty).toBe(true)
    expect(m.summary).toBe("Nothing in the song yet")
  })

  it("headings are only ever known section kinds", () => {
    fc.assert(
      fc.property(fc.array(fc.oneof(fc.string(), fc.constantFrom("[Verse]", "Chorus:", "(Bridge)", "pre-chorus")), { maxLength: 30 }), (lines) => {
        for (const h of lyricHeadings(lines.join("\n"))) {
          expect(["intro", "verse", "prechorus", "chorus", "hook", "refrain", "bridge", "outro"]).toContain(h)
        }
      }),
    )
  })
})

describe("waiting and time", () => {
  it("polling never gets faster as the wait goes on", () => {
    fc.assert(
      fc.property(fc.nat(10 * 60_000), fc.nat(10 * 60_000), (a, b) => {
        const [lo, hi] = a <= b ? [a, b] : [b, a]
        expect(pollDelay(hi)).toBeGreaterThanOrEqual(pollDelay(lo))
      }),
    )
  })

  it("time is shown as minutes:seconds with two-digit seconds", () => {
    fc.assert(
      fc.property(fc.double({ min: 0, max: 3600, noNaN: true }), (s) => {
        expect(formatTime(s)).toMatch(/^\d+:[0-5]\d$/)
      }),
    )
  })
})
