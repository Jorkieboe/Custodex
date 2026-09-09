import axios from 'axios'

export interface ApiStatus {
  status: string
  lm_studio_connected: boolean
  lm_studio_endpoint: string
  default_llm_model: string
  default_embedding_model: string
}

export interface AppConfig {
  default_llm_model: string
  default_embedding_model: string
  lm_studio_endpoint: string
  recent_projects: string[]
}

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
  order_index: int
  total_nodes: number
  current_embeddings: number
  stale_embeddings: number
  missing_embeddings: number
}

export interface NodeItem {
  id: string
  document_id: string
  parent_id: string | null
  node_type: 'header' | 'paragraph'
  text_content: string
  order_index: number
  embedding_status: 'current' | 'stale' | 'missing'
}

export const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

export async function fetchApiStatus(): Promise<ApiStatus> {
  const response = await apiClient.get<ApiStatus>('/api/status')
  return response.data
}

export async function fetchAppConfig(): Promise<AppConfig> {
  const response = await apiClient.get<AppConfig>('/api/config')
  return response.data
}

export async function updateAppConfig(config: AppConfig): Promise<AppConfig> {
  const response = await apiClient.put<AppConfig>('/api/config', config)
  return response.data
}

export async function fetchProjects(): Promise<Project[]> {
  const response = await apiClient.get<Project[]>('/api/projects')
  return response.data
}

export async function fetchProjectById(projectId: string): Promise<Project> {
  const response = await apiClient.get<Project>(`/api/projects/${projectId}`)
  return response.data
}

export async function createProject(payload: { name: string; llm_model?: string; embedding_model?: string }): Promise<Project> {
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

export async function updateProjectNode(projectId: string, nodeId: string, textContent: string): Promise<NodeItem> {
  const response = await apiClient.patch<NodeItem>(`/api/projects/${projectId}/nodes/${nodeId}`, {
    text_content: textContent
  })
  return response.data
}

export async function fetchProjectNodes(projectId: string): Promise<NodeItem[]> {
  const response = await apiClient.get<NodeItem[]>(`/api/projects/${projectId}/nodes`)
  return response.data
}

export async function splitProjectNode(projectId: string, nodeId: string, topText: string, bottomText: string): Promise<NodeItem[]> {
  const response = await apiClient.post<NodeItem[]>(`/api/projects/${projectId}/nodes/${nodeId}/split`, {
    top_text: topText,
    bottom_text: bottomText
  })
  return response.data
}

export async function mergeProjectNode(projectId: string, nodeId: string): Promise<NodeItem> {
  const response = await apiClient.post<NodeItem>(`/api/projects/${projectId}/nodes/${nodeId}/merge`)
  return response.data
}

export async function promoteProjectNode(projectId: string, nodeId: string): Promise<NodeItem> {
  const response = await apiClient.post<NodeItem>(`/api/projects/${projectId}/nodes/${nodeId}/promote`)
  return response.data
}

export async function demoteProjectNode(projectId: string, nodeId: string): Promise<NodeItem> {
  const response = await apiClient.post<NodeItem>(`/api/projects/${projectId}/nodes/${nodeId}/demote`)
  return response.data
}

export async function detachSelectionToHeader(projectId: string, nodeId: string, start: number, end: number): Promise<NodeItem[]> {
  const response = await apiClient.post<NodeItem[]>(`/api/projects/${projectId}/nodes/${nodeId}/detach-selection`, {
    selection_start: start,
    selection_end: end
  })
  return response.data
}