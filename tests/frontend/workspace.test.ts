import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkspaceStore } from '@/stores/workspace'
import * as api from '@/services/api'

describe('Workspace Pinia Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('initializes with default values', () => {
    const store = useWorkspaceStore()
    expect(store.currentProject).toBeNull()
    expect(store.documents).toEqual([])
    expect(store.currentStep).toBe('chunks')
    expect(store.selectedNodeIds.size).toBe(0)
  })

  it('switches steps without resetting active nodes or selections', () => {
    const store = useWorkspaceStore()
    store.nodes = [
      {
        id: 'chunk_1',
        document_id: 'doc_1',
        parent_id: null,
        node_type: 'paragraph',
        text_content: 'Test chunk text',
        order_index: 0,
        embedding_status: 'current'
      }
    ]
    store.toggleNodeSelection('chunk_1')
    expect(store.selectedNodeIds.has('chunk_1')).toBe(true)

    store.setStep('embeddings')
    expect(store.currentStep).toBe('embeddings')
    expect(store.nodes.length).toBe(1)
    expect(store.selectedNodeIds.has('chunk_1')).toBe(true)

    store.setStep('schema')
    expect(store.currentStep).toBe('schema')
    expect(store.nodes.length).toBe(1)
  })

  it('computes embedding status counts accurately', () => {
    const store = useWorkspaceStore()
    store.nodes = [
      { id: '1', document_id: 'd', parent_id: null, node_type: 'paragraph', text_content: 'A', order_index: 0, embedding_status: 'current' },
      { id: '2', document_id: 'd', parent_id: null, node_type: 'paragraph', text_content: 'B', order_index: 1, embedding_status: 'stale' },
      { id: '3', document_id: 'd', parent_id: null, node_type: 'paragraph', text_content: 'C', order_index: 2, embedding_status: 'missing' }
    ]

    expect(store.currentEmbeddingCounts).toEqual({
      current: 1,
      stale: 1,
      missing: 1
    })
  })

  it('handles multi-node selection toggle and select all', () => {
    const store = useWorkspaceStore()
    store.nodes = [
      { id: 'n1', document_id: 'd', parent_id: null, node_type: 'paragraph', text_content: 'A', order_index: 0, embedding_status: 'current' },
      { id: 'n2', document_id: 'd', parent_id: null, node_type: 'paragraph', text_content: 'B', order_index: 1, embedding_status: 'current' }
    ]

    store.toggleNodeSelection('n1')
    expect(store.selectedNodeIds.has('n1')).toBe(true)
    expect(store.selectedNodeIds.has('n2')).toBe(false)

    store.selectAllNodes()
    expect(store.selectedNodeIds.size).toBe(2)

    store.clearNodeSelection()
    expect(store.selectedNodeIds.size).toBe(0)
  })

  it('updates node text and transitions status to stale', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_test',
      name: 'Test',
      llm_model: 'm',
      embedding_model: 'e'
    }
    store.nodes = [
      {
        id: 'chunk_1',
        document_id: 'doc_1',
        parent_id: null,
        node_type: 'paragraph',
        text_content: 'Initial text',
        order_index: 0,
        embedding_status: 'current'
      }
    ]

    vi.spyOn(api, 'updateProjectNode').mockResolvedValueOnce({
      id: 'chunk_1',
      document_id: 'doc_1',
      parent_id: null,
      node_type: 'paragraph',
      text_content: 'Updated text with\n\nnew line',
      order_index: 0,
      embedding_status: 'stale'
    })

    await store.updateNode('chunk_1', 'Updated text with\n\nnew line')
    expect(store.nodes[0].text_content).toBe('Updated text with\n\nnew line')
    expect(store.nodes[0].embedding_status).toBe('stale')
  })
})