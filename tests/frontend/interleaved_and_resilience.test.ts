import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkspaceStore } from '@/stores/workspace'
import * as api from '@/services/api'

describe('Interleaved Workflows and Batch Resilience', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.spyOn(api, 'fetchProjectNodes').mockResolvedValue([])
    vi.spyOn(api, 'fetchProjectDocuments').mockResolvedValue([])
    vi.spyOn(api, 'fetchProjectSchema').mockResolvedValue([])
  })

  it('preserves active selection and step state during non-linear transitions', () => {
    const store = useWorkspaceStore()
    store.nodes = [
      { id: 'c1', document_id: 'd1', parent_id: null, node_type: 'paragraph', text_content: 'Text 1', order_index: 0, embedding_status: 'current' },
      { id: 'c2', document_id: 'd1', parent_id: null, node_type: 'paragraph', text_content: 'Text 2', order_index: 1, embedding_status: 'stale' }
    ]

    store.toggleNodeSelection('c1')
    expect(store.selectedNodeIds.has('c1')).toBe(true)

    store.setStep('metadata')
    expect(store.currentStep).toBe('metadata')
    expect(store.selectedNodeIds.has('c1')).toBe(true)

    store.setStep('embeddings')
    expect(store.currentStep).toBe('embeddings')
    expect(store.selectedNodeIds.has('c1')).toBe(true)

    store.setStep('export')
    expect(store.currentStep).toBe('export')
    expect(store.nodes.length).toBe(2)
  })

  it('clears metadata tracking when a chunk is split', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_interleaved',
      name: 'Interleaved Proj',
      llm_model: 'mock-llm',
      embedding_model: 'mock-emb'
    }
    store.nodes = [
      { id: 'c1', document_id: 'd1', parent_id: null, node_type: 'paragraph', text_content: 'Top. Bottom.', order_index: 0, embedding_status: 'current' }
    ]
    store.nodesWithMetadata.add('c1')
    expect(store.nodesWithMetadata.has('c1')).toBe(true)

    vi.spyOn(api, 'splitProjectNode').mockResolvedValueOnce([
      { id: 'c1', document_id: 'd1', parent_id: null, node_type: 'paragraph', text_content: 'Top.', order_index: 0, embedding_status: 'stale' },
      { id: 'c2', document_id: 'd1', parent_id: null, node_type: 'paragraph', text_content: 'Bottom.', order_index: 1, embedding_status: 'missing' }
    ])

    await store.splitNode('c1', 'Top.', 'Bottom.')
    expect(store.nodesWithMetadata.has('c1')).toBe(false)
    expect(store.nodesWithMetadata.has('c2')).toBe(false)
  })

  it('updates dirty embedding flags appropriately upon manual chunk mutations', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_interleaved',
      name: 'Interleaved Proj',
      llm_model: 'mock-llm',
      embedding_model: 'mock-emb'
    }
    store.nodes = [
      { id: 'c1', document_id: 'd1', parent_id: null, node_type: 'paragraph', text_content: 'Original', order_index: 0, embedding_status: 'current' }
    ]

    vi.spyOn(api, 'updateProjectNode').mockResolvedValueOnce({
      id: 'c1',
      document_id: 'd1',
      parent_id: null,
      node_type: 'paragraph',
      text_content: 'Original modified',
      order_index: 0,
      embedding_status: 'stale'
    })

    await store.updateNode('c1', 'Original modified')
    expect(store.nodes[0].embedding_status).toBe('stale')
    expect(store.currentEmbeddingCounts.stale).toBe(1)
    expect(store.currentEmbeddingCounts.current).toBe(0)
  })

  it('handles batch extraction failure and supports resuming from failure point', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_interleaved',
      name: 'Interleaved Proj',
      llm_model: 'mock-llm',
      embedding_model: 'mock-emb'
    }

    const startSpy = vi.spyOn(api, 'startMetadataJob').mockResolvedValueOnce({
      status: 'started'
    })

    await store.triggerMetadataExtraction({ force_overwrite: false, resume: true })
    expect(startSpy).toHaveBeenCalledWith('proj_interleaved', {
      force_overwrite: false,
      resume: true
    })
    expect(store.isBatchModalOpen).toBe(true)
    expect(store.metadataJobStatus.status).toBe('running')
  })
})