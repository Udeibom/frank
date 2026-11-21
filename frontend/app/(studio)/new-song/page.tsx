"use client"

/**
 * /new-song — a redirect trampoline.
 *
 * Used as the `?next=` destination when an unauthenticated user clicks
 * "Start a Song" on the homepage. After they sign up or log in they land
 * here, which immediately creates a project and drops them into the studio.
 */

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { createProject } from "@/lib/api/projects"

export default function NewSongPage() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    createProject({ title: "Untitled Song" })
      .then((project) => router.replace(`/${project.id}/idea`))
      .catch((err: unknown) => {
        const message =
          err instanceof Error ? err.message : "Something went wrong — want to try again?"
        setError(message)
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <div className="text-center">
          <p className="text-sm text-[#E26A5F]">{error}</p>
          <button
            onClick={() => {
              setError(null)
              createProject({ title: "Untitled Song" })
                .then((project) => router.replace(`/${project.id}/idea`))
                .catch((err: unknown) => {
                  const message =
                    err instanceof Error ? err.message : "Something went wrong — want to try again?"
                  setError(message)
                })
            }}
            className="mt-3 text-sm underline underline-offset-2 text-muted-foreground hover:text-foreground"
          >
            Try again
          </button>
        </div>
      </main>
    )
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <p className="text-sm text-muted-foreground">Opening the studio…</p>
    </main>
  )
}
