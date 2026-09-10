import { apiClient } from './client'
import { type NodeItem } from './nodes'

export interface SplitProposal {
  split_index: number
  confidence: number
  before_snippet: string
  after_snippet: string
}

export interface ProposedSliceItem {
  text: string
  token_count: number
}

export interface NodeSemanticSplitPreview {
  node_id: string
  document_id: string
  original_text: string
  total_tokens?: number
  order_index: number
  proposed_splits: SplitProposal[]
  proposed_slices: ProposedSliceItem[]
}

export interface EmbeddingStatusResponse {
  project_id: string
  current: number
  stale: number
  missing: number
  total: number
  faiss_total: number
}

export interface ModelSwitchCheckResult {
  action: 'unchanged' | 'requires_confirmation' | 'switched'
  requires_confirmation: boolean
  existing_vectors?: number
  current_model?: string
  new_model?: string
  message?: string
}

export async function previewSemanticSplits(
  projectId: string,
  nodeIds: string[],
  minTokens?: number,
  maxTokens?: number
): Promise<NodeSemanticSplitPreview[]> {
  const resp = await apiClient.post<NodeSemanticSplitPreview[]>(
    `/api/projects/${projectId}/nodes/semantic-split-preview`,
    {
      node_ids: nodeIds,
      min_tokens: minTokens,
      max_tokens: maxTokens
    }
  )
  return resp.data
}

export async function acceptSemanticSplits(
  projectId: string,
  items: { node_id: string; split_indices: number[] }[]
): Promise<NodeItem[]> {
  const resp = await apiClient.post<NodeItem[]>(
    `/api/projects/${projectId}/nodes/semantic-split-accept`,
    { items }
  )
  return resp.data
}

export async function fetchEmbeddingStatus(projectId: string): Promise<EmbeddingStatusResponse> {
  const resp = await apiClient.get<EmbeddingStatusResponse>(
    `/api/projects/${projectId}/embeddings/status`
  )
  return resp.data
}

export async function checkEmbeddingModelSwitch(
  projectId: string,
  newModel: string,
  confirm: boolean = false
): Promise<ModelSwitchCheckResult> {
  const resp = await apiClient.post<ModelSwitchCheckResult>(
    `/api/projects/${projectId}/embeddings/model-check`,
    { new_model: newModel, confirm }
  )
  return resp.data
}

export async function triggerEmbeddingRefresh(
  projectId: string,
  batchSize: number = 16
): Promise<any> {
  const resp = await apiClient.post(
    `/api/projects/${projectId}/embeddings/refresh`,
    { batch_size: batchSize }
  )
  return resp.data
}