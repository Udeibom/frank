import type { TakeWords } from "@/types/api"
import { api, uploadFile } from "./client"
import type { ConversationMessage, ConversationAction } from "@/types/api"
import type { PitchPoint } from "@/types/audio"

export type TakeKind = "take" | "tuned" | "lined_up" | "cleaned" | "harmony" | "quiet" | "instrument"

/** Plain facts the backend measured about a take (sing-it spec 06). */
export interface TakeFacts {
  seconds?: number
  sections?: number[]
  notes?: number
  on_the_notes?: number | null
  sits_ms?: number | null
  bleed?: number | null
  engineer?: string | null
}

export interface VocalTake {
  id: string
  project_id: string
  audio_url: string
  processed_url: string | null
  pitch_data: PitchPoint[] | null
  label: string | null
  created_at: string
  kind: TakeKind
  parent_take_id: string | null
  is_harmony: boolean
  params: Record<string, unknown>
  facts: TakeFacts
  /** Word timings and where each lyric line falls (frankenstein spec 14, 4.4). */
  words?: TakeWords | null
}

export interface UploadTakeResult {
  take: VocalTake
  analysis_job_id: string
}

export interface VoiceConversationResult {
  message: string
  actions: ConversationAction[]
}

/** Where a take sits against the beat it was sung over. */
export interface TakePlacement {
  beat_version_id: string
  beat_offset_s: number
  lead_in_s: number
}

export interface CompSegment {
  phrase_index?: number
  take_id: string
  start_time: number
  end_time: number
  section?: number | null
  scores?: Record<string, { total: number }>
}

export interface ActiveComp {
  id: string
  audio_url: string
  segments: CompSegment[]
  active: boolean
  created_at: string
}

type Job = { job_id: string }
type Mode = "light" | "moderate" | "full"

export async function uploadTake(
  projectId: string,
  audioBlob: Blob,
  fileExtension: string = "webm",
  placement?: TakePlacement | null,
  headphones?: boolean | null,
): Promise<UploadTakeResult> {
  const formData = new FormData()
  formData.append("file", audioBlob, `take.${fileExtension}`)
  if (placement) {
    formData.append("beat_version_id", placement.beat_version_id)
    formData.append("beat_offset_s", String(placement.beat_offset_s))
    formData.append("lead_in_s", String(placement.lead_in_s))
  }
  if (headphones !== null && headphones !== undefined) formData.append("headphones", String(headphones))
  return uploadFile<UploadTakeResult>(`/projects/${projectId}/voice/takes`, formData)
}

export async function listTakes(projectId: string): Promise<VocalTake[]> {
  return api.get<VocalTake[]>(`/projects/${projectId}/voice/takes`)
}

export async function deleteTake(projectId: string, takeId: string): Promise<void> {
  await api.delete(`/projects/${projectId}/voice/takes/${takeId}`)
}

export function correctPitch(projectId: string, takeId: string, mode: Mode): Promise<Job> {
  return api.post<Job>(`/projects/${projectId}/voice/takes/${takeId}/correct`, { mode })
}

export function lineUp(projectId: string, takeId: string, mode: "moderate" | "full" = "moderate"): Promise<Job> {
  return api.post<Job>(`/projects/${projectId}/voice/takes/${takeId}/align`, { mode })
}

export function removeBleed(projectId: string, takeId: string): Promise<Job> {
  return api.post<Job>(`/projects/${projectId}/voice/takes/${takeId}/remove-bleed`)
}

export function takeAsMelody(projectId: string, takeId: string): Promise<Job> {
  return api.post<Job>(`/projects/${projectId}/voice/takes/${takeId}/use-as-melody`)
}

export function makeGuide(projectId: string): Promise<Job> {
  return api.post<Job>(`/projects/${projectId}/voice/guide`)
}

export function buildComp(projectId: string, takeIds: string[]): Promise<Job> {
  return api.post<Job>(`/projects/${projectId}/voice/comp`, { take_ids: takeIds })
}

export function getActiveComp(projectId: string): Promise<{ comp: ActiveComp | null }> {
  return api.get(`/projects/${projectId}/voice/comp/active`)
}

export function swapPhrase(projectId: string, compId: string, phraseIndex: number, takeId: string): Promise<Job> {
  return api.post<Job>(`/projects/${projectId}/voice/comp/${compId}/swap`, { phrase_index: phraseIndex, take_id: takeId })
}

export function generateHarmony(
  projectId: string,
  takeId: string,
  type: "above" | "below" | "both",
  sections?: string[] | null,
): Promise<Job> {
  return api.post<Job>(`/projects/${projectId}/voice/harmony`, { take_id: takeId, type, sections: sections ?? null })
}

export async function setActiveVocal(projectId: string, vocalId: string, vocalType: "take" | "comp"): Promise<void> {
  await api.post(`/projects/${projectId}/voice/active`, { vocal_id: vocalId, vocal_type: vocalType })
}

export function getVoiceSettings(projectId: string): Promise<{ input_delay_ms: number | null }> {
  return api.get(`/projects/${projectId}/voice/settings`)
}

export function sendDelayCheck(
  projectId: string,
  blob: Blob,
  ext: string,
  clickTimes: number[],
): Promise<{ ok: boolean; delay_ms?: number; message: string }> {
  const formData = new FormData()
  formData.append("file", blob, `check.${ext}`)
  formData.append("click_times", JSON.stringify(clickTimes))
  return uploadFile(`/projects/${projectId}/voice/delay-check`, formData)
}

export async function sendVoiceMessage(
  projectId: string,
  message: string,
  history: ConversationMessage[],
): Promise<VoiceConversationResult> {
  return api.post<VoiceConversationResult>(`/projects/${projectId}/voice/conversation`, { message, history })
}
