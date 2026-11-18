"use client"

/**
 * What makes this song yours — the identity brief in plain words (creative-director spec 10, requirement 1.2).
 * Your own words and images, your voice, what to keep and what you turned down. Everyone on Frank's team reads it.
 */

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import { Loader2, RefreshCw } from "lucide-react"

interface Identity {
  own_words?: string[]
  own_images?: string[]
  voice?: string
  keep?: string[]
  avoid?: string[]
}

const GROUPS: { key: keyof Identity; title: string }[] = [
  { key: "own_words", title: "Words you use about it" },
  { key: "own_images", title: "Your images" },
  { key: "keep", title: "What Frank will protect" },
  { key: "avoid", title: "What you turned down" },
]

export default function YoursPage() {
  const params = useParams()
  const projectId = params.projectId as string
  const [identity, setIdentity] = useState<Identity | null | undefined>(undefined)
  const [working, setWorking] = useState(false)

  useEffect(() => {
    api.get<{ identity: Identity | null }>(`/projects/${projectId}/finish/identity`)
      .then((r) => setIdentity(r.identity))
      .catch(() => setIdentity(null))
  }, [projectId])

  async function refresh() {
    setWorking(true)
    try {
      const r = await api.post<{ identity: Identity | null }>(`/projects/${projectId}/finish/identity`)
      if (r.identity) setIdentity(r.identity)
    } finally {
      setWorking(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-8 py-10">
      <h1 className="text-xl font-semibold text-foreground">What makes this song yours</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Frank keeps this so every change protects what&apos;s yours. If something here would be lost, Frank says so once,
        and your call always wins.
      </p>
      {identity === undefined && (
        <p className="mt-6 flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</p>
      )}
      {identity === null && (
        <p className="mt-6 rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          Nothing yet. Talk to Frank about the song, write some words or record a take, and this fills in.
        </p>
      )}
      {identity && (
        <div className="mt-6 flex flex-col gap-4">
          {identity.voice && (
            <section className="rounded-xl border border-border bg-card p-4">
              <h2 className="mb-1 text-xs font-medium text-muted-foreground">Your voice</h2>
              <p className="text-sm text-foreground">{identity.voice}</p>
            </section>
          )}
          {GROUPS.map(({ key, title }) => {
            const items = (identity[key] as string[] | undefined) ?? []
            if (!items.length) return null
            return (
              <section key={key} className="rounded-xl border border-border bg-card p-4">
                <h2 className="mb-2 text-xs font-medium text-muted-foreground">{title}</h2>
                <ul className="list-disc pl-5 text-sm text-foreground">
                  {items.map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
              </section>
            )
          })}
        </div>
      )}
      <Button variant="outline" size="sm" className="mt-6" onClick={refresh} disabled={working}>
        {working ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />} Look again
      </Button>
    </div>
  )
}
