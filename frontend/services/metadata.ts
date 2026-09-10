import { apiClient } from './client'

export interface ChunkMetadataItem {
  id?: number
  node_id: string
  field_id: string
  field_value: any
  user_edited: boolean
  field_slug?: string
  field_label?: string
  field_type?: string
}

export interface MetadataJobStatus {
  status: 'idle' | 'running' | 'completed' | 'failed'
  completed_partitions: number
  total_partitions: number
  completed_chunks: number
  total_chunks: number
  last_error: string | null
}

export async function fetchNodeMetadata(
  projectId: string,
  nodeId: string
): Promise<ChunkMetadataItem[]> {
  const resp = await apiClient.get<ChunkMetadataItem[]>(
    `/api/projects/${projectId}/nodes/${nodeId}/metadata`
  )
  console.log(`[Custodex API] Loaded metadata for node ${nodeId}:`, resp.data)
  return resp.data
}

export async function updateNodeMetadata(
  projectId: string,
  nodeId: string,
  payload: Record<string, any>
): Promise<{ status: string; node_id: string }> {
  console.log(`[Custodex API] Saving metadata for node ${nodeId}:`, payload)
  const resp = await apiClient.put<{ status: string; node_id: string }>(
    `/api/projects/${projectId}/nodes/${nodeId}/metadata`,
    payload
  )
  return resp.data
}

export async function startMetadataJob(
  projectId: string,
  options: { node_id?: string; force_overwrite?: boolean; resume?: boolean } = {}
): Promise<any> {
  console.log(`[Custodex API] Starting metadata extraction on project ${projectId}:`, options)
  const resp = await apiClient.post(
    `/api/projects/${projectId}/metadata/start`,
    options
  )
  return resp.data
}