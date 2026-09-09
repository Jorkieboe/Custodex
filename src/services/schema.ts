import { apiClient } from './client'

export interface SchemaField {
  id: string
  project_id: string
  field_slug: string
  field_label: string
  field_type: 'string' | 'number' | 'boolean' | 'array[string]' | 'array[number]' | 'date'
  description: string
  is_required: boolean
  order_index: number
}

export async function fetchProjectSchema(projectId: string): Promise<SchemaField[]> {
  const response = await apiClient.get<SchemaField[]>(`/api/projects/${projectId}/schema`)
  return response.data
}

export async function fetchProjectJsonSchema(projectId: string): Promise<Record<string, any>> {
  const response = await apiClient.get<Record<string, any>>(`/api/projects/${projectId}/schema/json-schema`)
  return response.data
}

export async function createSchemaField(projectId: string, payload: Partial<SchemaField>): Promise<SchemaField> {
  const response = await apiClient.post<SchemaField>(`/api/projects/${projectId}/schema/fields`, payload)
  return response.data
}

export async function updateSchemaField(
  projectId: string,
  fieldId: string,
  payload: Partial<SchemaField>
): Promise<SchemaField> {
  const response = await apiClient.patch<SchemaField>(`/api/projects/${projectId}/schema/fields/${fieldId}`, payload)
  return response.data
}

export async function deleteSchemaField(projectId: string, fieldId: string): Promise<void> {
  await apiClient.delete(`/api/projects/${projectId}/schema/fields/${fieldId}`)
}

export async function replaceAllSchemaFields(projectId: string, fields: SchemaField[]): Promise<SchemaField[]> {
  const response = await apiClient.put<SchemaField[]>(`/api/projects/${projectId}/schema`, fields)
  return response.data
}