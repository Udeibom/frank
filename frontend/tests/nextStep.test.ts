/**
 * Core path (spec 15, requirement 5.1): every room shows exactly one next step, and it follows the song.
 */
import { describe, expect, it } from "vitest"
import fc from "fast-check"
import { nextStep, type Room } from "@/lib/nextStep"

const rooms: Room[] = ["idea", "feel", "beat", "voice", "mix", "export", "yours"]
const has = fc.record({ feeling: fc.boolean(), music: fc.boolean(), voice: fc.boolean(), blend: fc.boolean() })

describe("next step", () => {
  it("is one plain sentence, the same step from every room", () => {
    fc.assert(
      fc.property(has, (h) => {
        const steps = rooms.map((r) => nextStep(h, r))
        expect(new Set(steps.map((s) => s.room)).size).toBe(1)
        for (const s of steps) {
          expect(s.text.length).toBeGreaterThan(10)
          expect(s.text).not.toMatch(/\b(bpm|tempo|stem|mix ?down|take)\b/i)
        }
      }),
    )
  })

  it("says what to press when you are already in the room where it happens", () => {
    fc.assert(fc.property(has, (h) => {
      const s = nextStep(h, nextStep(h, "idea").room)
      expect(s.here).toBe(true)
    }))
  })

  it("walks the founder's path: feeling, music, voice, blend, finish", () => {
    expect(nextStep({ feeling: false, music: false, voice: false, blend: false }, "idea").room).toBe("feel")
    expect(nextStep({ feeling: true, music: false, voice: false, blend: false }, "feel").room).toBe("beat")
    expect(nextStep({ feeling: true, music: true, voice: false, blend: false }, "beat").room).toBe("voice")
    expect(nextStep({ feeling: true, music: true, voice: true, blend: false }, "voice").room).toBe("mix")
    expect(nextStep({ feeling: true, music: true, voice: true, blend: true }, "mix").room).toBe("export")
  })
})
