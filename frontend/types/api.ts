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
