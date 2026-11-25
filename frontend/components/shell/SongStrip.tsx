"use client"

/**
 * SongStrip: the song, always visible, in every room (design-and-ui.md).
 *
 * 48px title bar: song name (editable, font-written italic) on the left,
 * playback transport (play/pause + time) in the centre,
 * a row of four material-colour cells (Words / Feeling / Music / Voice) showing what
 * this song has built so far, and "All songs" link on the right.
 *
 * All JS logic, state, keyboard shortcuts, and hooks are preserved exactly.
 */

import Link from "next/link"
import { useEffect, useMemo, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Pause, Pencil, Play } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatTime, useAudio } from "@/store/audio"
import { useProjectStore } from "@/store/project"
import { useSongStore } from "@/store/song"
import { useDirections } from "@/store/directions"
import { updateProject } from "@/lib/api/projects"
import { buildStripModel, sectionAt, sectionStart, type LaneState } from "@/lib/songShape"


function Cell({ state, fill, ring }: { state: LaneState; fill: string; ring: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "block h-1.5 w-full rounded-[2px] transition-colors duration-300",
        state === "in_use" && fill,
        state === "tried"  && cn("border", ring, "opacity-70"),
        state === "none"   && "border border-dashed border-line",
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

  return (
    <header
      aria-label="Your song"
      className="flex h-12 shrink-0 flex-col border-b border-line bg-ground"
    >
      {/* Main row: title / transport / all-songs */}
      <div className="flex flex-1 items-center gap-4 px-4">
        {/* Song title — editable inline */}
        <div className="flex min-w-0 flex-1 items-center gap-2">
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
              className="min-w-0 max-w-xs rounded-md bg-raised px-1.5 font-written italic text-base text-ink outline-none border border-frank/40"
            />
          ) : (
            <button
              onClick={() => {
                setDraft(title || "Untitled song")
                setEditing(true)
              }}
              aria-label={`Song name: ${title || "Untitled song"}. Press to rename`}
              className="group flex min-w-0 items-center gap-1.5 text-left"
            >
              <span
                className="truncate font-written italic text-base text-ink"
                title={title || undefined}
              >
                {known ? title || "Untitled song" : title || "\u00a0"}
              </span>
              <Pencil
                aria-hidden="true"
                className="h-3 w-3 shrink-0 text-ink-3 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
              />
            </button>
          )}
        </div>

        {/* Transport — play/pause + time */}
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            disabled={!track}
            onClick={() => (playing ? pause() : track ? void toggle(track) : undefined)}
            aria-label={
              track
                ? `${playing ? "Pause" : "Play"} the song player: ${track.label}`
                : "Nothing is playing"
            }
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-full border transition-all duration-150",
              playing
                ? "border-frank bg-frank text-ground shadow-play-bloom"
                : track
                  ? "border-line text-ink hover:border-frank/50 hover:bg-raised"
                  : "border-line text-ink-3",
            )}
          >
            {playing ? (
              <Pause className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <Play className="h-3.5 w-3.5 translate-x-px" aria-hidden="true" />
            )}
          </button>
          {track && (
            <span className="font-mono text-code tabular-nums text-ink-3">
              {formatTime(position)} / {formatTime(duration)}
            </span>
          )}
        </div>

        {/* Right: back to songs */}
        <div className="flex shrink-0 items-center">
          <Link
            href="/songs"
            className="text-xs text-ink-3 hover:text-ink transition-colors"
          >
            All songs
          </Link>
        </div>
      </div>

      {/* Section cells row — four lanes × sections, showing what this song has built.
          Words: per-section coverage. Feeling/Music/Voice: overall model state repeated across sections.
          aria-label describes the overall lane states so screen readers get a useful summary. */}
      {model.sections.length > 0 && (
        <div
          aria-label={[
            "Song progress —",
            `Words: ${model.sections.filter((s) => s.words).length} of ${model.sections.length} sections covered`,
            `Feeling: ${STATE_WORDS[model.feel]}`,
            `Music: ${STATE_WORDS[model.music]}`,
            `Voice: ${STATE_WORDS[model.voice]}`,
          ].join("; ")}
          className="flex items-end gap-px px-4 pb-0.5"
        >
          {/* Words lane — per section */}
          <div className="flex flex-1 gap-px">
            {model.sections.map((sec, i) => (
              <Cell
                key={i}
                state={sec.words ? "in_use" : "none"}
                fill="bg-words"
                ring="border-words"
              />
            ))}
          </div>
          {/* Feel lane — global model state across every section */}
          <div className="flex flex-1 gap-px">
            {model.sections.map((_, i) => (
              <Cell key={i} state={model.feel} fill="bg-feel" ring="border-feel" />
            ))}
          </div>
          {/* Music lane — global model state */}
          <div className="flex flex-1 gap-px">
            {model.sections.map((_, i) => (
              <Cell key={i} state={model.music} fill="bg-music" ring="border-music" />
            ))}
          </div>
          {/* Voice lane — global model state */}
          <div className="flex flex-1 gap-px">
            {model.sections.map((_, i) => (
              <Cell key={i} state={model.voice} fill="bg-voice" ring="border-voice" />
            ))}
          </div>
        </div>
      )}
    </header>
  )
}
