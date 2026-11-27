"use client"

/**
 * Export Room — the finish line (finish-and-intent spec 11). Before the first download Frank plays the song and
 * asks, in the person's own words, whether it matches what they described. Then the finishing step (ready to
 * share), heard before and after, the download, separate parts, and one optional surprise idea.
 */

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { FrankNote } from "@/components/conversation/FrankNote"
import { PlayButton } from "@/components/audio/PlayButton"
import { SoundShape } from "@/components/audio/SoundShape"
import { createExport, listExports, getDownloadInfo, type ExportRecord } from "@/lib/api/export"
import { listMixVersions, type MixVersion } from "@/lib/api/mix"
import { setActiveBeatVersion } from "@/lib/api/beat"
import {
  answerIntent,
  getIntent,
  makeSurprise,
  separatePartsZip,
  skipSurprise as skipSurpriseApi,
  surpriseOffered,
  type IntentState,
  type SurpriseResult,
} from "@/lib/api/finish"
import { pollJob } from "@/lib/api/jobs"
import { useProjectStore } from "@/store/project"
import { formatTime, useAudio, usePlayback, type Track } from "@/store/audio"
import { Download } from "lucide-react"
import { MatchedFinish, NotesAndCredits } from "@/components/studio/FinishOrgans"
import { cn } from "@/lib/utils"

type Which = "finished" | "as_mixed"

interface Finished {
  exportId: string
  url: string
  beforeUrl: string | null
  waveform: number[]
  onTarget: boolean | null
}

export default function ExportRoomPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.projectId as string
  const { activeState, updateActiveState, currentProject } = useProjectStore()
  const engine = useAudio()

  const [activeMix, setActiveMix] = useState<MixVersion | null>(null)
  const [exports, setExports] = useState<ExportRecord[]>([])
  const [loadError, setLoadError] = useState(false)
  const [intent, setIntent] = useState<IntentState | null>(null)
  const [notYet, setNotYet] = useState(false)
  const [said, setSaid] = useState("")
  const [finished, setFinished] = useState<Finished | null>(null)
  const [which, setWhich] = useState<Which>("finished")
  const [working, setWorking] = useState<string | null>(null)
  const [downloaded, setDownloaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [surpriseState, setSurpriseState] = useState<"hidden" | "offer" | "making" | "ready" | "done">("hidden")
  const [surprise, setSurprise] = useState<SurpriseResult | null>(null)

  useEffect(() => {
    Promise.all([listMixVersions(projectId), listExports(projectId), getIntent(projectId).catch(() => null)])
      .then(([mixes, exps, it]) => {
        const active = mixes.find((m) => m.id === activeState?.active_mix_id) ?? mixes[0] ?? null
        setActiveMix(active)
        setExports(exps)
        setIntent(it)
      })
      .catch(() => setLoadError(true))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  const currentUrl = finished ? (which === "finished" ? finished.url : finished.beforeUrl ?? finished.url) : activeMix?.render_url ?? null

  // One track at a time through the shared engine; switching between "as blended" and "finished" keeps the
  // moment, so the difference is easy to hear.
  const track: Track | null = currentUrl
    ? {
        id: `finish:${currentUrl}`,
        url: currentUrl,
        label: finished ? (which === "finished" ? "The finished song" : "The song as you blended it") : "The song",
        material: "voice",
        onSong: true,
      }
    : null
  const playback = usePlayback(track?.id)
  useEffect(() => {
    const s = useAudio.getState()
    if (track && s.playing && s.track?.id.startsWith("finish:") && s.track.id !== track.id) {
      void s.play(track, { keepPosition: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [track?.id])

  const needsIntentCheck = Boolean(activeMix) && exports.length === 0 && intent !== null && intent.answered !== "yes"

  async function sayYes() {
    await answerIntent(projectId, true)
    setIntent((i) => (i ? { ...i, answered: "yes" } : i))
  }

  async function sayNotYet() {
    setWorking("Listening to what you said…")
    setError(null)
    try {
      const reply = await answerIntent(projectId, false, said)
      if (reply.next === "refine") router.push(`/${projectId}/mix?refine=${encodeURIComponent(reply.concern ?? said)}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Frank couldn't read that just then. Want to try again?")
    } finally {
      setWorking(null)
    }
  }

  async function finish() {
    if (!activeMix) return
    setWorking("Finishing your song: making it ready to share. This usually takes about a minute…")
    setError(null)
    try {
      const { job_id } = await createExport(projectId, activeMix.id, true)
      const done = await pollJob(job_id)
      const r = done.result as { export_id: string; audio_url: string; before_url?: string | null; waveform?: number[]; finish?: { on_target?: boolean } }
      setFinished({ exportId: r.export_id, url: r.audio_url, beforeUrl: r.before_url ?? null, waveform: r.waveform ?? [], onTarget: r.finish?.on_target ?? null })
      setWhich("finished")
      setExports(await listExports(projectId))
      surpriseOffered(projectId).then((s) => setSurpriseState(s.offered ? "done" : "offer")).catch(() => {})
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Frank couldn't finish it just then. Want to try again?")
    } finally {
      setWorking(null)
    }
  }

  async function download() {
    if (!finished) return
    setError(null)
    try {
      let id = finished.exportId
      if (which === "as_mixed") {
        const { job_id } = await createExport(projectId, activeMix!.id, false)
        id = ((await pollJob(job_id)).result as { export_id: string }).export_id
      }
      const info = await getDownloadInfo(projectId, id)
      clickDownload(info.url, info.filename)
      setDownloaded(true)
    } catch {
      setError("Something went wrong preparing your download. Want to try again?")
    }
  }

  async function downloadParts() {
    setWorking("Putting the separate parts together. If the music hasn't been split into parts yet, this takes a few minutes…")
    setError(null)
    try {
      const r = await separatePartsZip(projectId)
      clickDownload(r.zip_url, "separate-parts.zip")
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Frank couldn't put the parts together. Want to try again?")
    } finally {
      setWorking(null)
    }
  }

  async function showSurprise() {
    setSurpriseState("making")
    try {
      setSurprise(await makeSurprise(projectId))
      setSurpriseState("ready")
    } catch (err) {
      setError(err instanceof Error ? err.message : null)
      setSurpriseState("done")
    }
  }

  async function skipSurprise() {
    setSurpriseState("done")
    await skipSurpriseApi(projectId).catch(() => {})
  }

  async function chooseSurprise() {
    if (!surprise) return
    await setActiveBeatVersion(projectId, surprise.beat_version_id)
    updateActiveState({ active_beat_version_id: surprise.beat_version_id })
    router.push(`/${projectId}/mix`)
  }

  function clickDownload(url: string, filename: string) {
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  if (loadError) {
    return (
      <div className="stitch-room flex h-full items-center justify-center px-8">
        <FrankNote problem appearance="room" answers={[{ label: "Try again", onClick: () => window.location.reload() }]}>
          Frank had trouble loading your song just now. Nothing is lost.
        </FrankNote>
      </div>
    )
  }

  if (!activeMix) {
    // Blocked: say what is missing and offer the way there.
    return (
      <div className="stitch-room flex h-full flex-col gap-6 px-10 py-8">
        <div className="flex items-center gap-3 border-b border-line/60 pb-5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-frank shadow-[0_0_12px_rgb(var(--frank)/0.6)]" />
          <h1 className="stitch-title text-ink">Finish</h1>
          <span className="stitch-chip">Last step</span>
        </div>
        <FrankNote appearance="room" roleLabel="Producer Note" answers={[{ label: "Go to Blend", onClick: () => router.push(`/${projectId}/mix`), primary: true }]}>
          Once your voice and the music are blended, come back here to take your song with you.
        </FrankNote>
        <div aria-hidden="true" className="stitch-panel flex h-[120px] items-center rounded-2xl border-dashed px-6">
          <span className="text-base text-ink-3">Your finished song will be here, ready to hear and download.</span>
        </div>
      </div>
    )
  }

  const title = currentProject?.title || "Your song"
  const step = needsIntentCheck ? "ask" : !finished ? "finish" : "download"

  return (
    <div className="stitch-room flex h-full flex-col overflow-y-auto px-10 py-8 [--sweep:var(--voice)]">
      <div className="mx-auto flex w-full max-w-[860px] flex-col gap-6">
        <div className="flex items-end justify-between gap-4 border-b border-line/60 pb-5">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-frank shadow-[0_0_12px_rgb(var(--frank)/0.6)]" />
              <h1 className="stitch-title text-ink">Finish</h1>
              <span className="stitch-chip">Last step</span>
            </div>
            <p className="mt-2 text-sm text-on-surface-variant">A last listen, then it&apos;s yours.</p>
          </div>
        </div>


        <section aria-labelledby="song-name" className="stitch-panel relative flex flex-col gap-5 overflow-hidden p-8">
          <div aria-hidden="true" className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-frank/10 blur-3xl" />
          <div className="relative flex items-center gap-5">
            <PlayButton track={track!} size="stage" keepPosition />
            <div className="min-w-0">
              <span className="stitch-chip">Ready to share</span>
              <h2 id="song-name" className="mt-2 truncate font-written text-[34px] leading-[40px] text-on-surface">
                {title}
              </h2>
              <p className="text-base text-ink-2">
                {finished ? (which === "finished" ? "Finished, ready to share" : "As you blended it") : activeMix.label ?? "The blend in your song"}
                {playback.duration > 0 && <span className="ml-2 tabular-nums">{formatTime(playback.duration)}</span>}
              </p>
            </div>
          </div>
          {finished ? (
            <SoundShape
              points={finished.waveform}
              progress={playback.progress}
              material="voice"
              live={playback.isCurrent}
              label={title}
              onSeek={(f) => (playback.isCurrent ? engine.seekFraction(f) : void engine.play(track!, { atFraction: f }))}
              className="h-24"
            />
          ) : (
            <p className="text-sm text-ink-2">The shape of the song appears here once it's finished.</p>
          )}
          {finished && finished.beforeUrl && (
            <div className="flex flex-wrap items-center gap-3" role="group" aria-label="Compare before and after">
              <span className="text-sm text-ink-2">Hear it</span>
              {(["finished", "as_mixed"] as Which[]).map((w) => (
                <button
                  key={w}
                  aria-pressed={which === w}
                  onClick={() => setWhich(w)}
                  className={cn(
                    "rounded-md border px-3 py-1.5 text-base",
                    which === w ? "border-voice bg-raised text-ink" : "border-line text-ink-2 hover:text-ink",
                  )}
                >
                  {w === "finished" ? "Finished" : "As you blended it"}
                </button>
              ))}
              <span className="text-sm text-ink-2">
                {finished.onTarget === false
                  ? "It's close to the loudness songs usually have, not all the way. Still safe to share."
                  : "The finished one plays as loud as songs on streaming apps, with no harsh peaks."}
              </span>
            </div>
          )}
        </section>
        {/* One step at a time: does it match → finish it → download */}
        {step === "ask" && (
          <FrankNote
            appearance="room"
            roleLabel="Producer Note"
            answers={notYet ? [] : [
              { label: "Yes, that's it", onClick: () => void sayYes(), primary: true },
              { label: "Not yet", onClick: () => setNotYet(true) },
            ]}
          >
            {intent!.question}
          </FrankNote>
        )}
        {step === "ask" && notYet && (
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault()
              void sayNotYet()
            }}
          >
            <label className="text-sm font-medium text-ink-2" htmlFor="what-missing">
              What's missing, in your own words? (You can leave it blank.)
            </label>
            <div className="flex items-end gap-3">
              <input
                 id="what-missing"
                 value={said}
                 disabled={working !== null}
                 onChange={(e) => setSaid(e.target.value)}

                className="max-w-xl flex-1 rounded-md bg-raised px-3 py-2.5 font-written text-[17px] text-words placeholder:font-sans placeholder:text-base placeholder:text-ink-3"
                placeholder="It should feel lonelier…"
                autoFocus
              />
              <button type="submit" disabled={working !== null} className="h-10 rounded-md border border-line bg-raised px-5 text-base text-ink hover:border-ink-3 disabled:opacity-60">
                Find a few ideas
              </button>
            </div>
          </form>
        )}
        {step === "finish" && (
          <FrankNote
            appearance="room"
            roleLabel="Producer Note"
            busy={Boolean(working)}
            aside={working ? undefined : "Frank makes it as loud and even as songs on streaming apps. You'll hear before and after."}
            answers={working ? [] : [{ label: "Finish it, ready to share", onClick: () => void finish(), primary: true }]}
          >
            {working ?? "Happy with how it sounds? Let's finish it."}
          </FrankNote>
        )}
        {step === "download" && (
          <FrankNote
            appearance="room"
            roleLabel="Producer Note"
            busy={Boolean(working)}
            answers={[
              {
                label: which === "finished" ? "Download the finished song" : "Download it as you blended it",
                onClick: () => void download(),
                primary: true,
              },
              { label: "Download separate parts", onClick: () => void downloadParts(), disabled: Boolean(working) },
            ]}
            aside={downloaded && !error ? "It's yours. Good luck with it." : "An MP3 you can share anywhere. Separate parts are each sound on its own, for a friend who mixes."}
          >
            {working ?? (downloaded ? "Downloaded." : "Your song is ready.")}
          </FrankNote>
        )}
        {error && (
          <FrankNote problem appearance="room">
            {error}
          </FrankNote>
        )}

        {step === "download" && (
          <div className="grid max-w-[1000px] gap-4 xl:grid-cols-2">
            <div className="stitch-panel p-5">
              <NotesAndCredits projectId={projectId} onDownload={clickDownload} />
            </div>
            <div className="stitch-panel p-5">
              <MatchedFinish projectId={projectId} mixVersionId={activeMix.id} frankUrl={finished?.url ?? null} />
            </div>
          </div>
        )}

        {surpriseState === "offer" && (
          <FrankNote
            appearance="room"
            roleLabel="One idea"
            answers={[
              { label: "Show me", onClick: () => void showSurprise() },
              { label: "No thanks", onClick: () => void skipSurprise() },
            ]}
          >
            Before you go, I tried one idea. Want to hear it? Your version stays exactly as it is.
          </FrankNote>
        )}
        {surpriseState === "making" && (
          <FrankNote busy appearance="room">
            Making my idea. This takes a few minutes; your song is already safe.
          </FrankNote>
        )}
        {surpriseState === "ready" && surprise && (
          <section aria-label="Frank's idea" className="stitch-panel flex items-center gap-4 p-5">
            <PlayButton track={{ id: `surprise:${surprise.beat_version_id}`, url: surprise.render_url, label: surprise.title, material: "music", onSong: true }} size="card" keepPosition />
            <div className="min-w-0 flex-1">
              <p className="font-written text-xl text-ink">{surprise.title}</p>
              <p className="text-sm text-ink-2">{surprise.plain}</p>
            </div>
            <button onClick={() => void chooseSurprise()} className="rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:border-ink-3">
              Use this one instead
            </button>
            <button onClick={() => setSurpriseState("done")} className="text-sm text-ink-2 hover:text-ink">
              Keep mine
            </button>
          </section>
        )}

        {exports.length > 0 && (
          <section aria-labelledby="past-heading" className="stitch-panel flex flex-col gap-2 p-5">
            <h2 id="past-heading" className="stitch-kicker text-frank-text">
              Past downloads
            </h2>
            <ul className="flex flex-col">
              {exports.map((e) => (
                <li key={e.id} className="border-b border-line last:border-b-0">
                  <button
                    onClick={async () => {
                      const info = await getDownloadInfo(projectId, e.id)
                      clickDownload(info.url, info.filename)
                    }}
                    className="flex w-full items-center justify-between py-2.5 text-left text-base text-ink hover:text-frank"
                  >
                    {new Date(e.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
                    <span className="flex items-center gap-1.5 text-sm text-ink-2">
                      <Download className="h-4 w-4" aria-hidden="true" /> Download again
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  )
}
