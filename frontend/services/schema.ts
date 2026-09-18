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

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

export function generateJsonSchemaFromFields(fields: SchemaField[]): Record<string, any> {
  const properties: Record<string, any> = {}
  const required: string[] = []

  const sorted = [...fields].sort((a, b) => a.order_index - b.order_index)

  for (const field of sorted) {
    const slug = field.field_slug || `field_${field.id.slice(0, 8)}`
    const propDef: Record<string, any> = {}
    if (field.description) propDef.description = field.description

    if (field.field_type === 'string') propDef.type = 'string'
    else if (field.field_type === 'number') propDef.type = 'number'
    else if (field.field_type === 'boolean') propDef.type = 'boolean'
    else if (field.field_type === 'date') { propDef.type = 'string'; propDef.format = 'date' }
    else if (field.field_type === 'array[string]') { propDef.type = 'array'; propDef.items = { type: 'string' } }
    else if (field.field_type === 'array[number]') { propDef.type = 'array'; propDef.items = { type: 'number' } }

    properties[slug] = propDef
    if (field.is_required) required.push(slug)
  }

  const schema: Record<string, any> = {
    $schema: 'http://json-schema.org/draft-07/schema#',
    type: 'object',
    properties,
    additionalProperties: false
  }
  if (required.length > 0) schema.required = required
  return schema
}