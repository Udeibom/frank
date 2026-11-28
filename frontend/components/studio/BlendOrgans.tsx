"use client"

/**
 * Three of Frank's organs in the Blend room (frankenstein spec 14):
 * - ListenPanel (2.3): Frank listens to the song like a person would (Gemini), with its own measurements beside;
 *   a note the measurements confirm can go straight to "fix it"; the rest are said as "I think".
 * - AtmospherePanel (3.7): a real recorded sound, or one made from the song's feeling, as one removable layer.
 * - ConductPanel (8.5): raise or lower a hand in front of the camera to set a part's level. The camera picture is
 *   read in the browser by MediaPipe and never leaves it; no sound is processed.
 */

import { useEffect, useRef, useState } from "react"
import { Ear, Waves, Hand, Loader2 } from "lucide-react"
import { pollJob } from "@/lib/api/jobs"
import { addAtmosphere, listenToSong, switchAtmosphere } from "@/lib/api/organs"
import { GeminiNotice } from "@/components/studio/GeminiNotice"
import type { HeardByFrank } from "@/types/api"
import { PART_NAMES } from "@/lib/api/finish"

export function ListenPanel({ projectId, onFix }: { projectId: string; onFix: (concern: string) => void }) {
  const [working, setWorking] = useState(false)
  const [heard, setHeard] = useState<HeardByFrank | null>(null)
  const [plain, setPlain] = useState<string[]>([])
  const [problem, setProblem] = useState<string | null>(null)

  async function listen() {
    setWorking(true)
    setProblem(null)
    try {
      const { job_id } = await listenToSong(projectId)
      const done = await pollJob(job_id)
      const r = done.result as { heard?: HeardByFrank | null; findings?: { findings?: { plain: string }[] } }
      setHeard(r.heard ?? null)
      setPlain((r.findings?.findings ?? []).map((f) => f.plain).slice(0, 3))
    } catch (err) {
      setProblem(err instanceof Error ? err.message : "I couldn't listen just now.")
    } finally {
      setWorking(false)
    }
  }

  return (
    <section aria-labelledby="listen-frank" className="flex flex-col gap-3 rounded-md border border-line bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 id="listen-frank" className="flex items-center gap-2 text-base text-ink">
          <Ear className="h-4 w-4" aria-hidden="true" /> Have Frank listen
        </h2>
        <button onClick={() => void listen()} disabled={working} className="flex min-h-11 items-center rounded-md border border-line px-3 py-1 text-sm text-ink hover:border-ink-3 disabled:text-ink-3">
          {working ? "Listening…" : heard || plain.length ? "Listen again" : "Listen"}
        </button>
      </div>
      <p className="text-sm text-ink-2">Frank listens to the whole song and tells you, in plain words, the few things he would change.</p>
      <GeminiNotice what="a short clip of your song" />
      {problem && <p className="text-sm text-problem">{problem}</p>}
      {heard?.heard && <p className="font-written text-lg text-ink">{heard.heard}</p>}
      {heard && heard.notes.length > 0 && (
        <ul className="flex flex-col gap-2">
          {heard.notes.map((n) => (
            <li key={n.plain} className="flex items-start justify-between gap-3 text-sm">
              <span className="text-ink-2">
                {n.confirmed ? "" : "I think "}
                <span className="text-ink">{n.confirmed ? n.plain : n.plain.charAt(0).toLowerCase() + n.plain.slice(1)}</span>
                {n.confirmed && <span className="ml-1 text-ink-3">(my measurements agree)</span>}
              </span>
              {n.confirmed && (
                <button onClick={() => onFix(n.plain)} className="shrink-0 rounded-md border border-line px-2 py-0.5 text-ink-2 hover:text-ink">
                  Fix this
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {!heard && plain.length > 0 && (
        <ul className="list-disc pl-5 text-sm text-ink-2">
          {plain.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      {heard && heard.notes.length === 0 && plain.length === 0 && <p className="text-sm text-ink-2">Nothing stands out to me. It&apos;s yours to judge now.</p>}
    </section>
  )
}

export function AtmospherePanel({ projectId, current, onDone }: { projectId: string; current?: { enabled?: boolean; plain?: string } | null; onDone: () => void }) {
  const [working, setWorking] = useState<string | null>(null)
  const [problem, setProblem] = useState<string | null>(null)

  async function run(label: string, start: () => Promise<{ job_id: string }>) {
    setWorking(label)
    setProblem(null)
    try {
      await pollJob((await start()).job_id)
      onDone()
    } catch (err) {
      setProblem(err instanceof Error ? err.message : "That didn't work just now.")
    } finally {
      setWorking(null)
    }
  }

  return (
    <section aria-labelledby="atmo" className="flex flex-col gap-3 rounded-md border border-line bg-surface p-4">
      <h2 id="atmo" className="flex items-center gap-2 text-base text-ink">
        <Waves className="h-4 w-4" aria-hidden="true" /> A place around the song
      </h2>
      <p className="text-sm text-ink-2">
        {current?.plain && current.enabled !== false
          ? `${current.plain}. It sits quietly under everything.`
          : "Rain on a window, a city at night, an old record: a real sound under the song, from its feeling."}
      </p>
      <div className="flex flex-wrap gap-2">
        <button disabled={Boolean(working)} onClick={() => void run("Finding a real sound…", () => addAtmosphere(projectId, "recorded"))} className="flex min-h-11 items-center rounded-md border border-line px-3 py-1 text-sm text-ink hover:border-ink-3 disabled:text-ink-3">
          {current?.plain ? "Try another real sound" : "Add a real sound"}
        </button>
        <button disabled={Boolean(working)} onClick={() => void run("Making a sound from the feeling…", () => addAtmosphere(projectId, "generated"))} className="flex min-h-11 items-center rounded-md border border-line px-3 py-1 text-sm text-ink-2 hover:text-ink disabled:text-ink-3">
          Make one from the feeling
        </button>
        {current?.plain && (
          <button
            disabled={Boolean(working)}
            onClick={() => void run(current.enabled === false ? "Putting it back…" : "Taking it out…", () => switchAtmosphere(projectId, current.enabled === false))}
            className="flex min-h-11 items-center rounded-md border border-line px-3 py-1 text-sm text-ink-2 hover:text-ink disabled:text-ink-3"
          >
            {current.enabled === false ? "Put it back" : "Take it out"}
          </button>
        )}
      </div>
      {working && (
        <p className="flex items-center gap-2 text-xs text-ink-3" role="status">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> {working}
        </p>
      )}
      {problem && <p className="text-sm text-problem">{problem}</p>}
    </section>
  )
}

const WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm"
const MODEL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

/** Hand height (0 top .. 1 bottom of the picture) to a level change in loudness steps, -9 .. +9. */
export function handToLevel(y: number): number {
  const clamped = Math.max(0.15, Math.min(0.85, y))
  return Math.round(((0.5 - clamped) / 0.35) * 9)
}

export function ConductPanel({ parts, onSet }: { parts: string[]; onSet: (part: string, deltaDb: number) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [on, setOn] = useState(false)
  const [part, setPart] = useState(parts[0] ?? "drums")
  const [level, setLevel] = useState<number | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const stopRef = useRef<() => void>(() => {})

  useEffect(() => () => stopRef.current(), [])

  async function start() {
    setProblem(null)
    try {
      const { FilesetResolver, HandLandmarker } = await import("@mediapipe/tasks-vision")
      const files = await FilesetResolver.forVisionTasks(WASM)
      const hands = await HandLandmarker.createFromOptions(files, { baseOptions: { modelAssetPath: MODEL }, runningMode: "VIDEO", numHands: 1 })
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: false })
      if (!video.current) return
      video.current.srcObject = stream
      await video.current.play()
      setOn(true)
      let raf = 0
      const tick = () => {
        if (!video.current) return
        const res = hands.detectForVideo(video.current, performance.now())
        const wrist = res.landmarks?.[0]?.[9]           // the middle of the palm
        setLevel(wrist ? handToLevel(wrist.y) : null)
        raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
      stopRef.current = () => {
        cancelAnimationFrame(raf)
        stream.getTracks().forEach((t) => t.stop())
        hands.close()
        setOn(false)
      }
    } catch {
      setProblem("I couldn't use the camera. Check your browser let me, or use the louder and softer buttons instead.")
    }
  }

  return (
    <section aria-labelledby="conduct" className="flex flex-col gap-3 rounded-md border border-line bg-surface p-4">
      <h2 id="conduct" className="flex items-center gap-2 text-base text-ink">
        <Hand className="h-4 w-4" aria-hidden="true" /> Conduct it
      </h2>
      <p className="text-sm text-ink-2">Raise your hand to bring a part up, lower it to bring it down, then keep the level. Your camera stays on this computer.</p>
      <div className="flex flex-wrap items-center gap-2">
        <select value={part} onChange={(e) => setPart(e.target.value)} aria-label="Which part to conduct" className="min-h-11 rounded-md border border-line bg-raised px-2 py-1 text-sm text-ink">
          {parts.map((p) => (
            <option key={p} value={p}>
              {PART_NAMES[p] ?? p}
            </option>
          ))}
        </select>
        {!on ? (
          <button onClick={() => void start()} className="rounded-md border border-line px-3 py-1 text-sm text-ink hover:border-ink-3">Start the camera</button>
        ) : (
          <>
            <button
              disabled={level === null || level === 0}
              onClick={() => {
                if (level) onSet(part, level)
                stopRef.current()
              }}
              className="flex min-h-11 items-center rounded-md border border-line px-3 py-1 text-sm text-ink hover:border-ink-3 disabled:text-ink-3"
            >
              Keep this level
            </button>
            <button onClick={() => stopRef.current()} className="text-sm text-ink-2 hover:text-ink">Stop</button>
          </>
        )}
      </div>
      <div className={on ? "flex items-center gap-4" : "hidden"}>
        <video ref={video} muted playsInline className="h-24 w-32 -scale-x-100 rounded-sm bg-raised object-cover" aria-label="Your camera" />
        <p className="text-sm text-ink" role="status" aria-live="polite">
          {level === null ? "Show me your hand." : level === 0 ? "As it is." : level > 0 ? `Louder by ${level}.` : `Softer by ${-level}.`}
        </p>
      </div>
      {problem && <p className="text-sm text-problem">{problem}</p>}
    </section>
  )
}
