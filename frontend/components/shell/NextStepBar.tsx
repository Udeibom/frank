"use client"
/**
 * One line under the Song Strip: what to do next for this song (core-path spec 15, requirement 5.1).
 * It points; it never blocks. In the room where the step happens it says what to press there.
 */
import Link from "next/link"
import { ArrowRight } from "lucide-react"
import { useProjectStore } from "@/store/project"
import { nextStep, roomName, type Room } from "@/lib/nextStep"

export function NextStepBar({ projectId, room }: { projectId: string; room: Room }) {
  const active = useProjectStore((s) => s.activeState)
  const step = nextStep(
    {
      feeling: Boolean(active?.active_fingerprint_id),
      music: Boolean(active?.active_beat_version_id),
      voice: Boolean(active?.active_vocal_id || active?.active_comp_id),
      blend: Boolean(active?.active_mix_id),
    },
    room,
  )
  return (
    <div role="note" aria-label="What to do next" className="flex flex-wrap items-center gap-3 border-b border-line bg-surface px-4 py-3 text-sm sm:px-5 sm:py-3.5">
      <span className="min-w-0 flex-1 text-ink">{step.text}</span>
      {!step.here && (
        <Link
          href={`/${projectId}/${step.room}`}
          className="ml-auto flex min-h-11 shrink-0 items-center gap-1 rounded-md border border-line px-3 py-1.5 text-ink hover:border-frank/50 hover:text-frank transition-colors"
        >
          Go to {roomName(step.room)} <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      )}
    </div>
  )
}
