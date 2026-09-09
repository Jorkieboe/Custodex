<script setup lang="ts">
import { ref, computed } from 'vue'
import { type NodeItem } from '../../services/api'
import { useWorkspaceStore } from '../../stores/workspace'
import HeaderNodeView from './HeaderNodeView.vue'
import ChunkNodeView from './ChunkNodeView.vue'

const store = useWorkspaceStore()

const floatingToolbarVisible = ref(false)
const floatingToolbarPos = ref({ x: 0, y: 0 })
const activeSelection = ref<{
  nodeId: string
  text: string
  start: number
  end: number
} | null>(null)

const headerChildCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const node of store.nodes) {
    if (node.node_type === 'paragraph' && node.parent_id) {
      counts[node.parent_id] = (counts[node.parent_id] || 0) + 1
    }
  }
  return counts
})

function handleSelectionChange(nodeId: string, text: string, start: number, end: number) {
  activeSelection.value = { nodeId, text, start, end }
  const selection = window.getSelection()
  if (selection && selection.rangeCount > 0) {
    const rect = selection.getRangeAt(0).getBoundingClientRect()
    floatingToolbarPos.value = {
      x: rect.left + rect.width / 2,
      y: rect.top - 40
    }
    floatingToolbarVisible.value = true
  }
}

function clearSelection() {
  floatingToolbarVisible.value = false
  activeSelection.value = null
}

async function handleMakeHeader() {
  if (!activeSelection.value) return
  const { nodeId, start, end } = activeSelection.value
  await store.detachSelection(nodeId, start, end)
  clearSelection()
}

async function handleSplitFromSelection() {
  if (!activeSelection.value) return
  const { nodeId, start } = activeSelection.value
  const targetNode = store.nodes.find((n: NodeItem) => n.id === nodeId)
  if (!targetNode) return
  const top = targetNode.text_content.slice(0, start).trim()
  const bottom = targetNode.text_content.slice(start).trim()
  if (top && bottom) {
    await store.splitNode(nodeId, top, bottom)
  }
  clearSelection()
}

function canMerge(index: number): boolean {
  if (index >= store.nodes.length - 1) return false
  const current = store.nodes[index]
  const next = store.nodes[index + 1]
  return current.node_type === 'paragraph' && next.node_type === 'paragraph'
}
</script>

<template>
  <div class="chunk-canvas-wrapper" @click="clearSelection">
    <!-- Multi-Chunk Selection Toolbar -->
    <div v-if="store.nodes.length > 0" class="selection-action-bar">
      <div class="selection-info">
        <label class="select-all-label">
          <input
            type="checkbox"
            :checked="store.selectedNodeIds.size === store.nodes.length && store.nodes.length > 0"
            @change="$event => ($event.target as HTMLInputElement).checked ? store.selectAllNodes() : store.clearNodeSelection()"
          />
          <span>Select All ({{ store.selectedNodeIds.size }} / {{ store.nodes.length }})</span>
        </label>
      </div>

      <div v-if="store.selectedNodeIds.size > 0" class="batch-buttons">
        <span class="batch-hint">Batch operations available for selected chunks</span>
        <button class="btn btn-sm btn-secondary" @click="store.clearNodeSelection">
          Deselect
        </button>
      </div>
    </div>

    <!-- Visual Canvas Content -->
    <div class="canvas-scroll-container">
      <div v-if="store.documents.length === 0" class="canvas-empty">
        <p>No documents imported yet. Import documents from Ingestion to get started.</p>
      </div>

      <div v-else-if="store.nodes.length === 0" class="canvas-empty">
        <p>Document has no structural nodes.</p>
      </div>

      <div v-else class="nodes-list">
        <template v-for="(node, index) in store.nodes" :key="node.id">
          <HeaderNodeView
            v-if="node.node_type === 'header'"
            :node="node"
            :child-count="headerChildCounts[node.id] || 0"
            @demote="id => store.demoteNode(id)"
          />
          <ChunkNodeView
            v-else
            :node="node"
            :can-merge="canMerge(index)"
            @split="(id, top, bot) => store.splitNode(id, top, bot)"
            @merge="id => store.mergeNode(id)"
            @promote="id => store.promoteNode(id)"
            @selection-change="handleSelectionChange"
          />
        </template>
      </div>
    </div>

    <!-- Floating Text Selection Toolbar -->
    <div
      v-if="floatingToolbarVisible"
      class="floating-selection-toolbar"
      :style="{ top: `${floatingToolbarPos.y}px`, left: `${floatingToolbarPos.x}px` }"
      @click.stop
    >
      <button class="float-btn" @click="handleMakeHeader">
        ✦ Make Header
      </button>
      <button class="float-btn" @click="handleSplitFromSelection">
        ✂ Split Chunk Here
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.chunk-canvas-wrapper {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: calc(100vh - #{$header-height});
  background-color: $color-bg;
  position: relative;
}

.selection-action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 24px;
  background-color: $color-surface;
  border-bottom: 1px solid $color-border;
  font-size: 13px;
}

.select-all-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  color: $color-text-secondary;

  input {
    accent-color: $color-primary;
  }
}

.batch-buttons {
  display: flex;
  align-items: center;
  gap: 12px;
}

.batch-hint {
  font-size: 12px;
  color: $color-text-muted;
}

.canvas-scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.nodes-list {
  max-width: 860px;
  margin: 0 auto;
}

.canvas-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: $color-text-muted;
  font-size: 15px;
}

.floating-selection-toolbar {
  position: fixed;
  transform: translateX(-50%);
  background-color: $color-surface;
  border: 1px solid $color-primary;
  border-radius: $radius-md;
  box-shadow: $shadow-modal;
  display: flex;
  padding: 4px;
  gap: 4px;
  z-index: 3000;
}

.float-btn {
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  color: $color-text-primary;
  border-radius: $radius-sm;
  cursor: pointer;

  &:hover {
    background-color: $color-primary;
    color: #000;
  }
}

.btn {
  padding: 4px 10px;
  border-radius: $radius-md;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;

  &.btn-secondary {
    background-color: $color-surface-hover;
    color: $color-text-primary;
    border: 1px solid $color-border;
    &:hover {
      background-color: lighten(#334155, 5%);
    }
  }
}
</style>