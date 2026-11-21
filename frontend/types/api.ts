// ─────────────────────────────────────────────
// API request / response shapes for Frank
// Mirror the FastAPI Pydantic models on the backend
// ─────────────────────────────────────────────

import type {
  Project,
  ProjectActiveState,
  ProjectWithState,
  LyricsVersion,
  FeelFingerprint,
  MusicalFingerprint,
  TextureSample,
  BeatVersion,
  BeatStem,
  VocalTake,
  VocalComp,
  MixVersion,
  ExportRecord,
  AsyncJob,
} from "./project"

// ─── Projects ────────────────────────────────

export interface CreateProjectRequest {
  title?: string
}

export interface UpdateProjectRequest {
  title?: string
  status?: "draft" | "in_progress" | "exported"
}

export type ProjectResponse = Project
export type ProjectWithStateResponse = ProjectWithState
export type ProjectListResponse = Project[]

// ─── Lyrics ──────────────────────────────────

export interface SaveLyricsRequest {
  content: string
  label?: string
}

export interface UpdateLyricsLabelRequest {
  label: string
}

export interface SetActiveLyricsRequest {
  lyrics_version_id: string
}

export type LyricsVersionResponse = LyricsVersion
export type LyricsListResponse = LyricsVersion[]

// ─── Feel Lab ────────────────────────────────

export interface FeelConversationRequest {
  message: string
  fingerprint: Partial<MusicalFingerprint>
  history: ConversationMessage[]
}

export interface FeelConversationResponse {
  message: string
  fingerprint_update: Partial<MusicalFingerprint>
  actions: ConversationAction[]
}

export interface GenerateTextureRequest {
  fingerprint: Partial<MusicalFingerprint>
}

export interface AnalyzeHumResponse {
  analysis: {
    description: string
    fingerprint_hints: Partial<MusicalFingerprint>
  }
  audio_url: string
}

export interface SaveFingerprintRequest {
  fingerprint: MusicalFingerprint
  conversation_summary: string
}

// ─── Beat Room ───────────────────────────────

export interface GenerateBeatRequest {
  fingerprint: MusicalFingerprint
  duration_hint?: number
}

export interface GenerateSectionRequest {
  section_id: string
  fingerprint: MusicalFingerprint
  instruction?: string
}

export interface AddStemRequest {
  section_id: string
  stem_type: string
  fingerprint: MusicalFingerprint
}

export interface BeatConversationRequest {
  message: string
  beat_state: Record<string, unknown>
  history: ConversationMessage[]
}

// ─── Voice Room ──────────────────────────────

export interface CorrectPitchRequest {
  mode: "light" | "moderate" | "full"
}

export interface GenerateCompRequest {
  take_ids: string[]
  instruction?: string
}

export interface GenerateHarmonyRequest {
  take_id: string
  type: "above" | "below" | "both"
  fingerprint: Partial<MusicalFingerprint>
}

export interface SetActiveVocalRequest {
  vocal_id: string
  vocal_type: "take" | "comp"
}

// ─── Mix Room ────────────────────────────────

export interface RenderMixRequest {
  mix_params: Record<string, unknown>
  quality: "preview" | "full"
}

export interface MixConversationRequest {
  message: string
  mix_state: Record<string, unknown>
  history: ConversationMessage[]
}

// ─── Export Room ─────────────────────────────

export interface CreateExportRequest {
  mix_version_id: string
  apply_mastering: boolean
}

export interface DownloadUrlResponse {
  url: string
  expires_at: string
}

// ─── Shared ──────────────────────────────────

export interface JobResponse {
  job_id: string
}

export interface JobStatusResponse {
  job_id: string
  status: "pending" | "processing" | "complete" | "failed"
  result: Record<string, unknown> | null
  error: string | null
}

export interface ConversationMessage {
  role: "user" | "assistant"
  content: string
}

export interface ConversationAction {
  type: string
  params: Record<string, unknown>
}

export interface ConversationResponse {
  message: string
  actions: ConversationAction[]
}

// ─── API Error ───────────────────────────────

export interface ApiError {
  detail: string
  status: number
}

// ── Refine loop (spec 08) ──────────────────────────────────────────────

/** One way to fix what feels wrong. `actions` are typed changes the backend validated. */
export interface RefineDirection {
  title: string
  plain: string
  kind: "beat" | "mix"
  actions: Record<string, unknown>[]
  changes: string[]
  sections: number[]
  preview_url: string | null
  before_url: string | null
}

export interface RefineFinding {
  id: string
  plain: string
  sections: number[]
}

/** The result of a refine job: what Frank heard and the directions to try. */
export interface RefineProposal {
  proposal_id: string
  message: string
  experiment: boolean
  directions: RefineDirection[]
  findings: RefineFinding[]
  could_not_check: string[]
}

export interface RefinePreview {
  n: number
  preview_url: string
  before_url: string | null
}

export interface RefineChooseResponse {
  job_id: string
  kind: "beat" | "mix"
  message: string
}

export interface VersionCandidate {
  id: string
  label: string | null
  render_url: string | null
  created_at: string
}

// ── Frankenstein (spec 14): Frank's new organs ────────────────────────────────────────────────────────

export interface LyricWordSound {
  text: string
  syllables: number
  /** One digit per syllable: 1 strong, 2 medium, 0 weak. */
  stresses: string
}

export interface LyricLineSound {
  text: string
  syllables: number
  /** Lines with the same number rhyme with each other; null when the line rhymes with none. */
  rhyme_group: number | null
  guessed: boolean
  words: LyricWordSound[]
}

export interface LyricsAnalysis {
  lines: LyricLineSound[]
  notes: string[]
}

export interface RhymeSuggestions {
  word: string
  rhymes: string[]
  near: string[]
  sounds_like: string[]
}

export interface LyricEmotionSection {
  section: string
  feels: string[]
  energy: number
}

export interface LyricEmotions {
  sections: LyricEmotionSection[]
  message: string
}

export interface StartReply {
  ok: boolean
  message: string
  heard?: string | null
  asked?: string | null
  filled: string[]
}

export interface JamendoTrack {
  id: string
  title: string
  artist: string
  seconds: number
  license: string
  attribution: string
  image?: string | null
  moods: string[]
  genres: string[]
}

export interface SongReference {
  id: string
  source: "upload" | "jamendo" | "named"
  title: string | null
  artist: string | null
  license: string | null
  attribution: string | null
  analysis: { feeling_words?: string[]; differences?: string[] }
  active: boolean
  created_at: string
}

export interface CreditLine {
  organ: string
  plain: string
  attribution: string | null
  layer: string
}

export interface RankedDirection {
  texture_id: string
  score: number
}

export interface HeardNote {
  tag: string
  plain: string
  confidence: number
  confirmed: boolean
}

export interface HeardByFrank {
  heard: string
  notes: HeardNote[]
  from_seconds: number
  seconds: number
}

export interface WordTiming {
  word: string
  start: number
  end: number
}

export interface LineSpan {
  line: number
  text: string
  start: number | null
  end: number | null
}

export interface TakeWords {
  words: WordTiming[]
  lines: LineSpan[]
}

export interface MadeWell {
  before: number
  after: number
  plain: string
}
