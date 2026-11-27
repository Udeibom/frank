import { describe, expect, it } from "vitest"
import { addBeatEdit, beatEditWhere, beatOps, isBeatApplyRequest, isBeatCellStaged, isBeatSectionStaged, stagedSectionLabel, type StagedBeatEdit } from "@/lib/beatEdits"
import type { BeatSection } from "@/lib/api/beat"

function section(label: string): BeatSection {
  return { index: 0, name: "chorus", label, bars: 4, energy: 0.6, density: 0.5, layers: ["drums", "keys"] }
}

function edit(id: string, ops: StagedBeatEdit["ops"], where: StagedBeatEdit["where"] = { section: 0 }): StagedBeatEdit {
  return { id, ops, where, words: id }
}

describe("staged beat edits", () => {
  it("keeps edits waiting in order until Frank is told to apply them", () => {
    let edits: StagedBeatEdit[] = []
    edits = addBeatEdit(edits, edit("one", [{ op: "bigger", section: 0 }]))
    edits = addBeatEdit(edits, edit("two", [{ op: "sparser", part: "keys", section: 0 }]))
    expect(edits.map((e) => e.id)).toEqual(["one", "two"])
    expect(beatOps(edits)).toEqual([
      { op: "bigger", section: 0 },
      { op: "sparser", part: "keys", section: 0 },
    ])
  })

  it("never lets more than eight operations wait at once", () => {
    let edits: StagedBeatEdit[] = []
    for (let i = 0; i < 10; i++) edits = addBeatEdit(edits, edit(String(i), [{ op: "bigger", section: i }]))
    expect(beatOps(edits)).toHaveLength(8)
    expect(beatOps(edits)[0]).toEqual({ op: "bigger", section: 2 })
  })

  it("shows the latest staged name for a section", () => {
    const sections = [section("Chorus")]
    let edits: StagedBeatEdit[] = []
    edits = addBeatEdit(edits, edit("one", [{ op: "rename_section", section: 0, label: "Lift" }]))
    edits = addBeatEdit(edits, edit("two", [{ op: "rename_section", section: 0, label: "Final lift" }]))
    expect(stagedSectionLabel(sections, edits, 0)).toBe("Final lift")
    expect(stagedSectionLabel(sections, [], 0)).toBe("Chorus")
  })

  it("marks the exact cell or section that has an edit waiting", () => {
    const edits = [
      edit("one", [{ op: "sparser", part: "keys", section: 1 }]),
      edit("two", [{ op: "bigger", section: 2 }]),
      edit("three", [{ op: "rename_section", section: 3, label: "Ending" }]),
    ]
    expect(isBeatCellStaged(edits, 1, "keys")).toBe(true)
    expect(isBeatCellStaged(edits, 1, "drums")).toBe(false)
    expect(isBeatCellStaged(edits, 2, "drums")).toBe(true)
    expect(isBeatCellStaged(edits, 3, "drums")).toBe(false)
    expect(isBeatSectionStaged(edits, 3)).toBe(true)
  })

  it("uses the section named in an operation when there is one", () => {
    expect(beatEditWhere({ op: "bigger", section: 4 })).toEqual({ section: 4 })
    expect(beatEditWhere({ op: "busier", part: "drums", section: [2, 3] })).toEqual({ section: 2, part: "drums" })
    expect(beatEditWhere({ op: "another_song" })).toEqual({ section: 0 })
  })

  it("only treats a plain go-ahead as permission to apply", () => {
    expect(isBeatApplyRequest("Go ahead.")).toBe(true)
    expect(isBeatApplyRequest("go ahead and implement them")).toBe(true)
    expect(isBeatApplyRequest("apply changes")).toBe(true)
    expect(isBeatApplyRequest("do it")).toBe(true)
    expect(isBeatApplyRequest("yes")).toBe(false)
    expect(isBeatApplyRequest("go ahead and make the chorus fuller")).toBe(false)
    expect(isBeatApplyRequest("make the chorus fuller")).toBe(false)
  })
})
