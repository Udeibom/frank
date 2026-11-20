"use client"

/**
 * VersionChoice: when "give me that version back" could mean two versions, Frank plays both and lets the
 * person pick (spec 08, requirement 5.2). Both play through the shared AudioEngine, switching at the same moment.
 */

import { X } from "lucide-react"
import { PlayButton } from "@/components/audio/PlayButton"
import type { VersionCandidate } from "@/types/api"
import type { Material } from "@/store/audio"

interface VersionChoiceProps {
  candidates: VersionCandidate[]
  onPick: (versionId: string) => void
  onClose: () => void
  material?: Material
}

export function VersionChoice({ candidates, onPick, onClose, material = "music" }: VersionChoiceProps) {
  return (
    <section aria-label="Which version did you mean?" className="rounded-md border border-line bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-base text-ink">Which one did you mean?</p>
        <button onClick={onClose} aria-label="Close" className="rounded-sm p-1 text-ink-3 hover:text-ink">
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <div className="flex flex-col gap-2">
        {candidates.map((c) => (
          <div key={c.id} className="flex items-center gap-3 rounded-md bg-raised px-3 py-2">
            {c.render_url && (
              <PlayButton
                size="row"
                keepPosition
                track={{ id: `choice:${c.id}`, url: c.render_url, label: c.label ?? "Version", material, onSong: true }}
              />
            )}
            <span className="flex-1 truncate text-base text-ink">{c.label ?? "Version"}</span>
            <button onClick={() => onPick(c.id)} className="rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:border-ink-3">
              This one
            </button>
          </div>
        ))}
      </div>
    </section>
  )
}
