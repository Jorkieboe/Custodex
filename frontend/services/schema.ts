import { apiClient } from './client'

export type FieldType = 'string' | 'number' | 'boolean' | 'array[string]' | 'array[number]' | 'date'

export interface SchemaField {
  id: string
  project_id: string
  field_slug: string
  field_label: string
  field_type: FieldType
  description: string
  is_required: boolean
  order_index: number
}

export async function fetchProjectSchema(projectId: string): Promise<SchemaField[]> {
  const resp = await apiClient.get<SchemaField[]>(`/api/projects/${projectId}/schema`)
  return resp.data
}

export async function createSchemaField(
  projectId: string,
  payload: Partial<SchemaField>
): Promise<SchemaField> {
  const resp = await apiClient.post<SchemaField>(
    `/api/projects/${projectId}/schema/fields`,
    payload
  )
  return resp.data
}

export async function updateSchemaField(
  projectId: string,
  fieldId: string,
  payload: Partial<SchemaField>
): Promise<SchemaField> {
  const resp = await apiClient.patch<SchemaField>(
    `/api/projects/${projectId}/schema/fields/${fieldId}`,
    payload
  )
  return resp.data
}

export async function deleteSchemaField(
  projectId: string,
  fieldId: string
): Promise<void> {
  await apiClient.delete(`/api/projects/${projectId}/schema/fields/${fieldId}`)
}

export async function replaceAllSchemaFields(
  projectId: string,
  fields: SchemaField[]
): Promise<SchemaField[]> {
  const resp = await apiClient.put<SchemaField[]>(
    `/api/projects/${projectId}/schema/fields`,
    fields
  )
  return resp.data
}