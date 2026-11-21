"use client"

import { useRouter } from "next/navigation"
import { createProject } from "@/lib/api/projects"
import { createClient } from "@/lib/supabase/client"
import { useState, useEffect, useRef } from "react"
import Image from "next/image"

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
      : "Start Your Song"

  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* ── Fixed top nav ──────────────────────────────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4 md:px-10">
        <span className="font-written text-xl italic text-foreground/90 tracking-tight">
          Frank
        </span>
        <a
          href="/login"
          className="text-sm text-ink-2 hover:text-foreground transition-colors"
        >
          Sign in
        </a>
      </nav>

      {/* ── Hero section ───────────────────────────────────────────────────── */}
      <main className="relative flex min-h-screen flex-col items-center justify-center px-4 pt-16 overflow-hidden">

        {/* Layered ambient background */}
        <div className="pointer-events-none absolute inset-0 -z-10">
          {/* Bottom-center: amber bloom */}
          <div style={{
            position: "absolute", inset: 0,
            background: "radial-gradient(ellipse 70% 55% at 50% 75%, rgb(240 168 48 / 0.12) 0%, transparent 65%)",
          }} />
          {/* Top-left: feel/purple bloom */}
          <div style={{
            position: "absolute", inset: 0,
            background: "radial-gradient(ellipse 50% 45% at 10% 10%, rgb(142 134 201 / 0.08) 0%, transparent 60%)",
          }} />
          {/* Top-right: music/teal bloom */}
          <div style={{
            position: "absolute", inset: 0,
            background: "radial-gradient(ellipse 45% 40% at 90% 15%, rgb(79 163 154 / 0.06) 0%, transparent 55%)",
          }} />
        </div>

        <div className="flex flex-col items-center gap-6 text-center max-w-3xl mx-auto">

          {/* Eyebrow */}
          <p className="landing-fade landing-fade-1 text-xs font-medium tracking-[0.18em] uppercase text-primary/80">
            Your AI songwriting partner
          </p>

          {/* Wordmark */}
          <h1
            className="landing-fade landing-fade-2 font-written italic tracking-tight text-foreground"
            style={{
              fontSize: "clamp(5rem, 14vw, 9rem)",
              lineHeight: 1,
              textShadow: "0 0 60px rgb(240 168 48 / 0.2)",
            }}
          >
            Frank
          </h1>

          {/* Subtitle */}
          <p className="landing-fade landing-fade-3 text-xl text-ink-2 max-w-md leading-relaxed">
            You have the song.<br className="hidden sm:block" /> Frank handles the rest.
          </p>

          {/* CTA */}
          <div className="landing-fade landing-fade-4 flex flex-col items-center gap-3 mt-2">
            <button
              onClick={handleStart}
              disabled={loading}
              className="cta-glow group relative rounded-full bg-primary px-12 py-4 text-base font-semibold text-primary-foreground disabled:opacity-60"
            >
              <span className="flex items-center gap-2">
                {buttonLabel}
                {!loading && (
                  <span
                    className="inline-block transition-transform duration-200 group-hover:translate-x-1"
                    aria-hidden="true"
                  >
                    →
                  </span>
                )}
              </span>
            </button>

            {/* Error message */}
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

            <p className="text-xs text-muted-foreground/40 tracking-widest uppercase mt-1">
              Free to start · No credit card
            </p>
          </div>
        </div>

        {/* Scroll hint */}
        <div className="landing-fade landing-fade-5 absolute bottom-8 flex flex-col items-center gap-1 text-ink-3/50">
          <span className="text-xs tracking-widest uppercase">Scroll</span>
          <span className="text-base" aria-hidden="true">↓</span>
        </div>
      </main>

      {/* ── How it Works strip ──────────────────────────────────────────────── */}
      <section className="py-24 px-4">
        <div className="max-w-4xl mx-auto">
          <p className="text-center text-xs tracking-[0.18em] uppercase text-ink-3 mb-12">
            How it works
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                step: "01",
                color: "rgb(var(--words))",
                title: "Write",
                body: "Start with a line, a title, or just a feeling. Frank listens and helps your lyrics take shape.",
              },
              {
                step: "02",
                color: "rgb(var(--music))",
                title: "Compose",
                body: "Describe a vibe or hum a melody. Frank builds chords, rhythm, and an arrangement around you.",
              },
              {
                step: "03",
                color: "rgb(var(--voice))",
                title: "Record",
                body: "Lay down your vocal. Frank tunes, layers, and mixes so you sound the way you hear yourself.",
              },
            ].map(({ step, color, title, body }) => (
              <div
                key={step}
                className="relative rounded-xl border border-line bg-surface p-6 flex flex-col gap-4"
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ background: color }}
                    aria-hidden="true"
                  />
                  <span className="text-xs text-ink-3 tracking-widest font-medium">{step}</span>
                </div>
                <h2
                  className="font-written italic text-3xl text-foreground"
                  style={{ color }}
                >
                  {title}
                </h2>
                <p className="text-sm text-ink-2 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Photo + Quote — Row 1 (image left) ─────────────────────────────── */}
      <section className="py-16 px-4">
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          <div className="relative aspect-square max-w-sm mx-auto w-full overflow-hidden rounded-2xl">
            <Image
              src="/landing-woman.png"
              alt="A songwriter listening to music she just created with Frank"
              fill
              className="object-cover"
              sizes="(max-width: 768px) 100vw, 50vw"
            />
          </div>
          <div className="flex flex-col gap-6 max-w-md">
            <div
              className="w-8 h-1 rounded-full"
              style={{ background: "rgb(var(--frank))" }}
              aria-hidden="true"
            />
            <blockquote className="font-written italic text-2xl md:text-3xl text-foreground leading-snug">
              "I had a melody in my head for three years. Frank helped me finish it in one afternoon."
            </blockquote>
            <p className="text-sm text-ink-3">
              Maya R. — Singer-Songwriter, Lagos
            </p>
          </div>
        </div>
      </section>

      {/* ── Photo + Quote — Row 2 (image right) ─────────────────────────────── */}
      <section className="py-16 px-4">
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          <div className="flex flex-col gap-6 max-w-md md:order-first order-last">
            <div
              className="w-8 h-1 rounded-full"
              style={{ background: "rgb(var(--music))" }}
              aria-hidden="true"
            />
            <blockquote className="font-written italic text-2xl md:text-3xl text-foreground leading-snug">
              "I'm not a producer. I'm just a guy who writes. Frank speaks my language."
            </blockquote>
            <p className="text-sm text-ink-3">
              Jordan K. — Poet &amp; Lyricist, Toronto
            </p>
          </div>
          <div className="relative aspect-square max-w-sm mx-auto w-full overflow-hidden rounded-2xl md:order-last order-first">
            <Image
              src="/landing-man.png"
              alt="A songwriter writing in his notebook with Frank open on his laptop"
              fill
              className="object-cover"
              sizes="(max-width: 768px) 100vw, 50vw"
            />
          </div>
        </div>
      </section>

      {/* ── Feature highlight strip ─────────────────────────────────────────── */}
      <section className="py-24 px-4" style={{ background: "rgb(var(--raised) / 0.5)" }}>
        <div className="max-w-4xl mx-auto">
          <p className="text-center text-xs tracking-[0.18em] uppercase text-ink-3 mb-4">
            Three rooms. One song.
          </p>
          <h2 className="font-written italic text-center text-4xl md:text-5xl text-foreground mb-14">
            Everything a song needs,<br className="hidden sm:block" /> in one place.
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[
              {
                label: "Words Room",
                color: "rgb(var(--words))",
                bg: "rgb(var(--words) / 0.07)",
                icon: "✍️",
                desc: "Write and edit lyrics with live rhyme detection, syllable stress markers, and structure suggestions.",
              },
              {
                label: "Music Room",
                color: "rgb(var(--music))",
                bg: "rgb(var(--music) / 0.07)",
                icon: "🎸",
                desc: "Describe a vibe in plain English. Frank generates chords, progressions, and a full arrangement.",
              },
              {
                label: "Voice Room",
                color: "rgb(var(--voice))",
                bg: "rgb(var(--voice) / 0.07)",
                icon: "🎤",
                desc: "Record a melody, hum a hook, or just talk it out. Frank transcribes, refines, and layers your voice.",
              },
            ].map(({ label, color, bg, icon, desc }) => (
              <div
                key={label}
                className="rounded-xl border border-line p-6 flex flex-col gap-4"
                style={{ background: bg }}
              >
                <span className="text-2xl" role="img" aria-hidden="true">{icon}</span>
                <h3
                  className="font-semibold text-base"
                  style={{ color }}
                >
                  {label}
                </h3>
                <p className="text-sm text-ink-2 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA band ──────────────────────────────────────────────────── */}
      <section className="relative py-28 px-4 overflow-hidden">
        {/* Ambient glow behind the final CTA */}
        <div
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background: "radial-gradient(ellipse 60% 60% at 50% 50%, rgb(240 168 48 / 0.09) 0%, transparent 70%)",
          }}
        />
        <div className="max-w-2xl mx-auto flex flex-col items-center gap-6 text-center">
          <h2
            className="font-written italic text-5xl md:text-6xl text-foreground"
            style={{ textShadow: "0 0 40px rgb(240 168 48 / 0.15)" }}
          >
            Your next song is waiting.
          </h2>
          <p className="text-lg text-ink-2 max-w-sm leading-relaxed">
            No music theory required.<br className="hidden sm:block" /> No studio needed. Just you and an idea.
          </p>

          {/* Second instance of the CTA — same handleStart, same logic */}
          <button
            onClick={handleStart}
            disabled={loading}
            className="cta-glow group relative mt-4 rounded-full bg-primary px-12 py-4 text-base font-semibold text-primary-foreground disabled:opacity-60"
          >
            <span className="flex items-center gap-2">
              {buttonLabel}
              {!loading && (
                <span
                  className="inline-block transition-transform duration-200 group-hover:translate-x-1"
                  aria-hidden="true"
                >
                  →
                </span>
              )}
            </span>
          </button>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer className="border-t border-line py-8 px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-ink-3">
        <span className="font-written italic text-sm text-foreground/50">Frank</span>
        <div className="flex items-center gap-6">
          <a href="/login" className="hover:text-foreground transition-colors">Sign in</a>
          <a href="/signup" className="hover:text-foreground transition-colors">Sign up</a>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            GitHub
          </a>
        </div>
      </footer>

    </div>
  )
}
