import { api, uploadFile } from "./client"
import type { MusicalFingerprint } from "@/types/project"
import type { ConversationMessage, ConversationAction } from "@/types/api"

export interface FeelConversationResult {
  message: string
  fingerprint_update: Partial<MusicalFingerprint>
  actions: ConversationAction[]
}

export interface HumAnalysisResult {
  analysis: {
    tempo_bpm: number
    energy_level: number
    pitch_movement: string
    register: string
    fingerprint_hints: Partial<MusicalFingerprint>
  }
  audio_url: string
}

export interface FingerprintRecord {
  id: string
  project_id: string
  fingerprint: MusicalFingerprint
  conversation_summary: string | null
  created_at: string
}

export async function sendFeelMessage(
  projectId: string,
  message: string,
  fingerprint: Partial<MusicalFingerprint>,
  history: ConversationMessage[],
): Promise<FeelConversationResult> {
  return api.post<FeelConversationResult>(
    `/projects/${projectId}/feel/conversation`,
    { message, fingerprint, history },
  )
}

export async function generateTexture(
  projectId: string,
  fingerprint: Partial<MusicalFingerprint>,
  fingerprintId?: string,
): Promise<{ job_id: string }> {
  return api.post<{ job_id: string }>(`/projects/${projectId}/feel/texture`, {
    fingerprint,
    fingerprint_id: fingerprintId,
  })
}

export async function analyzeHum(
  projectId: string,
  audioBlob: Blob,
  fileExtension: string = "webm",
): Promise<HumAnalysisResult> {
  const formData = new FormData()
  formData.append("file", audioBlob, `hum.${fileExtension}`)
  return uploadFile<HumAnalysisResult>(
    `/projects/${projectId}/feel/hum`,
    formData,
  )
}

export async function saveFingerprint(
  projectId: string,
  fingerprint: MusicalFingerprint,
  conversationSummary?: string,
): Promise<FingerprintRecord> {
  return api.post<FingerprintRecord>(
    `/projects/${projectId}/feel/fingerprint`,
    { fingerprint, conversation_summary: conversationSummary },
  )
}

export async function getFingerprint(
  projectId: string,
): Promise<FingerprintRecord | null> {
  return api.get<FingerprintRecord | null>(
    `/projects/${projectId}/feel/fingerprint`,
  )
}
