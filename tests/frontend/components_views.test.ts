import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createApp, h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useWorkspaceStore } from '@/stores/workspace'
import FieldCard from '@/components/schema/FieldCard.vue'
import ExportGateModal from '@/components/export/ExportGateModal.vue'
import BatchProgressModal from '@/components/metadata/BatchProgressModal.vue'

describe('Frontend Components and Modal Views', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.restoreAllMocks()
  })

  it('mounts and renders FieldCard with field properties', () => {
    const container = document.createElement('div')
    const mockField = {
      id: 'field_test_123',
      project_id: 'proj_1',
      field_slug: 'test_slug',
      field_label: 'Test Label',
      field_type: 'string' as const,
      description: 'Test description',
      is_required: true,
      order_index: 0
    }

    const app = createApp({
      render() {
        return h(FieldCard, {
          field: mockField,
          isFirst: true,
          isLast: false
        })
      }
    })
    app.use(pinia)
    app.mount(container)

    const inputs = container.querySelectorAll('input')
    const textarea = container.querySelector('textarea')

    expect((inputs[0] as HTMLInputElement).value).toBe('Test Label')
    expect((inputs[1] as HTMLInputElement).value).toBe('test_slug')
    expect((textarea as HTMLTextAreaElement).value).toBe('Test description')
    expect(container.innerHTML).toContain('ID: field_te')
    app.unmount()
  })

  it('mounts ExportGateModal and displays blocker diagnostics when blocked', () => {
    const store = useWorkspaceStore()
    store.currentProject = {
      id: 'proj_gate',
      name: 'Gate Project',
      llm_model: 'm',
      embedding_model: 'e'
    }
    store.isExportModalOpen = true
    store.validationResult = {
      is_valid: false,
      total_chunks: 3,
      total_blockers: 1,
      blockers: [
        {
          rule: 'empty_chunk',
          node_id: 'node_empty_id',
          document_id: 'doc_1',
          filename: 'notes.md',
          message: 'Chunk text is empty',
          remediation: 'Fill in chunk text'
        }
      ],
      summary: {
        empty_chunks: 1,
        uncalculated_embeddings: 0,
        schema_violations: 0
      }
    }

    const container = document.createElement('div')
    const app = createApp({
      render() {
        return h(ExportGateModal)
      }
    })
    app.use(pinia)
    app.mount(container)

    expect(container.innerHTML).toContain('Export Blocked: 1 Issues Found')
    expect(container.innerHTML).toContain('1 Empty Chunks')
    expect(container.innerHTML).toContain('notes.md')
    expect(container.innerHTML).toContain('Fill in chunk text')
    app.unmount()
  })

  it('mounts BatchProgressModal and displays failure diagnostic message', () => {
    const store = useWorkspaceStore()
    store.isBatchModalOpen = true
    store.metadataJobStatus = {
      status: 'failed',
      completed_partitions: 2,
      total_partitions: 5,
      completed_chunks: 20,
      total_chunks: 50,
      last_error: 'LM Studio endpoint timed out'
    }

    const container = document.createElement('div')
    const app = createApp({
      render() {
        return h(BatchProgressModal)
      }
    })
    app.use(pinia)
    app.mount(container)

    expect(container.innerHTML).toContain('Extraction stopped due to an error')
    expect(container.innerHTML).toContain('LM Studio endpoint timed out')
    expect(container.innerHTML).toContain('Resume Extraction')
    app.unmount()
  })
})