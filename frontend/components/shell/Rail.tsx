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
  activeText: string
}

const ROOMS: Room[] = [
  { slug: "idea",   name: "Words",   icon: PenLine,           bar: "bg-words",  activeText: "text-words"  },
  { slug: "feel",   name: "Feeling", icon: Sparkles,          bar: "bg-feel",   activeText: "text-feel"   },
  { slug: "beat",   name: "Music",   icon: Drum,              bar: "bg-music",  activeText: "text-music"  },
  { slug: "voice",  name: "Voice",   icon: Mic2,              bar: "bg-voice",  activeText: "text-voice"  },
  { slug: "mix",    name: "Blend",   icon: SlidersHorizontal, bar: "bg-ink-2",  activeText: "text-ink"    },
  { slug: "export", name: "Finish",  icon: Download,          bar: "bg-ink-2",  activeText: "text-ink"    },
]

function RoomLink({ room, href, active, mobile }: { room: Room; href: string; active: boolean; mobile: boolean }) {
  const { name, icon: Icon, bar, activeText } = room
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        mobile
          ? "relative flex min-h-[56px] w-full flex-col items-center justify-center gap-1 rounded-lg px-0.5 text-[10px] font-medium uppercase tracking-[0.03em] transition-colors"
          : "relative flex flex-col items-center gap-1.5 rounded-lg px-1 py-3 text-[10px] font-medium uppercase tracking-[0.04em] transition-all duration-150",
        active ? cn("bg-raised", activeText) : "text-ink-3 hover:bg-raised/60 hover:text-ink-2",
      )}
    >
      {active && (
        <span
          aria-hidden="true"
          className={cn(
            mobile
              ? cn("absolute left-1/2 top-1 h-[3px] w-8 -translate-x-1/2 rounded-full", bar)
              : cn("absolute bottom-3 left-0 top-3 w-[3px] rounded-r-full", bar),
          )}
        />
      )}
      <Icon className={cn("h-5 w-5 transition-transform duration-150", active && "scale-110")} aria-hidden="true" />
      <span className="leading-none">{name}</span>
    </Link>
  )
}

export function Rail({ projectId, onStart }: { projectId: string; onStart: () => void }) {
  const pathname = usePathname()
  return (
    <>
      <nav aria-label="Rooms" className="fixed inset-x-0 bottom-0 z-30 safe-bottom md:hidden">
        <ul className="flex h-16 items-stretch border-t border-line bg-ground px-1">
          {ROOMS.map((room) => (
            <li key={room.slug} className="flex min-w-0 flex-1">
              <RoomLink
                room={room}
                href={`/${projectId}/${room.slug}`}
                active={pathname.startsWith(`/${projectId}/${room.slug}`)}
                mobile
              />
            </li>
          ))}
        </ul>
      </nav>
      <nav aria-label="Rooms" className="hidden w-20 shrink-0 flex-col border-r border-line bg-ground py-2 md:flex">
        <div className="mb-2 flex items-center justify-center py-3">
          <span
            className="font-written italic text-xl leading-none select-none"
            style={{ color: "rgb(var(--frank))" }}
            aria-label="Frank"
          >
            f
          </span>
        </div>
        <ul className="flex flex-col gap-0.5 px-1">
          {ROOMS.map((room) => (
            <li key={room.slug}>
              <RoomLink
                room={room}
                href={`/${projectId}/${room.slug}`}
                active={pathname.startsWith(`/${projectId}/${room.slug}`)}
                mobile={false}
              />
            </li>
          ))}
        </ul>
        <div className="flex-1" />
        <div className="flex flex-col items-center gap-1 px-1 pb-2">
          <YouMenu projectId={projectId} onStart={onStart} />
        </div>
      </nav>
    </>
  )
}
