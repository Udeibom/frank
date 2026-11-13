"use client"

/**
 * "Where your song is": a plain-language view of what Frank knows and what is
 * still missing. It never shows raw fields, and it offers to move into
 * refining only when a first full draft exists (song-record spec 01, req. 5, 7).
 */

import { useEffect } from "react"
import { Check, Circle } from "lucide-react"
import { useProjectStore } from "@/store/project"
import { useSongStore } from "@/store/song"
import type { SongRecord } from "@/types/song"

interface Line {
  label: string
  done: boolean
}

function describe(record: SongRecord): Line[] {
  const hasIntent = Boolean((record.facets.intent as { text?: string } | null)?.text)
  return [
    { label: "What you want it to feel like", done: hasIntent || Boolean(record.facets.feeling) },
    { label: "Your words", done: Boolean(record.lyrics) },
    { label: "Your tune", done: Boolean(record.facets.melody) },
    { label: "The music behind it", done: Boolean(record.beat) },
    { label: "Your voice", done: Boolean(record.vocal) },
  ]
}

/** A first complete draft: music plus a voice or a confirmed tune. */
function hasFirstDraft(record: SongRecord): boolean {
  const melody = record.facets.melody as { confirmed?: boolean } | null | undefined
  return Boolean(record.beat) && (Boolean(record.vocal) || Boolean(melody?.confirmed))
}

export function SongSummary({ projectId }: { projectId: string }) {
  const revision = useProjectStore((s) => s.revision)
  const { record, load, setPhase } = useSongStore()

  // Re-read whenever the shared project state is refreshed (rooms bump `revision`).
  useEffect(() => {
    load(projectId)
  }, [projectId, revision, load])

  if (!record) return null

  const lines = describe(record)
  const draftReady = hasFirstDraft(record)

  return (
    <section aria-label="Where your song is" className="mb-4 px-1">
      <p className="mb-1.5 text-xs font-medium text-muted-foreground">Where your song is</p>
      <ul className="flex flex-col gap-1">
        {lines.map((l) => (
          <li key={l.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {l.done ? (
              <Check aria-hidden="true" className="h-3 w-3 text-primary" />
            ) : (
              <Circle aria-hidden="true" className="h-3 w-3 text-muted-foreground/30" />
            )}
            <span className={l.done ? "text-foreground/80" : undefined}>{l.label}</span>
            <span className="sr-only">{l.done ? ", done" : ", not yet"}</span>
          </li>
        ))}
      </ul>

      {record.phase === "creating" && draftReady && (
        <div className="mt-2 rounded-md bg-primary/10 p-2">
          <p className="text-xs text-foreground/90">
            You have music and a voice or a tune. Want to start polishing it?
          </p>
          <button
            onClick={() => setPhase(projectId, "refining")}
            className="mt-1.5 text-xs font-medium text-primary hover:underline"
          >
            Yes, let&apos;s polish it
          </button>
        </div>
      )}

      {record.phase === "refining" && (
        <p className="mt-2 text-xs text-muted-foreground">
          You&apos;re polishing it now.{" "}
          <button
            onClick={() => setPhase(projectId, "creating")}
            className="text-primary hover:underline"
          >
            Back to adding things
          </button>
        </p>
      )}
    </section>
  )
}
