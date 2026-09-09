<script setup lang="ts">
import { computed } from 'vue'
import { useWorkspaceStore, type WorkspaceStep } from '../stores/workspace'

const store = useWorkspaceStore()

const emit = defineEmits<{
  (e: 'open-settings'): void
  (e: 'back-to-hub'): void
}>()

const steps: { id: WorkspaceStep; label: string; number: number }[] = [
  { id: 'ingestion', label: 'Ingestion', number: 1 },
  { id: 'chunks', label: 'Chunk Canvas', number: 2 },
  { id: 'schema', label: 'Schema Designer', number: 3 },
  { id: 'metadata', label: 'Metadata', number: 4 },
  { id: 'embeddings', label: 'Embeddings', number: 5 },
  { id: 'export', label: 'Export', number: 6 }
]

const counts = computed(() => store.currentEmbeddingCounts)
</script>

<template>
  <header class="step-navigator">
    <div class="nav-left">
      <button class="btn-hub" @click="emit('back-to-hub')" title="Return to Project Hub">
        📦 <span class="project-name">{{ store.currentProject?.name || 'Custodex' }}</span>
      </button>
    </div>

    <nav class="steps-list">
      <button
        v-for="step in steps"
        :key="step.id"
        class="step-item"
        :class="{ active: store.currentStep === step.id }"
        @click="store.setStep(step.id)"
      >
        <span class="step-num">{{ step.number }}</span>
        <span class="step-label">{{ step.label }}</span>
        <span
          v-if="step.id === 'embeddings' && (counts.stale > 0 || counts.missing > 0)"
          class="badge-pill"
          :class="counts.missing > 0 ? 'badge-missing' : 'badge-stale'"
          title="Stale or uncalculated vectors require refresh"
        >
          {{ counts.missing + counts.stale }}
        </span>
      </button>
    </nav>

    <div class="nav-right">
      <button class="settings-btn" @click="emit('open-settings')" title="Global Settings">
        ⚙️ Settings
      </button>
    </div>
  </header>
</template>

<style scoped lang="scss">
@use '../styles/variables' as *;

.step-navigator {
  height: $header-height;
  background-color: $color-surface;
  border-bottom: 1px solid $color-border;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  user-select: none;
}

.nav-left {
  display: flex;
  align-items: center;
}

.btn-hub {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: $color-text-primary;
  padding: 6px 10px;
  border-radius: $radius-md;
  background-color: transparent;
  transition: background-color 0.15s ease;

  &:hover {
    background-color: $color-surface-hover;
  }

  .project-name {
    max-width: 180px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.steps-list {
  display: flex;
  align-items: center;
  gap: 4px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: $radius-md;
  color: $color-text-secondary;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s ease;

  .step-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background-color: rgba(255, 255, 255, 0.08);
    font-size: 11px;
    font-weight: 700;
  }

  &:hover {
    color: $color-text-primary;
    background-color: rgba(255, 255, 255, 0.04);
  }

  &.active {
    color: $color-primary;
    background-color: rgba(56, 189, 248, 0.1);

    .step-num {
      background-color: $color-primary;
      color: #000;
    }
  }
}

.badge-pill {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 999px;

  &.badge-stale {
    background-color: $color-status-stale-bg;
    color: $color-status-stale;
  }

  &.badge-missing {
    background-color: $color-status-missing-bg;
    color: $color-status-missing;
  }
}

.nav-right {
  display: flex;
  align-items: center;
}

.settings-btn {
  font-size: 13px;
  color: $color-text-secondary;
  padding: 6px 10px;
  border-radius: $radius-md;
  &:hover {
    color: $color-text-primary;
    background-color: $color-surface-hover;
  }
}
</style>