import { api } from "./client"

export interface ExportRecord {
  id: string
  project_id: string
  audio_url: string
  format: string
  quality: string
  created_at: string
}

export interface DownloadInfo {
  url: string
  filename: string
}

export async function createExport(
  projectId: string,
  mixVersionId: string,
  applyMastering: boolean,
): Promise<{ job_id: string }> {
  return api.post<{ job_id: string }>(`/projects/${projectId}/export`, {
    mix_version_id: mixVersionId,
    apply_mastering: applyMastering,
  })
}

export async function listExports(
  projectId: string,
): Promise<ExportRecord[]> {
  return api.get<ExportRecord[]>(`/projects/${projectId}/export`)
}

export async function getDownloadInfo(
  projectId: string,
  exportId: string,
): Promise<DownloadInfo> {
  return api.get<DownloadInfo>(
    `/projects/${projectId}/export/${exportId}/download`,
  )
}
