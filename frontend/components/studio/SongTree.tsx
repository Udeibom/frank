"use client"

/**
 * The song's family tree (frankenstein spec 14, requirement 8.2), drawn with React Flow: each version of the
 * feeling, the tune or what the song is, under what it came from. Nothing is ever lost; any version can come back.
 */

import { useEffect, useMemo, useState } from "react"
import { ReactFlow, Background, type Edge, type Node } from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { listFacetVersions, restoreFacetVersion } from "@/lib/api/song"
import { layoutTree } from "@/lib/songTree"
import type { SongFacetName, SongFacetVersion } from "@/types/song"

const FACETS: { facet: SongFacetName; label: string }[] = [
  { facet: "feeling", label: "The feeling" },
  { facet: "melody", label: "Your tune" },
  { facet: "intent", label: "What the song is" },
  { facet: "references", label: "Music you pointed at" },
]

const OPERATION_WORDS: Record<string, string> = {
  read_description: "From what you described",
  read_voice_memo: "From what you said",
  read_picture: "From your picture",
  read_moment: "From your moment",
  loved_qualities: "What you love in a song",
  hum: "From your hum",
  restore: "Brought back",
}

function describe(v: SongFacetVersion): string {
  if (v.label) return v.label
  const op = OPERATION_WORDS[v.operation] ?? v.operation.replace(/_/g, " ")
  return op.charAt(0).toUpperCase() + op.slice(1)
}

export function SongTree({ projectId }: { projectId: string }) {
  const [facet, setFacet] = useState<SongFacetName>("feeling")
  const [versions, setVersions] = useState<SongFacetVersion[] | null>(null)
  const [picked, setPicked] = useState<SongFacetVersion | null>(null)
  const [said, setSaid] = useState<string | null>(null)

  useEffect(() => {
    setVersions(null)
    setPicked(null)
    listFacetVersions(projectId, facet).then(setVersions).catch(() => setVersions([]))
  }, [projectId, facet])

  const { nodes, edges } = useMemo(() => {
    const vs = versions ?? []
    const placed = new Map(layoutTree(vs).map((p) => [p.id, p]))
    const nodes: Node[] = vs.map((v) => {
      const p = placed.get(v.id)!
      return {
        id: v.id,
        position: { x: p.column * 200, y: p.depth * 90 },
        data: { label: describe(v) },
        style: {
          background: "rgb(var(--surface))",
          color: "rgb(var(--ink))",
          border: `1px solid ${v.is_active ? "rgb(var(--frank))" : "rgb(var(--line))"}`,
          borderRadius: 8,
          fontSize: 12,
          width: 170,
        },
        ariaLabel: `${describe(v)}${v.is_active ? ", in the song now" : ""}`,
      }
    })
    const edges: Edge[] = vs
      .filter((v) => v.parent_id && placed.has(v.parent_id))
      .map((v) => ({ id: `${v.parent_id}-${v.id}`, source: v.parent_id!, target: v.id, style: { stroke: "rgb(var(--ink-3))" } }))
    return { nodes, edges }
  }, [versions])

  return (
    <section aria-labelledby="tree-heading" className="mt-8 flex flex-col gap-3">
      <h2 id="tree-heading" className="text-xs font-semibold uppercase tracking-[0.06em] text-ink-3">How the song grew</h2>
      <div role="tablist" aria-label="Which part of the song" className="flex flex-wrap gap-2">
        {FACETS.map((f) => (
          <button key={f.facet} role="tab" aria-selected={facet === f.facet} onClick={() => setFacet(f.facet)}
            className={facet === f.facet ? "rounded-full border border-ink-3 px-3 py-1 text-sm text-ink" : "rounded-full border border-line px-3 py-1 text-sm text-ink-2 hover:text-ink"}>
            {f.label}
          </button>
        ))}
      </div>
      {versions === null ? (
        <p className="text-sm text-ink-3">Gathering the versions…</p>
      ) : versions.length === 0 ? (
        <p className="text-sm text-ink-3">Nothing here yet. Every version will appear as the song grows.</p>
      ) : (
        <div className="h-[340px] w-full rounded-md border border-line bg-ground">
          <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false} proOptions={{ hideAttribution: true }}
            onNodeClick={(_, n) => setPicked(versions.find((v) => v.id === n.id) ?? null)}>
            <Background color="rgb(var(--line))" gap={24} />
          </ReactFlow>
        </div>
      )}
      {picked && (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-ink">{describe(picked)}</span>
          {picked.is_active ? (
            <span className="text-ink-3">This is in the song now.</span>
          ) : (
            <button
              onClick={() =>
                restoreFacetVersion(projectId, facet, picked.id)
                  .then(() => listFacetVersions(projectId, facet).then(setVersions))
                  .then(() => setSaid("Brought back. Everything after it is still kept."))
                  .catch(() => setSaid("I couldn't bring that one back just now."))
              }
              className="rounded-md border border-line px-3 py-1 text-ink hover:border-ink-3"
            >
              Bring this one back
            </button>
          )}
          {said && <span className="text-ink-2" role="status">{said}</span>}
        </div>
      )}
    </section>
  )
}
