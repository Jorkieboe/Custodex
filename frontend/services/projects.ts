import { apiClient } from './client'

export interface Project {
  id: string
  name: string
  llm_model: string
  embedding_model: string
  created_at?: string
  updated_at?: string
}

export interface DocumentSummary {
  id: string
  project_id: string
  filename: string
  file_type: string
  order_index: number
  total_nodes: number
  current_embeddings: number
  stale_embeddings: number
  missing_embeddings: number
}

export async function fetchProjects(): Promise<Project[]> {
  const resp = await apiClient.get<Project[]>('/api/projects')
  return resp.data
}

export async function fetchProjectById(projectId: string): Promise<Project> {
  const resp = await apiClient.get<Project>(`/api/projects/${projectId}`)
  return resp.data
}

export async function createProject(payload: {
  name: string
  llm_model?: string
  embedding_model?: string
}): Promise<Project> {
  const resp = await apiClient.post<Project>('/api/projects', payload)
  return resp.data
}

export async function fetchProjectDocuments(projectId: string): Promise<DocumentSummary[]> {
  const resp = await apiClient.get<DocumentSummary[]>(`/api/projects/${projectId}/documents`)
  return resp.data
}

export async function uploadProjectDocuments(
  projectId: string,
  files: File[]
): Promise<DocumentSummary[]> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  const resp = await apiClient.post<DocumentSummary[]>(
    `/api/projects/${projectId}/documents/upload`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return resp.data
}

export async function deleteProjectDocument(
  projectId: string,
  documentId: string
): Promise<{ status: string; document_id: string }> {
  const resp = await apiClient.delete<{ status: string; document_id: string }>(
    `/api/projects/${projectId}/documents/${documentId}`
  )
  return resp.data
}