/** Song Record types (song-record spec 01). Mirror backend/app/models/song.py. */

export type SongFacetName =
  | "intent"
  | "feeling"
  | "melody"
  | "structure"
  | "references"
  | "identity_brief"

export type SongPhase = "creating" | "refining"

/** A facet's content is free-form JSON on the wire; the UI describes it in plain words. */
export type FacetContent = Record<string, unknown>

export interface SongDecision {
  id: string
  project_id: string
  summary: string
  rationale: string | null
  proposed_by: string
  options: Record<string, unknown>[]
  evidence: Record<string, unknown>[]
  chosen_option: string | null
  user_reaction: string | null
  created_at: string | null
}

export interface SongRecord {
  project_id: string
  phase: SongPhase
  facets: Partial<Record<SongFacetName, FacetContent | null>>
  lyrics: string | null
  fingerprint: Record<string, unknown> | null
  beat: Record<string, unknown> | null
  vocal: Record<string, unknown> | null
  mix: Record<string, unknown> | null
  decisions: SongDecision[]
}

export interface SongFacetVersion {
  id: string
  facet: SongFacetName
  content: FacetContent
  parent_id: string | null
  operation: string
  author: string
  label: string | null
  is_active: boolean
  created_at: string | null
}
