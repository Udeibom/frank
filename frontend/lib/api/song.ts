import { api } from "./client"
import type {
  FacetContent,
  SongFacetName,
  SongFacetVersion,
  SongPhase,
  SongRecord,
} from "@/types/song"

export async function getSong(projectId: string): Promise<SongRecord> {
  return api.get<SongRecord>(`/projects/${projectId}/song`)
}

export async function writeFacet(
  projectId: string,
  facet: SongFacetName,
  content: FacetContent,
  options: { label?: string; operation?: string; parentId?: string } = {},
): Promise<SongFacetVersion> {
  return api.post<SongFacetVersion>(`/projects/${projectId}/song/facets/${facet}`, {
    content,
    label: options.label,
    operation: options.operation ?? "user_set",
    parent_id: options.parentId,
  })
}

export async function listFacetVersions(
  projectId: string,
  facet: SongFacetName,
): Promise<SongFacetVersion[]> {
  return api.get<SongFacetVersion[]>(`/projects/${projectId}/song/facets/${facet}/versions`)
}

export async function restoreFacetVersion(
  projectId: string,
  facet: SongFacetName,
  versionId: string,
): Promise<SongFacetVersion> {
  return api.post<SongFacetVersion>(`/projects/${projectId}/song/facets/${facet}/restore`, {
    version_id: versionId,
  })
}

export async function setSongPhase(projectId: string, phase: SongPhase): Promise<void> {
  await api.patch(`/projects/${projectId}/song/phase`, { phase })
}
