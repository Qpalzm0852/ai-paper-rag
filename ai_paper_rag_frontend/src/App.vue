<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import WorkspaceChatView from './components/WorkspaceChatView.vue'
import WorkspaceSettingsView from './components/WorkspaceSettingsView.vue'
import WorkspaceSidebar from './components/WorkspaceSidebar.vue'
import { useWorkspaceApp } from './composables/useWorkspaceApp'

const demoModeStorageKey = 'ai-paper-rag-demo-mode'

const {
  apiBaseUrl,
  currentView,
  userInput,
  isLoading,
  isUploading,
  documentsLoading,
  statusLoading,
  settingsLoading,
  savingSettings,
  deletingFileName,
  uploadedFiles,
  conversations,
  activeConversationId,
  activeConversation,
  activeMessages,
  statusSnapshot,
  settingsItems,
  settingsDraft,
  indexingTask,
  focusedDocuments,
  linkedDocumentName,
  workspaceAlerts,
  settingsError,
  canExportHistory,
  quickStatusTone,
  workspaceStatus,
  statusCards,
  initialize,
  switchView,
  handleFileUpload,
  createConversation,
  exportConversation,
  refreshWorkspaceData,
  setActiveConversation,
  deleteConversation,
  deleteDocument,
  toggleFocusedDocument,
  clearFocusedDocuments,
  linkSourceDocument,
  focusSourceDocument,
  prepareComparisonQuestion,
  preparePaperBriefQuestion,
  sendMessage,
  runComparison,
  runPaperBriefForDocument,
  refreshSettingsView,
  fetchSettings,
  saveSettings,
  updateSettingDraft,
} = useWorkspaceApp()

const isDemoMode = ref(false)

const stageBadges = computed(() => {
  const snapshot = statusSnapshot.value || {}
  return [
    `文献 ${snapshot.document_count || 0}`,
    `向量 ${snapshot.vector_record_count || 0}`,
    snapshot.models?.llm ? `模型 ${snapshot.models.llm}` : '模型待配置',
  ]
})

function loadDemoModePreference() {
  if (typeof window === 'undefined') return
  isDemoMode.value = window.localStorage.getItem(demoModeStorageKey) === '1'
}

function persistDemoModePreference(value) {
  if (typeof window === 'undefined') return
  if (value) {
    window.localStorage.setItem(demoModeStorageKey, '1')
    return
  }
  window.localStorage.removeItem(demoModeStorageKey)
}

function toggleDemoMode() {
  isDemoMode.value = !isDemoMode.value
}

watch(
  isDemoMode,
  (value) => {
    persistDemoModePreference(value)
  },
)

onMounted(async () => {
  loadDemoModePreference()
  await initialize()
})
</script>

<template>
  <div class="app-stage" :class="{ 'demo-mode': isDemoMode }">
    <span class="ambient-orb orb-a"></span>
    <span class="ambient-orb orb-b"></span>
    <span class="ambient-orb orb-c"></span>

    <header class="stage-header">
      <div class="stage-title-wrap">
        <p class="eyebrow">Graduate Interview Showcase</p>
        <h1>AI Paper RAG 文献演示台</h1>
        <p class="stage-subtitle">面向考研复试与作品展示的文献问答系统，强调可解释性、可追踪性与工程完成度。</p>
      </div>
      <div class="stage-badge-row">
        <button class="stage-toggle" type="button" @click="toggleDemoMode">
          {{ isDemoMode ? '退出演示模式' : '进入演示模式' }}
        </button>
        <span class="status-pill" :class="quickStatusTone">{{ workspaceStatus }}</span>
        <span v-for="badge in stageBadges" :key="badge" class="stage-badge">{{ badge }}</span>
      </div>
    </header>

    <div class="workspace-shell" :class="{ 'demo-mode': isDemoMode }">
      <WorkspaceSidebar
        :current-view="currentView"
        :uploaded-files="uploadedFiles"
        :conversations="conversations"
        :active-conversation-id="activeConversationId"
        :can-export-history="canExportHistory"
        :workspace-status="workspaceStatus"
        :quick-status-tone="quickStatusTone"
        :api-base-url="apiBaseUrl"
        :is-uploading="isUploading"
        :is-loading="isLoading"
        :deleting-file-name="deletingFileName"
        :documents-loading="documentsLoading"
        :status-loading="statusLoading"
        :indexing-task="indexingTask"
        :focused-documents="focusedDocuments"
        :linked-document-name="linkedDocumentName"
        :demo-mode="isDemoMode"
        @switch-view="switchView"
        @file-upload="handleFileUpload"
        @create-conversation="createConversation"
        @export-conversation="exportConversation"
        @refresh-workspace-data="refreshWorkspaceData"
        @set-active-conversation="setActiveConversation"
        @delete-conversation="deleteConversation"
        @delete-document="deleteDocument"
        @toggle-focused-document="toggleFocusedDocument"
        @clear-focused-documents="clearFocusedDocuments"
        @prepare-paper-brief-question="preparePaperBriefQuestion"
        @run-paper-brief="runPaperBriefForDocument"
      />

      <WorkspaceChatView
        v-if="currentView === 'workspace'"
        :active-conversation="activeConversation"
        :active-messages="activeMessages"
        :status-snapshot="statusSnapshot"
        :focused-documents="focusedDocuments"
        :linked-document-name="linkedDocumentName"
        :workspace-alerts="workspaceAlerts"
        :is-loading="isLoading"
        :is-uploading="isUploading"
        :deleting-file-name="deletingFileName"
        :user-input="userInput"
        :demo-mode="isDemoMode"
        @update:user-input="userInput = $event"
        @send-message="sendMessage"
        @prepare-comparison-question="prepareComparisonQuestion"
        @run-comparison="runComparison"
        @link-source-document="linkSourceDocument"
        @focus-source-document="focusSourceDocument"
      />

      <WorkspaceSettingsView
        v-else
        :status-snapshot="statusSnapshot"
        :status-cards="statusCards"
        :workspace-status="workspaceStatus"
        :quick-status-tone="quickStatusTone"
        :status-loading="statusLoading"
        :settings-loading="settingsLoading"
        :saving-settings="savingSettings"
        :settings-items="settingsItems"
        :settings-draft="settingsDraft"
        :settings-error="settingsError"
        :demo-mode="isDemoMode"
        @refresh-settings-view="refreshSettingsView"
        @fetch-settings="fetchSettings"
        @save-settings="saveSettings"
        @update-setting="updateSettingDraft"
      />
    </div>
  </div>
</template>
