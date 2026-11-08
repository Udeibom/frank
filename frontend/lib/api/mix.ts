import { api } from "./client"
import type { ConversationMessage, ConversationAction } from "@/types/api"

export interface MixParams {
  vocal_gain_db: number
  beat_gain_db: number
  harmony_gain_db: number
  harmony_enabled: boolean
  vocal_effects: string[]
  beat_effects: string[]
  section_gain_db: Record<string, number>
}

export interface MixVersion {
  id: string
  project_id: string
  render_url: string | null
  label: string | null
  mix_params: Partial<MixParams>
  created_at: string
}

export interface MixConversationResult {
  message: string
  mix_params: MixParams
  actions: ConversationAction[]
  render: boolean
}

export async function renderMix(
  projectId: string,
  mixParams: Partial<MixParams>,
  quality: "preview" | "full" = "preview",
): Promise<{ job_id: string }> {
  return api.post<{ job_id: string }>(`/projects/${projectId}/mix/render`, {
    mix_params: mixParams,
    quality,
  })
}

export async function sendMixMessage(
  projectId: string,
  message: string,
  mixParams: Partial<MixParams>,
  history: ConversationMessage[],
): Promise<MixConversationResult> {
  return api.post<MixConversationResult>(
    `/projects/${projectId}/mix/conversation`,
    { message, mix_params: mixParams, history },
  )
}

export async function listMixVersions(
  projectId: string,
): Promise<MixVersion[]> {
  return api.get<MixVersion[]>(`/projects/${projectId}/mix/versions`)
}

export async function setActiveMixVersion(
  projectId: string,
  mixVersionId: string,
): Promise<void> {
  await api.post(`/projects/${projectId}/mix/versions/active`, {
    mix_version_id: mixVersionId,
  })
}
