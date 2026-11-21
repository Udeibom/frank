"use client"

import { useRouter } from "next/navigation"
import { createProject } from "@/lib/api/projects"
import { createClient } from "@/lib/supabase/client"
import { useState, useEffect, useRef } from "react"

export default function LandingPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [slowStart, setSlowStart] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const slowTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Ping the backend the moment the page loads so it starts waking up
  // before the user clicks anything. Fire-and-forget — we don't care if it fails.
  useEffect(() => {
    fetch("/api/wake").catch(() => {})
    return () => {
      if (slowTimer.current) clearTimeout(slowTimer.current)
    }
  }, [])

  async function handleStart() {
    setLoading(true)
    setError(null)
    setSlowStart(false)

    // If the backend takes more than 3 seconds (Render free-tier cold start),
    // show an honest message so the user knows to keep waiting.
    slowTimer.current = setTimeout(() => setSlowStart(true), 3000)

    try {
      // Signed-out visitors make an account first; signed-in users go straight in.
      const { data } = await createClient().auth.getUser()
      if (!data.user) {
        setLoading(false)
        // Pass ?next=/new-song so after sign-up/login the user lands on the
        // trampoline page that creates a project and enters the studio.
        router.push("/signup?next=%2Fnew-song")
        return
      }
      const project = await createProject({ title: "Untitled Song" })
      // Navigation is happening — leave the loading state so there's no flash.
      router.push(`/${project.id}/idea`)
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Something went wrong — want to try again?"
      setError(message)
      setLoading(false)
      setSlowStart(false)
    } finally {
      if (slowTimer.current) {
        clearTimeout(slowTimer.current)
        slowTimer.current = null
      }
    }
  }

  const buttonLabel = slowStart
    ? "Frank is waking up\u2026"
    : loading
      ? "Opening the studio\u2026"
      : "Start a Song"

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      {/* Ambient background glow */}
      <div
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 60%, hsl(38 92% 50% / 0.06) 0%, transparent 70%)",
        }}
      />

      <div className="flex flex-col items-center gap-8 text-center">
        {/* Wordmark */}
        <div className="flex flex-col items-center gap-2">
          <h1 className="text-7xl font-bold tracking-tight text-foreground">
            Frank
          </h1>
          <p className="text-lg text-muted-foreground">
            You have the song. Frank handles the rest.
          </p>
        </div>

        {/* CTA */}
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={handleStart}
            disabled={loading}
            className="group relative mt-4 rounded-full bg-primary px-10 py-4 text-base font-semibold text-primary-foreground transition-all hover:bg-primary/90 hover:glow-amber disabled:opacity-60"
          >
            {buttonLabel}
          </button>

          {/* Error message — shown in place, beneath the button */}
          {error && (
            <p className="text-sm text-[#E26A5F] max-w-xs">
              {error}{" "}
              <button
                onClick={handleStart}
                className="underline underline-offset-2 hover:no-underline"
              >
                Try again
              </button>
            </p>
          )}
        </div>

        {/* Subtle tagline */}
        <p className="text-xs text-muted-foreground/50 tracking-widest uppercase">
          Use Frank.
        </p>
      </div>
    </main>
  )
}
