<script setup>
import { computed, nextTick, watch } from 'vue'

const props = defineProps({
  currentView: { type: String, required: true },
  uploadedFiles: { type: Array, required: true },
  conversations: { type: Array, required: true },
  activeConversationId: { type: String, required: true },
  canExportHistory: { type: Boolean, required: true },
  workspaceStatus: { type: String, required: true },
  quickStatusTone: { type: String, required: true },
  apiBaseUrl: { type: String, required: true },
  isUploading: { type: Boolean, required: true },
  isLoading: { type: Boolean, required: true },
  deletingFileName: { type: String, required: true },
  documentsLoading: { type: Boolean, required: true },
  statusLoading: { type: Boolean, required: true },
  indexingTask: { type: Object, default: null },
  focusedDocuments: { type: Array, required: true },
  linkedDocumentName: { type: String, default: '' },
  demoMode: { type: Boolean, default: false },
})

const emit = defineEmits([
  'switch-view',
  'file-upload',
  'create-conversation',
  'export-conversation',
  'refresh-workspace-data',
  'set-active-conversation',
  'delete-conversation',
  'delete-document',
  'toggle-focused-document',
  'clear-focused-documents',
  'prepare-paper-brief-question',
  'run-paper-brief',
])

const fileElementMap = new Map()

const filesPrimaryState = computed(() => {
  if (props.uploadedFiles.length) return null
  if (props.documentsLoading) {
    return {
      tone: 'loading',
      title: '正在同步文献列表',
      description: '请稍候，系统正在从后端加载已上传文献。',
    }
  }
  return {
    tone: 'empty',
    title: '还没有文献',
    description: '上传至少一篇 PDF 后，这里会出现文献详情和操作入口。',
  }
})

const filesSyncState = computed(() => {
  if (!props.documentsLoading || !props.uploadedFiles.length) return null
  return {
    tone: 'loading',
    title: '文献列表同步中',
    description: '当前先展示本地缓存，完成后会自动更新最新数据。',
  }
})

const conversationState = computed(() => {
  if (props.conversations.length) return null
  return {
    tone: 'empty',
    title: '暂无会话',
    description: '点击“新建对话”即可开始一轮新的问答记录。',
  }
})

function setFileElement(fileName, element) {
  if (!fileName) return
  if (element) {
    fileElementMap.set(fileName, element)
    return
  }
  fileElementMap.delete(fileName)
}

function isFocusedDocument(fileName) {
  return props.focusedDocuments.some((item) => item.name === fileName)
}

function isLinkedDocument(fileName) {
  return props.linkedDocumentName === fileName
}

watch(
  () => props.linkedDocumentName,
  async (fileName) => {
    if (!fileName) return
    await nextTick()
    const element = fileElementMap.get(fileName)
    if (element && typeof element.scrollIntoView === 'function') {
      element.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  },
)
</script>

<template>
  <aside :class="['workspace-sidebar', { 'is-demo': demoMode }]">
    <div class="brand-block showcase-card premium-showcase-card">
      <p class="eyebrow">AI Paper RAG</p>
      <h1>{{ demoMode ? '演示模式' : '文献智能问答工作台' }}</h1>
      <p class="sidebar-copy">
        {{ demoMode ? '当前已切到大屏展示布局，聚焦核心问答与来源卡片。' : '更适合复试展示的论文检索问答前端，强调来源追踪、系统状态与产品完成度。' }}
      </p>
      <div class="brand-metrics">
        <span class="mini-tag">文献 {{ uploadedFiles.length }}</span>
        <span class="mini-tag subtle">对话 {{ conversations.length }}</span>
        <span class="mini-tag accent">展示版 UI</span>
      </div>
      <div class="brand-note">
        <span class="status-dot" :class="quickStatusTone"></span>
        <span>{{ workspaceStatus }}</span>
      </div>
      <div v-if="!demoMode" class="brand-proof-list">
        <div class="brand-proof-item">
          <strong>解释性</strong>
          <span>回答、来源、文献列表三者联动</span>
        </div>
        <div class="brand-proof-item">
          <strong>差异化</strong>
          <span>支持多文献对比和单篇论文速览卡</span>
        </div>
        <div class="brand-proof-item">
          <strong>工程化</strong>
          <span>异步索引、状态页、任务持久化一套打通</span>
        </div>
      </div>
    </div>

    <div v-if="indexingTask && ['queued', 'running', 'failed'].includes(indexingTask.status)" class="sidebar-panel task-panel">
      <div class="panel-head">
        <span>索引任务</span>
        <span class="mini-tag">{{ indexingTask.progress }}%</span>
      </div>
      <p class="file-name">{{ indexingTask.metadata?.file_name || '文献索引任务' }}</p>
      <p class="panel-hint">{{ indexingTask.error || indexingTask.message }}</p>
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: `${indexingTask.progress}%` }"></div>
      </div>
    </div>

    <div class="nav-switcher">
      <button class="nav-chip" :class="{ active: currentView === 'workspace' }" type="button" @click="emit('switch-view', 'workspace')">
        文献工作台
      </button>
      <button class="nav-chip" :class="{ active: currentView === 'settings' }" type="button" @click="emit('switch-view', 'settings')">
        设置与状态
      </button>
    </div>

    <label class="upload-action" :class="{ disabled: isUploading || isLoading || !!deletingFileName }">
      <span>{{ isUploading ? '上传中...' : '上传论文 PDF' }}</span>
      <strong>{{ uploadedFiles.length }}</strong>
      <input class="hidden-input" type="file" accept="application/pdf" :disabled="isUploading || isLoading || !!deletingFileName" @change="emit('file-upload', $event)" />
    </label>

    <section v-if="demoMode" class="sidebar-panel demo-brief-panel">
      <div class="panel-head tight">
        <span>演示视图</span>
        <span class="mini-tag accent">精简布局</span>
      </div>
      <p class="panel-hint">已隐藏会话与文献详情侧栏，右侧内容更适合现场演示和录屏。</p>
    </section>

    <section v-if="!demoMode" class="sidebar-panel action-panel">
      <button class="secondary-action" type="button" @click="emit('create-conversation')" :disabled="isLoading || isUploading || !!deletingFileName">
        新建对话
      </button>
      <button class="secondary-action" type="button" @click="emit('export-conversation')" :disabled="!canExportHistory || isLoading">
        导出演示记录
      </button>
    </section>

    <section class="sidebar-panel status-panel">
      <div class="panel-head">
        <span>运行状态</span>
        <span class="status-pill" :class="quickStatusTone">{{ workspaceStatus }}</span>
      </div>
      <p class="panel-hint">{{ statusLoading ? '正在同步后端状态...' : `后端接口连接到 ${apiBaseUrl}` }}</p>
    </section>

    <section v-if="!demoMode && focusedDocuments.length >= 2" class="sidebar-panel compare-panel">
      <div class="panel-head">
        <span>多文献对比</span>
        <span class="mini-tag accent">{{ focusedDocuments.length }} 篇</span>
      </div>
      <p class="panel-hint">
        当前聚焦范围已经满足对比条件。右侧工作台支持一键生成对比提问和对比证据摘要。
      </p>
    </section>

    <section v-if="!demoMode" class="sidebar-panel sessions-panel">
      <div class="panel-head">
        <span>会话列表</span>
        <span>{{ conversations.length }} 个</span>
      </div>
      <article v-if="conversationState" class="state-block" :class="conversationState.tone">
        <p class="state-title">{{ conversationState.title }}</p>
        <p class="state-description">{{ conversationState.description }}</p>
      </article>
      <ul v-else class="session-list">
        <li
          v-for="conversation in conversations"
          :key="conversation.id"
          :class="['session-item', { active: conversation.id === activeConversationId }]"
        >
          <button class="session-main" type="button" @click="emit('set-active-conversation', conversation.id)">
            <span class="session-title">{{ conversation.title }}</span>
            <span class="session-meta">{{ conversation.updatedAtLabel }}</span>
          </button>
          <button
            class="session-delete"
            type="button"
            :disabled="conversations.length === 1 || isLoading || isUploading"
            @click="emit('delete-conversation', conversation.id)"
          >
            删除
          </button>
        </li>
      </ul>
    </section>

    <section v-if="!demoMode" class="sidebar-panel files-panel">
      <div class="panel-head">
        <span>文献详情</span>
        <div class="header-actions wrap">
          <span v-if="focusedDocuments.length" class="mini-tag accent">已聚焦 {{ focusedDocuments.length }} 篇</span>
          <button class="text-button" type="button" @click="emit('refresh-workspace-data')" :disabled="documentsLoading || statusLoading">
            刷新
          </button>
        </div>
      </div>

      <article v-if="filesSyncState" class="state-block" :class="filesSyncState.tone">
        <p class="state-title">{{ filesSyncState.title }}</p>
        <p class="state-description">{{ filesSyncState.description }}</p>
      </article>

      <div v-if="focusedDocuments.length" class="focus-summary-panel">
        <div class="panel-head tight">
          <span>当前问答范围</span>
          <button class="text-button" type="button" @click="emit('clear-focused-documents')">清空</button>
        </div>
        <div class="selection-pill-group">
          <span v-for="file in focusedDocuments" :key="file.id" class="selection-pill">{{ file.name }}</span>
        </div>
      </div>

      <article v-if="filesPrimaryState" class="state-block" :class="filesPrimaryState.tone">
        <p class="state-title">{{ filesPrimaryState.title }}</p>
        <p class="state-description">{{ filesPrimaryState.description }}</p>
      </article>

      <ul v-else class="file-list detailed">
        <li
          v-for="file in uploadedFiles"
          :key="file.id"
          :ref="(element) => setFileElement(file.name, element)"
          :class="['file-item', 'detailed', { linked: isLinkedDocument(file.name) }]"
        >
          <div class="file-item-main vertical">
            <div>
              <p class="file-name">{{ file.name }}</p>
              <p class="file-time">{{ file.addedAt }}</p>
            </div>
            <div class="file-tags">
              <span class="mini-tag">{{ file.sizeLabel }}</span>
              <span v-if="file.path" class="mini-tag subtle">本地文件</span>
              <span v-if="isFocusedDocument(file.name)" class="mini-tag accent">问答聚焦中</span>
              <span v-if="isLinkedDocument(file.name)" class="mini-tag link-tag">来源定位</span>
            </div>
            <p v-if="file.path" class="file-path">{{ file.path }}</p>
            <div class="file-actions compact-wrap">
              <button
                class="secondary-action file-brief"
                type="button"
                :disabled="isUploading || isLoading || deletingFileName === file.name"
                @click="emit('run-paper-brief', file)"
              >
                论文速览
              </button>
              <button
                class="secondary-action file-template"
                type="button"
                :disabled="isUploading || isLoading || deletingFileName === file.name"
                @click="emit('prepare-paper-brief-question', file)"
              >
                速览模板
              </button>
              <button
                class="secondary-action file-focus"
                type="button"
                :disabled="isUploading || isLoading || deletingFileName === file.name"
                @click="emit('toggle-focused-document', file)"
              >
                {{ isFocusedDocument(file.name) ? '取消聚焦' : '聚焦问答' }}
              </button>
              <button
                class="file-delete"
                type="button"
                :disabled="deletingFileName === file.name || isUploading || isLoading"
                @click="emit('delete-document', file)"
              >
                {{ deletingFileName === file.name ? '删除中...' : '删除' }}
              </button>
            </div>
          </div>
        </li>
      </ul>
    </section>
  </aside>
</template>
