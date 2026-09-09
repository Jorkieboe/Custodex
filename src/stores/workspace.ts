import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  type Project,
  type DocumentSummary,
  type NodeItem,
  fetchProjectById,
  fetchProjectDocuments,
  fetchProjectNodes,
  uploadProjectDocuments,
  deleteProjectDocument,
  splitProjectNode,
  mergeProjectNode,
  promoteProjectNode,
  detachSelectionToHeader,
  updateProjectNode
} from '../services/api'

export type WorkspaceStep = 'ingestion' | 'chunks' | 'schema' | 'metadata' | 'embeddings' | 'export'

export const useWorkspaceStore = defineStore('workspace', () => {
  const currentProject = ref<Project | null>(null)
  const documents = ref<DocumentSummary[]>([])
  const activeDocumentId = ref<string | null>(null)
  const nodes = ref<NodeItem[]>([])
  const selectedNodeIds = ref<Set<string>>(new Set())
  const currentStep = ref<WorkspaceStep>('chunks')
  const isLoading = ref<boolean>(false)
  const errorMessage = ref<string | null>(null)

  const activeDocument = computed(() => {
    return documents.value.find((d) => d.id === activeDocumentId.value) || null
  })

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
      if (documents.value.length > 0) {
        await selectDocument(documents.value[0].id)
      } else {
        nodes.value = []
        activeDocumentId.value = null
      }
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

  async function selectDocument(documentId: string) {
    if (!currentProject.value) return
    activeDocumentId.value = documentId
    selectedNodeIds.value.clear()
    isLoading.value = true
    try {
      const fetchedNodes = await fetchProjectNodes(currentProject.value.id, documentId)
      nodes.value = fetchedNodes
    } catch (err: any) {
      errorMessage.value = err.message || 'Failed to load document nodes'
    } finally {
      isLoading.value = false
    }
  }

  async function uploadFiles(files: File[]) {
    if (!currentProject.value) return
    isLoading.value = true
    try {
      await uploadProjectDocuments(currentProject.value.id, files)
      await reloadDocuments()
      if (documents.value.length > 0 && !activeDocumentId.value) {
        await selectDocument(documents.value[0].id)
      }
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
      await reloadDocuments()
      if (activeDocumentId.value === documentId) {
        if (documents.value.length > 0) {
          await selectDocument(documents.value[0].id)
        } else {
          activeDocumentId.value = null
          nodes.value = []
        }
      }
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
    if (!currentProject.value || !activeDocumentId.value) return
    const fetched = await fetchProjectNodes(currentProject.value.id, activeDocumentId.value)
    nodes.value = fetched
    await reloadDocuments()
  }

  return {
    currentProject,
    documents,
    activeDocumentId,
    activeDocument,
    nodes,
    selectedNodeIds,
    currentStep,
    isLoading,
    errorMessage,
    currentEmbeddingCounts,
    loadProject,
    reloadDocuments,
    selectDocument,
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
    detachSelection,
    reloadNodes
  }
})