"use client"

/**
 * Rail: the six rooms, always reachable, by plain names. It carries no status marks: the Song Strip owns
 * "what is in the song". Route slugs keep their original names so links and saved state do not break.
 */

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Download, Drum, Mic2, PenLine, SlidersHorizontal, Sparkles, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { YouMenu } from "@/components/shell/YouMenu"

interface Room {
  slug: string
  name: string
  icon: LucideIcon
  /** The accent bar colour: the material the room works on, or plain ink for rooms about the whole song. */
  bar: string
}

const ROOMS: Room[] = [
  { slug: "idea", name: "Words", icon: PenLine, bar: "bg-words" },
  { slug: "feel", name: "Feeling", icon: Sparkles, bar: "bg-feel" },
  { slug: "beat", name: "Music", icon: Drum, bar: "bg-music" },
  { slug: "voice", name: "Voice", icon: Mic2, bar: "bg-voice" },
  { slug: "mix", name: "Blend", icon: SlidersHorizontal, bar: "bg-ink-2" },
  { slug: "export", name: "Finish", icon: Download, bar: "bg-ink-2" },
]

export function Rail({ projectId, onStart }: { projectId: string; onStart: () => void }) {
  const pathname = usePathname()
  return (
    <nav aria-label="Rooms" className="flex w-[76px] shrink-0 flex-col border-r border-line bg-ground py-3">
      <ul className="flex flex-col gap-0.5">
        {ROOMS.map(({ slug, name, icon: Icon, bar }) => {
          const active = pathname.startsWith(`/${projectId}/${slug}`)
          return (
            <li key={slug}>
              <Link
                href={`/${projectId}/${slug}`}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex flex-col items-center gap-1 py-2.5 text-xs transition-colors",
                  active ? "bg-surface text-ink" : "text-ink-2 hover:bg-surface hover:text-ink",
                )}
              >
                {active && <span aria-hidden="true" className={cn("absolute bottom-2 left-0 top-2 w-[3px] rounded-r-sm", bar)} />}
                <Icon className="h-5 w-5" aria-hidden="true" />
                {name}
              </Link>
            </li>
          )
        })}
      </ul>
      <div className="flex-1" />
      <YouMenu projectId={projectId} onStart={onStart} />
    </nav>
  )
}
