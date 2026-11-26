"use client"

import { useRouter } from "next/navigation"
import { createProject } from "@/lib/api/projects"
import { createClient } from "@/lib/supabase/client"
import { useState, useEffect, useRef } from "react"
import Image from "next/image"
import Link from "next/link"

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
        router.push("/signup?next=%2Fnew-song")
        return
      }
      const project = await createProject({ title: "Untitled Song" })
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

  const buttonLabel = loading
    ? slowStart
      ? "Waking up the studio… (this takes about 20 seconds on first visit)"
      : "Opening your studio…"
    : "Start a Song — Free Session"

  return (
    <div className="min-h-screen bg-ground text-ink">

      {/* ── Sticky nav ───────────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 w-full border-b border-line/60 bg-ground/95 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
          {/* Wordmark */}
          <div className="flex items-center gap-2">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg"
              style={{ background: "rgb(var(--frank))", boxShadow: "0 0 12px rgba(245,158,11,0.3)" }}
            >
              <span className="font-written italic text-base leading-none text-ground select-none">f</span>
            </div>
            <span className="text-sm font-semibold tracking-tight text-ink">Frank</span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-ink-3 ml-0.5">Studio</span>
          </div>
          {/* Nav links — smooth-scroll to page sections */}
          <div className="hidden items-center gap-6 md:flex">
            {([
              ["Overview",    "overview"],
              ["Rooms",       "rooms"],
              ["How It Works","why-frank"],
              ["Philosophy",  "philosophy"],
              ["Listen",      "listen"],
            ] as [string, string][]).map(([label, id]) => (
              <button
                key={label}
                onClick={() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" })}
                className="text-xs font-medium uppercase tracking-wide text-ink-2 transition-colors hover:text-ink"
              >
                {label}
              </button>
            ))}
          </div>
          {/* Auth + CTA */}
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-xs text-ink-2 hover:text-ink transition-colors">
              Sign in
            </Link>
            <button
              onClick={handleStart}
              disabled={loading}
              className="rounded-md px-4 py-2 text-xs font-semibold text-ground transition-all disabled:opacity-60"
              style={{ background: "rgb(var(--frank))", boxShadow: "0 0 14px rgba(245,158,11,0.3)" }}
            >
              {loading ? "Opening…" : "Open Studio"}
            </button>
          </div>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────────────────────── */}
      <section id="overview" className="relative overflow-hidden px-6 pb-0 pt-24 text-center">
        {/* Ambient amber glow behind hero */}
        <div
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(ellipse 70% 60% at 50% -10%, rgba(245,158,11,0.12) 0%, transparent 65%)",
          }}
        />
        {/* Eyebrow */}
        <p className="mb-6 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-3">
          Songwriter &bull; Production &bull; Master Calibration
        </p>
        {/* Headline */}
        <h1 className="font-written text-5xl font-normal leading-tight text-ink md:text-6xl landing-fade landing-fade-1">
          You have a song in your head.
          <br />
          <em style={{ color: "rgb(var(--frank))" }}>Let&apos;s get it out.</em>
        </h1>
        <p className="mx-auto mt-6 max-w-xl text-base text-ink-2 leading-relaxed landing-fade landing-fade-2">
          Frank is your co-writer, session band, vocal producer, and tape mastering engineer. From a
          hummed note or half-written notebook line to a finished 24-bit record — in five collaborative rooms.
        </p>
        {/* Error message */}
        {error && (
          <p className="mt-4 text-sm text-center" style={{ color: "rgb(var(--problem))" }}>
            {error}
          </p>
        )}
        {/* CTAs */}
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row landing-fade landing-fade-3">
          <button
            onClick={handleStart}
            disabled={loading}
            className="cta-glow flex items-center gap-2 rounded-md px-6 py-3 text-sm font-semibold text-ground transition-all disabled:opacity-60"
            style={{ background: "rgb(var(--frank))", boxShadow: "0 0 28px rgba(245,158,11,0.45)" }}
          >
            <span>▶</span>
            <span>{buttonLabel}</span>
          </button>
          <button
            onClick={() => document.getElementById("listen")?.scrollIntoView({ behavior: "smooth" })}
            className="rounded-md border border-line px-6 py-3 text-sm text-ink-2 transition-colors hover:border-line hover:text-ink"
          >
            Listen to Records Made in Frank
          </button>
        </div>
        {/* Studio screenshot hero */}
        <div
          className="relative mx-auto mt-14 max-w-5xl overflow-hidden rounded-t-xl border border-line/60 landing-fade landing-fade-4"
          style={{ boxShadow: "0 -4px 48px rgba(0,0,0,0.6)" }}
        >
          <Image
            src="/stitch-hero.png"
            alt="The Frank studio — Words room with a song in progress"
            width={1440}
            height={900}
            className="w-full object-cover object-top"
            priority
            onError={(e) => {
              // Fallback if the screenshot isn't there yet
              const target = e.target as HTMLImageElement
              target.style.display = "none"
            }}
          />
          {/* Gradient fade at bottom of screenshot */}
          <div
            className="absolute inset-x-0 bottom-0 h-32"
            style={{ background: "linear-gradient(to bottom, transparent, rgb(var(--ground)))" }}
          />
        </div>
      </section>

      {/* ── A room with no faders ────────────────────────────────────────────── */}
      <section id="rooms" className="px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-3">The Workflow</p>
          <h2 className="mb-3 font-written text-4xl font-normal text-ink">
            A room with no faders or cold numbers.
          </h2>
          <p className="mb-12 max-w-2xl text-sm text-ink-2 leading-relaxed">
            Most audio workstations look like Boeing cockpits: 4,000 controls, tiny frequency graphs, and
            confusing jargon that freezes your creative impulses before the first verse is even written.
          </p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {[
              {
                n: "01", material: "WORDS", color: "rgb(var(--words))",
                name: "The Lyricist's Desk",
                body: "Type whatever is in your head. Frank finds structure and suggests rhymes that don't make you feel silly for writing them.",
              },
              {
                n: "02", material: "FEELING", color: "rgb(var(--feel))",
                name: "Vibe & Harmonic Direction",
                body: "No dropdown menus for 128 synths. Tell Frank 'slow and warm' or 'urgent and bright' and he auditions three emotionally distinct harmonic directions in real time.",
              },
              {
                n: "03", material: "MUSIC", color: "rgb(var(--music))",
                name: "Plain-English Arrangement",
                body: "A transparent bar-by-bar arrangement. Click on any cell, tell Frank the vibe or simply 'Fuller' and 'Calmer'. Sections build themselves.",
              },
              {
                n: "04", material: "VOICE", color: "rgb(var(--voice))",
                name: "Safe Vocal Booth & Comping",
                body: "Sing directly into your microphone. Frank counts you in, keeps every take safe, tunes within ear-plausible ranges, and locks your signature without sounding engineered.",
              },
              {
                n: "05", material: "BLEND", color: "rgb(var(--ink-2))",
                name: "Tape Mastering & Stem Export",
                body: "No decibels or fader readings. Simply say 'more compressed' or 'warmer bass'. Frank masters to professional -14LUFS and produces 24-bit WAV with isolated stems.",
              },
              {
                n: "06", material: "FINISH", color: "rgb(var(--ink-2))",
                name: "Master & Release",
                body: "A last listen, then it's yours. Download your song in 24-bit, grab individual stems, or take Frank's one surprise idea before you go.",
              },
            ].map(({ n, material, color, name, body }) => (
              <div key={n} className="rounded-md border border-line bg-surface p-5 flex flex-col gap-3 transition-colors hover:border-line hover:bg-raised">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] text-ink-3">Room {n} //</span>
                  <span className="font-mono text-[10px]" style={{ color }}>{material}</span>
                </div>
                <h3 className="text-sm font-semibold text-ink">{name}</h3>
                <p className="text-xs text-ink-2 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Frank quote block ────────────────────────────────────────────────── */}
      <section className="border-y border-line bg-surface px-6 py-16 text-center" id="philosophy">
        <div className="mx-auto max-w-3xl">
          <div className="mb-6 flex items-center justify-center gap-3">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-lg"
              style={{ background: "rgb(var(--frank) / 0.15)", border: "1px solid rgb(var(--frank) / 0.3)" }}
            >
              <span className="font-written italic text-xl" style={{ color: "rgb(var(--frank))" }}>f</span>
            </div>
            <span className="font-mono text-[10px] uppercase tracking-widest text-ink-3">The Wire Plugin</span>
          </div>
          <blockquote className="font-written italic text-2xl leading-relaxed text-ink">
            &ldquo;Frank is designed for how songs are actually born — on a piano bench at midnight,
            in the car humming into a voice memo, or sitting with a notebook trying to find the line
            that makes you cry.&rdquo;
          </blockquote>
        </div>
      </section>

      {/* ── Why Frank comparison ─────────────────────────────────────────────── */}
      <section id="why-frank" className="border-t border-line px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <p className="mb-10 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-3">Why Frank</p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {[
              {
                label: "Engineering Overload", tag: "TRADITIONAL PRO DAWS", bad: true,
                items: [
                  "Hundreds of samples, sample rates, side-chain routings, and buffers.",
                  "The intimidating blank timeline with eleven panels before you write a word.",
                  "Requires years of audio school before your sessions feel productive.",
                  "Technical troubleshooting drains your creative momentum.",
                ],
              },
              {
                label: "Zero Creative Control", tag: "ALGO BEAT GENERATORS", bad: true,
                items: [
                  "Type a prompt and edit the result. You don't set the direction.",
                  "Doesn't feel like your project — it's not your art.",
                  "No persistent memory of your style across sessions.",
                  "Platform watermarks embedded whenever you share a track.",
                ],
              },
              {
                label: "Collaborative Craft", tag: "FRANK STUDIO", bad: false,
                items: [
                  "Including the feeling & melody: Frank learns the orchestration with you.",
                  "Complete vocal anatomy: edit every lyric, bar by bar in real time.",
                  "Learned vocal texture — compact, polished — without pitch correction artifacts.",
                  "24-bit master in one exportable stereo mix plus isolated stems.",
                ],
              },
            ].map(({ label, tag, bad, items }) => (
              <div
                key={label}
                className="rounded-md border p-5"
                style={{
                  borderColor: bad ? "rgb(var(--line))" : "rgb(var(--frank) / 0.4)",
                  background: bad ? "rgb(var(--surface))" : "rgb(var(--frank) / 0.05)",
                  boxShadow: bad ? undefined : "0 0 24px rgba(245,158,11,0.1)",
                }}
              >
                <p
                  className="mb-1 font-mono text-[10px] uppercase tracking-widest"
                  style={{ color: bad ? "rgb(var(--ink-3))" : "rgb(var(--frank))" }}
                >
                  {tag}
                </p>
                <h3 className="mb-4 text-sm font-semibold text-ink">{label}</h3>
                <ul className="flex flex-col gap-2">
                  {items.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-ink-2">
                      <span className="mt-0.5 shrink-0" style={{ color: bad ? "rgb(var(--problem))" : "rgb(var(--ok))" }}>
                        {bad ? "✕" : "✓"}
                      </span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Testimonials ────────────────────────────────────────────────────── */}
      <section id="listen" className="border-t border-line px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-3">Born With Frank</p>
          <h2 className="mb-10 font-written text-4xl font-normal text-ink">Real Songs. Real Songwriters.</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {[
              {
                tag: "FOLK", title: "Late Night Train", by: "ClaraM • Brooklyn, NY", time: "3:24",
                quote: "\"Hummed on a voice note at 3 am after revisiting my grandparents' house. Frank gave me the upright piano and what it could feel like. I can still hear the original.\"",
                stats: "4:04 • Dm • 3 TAKES BEFORE SCORED",
              },
              {
                tag: "SILVER POP", title: "Silver Lake Fog", by: "Marco • Los Angeles, CA", time: "3:04",
                quote: "\"Started with 4 lines in my Notes app. Frank suggested 70 BPM grooves and dreamy Rhodes studies that filled the room on a Sunday morning.\"",
                stats: "4:17 • Eb+ • 2 TAKES BEFORE SCORED",
              },
              {
                tag: "DUSTY AMERICANA", title: "Highway Motel", by: "Marcus Thorne • Austin, TX", time: "4:12",
                quote: "\"I sang into a cheap headphone mic. Frank tuned it without making me sound like a robot and added a lower-pitched descant harmony that I never would have thought of.\"",
                stats: "4:17 • G+ • 3 TAKES BEFORE SCORED",
              },
            ].map(({ tag, title, by, time, quote, stats }) => (
              <div key={title} className="rounded-md border border-line bg-surface p-5 flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-widest text-ink-3">{tag}</span>
                  <span className="font-mono text-[10px] text-ink-3">{time}</span>
                </div>
                <div className="flex items-center gap-3">
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md"
                    style={{ background: "rgb(var(--frank) / 0.15)", border: "1px solid rgb(var(--frank) / 0.2)" }}
                  >
                    <span className="text-xs" style={{ color: "rgb(var(--frank))" }}>▶</span>
                  </div>
                  <div>
                    <p className="font-written italic text-sm font-medium text-ink">{title}</p>
                    <p className="font-mono text-[10px] text-ink-3">{by}</p>
                  </div>
                </div>
                <p className="text-xs italic text-ink-2">{quote}</p>
                <p className="font-mono text-[10px] text-ink-3 border-t border-line/40 pt-2 mt-auto">{stats}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── The more you write ─────────────────────────────────────────────── */}
      <section className="border-t border-line bg-surface px-6 py-24">
        <div className="mx-auto max-w-6xl grid grid-cols-1 gap-12 md:grid-cols-2 items-start">
          <div>
            <p className="mb-2 font-mono text-[11px] uppercase tracking-widest text-ink-3">Session Continuity</p>
            <h2 className="mb-4 font-written text-4xl font-normal text-ink leading-tight">
              The more you write, the deeper Frank listens.
            </h2>
            <p className="mb-6 text-sm text-ink-2 leading-relaxed">
              A real producer knows what key flatters your voice, what tempo you gravitate toward at night,
              and what instrumentally motivates you to finish. Frank builds this across sessions — encrypted
              privately to you.
            </p>
            <ul className="flex flex-col gap-2">
              {[
                "Remembers your comfortable vocal range ±12 to ±8",
                "Honors your recurring lyric themes and translates them into a beat cycle.",
                "Learns your natural tuning without training publicly or sharing any files.",
              ].map((item) => (
                <li key={item} className="flex items-start gap-2 text-xs text-ink-2">
                  <span style={{ color: "rgb(var(--ok))" }}>→</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
          {/* Taste profile card */}
          <div className="rounded-md border border-line bg-ground p-5">
            <div className="mb-4 flex items-center justify-between">
              <p className="font-mono text-[10px] uppercase tracking-widest" style={{ color: "rgb(var(--frank))" }}>
                Songwriter Taste Profile // Session #37654
              </p>
              <span className="font-mono text-[10px] text-ink-3">Encrypted</span>
            </div>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {[
                { label: "Vocal Arrangement", color: "rgb(var(--words))", text: "Prefers intimate, near-mic vocal delivery with gentle lower-octave harmonies in choruses." },
                { label: "Sonic Atmosphere", color: "rgb(var(--music))", text: "Gravitates toward analog warmth, subtle vinyl dust, upright felt piano, and sparse midnight pulse rhythms." },
                { label: "Tempo & Groove", color: "rgb(var(--feel))", text: "Comfortable with relaxed walking paces between 76 and 84 BPM, favoring unhurried cadences." },
                { label: "Mastering Target", color: "rgb(var(--ok))", text: "Balanced streaming loudness with healthy -1.4dB true peak ceiling to avoid digital clipping." },
              ].map(({ label, color, text }) => (
                <div key={label} className="rounded-md border border-line bg-surface p-3">
                  <p className="mb-1 font-mono text-[10px] uppercase tracking-wider" style={{ color }}>{label}</p>
                  <p className="text-xs text-ink-2">{text}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-start gap-2 rounded-md border border-line bg-surface p-3">
              <div
                className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded"
                style={{ background: "rgb(var(--frank) / 0.15)", border: "1px solid rgb(var(--frank) / 0.3)" }}
              >
                <span className="font-written italic text-xs" style={{ color: "rgb(var(--frank))" }}>f</span>
              </div>
              <p className="text-xs text-ink-2">
                &ldquo;I know you dislike high pop sheen on your vocals. Whenever you hit record, I will
                automatically default to our vintage ribbon mic calibration.&rdquo;
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Final CTA ───────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-t border-line px-6 py-28 text-center">
        <div
          className="pointer-events-none absolute inset-0 -z-10"
          style={{ background: "radial-gradient(ellipse 60% 50% at 50% 50%, rgba(245,158,11,0.08) 0%, transparent 70%)" }}
        />
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-6">
          <div
            className="flex h-12 w-12 items-center justify-center rounded-xl"
            style={{ background: "rgb(var(--frank))", boxShadow: "0 0 24px rgba(245,158,11,0.4)" }}
          >
            <span className="font-written italic text-2xl text-ground">f</span>
          </div>
          <h2 className="font-written text-4xl font-normal text-ink md:text-5xl">
            The best time to make your song is while it&apos;s still in your head.
          </h2>
          <p className="text-base text-ink-2 leading-relaxed">
            No hardware to connect. No expensive gear or production manuals. Just sit down, speak to Frank,
            and hear your idea turn into music.
          </p>
          <div className="flex flex-col items-center gap-3 sm:flex-row">
            <button
              onClick={handleStart}
              disabled={loading}
              className="cta-glow flex items-center gap-2 rounded-md px-6 py-3 text-sm font-semibold text-ground transition-all disabled:opacity-60"
              style={{ background: "rgb(var(--frank))", boxShadow: "0 0 28px rgba(245,158,11,0.45)" }}
            >
              <span>▶</span>
              <span>Open Frank Studio — Free Session</span>
            </button>
            <button
              onClick={() => document.getElementById("rooms")?.scrollIntoView({ behavior: "smooth" })}
              className="rounded-md border border-line px-6 py-3 text-sm text-ink-2 transition-colors hover:text-ink"
            >
              Explore All 6 Rooms
            </button>
          </div>
          <p className="font-mono text-[11px] uppercase tracking-widest text-ink-3">
            Works in Chrome • Safari • No Installation • Export 24-bit Stems Anytime
          </p>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────────────── */}
      <footer className="border-t border-line/30 bg-ground">
        <div className="mx-auto max-w-7xl px-6 py-16">
          <div className="grid grid-cols-1 gap-10 md:grid-cols-2 lg:grid-cols-12">
            {/* Brand */}
            <div className="lg:col-span-4 flex flex-col gap-4">
              <div className="flex items-center gap-2">
                <div
                  className="flex h-8 w-8 items-center justify-center rounded-lg"
                  style={{ background: "rgb(var(--frank))", boxShadow: "0 0 12px rgba(245,158,11,0.2)" }}
                >
                  <span className="font-written italic text-base leading-none text-ground">f</span>
                </div>
                <span className="text-sm font-semibold text-ink">Frank Studio</span>
              </div>
              <p className="font-written italic text-sm text-ink-2 max-w-xs">
                &ldquo;You bring the feeling humming in your head. Frank brings the late-night console,
                the tape machine, and the patient ears to bring it out.&rdquo;
              </p>
              <div className="flex gap-2">
                <span
                  className="rounded border border-line bg-raised px-2 py-1 font-mono text-[10px]"
                  style={{ color: "rgb(var(--frank))" }}
                >
                  Desktop Workstation v2.4
                </span>
                <span
                  className="rounded border border-line bg-raised px-2 py-1 font-mono text-[10px]"
                  style={{ color: "rgb(var(--music))" }}
                >
                  48kHz // 24-BIT
                </span>
              </div>
            </div>
            {/* Rooms */}
            <div className="lg:col-span-3 flex flex-col gap-2">
              <span
                className="font-mono text-[11px] uppercase tracking-widest font-bold"
                style={{ color: "rgb(var(--frank))" }}
              >
                The Production Rooms
              </span>
              {[
                ["Room 1: Words", "Lyricist Deck"],
                ["Room 2: Feeling", "Vibe & Chords"],
                ["Room 3: Music", "Arrangement"],
                ["Room 4: Voice", "Mic Booth"],
                ["Room 5: Blend", "Mixer Rack"],
                ["Room 6: Finish", "Tape Master"],
              ].map(([room, label]) => (
                <div key={room} className="flex items-center justify-between border-b border-line/10 py-1">
                  <span className="text-xs text-ink-2">{room}</span>
                  <span className="font-mono text-[10px] text-ink-3">{label}</span>
                </div>
              ))}
            </div>
            {/* Architecture */}
            <div className="lg:col-span-3 flex flex-col gap-2">
              <span
                className="font-mono text-[11px] uppercase tracking-widest font-bold"
                style={{ color: "rgb(var(--frank))" }}
              >
                Studio Architecture
              </span>
              {["How it Works", "The Analog Duality Manifesto", "Listening Session Tape", "Quick Capture Mode", "Hardware & Latency Specs"].map((l) => (
                <span key={l} className="py-1 text-xs text-ink-2 hover:text-ink cursor-pointer transition-colors">{l}</span>
              ))}
            </div>
            {/* Access */}
            <div className="lg:col-span-2 flex flex-col gap-2">
              <span
                className="font-mono text-[11px] uppercase tracking-widest font-bold"
                style={{ color: "rgb(var(--frank))" }}
              >
                Session Access
              </span>
              <Link href="/login" className="py-1 text-xs text-ink-2 hover:text-ink transition-colors">
                Open Frank Studio
              </Link>
              <Link href="/signup" className="py-1 text-xs text-ink-2 hover:text-ink transition-colors">
                Create an Account
              </Link>
              <span className="py-1 text-xs text-ink-2 cursor-pointer hover:text-ink transition-colors">
                Creator Ethics & Royalties
              </span>
            </div>
          </div>
          {/* Bottom bar */}
          <div className="mt-10 flex flex-col items-center justify-between gap-4 border-t border-line/30 pt-6 md:flex-row">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: "rgb(var(--music))" }} />
              <span className="font-mono text-[11px] text-ink-3">
                FRANK STUDIO ENGINE © 2025 // ALL ANALOG RIGHTS RESERVED
              </span>
            </div>
            <div className="flex gap-6 font-mono text-[11px] text-ink-3">
              <span>NO SYNTHETIC NOISE</span>
              <span>•</span>
              <span>TACTILE CREATIVE AGENCY</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
