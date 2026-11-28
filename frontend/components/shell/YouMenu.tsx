"use client"

/**
 * YouMenu: everything that is about the person rather than the song, in one place at the foot of the rail.
 * (Replaces four separate small links in the old sidebar.)
 */

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { LogOut, Sparkles, User } from "lucide-react"
import { createClient } from "@/lib/supabase/client"

export function YouMenu({ projectId, onStart }: { projectId: string; onStart: () => void }) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const away = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false)
    document.addEventListener("mousedown", away)
    document.addEventListener("keydown", esc)
    return () => {
      document.removeEventListener("mousedown", away)
      document.removeEventListener("keydown", esc)
    }
  }, [open])

  async function logOut() {
    await createClient().auth.signOut()
    router.push("/login")
    router.refresh()
  }

  const item =
    "flex min-h-11 w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-sm text-ink-2 hover:bg-raised hover:text-ink"

  return (
    <div ref={wrap} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex min-h-11 w-full flex-col items-center justify-center gap-1 px-2 py-1.5 text-xs text-ink-2 hover:text-ink md:py-2.5"
      >
        <User className="h-5 w-5" aria-hidden="true" />
        You
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40 bg-ground/70 md:hidden" onClick={() => setOpen(false)} aria-hidden="true" />
          <div
            role="menu"
            aria-label="You"
            className="fixed inset-x-0 bottom-0 z-50 safe-bottom overscroll-contain rounded-t-xl border-t border-line bg-surface p-2 shadow-l3 md:absolute md:bottom-0 md:left-full md:z-40 md:ml-2 md:w-64 md:rounded-md md:border md:p-1 md:shadow-xl"
          >
            <Link role="menuitem" href="/songs" className={item} onClick={() => setOpen(false)}>
              All your songs
            </Link>
            <button
              role="menuitem"
              className={item}
              onClick={() => {
                setOpen(false)
                onStart()
              }}
            >
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              Start with whatever you have
            </button>
            <Link role="menuitem" href={`/${projectId}/yours`} className={item} onClick={() => setOpen(false)}>
              What makes this song yours
            </Link>
            <Link role="menuitem" href="/taste" className={item} onClick={() => setOpen(false)}>
              What Frank knows about your taste
            </Link>
            <button role="menuitem" className={item} onClick={logOut}>
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Log out
            </button>
          </div>
        </>
      )}
    </div>
  )
}
