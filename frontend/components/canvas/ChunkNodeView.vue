<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { type NodeItem } from '../../services/api'
import { useWorkspaceStore } from '../../stores/workspace'

const props = defineProps<{
  node: NodeItem
  canMerge: boolean
}>()

const emit = defineEmits<{
  (e: 'split', nodeId: string, topText: string, bottomText: string): void
  (e: 'merge', nodeId: string): void
  (e: 'promote', nodeId: string): void
  (e: 'selection-change', nodeId: string, text: string, start: number, end: number): void
}>()

const store = useWorkspaceStore()
const chunkRef = ref<HTMLDivElement | null>(null)
const segmentRefs = ref<HTMLDivElement[]>([])
const segments = ref<string[]>([])
const contextMenuVisible = ref(false)
const contextMenuPosition = ref({ x: 0, y: 0 })
const contextSegmentIndex = ref<number | null>(null)
const contextCaretOffset = ref<number | null>(null)
let saveTimeout: ReturnType<typeof setTimeout> | null = null

const showEmbeddingStatus = computed(() => store.currentStep === 'embeddings')
const isSelected = computed(() => store.selectedNodeIds.has(props.node.id))
const activeProposal = computed(() => store.semanticSplitProposals.get(props.node.id))
const isAnalyzing = ref(false)
const noSplitsNotice = ref(false)

const estimatedTokens = computed(() => {
  const text = props.node.text_content || ''
  if (!text.trim()) return 0
  const count = text.trim().split(/\s+/).length
  return Math.max(1, Math.round(count * 1.25))
})

async function handleTriggerAutoSplit() {
  isAnalyzing.value = true
  noSplitsNotice.value = false
  try {
    const previews = await store.requestSemanticSplitPreview([props.node.id])
    if (!previews || previews.length === 0 || previews[0].proposed_splits.length === 0) {
      noSplitsNotice.value = true
      setTimeout(() => {
        noSplitsNotice.value = false
      }, 3500)
    }
  } finally {
    isAnalyzing.value = false
  }
}

function handleAcceptInlineSplit(splitIndex: number) {
  store.acceptProposedSplit(props.node.id, [splitIndex])
}

function parseSegmentsFromText(rawText: string): string[] {
  const parts = rawText.split(/\n\s*\n/)
  return parts.length > 0 ? parts : ['']
}

function initSegments(text: string) {
  segments.value = parseSegmentsFromText(text)
  nextTick(() => {
    segmentRefs.value.forEach((el, idx) => {
      if (el && segments.value[idx] !== undefined) {
        el.innerText = segments.value[idx]
      }
    })
  })
}

onMounted(() => {
  initSegments(props.node.text_content)
})

watch(
  () => props.node.text_content,
  (newVal) => {
    const isEditing = segmentRefs.value.some((el) => el === document.activeElement)
    if (!isEditing) {
      initSegments(newVal)
    }
  }
)

const contextMenuItems = computed(() => {
  const items = []

  if (store.currentStep === 'chunks') {
    items.push(
      {
        label: '✂️ Split Chunk Here',
        action: handleContextSplit,
      },
      {
        label: '⚡ Semantic Auto-Split',
        action: handleTriggerAutoSplit,
      },
      {
        label: '↥ Promote to Header',
        action: () => emit('promote', props.node.id),
      },
    )

    if (props.canMerge) {
      items.push({
        label: '⤓ Merge with Below',
        action: () => emit('merge', props.node.id),
      })
    }
  }

  if (store.currentStep === 'embeddings') {
    items.push({
      label: 'Generate Embeddings',
      action: () => {},
    })
  }

  return items
})

function setSegmentRef(el: any, idx: number) {
  if (el) {
    segmentRefs.value[idx] = el as HTMLDivElement
  }
}

function handleSegmentInput(idx: number, event: Event) {
  const el = event.target as HTMLDivElement
  const currentVal = el.innerText

  if (currentVal.includes('\n\n')) {
    const innerParts = currentVal.split(/\n\s*\n/)
    segments.value.splice(idx, 1, ...innerParts)
    persistFullText()

    nextTick(() => {
      segmentRefs.value.forEach((targetEl, i) => {
        if (targetEl && segments.value[i] !== undefined) {
          targetEl.innerText = segments.value[i]
        }
      })
      const nextEl = segmentRefs.value[idx + 1]
      if (nextEl) {
        nextEl.focus()
      }
    })
    return
  }

  segments.value[idx] = currentVal
  persistFullText()
}

function handleSegmentKeyDown(idx: number, event: KeyboardEvent) {
  const el = segmentRefs.value[idx]
  if (!el) return

  if (event.key === 'Enter' && !event.shiftKey) {
    const selection = window.getSelection()
    if (selection && selection.rangeCount > 0) {
      const range = selection.getRangeAt(0)
      const preRange = range.cloneRange()
      preRange.selectNodeContents(el)
      preRange.setEnd(range.endContainer, range.endOffset)
      const textBefore = preRange.toString()

      if (textBefore.endsWith('\n')) {
        event.preventDefault()
        const topText = textBefore.replace(/\n$/, '').trim()
        const full = el.innerText
        const bottomText = full.slice(textBefore.length).trim()

        segments.value[idx] = topText
        segments.value.splice(idx + 1, 0, bottomText)
        persistFullText()

        nextTick(() => {
          segmentRefs.value.forEach((targetEl, i) => {
            if (targetEl && segments.value[i] !== undefined) {
              targetEl.innerText = segments.value[i]
            }
          })
          const nextEl = segmentRefs.value[idx + 1]
          if (nextEl) {
            nextEl.focus()
          }
        })
        return
      }
    }
  }

  if (event.key === 'Backspace' && idx > 0) {
    const selection = window.getSelection()
    if (selection && selection.rangeCount > 0 && selection.isCollapsed) {
      const range = selection.getRangeAt(0)
      const preRange = range.cloneRange()
      preRange.selectNodeContents(el)
      preRange.setEnd(range.endContainer, range.endOffset)
      if (preRange.toString().length === 0) {
        event.preventDefault()
        const prevText = segments.value[idx - 1]
        const currText = segments.value[idx]
        const mergedText = prevText + (currText ? '\n' + currText : '')

        segments.value[idx - 1] = mergedText
        segments.value.splice(idx, 1)
        segmentRefs.value.splice(idx, 1)
        persistFullText()

        nextTick(() => {
          segmentRefs.value.forEach((targetEl, i) => {
            if (targetEl && segments.value[i] !== undefined) {
              targetEl.innerText = segments.value[i]
            }
          })
          const prevEl = segmentRefs.value[idx - 1]
          if (prevEl) {
            prevEl.focus()
          }
        })
      }
    }
  }
}

function persistFullText() {
  const full = segments.value.join('\n\n')
  if (saveTimeout) clearTimeout(saveTimeout)
  saveTimeout = setTimeout(() => {
    store.updateNode(props.node.id, full)
  }, 400)
}

function handleSegmentBlur() {
  if (saveTimeout) clearTimeout(saveTimeout)
  const full = segments.value.join('\n\n')
  if (full !== props.node.text_content) {
    store.updateNode(props.node.id, full)
  }
}

function handleSplitBetween(dividerIndex: number) {
  const topText = segments.value.slice(0, dividerIndex + 1).join('\n\n').trim()
  const bottomText = segments.value.slice(dividerIndex + 1).join('\n\n').trim()
  if (topText && bottomText) {
    emit('split', props.node.id, topText, bottomText)
  }
}

function handleContextMenu(event: MouseEvent) {
  event.preventDefault()
  contextMenuPosition.value = { x: event.clientX, y: event.clientY }
  contextMenuVisible.value = true

  const selection = window.getSelection()
  contextSegmentIndex.value = null
  contextCaretOffset.value = null

  if (selection && selection.focusNode) {
    const foundIdx = segmentRefs.value.findIndex((el) => el && el.contains(selection.focusNode))
    if (foundIdx !== -1) {
      contextSegmentIndex.value = foundIdx
      const range = selection.getRangeAt(0)
      const preRange = range.cloneRange()
      preRange.selectNodeContents(segmentRefs.value[foundIdx])
      preRange.setEnd(range.endContainer, range.endOffset)
      contextCaretOffset.value = preRange.toString().length
    }
  }
}

function closeContextMenu() {
  contextMenuVisible.value = false
}

function handleContextSplit() {
  if (contextSegmentIndex.value !== null && contextCaretOffset.value !== null) {
    const idx = contextSegmentIndex.value
    const offset = contextCaretOffset.value
    const segText = segments.value[idx] || ''

    const segTop = segText.slice(0, offset).trim()
    const segBottom = segText.slice(offset).trim()

    const topParts = [...segments.value.slice(0, idx), segTop].filter(Boolean)
    const bottomParts = [segBottom, ...segments.value.slice(idx + 1)].filter(Boolean)

    const top = topParts.join('\n\n').trim()
    const bottom = bottomParts.join('\n\n').trim()

    if (top && bottom) {
      emit('split', props.node.id, top, bottom)
    }
  } else if (segments.value.length > 1) {
    handleSplitBetween(0)
  }
  closeContextMenu()
}

function handleSegmentMouseUp(idx: number) {
  const selection = window.getSelection()
  if (!selection || selection.isCollapsed) return
  const text = selection.toString().trim()
  const el = segmentRefs.value[idx]
  if (text.length > 0 && el && el.contains(selection.anchorNode)) {
    let precedingCharCount = 0
    for (let i = 0; i < idx; i++) {
      precedingCharCount += segments.value[i].length + 2
    }
    const range = selection.getRangeAt(0)
    const preRange = range.cloneRange()
    preRange.selectNodeContents(el)
    preRange.setEnd(range.startContainer, range.startOffset)
    const startInSeg = preRange.toString().length
    const globalStart = precedingCharCount + startInSeg
    emit('selection-change', props.node.id, text, globalStart, globalStart + text.length)
  }
}
</script>

<template>
  <div
    ref="chunkRef"
    class="chunk-node-container"
    :class="{ selected: isSelected }"
    @contextmenu="handleContextMenu"
  >
    <div class="chunk-header">
      <div class="chunk-meta">
        <input
          type="checkbox"
          class="chunk-checkbox"
          :checked="isSelected"
          @change="store.toggleNodeSelection(node.id)"
        />
        <span class="order-badge">#{{ node.order_index }}</span>
        <span class="tokens-badge" title="Estimated token size of this chunk">~{{ estimatedTokens }} tok</span>

        <span
          v-if="showEmbeddingStatus"
          class="status-pill"
          :class="`status-${node.embedding_status}`"
        >
          <span class="status-dot"></span>
          {{ node.embedding_status.toUpperCase() }}
        </span>
      </div>

      <div class="chunk-tools" v-if="store.currentStep == 'chunks'">
        <button
          class="btn-tool btn-autosplit"
          :disabled="isAnalyzing"
          @click="handleTriggerAutoSplit"
          title="Analyze chunk for semantic shifts and suggest split points"
        >
          {{ isAnalyzing ? 'Analyzing...' : '⚡ Auto-Split' }}
        </button>
        <button
          v-if="canMerge"
          class="btn-tool"
          @click="emit('merge', node.id)"
          title="Merge with succeeding chunk"
        >
          Merge Down ⤓
        </button>
        <button
          class="btn-tool"
          @click="emit('promote', node.id)"
          title="Promote paragraph to structural header"
        >
          Promote to Header ↥
        </button>
      </div>
    </div>

    <!-- Feedback banner when no splits found -->
    <div v-if="noSplitsNotice" class="no-splits-banner">
      <span>ℹ️ No semantic breaks detected (chunk is already compact or uniform in topic).</span>
    </div>

    <!-- Active Proposal Review Banner -->
    <div v-if="activeProposal" class="semantic-split-proposal-banner">
      <div class="proposal-info">
        <span class="proposal-badge">⚡ {{ activeProposal.proposed_splits.length }} Proposed Split(s)</span>
        <span class="proposal-tutorial">Suggested split — double Enter splits chunks like this</span>
      </div>
      <div class="proposal-banner-actions">
        <button class="btn-proposal-accept" @click="store.acceptProposedSplit(node.id)">
          ✓ Accept All
        </button>
        <button class="btn-proposal-reject" @click="store.rejectProposedSplit(node.id)">
          ✕ Reject
        </button>
      </div>
    </div>

    <div class="chunk-body">
   

      <template v-if="activeProposal && activeProposal.proposed_splits.length > 0">
        <div class="proposed-review-container">
          <template v-for="(sliceItem, sIdx) in activeProposal.proposed_slices" :key="sIdx">
            <div class="candidate-slice-card">
              <div class="slice-card-top">
                <span class="slice-index-tag">Slice {{ sIdx + 1 }}</span>
                <span class="slice-token-badge">~{{ typeof sliceItem === 'object' ? sliceItem.token_count : Math.round(sliceItem.length / 4) }} tok</span>
              </div>
              <p class="candidate-slice-text">{{ typeof sliceItem === 'object' ? sliceItem.text : sliceItem }}</p>
            </div>

            <div
              v-if="sIdx < activeProposal.proposed_splits.length"
              class="hover-split-divider"
            >
              <div class="divider-line"></div>
              <div class="split-button-wrapper">
                <button
                  type="button"
                  class="split-pill-btn"
                  @click="handleAcceptInlineSplit(activeProposal.proposed_splits[sIdx].split_index)"
                >
                  ✓ Accept This Split
                </button>
                <button
                  type="button"
                  class="split-pill-btn"
                  @click="store.rejectProposedSplit(node.id)"
                >
                  ✕ Reject
                </button>
              </div>
            </div>
          </template>
        </div>
      </template>

      <template template v-if="!activeProposal || activeProposal.proposed_splits.length == 0" v-for="(_, idx) in segments" :key="idx">
        <div
          :ref="el => setSegmentRef(el, idx)"
          class="chunk-editable-content"
          :contenteditable="store.currentStep == 'chunks'"
          spellcheck="false"
          @input="e => handleSegmentInput(idx, e)"
          @keydown="e => handleSegmentKeyDown(idx, e)"
          @blur="handleSegmentBlur"
          @mouseup="() => handleSegmentMouseUp(idx)"
        ></div>

        <div
          v-if="idx < segments.length - 1 && store.currentStep == 'chunks'"
          class="hover-split-divider"
          @click="handleSplitBetween(idx)"
          title="Click to split chunk here (or double Enter)"
        >
          <div class="divider-line"></div>
          <div class="split-button-wrapper">
            <button class="split-pill-btn" type="button">✂ Split Chunk Here</button>
          </div>
        </div>
      </template>

    </div>

    <div
      v-if="contextMenuVisible && contextMenuItems.length > 0"
      class="context-menu-backdrop"
      @click="closeContextMenu"
    >
      <div
        class="context-menu"
        :style="{ top: `${contextMenuPosition.y}px`, left: `${contextMenuPosition.x}px` }"
        @click.stop
      >
        <button
          v-for="item in contextMenuItems"
          :key="item.label"
          class="context-item"
          @click="item.action"
        >
          {{ item.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as *;

.chunk-node-container {
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-md;
  margin-bottom: 12px;
  position: relative;
  transition: all 0.15s ease;

  &:hover {
    border-color: rgba(56, 189, 248, 0.4);
  }

  &.selected {
    border-color: $color-primary;
    background-color: rgba(56, 189, 248, 0.03);
  }
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  user-select: none;
}

.chunk-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chunk-checkbox {
  cursor: pointer;
  accent-color: $color-primary;
}

.order-badge {
  font-family: $font-family-mono;
  font-size: 11px;
  color: $color-text-muted;
  background-color: rgba(0, 0, 0, 0.25);
  padding: 1px 6px;
  border-radius: $radius-sm;
}

.tokens-badge {
  font-family: $font-family-mono;
  font-size: 10px;
  font-weight: 600;
  color: $color-primary;
  background-color: rgba(56, 189, 248, 0.1);
  padding: 1px 5px;
  border-radius: $radius-sm;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  &.status-current {
    background-color: $color-status-current-bg;
    color: $color-status-current;
    .status-dot { background-color: $color-status-current; }
  }

  &.status-stale {
    background-color: $color-status-stale-bg;
    color: $color-status-stale;
    .status-dot { background-color: $color-status-stale; }
  }

  &.status-missing {
    background-color: $color-status-missing-bg;
    color: $color-status-missing;
    .status-dot { background-color: $color-status-missing; }
  }
}

.chunk-tools {
  display: flex;
  gap: 6px;
}

.btn-tool {
  font-size: 11px;
  color: $color-text-secondary;
  background-color: transparent;
  padding: 2px 6px;
  border-radius: $radius-sm;

  &:hover {
    color: $color-text-primary;
    background-color: $color-surface-hover;
  }

  &.btn-autosplit {
    color: $color-primary;
    background-color: rgba(56, 189, 248, 0.1);
    font-weight: 600;

    &:hover:not(:disabled) {
      background-color: $color-primary;
      color: #000;
    }

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
}

.no-splits-banner {
  background-color: rgba(234, 179, 8, 0.1);
  border-bottom: 1px solid rgba(234, 179, 8, 0.25);
  color: #eab308;
  font-size: 11px;
  padding: 6px 14px;
}

.semantic-split-proposal-banner {
  background-color: rgba(56, 189, 248, 0.12);
  border-bottom: 1px solid rgba(56, 189, 248, 0.3);
  padding: 8px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.proposal-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.proposal-badge {
  font-size: 10px;
  font-weight: 700;
  background-color: $color-primary;
  color: #000;
  padding: 2px 6px;
  border-radius: $radius-sm;
}

.proposal-tutorial {
  font-size: 11px;
  color: $color-text-secondary;
}

.proposal-banner-actions {
  display: flex;
  gap: 6px;
}

.btn-proposal-accept {
  background-color: #22c55e;
  color: #000;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: $radius-sm;
  cursor: pointer;
}

.btn-proposal-reject {
  background-color: transparent;
  color: $color-text-secondary;
  font-size: 11px;
  padding: 3px 6px;
  border-radius: $radius-sm;
  cursor: pointer;

  &:hover {
    color: $color-text-primary;
    background-color: rgba(255, 255, 255, 0.1);
  }
}

.proposed-review-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.proposed-review-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: $color-primary;
  letter-spacing: 0.04em;
}

.candidate-slice-card {
  background-color: rgba(0, 0, 0, 0.25);
  border: 1px dashed rgba(56, 189, 248, 0.3);
  border-radius: $radius-sm;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.slice-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.slice-index-tag {
  font-size: 10px;
  font-weight: 700;
  font-family: $font-family-mono;
  color: $color-primary;
}

.slice-token-badge {
  font-size: 10px;
  font-weight: 700;
  font-family: $font-family-mono;
  color: #22c55e;
  background-color: rgba(34, 197, 94, 0.1);
  padding: 1px 5px;
  border-radius: $radius-sm;
}

.candidate-slice-text {
  font-size: 13px;
  line-height: 1.5;
  color: $color-text-primary;
}

.split-button-wrapper{
  position: absolute;
  display: flex;
  width: 100%;
  justify-content: center;
}


.confidence-tag {
  font-size: 10px;
  font-weight: 700;
  font-family: $font-family-mono;
  color: $color-primary;
  padding-right: 4px;
}

.btn-candidate-accept {
  background-color: #22c55e;
  color: #000;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  cursor: pointer;

  &:hover {
    background-color: #16a34a;
  }
}

.btn-candidate-reject {
  background-color: transparent;
  color: $color-text-muted;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 999px;
  cursor: pointer;

  &:hover {
    color: #ef4444;
  }
}

.chunk-body {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
}

.chunk-editable-content {
  font-size: 14px;
  line-height: 1.6;
  color: $color-text-primary;
  white-space: pre-wrap;
  outline: none;
  min-height: 24px;
  cursor: text;
  word-break: break-word;
  padding: 4px 6px;
  border-radius: $radius-sm;
  transition: background-color 0.15s ease;

  &:focus {
    background-color: rgba(255, 255, 255, 0.03);
  }
}

.hover-split-divider {
  position: relative;
  margin: 10px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  height: 24px;
  user-select: none;

  .divider-line {
    width: 100%;
    height: 1px;
    border-top: 1px dashed $color-border;
  }

  .split-pill-btn {
    background-color: $color-surface;
    border: 1px solid rgba(56, 189, 248, 0.4);
    color: $color-primary;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 12px;
    border-radius: 999px;
    opacity: 0.5;
    transition: all 0.15s ease;
    cursor: pointer;
    margin-right: 1rem;

    &:hover{
      opacity: 1;
      transform: scale(1.05);
      background-color: $color-primary;
      color: #000;
      border-color: $color-primary;
    }

    &:has(.split-pill-btn:hover) {
      .divider-line {
        border-top-color: $color-primary;
      }
    }
  }
}

.context-menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2000;
}

.context-menu {
  position: fixed;
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-md;
  box-shadow: $shadow-modal;
  display: flex;
  flex-direction: column;
  padding: 4px;
  min-width: 160px;
  z-index: 2001;
}

.context-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: $color-text-primary;
  border-radius: $radius-sm;
  text-align: left;
  cursor: pointer;

  &:hover {
    background-color: $color-surface-hover;
    color: $color-primary;
  }
}
</style>