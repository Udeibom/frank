import type { BeatOperation, BeatSection } from "@/lib/api/beat"

export interface StagedBeatEdit {
  id: string
  ops: BeatOperation[]
  where: { section: number; part?: string }
  words: string
}

const MAX_OPS = 8

export function addBeatEdit(edits: StagedBeatEdit[], edit: StagedBeatEdit): StagedBeatEdit[] {
  const next = [...edits, edit]
  let extra = next.reduce((total, item) => total + item.ops.length, 0) - MAX_OPS
  while (extra > 0 && next.length) {
    const first = next[0]
    if (first.ops.length <= extra) {
      extra -= first.ops.length
      next.shift()
    } else {
      next[0] = { ...first, ops: first.ops.slice(extra) }
      extra = 0
    }
  }
  return next
}

export function beatOps(edits: StagedBeatEdit[]): BeatOperation[] {
  return edits.flatMap((edit) => edit.ops)
}

export function beatEditWhere(op: BeatOperation, fallback = 0): { section: number; part?: string } {
  const raw = op.section
  const section = typeof raw === "number" ? raw : Array.isArray(raw) && typeof raw[0] === "number" ? raw[0] : fallback
  const part = typeof op.part === "string" ? op.part : undefined
  return part ? { section, part } : { section }
}

export function stagedSectionLabel(sections: BeatSection[], edits: StagedBeatEdit[], index: number): string {
  for (let e = edits.length - 1; e >= 0; e--) {
    for (let o = edits[e].ops.length - 1; o >= 0; o--) {
      const op = edits[e].ops[o]
      if (op.op === "rename_section" && Number(op.section) === index && typeof op.label === "string") return op.label
    }
  }
  return sections[index]?.label ?? ""
}

export function isBeatCellStaged(edits: StagedBeatEdit[], section: number, part: string): boolean {
  return edits.some((edit) => edit.ops.some((op) => {
    if (op.op === "rename_section") return false
    if (Number(op.section) !== section) return false
    return typeof op.part !== "string" || op.part === part
  }))
}

export function isBeatSectionStaged(edits: StagedBeatEdit[], section: number): boolean {
  return edits.some((edit) => edit.ops.some((op) => Number(op.section) === section))
}

export function isBeatApplyRequest(message: string): boolean {
  const words = message.trim().toLowerCase().replace(/[.!]+$/, "")
  if (["go ahead", "apply", "apply changes", "do it", "make it so"].includes(words)) return true
  return /^go ahead(?: and)? (?:apply|implement|do it|make it so)(?: (?:the|these|those|my|it|them)(?: changes?)?)?$/.test(words)
}
