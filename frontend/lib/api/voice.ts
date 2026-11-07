import { api, uploadFile } from "./client"
import type { ConversationMessage, ConversationAction } from "@/types/api"
import type { PitchPoint } from "@/types/audio"

export interface VocalTake {
  id: string
  project_id: string
  audio_url: string
  processed_url: string | null
  pitch_data: PitchPoint[] | null
  label: string | null
  created_at: string
}

export interface UploadTakeResult {
  take: VocalTake
  analysis_job_id: string
}

export interface VoiceConversationResult {
  message: string
  actions: ConversationAction[]
}

export async function uploadTake(
  projectId: string,
  audioBlob: Blob,
  fileExtension: string = "webm",
): Promise<UploadTakeResult> {
  const formData = new FormData()
  formData.append("file", audioBlob, `take.${fileExtension}`)
  return uploadFile<UploadTakeResult>(
    `/projects/${projectId}/voice/takes`,
    formData,
  )
}

export async function listTakes(projectId: string): Promise<VocalTake[]> {
  return api.get<VocalTake[]>(`/projects/${projectId}/voice/takes`)
}

export async function deleteTake(
  projectId: string,
  takeId: string,
): Promise<void> {
  await api.delete(`/projects/${projectId}/voice/takes/${takeId}`)
}

export async function correctPitch(
  projectId: string,
  takeId: string,
  mode: "light" | "moderate" | "full",
): Promise<{ job_id: string }> {
  return api.post<{ job_id: string }>(
    `/projects/${projectId}/voice/takes/${takeId}/correct`,
    { mode },
  )
}

export async function buildComp(
  projectId: string,
  takeIds: string[],
): Promise<{ job_id: string }> {
  return api.post<{ job_id: string }>(`/projects/${projectId}/voice/comp`, {
    take_ids: takeIds,
  })
}

export async function generateHarmony(
  projectId: string,
  takeId: string,
  type: "above" | "below" | "both",
): Promise<{ job_id: string }> {
  return api.post<{ job_id: string }>(`/projects/${projectId}/voice/harmony`, {
    take_id: takeId,
    type,
  })
}

export async function setActiveVocal(
  projectId: string,
  vocalId: string,
  vocalType: "take" | "comp",
): Promise<void> {
  await api.post(`/projects/${projectId}/voice/active`, {
    vocal_id: vocalId,
    vocal_type: vocalType,
  })
}

export async function sendVoiceMessage(
  projectId: string,
  message: string,
  history: ConversationMessage[],
): Promise<VoiceConversationResult> {
  return api.post<VoiceConversationResult>(
    `/projects/${projectId}/voice/conversation`,
    { message, history },
  )
}
