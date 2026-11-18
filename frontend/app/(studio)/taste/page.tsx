"use client"

/**
 * Your taste — what Frank has learned about what you like, across all your songs (spec 09, requirement 4).
 * Plain sentences. Edit any line, forget any line, or forget everything. Forgetting really deletes.
 */

import { useEffect, useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { editTaste, forgetAllTaste, forgetTaste, listTaste, type TasteLine } from "@/lib/api/taste"
import { ChevronLeft, Pencil, Trash2, Loader2 } from "lucide-react"

const ABOUT: Record<string, string> = {
  beat_maker: "the music",
  producer: "the feel of your songs",
  mix_engineer: "how it all sits together",
  vocal_producer: "your voice",
  songwriter: "your words",
  mastering_engineer: "the finish",
}

export default function TastePage() {
  const [items, setItems] = useState<TasteLine[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [confirmAll, setConfirmAll] = useState(false)

  useEffect(() => {
    listTaste()
      .then((r) => setItems(r.items))
      .catch(() => setError("I couldn't load this just now. Try again in a moment."))
  }, [])

  async function save(id: string) {
    const text = draft.trim()
    setEditing(null)
    if (text.length < 3) return
    const row = await editTaste(id, text)
    setItems((xs) => xs?.map((x) => (x.id === id ? row : x)) ?? null)
  }

  async function forget(id: string) {
    await forgetTaste(id)
    setItems((xs) => xs?.filter((x) => x.id !== id) ?? null)
  }

  async function forgetAll() {
    await forgetAllTaste()
    setItems([])
    setConfirmAll(false)
  }

  return (
    <div className="mx-auto max-w-2xl px-8 py-10">
      <Link href="/songs" className="mb-6 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
        <ChevronLeft className="h-3.5 w-3.5" /> All Songs
      </Link>
      <h1 className="text-xl font-semibold text-foreground">What Frank knows about your taste</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Frank only writes something here after you&apos;ve shown it a few times, across more than one song, or when you
        say it yourself. It helps Frank choose what to try first. It never stops you doing anything.
      </p>

      {error && <p className="mt-6 text-sm text-red-400">{error}</p>}
      {items === null && !error && (
        <p className="mt-6 flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</p>
      )}
      {items && items.length === 0 && (
        <p className="mt-6 rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          Nothing yet. As you make songs, Frank will notice what you keep choosing.
        </p>
      )}

      {items && items.length > 0 && (
        <ul className="mt-6 flex flex-col gap-2">
          {items.map((t) => (
            <li key={t.id} className="flex items-start gap-3 rounded-xl border border-border bg-card px-4 py-3">
              <div className="min-w-0 flex-1">
                {editing === t.id ? (
                  <input
                    value={draft}
                    autoFocus
                    maxLength={300}
                    aria-label="Change this line"
                    onChange={(e) => setDraft(e.target.value)}
                    onBlur={() => save(t.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") save(t.id)
                      if (e.key === "Escape") setEditing(null)
                    }}
                    className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm"
                  />
                ) : (
                  <p className="text-sm text-foreground">{t.statement}</p>
                )}
                <p className="mt-1 text-[11px] text-muted-foreground">
                  About {ABOUT[t.about] ?? "your songs"}
                  {t.said_by_you ? " · you said this" : " · learned from your choices"}
                  {t.edited ? " · changed by you" : ""}
                </p>
              </div>
              <button
                onClick={() => {
                  setDraft(t.statement)
                  setEditing(t.id)
                }}
                aria-label={`Change: ${t.statement}`}
                className="rounded p-1 text-muted-foreground hover:text-foreground"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button onClick={() => forget(t.id)} aria-label={`Forget: ${t.statement}`} className="rounded p-1 text-muted-foreground hover:text-red-400">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {items && items.length > 0 && (
        <div className="mt-8">
          {confirmAll ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-foreground">Forget everything Frank has learned about your taste?</span>
              <Button size="sm" variant="outline" onClick={() => setConfirmAll(false)}>Keep it</Button>
              <Button size="sm" onClick={forgetAll}>Yes, forget everything</Button>
            </div>
          ) : (
            <button onClick={() => setConfirmAll(true)} className="text-xs text-muted-foreground underline hover:text-foreground">
              Forget everything
            </button>
          )}
        </div>
      )}
    </div>
  )
}
