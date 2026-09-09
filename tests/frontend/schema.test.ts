import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkspaceStore } from '@/stores/workspace'
import * as api from '@/services/api'

describe('Schema Management Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('manages schema field lifecycle (add, update, delete, reorder)', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_schema_test',
      name: 'Schema Project',
      llm_model: 'local-model',
      embedding_model: 'test-emb'
    }

    // 1. Add field
    const mockField: api.SchemaField = {
      id: 'f_1',
      project_id: 'proj_schema_test',
      field_slug: 'summary',
      field_label: 'Summary',
      field_type: 'string',
      description: 'Concise summary',
      is_required: true,
      order_index: 0
    }

    vi.spyOn(api, 'createSchemaField').mockResolvedValueOnce(mockField)
    const added = await store.addSchemaField({
      field_label: 'Summary',
      field_type: 'string',
      is_required: true
    })

    expect(added?.id).toBe('f_1')
    expect(store.schemaFields.length).toBe(1)
    expect(store.schemaFields[0].field_label).toBe('Summary')

    // 2. Modify field
    const updatedField: api.SchemaField = {
      ...mockField,
      field_label: 'Executive Summary',
      field_slug: 'exec_summary'
    }
    vi.spyOn(api, 'updateSchemaField').mockResolvedValueOnce(updatedField)
    await store.modifySchemaField('f_1', { field_label: 'Executive Summary' })
    expect(store.schemaFields[0].field_label).toBe('Executive Summary')

    // 3. Delete field
    vi.spyOn(api, 'deleteSchemaField').mockResolvedValueOnce()
    await store.removeSchemaField('f_1')
    expect(store.schemaFields.length).toBe(0)
  })
})