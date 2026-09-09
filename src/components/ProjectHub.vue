<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchProjects, createProject, type Project } from '../services/api'
import SettingsModal from './SettingsModal.vue'

const emit = defineEmits<{
  (e: 'select-project', projectId: string): void
}>()

const projects = ref<Project[]>([])
const showCreateModal = ref(false)
const showSettingsModal = ref(false)
const manualProjectId = ref('')

const newProjectName = ref('')
const newProjectLLM = ref('local-model')
const newProjectEmbedding = ref('text-embedding-nomic-embed-text-v1.5')
const isCreating = ref(false)
const isLoading = ref(true)

onMounted(async () => {
  await loadProjects()
})

async function loadProjects() {
  isLoading.value = true
  try {
    projects.value = await fetchProjects()
  } catch (err) {
    console.error('Failed to load projects', err)
  } finally {
    isLoading.value = false
  }
}

async function handleCreateProject() {
  if (!newProjectName.value.trim()) return
  isCreating.value = true
  try {
    const proj = await createProject({
      name: newProjectName.value.trim(),
      llm_model: newProjectLLM.value,
      embedding_model: newProjectEmbedding.value
    })
    showCreateModal.value = false
    emit('select-project', proj.id)
  } catch (err) {
    console.error('Failed to create project', err)
  } finally {
    isCreating.value = false
  }
}

function handleOpenManual() {
  if (!manualProjectId.value.trim()) return
  emit('select-project', manualProjectId.value.trim())
}
</script>

<template>
  <div class="hub-container">
    <header class="hub-header">
      <div class="brand">
        <span class="brand-icon">📦</span>
        <span class="brand-title">Custodex</span>
        <span class="brand-tag">Workspace Hub</span>
      </div>
      <button class="btn btn-secondary" @click="showSettingsModal = true">
        ⚙️ Settings
      </button>
    </header>

    <main class="hub-content">
      <div class="hub-hero">
        <h1>Local-First RAG Dataset Workbench</h1>
        <p>Visually curate hierarchical documents, craft CMS metadata, and produce verified vector indexes.</p>
        <div class="hero-actions">
          <button class="btn btn-primary btn-large" @click="showCreateModal = true">
            + Create New Project
          </button>
        </div>
      </div>

      <div class="hub-sections">
        <div class="card recent-projects-card">
          <div class="card-header">
            <h3>Recent Projects</h3>
            <button class="btn btn-sm btn-ghost" @click="loadProjects">Refresh</button>
          </div>

          <div v-if="isLoading" class="muted-text">Loading projects...</div>

          <div v-else-if="projects.length === 0" class="empty-state">
            <p>No recent projects found. Create one to begin.</p>
          </div>

          <div v-else class="project-list">
            <div
              v-for="proj in projects"
              :key="proj.id"
              class="project-item"
              @click="emit('select-project', proj.id)"
            >
              <div class="proj-info">
                <h4>{{ proj.name }}</h4>
                <span class="proj-id">{{ proj.id }}</span>
              </div>
              <div class="proj-models">
                <span class="model-badge">{{ proj.embedding_model }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="card open-project-card">
          <div class="card-header">
            <h3>Open Project by ID</h3>
          </div>
          <p class="card-desc">Enter an existing project UUID to load its SQLite database.</p>
          <div class="input-row">
            <input
              v-model="manualProjectId"
              type="text"
              placeholder="e.g. proj_uuid..."
              @keyup.enter="handleOpenManual"
            />
            <button class="btn btn-secondary" @click="handleOpenManual" :disabled="!manualProjectId.trim()">
              Open
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- Create Project Modal -->
    <div v-if="showCreateModal" class="modal-backdrop" @click.self="showCreateModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Create New Project</h3>
          <button class="close-btn" @click="showCreateModal = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Project Name</label>
            <input v-model="newProjectName" type="text" placeholder="e.g. Enterprise Knowledge Base" autofocus />
          </div>
          <div class="form-group">
            <label>LLM Extraction Model</label>
            <input v-model="newProjectLLM" type="text" placeholder="local-model" />
          </div>
          <div class="form-group">
            <label>Vector Embedding Model</label>
            <input v-model="newProjectEmbedding" type="text" placeholder="text-embedding-nomic-embed-text-v1.5" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showCreateModal = false">Cancel</button>
          <button
            class="btn btn-primary"
            @click="handleCreateProject"
            :disabled="!newProjectName.trim() || isCreating"
          >
            {{ isCreating ? 'Creating...' : 'Create Project' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Settings Modal -->
    <SettingsModal v-if="showSettingsModal" @close="showSettingsModal = false" />
  </div>
</template>

<style scoped lang="scss">
@use '../styles/variables' as *;

.hub-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: $color-bg;
}

.hub-header {
  height: $header-height;
  background-color: $color-surface;
  border-bottom: 1px solid $color-border;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;

  .brand-icon {
    font-size: 20px;
  }
  .brand-title {
    font-size: 18px;
    font-weight: 700;
  }
  .brand-tag {
    font-size: 11px;
    background-color: $color-surface-hover;
    color: $color-primary;
    padding: 2px 8px;
    border-radius: $radius-sm;
    font-weight: 600;
  }
}

.hub-content {
  flex: 1;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
  padding: 48px 24px;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.hub-hero {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;

  h1 {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
  }

  p {
    font-size: 15px;
    color: $color-text-secondary;
    max-width: 540px;
  }

  .hero-actions {
    margin-top: 12px;
  }
}

.hub-sections {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
}

.card {
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-lg;
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  h3 {
    font-size: 16px;
    font-weight: 600;
  }
}

.card-desc {
  font-size: 13px;
  color: $color-text-secondary;
  margin-bottom: 12px;
}

.project-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.project-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: rgba(0, 0, 0, 0.2);
  border: 1px solid $color-border-subtle;
  border-radius: $radius-md;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background-color: $color-surface-hover;
    border-color: $color-primary;
  }

  .proj-info h4 {
    font-size: 14px;
    font-weight: 600;
  }

  .proj-id {
    font-size: 11px;
    font-family: $font-family-mono;
    color: $color-text-muted;
  }
}

.model-badge {
  font-size: 11px;
  font-family: $font-family-mono;
  background-color: rgba(56, 189, 248, 0.1);
  color: $color-primary;
  padding: 2px 8px;
  border-radius: $radius-sm;
}

.input-row {
  display: flex;
  gap: 8px;

  input {
    flex: 1;
    background-color: rgba(0, 0, 0, 0.3);
    border: 1px solid $color-border;
    border-radius: $radius-md;
    padding: 8px 12px;
    color: $color-text-primary;
    outline: none;

    &:focus {
      border-color: $color-primary;
    }
  }
}

.btn {
  padding: 8px 16px;
  border-radius: $radius-md;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;

  &.btn-large {
    padding: 10px 24px;
    font-size: 15px;
  }

  &.btn-primary {
    background-color: $color-primary;
    color: #000;
    &:hover:not(:disabled) {
      background-color: $color-primary-hover;
    }
  }

  &.btn-secondary {
    background-color: $color-surface-hover;
    color: $color-text-primary;
    border: 1px solid $color-border;
    &:hover:not(:disabled) {
      background-color: lighten(#334155, 5%);
    }
  }

  &.btn-ghost {
    color: $color-text-secondary;
    padding: 4px 8px;
    &:hover {
      color: $color-text-primary;
    }
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  background-color: $color-surface;
  border: 1px solid $color-border;
  border-radius: $radius-lg;
  width: 460px;
  max-width: 90vw;
  box-shadow: $shadow-modal;
}

.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid $color-border;
  display: flex;
  justify-content: space-between;
  align-items: center;

  .close-btn {
    color: $color-text-secondary;
    &:hover {
      color: $color-text-primary;
    }
  }
}

.modal-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;

  label {
    font-size: 12px;
    font-weight: 600;
    color: $color-text-secondary;
    text-transform: uppercase;
  }

  input {
    background-color: rgba(0, 0, 0, 0.3);
    border: 1px solid $color-border;
    border-radius: $radius-md;
    padding: 8px 12px;
    color: $color-text-primary;
    outline: none;

    &:focus {
      border-color: $color-primary;
    }
  }
}

.modal-footer {
  padding: 14px 20px;
  border-top: 1px solid $color-border;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.empty-state {
  color: $color-text-muted;
  text-align: center;
  padding: 24px;
}
</style>