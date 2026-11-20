"use client"

/**
 * SongStrip: the song, always visible, in every room (design-and-ui.md).
 *
 * Left to right: the song's name (in the written face), what is in it, which phase it is in; the song's
 * sections with one lane per material (words, feeling, music, voice); the one transport.
 * It is the only place song status is shown. Everything here is read from the shared song record and the
 * AudioEngine; nothing in the strip changes the song except the title and the phase.
 */

import Link from "next/link"
import { useEffect, useMemo, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Pause, Pencil, Play } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatTime, useAudio, type Material } from "@/store/audio"
import { useProjectStore } from "@/store/project"
import { useSongStore } from "@/store/song"
import { useDirections } from "@/store/directions"
import { updateProject } from "@/lib/api/projects"
import { buildStripModel, sectionAt, sectionStart, type LaneState } from "@/lib/songShape"

const LANES: { key: "words" | "feel" | "music" | "voice"; label: string; material: Material; fill: string; ring: string }[] = [
  { key: "words", label: "Words", material: "words", fill: "bg-words", ring: "border-words" },
  { key: "feel", label: "Feeling", material: "feel", fill: "bg-feel", ring: "border-feel" },
  { key: "music", label: "Music", material: "music", fill: "bg-music", ring: "border-music" },
  { key: "voice", label: "Voice", material: "voice", fill: "bg-voice", ring: "border-voice" },
]

function Cell({ state, fill, ring }: { state: LaneState; fill: string; ring: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "block h-2 w-full rounded-[2px]",
        state === "in_use" && fill,
        state === "tried" && cn("border", ring),
        state === "none" && "border border-dashed border-ink-3/70",
      )}
    />
  )
}

const STATE_WORDS: Record<LaneState, string> = { in_use: "in use", tried: "tried, not kept", none: "nothing yet" }

export function SongStrip({ projectId, onStart }: { projectId: string; onStart: () => void }) {
  const router = useRouter()
  const { currentProject, revision, updateProjectTitle } = useProjectStore()
  const { record, load: loadSong, setPhase } = useSongStore()
  const directions = useDirections((s) => s.directions)
  const loadDirections = useDirections((s) => s.load)
  const { track, playing, position, duration, loading, toggle, resume, pause, seek, seekFraction } = useAudio()

  // The strip is where the song is read from, so it keeps the shared record fresh whenever the studio changes.
  useEffect(() => {
    void loadSong(projectId)
  }, [projectId, revision, loadSong])
  // The directions only change through their own store, so one load per song is enough.
  useEffect(() => {
    void loadDirections(projectId)
  }, [projectId, loadDirections])

  const tried = directions.some((d) => d.status === "ready")
  const model = useMemo(() => buildStripModel(record, tried), [record, tried])

  // ─── Title ───
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")
  const titleRef = useRef<HTMLInputElement>(null)
  const title = currentProject?.title ?? ""
  useEffect(() => {
    if (editing) titleRef.current?.select()
  }, [editing])

  async function saveTitle() {
    setEditing(false)
    const next = draft.trim() || "Untitled song"
    if (next === title) return
    updateProjectTitle(next)
    try {
      await updateProject(projectId, { title: next })
    } catch {
      updateProjectTitle(title)
    }
  }

  // ─── What the playhead means ───
  const onSong = Boolean(track?.onSong) && model.fromMusic && duration > 0
  const fraction = onSong ? Math.min(1, position / duration) : 0
  const playingSection = onSong ? sectionAt(model.sections, fraction) : -1

  // ─── Phase ───
  const melody = record?.facets.melody as { confirmed?: boolean } | null | undefined
  const draftReady = Boolean(record?.beat) && (Boolean(record?.vocal) || Boolean(melody?.confirmed))

  // ─── Keyboard: Space plays/pauses, arrows move, 1-6 jump rooms. Never while typing or on a control that uses the key. ───
  useEffect(() => {
    const slugs = ["idea", "feel", "beat", "voice", "mix", "export"]
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const t = e.target instanceof HTMLElement ? e.target : null
      const tag = t?.tagName
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || Boolean(t?.isContentEditable)
      if (typing) return
      const onControl = tag === "BUTTON" || tag === "A" || t?.getAttribute("role") === "slider"
      if (e.key === " " && !onControl) {
        if (!useAudio.getState().track) return
        e.preventDefault()
        if (useAudio.getState().playing) pause()
        else resume()
      } else if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && !onControl) {
        const s = useAudio.getState()
        if (!s.track) return
        e.preventDefault()
        seek(s.position + (e.key === "ArrowRight" ? 5 : -5))
      } else if (/^[1-6]$/.test(e.key) && !onControl) {
        router.push(`/${projectId}/${slugs[Number(e.key) - 1]}`)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [pause, resume, seek, router, projectId])

  // Until this song's record has arrived, say so: never claim an empty song that may not be empty.
  const known = Boolean(record && record.project_id === projectId && currentProject?.id === projectId)
  const nowPlaying = track
    ? `${loading && !playing ? "Getting ready" : playing ? "Playing" : "Paused"}: ${track.label}`
    : known
      ? model.summary
      : "Opening your song…"

  return (
    <header aria-label="Your song" className="flex h-24 shrink-0 border-b border-line bg-surface">
      <Link
        href="/songs"
        aria-label="All your songs"
        className="flex w-[76px] shrink-0 items-center justify-center border-r border-line text-xs font-semibold tracking-[0.14em] text-ink-3 hover:text-ink"
      >
        FRANK
      </Link>

      {/* The song */}
      <div className="flex w-[300px] shrink-0 flex-col justify-center gap-0.5 px-5">
        {editing ? (
          <input
            ref={titleRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={saveTitle}
            onKeyDown={(e) => {
              if (e.key === "Enter") void saveTitle()
              if (e.key === "Escape") setEditing(false)
            }}
            aria-label="Song name"
            className="w-full rounded-sm bg-raised px-1 font-written text-2xl text-ink outline-none"
          />
        ) : (
          <button
            onClick={() => {
              setDraft(title || "Untitled song")
              setEditing(true)
            }}
            aria-label={`Song name: ${title || "Untitled song"}. Press to rename`}
            className="group flex min-w-0 items-center gap-2 text-left"
          >
            <span className="truncate font-written text-2xl text-ink" title={title || undefined}>{known ? title || "Untitled song" : title || " "}</span>
            <Pencil aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-ink-3 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100" />
          </button>
        )}
        <p className="truncate text-sm text-ink-2" aria-live="polite">
          {nowPlaying}
        </p>
        {known && model.empty ? (
          <button
            onClick={onStart}
            className="mt-1 w-fit rounded-md border border-line bg-raised px-3 py-1 text-sm text-ink hover:border-ink-3"
          >
            Start with whatever you have
          </button>
        ) : (
          record &&
          (draftReady || record.phase === "refining") && (
            <div role="group" aria-label="Where the song is" className="mt-0.5 flex w-fit gap-px overflow-hidden rounded-md border border-line text-xs">
              <button
                aria-pressed={record.phase === "creating"}
                onClick={() => void setPhase(projectId, "creating")}
                className={cn("px-2.5 py-0.5", record.phase === "creating" ? "bg-raised text-ink" : "text-ink-3 hover:text-ink")}
              >
                Adding things
              </button>
              <button
                aria-pressed={record.phase === "refining"}
                disabled={!draftReady && record.phase !== "refining"}
                title={draftReady || record.phase === "refining" ? undefined : "Once the song has music and a voice or a tune"}
                onClick={() => void setPhase(projectId, "refining")}
                className={cn(
                  "px-2.5 py-0.5",
                  record.phase === "refining" ? "bg-raised text-ink" : "text-ink-3 hover:text-ink",
                  "disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:text-ink-3",
                )}
              >
                Polishing
              </button>
            </div>
          )
        )}
      </div>

      {/* The song's shape: sections and a lane for each thing it is made of */}
      <div className="flex min-w-0 flex-1 items-center gap-3 border-l border-line px-4">
        <div aria-hidden="true" className="flex shrink-0 flex-col pt-4 text-xs leading-[13px] text-ink-3">
          {LANES.map((l) => (
            <span key={l.key} className="flex h-[13px] items-center gap-1.5">
              <span className={cn("h-1.5 w-1.5 rounded-full", l.fill)} />
              {l.label}
            </span>
          ))}
        </div>

        <div role="group" aria-label="The song, section by section" className="relative min-w-0 flex-1">
          {model.sections.length === 0 ? (
            <div className="flex flex-col">
              <span className="h-4 text-xs leading-4 text-ink-3">
                {!known ? "" : model.empty ? "Your song takes shape here" : "Sections appear as the song takes shape"}
              </span>
              <div className="flex flex-col gap-[5px]">
                {LANES.map((l) => (
                  <Cell
                    key={l.key}
                    state={l.key === "words" ? (record?.lyrics?.trim() ? "in_use" : "none") : model[l.key]}
                    fill={l.fill}
                    ring={l.ring}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="flex gap-0.5">
              {model.sections.map((s, i) => {
                const seekable = onSong
                const states: Record<string, LaneState> = {
                  words: s.words ? "in_use" : "none",
                  feel: model.feel,
                  music: model.music,
                  voice: model.voice,
                }
                return (
                  <button
                    key={s.key}
                    type="button"
                    disabled={!seekable}
                    onClick={() => seekFraction(sectionStart(model.sections, i))}
                    style={{ flexGrow: s.weight, flexBasis: 0 }}
                    aria-label={`${s.name || "Section"}: ${LANES.map((l) => `${l.label.toLowerCase()} ${STATE_WORDS[states[l.key]]}`).join(", ")}${
                      seekable ? ". Press to jump here" : ""
                    }`}
                    className={cn(
                      "flex min-w-0 flex-col rounded-[2px] text-left",
                      i === playingSection ? "bg-raised" : seekable ? "hover:bg-raised" : "",
                      "disabled:cursor-default",
                    )}
                  >
                    <span className="h-4 truncate text-xs leading-4 text-ink-3">{s.name}</span>
                    <span className="flex flex-col gap-[5px]">
                      {LANES.map((l) => (
                        <Cell key={l.key} state={states[l.key]} fill={l.fill} ring={l.ring} />
                      ))}
                    </span>
                  </button>
                )
              })}
              {onSong && (
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute -bottom-1 -top-1 w-0.5 bg-frank"
                  style={{ left: `${fraction * 100}%` }}
                />
              )}
            </div>
          )}
        </div>
      </div>

      {/* The one transport */}
      <div className="flex w-[208px] shrink-0 items-center gap-3 border-l border-line px-5">
        <button
          type="button"
          disabled={!track}
          onClick={() => (playing ? pause() : track ? void toggle(track) : undefined)}
          aria-label={track ? `${playing ? "Pause" : "Play"} the song player: ${track.label}` : "Nothing is playing"}
          className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-full border transition-colors",
            playing ? "border-frank bg-frank text-ground" : track ? "border-ink-3 text-ink hover:bg-raised" : "border-line text-ink-3",
          )}
        >
          {playing ? <Pause className="h-5 w-5" aria-hidden="true" /> : <Play className="h-5 w-5 translate-x-px" aria-hidden="true" />}
        </button>
        <div className="min-w-0 text-sm tabular-nums leading-[18px] text-ink-2">
          <span className="block text-ink">{formatTime(track ? position : 0)}</span>
          <span className="block">{track ? `of ${formatTime(duration)}` : loading ? "getting ready" : "nothing playing"}</span>
        </div>
      </div>
    </header>
  )
}
