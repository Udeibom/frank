"use client"

/**
 * Starting from the world (frankenstein spec 14, requirements 6.1, 6.6, 6.7): a picture that shows the feeling,
 * the person's own "right now" (time of day and weather), or a song they love. Each one becomes feeling words
 * and gentle hints for the song's direction; none of them is copied.
 */

import { useRef, useState } from "react"
import { Image as ImageIcon, CloudSun, Music2, Loader2 } from "lucide-react"
import { pollJob } from "@/lib/api/jobs"
import { nameASong, pickFreeMusic, searchFreeMusic, startFromMoment, startFromPicture, uploadReference } from "@/lib/api/organs"
import { GeminiNotice } from "@/components/studio/GeminiNotice"
import type { JamendoTrack } from "@/types/api"

interface WorldStartsProps {
  projectId: string
  onSay: (message: string) => void
  onChanged?: () => void
}

type Panel = null | "song"

export function WorldStarts({ projectId, onSay, onChanged }: WorldStartsProps) {
  const [working, setWorking] = useState<string | null>(null)
  const [panel, setPanel] = useState<Panel>(null)
  const [query, setQuery] = useState("")
  const [named, setNamed] = useState("")
  const [tracks, setTracks] = useState<JamendoTrack[] | null>(null)
  const [freeNote, setFreeNote] = useState<string | null>(null)
  const [ownsIt, setOwnsIt] = useState(false)
  const picture = useRef<HTMLInputElement>(null)
  const songFile = useRef<HTMLInputElement>(null)

  async function run<T>(label: string, fn: () => Promise<T>, then: (r: T) => void) {
    setWorking(label)
    try {
      then(await fn())
      onChanged?.()
    } catch (err) {
      onSay(err instanceof Error && err.message ? err.message : "That didn't work just now. Want to try again?")
    } finally {
      setWorking(null)
    }
  }

  function onPicture(file: File | undefined) {
    if (!file) return
    void run("Looking at your picture…", () => startFromPicture(projectId, file), (r) => onSay(r.message))
  }

  function rightNow() {
    if (!("geolocation" in navigator)) {
      onSay("Your browser won't tell me where you are, so I can't see your weather. Describe your moment in words instead?")
      return
    }
    setWorking("Finding your moment…")
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        void run("Reading the sky where you are…", () =>
          startFromMoment(projectId, pos.coords.latitude, pos.coords.longitude, new Date().getHours()), (r) => onSay(r.message)),
      () => {
        setWorking(null)
        onSay("No problem. Without your location I can still go by the time of day: tell me where you are in a few words.")
      },
      { maximumAge: 600_000, timeout: 15_000 },
    )
  }

  async function referenceJob(label: string, start: () => Promise<{ job_id: string }>) {
    await run(label, async () => (await pollJob((await start()).job_id)).result as { message?: string }, (r) => {
      onSay(r?.message ?? "I listened. I'll keep that feeling in mind.")
      setPanel(null)
    })
  }

  return (
    <section aria-label="Start from something around you" className="flex flex-col gap-3">
      <p className="text-xs text-ink-3">Or start from something around you</p>
      <div className="flex flex-wrap gap-2">
        <button onClick={() => picture.current?.click()} disabled={Boolean(working)} className="flex items-center gap-2 rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:border-ink-3 disabled:text-ink-3">
          <ImageIcon className="h-4 w-4" aria-hidden="true" /> A picture
        </button>
        <button onClick={rightNow} disabled={Boolean(working)} className="flex items-center gap-2 rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:border-ink-3 disabled:text-ink-3">
          <CloudSun className="h-4 w-4" aria-hidden="true" /> Right now, where I am
        </button>
        <button onClick={() => setPanel(panel === "song" ? null : "song")} aria-expanded={panel === "song"} disabled={Boolean(working)} className="flex items-center gap-2 rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:border-ink-3 disabled:text-ink-3">
          <Music2 className="h-4 w-4" aria-hidden="true" /> A song I love
        </button>
        <input ref={picture} type="file" accept="image/*" className="hidden" onChange={(e) => onPicture(e.target.files?.[0])} aria-label="Choose a picture" />
      </div>
      <GeminiNotice what="pictures and short clips of your song" />

      {panel === "song" && (
        <div className="flex flex-col gap-4 rounded-md border border-line bg-surface p-4 text-sm">
          <p className="text-ink-2">I&apos;ll listen for how it feels, not to copy it.</p>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              if (named.trim()) void referenceJob("Looking that song up…", () => nameASong(projectId, named.trim()))
            }}
          >
            <input value={named} onChange={(e) => setNamed(e.target.value)} placeholder="Name a song, like Nights by Frank Ocean" aria-label="Name a song" className="min-w-0 flex-1 rounded-md border border-line bg-raised px-3 py-1.5 text-ink" />
            <button type="submit" className="rounded-md border border-line px-3 py-1.5 text-ink hover:border-ink-3">Tell Frank</button>
          </form>

          <div className="flex flex-col gap-2">
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault()
                if (!query.trim()) return
                void run("Searching free music…", () => searchFreeMusic(projectId, query.trim()), (r) => {
                  setTracks(r.tracks)
                  setFreeNote(r.message ?? (r.tracks.length ? null : "Nothing came up for that. Try a feeling, like 'rainy piano'."))
                })
              }}
            >
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Or find free music by feeling: late night soul" aria-label="Find free music by feeling" className="min-w-0 flex-1 rounded-md border border-line bg-raised px-3 py-1.5 text-ink" />
              <button type="submit" className="rounded-md border border-line px-3 py-1.5 text-ink hover:border-ink-3">Find</button>
            </form>
            {freeNote && <p className="text-ink-3">{freeNote}</p>}
            {tracks && tracks.length > 0 && (
              <ul className="flex flex-col gap-1" aria-label="Free music">
                {tracks.map((t) => (
                  <li key={t.id} className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-ink">
                      {t.title} <span className="text-ink-3">by {t.artist}</span>
                    </span>
                    <button onClick={() => void referenceJob("Listening to it…", () => pickFreeMusic(projectId, t.id))} className="shrink-0 rounded-md border border-line px-2 py-0.5 text-ink-2 hover:text-ink">
                      Use this
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-ink-3">Free music from Jamendo, shared by its makers under Creative Commons.</p>
          </div>

          <div className="flex flex-col gap-2">
            <label className="flex items-center gap-2 text-ink-2">
              <input type="checkbox" checked={ownsIt} onChange={(e) => setOwnsIt(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--feel))]" />
              I&apos;m allowed to use this song (I made it, or I own it)
            </label>
            <button
              onClick={() => songFile.current?.click()}
              disabled={!ownsIt || Boolean(working)}
              className="self-start rounded-md border border-line px-3 py-1.5 text-ink hover:border-ink-3 disabled:text-ink-3"
            >
              Use a song file
            </button>
            <input
              ref={songFile}
              type="file"
              accept="audio/*"
              className="hidden"
              aria-label="Choose a song file"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void referenceJob("Listening to it closely…", () => uploadReference(projectId, f))
              }}
            />
            <p className="text-xs text-ink-3">I listen to it once and keep only what I heard. The file itself isn&apos;t stored.</p>
          </div>
        </div>
      )}

      {working && (
        <p className="flex items-center gap-2 text-xs text-ink-3" role="status">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> {working}
        </p>
      )}
    </section>
  )
}
