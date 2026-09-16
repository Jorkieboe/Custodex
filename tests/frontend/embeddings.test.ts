import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkspaceStore } from '@/stores/workspace'
import * as api from '@/services/api'

describe('Semantic Splitting and Embeddings Store Actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.spyOn(api, 'fetchProjectNodes').mockResolvedValue([])
    vi.spyOn(api, 'fetchProjectDocuments').mockResolvedValue([])
  })

  it('manages semantic split preview and candidate rejection', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_embed',
      name: 'Embeddings Proj',
      llm_model: 'mock-llm',
      embedding_model: 'mock-emb'
    }

    const mockPreview: api.NodeSemanticSplitPreview[] = [
      {
        node_id: 'node_alpha',
        document_id: 'doc_1',
        original_text: 'First half. Second half.',
        order_index: 0,
        proposed_splits: [
          {
            split_index: 12,
            confidence: 0.85,
            before_snippet: 'First half.',
            after_snippet: 'Second half.'
          }
        ],
        proposed_slices: ['First half.', 'Second half.']
      }
    ]

    vi.spyOn(api, 'previewSemanticSplits').mockResolvedValueOnce(mockPreview)
    await store.requestSemanticSplitPreview(['node_alpha'])

    expect(store.semanticSplitProposals.has('node_alpha')).toBe(true)

    store.rejectProposedSplit('node_alpha')
    expect(store.semanticSplitProposals.has('node_alpha')).toBe(false)
  })

  it('accepts single proposed split for a node', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_embed',
      name: 'Embeddings Proj',
      llm_model: 'mock-llm',
      embedding_model: 'mock-emb'
    }

    store.semanticSplitProposals.set('n1', {
      node_id: 'n1',
      document_id: 'doc_1',
      original_text: 'First slice. Second slice.',
      order_index: 0,
      proposed_splits: [{ split_index: 12, confidence: 0.85, before_snippet: '', after_snippet: '' }],
      proposed_slices: [{ text: 'First slice.', token_count: 3 }, { text: 'Second slice.', token_count: 3 }]
    })

    const acceptSpy = vi.spyOn(api, 'acceptSemanticSplits').mockResolvedValueOnce([
      { id: 'n1', document_id: 'd', parent_id: null, node_type: 'paragraph', text_content: 'First slice.', order_index: 0, embedding_status: 'stale' },
      { id: 'n2', document_id: 'd', parent_id: null, node_type: 'paragraph', text_content: 'Second slice.', order_index: 1, embedding_status: 'missing' }
    ])

    await store.acceptProposedSplit('n1', [12])
    expect(acceptSpy).toHaveBeenCalledWith('proj_embed', [{ node_id: 'n1', split_indices: [12] }])
    expect(store.semanticSplitProposals.has('n1')).toBe(false)
  })

  it('accepts all semantic splits in batch', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_embed',
      name: 'Embeddings Proj',
      llm_model: 'mock-llm',
      embedding_model: 'mock-emb'
    }

    store.semanticSplitProposals.set('n1', {
      node_id: 'n1',
      document_id: 'doc_1',
      original_text: 'Text 1. Text 2.',
      order_index: 0,
      proposed_splits: [{ split_index: 8, confidence: 0.9, before_snippet: '', after_snippet: '' }],
      proposed_slices: ['Text 1.', 'Text 2.']
    })

    const acceptSpy = vi.spyOn(api, 'acceptSemanticSplits').mockResolvedValueOnce([
      { id: 'n1', document_id: 'd', parent_id: null, node_type: 'paragraph', text_content: 'Text 1.', order_index: 0, embedding_status: 'stale' },
      { id: 'n2', document_id: 'd', parent_id: null, node_type: 'paragraph', text_content: 'Text 2.', order_index: 1, embedding_status: 'missing' }
    ])

    await store.acceptAllProposedSplits()
    expect(acceptSpy).toHaveBeenCalledWith('proj_embed', [{ node_id: 'n1', split_indices: [8] }])
    expect(store.semanticSplitProposals.size).toBe(0)
  })

  it('validates embedding model switch with confirmation', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_embed',
      name: 'Embeddings Proj',
      llm_model: 'mock-llm',
      embedding_model: 'model-a'
    }

    vi.spyOn(api, 'checkEmbeddingModelSwitch').mockResolvedValueOnce({
      action: 'switched',
      requires_confirmation: false
    })

    const res = await store.validateModelSwitch('model-b', true)
    expect(res?.action).toBe('switched')
    expect(store.currentProject.embedding_model).toBe('model-b')
  })

  it('triggers refreshEmbeddingsStream and sets isEmbeddingRefreshing to true', () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_embed_test',
      name: 'Embeddings Proj',
      llm_model: 'mock-llm',
      embedding_model: 'test-emb'
    }

    const mockEventSource = vi.fn().mockImplementation(() => ({
      addEventListener: vi.fn(),
      close: vi.fn(),
      onerror: null
    }))
    vi.stubGlobal('EventSource', mockEventSource)

    store.refreshEmbeddingsStream()
    expect(store.isEmbeddingRefreshing).toBe(true)
    expect(mockEventSource).toHaveBeenCalledWith(
      'http://localhost:8000/api/projects/proj_embed_test/embeddings/stream?batch_size=16'
    )
    vi.unstubAllGlobals()
  })
})