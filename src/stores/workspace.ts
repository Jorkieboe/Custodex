import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
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
  updateProjectNode
} from '../services/api'

export type WorkspaceStep = 'ingestion' | 'chunks' | 'schema' | 'metadata' | 'embeddings' | 'export'

export const useWorkspaceStore = defineStore('workspace', () => {
  const currentProject = ref<Project | null>(null)
  const documents = ref<DocumentSummary[]>([])
  const nodes = ref<NodeItem[]>([])
  const schemaFields = ref<SchemaField[]>([])
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
    const target = nodes.value.find((n) => n.id === nodeId)
    if (target) {
      target.text_content = newText
      if (target.embedding_status === 'current') {
        target.embedding_status = 'stale'
      }
    }
    try {
      const updated = await updateProjectNode(currentProject.value.id, nodeId, newText)
      const idx = nodes.value.findIndex((n) => n.id === nodeId)
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
    selectedNodeIds.value = new Set(nodes.value.map((n) => n.id))
  }

  function clearNodeSelection() {
    selectedNodeIds.value.clear()
  }

  async function splitNode(nodeId: string, topText: string, bottomText: string) {
    if (!currentProject.value) return
    const originalNodes = [...nodes.value]
    const targetIdx = nodes.value.findIndex((n) => n.id === nodeId)
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
    reorderSchemaFields
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
    return created
  }

  async function modifySchemaField(fieldId: string, payload: Partial<SchemaField>) {
    if (!currentProject.value) return
    const updated = await updateSchemaField(currentProject.value.id, fieldId, payload)
    const idx = schemaFields.value.findIndex((f) => f.id === fieldId)
    if (idx !== -1) {
      schemaFields.value[idx] = updated
    }
    return updated
  }

  async function removeSchemaField(fieldId: string) {
    if (!currentProject.value) return
    await deleteSchemaField(currentProject.value.id, fieldId)
    schemaFields.value = schemaFields.value.filter((f) => f.id !== fieldId)
  }

  async function reorderSchemaFields(newFields: SchemaField[]) {
    if (!currentProject.value) return
    schemaFields.value = [...newFields]
    const updated = await replaceAllSchemaFields(currentProject.value.id, newFields)
    schemaFields.value = updated
  }
})