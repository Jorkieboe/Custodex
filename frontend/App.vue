<script setup lang="ts">
import { ref } from 'vue'
import { useWorkspaceStore } from './stores/workspace'
import ProjectHub from './components/ProjectHub.vue'
import StepNavigator from './components/StepNavigator.vue'
import IngestionView from './views/01_ImportView.vue'
import ChunkCanvas from './views/02_ChunkCanvas.vue'
import SchemaDesigner from './views/03_schemaDesigner.vue'
import MetadataView from './views/04_MetadataView.vue'
import ExportView from './views/05_ExportView.vue'
import ExportGateModal from './components/export/ExportGateModal.vue'
import SettingsModal from './components/SettingsModal.vue'

const store = useWorkspaceStore()
const activeProjectId = ref<string | null>(null)
const showSettings = ref(false)

async function handleSelectProject(projectId: string) {
  activeProjectId.value = projectId
  await store.loadProject(projectId)
}

function handleBackToHub() {
  activeProjectId.value = null
}
</script>

<template>
  <div class="app-root">
    <!-- Hub View when no active project -->
    <ProjectHub
      v-if="!activeProjectId"
      @select-project="handleSelectProject"
    />

    <!-- Active Project Workspace -->
    <div v-else class="workspace-layout">
      <StepNavigator
        @open-settings="showSettings = true"
        @back-to-hub="handleBackToHub"
      />

      <main class="workspace-main">
        <!-- Step 1: Ingestion -->
        <IngestionView v-if="store.currentStep === 'ingestion'" />

        <!-- Step 2: Chunk Canvas -->
        <ChunkCanvas v-else-if="store.currentStep === 'chunks'" />

        <!-- Step 3: Schema Designer -->
        <SchemaDesigner v-else-if="store.currentStep === 'schema'" />

        <!-- Step 4: Metadata Extraction Workbench -->
        <MetadataView v-else-if="store.currentStep === 'metadata'" />

        <!-- Step 5: Incremental Embedding Refresh -->
        <!-- Note: Embedding status indicators and refresh controls are integrated into ActionBar -->
        <div v-else-if="store.currentStep === 'embeddings'" class="embeddings-step-layout">
          <ChunkCanvas />
        </div>

        <!-- Step 6: Export -->
        <ExportView v-else-if="store.currentStep === 'export'" />
      </main>

      <ExportGateModal />
      <SettingsModal v-if="showSettings" @close="showSettings = false" />
    </div>
  </div>
</template>

<style scoped lang="scss">
@use './styles/variables' as *;

.app-root {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.workspace-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.workspace-main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.step-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.placeholder-card {
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-lg;
  padding: 36px;
  text-align: center;
  max-width: 500px;
  display: flex;
  flex-direction: column;
  gap: 16px;

  h2 {
    font-size: 20px;
    font-weight: 700;
  }

  p {
    font-size: 14px;
    color: $color-text-secondary;
  }
}

.embeddings-step-layout {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: calc(100vh - #{$header-height});
}

.embeddings-banner {
  background-color: $color-surface;
  border-bottom: 1px solid $color-border;
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;

  h3 {
    font-size: 15px;
    font-weight: 600;
  }

  p {
    font-size: 12px;
    color: $color-text-secondary;
    margin-top: 2px;
  }
}

.btn {
  padding: 8px 16px;
  border-radius: $radius-md;
  font-weight: 500;
  cursor: pointer;

  &.btn-primary {
    background-color: $color-primary;
    color: #000;
    &:hover {
      background-color: $color-primary-hover;
    }
  }
}
</style>