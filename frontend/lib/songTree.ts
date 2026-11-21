/**
 * The song's family tree (frankenstein spec 14, requirement 8.2): every version of a part of the song, placed so
 * each change sits under what it came from and side branches sit beside each other. Pure, so it can be checked.
 */

export interface TreeVersion {
  id: string
  parent_id: string | null
}

export interface Placed {
  id: string
  depth: number
  column: number
}

/**
 * Depth = steps from the first version; column = left-to-right slot (a parent sits over its first child).
 * Versions whose parent is unknown start their own root. Cycles (never expected) are cut.
 */
export function layoutTree(versions: TreeVersion[]): Placed[] {
  const byId = new Map(versions.map((v) => [v.id, v]))
  const children = new Map<string, string[]>()
  const roots: string[] = []
  for (const v of versions) {
    if (v.parent_id && byId.has(v.parent_id) && v.parent_id !== v.id) {
      children.set(v.parent_id, [...(children.get(v.parent_id) ?? []), v.id])
    } else {
      roots.push(v.id)
    }
  }
  const out = new Map<string, Placed>()
  let nextColumn = 0
  const visit = (id: string, depth: number, seen: Set<string>): number => {
    if (seen.has(id) || out.has(id)) return out.get(id)?.column ?? nextColumn
    seen.add(id)
    const kids = children.get(id) ?? []
    let column: number
    if (kids.length === 0) {
      column = nextColumn++
    } else {
      const cols = kids.map((k) => visit(k, depth + 1, seen))
      column = Math.min(...cols)
    }
    out.set(id, { id, depth, column })
    return column
  }
  for (const r of roots) visit(r, 0, new Set())
  // Anything left (only possible with a cycle) becomes its own root.
  for (const v of versions) if (!out.has(v.id)) visit(v.id, 0, new Set())
  return versions.map((v) => out.get(v.id)!)
}
