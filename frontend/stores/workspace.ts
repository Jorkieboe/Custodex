import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  apiClient,
  type Project,
  type DocumentSummary,
  type NodeItem,
  type SchemaField,
  fetchProjectById,
  fetchProjectSchema,
  createSchemaField,
  updateSchemaField,
  deleteSchemaField,
  replaceAllSchemaFields,
  fetchProjectDocuments,
  fetchProjectNodes,
  uploadProjectDocuments,
  deleteProjectDocument,
  splitProjectNode,
  mergeProjectNode,
  promoteProjectNode,
  demoteProjectNode,
  detachSelectionToHeader,
  updateProjectNode,
  type ChunkMetadataItem,
  type MetadataJobStatus,
  fetchNodeMetadata,
  updateNodeMetadata,
  startMetadataJob
} from '../services/api'

export type WorkspaceStep = 'ingestion' | 'chunks' | 'schema' | 'metadata' | 'embeddings' | 'export'

export const useWorkspaceStore = defineStore('workspace', () => {
  const currentProject = ref<Project | null>(null)
  const documents = ref<DocumentSummary[]>([])
  const nodes = ref<NodeItem[]>([])
  const schemaFields = ref<SchemaField[]>([])
  const activeNodeId = ref<string | null>(null)
  const activeNodeMetadata = ref<ChunkMetadataItem[]>([])
  const isInspectorOpen = ref(false)
  const isBatchModalOpen = ref(false)
  const nodesWithMetadata = ref<Set<string>>(new Set())
  const isGeneratingSingle = ref<string | null>(null)
  let sseEventSource: EventSource | null = null

  const metadataJobStatus = ref<MetadataJobStatus>({
    status: 'idle',
    completed_partitions: 0,
    total_partitions: 0,
    completed_chunks: 0,
    total_chunks: 0,
    last_error: null
  })
  const selectedNodeIds = ref<Set<string>>(new Set())
  const currentStep = ref<WorkspaceStep>('chunks')
  const isLoading = ref<boolean>(false)
  const errorMessage = ref<string | null>(null)

  const currentEmbeddingCounts = computed(() => {
    let current = 0
    let stale = 0
    let missing = 0
    for (const node of nodes.value) {
      if (node.embedding_status === 'current') current++
      else if (node.embedding_status === 'stale') stale++
      else if (node.embedding_status === 'missing') missing++
    }
    return { current, stale, missing }
  })

  async function loadProject(projectId: string) {
    isLoading.value = true
    errorMessage.value = null
    try {
      const proj = await fetchProjectById(projectId)
      currentProject.value = proj
      await reloadDocuments()
      await reloadNodes()
      await reloadSchema()
    } catch (err: any) {
      errorMessage.value = err.message || 'Failed to load project'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function reloadDocuments() {
    if (!currentProject.value) return
    const docs = await fetchProjectDocuments(currentProject.value.id)
    documents.value = docs
  }

  async function uploadFiles(files: File[]) {
    if (!currentProject.value) return
    isLoading.value = true
    try {
      await uploadProjectDocuments(currentProject.value.id, files)
      await reloadNodes()
    } catch (err: any) {
      errorMessage.value = err.message || 'File upload failed'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function removeDocument(documentId: string) {
    if (!currentProject.value) return
    isLoading.value = true
    try {
      await deleteProjectDocument(currentProject.value.id, documentId)
      await reloadNodes()
    } catch (err: any) {
      errorMessage.value = err.message || 'Failed to delete document'
    } finally {
      isLoading.value = false
    }
  }

  async function updateNode(nodeId: string, newText: string) {
    if (!currentProject.value) return
    const target = nodes.value.find((n: NodeItem) => n.id === nodeId)
    if (target) {
      target.text_content = newText
      if (target.embedding_status === 'current') {
        target.embedding_status = 'stale'
      }
    }
    try {
      const updated = await updateProjectNode(currentProject.value.id, nodeId, newText)
      const idx = nodes.value.findIndex((n: NodeItem) => n.id === nodeId)
      if (idx !== -1) {
        nodes.value[idx] = updated
      }
      return updated
    } catch (err: any) {
      errorMessage.value = err.message || 'Failed to update node'
      throw err
    }
  }

  function setStep(step: WorkspaceStep) {
    currentStep.value = step
  }

  function toggleNodeSelection(nodeId: string) {
    if (selectedNodeIds.value.has(nodeId)) {
      selectedNodeIds.value.delete(nodeId)
    } else {
      selectedNodeIds.value.add(nodeId)
    }
  }

  function selectAllNodes() {
    selectedNodeIds.value = new Set(nodes.value.map((n: NodeItem) => n.id))
  }

  function clearNodeSelection() {
    selectedNodeIds.value.clear()
  }

  async function splitNode(nodeId: string, topText: string, bottomText: string) {
    if (!currentProject.value) return
    const originalNodes = [...nodes.value]
    const targetIdx = nodes.value.findIndex((n: NodeItem) => n.id === nodeId)
    if (targetIdx === -1) return

    try {
      const [updatedUpper, newLower] = await splitProjectNode(
        currentProject.value.id,
        nodeId,
        topText,
        bottomText
      )
      await reloadNodes()
      return [updatedUpper, newLower]
    } catch (err: any) {
      nodes.value = originalNodes
      errorMessage.value = err.message || 'Split operation failed'
      throw err
    }
  }

  async function mergeNode(leadNodeId: string) {
    if (!currentProject.value) return
    const originalNodes = [...nodes.value]
    try {
      const merged = await mergeProjectNode(currentProject.value.id, leadNodeId)
      await reloadNodes()
      return merged
    } catch (err: any) {
      nodes.value = originalNodes
      errorMessage.value = err.message || 'Merge operation failed'
      throw err
    }
  }

  async function promoteNode(nodeId: string) {
    if (!currentProject.value) return
    console.log('tja')
    const originalNodes = [...nodes.value]
    try {
      const promoted = await promoteProjectNode(currentProject.value.id, nodeId)
      await reloadNodes()
      return promoted
    } catch (err: any) {
      nodes.value = originalNodes
      errorMessage.value = err.message || 'Promotion failed'
      throw err
    }
  }

  async function demoteNode(nodeId: string) {
    if (!currentProject.value) return
    const originalNodes = [...nodes.value]
    try {
      const demoted = await demoteProjectNode(currentProject.value.id, nodeId)
      await reloadNodes()
      return demoted
    } catch (err: any) {
      nodes.value = originalNodes
      errorMessage.value = err.message || 'Demotion failed'
      throw err
    }
  }

  async function detachSelection(nodeId: string, start: number, end: number) {
    if (!currentProject.value) return
    const originalNodes = [...nodes.value]
    try {
      const createdNodes = await detachSelectionToHeader(
        currentProject.value.id,
        nodeId,
        start,
        end
      )
      await reloadNodes()
      return createdNodes
    } catch (err: any) {
      nodes.value = originalNodes
      errorMessage.value = err.message || 'Detach header failed'
      throw err
    }
  }

  async function reloadNodes() {
    if (!currentProject.value) return
    const fetched = await fetchProjectNodes(currentProject.value.id)
    nodes.value = fetched
    await reloadDocuments()
  }

  return {
    currentProject,
    documents,
    nodes,
    selectedNodeIds,
    currentStep,
    isLoading,
    errorMessage,
    currentEmbeddingCounts,
    loadProject,
    reloadDocuments,
    uploadFiles,
    removeDocument,
    setStep,
    toggleNodeSelection,
    selectAllNodes,
    clearNodeSelection,
    updateNode,
    splitNode,
    mergeNode,
    promoteNode,
    demoteNode,
    detachSelection,
    reloadNodes,
    schemaFields,
    reloadSchema,
    addSchemaField,
    modifySchemaField,
    removeSchemaField,
    reorderSchemaFields,
    activeNodeId,
    activeNodeMetadata,
    isInspectorOpen,
    isBatchModalOpen,
    metadataJobStatus,
    selectNode,
    openInspector,
    closeInspector,
    openBatchModal,
    closeBatchModal,
    loadActiveNodeMetadata,
    saveNodeMetadataField,
    triggerMetadataExtraction,
    nodesWithMetadata,
    isGeneratingSingle,
    generateMetadataForNode,
    startAutogeneration,
    cancelAutogeneration,
    loadProjectMetadataOverview
  }

  function isNodeFullyExtracted(metaItems: ChunkMetadataItem[]): boolean {
    if (!metaItems || metaItems.length === 0) return false
    return metaItems.every((item) => {
      if (item.field_value === null || item.field_value === undefined) return false
      if (typeof item.field_value === 'string' && item.field_value.trim() === '') return false
      if (Array.isArray(item.field_value) && item.field_value.length === 0) return false
      return true
    })
  }

  async function loadProjectMetadataOverview() {
    if (!currentProject.value) return
    try {
      nodesWithMetadata.value.clear()
      const resp = await fetchProjectNodes(currentProject.value.id)
      for (const n of resp) {
        if (n.node_type === 'paragraph') {
          try {
            const meta = await fetchNodeMetadata(currentProject.value.id, n.id)
            if (isNodeFullyExtracted(meta)) {
              nodesWithMetadata.value.add(n.id)
            }
          } catch {
            // Ignore individual chunk metadata lookup errors
          }
        }
      }
    } catch (err) {
      console.error('Failed to load project metadata overview:', err)
    }
  }

  async function generateMetadataForNode(nodeId: string) {
    if (!currentProject.value) return
    isGeneratingSingle.value = nodeId
    try {
      await startMetadataJob(currentProject.value.id, {
        node_id: nodeId,
        force_overwrite: true
      })
      await loadActiveNodeMetadata(nodeId)
      nodesWithMetadata.value.add(nodeId)
    } catch (err: any) {
      console.error('Single chunk metadata generation failed:', err)
      errorMessage.value = err.message || 'Metadata generation failed for selected chunk'
      throw err
    } finally {
      isGeneratingSingle.value = null
    }
  }

  function startAutogeneration(options: { force_overwrite?: boolean; resume?: boolean } = {}) {
    if (!currentProject.value) return

    if (sseEventSource) {
      sseEventSource.close()
      sseEventSource = null
    }

    const totalParagraphs = nodes.value.filter((n: NodeItem) => n.node_type === 'paragraph').length
    metadataJobStatus.value = {
      status: 'running',
      completed_partitions: 0,
      total_partitions: 1,
      completed_chunks: 0,
      total_chunks: totalParagraphs,
      last_error: null
    }

    const baseUrl = apiClient.defaults.baseURL || 'http://localhost:8000'
    const sseUrl = `${baseUrl}/api/projects/${currentProject.value.id}/metadata/stream?force_overwrite=${Boolean(options.force_overwrite)}`

    console.log(`[Custodex SSE] Initiating EventSource connection to: ${sseUrl}`)
    console.log('[Custodex SSE] Current project:', currentProject.value)

    sseEventSource = new EventSource(sseUrl)

    sseEventSource.onopen = (event) => {
      console.log('[Custodex SSE] Stream connection OPENED successfully to:', sseUrl, event)
    }

    const handleMessage = (data: any) => {
      if (data.status) metadataJobStatus.value.status = data.status
      if (data.completed_chunks !== undefined) metadataJobStatus.value.completed_chunks = data.completed_chunks
      if (data.total_chunks !== undefined) metadataJobStatus.value.total_chunks = data.total_chunks
      if (data.completed_partitions !== undefined) metadataJobStatus.value.completed_partitions = data.completed_partitions
      if (data.total_partitions !== undefined) metadataJobStatus.value.total_partitions = data.total_partitions
      if (data.last_error) metadataJobStatus.value.last_error = data.last_error

      if (data.current_chunk_id) {
        nodesWithMetadata.value.add(data.current_chunk_id)
        if (activeNodeId.value === data.current_chunk_id) {
          loadActiveNodeMetadata(data.current_chunk_id)
        }
      }

      if (data.status === 'completed' || data.status === 'failed') {
        if (sseEventSource) {
          sseEventSource.close()
          sseEventSource = null
        }
        if (activeNodeId.value) {
          loadActiveNodeMetadata(activeNodeId.value)
        }
      }
    }

    sseEventSource.onmessage = (event: MessageEvent) => {
      try {
        console.log('[Custodex SSE] Received generic message:', event.data)
        const parsed = JSON.parse(event.data)
        handleMessage(parsed)
      } catch (err) {
        console.error('[Custodex SSE] Error parsing SSE event data:', err)
      }
    }

    sseEventSource.addEventListener('progress', (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data)
        console.log(`[Custodex SSE Progress] Chunk ${parsed.completed_chunks}/${parsed.total_chunks}:`, parsed)
        handleMessage(parsed)
      } catch (err) {
        console.error('[Custodex SSE] Error parsing SSE progress event:', err)
      }
    })

    sseEventSource.addEventListener('failure', (event: MessageEvent) => {
      try {
        console.error('[Custodex SSE] Received failure event from backend:', event.data)
        const parsed = JSON.parse(event.data)
        metadataJobStatus.value.status = 'failed'
        metadataJobStatus.value.last_error = parsed.last_error || 'Extraction failed on server'
        if (sseEventSource) {
          sseEventSource.close()
          sseEventSource = null
        }
        if (activeNodeId.value) {
          loadActiveNodeMetadata(activeNodeId.value)
        }
      } catch (err) {
        console.error('[Custodex SSE] Error parsing SSE failure event:', err)
      }
    })

    sseEventSource.addEventListener('complete', (event: MessageEvent) => {
      console.log('[Custodex SSE] Received complete event from backend:', event.data)
      metadataJobStatus.value.status = 'completed'
      if (sseEventSource) {
        sseEventSource.close()
        sseEventSource = null
      }
      if (activeNodeId.value) {
        loadActiveNodeMetadata(activeNodeId.value)
      }
    })

    sseEventSource.onerror = (event) => {
      const readyState = sseEventSource ? sseEventSource.readyState : 'unknown'
      console.error(`[Custodex SSE Error] Connection error. readyState = ${readyState} (0=CONNECTING, 1=OPEN, 2=CLOSED). Target URL: ${sseUrl}`, event)

      if (metadataJobStatus.value.status === 'running') {
        metadataJobStatus.value.status = 'failed'
        if (!metadataJobStatus.value.last_error) {
          metadataJobStatus.value.last_error = `Connection lost (EventSource state: ${readyState}). Ensure backend at ${baseUrl} is running.`
        }
      }
      if (sseEventSource) {
        sseEventSource.close()
        sseEventSource = null
      }
    }
  }

  function cancelAutogeneration() {
    if (sseEventSource) {
      sseEventSource.close()
      sseEventSource = null
    }
    metadataJobStatus.value.status = 'idle'
  }

  async function selectNode(id: string | null) {
    activeNodeId.value = id
    if (id && currentProject.value) {
      await loadActiveNodeMetadata(id)
    } else {
      activeNodeMetadata.value = []
    }
  }

  async function loadActiveNodeMetadata(nodeId: string) {
    if (!currentProject.value) return
    try {
      activeNodeMetadata.value = await fetchNodeMetadata(currentProject.value.id, nodeId)
    } catch (err) {
      console.error('Failed to load node metadata:', err)
    }
  }

  async function saveNodeMetadataField(nodeId: string, fieldId: string, value: any) {
    if (!currentProject.value) return
    const payload: Record<string, any> = { [fieldId]: value }
    await updateNodeMetadata(currentProject.value.id, nodeId, payload)
    const item = activeNodeMetadata.value.find((m: ChunkMetadataItem) => m.field_id === fieldId)
    if (item) {
      item.field_value = value
      item.user_edited = true
    }
    if (isNodeFullyExtracted(activeNodeMetadata.value)) {
      nodesWithMetadata.value.add(nodeId)
    } else {
      nodesWithMetadata.value.delete(nodeId)
    }
  }

  function openInspector() {
    isInspectorOpen.value = true
  }

  function closeInspector() {
    isInspectorOpen.value = false
  }

  function openBatchModal() {
    isBatchModalOpen.value = true
  }

  function closeBatchModal() {
    isBatchModalOpen.value = false
  }

  async function triggerMetadataExtraction(options: { force_overwrite?: boolean; resume?: boolean } = {}) {
    if (!currentProject.value) return
    await startMetadataJob(currentProject.value.id, options)
    metadataJobStatus.value.status = 'running'
    openBatchModal()
  }

  async function reloadSchema() {
    if (!currentProject.value) return
    const fields = await fetchProjectSchema(currentProject.value.id)
    schemaFields.value = fields
  }

  async function addSchemaField(payload: Partial<SchemaField>) {
    if (!currentProject.value) return
    const created = await createSchemaField(currentProject.value.id, payload)
    schemaFields.value.push(created)
    nodesWithMetadata.value.clear()
    await loadProjectMetadataOverview()
    return created
  }

  async function modifySchemaField(fieldId: string, payload: Partial<SchemaField>) {
    if (!currentProject.value) return
    const updated = await updateSchemaField(currentProject.value.id, fieldId, payload)
    const idx = schemaFields.value.findIndex((f: SchemaField) => f.id === fieldId)
    if (idx !== -1) {
      schemaFields.value[idx] = updated
    }
    return updated
  }

  async function removeSchemaField(fieldId: string) {
    if (!currentProject.value) return
    await deleteSchemaField(currentProject.value.id, fieldId)
    schemaFields.value = schemaFields.value.filter((f: SchemaField) => f.id !== fieldId)
    await loadProjectMetadataOverview()
  }

  async function reorderSchemaFields(newFields: SchemaField[]) {
    if (!currentProject.value) return
    schemaFields.value = [...newFields]
    const updated = await replaceAllSchemaFields(currentProject.value.id, newFields)
    schemaFields.value = updated
    await loadProjectMetadataOverview()
  }
})