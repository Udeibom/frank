"use client"

/**
 * In the Finish room (frankenstein spec 14):
 * - MatchedFinish (6.4): a second finish, matched to how loud, bright and wide a song they pick sounds. Frank's own
 *   finish is kept; the two are played side by side at the same moment.
 * - NotesAndCredits (8.3): "Download the notes" (the music as a file any music app opens) and the song's credits:
 *   who and what made each part, and what to credit when sharing it.
 */

import { useEffect, useRef, useState } from "react"
import { FileMusic, ScrollText, Scale, Loader2 } from "lucide-react"
import { PlayButton } from "@/components/audio/PlayButton"
import { pollJob } from "@/lib/api/jobs"
import { downloadNotes, matchToReference, searchFreeMusic, songCredits } from "@/lib/api/organs"
import type { CreditLine, JamendoTrack } from "@/types/api"

export function MatchedFinish({ projectId, mixVersionId, frankUrl }: { projectId: string; mixVersionId: string; frankUrl: string | null }) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState("")
  const [tracks, setTracks] = useState<JamendoTrack[]>([])
  const [owns, setOwns] = useState(false)
  const [working, setWorking] = useState<string | null>(null)
  const [matched, setMatched] = useState<string | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const file = useRef<HTMLInputElement>(null)

  async function make(source: { file?: File; jamendoTrackId?: string }) {
    setWorking("Finishing it to match that song. This takes a few minutes…")
    setProblem(null)
    try {
      const { job_id } = await matchToReference(projectId, mixVersionId, source)
      const r = (await pollJob(job_id)).result as { audio_url?: string }
      setMatched(r.audio_url ?? null)
    } catch (err) {
      setProblem(err instanceof Error ? err.message : "That didn't work just now.")
    } finally {
      setWorking(null)
    }
  }

  return (
    <section aria-labelledby="matched" className="flex flex-col gap-3 rounded-md border border-line bg-surface p-4">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex items-center gap-2 self-start text-base text-ink">
        <Scale className="h-4 w-4" aria-hidden="true" /> Finish it like a song I love
      </button>
      {open && (
        <>
          <p className="text-sm text-ink-2">I&apos;ll make a second finish that sits as loud, bright and wide as a song you pick. Yours is kept; listen to both.</p>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              if (q.trim()) void searchFreeMusic(projectId, q.trim()).then((r) => setTracks(r.tracks)).catch(() => setTracks([]))
            }}
          >
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find free music by feeling" aria-label="Find free music" className="min-w-0 flex-1 rounded-md border border-line bg-raised px-3 py-1.5 text-sm text-ink" />
            <button type="submit" className="rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:border-ink-3">Find</button>
          </form>
          {tracks.length > 0 && (
            <ul className="flex flex-col gap-1 text-sm">
              {tracks.slice(0, 6).map((t) => (
                <li key={t.id} className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate text-ink">{t.title} <span className="text-ink-3">by {t.artist}</span></span>
                  <button disabled={Boolean(working)} onClick={() => void make({ jamendoTrackId: t.id })} className="rounded-md border border-line px-2 py-0.5 text-ink-2 hover:text-ink">
                    Match this
                  </button>
                </li>
              ))}
            </ul>
          )}
          <label className="flex items-center gap-2 text-sm text-ink-2">
            <input type="checkbox" checked={owns} onChange={(e) => setOwns(e.target.checked)} className="h-4 w-4" />
            Or use a song file I&apos;m allowed to use
          </label>
          {owns && (
            <button onClick={() => file.current?.click()} disabled={Boolean(working)} className="self-start rounded-md border border-line px-3 py-1 text-sm text-ink hover:border-ink-3">Choose the file</button>
          )}
          <input ref={file} type="file" accept="audio/*" className="hidden" aria-label="Song file to match" onChange={(e) => e.target.files?.[0] && void make({ file: e.target.files[0] })} />
          {working && <p className="flex items-center gap-2 text-xs text-ink-3" role="status"><Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> {working}</p>}
          {problem && <p className="text-sm text-problem">{problem}</p>}
          {matched && (
            <div role="group" aria-label="Compare the two finishes" className="flex flex-wrap items-center gap-4">
              {frankUrl && (
                <span className="flex items-center gap-2 text-sm text-ink-2">
                  <PlayButton track={{ id: `finish:${frankUrl}`, url: frankUrl, label: "Frank's finish", material: "music", onSong: true }} size="row" keepPosition /> Frank&apos;s finish
                </span>
              )}
              <span className="flex items-center gap-2 text-sm text-ink-2">
                <PlayButton track={{ id: `matched:${matched}`, url: matched, label: "Matched to your song", material: "music", onSong: true }} size="row" keepPosition /> Matched to your song
              </span>
            </div>
          )}
        </>
      )}
    </section>
  )
}

export function NotesAndCredits({ projectId, onDownload }: { projectId: string; onDownload: (url: string, filename: string) => void }) {
  const [credits, setCredits] = useState<CreditLine[] | null>(null)
  const [showCredits, setShowCredits] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    if (showCredits && credits === null) songCredits(projectId).then((r) => setCredits(r.credits)).catch(() => setCredits([]))
  }, [showCredits, credits, projectId])

  const attributions = (credits ?? []).filter((c) => c.attribution)
  return (
    <section aria-label="The notes and the credits" className="flex flex-col gap-3 rounded-md border border-line bg-surface p-4">
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() =>
            downloadNotes(projectId)
              .then((r) => onDownload(r.url, r.filename))
              .catch((err) => setProblem(err instanceof Error ? err.message : "I couldn't write the notes down just now."))
          }
          className="flex items-center gap-2 rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:border-ink-3"
        >
          <FileMusic className="h-4 w-4" aria-hidden="true" /> Download the notes
        </button>
        <button onClick={() => setShowCredits(!showCredits)} aria-expanded={showCredits} className="flex items-center gap-2 rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:border-ink-3">
          <ScrollText className="h-4 w-4" aria-hidden="true" /> Who made what
        </button>
      </div>
      <p className="text-xs text-ink-3">The notes are the music written down, part by part, for a producer, a band or any music app.</p>
      {problem && <p className="text-sm text-problem">{problem}</p>}
      {showCredits && (
        <div className="flex flex-col gap-2 text-sm">
          <p className="text-ink">Your words, your voice and your choices: you. Frank helped like this:</p>
          {credits === null ? (
            <p className="text-ink-3">Gathering the credits…</p>
          ) : credits.length === 0 ? (
            <p className="text-ink-3">Frank&apos;s own engine made the music; nothing else needs crediting.</p>
          ) : (
            <ul className="list-disc pl-5 text-ink-2">
              {credits.map((c) => (
                <li key={c.organ + (c.attribution ?? "")}>{c.plain}</li>
              ))}
            </ul>
          )}
          {attributions.length > 0 && (
            <>
              <p className="mt-2 text-ink">When you share the song, include this:</p>
              <pre className="whitespace-pre-wrap rounded-md bg-raised p-3 font-sans text-xs text-ink-2">
                {["Made with Frank.", ...attributions.map((c) => c.attribution)].join("\n")}
              </pre>
            </>
          )}
        </div>
      )}
    </section>
  )
}
