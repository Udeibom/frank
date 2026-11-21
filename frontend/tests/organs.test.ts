/** Property tests for the frontend pieces of frankenstein spec 14 (version tree, conducting, lyric lines). */
import { describe, expect, it } from "vitest"
import fc from "fast-check"
import { layoutTree, type TreeVersion } from "@/lib/songTree"
import { handToLevel } from "@/components/studio/BlendOrgans"
import { matchLines } from "@/components/studio/LyricsEditor"
import type { LyricLineSound } from "@/types/api"

/** Random version histories: each version's parent is an earlier version (or none). */
const histories = fc.array(fc.option(fc.nat(), { nil: null }), { minLength: 1, maxLength: 40 }).map((parents) =>
  parents.map((p, i): TreeVersion => ({ id: `v${i}`, parent_id: i === 0 || p === null ? null : `v${p % i}` })),
)

describe("song family tree", () => {
  it("places every version exactly once, children below their parent", () => {
    fc.assert(
      fc.property(histories, (vs) => {
        const placed = layoutTree(vs)
        expect(placed.map((p) => p.id)).toEqual(vs.map((v) => v.id))
        const at = new Map(placed.map((p) => [p.id, p]))
        for (const v of vs) if (v.parent_id) expect(at.get(v.id)!.depth).toBe(at.get(v.parent_id)!.depth + 1)
      }),
    )
  })

  it("never puts two versions on the same spot", () => {
    fc.assert(
      fc.property(histories, (vs) => {
        const spots = layoutTree(vs).map((p) => `${p.depth}:${p.column}`)
        expect(new Set(spots).size).toBe(spots.length)
      }),
    )
  })

  it("survives a broken history (a cycle or a missing parent)", () => {
    const placed = layoutTree([{ id: "a", parent_id: "b" }, { id: "b", parent_id: "a" }, { id: "c", parent_id: "gone" }])
    expect(placed).toHaveLength(3)
  })
})

describe("conducting", () => {
  it("a higher hand is never softer, and the change stays within nine steps", () => {
    fc.assert(
      fc.property(fc.double({ min: 0, max: 1, noNaN: true }), fc.double({ min: 0, max: 1, noNaN: true }), (a, b) => {
        const [high, low] = a <= b ? [a, b] : [b, a]                 // smaller y is higher in the picture
        expect(handToLevel(high)).toBeGreaterThanOrEqual(handToLevel(low))
        expect(Math.abs(handToLevel(a))).toBeLessThanOrEqual(9)
      }),
    )
  })
})

describe("rhythm marks", () => {
  it("only lines that were analysed get marks, and headings and blank lines never do", () => {
    const lines = fc.array(fc.oneof(fc.constantFrom("", "Chorus", "[Verse 2]"), fc.string({ minLength: 1, maxLength: 20 })), { maxLength: 20 })
    fc.assert(
      fc.property(lines, (paras) => {
        const analysed: LyricLineSound[] = paras
          .filter((t) => t.trim() && !/^\s*[[(]?\s*(intro|verse|pre-?chorus|chorus|hook|refrain|bridge|outro)\b[^\])]*[\])]?\s*:?\s*$/i.test(t))
          .map((t) => ({ text: t, syllables: 3, rhyme_group: null, guessed: false, words: [] }))
        const matched = matchLines(paras, analysed)
        expect(matched).toHaveLength(paras.length)
        paras.forEach((t, i) => {
          if (!t.trim() || /^(chorus|\[verse 2\])$/i.test(t.trim())) expect(matched[i]).toBeNull()
          if (matched[i]) expect(matched[i]!.text.trim()).toBe(t.trim())
        })
      }),
    )
  })
})
