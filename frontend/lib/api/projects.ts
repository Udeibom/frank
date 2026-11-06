import { api } from "./client"
import type {
  ProjectResponse,
  ProjectListResponse,
  ProjectWithStateResponse,
  CreateProjectRequest,
  UpdateProjectRequest,
} from "@/types/api"

export async function createProject(
  data: CreateProjectRequest = {},
): Promise<ProjectResponse> {
  return api.post<ProjectResponse>("/projects", data)
}

export async function listProjects(): Promise<ProjectListResponse> {
  return api.get<ProjectListResponse>("/projects")
}

export async function getProject(
  id: string,
): Promise<ProjectWithStateResponse> {
  return api.get<ProjectWithStateResponse>(`/projects/${id}`)
}

export async function updateProject(
  id: string,
  data: UpdateProjectRequest,
): Promise<ProjectResponse> {
  return api.patch<ProjectResponse>(`/projects/${id}`, data)
}
