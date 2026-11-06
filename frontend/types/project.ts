// ─────────────────────────────────────────────
// Core project types for Frank
// ─────────────────────────────────────────────

// Import audio types needed within this file
import type { PitchPoint } from "./audio"

export type ProjectStatus = "draft" | "in_progress" | "exported"

export interface Project {
  id: string
  user_id: string
  title: string
  status: ProjectStatus
  created_at: string
  updated_at: string
}

export interface ProjectActiveState {
  project_id: string
  active_lyrics_id: string | null
  active_fingerprint_id: string | null
  active_beat_version_id: string | null
  active_vocal_id: string | null
  active_comp_id: string | null
  active_mix_id: string | null
  updated_at: string | null
}

export interface ProjectWithState {
  project: Project
  active_state: ProjectActiveState | null
}

// ─────────────────────────────────────────────
// Layer: Idea Room
// ─────────────────────────────────────────────

export interface LyricsVersion {
  id: string
  project_id: string
  content: string
  label: string | null
  created_at: string
}

// ─────────────────────────────────────────────
// Layer: Feel Lab
// ─────────────────────────────────────────────

export type TempoFeel = "steady" | "building" | "floating" | "driving"

export interface MusicalFingerprint {
  tempo_bpm: number | null
  tempo_feel: TempoFeel | null
  key: string | null
  mode: "minor" | "major" | "modal" | null
  energy_level: number | null   // 0.0 – 1.0
  density: number | null        // 0.0 – 1.0
  brightness: number | null     // 0.0 – 1.0
  warmth: number | null         // 0.0 – 1.0
  genre_proximity: string[]
  instrumentation_hints: string[]
  reference_texture_id: string | null
  hum_reference_file: string | null
}

export interface FeelFingerprint {
  id: string
  project_id: string
  fingerprint: MusicalFingerprint
  conversation_summary: string | null
  created_at: string
}

export interface TextureSample {
  id: string
  project_id: string
  fingerprint_id: string | null
  audio_url: string
  approved: boolean
  created_at: string
}

// ─────────────────────────────────────────────
// Layer: Beat Room
// ─────────────────────────────────────────────

export interface BeatStem {
  id: string
  project_id: string
  beat_version_id: string | null
  stem_type: string
  section: string | null
  audio_url: string
  version_of: string | null
  created_at: string
}

export interface BeatVersion {
  id: string
  project_id: string
  render_url: string | null
  label: string | null
  params: Record<string, unknown>
  created_at: string
}

// ─────────────────────────────────────────────
// Layer: Voice Room
// ─────────────────────────────────────────────

export interface VocalTake {
  id: string
  project_id: string
  audio_url: string
  processed_url: string | null
  pitch_data: PitchPoint[] | null
  label: string | null
  deleted: boolean
  created_at: string
}

export interface VocalComp {
  id: string
  project_id: string
  audio_url: string
  segments: CompSegment[]
  created_at: string
}

export interface CompSegment {
  take_id: string
  start_time: number
  end_time: number
}

// ─────────────────────────────────────────────
// Layer: Mix Room
// ─────────────────────────────────────────────

export interface MixParams {
  stem_levels: Record<string, number>  // stem_id -> gain_db
  effects: Record<string, unknown>
  section_adjustments: Record<string, number>  // section_id -> gain_db
}

export interface MixVersion {
  id: string
  project_id: string
  render_url: string | null
  label: string | null
  mix_params: MixParams
  created_at: string
}

// ─────────────────────────────────────────────
// Layer: Export Room
// ─────────────────────────────────────────────

export interface ExportRecord {
  id: string
  project_id: string
  audio_url: string
  format: string
  quality: string
  created_at: string
}

// ─────────────────────────────────────────────
// Async Jobs
// ─────────────────────────────────────────────

export type JobStatus = "pending" | "processing" | "complete" | "failed"

export interface AsyncJob {
  id: string
  project_id: string
  job_type: string
  status: JobStatus
  result: Record<string, unknown> | null
  error: string | null
  created_at: string
  updated_at: string
}

// Re-export for consumers who import from project.ts
export type { PitchPoint }
