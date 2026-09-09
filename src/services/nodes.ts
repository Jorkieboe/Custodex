import { apiClient } from './client'

export interface NodeItem {
  id: string
  document_id: string
  parent_id: string | null
  node_type: 'header' | 'paragraph'
  text_content: string
  order_index: number
  embedding_status: 'current' | 'stale' | 'missing'
}

export async function fetchProjectNodes(projectId: string): Promise<NodeItem[]> {
  const response = await apiClient.get<NodeItem[]>(`/api/projects/${projectId}/nodes`)
  return response.data
}

export async function updateProjectNode(projectId: string, nodeId: string, textContent: string): Promise<NodeItem> {
  const response = await apiClient.patch<NodeItem>(`/api/projects/${projectId}/nodes/${nodeId}`, {
    text_content: textContent
  })
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

export async function detachSelectionToHeader(
  projectId: string,
  nodeId: string,
  start: number,
  end: number
): Promise<NodeItem[]> {
  const response = await apiClient.post<NodeItem[]>(`/api/projects/${projectId}/nodes/${nodeId}/detach-selection`, {
    selection_start: start,
    selection_end: end
  })
  return response.data
}