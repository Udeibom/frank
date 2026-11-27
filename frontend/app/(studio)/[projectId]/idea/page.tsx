"use client"

/**
 * Words (the Idea Room): where a song starts.
 *
 * The stage is a page: the person's words in the written face at reading width, with their drafts and the
 * sections Frank can see in the margin. Ways to catch an idea (read my words, hum or speak) are on the stage.
 * Frank's suggestions arrive in the panel as words you can add, never as replacements.
 */

import { useEffect, useState, useCallback, useRef } from "react"
import { useParams } from "next/navigation"
import { ListMusic } from "lucide-react"
import { WordsFeel } from "@/components/studio/WordsFeel"
import { LyricsEditor } from "@/components/studio/LyricsEditor"
import { LyricsVersionHistory } from "@/components/studio/LyricsVersionHistory"
import { VoiceMemoButton } from "@/components/studio/VoiceMemoButton"
import { ReadWordsButton } from "@/components/studio/ReadWordsButton"
import { ConversationPanel, type ChatTurn } from "@/components/conversation/ConversationPanel"
import { FrankNote } from "@/components/conversation/FrankNote"
import { ChangeLine } from "@/components/conversation/ChangeLine"
import { listLyricsVersions, setActiveLyrics } from "@/lib/api/lyrics"
import { sendIdeaMessage } from "@/lib/api/conversation"
import { updateProject } from "@/lib/api/projects"
import { lyricHeadings } from "@/lib/songShape"
import { useProjectStore } from "@/store/project"
import { useSongStore } from "@/store/song"
import type { LyricsVersion } from "@/types/project"
import type { ConversationMessage } from "@/types/api"

const UNTITLED = /^untitled song$/i

/** The first line of the words that isn't a section heading: what the song might be called. */
function suggestedTitle(words: string): string | null {
  for (const raw of words.split("\n")) {
    const line = raw.trim()
    if (!line) continue
    if (lyricHeadings(line).length) continue
    const clean = line.replace(/[.,;:!?]+$/, "")
    return clean.length > 60 ? `${clean.slice(0, 57).trimEnd()}…` : clean
  }
  return null
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

const SECTION_HEADING = /^\s*[\[(]?\s*(intro|verse|pre[\s-]?chorus|chorus|hook|refrain|bridge|outro)\b/i

interface SectionSpan {
  name: string
  range: string
  chorus: boolean
}

function sectionSpans(words: string): SectionSpan[] {
  const result: SectionSpan[] = []
  let current: { name: string; start: number; end: number; chorus: boolean } | null = null
  let lyricLine = 0
  const flush = () => {
    if (!current) return
    result.push({
      name: current.name,
      range: current.start === current.end ? `Line ${current.start}` : `Lines ${current.start}–${current.end}`,
      chorus: current.chorus,
    })
  }
  for (const raw of words.split("\n")) {
    const line = raw.trim()
    if (!line) continue
    const heading = SECTION_HEADING.exec(line)
    if (heading) {
      flush()
      const kind = heading[1].toLowerCase().replace(/[\s-]/g, "")
      current = {
        name: capitalise(line),
        start: lyricLine + 1,
        end: lyricLine,
        chorus: kind === "chorus" || kind === "hook" || kind === "refrain",
      }
      continue
    }
    lyricLine += 1
    if (current) current.end = lyricLine
  }
  flush()
  return result
}

export default function WordsPage() {
  const params = useParams()
  const projectId = params.projectId as string
  const { activeState, currentProject, updateProjectTitle } = useProjectStore()
  const loadSong = useSongStore((s) => s.load)

  const [versions, setVersions] = useState<LyricsVersion[]>([])
  const [editorContent, setEditorContent] = useState("")
  const [liveWords, setLiveWords] = useState("")
  const [loaded, setLoaded] = useState(false)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [isThinking, setIsThinking] = useState(false)
  const [titleOffer, setTitleOffer] = useState<string | null>(null)
  const declinedTitle = useRef(false)

  // Live references the conversation reads at send time
  const currentLyricsRef = useRef("")
  const selectedTextRef = useRef<string | undefined>(undefined)
  const historyRef = useRef<ConversationMessage[]>([])

  // Load the drafts on entry and put the one in use on the page (the active pointer, not just the newest).
  useEffect(() => {
    listLyricsVersions(projectId)
      .then((vs) => {
        setVersions(vs)
        const activeId = useProjectStore.getState().activeState?.active_lyrics_id
        const active = vs.find((v) => v.id === activeId) ?? vs[0]
        if (active) {
          setEditorContent(active.content)
          setLiveWords(active.content)
          currentLyricsRef.current = active.content
        }
      })
      .finally(() => setLoaded(true))
  }, [projectId])

  const refreshVersions = useCallback(async () => {
    setVersions(await listLyricsVersions(projectId))
  }, [projectId])

  function handleContentChange(content: string) {
    currentLyricsRef.current = content
    setLiveWords(content)
  }

  function handleVersionSaved(_id: string, content: string) {
    void refreshVersions()
    // The song is still called "Untitled Song": offer the first line (project-layer.md, "Naming").
    if (!declinedTitle.current && UNTITLED.test(useProjectStore.getState().currentProject?.title ?? "")) {
      const t = suggestedTitle(content)
      if (t) setTitleOffer(capitalise(t))
    }
  }

  async function acceptTitle() {
    if (!titleOffer) return
    const before = currentProject?.title ?? "Untitled Song"
    const next = titleOffer
    setTitleOffer(null)
    updateProjectTitle(next)
    try {
      await updateProject(projectId, { title: next })
      sayAsFrank("", <ChangeLine material="words">The song is called “{next}”. Rename it any time from its name at the top.</ChangeLine>)
    } catch {
      updateProjectTitle(before)
      sayAsFrank("I couldn't rename the song just now. You can try again from its name at the top.")
    }
  }

  async function handleRestore(version: LyricsVersion) {
    setEditorContent(version.content)
    setLiveWords(version.content)
    currentLyricsRef.current = version.content
    await setActiveLyrics(projectId, version.id)
    useProjectStore.getState().updateActiveState({ active_lyrics_id: version.id })
    await refreshVersions()
    sayAsFrank("", <ChangeLine material="words">An earlier draft is back on the page. The newer ones are kept.</ChangeLine>)
  }

  function addToEditor(content: string, sectionLabel?: string) {
    const prefix = currentLyricsRef.current.trim() ? "\n\n" : ""
    const section = sectionLabel ? `${sectionLabel}\n` : ""
    const next = currentLyricsRef.current + prefix + section + content
    setEditorContent(next)
    setLiveWords(next)
    currentLyricsRef.current = next
  }

  /** Frank speaks in the conversation, and remembers having said it. */
  function sayAsFrank(content: string, actionBlock?: React.ReactNode) {
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content, actionBlock }])
    if (content) historyRef.current.push({ role: "assistant", content })
  }

  async function handleSend(message: string) {
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "user", content: message }])
    historyRef.current.push({ role: "user", content: message })
    setIsThinking(true)
    try {
      const res = await sendIdeaMessage(projectId, {
        message,
        currentLyrics: currentLyricsRef.current,
        selectedText: selectedTextRef.current,
        history: historyRef.current.slice(0, -1),
      })
      void loadSong(projectId)
      const suggestion = res.actions.find((a) => a.type === "suggest_lyrics")
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: res.message,
          actionBlock: suggestion ? (
            <SuggestionBlock
              content={String(suggestion.params.content ?? "")}
              sectionLabel={suggestion.params.section_label ? String(suggestion.params.section_label) : undefined}
              onAdd={(c, s) => addToEditor(c, s)}
            />
          ) : undefined,
        },
      ])
      historyRef.current.push({ role: "assistant", content: res.message })
      selectedTextRef.current = undefined
    } catch {
      setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content: "Frank got distracted for a second. Try saying that again?" }])
    } finally {
      setIsThinking(false)
    }
  }

  const activeVersionId = activeState?.active_lyrics_id ?? versions[0]?.id ?? null
  const sections = sectionSpans(liveWords)
  const hasWords = liveWords.trim().length > 0
  const missingSections = [
    { label: "Pre-chorus", found: sections.some((s) => /pre-?chorus/i.test(s.name)) },
    { label: "Bridge", found: sections.some((s) => /bridge/i.test(s.name)) },
    { label: "Outro", found: sections.some((s) => /outro/i.test(s.name)) },
  ].filter((s) => !s.found)

  // ─── What Frank is saying on the stage ───
  let note: React.ReactNode
  let answers: { label: string; onClick: () => void; primary?: boolean }[] = []
  if (titleOffer) {
    note = <>Want to call the song “{titleOffer}”?</>
    answers = [
      { label: "Yes, call it that", onClick: acceptTitle, primary: true },
      {
        label: "Not now",
        onClick: () => {
          declinedTitle.current = true
          setTitleOffer(null)
        },
      },
    ]
  } else if (!hasWords) {
    note = "Write anything: a line, a feeling, a chorus. Or say it out loud and I'll write it down."
  } else {
    note = "Select a line and ask me for a rhyme or another way to say it. I'll offer, never replace."
  }

  return (
    <div className="words-design flex h-full">
      <div className="room-words flex min-w-0 flex-1 flex-col gap-6 overflow-y-auto px-6 py-6">
        <header className="mx-auto flex w-full max-w-[1020px] flex-col justify-between gap-4 border-b border-line/50 pb-4 md:flex-row md:items-end">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-words shadow-[0_0_8px_rgba(244,63,94,0.4)]" />
              <h1 className="font-written text-3xl font-normal tracking-tight text-on-surface">Words</h1>
              <span className="text-code rounded bg-surface-high px-1 py-0.5 uppercase text-on-surface-variant">Room 01</span>
            </div>
            <p className="text-sm text-on-surface-variant">Write your song in plain language. Frank listens, catches rhymes, and never overwrites without asking.</p>
          </div>
        </header>

        <div className="mx-auto flex w-full max-w-[1020px] flex-col gap-6">
          <FrankNote answers={answers} material="words" appearance="room" roleLabel="Lyric Companion">
            {note}
          </FrankNote>

          <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
            <div className="flex min-w-0 flex-col gap-5">
              {loaded ? (
                <div className="rounded-xl border border-line/40 bg-surface-low p-6 shadow-[0_8px_30px_rgba(0,0,0,0.4)]">
                  <LyricsEditor
                    projectId={projectId}
                    initialContent={editorContent}
                    onContentChange={handleContentChange}
                    onSelectionChange={(text) => (selectedTextRef.current = text)}
                    onVersionSaved={handleVersionSaved}
                  />
                </div>
              ) : (
                <p className="text-base text-on-surface-variant" role="status">
                  Opening your words…
                </p>
              )}
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <ReadWordsButton projectId={projectId} getWords={() => currentLyricsRef.current} onSay={(m) => sayAsFrank(m)} appearance="stage" />
                <VoiceMemoButton
                  projectId={projectId}
                  appearance="stage"
                  onTranscription={(text) =>
                    sayAsFrank("Here's what I heard. Want to use any of it?", <SuggestionBlock content={text} onAdd={(c) => addToEditor(c)} />)
                  }
                  onError={(message) => sayAsFrank(message)}
                />
              </div>
              <WordsFeel projectId={projectId} getWords={() => currentLyricsRef.current} onSay={(m) => sayAsFrank(m)} />
            </div>

            <aside aria-label="About your words" className="hidden w-[280px] shrink-0 flex-col gap-6 lg:flex">
              <section aria-labelledby="sections-heading" className="flex flex-col gap-3 rounded-xl bg-surface-low p-4 shadow-[0_4px_16px_rgba(0,0,0,0.25)]">
                <div className="flex items-center justify-between pb-1">
                  <h2 id="sections-heading" className="text-label-sm font-semibold uppercase tracking-[0.06em] text-on-surface-variant">
                    Detected Sections
                  </h2>
                  <ListMusic className="h-4 w-4 text-on-surface-variant" aria-hidden="true" />
                </div>
                <div className="flex flex-col gap-1.5">
                  {sections.length ? (
                    sections.map((s, i) => (
                      <div
                        key={`${s.name}-${i}`}
                        className={`flex items-center justify-between rounded-lg p-2 ${s.chorus ? "bg-surface-high shadow-[0_0_8px_rgba(245,158,11,0.15)]" : "bg-surface-container hover:bg-surface-high"}`}
                      >
                        <div className="flex items-center gap-2">
                          <span className={`h-2 w-2 rounded-full ${s.chorus ? "bg-frank" : "bg-words"}`} />
                          <span className={`text-label-md ${s.chorus ? "font-semibold text-frank-text" : "text-on-surface"}`}>{s.name}</span>
                        </div>
                        <span className={`text-code ${s.chorus ? "text-frank-text" : "text-on-surface-variant"}`}>{s.range}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-on-surface-variant">
                      {hasWords ? "Give a section its own line (Verse, Chorus) and it shows up here." : "Your sections will show up here."}
                    </p>
                  )}
                  {missingSections.length > 0 && (
                    <div className="flex flex-col gap-1.5 pt-2 opacity-60">
                      {missingSections.map((s) => (
                        <div key={s.label} className="flex items-center justify-between px-2 py-1">
                          <div className="flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full bg-surface-highest" />
                            <span className="text-sm text-on-surface-variant">{s.label}</span>
                          </div>
                          <span className="font-mono text-[10px] text-on-surface-variant">Not yet</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
              <LyricsVersionHistory
                versions={versions}
                activeVersionId={activeVersionId}
                onRestore={handleRestore}
                onLabelUpdated={(id, label) => setVersions((vs) => vs.map((v) => (v.id === id ? { ...v, label } : v)))}
              />
            </aside>
          </div>
        </div>
      </div>

      <ConversationPanel
        projectId={projectId}
        room="idea"
        material="words"
        emptyText="Stuck on a line? Need a rhyme? Want a second pair of ears? Frank is here."
        turns={turns}
        onSend={handleSend}
        isThinking={isThinking}
        placeholder="Ask for a rhyme or a line…"
      />
    </div>
  )
}

// ─────────────────────────────────────────────
// A lyric suggestion in the conversation: words you can add, or leave
// ─────────────────────────────────────────────
function SuggestionBlock({
  content,
  sectionLabel,
  onAdd,
}: {
  content: string
  sectionLabel?: string
  onAdd: (content: string, sectionLabel?: string) => void
}) {
  const [resolved, setResolved] = useState<"added" | "ignored" | null>(null)
  if (resolved === "ignored") return null
  return (
    <div className="rounded-lg border border-frank/20 bg-surface-high p-3 shadow-[0_0_16px_rgba(245,158,11,0.2)]">
      {sectionLabel && <p className="mb-1.5 text-label-sm font-semibold uppercase tracking-[0.06em] text-on-surface-variant">{sectionLabel}</p>}
      <p className="whitespace-pre-wrap font-written text-xl leading-[30px] text-frank-text">“{content}”</p>
      <div className="mt-2.5 flex items-center gap-2">
        {resolved === "added" ? (
          <span className="text-sm text-words">Added to your words</span>
        ) : (
          <>
            <button
              onClick={() => {
                onAdd(content, sectionLabel)
                setResolved("added")
              }}
              className="rounded bg-frank px-3 py-1 text-label-sm font-semibold text-on-primary"
            >
              Add to my words
            </button>
            <button onClick={() => setResolved("ignored")} className="rounded bg-surface-highest px-3 py-1 text-label-sm text-on-surface-variant">
              Leave it
            </button>
          </>
        )}
      </div>
    </div>
  )
}
