import { apiClient } from './client'

export type NodeType = 'header' | 'paragraph'
export type EmbeddingStatus = 'current' | 'stale' | 'missing'

export interface NodeItem {
  id: string
  document_id: string
  parent_id: string | null
  node_type: NodeType
  text_content: string
  order_index: number
  embedding_status: EmbeddingStatus
}

export async function fetchProjectNodes(projectId: string): Promise<NodeItem[]> {
  const resp = await apiClient.get<NodeItem[]>(`/api/projects/${projectId}/nodes`)
  return resp.data
}

export async function updateProjectNode(
  projectId: string,
  nodeId: string,
  textContent: string
): Promise<NodeItem> {
  const resp = await apiClient.patch<NodeItem>(
    `/api/projects/${projectId}/nodes/${nodeId}`,
    { text_content: textContent }
  )
  return resp.data
}

export async function splitProjectNode(
  projectId: string,
  nodeId: string,
  topText: string,
  bottomText: string
): Promise<[NodeItem, NodeItem]> {
  const resp = await apiClient.post<[NodeItem, NodeItem]>(
    `/api/projects/${projectId}/nodes/${nodeId}/split`,
    { top_text: topText, bottom_text: bottomText }
  )
  return resp.data
}

export async function mergeProjectNode(
  projectId: string,
  nodeId: string
): Promise<NodeItem> {
  const resp = await apiClient.post<NodeItem>(
    `/api/projects/${projectId}/nodes/${nodeId}/merge`
  )
  return resp.data
}

export async function promoteProjectNode(
  projectId: string,
  nodeId: string
): Promise<NodeItem> {
  const resp = await apiClient.post<NodeItem>(
    `/api/projects/${projectId}/nodes/${nodeId}/promote`
  )
  return resp.data
}

export async function demoteProjectNode(
  projectId: string,
  nodeId: string
): Promise<NodeItem> {
  const resp = await apiClient.post<NodeItem>(
    `/api/projects/${projectId}/nodes/${nodeId}/demote`
  )
  return resp.data
}

export async function detachSelectionToHeader(
  projectId: string,
  nodeId: string,
  selectionStart: number,
  selectionEnd: number
): Promise<NodeItem[]> {
  const resp = await apiClient.post<NodeItem[]>(
    `/api/projects/${projectId}/nodes/${nodeId}/detach-selection`,
    { selection_start: selectionStart, selection_end: selectionEnd }
  )
  return resp.data
}