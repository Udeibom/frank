"use client"

import { useRouter } from "next/navigation"
import { createProject } from "@/lib/api/projects"
import { useState } from "react"

export default function LandingPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)

  async function handleStart() {
    setLoading(true)
    try {
      const project = await createProject({ title: "Untitled Song" })
      router.push(`/${project.id}/idea`)
    } catch {
      setLoading(false)
    }
  }

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
        <button
          onClick={handleStart}
          disabled={loading}
          className="group relative mt-4 rounded-full bg-primary px-10 py-4 text-base font-semibold text-primary-foreground transition-all hover:bg-primary/90 hover:glow-amber disabled:opacity-60"
        >
          {loading ? "Opening the studio\u2026" : "Start a Song"}
        </button>

        {/* Subtle tagline */}
        <p className="text-xs text-muted-foreground/50 tracking-widest uppercase">
          Use Frank.
        </p>
      </div>
    </main>
  )
}
