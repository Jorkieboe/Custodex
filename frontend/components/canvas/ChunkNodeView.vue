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

function handleContainerClick() {
  store.selectNode(props.node.id)
}

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
      action: () => store.refreshEmbeddingsStream(),
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
    :id="`node-${node.id}`"
    :data-node-id="node.id"
    ref="chunkRef"
    class="chunk-row-wrapper"
    @contextmenu="handleContextMenu"
  >
    <!-- Selection checkbox placed outside the chunk container -->
    <div class="chunk-outside-selection">
      <input
        type="checkbox"
        class="chunk-outside-checkbox"
        :checked="isSelected"
        @change="store.toggleNodeSelection(node.id)"
      />
    </div>

    <div
      class="chunk-node-container"
      :class="{
        selected: isSelected,
        active: store.activeNodeId === node.id,
        [`status-${node.embedding_status}`]: showEmbeddingStatus
      }"
      @click="handleContainerClick"
    >
      <!-- Absolute action buttons toolbar on the node -->
      <!-- Embedding status pill if in embeddings view -->
      <!-- <span

        class="status-pill status-pill-absolute"

      >
        <span class="status-dot"></span>
        {{ node.embedding_status.toUpperCase() }}
      </span> -->
      <div class="chunk-actions-absolute" v-if="store.currentStep === 'chunks'">
        <button
          class="btn-action-pill"
          @click="emit('promote', node.id)"
          title="Promote paragraph to structural header"
        >
          Promote to Header ↥
        </button>
        <button
          v-if="canMerge"
          class="btn-action-pill"
          @click="emit('merge', node.id)"
          title="Merge with succeeding chunk"
        >
          Merge Down ⤓
        </button>
        <button
          class="btn-action-pill btn-autosplit-pill"
          :disabled="isAnalyzing"
          @click="handleTriggerAutoSplit"
          title="Analyze chunk for semantic shifts and suggest split points"
        >
          {{ isAnalyzing ? 'Analyzing...' : '⚡ Auto-Split' }}
        </button>
      </div>
      <div class="chunk-actions-absolute" v-else-if="store.currentStep === 'metadata'">
        <button
          class="btn-action-pill btn-meta-generate"
          :disabled="store.isGeneratingSingle === node.id"
          @click.stop="store.generateMetadataForNode(node.id)"
          :title="store.nodesWithMetadata.has(node.id) ? 'Regenerate metadata for this chunk' : 'Generate metadata for this chunk'"
        >
          {{ store.isGeneratingSingle === node.id ? 'Generating...' : (store.nodesWithMetadata.has(node.id) ? 'Regenerate ↻' : 'Generate ✨') }}
        </button>
      </div>

      <!-- Token count visible only on hover -->
      <div class="chunk-hover-token-badge">
        {{ estimatedTokens }} tokens
      </div>

      <!-- Metadata extraction status badge if in metadata view -->
      <div
        v-if="store.currentStep === 'metadata' && store.nodesWithMetadata.has(node.id)"
        class="chunk-metadata-extracted-badge"
      >
        ✓ Extracted
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
            <button class="split-pill-btn" type="button">split</button>
          </div>
        </div>
      </template>

      </div>
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

.chunk-row-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 16px;
  position: relative;
}

.chunk-outside-selection {
  display: flex;
  flex-direction: column;
  height: 100%;
  align-self: center;

  width: fit-content;

  // input{
  //   justify-content: center;
  //   align-items: center;
  // }

}

.chunk-outside-checkbox {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #E8A643;
  border: 1px solid #94a3b8;
}

.chunk-node-container {
  flex: 1;
  background: rgba(67, 75, 232, 0.2);
  position: relative;
  transition: all 10.15s ease;
  border: 1px solid transparent;

    &.status-current{
      background: linear-gradient(
      to right,
      $color-status-current,
      $color-status-current 5px,
      rgba(67, 75, 232, 0.2) 5px,
        rgba(67, 75, 232, 0.2) 100%,

    );
    }

    &.status-stale{
      background: linear-gradient(
      to right,
      $color-status-stale,
      $color-status-stale 5px,
      rgba(67, 75, 232, 0.2) 5px,
        rgba(67, 75, 232, 0.2) 100%,

    );
    }

    &.status-missing{
      background: linear-gradient(
      to right,
      $color-status-missing,
      $color-status-missing 5px,
      rgba(67, 75, 232, 0.2) 5px,
        rgba(67, 75, 232, 0.2) 100%,

    );
  }

  &:hover {
    border-color: rgba(67, 75, 232, 0.4);

    .chunk-hover-token-badge {
      opacity: 1;
      transform: translateY(0);
      pointer-events: auto;
    }

    .chunk-actions-absolute {
      opacity: 1;
      transform: translate(-50%, 0);
      pointer-events: auto;
    }
  }

  &.selected {
    border-color: #434BE8;
    box-shadow: 0 0 0 2px rgba(67, 75, 232, 0.3);
  }

  &.active {
    border-color: #E8A643;
    box-shadow: 0 0 0 2px rgba(232, 166, 67, 0.35);
  }

  &.selected.active {
    border-color: #E8A643;
    box-shadow: 0 0 0 2px rgba(232, 166, 67, 0.5);
  }
}

.chunk-metadata-extracted-badge {
  position: absolute;
  top: 5px;
  right: 12px;
  font-size: 10px;
  font-weight: 700;
  color: #065f46;
  background-color: #a7f3d0;
  border: 1px solid #6ee7b7;
  padding: 1px 6px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  z-index: 10;
}

.chunk-actions-absolute {
  position: absolute;
  top: -14px;
  left: 50%;
  transform: translate(-50%, 6px);
  display: flex;
  gap: 4px;
  z-index: 20;
  opacity: 0;
  pointer-events: none;
  transition: opacity 1.0s cubic-bezier(0.16, 1, 0.3, 1), transform 1.0s cubic-bezier(0.16, 1, 0.3, 1);
}

.btn-action-pill {
  background-color: #E8A643;
  color: #ffffff;
  border: 1px solid #d6932f;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.25s ease;

  &:hover {
    background-color: #d6932f;
    color: #ffffff;
  }

  &.btn-autosplit-pill {
    background-color: #E8A643;
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
}

.chunk-hover-token-badge {
  position: absolute;
  top: 5px;
  right: 12px;
  font-family: $font-family-mono;
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  background-color: rgba(255, 255, 255, 0.95);
  border: 1px solid #e2e8f0;
  padding: 1px 6px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  opacity: 0;
  transform: translateY(4px);
  pointer-events: none;
  transition: opacity 1s cubic-bezier(0.16, 1, 0.3, 1), transform 1s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 10;
}

.status-pill-absolute {
  position: absolute;
  top: 8px;
  right: 10px;
  z-index: 15;
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
  cursor: pointer;
}

.btn-proposal-reject {
  background-color: transparent;
  color: $color-text-secondary;
  font-size: 11px;
  padding: 3px 6px;
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
  padding: 20px;
  display: flex;
  flex-direction: column;
}

.chunk-editable-content {
  font-size: 14px;
  line-height: 1.6;
  color: #1e293b;
  white-space: pre-wrap;
  outline: none;
  min-height: 24px;
  cursor: text;
  word-break: break-word;
  padding: 4px 6px;
  transition: background-color 0.15s ease;

  &:focus {
    background-color: rgba(255, 255, 255, 0.4);
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
    background: repeating-linear-gradient(
      to right,
      black 0,
      black 4px,
      transparent 4px,
      transparent 10px
    );
  }

  .split-pill-btn {
    background-color: #E8A643;
    border: 1px solid #d6932f;
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 14px;
    border-radius: 999px;
    opacity: 0.9;
    transition: all 0.15s ease;
    cursor: pointer;
    margin-right: 1rem;

    &:hover {
      opacity: 1;
      transform: scale(1.05);
      background-color: #d6932f;
      color: #ffffff;
    }

    &:has(.split-pill-btn:hover) {
      .divider-line {
        border-top-color: #E8A643;
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