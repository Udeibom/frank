import { api } from "./client"
import type { MusicalFingerprint } from "@/types/project"
import type { ConversationMessage, ConversationAction } from "@/types/api"

export interface BeatSection {
  index: number
  name: string
  label: string
  bars: number
  energy: number
  density: number
  layers: string[]
}

/** What the beat did with the person's own hummed tune (from the backend's lead_info). */
export interface LeadInfo {
  used: boolean
  reason?: string
  cut?: boolean
  tune_bars?: number
  heard_bars?: number
}

/** Plain-language sentence about the tune, or null when there was no hummed tune to talk about. */
export function describeLead(info: LeadInfo | undefined): string | null {
  if (!info) return null
  if (info.used) {
    return info.cut
      ? "I built the chorus around your tune. The chorus was shorter than your tune, so the end of it is left out."
      : "I built the chorus around your tune."
  }
  if (info.reason === "no_chorus_plays_it") {
    return "I have your tune, but no chorus plays it yet, so it isn't in this version."
  }
  return null
}

export interface BeatVersion {
  id: string
  project_id: string
  render_url: string | null
  label: string | null
  params: {
    fingerprint?: Partial<MusicalFingerprint>
    sections?: BeatSection[]
    lead_info?: LeadInfo
  }
  created_at: string
}

export interface BeatConversationResult {
  message: string
  actions: ConversationAction[]
}

export async function generateBeat(
  projectId: string,
  fingerprint: Partial<MusicalFingerprint>,
): Promise<{ job_id: string }> {
  return api.post<{ job_id: string }>(`/projects/${projectId}/beat/generate`, {
    fingerprint,
  })
}

export async function editSection(
  projectId: string,
  sectionIndex: number,
  instruction?: string,
): Promise<{ job_id: string }> {
  return api.post<{ job_id: string }>(
    `/projects/${projectId}/beat/generate-section`,
    { section_index: sectionIndex, instruction },
  )
}

export async function addStem(
  projectId: string,
  stemType: string,
  sectionIndex: number | null,
): Promise<{ job_id: string }> {
  return api.post<{ job_id: string }>(`/projects/${projectId}/beat/add-stem`, {
    stem_type: stemType,
    section_index: sectionIndex,
  })
}

export async function muteStem(
  projectId: string,
  stemType: string,
  sectionIndex: number | null,
): Promise<{ job_id: string }> {
  return api.post<{ job_id: string }>(`/projects/${projectId}/beat/mute-stem`, {
    stem_type: stemType,
    section_index: sectionIndex,
  })
}

export async function sendBeatMessage(
  projectId: string,
  message: string,
  beatState: { sections?: BeatSection[] },
  history: ConversationMessage[],
): Promise<BeatConversationResult> {
  return api.post<BeatConversationResult>(
    `/projects/${projectId}/beat/conversation`,
    { message, beat_state: beatState, history },
  )
}

export async function listBeatVersions(
  projectId: string,
): Promise<BeatVersion[]> {
  return api.get<BeatVersion[]>(`/projects/${projectId}/beat/versions`)
}

export async function setActiveBeatVersion(
  projectId: string,
  beatVersionId: string,
): Promise<void> {
  await api.post(`/projects/${projectId}/beat/versions/active`, {
    beat_version_id: beatVersionId,
  })
}

export async function previewWithVocal(
  projectId: string,
): Promise<{ job_id: string }> {
  return api.post<{ job_id: string }>(
    `/projects/${projectId}/beat/preview-with-vocal`,
    {},
  )
}

export async function updateSection(
  projectId: string,
  sectionIndex: number,
  data: { label?: string; new_index?: number },
): Promise<void> {
  await api.patch(
    `/projects/${projectId}/beat/sections/${sectionIndex}`,
    data,
  )
}
