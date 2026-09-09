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
  const response = await apiClient.get<Project[]>('/api/projects')
  return response.data
}

export async function fetchProjectById(projectId: string): Promise<Project> {
  const response = await apiClient.get<Project>(`/api/projects/${projectId}`)
  return response.data
}

export async function createProject(payload: {
  name: string
  llm_model?: string
  embedding_model?: string
}): Promise<Project> {
  const response = await apiClient.post<Project>('/api/projects', payload)
  return response.data
}

export async function fetchProjectDocuments(projectId: string): Promise<DocumentSummary[]> {
  const response = await apiClient.get<DocumentSummary[]>(`/api/projects/${projectId}/documents`)
  return response.data
}

export async function uploadProjectDocuments(projectId: string, files: File[]): Promise<DocumentSummary[]> {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }
  const response = await apiClient.post<DocumentSummary[]>(`/api/projects/${projectId}/documents/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return response.data
}

export async function deleteProjectDocument(projectId: string, docId: string): Promise<void> {
  await apiClient.delete(`/api/projects/${projectId}/documents/${docId}`)
}