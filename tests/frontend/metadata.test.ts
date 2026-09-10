import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkspaceStore } from '@/stores/workspace'
import * as api from '@/services/api'

describe('Metadata Workbench Store Actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('initializes with empty metadata tracking', () => {
    const store = useWorkspaceStore()
    expect(store.nodesWithMetadata.size).toBe(0)
    expect(store.isGeneratingSingle).toBeNull()
    expect(store.metadataJobStatus.status).toBe('idle')
  })

  it('generates metadata for a single node and adds to nodesWithMetadata', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'test_proj',
      name: 'Test',
      llm_model: 'local-model',
      embedding_model: 'test-emb'
    }

    const startJobSpy = vi.spyOn(api, 'startMetadataJob').mockResolvedValueOnce({
      status: 'completed',
      completed_partitions: 1,
      total_partitions: 1,
      completed_chunks: 1,
      total_chunks: 1,
      last_error: null
    })

    const fetchMetaSpy = vi.spyOn(api, 'fetchNodeMetadata').mockResolvedValueOnce([
      {
        id: 1,
        node_id: 'node_1',
        field_id: 'field_people',
        field_value: 'Alice, Bob',
        user_edited: false
      }
    ])

    await store.generateMetadataForNode('node_1')

    expect(startJobSpy).toHaveBeenCalledWith('test_proj', {
      node_id: 'node_1',
      force_overwrite: true
    })
    expect(store.nodesWithMetadata.has('node_1')).toBe(true)
    expect(store.isGeneratingSingle).toBeNull()
  })

  it('does not mark node as extracted if any field is null', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'test_proj',
      name: 'Test',
      llm_model: 'local-model',
      embedding_model: 'test-emb'
    }

    vi.spyOn(api, 'fetchProjectNodes').mockResolvedValueOnce([
      {
        id: 'node_empty',
        document_id: 'doc_1',
        parent_id: null,
        node_type: 'paragraph',
        text_content: 'sample text',
        order_index: 0,
        embedding_status: 'current'
      }
    ])

    vi.spyOn(api, 'fetchNodeMetadata').mockResolvedValueOnce([
      {
        id: 1,
        node_id: 'node_empty',
        field_id: 'field_topic',
        field_value: null,
        user_edited: false
      }
    ])

    await store.loadProjectMetadataOverview()
    expect(store.nodesWithMetadata.has('node_empty')).toBe(false)
  })

  it('recognizes empty array as extracted metadata and respects optional fields', async () => {
    const store = useWorkspaceStore()
    store.schemaFields = [
      {
        id: 'f_title',
        project_id: 'test_proj',
        field_slug: 'title',
        field_label: 'Title',
        field_type: 'string',
        description: '',
        is_required: true,
        order_index: 0
      },
      {
        id: 'f_years',
        project_id: 'test_proj',
        field_slug: 'years',
        field_label: 'Years',
        field_type: 'array[number]',
        description: '',
        is_required: false,
        order_index: 1
      }
    ]

    // Required title filled, optional years is empty array [] -> extracted!
    const items = [
      { node_id: 'n1', field_id: 'f_title', field_value: 'Doc Title', user_edited: false, is_required: true },
      { node_id: 'n1', field_id: 'f_years', field_value: [], user_edited: false, is_required: false }
    ]
    expect(store.isNodeFullyExtracted(items, store.schemaFields)).toBe(true)

    // Required title filled, optional years is null -> still extracted!
    const itemsWithNullOptional = [
      { node_id: 'n1', field_id: 'f_title', field_value: 'Doc Title', user_edited: false, is_required: true },
      { node_id: 'n1', field_id: 'f_years', field_value: null, user_edited: false, is_required: false }
    ]
    expect(store.isNodeFullyExtracted(itemsWithNullOptional, store.schemaFields)).toBe(true)

    // Required title null -> not extracted!
    const itemsWithNullRequired = [
      { node_id: 'n1', field_id: 'f_title', field_value: null, user_edited: false, is_required: true },
      { node_id: 'n1', field_id: 'f_years', field_value: [], user_edited: false, is_required: false }
    ]
    expect(store.isNodeFullyExtracted(itemsWithNullRequired, store.schemaFields)).toBe(false)
  })

  it('updates metadata fields with user_edited true', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'test_proj',
      name: 'Test',
      llm_model: 'local-model',
      embedding_model: 'test-emb'
    }

    store.activeNodeMetadata = [
      {
        id: 1,
        node_id: 'node_1',
        field_id: 'field_places',
        field_value: 'New York',
        user_edited: false
      }
    ]

    const updateSpy = vi.spyOn(api, 'updateNodeMetadata').mockResolvedValueOnce({
      status: 'saved',
      node_id: 'node_1'
    })

    await store.saveNodeMetadataField('node_1', 'field_places', 'San Francisco')

    expect(updateSpy).toHaveBeenCalledWith('test_proj', 'node_1', {
      field_places: 'San Francisco'
    })
    expect(store.activeNodeMetadata[0].field_value).toBe('San Francisco')
    expect(store.activeNodeMetadata[0].user_edited).toBe(true)
  })

  it('cancels autogeneration and resets status to idle', () => {
    const store = useWorkspaceStore()
    store.metadataJobStatus.status = 'running'

    store.cancelAutogeneration()
    expect(store.metadataJobStatus.status).toBe('idle')
  })
})