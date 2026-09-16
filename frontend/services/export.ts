import { apiClient } from './client'

export interface ValidationBlocker {
  rule: 'empty_chunk' | 'uncalculated_embedding' | 'schema_violation'
  node_id: string
  document_id: string
  filename: string
  field_id?: string
  field_slug?: string
  message: string
  remediation: string
}

export interface ValidationSummary {
  empty_chunks: number
  uncalculated_embeddings: number
  schema_violations: number
}

export interface ValidationResult {
  is_valid: boolean
  total_chunks: number
  total_blockers: number
  blockers: ValidationBlocker[]
  summary: ValidationSummary
}

export async function fetchProjectValidation(projectId: string): Promise<ValidationResult> {
  const resp = await apiClient.get<ValidationResult>(`/api/projects/${projectId}/validate`)
  return resp.data
}

export async function downloadExportBundle(projectId: string): Promise<{ blob: Blob; filename: string }> {
  const resp = await apiClient.get(`/api/projects/${projectId}/export`, {
    responseType: 'blob'
  })

  let filename = 'rag-bundle.zip'
  const disposition = resp.headers['content-disposition']
  if (disposition && disposition.includes('filename=')) {
    const match = disposition.match(/filename=["']?([^"';]+)["']?/)
    if (match && match[1]) {
      filename = match[1].trim()
    }
  }

  return { blob: resp.data, filename }
}