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

  it('updates proposal when accepting one of multiple split points (A B C)', async () => {
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
      original_text: 'Slice A. Slice B. Slice C.',
      order_index: 0,
      proposed_splits: [
        { split_index: 8, confidence: 0.85, before_snippet: '', after_snippet: '' },
        { split_index: 17, confidence: 0.85, before_snippet: '', after_snippet: '' }
      ],
      proposed_slices: [
        { text: 'Slice A.', token_count: 2 },
        { text: 'Slice B.', token_count: 2 },
        { text: 'Slice C.', token_count: 2 }
      ]
    })

    vi.spyOn(api, 'acceptSemanticSplits').mockResolvedValueOnce([
      { id: 'n1', document_id: 'doc_1', parent_id: null, node_type: 'paragraph', text_content: 'Slice A.', order_index: 0, embedding_status: 'stale' },
      { id: 'n2_new', document_id: 'doc_1', parent_id: null, node_type: 'paragraph', text_content: 'Slice B. Slice C.', order_index: 1, embedding_status: 'missing' }
    ])

    await store.acceptProposedSplit('n1', [8])

    // n1 (Slice A) is now a single-slice paragraph with no remaining splits
    expect(store.semanticSplitProposals.has('n1')).toBe(false)

    // n2_new (Slice B + Slice C) receives the updated proposal with the remaining split
    expect(store.semanticSplitProposals.has('n2_new')).toBe(true)
    const n2Prop = store.semanticSplitProposals.get('n2_new')
    expect(n2Prop?.proposed_slices.length).toBe(2)
    expect(n2Prop?.proposed_splits.length).toBe(1)
  })

  it('splits proposal into two separate proposals when splitting in the middle (A B C D)', async () => {
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
      original_text: 'Slice A. Slice B. Slice C. Slice D.',
      order_index: 0,
      proposed_splits: [
        { split_index: 8, confidence: 0.85, before_snippet: '', after_snippet: '' },
        { split_index: 17, confidence: 0.85, before_snippet: '', after_snippet: '' },
        { split_index: 26, confidence: 0.85, before_snippet: '', after_snippet: '' }
      ],
      proposed_slices: [
        { text: 'Slice A.', token_count: 2 },
        { text: 'Slice B.', token_count: 2 },
        { text: 'Slice C.', token_count: 2 },
        { text: 'Slice D.', token_count: 2 }
      ]
    })

    vi.spyOn(api, 'acceptSemanticSplits').mockResolvedValueOnce([
      { id: 'n1', document_id: 'doc_1', parent_id: null, node_type: 'paragraph', text_content: 'Slice A. Slice B.', order_index: 0, embedding_status: 'stale' },
      { id: 'n2_new', document_id: 'doc_1', parent_id: null, node_type: 'paragraph', text_content: 'Slice C. Slice D.', order_index: 1, embedding_status: 'missing' }
    ])

    // Accept split 1 (between B and C)
    await store.acceptProposedSplit('n1', [17])

    // n1 (Slice A + B) retains its proposal with 1 split (between A and B)
    expect(store.semanticSplitProposals.has('n1')).toBe(true)
    const n1Prop = store.semanticSplitProposals.get('n1')
    expect(n1Prop?.proposed_slices.length).toBe(2)
    expect(n1Prop?.proposed_splits.length).toBe(1)

    // n2_new (Slice C + D) receives a proposal with 1 split (between C and D)
    expect(store.semanticSplitProposals.has('n2_new')).toBe(true)
    const n2Prop = store.semanticSplitProposals.get('n2_new')
    expect(n2Prop?.proposed_slices.length).toBe(2)
    expect(n2Prop?.proposed_splits.length).toBe(1)
  })

  it('merges adjacent slices when rejecting an individual inline split divider', () => {
    const store = useWorkspaceStore()
    store.semanticSplitProposals.set('n1', {
      node_id: 'n1',
      document_id: 'doc_1',
      original_text: 'A. B. C.',
      order_index: 0,
      proposed_splits: [
        { split_index: 2, confidence: 0.8, before_snippet: '', after_snippet: '' },
        { split_index: 5, confidence: 0.8, before_snippet: '', after_snippet: '' }
      ],
      proposed_slices: [
        { text: 'A.', token_count: 1 },
        { text: 'B.', token_count: 1 },
        { text: 'C.', token_count: 1 }
      ]
    })

    // Reject divider 0 (between A and B)
    store.rejectProposedSplit('n1', 0)

    const prop = store.semanticSplitProposals.get('n1')
    expect(prop?.proposed_splits.length).toBe(1)
    expect(prop?.proposed_slices.length).toBe(2)
    expect(prop?.proposed_slices[0].text).toContain('A.\n\nB.')
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