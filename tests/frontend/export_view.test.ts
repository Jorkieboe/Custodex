import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createApp, h, nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkspaceStore } from '@/stores/workspace'
import ExportView from '@/components/export/ExportView.vue'
import * as api from '@/services/api'

describe('ExportView Component', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.restoreAllMocks()
  })

  it('runs validation on mount and renders satisfied status when valid', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_export_screen',
      name: 'Screen Test',
      llm_model: 'mock-llm',
      embedding_model: 'mock-emb'
    }

    vi.spyOn(api, 'fetchProjectSchema').mockResolvedValueOnce([])
    vi.spyOn(api, 'fetchProjectValidation').mockResolvedValueOnce({
      is_valid: true,
      total_chunks: 3,
      total_blockers: 0,
      blockers: [],
      summary: {
        empty_chunks: 0,
        uncalculated_embeddings: 0,
        schema_violations: 0
      }
    })

    const container = document.createElement('div')
    const app = createApp({
      render() {
        return h(ExportView)
      }
    })
    app.use(pinia)
    app.mount(container)

    await new Promise((r) => setTimeout(r, 50))

    expect(container.innerHTML).toContain('All Validation Invariants Satisfied')
    expect(container.innerHTML).toContain('db.faiss')
    expect(container.innerHTML).toContain('dbmetadata.json')
    expect(container.innerHTML).toContain('metadatascheme.json')
    const exportBtn = container.querySelector('button.btn-export') as HTMLButtonElement
    expect(exportBtn.disabled).toBe(false)
    app.unmount()
  })

  it('renders blockers and disables export button when validation fails', async () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_export_blocked',
      name: 'Blocked Test',
      llm_model: 'mock-llm',
      embedding_model: 'mock-emb'
    }

    vi.spyOn(api, 'fetchProjectSchema').mockResolvedValueOnce([])
    vi.spyOn(api, 'fetchProjectValidation').mockResolvedValueOnce({
      is_valid: false,
      total_chunks: 5,
      total_blockers: 1,
      blockers: [
        {
          rule: 'uncalculated_embedding',
          node_id: 'node_test_1',
          document_id: 'doc_1',
          filename: 'guide.docx',
          message: "Chunk embedding status is 'stale' (must be 'current').",
          remediation: 'Refresh embeddings in the Embedding Refresh step.'
        }
      ],
      summary: {
        empty_chunks: 0,
        uncalculated_embeddings: 1,
        schema_violations: 0
      }
    })

    const container = document.createElement('div')
    const app = createApp({
      render() {
        return h(ExportView)
      }
    })
    app.use(pinia)
    app.mount(container)

    await new Promise((r) => setTimeout(r, 50))

    expect(container.innerHTML).toContain('Export Blocked: 1 Issue(s) Detected')
    expect(container.innerHTML).toContain('guide.docx')
    expect(container.innerHTML).toContain('Jump to Chunk →')
    const exportBtn = container.querySelector('button.btn-export') as HTMLButtonElement
    expect(exportBtn.disabled).toBe(true)
    app.unmount()
  })
})