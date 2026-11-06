import { api, uploadFile } from "./client"
import type { LyricsVersion } from "@/types/project"

export interface VoiceMemoResult {
  transcription: string
  audio_url: string
}

export async function saveLyrics(
  projectId: string,
  content: string,
  label?: string,
): Promise<LyricsVersion> {
  return api.post<LyricsVersion>(`/projects/${projectId}/lyrics`, {
    content,
    label,
  })
}

export async function listLyricsVersions(
  projectId: string,
): Promise<LyricsVersion[]> {
  return api.get<LyricsVersion[]>(`/projects/${projectId}/lyrics`)
}

export async function getLyricsVersion(
  projectId: string,
  versionId: string,
): Promise<LyricsVersion> {
  return api.get<LyricsVersion>(`/projects/${projectId}/lyrics/${versionId}`)
}

export async function updateLyricsLabel(
  projectId: string,
  versionId: string,
  label: string,
): Promise<LyricsVersion> {
  return api.patch<LyricsVersion>(
    `/projects/${projectId}/lyrics/${versionId}`,
    { label },
  )
}

export async function setActiveLyrics(
  projectId: string,
  lyricsVersionId: string,
): Promise<void> {
  await api.post(`/projects/${projectId}/lyrics/active`, {
    lyrics_version_id: lyricsVersionId,
  })
}

export async function uploadVoiceMemo(
  projectId: string,
  audioBlob: Blob,
  fileExtension: string = "webm",
): Promise<VoiceMemoResult> {
  const formData = new FormData()
  formData.append("file", audioBlob, `memo.${fileExtension}`)
  return uploadFile<VoiceMemoResult>(
    `/projects/${projectId}/lyrics/voice-memo`,
    formData,
  )
}
