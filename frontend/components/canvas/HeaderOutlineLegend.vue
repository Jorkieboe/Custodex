<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { type NodeItem, type DocumentSummary } from '../../services/api'

interface HeaderItem {
  node: NodeItem
  level: number
  children: HeaderItem[]
}

interface DocumentGroup {
  document: DocumentSummary
  colorPalette: BookColorPalette
  isExpanded: boolean
  headers: HeaderItem[]
}

interface BookColorPalette {
  id: number
  bookBg: string
  bookText: string
  headerBg: string
  subHeaderBg: string
  accent: string
  border: string
}

const store = useWorkspaceStore()

const BOOK_PALETTES: BookColorPalette[] = [
  {
    id: 0,
    bookBg: '#ffe4e6', // Soft pink / rose
    bookText: '#4c0519',
    headerBg: '#fecdd3',
    subHeaderBg: '#ffe4e6',
    accent: '#f43f5e',
    border: '#fda4af'
  },
  {
    id: 1,
    bookBg: '#dcfce7', // Sage / soft green
    bookText: '#064e3b',
    headerBg: '#bbf7d0',
    subHeaderBg: '#dcfce7',
    accent: '#16a34a',
    border: '#86efac'
  },
  {
    id: 2,
    bookBg: '#dbeafe', // Periwinkle / soft blue
    bookText: '#1e3a8a',
    headerBg: '#bfdbfe',
    subHeaderBg: '#dbeafe',
    accent: '#2563eb',
    border: '#93c5fd'
  },
  {
    id: 3,
    bookBg: '#fef3c7', // Peach / warm amber
    bookText: '#78350f',
    headerBg: '#fde68a',
    subHeaderBg: '#fef3c7',
    accent: '#d97706',
    border: '#fcd34d'
  },
  {
    id: 4,
    bookBg: '#f3e8ff', // Lilac / soft purple
    bookText: '#581c87',
    headerBg: '#e9d5ff',
    subHeaderBg: '#f3e8ff',
    accent: '#9333ea',
    border: '#d8b4fe'
  },
  {
    id: 5,
    bookBg: '#ccfbf1', // Aqua / soft teal
    bookText: '#134e4a',
    headerBg: '#99f6e4',
    subHeaderBg: '#ccfbf1',
    accent: '#0d9488',
    border: '#5eead4'
  }
]

const collapsedDocIds = ref<Set<string>>(new Set())
const collapsedHeaderIds = ref<Set<string>>(new Set())
const scrollPercentage = ref(0)
const activeHeaderId = ref<string | null>(null)

function getPaletteForIndex(index: number): BookColorPalette {
  return BOOK_PALETTES[index % BOOK_PALETTES.length]
}

function buildHeaderHierarchy(nodes: NodeItem[]): HeaderItem[] {
  const headerNodes = nodes.filter((n) => n.node_type === 'header')
  const headerMap = new Map<string, HeaderItem>()
  const rootHeaders: HeaderItem[] = []

  for (const hn of headerNodes) {
    headerMap.set(hn.id, {
      node: hn,
      level: 1,
      children: []
    })
  }

  for (const hn of headerNodes) {
    const item = headerMap.get(hn.id)!
    if (hn.parent_id && headerMap.has(hn.parent_id)) {
      const parentItem = headerMap.get(hn.parent_id)!
      item.level = parentItem.level + 1
      parentItem.children.push(item)
    } else {
      rootHeaders.push(item)
    }
  }

  return rootHeaders
}

const documentGroups = computed<DocumentGroup[]>(() => {
  if (!store.documents || store.documents.length === 0) {
    const docIds = Array.from(new Set(store.nodes.map((n) => n.document_id).filter(Boolean)))
    return docIds.map((docId, index) => {
      const docNodes = store.nodes.filter((n) => n.document_id === docId)
      const virtualDoc: DocumentSummary = {
        id: docId,
        project_id: store.currentProject?.id || '',
        filename: `document ${index + 1}`,
        file_type: 'txt',
        order_index: index,
        total_nodes: docNodes.length,
        current_embeddings: 0,
        stale_embeddings: 0,
        missing_embeddings: 0
      }
      return {
        document: virtualDoc,
        colorPalette: getPaletteForIndex(index),
        isExpanded: !collapsedDocIds.value.has(docId),
        headers: buildHeaderHierarchy(docNodes)
      }
    })
  }

  return store.documents.map((doc, index) => {
    const docNodes = store.nodes.filter((n) => n.document_id === doc.id)
    return {
      document: doc,
      colorPalette: getPaletteForIndex(index),
      isExpanded: !collapsedDocIds.value.has(doc.id),
      headers: buildHeaderHierarchy(docNodes)
    }
  })
})

function toggleDocument(docId: string, event?: Event) {
  if (event) event.stopPropagation()
  if (collapsedDocIds.value.has(docId)) {
    collapsedDocIds.value.delete(docId)
  } else {
    collapsedDocIds.value.add(docId)
  }
}

function toggleHeader(headerId: string, event?: Event) {
  if (event) event.stopPropagation()
  if (collapsedHeaderIds.value.has(headerId)) {
    collapsedHeaderIds.value.delete(headerId)
  } else {
    collapsedHeaderIds.value.add(headerId)
  }
}

function fastForwardToDocument(docId: string) {
  const firstNode = store.nodes.find((n) => n.document_id === docId)
  if (firstNode) {
    fastForwardToNode(firstNode.id)
  }
}

function fastForwardToNode(nodeId: string) {
  activeHeaderId.value = nodeId
  store.scrollToNode(nodeId)
}

function handleRailClick(event: MouseEvent) {
  const rail = event.currentTarget as HTMLElement
  const rect = rail.getBoundingClientRect()
  const clickY = event.clientY - rect.top
  const ratio = Math.max(0, Math.min(1, clickY / rect.height))
  const scrollContainer = document.querySelector('.canvas-scroll-container') || window
  if (scrollContainer === window) {
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight
    window.scrollTo({ top: maxScroll * ratio, behavior: 'smooth' })
  } else {
    const el = scrollContainer as HTMLElement
    const maxScroll = el.scrollHeight - el.clientHeight
    el.scrollTo({ top: maxScroll * ratio, behavior: 'smooth' })
  }
}

function updateScrollProgress() {
  const scrollContainer = document.querySelector('.canvas-scroll-container')
  if (scrollContainer) {
    const el = scrollContainer as HTMLElement
    const max = el.scrollHeight - el.clientHeight
    scrollPercentage.value = max > 0 ? (el.scrollTop / max) * 100 : 0
  } else {
    const max = document.documentElement.scrollHeight - window.innerHeight
    scrollPercentage.value = max > 0 ? (window.scrollY / max) * 100 : 0
  }
}

onMounted(() => {
  window.addEventListener('scroll', updateScrollProgress, { passive: true })
  const container = document.querySelector('.canvas-scroll-container')
  if (container) {
    container.addEventListener('scroll', updateScrollProgress, { passive: true })
  }
  updateScrollProgress()
})

onUnmounted(() => {
  window.removeEventListener('scroll', updateScrollProgress)
  const container = document.querySelector('.canvas-scroll-container')
  if (container) {
    container.removeEventListener('scroll', updateScrollProgress)
  }
})
</script>

<template>
  <aside class="header-outline-legend">
    <div class="legend-rail-container" @click="handleRailClick" title="Scroll track">
      <div class="rail-cap rail-cap-top"></div>
      <div class="rail-line">
        <div
          class="rail-indicator"
          :style="{ height: `${Math.max(8, scrollPercentage)}%` }"
        ></div>
      </div>
      <div class="rail-cap rail-cap-bottom"></div>
    </div>

    <div class="legend-tree-container">
      <div v-if="documentGroups.length === 0" class="legend-empty">
        <span>No documents loaded</span>
      </div>

      <div
        v-for="group in documentGroups"
        :key="group.document.id"
        class="legend-doc-group"
        :style="{
          '--doc-bg': group.colorPalette.bookBg,
          '--doc-text': group.colorPalette.bookText,
          '--header-bg': group.colorPalette.headerBg,
          '--subheader-bg': group.colorPalette.subHeaderBg,
          '--doc-accent': group.colorPalette.accent,
          '--doc-border': group.colorPalette.border
        }"
      >
        <div
          class="legend-item legend-doc-item"
          :class="{ active: group.document.id === activeHeaderId }"
          @click="fastForwardToDocument(group.document.id)"
          :title="`Jump to ${group.document.filename}`"
        >
          <button
            class="chevron-btn"
            @click="toggleDocument(group.document.id, $event)"
            :title="group.isExpanded ? 'Collapse document' : 'Expand document'"
          >
            {{ group.isExpanded ? '⌃' : '⌄' }}
          </button>
          <span class="item-title">{{ group.document.filename }}</span>
        </div>

        <div v-if="group.isExpanded" class="legend-headers-list">
          <template v-for="h1 in group.headers" :key="h1.node.id">
            <div
              class="legend-item legend-h1-item"
              :class="{ active: h1.node.id === activeHeaderId }"
              @click="fastForwardToNode(h1.node.id)"
              :title="`Jump to ${h1.node.text_content}`"
            >
              <button
                v-if="h1.children.length > 0"
                class="chevron-btn"
                @click="toggleHeader(h1.node.id, $event)"
                :title="collapsedHeaderIds.has(h1.node.id) ? 'Expand subheaders' : 'Collapse subheaders'"
              >
                {{ collapsedHeaderIds.has(h1.node.id) ? '⌄' : '⌃' }}
              </button>
              <span v-else class="chevron-spacer"></span>
              <span class="item-title">{{ h1.node.text_content || 'Untitled Header' }}</span>
            </div>

            <div
              v-if="!collapsedHeaderIds.has(h1.node.id)"
              class="legend-subheaders-list"
            >
              <div
                v-for="sub in h1.children"
                :key="sub.node.id"
                class="legend-item legend-sub-item"
                :class="{ active: sub.node.id === activeHeaderId }"
                @click="fastForwardToNode(sub.node.id)"
                :title="`Jump to ${sub.node.text_content}`"
              >
                <span class="item-title">{{ sub.node.text_content || 'Untitled Sub-header' }}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped lang="scss">
.header-outline-legend {
 
  display: flex;
  align-items: flex-start;
  width: 220px;
  min-width: 180px;
  max-width: 260px;
  height: 100%;
  padding: 16px 8px 16px 12px;
  user-select: none;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

.legend-rail-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 12px;
  height: calc(100vh - 120px);
  position: sticky;
  top: 16px;
  cursor: pointer;
}

.rail-cap {
  width: 10px;
  height: 2px;
  background-color: #94a3b8;
}

.rail-line {
  flex: 1;
  width: 2px;
  background-color: #cbd5e1;
  position: relative;
}

.rail-indicator {
  position: absolute;
  top: 0;
  left: -1px;
  width: 4px;
  background-color: #2563eb;
  transition: height 0.1s ease-out;
}

.legend-tree-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  max-height: calc(100vh - 120px);
  padding-right: 4px;
}

.legend-empty {
  font-size: 11px;
  color: #94a3b8;
  padding: 12px 6px;
  font-style: italic;
}

.legend-doc-group {
  display: flex;
  flex-direction: column;
}

.legend-item {
  display: flex;
  align-items: center;
  cursor: pointer;
  transition: filter 0.15s ease, transform 0.1s ease;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;

  &:hover {
    filter: brightness(0.95);
  }

  &.active {
    filter: brightness(0.92);
  }
}

.legend-doc-item {
  background-color: var(--doc-bg);
  color: var(--doc-text);
  border-bottom: 1px solid var(--doc-border);
  padding: 4px 8px 4px 6px;
  font-size: 12px;
  font-weight: 600;
  width: 100%;
}

.legend-headers-list {
  display: flex;
  flex-direction: column;
}

.legend-h1-item {
  background-color: var(--header-bg);
  color: var(--doc-text);
  border-bottom: 1px solid var(--doc-border);
  width: calc(100% - 18px);
  padding: 3px 6px 3px 4px;
  font-size: 11.5px;
  font-weight: 500;
}

.legend-subheaders-list {
  display: flex;
  flex-direction: column;
}

.legend-sub-item {
  background-color: var(--subheader-bg);
  color: var(--doc-text);
  border-bottom: 1px solid var(--doc-border);
  width: calc(100% - 32px);
  padding: 3px 6px;
  font-size: 11px;
  font-weight: 400;
}

.item-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chevron-btn {
  background: transparent;
  border: none;
  color: var(--doc-text);
  font-size: 11px;
  line-height: 1;
  padding: 0 2px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  &:hover {
    color: var(--doc-accent);
  }
}

.chevron-spacer {
  width: 10px;
  display: inline-block;
}
</style>