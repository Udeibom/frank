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
    <div role="note" aria-label="What to do next" className="flex items-center gap-3 border-b border-line bg-surface px-5 py-2 text-sm">
      <span className="text-ink">{step.text}</span>
      {!step.here && (
        <Link
          href={`/${projectId}/${step.room}`}
          className="ml-auto flex shrink-0 items-center gap-1 rounded-md border border-line px-2.5 py-1 text-ink hover:border-ink-3"
        >
          Go to {roomName(step.room)} <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      )}
    </div>
  )
}
