import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkspaceStore } from '@/stores/workspace'
import * as api from '@/services/api'

describe('Validation Gate & Bundle Exporter Store Actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('runs validation and stores diagnostic blockers', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_export',
      name: 'Export Project',
      llm_model: 'mock-llm',
      embedding_model: 'mock-emb'
    }

    const mockValidation: api.ValidationResult = {
      is_valid: false,
      total_chunks: 2,
      total_blockers: 1,
      blockers: [
        {
          rule: 'uncalculated_embedding',
          node_id: 'n_stale',
          document_id: 'doc_1',
          filename: 'doc.md',
          message: "Chunk embedding status is 'stale'",
          remediation: 'Refresh embeddings'
        }
      ],
      summary: {
        empty_chunks: 0,
        uncalculated_embeddings: 1,
        schema_violations: 0
      }
    }

    vi.spyOn(api, 'fetchProjectValidation').mockResolvedValueOnce(mockValidation)

    const result = await store.runValidation()
    expect(result?.is_valid).toBe(false)
    expect(store.validationResult?.total_blockers).toBe(1)
    expect(store.validationResult?.blockers[0].rule).toBe('uncalculated_embedding')
  })

  it('navigates to blocker node and routes to corresponding workspace step', () => {
    const store = useWorkspaceStore()
    store.currentStep = 'chunks'
    store.isExportModalOpen = true

    const blocker: api.ValidationBlocker = {
      rule: 'uncalculated_embedding',
      node_id: 'n_vec',
      document_id: 'doc_1',
      filename: 'sample.md',
      message: 'Vector missing',
      remediation: 'Run embeddings'
    }

    store.navigateToBlocker(blocker)

    expect(store.activeNodeId).toBe('n_vec')
    expect(store.currentStep).toBe('embeddings')
    expect(store.isExportModalOpen).toBe(false)
  })

  it('triggers bundle download via API service', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_export',
      name: 'Export Project',
      llm_model: 'mock-llm',
      embedding_model: 'mock-emb'
    }

    const mockBlob = new Blob(['zip content'], { type: 'application/zip' })
    const downloadSpy = vi.spyOn(api, 'downloadExportBundle').mockResolvedValueOnce({
      blob: mockBlob,
      filename: 'export-bundle.zip'
    })

    // Mock DOM elements to prevent JSDOM errors on a.click()
    const mockClick = vi.fn()
    const origCreateElement = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      const el = origCreateElement(tag)
      if (tag === 'a') {
        el.click = mockClick
      }
      return el
    })

    await store.executeBundleDownload()
    expect(downloadSpy).toHaveBeenCalledWith('proj_export')
  })
})