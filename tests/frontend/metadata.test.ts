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