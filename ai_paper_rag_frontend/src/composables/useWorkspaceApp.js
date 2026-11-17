import { computed, ref, watch } from 'vue'
import { marked } from 'marked'

marked.setOptions({
  gfm: true,
  breaks: true,
})

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const uploadedFilesStorageKey = 'ai-paper-rag-uploaded-files'
const conversationsStorageKey = 'ai-paper-rag-conversations'
const activeConversationStorageKey = 'ai-paper-rag-active-conversation'
const currentViewStorageKey = 'ai-paper-rag-current-view'
const focusedDocumentsStorageKey = 'ai-paper-rag-focused-documents'

function renderMarkdown(value) {
  return marked.parse(value || '')
}

function formatTimestamp(timestamp) {
  return new Date(timestamp).toLocaleString('zh-CN', { hour12: false })
}

function formatFileSize(size) {
  if (!Number.isFinite(size) || size < 0) return '未知大小'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function buildWelcomeMessage() {
  return {
    id: crypto.randomUUID(),
    role: 'ai',
    content: renderMarkdown('## 文献智能问答工作台\n上传 PDF 后，你可以围绕论文内容提问、做跨文档对比，并查看每次回答附带的来源卡片。'),
    rawText: '',
    sources: [],
    comparisonMode: false,
    comparisonBrief: null,
    paperBriefMode: false,
    paperBrief: null,
    focusedDocuments: [],
  }
}

function buildConversation(title = '新对话') {
  const now = Date.now()
  return {
    id: crypto.randomUUID(),
    title,
    updatedAt: now,
    updatedAtLabel: formatTimestamp(now),
    messages: [buildWelcomeMessage()],
  }
}

function normalizeSource(source) {
  return {
    fileName: source.file_name || source.fileName || '未知文献',
    pageLabel: source.page_label || source.pageLabel || '',
    snippet: source.snippet || '',
    score: source.score ?? null,
    metadata: source.metadata && typeof source.metadata === 'object' ? source.metadata : {},
  }
}

function sanitizeMessage(message) {
  return {
    id: message.id || crypto.randomUUID(),
    role: message.role,
    content: typeof message.content === 'string' ? message.content : '',
    rawText: typeof message.rawText === 'string' ? message.rawText : '',
    sources: Array.isArray(message.sources) ? message.sources.map((item) => normalizeSource(item)) : [],
    comparisonMode: Boolean(message.comparisonMode),
    comparisonBrief: normalizeComparisonBrief(message.comparisonBrief),
    paperBriefMode: Boolean(message.paperBriefMode),
    paperBrief: normalizePaperBrief(message.paperBrief),
    focusedDocuments: normalizeStringList(message.focusedDocuments),
  }
}

function sanitizeConversation(conversation) {
  const updatedAt = Number(conversation.updatedAt || Date.now())
  const messages = Array.isArray(conversation.messages)
    ? conversation.messages.filter((message) => message && message.role).map((message) => sanitizeMessage(message))
    : [buildWelcomeMessage()]

  return {
    id: conversation.id || crypto.randomUUID(),
    title: conversation.title || '未命名对话',
    updatedAt,
    updatedAtLabel: conversation.updatedAtLabel || formatTimestamp(updatedAt),
    messages: messages.length ? messages : [buildWelcomeMessage()],
  }
}

function normalizeUploadedFile(file) {
  const size = Number(file.size || 0)
  return {
    id: file.id || file.name || crypto.randomUUID(),
    name: file.name,
    size,
    sizeLabel: file.size_display || file.sizeLabel || formatFileSize(size),
    addedAt: file.updated_at_display || file.addedAt || '刚刚上传',
    path: file.path || '',
  }
}

function normalizeSettingItem(item) {
  return {
    key: item.key,
    label: item.label,
    helpText: item.help_text || item.helpText || '',
    type: item.type || 'text',
    secret: Boolean(item.secret),
    value: item.value ?? '',
    default: item.default ?? '',
  }
}

function normalizeTask(task) {
  return {
    id: task.id,
    taskType: task.task_type || task.taskType || 'task',
    status: task.status || 'queued',
    progress: Number(task.progress || 0),
    message: task.message || '',
    metadata: task.metadata || {},
    result: task.result || null,
    error: task.error || '',
    updatedAt: task.updated_at || task.updatedAt || Date.now() / 1000,
  }
}

function normalizeStringList(items) {
  if (!Array.isArray(items)) return []
  return items
    .map((item) => String(item || '').trim())
    .filter((item, index, list) => item && list.indexOf(item) === index)
}

function normalizeComparisonEvidence(item) {
  return {
    fileName: item.file_name || item.fileName || '未知文献',
    sourceCount: Number(item.source_count ?? item.sourceCount ?? 0),
    pageLabels: normalizeStringList(item.page_labels || item.pageLabels),
    topSnippets: normalizeStringList(item.top_snippets || item.topSnippets),
    bestScore: item.best_score ?? item.bestScore ?? null,
  }
}

function normalizeComparisonBrief(brief) {
  if (!brief || typeof brief !== 'object') return null

  const documents = normalizeStringList(brief.documents)
  const evidence = Array.isArray(brief.evidence) ? brief.evidence.map((item) => normalizeComparisonEvidence(item)) : []
  const missingDocuments = normalizeStringList(brief.missing_documents || brief.missingDocuments)

  if (!documents.length && !evidence.length) {
    return null
  }

  return {
    question: typeof brief.question === 'string' ? brief.question : '',
    summary: typeof brief.summary === 'string' ? brief.summary : '',
    documents,
    evidence,
    missingDocuments,
  }
}

function normalizePaperBrief(brief) {
  if (!brief || typeof brief !== 'object') return null

  const documentName = String(brief.document || brief.document_name || '').trim()
  const pageLabels = normalizeStringList(brief.page_labels || brief.pageLabels)
  const topSnippets = normalizeStringList(brief.top_snippets || brief.topSnippets)
  const sourceCount = Number(brief.source_count ?? brief.sourceCount ?? 0)
  const summary = typeof brief.summary === 'string' ? brief.summary : ''

  if (!documentName && !summary && !pageLabels.length && !topSnippets.length && !sourceCount) {
    return null
  }

  return {
    document: documentName,
    summary,
    sourceCount,
    pageLabels,
    topSnippets,
  }
}

function buildComparisonQuestion(documentNames) {
  const normalized = normalizeStringList(documentNames)
  if (normalized.length < 2) {
    return '请比较这些文献的研究问题、核心方法、实验结论和适用场景。'
  }
  return `请对比 ${normalized.map((name) => `《${name}》`).join('、')} 的研究问题、核心方法、实验结论和适用场景。`
}

function buildPaperBriefQuestion(documentName) {
  const normalized = String(documentName || '').trim()
  if (!normalized) {
    return '请生成这篇论文的速览卡。'
  }
  return `请为《${normalized}》生成一张论文速览卡。`
}

function buildDefaultStatus() {
  return {
    rag_ready: false,
    startup_error: '',
    dependencies_ok: false,
    rag_import_error: '',
    google_api_key_configured: false,
    llama_parse_configured: false,
    document_count: 0,
    vector_record_count: 0,
    collection_name: '',
    uploads_dir: '',
    chroma_db_path: '',
    recent_tasks: [],
    models: {
      llm: '',
      embedding: '',
    },
  }
}

function loadStorage(key) {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(key)
}

function saveStorage(key, value) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(key, value)
}

function removeStorage(key) {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(key)
}

export function useWorkspaceApp() {
  const currentView = ref('workspace')
  const userInput = ref('')
  const isLoading = ref(false)
  const isUploading = ref(false)
  const documentsLoading = ref(false)
  const statusLoading = ref(false)
  const settingsLoading = ref(false)
  const savingSettings = ref(false)
  const deletingFileName = ref('')
  const uploadedFiles = ref([])
  const conversations = ref([buildConversation()])
  const activeConversationId = ref(conversations.value[0].id)
  const statusSnapshot = ref(buildDefaultStatus())
  const settingsItems = ref([])
  const settingsDraft = ref({})
  const indexingTask = ref(null)
  const taskPollTimer = ref(null)
  const focusedDocumentNames = ref([])
  const linkedDocumentName = ref('')
  const settingsError = ref('')

  const activeConversation = computed(() => {
    return conversations.value.find((conversation) => conversation.id === activeConversationId.value) || conversations.value[0] || null
  })

  const activeMessages = computed(() => activeConversation.value?.messages || [])
  const focusedDocuments = computed(() => uploadedFiles.value.filter((file) => focusedDocumentNames.value.includes(file.name)))
  const canExportHistory = computed(() => (activeConversation.value?.messages.length || 0) > 1)
  const quickStatusTone = computed(() => {
    if (indexingTask.value && indexingTask.value.status === 'failed') return 'warning'
    if (statusSnapshot.value.rag_ready) return 'online'
    if (statusSnapshot.value.startup_error) return 'warning'
    return 'neutral'
  })
  const workspaceStatus = computed(() => {
    if (indexingTask.value && ['queued', 'running'].includes(indexingTask.value.status)) {
      return `正在索引 ${indexingTask.value.metadata?.file_name || '文献'} (${indexingTask.value.progress}%)`
    }
    if (isUploading.value) return '正在上传文件'
    if (isLoading.value) return '正在生成回答'
    if (savingSettings.value) return '正在保存设置'
    if (documentsLoading.value || statusLoading.value || settingsLoading.value) return '正在同步数据'
    if (deletingFileName.value) return '正在删除文献'
    if (statusSnapshot.value.rag_ready) return '系统在线'
    return statusSnapshot.value.startup_error || '系统待配置'
  })
  const statusCards = computed(() => {
    const snapshot = statusSnapshot.value
    return [
      {
        label: 'RAG 引擎',
        value: snapshot.rag_ready ? '已就绪' : '未就绪',
        tone: snapshot.rag_ready ? 'good' : 'warn',
        note: snapshot.startup_error || '可直接执行检索问答',
      },
      {
        label: '依赖状态',
        value: snapshot.dependencies_ok ? '正常' : '缺失',
        tone: snapshot.dependencies_ok ? 'good' : 'danger',
        note: snapshot.rag_import_error || '核心依赖已加载',
      },
      {
        label: '已收录文献',
        value: String(snapshot.document_count || 0),
        tone: 'neutral',
        note: '上传目录中的 PDF 文件数',
      },
      {
        label: '向量条目',
        value: String(snapshot.vector_record_count || 0),
        tone: 'neutral',
        note: snapshot.collection_name || 'ai_paper',
      },
      {
        label: 'Google API Key',
        value: snapshot.google_api_key_configured ? '已配置' : '未配置',
        tone: snapshot.google_api_key_configured ? 'good' : 'warn',
        note: 'Gemini 模型调用所需',
      },
      {
        label: '索引任务',
        value: indexingTask.value ? `${indexingTask.value.progress}%` : String((snapshot.recent_tasks || []).length),
        tone: indexingTask.value?.status === 'failed' ? 'danger' : 'neutral',
        note: indexingTask.value ? indexingTask.value.message : '最近任务记录数',
      },
    ]
  })
  const workspaceAlerts = computed(() => {
    const alerts = []
    const hasDocuments = uploadedFiles.value.length > 0

    if (!hasDocuments) {
      alerts.push({
        id: 'no-documents',
        tone: 'warning',
        title: '还没有上传文献',
        description: '先上传至少一篇 PDF，再进行问答或来源追踪。',
      })
    }

    if (statusSnapshot.value.startup_error && hasDocuments) {
      alerts.push({
        id: 'startup-error',
        tone: 'danger',
        title: '系统尚未就绪',
        description: statusSnapshot.value.startup_error,
      })
    }

    if (indexingTask.value?.status === 'running' || indexingTask.value?.status === 'queued') {
      alerts.push({
        id: 'indexing-task',
        tone: 'info',
        title: '索引任务进行中',
        description: indexingTask.value.error || indexingTask.value.message,
      })
    }

    if (indexingTask.value?.status === 'failed') {
      alerts.push({
        id: 'indexing-failed',
        tone: 'danger',
        title: '索引任务失败',
        description: indexingTask.value.error || indexingTask.value.message,
      })
    }

    return alerts
  })

  function applyStatusSnapshot(snapshot, options = {}) {
    const { resumePolling = true } = options
    const recentTasks = Array.isArray(snapshot?.recent_tasks) ? snapshot.recent_tasks.map((item) => normalizeTask(item)) : []

    statusSnapshot.value = {
      ...buildDefaultStatus(),
      ...(snapshot || {}),
      recent_tasks: recentTasks,
    }

    if (!resumePolling) {
      return
    }

    const activeTask = recentTasks.find((task) => ['queued', 'running'].includes(task.status))
    if (activeTask) {
      const shouldResumePolling = indexingTask.value?.id !== activeTask.id || !['queued', 'running'].includes(indexingTask.value?.status)
      indexingTask.value = activeTask
      if (shouldResumePolling) {
        void pollTask(activeTask.id)
      }
      return
    }

    if (!indexingTask.value || ['queued', 'running'].includes(indexingTask.value.status)) {
      indexingTask.value = null
      clearTaskPolling()
    }
  }

  function clearTaskPolling() {
    if (taskPollTimer.value) {
      window.clearTimeout(taskPollTimer.value)
      taskPollTimer.value = null
    }
  }

  function loadUploadedFilesFromStorage() {
    const raw = loadStorage(uploadedFilesStorageKey)
    if (!raw) return

    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        uploadedFiles.value = parsed.filter((item) => item && item.name).map((item) => normalizeUploadedFile(item))
      }
    } catch {
      removeStorage(uploadedFilesStorageKey)
    }
  }

  function loadConversationsFromStorage() {
    const raw = loadStorage(conversationsStorageKey)
    if (!raw) return

    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length) {
        conversations.value = parsed.map((conversation) => sanitizeConversation(conversation))
      }
    } catch {
      removeStorage(conversationsStorageKey)
    }
  }

  function loadFocusedDocumentsFromStorage() {
    const raw = loadStorage(focusedDocumentsStorageKey)
    if (!raw) return

    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        focusedDocumentNames.value = normalizeStringList(parsed)
      }
    } catch {
      removeStorage(focusedDocumentsStorageKey)
    }
  }

  function loadViewState() {
    const savedView = loadStorage(currentViewStorageKey)
    if (savedView === 'workspace' || savedView === 'settings') {
      currentView.value = savedView
    }

    const savedActiveConversationId = loadStorage(activeConversationStorageKey)
    const exists = conversations.value.some((conversation) => conversation.id === savedActiveConversationId)
    activeConversationId.value = exists ? savedActiveConversationId : conversations.value[0]?.id || ''
  }

  function syncFocusedDocuments() {
    const availableNames = new Set(uploadedFiles.value.map((file) => file.name))
    focusedDocumentNames.value = focusedDocumentNames.value.filter((name) => availableNames.has(name))
    if (linkedDocumentName.value && !availableNames.has(linkedDocumentName.value)) {
      linkedDocumentName.value = ''
    }
  }

  function replaceUploadedFiles(files) {
    uploadedFiles.value = files.map((file) => normalizeUploadedFile(file))
    syncFocusedDocuments()
  }

  function upsertUploadedFile(file) {
    const normalized = normalizeUploadedFile(file)
    const nextFiles = uploadedFiles.value.filter((item) => item.name !== normalized.name)
    nextFiles.unshift(normalized)
    uploadedFiles.value = nextFiles
    syncFocusedDocuments()
  }

  function toggleFocusedDocument(file) {
    const fileName = file?.name
    if (!fileName) return

    if (focusedDocumentNames.value.includes(fileName)) {
      focusedDocumentNames.value = focusedDocumentNames.value.filter((name) => name !== fileName)
      return
    }

    focusedDocumentNames.value = [...focusedDocumentNames.value, fileName]
  }

  function clearFocusedDocuments() {
    focusedDocumentNames.value = []
  }

  function linkSourceDocument(fileName) {
    const normalized = String(fileName || '').trim()
    if (!normalized) return
    linkedDocumentName.value = normalized
  }

  function focusSourceDocument(fileName) {
    const normalized = String(fileName || '').trim()
    if (!normalized) return

    linkSourceDocument(normalized)
    if (!focusedDocumentNames.value.includes(normalized)) {
      focusedDocumentNames.value = [...focusedDocumentNames.value, normalized]
    }
    currentView.value = 'workspace'
  }

  async function fetchDocuments() {
    documentsLoading.value = true
    try {
      const response = await fetch(`${apiBaseUrl}/api/documents/`)
      const payload = await response.json()
      if (!response.ok || payload.code !== 200 || !Array.isArray(payload.data)) {
        throw new Error(payload.msg || '加载文献列表失败')
      }
      replaceUploadedFiles(payload.data)
    } catch {
      // Keep local cache if backend list fails.
    } finally {
      documentsLoading.value = false
    }
  }

  async function fetchStatus(options = {}) {
    const { resumePolling = true } = options
    statusLoading.value = true
    try {
      const response = await fetch(`${apiBaseUrl}/api/status/`)
      const payload = await response.json()
      if (!response.ok || payload.code !== 200) {
        throw new Error(payload.msg || '加载系统状态失败')
      }
      applyStatusSnapshot(payload.data, { resumePolling })
    } catch (error) {
      statusSnapshot.value = {
        ...statusSnapshot.value,
        startup_error: error.message,
      }
    } finally {
      statusLoading.value = false
    }
  }

  async function fetchTask(taskId) {
    const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}/`)
    const payload = await response.json()
    if (!response.ok || payload.code !== 200) {
      throw new Error(payload.msg || '任务状态读取失败')
    }
    return normalizeTask(payload.data)
  }

  async function pollTask(taskId) {
    clearTaskPolling()
    try {
      const task = await fetchTask(taskId)
      indexingTask.value = task
      await fetchStatus({ resumePolling: false })

      if (task.status === 'completed') {
        if (task.result) {
          upsertUploadedFile(task.result)
        } else {
          await fetchDocuments()
        }
        pushMessage('ai', renderMarkdown(`**${task.metadata?.file_name || '文献'}** 已完成索引，可以开始提问。`))
        return
      }

      if (task.status === 'failed') {
        pushMessage('ai', `<p class="error-text">索引失败：${task.error || task.message}</p>`)
        return
      }

      taskPollTimer.value = window.setTimeout(() => {
        pollTask(taskId)
      }, 2000)
    } catch (error) {
      pushMessage('ai', `<p class="error-text">任务状态同步失败：${error.message}</p>`)
    }
  }

  async function fetchSettings() {
    settingsLoading.value = true
    try {
      const response = await fetch(`${apiBaseUrl}/api/settings/`)
      const payload = await response.json()
      if (!response.ok || payload.code !== 200 || !Array.isArray(payload.data)) {
        throw new Error(payload.msg || '加载设置失败')
      }
      const nextItems = payload.data.map((item) => normalizeSettingItem(item))
      settingsItems.value = nextItems
      settingsDraft.value = Object.fromEntries(nextItems.map((item) => [item.key, item.value]))
      settingsError.value = ''
    } catch (error) {
      settingsItems.value = []
      settingsError.value = error.message
    } finally {
      settingsLoading.value = false
    }
  }

  function switchView(view) {
    currentView.value = view
  }

  function getActiveConversation() {
    return activeConversation.value
  }

  function touchConversation(conversation, nextTitle) {
    if (!conversation) return
    const now = Date.now()
    conversation.updatedAt = now
    conversation.updatedAtLabel = formatTimestamp(now)
    if (nextTitle) conversation.title = nextTitle
  }

  function deriveConversationTitle(content) {
    const plainText = content.replace(/^\[上传文件\]\s*/u, '').replace(/\s+/g, ' ').trim()
    return plainText.length > 18 ? `${plainText.slice(0, 18)}...` : plainText || '新对话'
  }

  function pushMessage(role, content, rawText = '', sources = [], extras = {}) {
    const conversation = getActiveConversation()
    if (!conversation) return

    conversation.messages.push(
      sanitizeMessage({
        id: crypto.randomUUID(),
        role,
        content,
        rawText,
        sources,
        comparisonMode: extras.comparisonMode,
        comparisonBrief: extras.comparisonBrief,
        paperBriefMode: extras.paperBriefMode,
        paperBrief: extras.paperBrief,
        focusedDocuments: extras.focusedDocuments,
      }),
    )

    if (role === 'user' && !content.startsWith('[上传文件]') && (conversation.title === '新对话' || conversation.messages.length <= 2)) {
      touchConversation(conversation, deriveConversationTitle(content))
    } else {
      touchConversation(conversation)
    }
  }

  function createConversation() {
    const conversation = buildConversation()
    conversations.value.unshift(conversation)
    activeConversationId.value = conversation.id
    currentView.value = 'workspace'
  }

  function setActiveConversation(conversationId) {
    activeConversationId.value = conversationId
    currentView.value = 'workspace'
  }

  function deleteConversation(conversationId) {
    const targetConversation = conversations.value.find((conversation) => conversation.id === conversationId)
    if (!targetConversation) return
    if (!window.confirm(`确定删除对话“${targetConversation.title}”吗？`)) return

    const nextConversations = conversations.value.filter((conversation) => conversation.id !== conversationId)
    conversations.value = nextConversations.length ? nextConversations : [buildConversation()]
    if (!conversations.value.some((conversation) => conversation.id === activeConversationId.value)) {
      activeConversationId.value = conversations.value[0].id
    }
  }

  function exportConversation() {
    const conversation = getActiveConversation()
    if (!conversation) return

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
    const content = conversation.messages
      .map((message) => {
        const title = message.role === 'ai' ? 'AI' : 'USER'
        const body = (message.rawText || message.content || '').replace(/<[^>]+>/g, '')
        const sourceText = Array.isArray(message.sources) && message.sources.length
          ? `\n\n来源:\n${message.sources.map((source) => `- ${source.fileName}${source.pageLabel ? ` 第 ${source.pageLabel} 页` : ''}: ${source.snippet || '无摘要'}`).join('\n')}`
          : ''
        return `## ${title}\n${body}${sourceText}`
      })
      .join('\n\n')

    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${conversation.title.replace(/[\\/:*?"<>|]/g, '-')}-${timestamp}.md`
    link.click()
    URL.revokeObjectURL(url)
  }

  async function handleFileUpload(event) {
    const file = event.target.files?.[0]
    if (!file) return

    pushMessage('user', `[上传文件] ${file.name}`)
    pushMessage('ai', renderMarkdown(`已接收 **${file.name}**，系统将后台建立索引，你可以继续浏览页面。`))

    isUploading.value = true
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`${apiBaseUrl}/api/upload/`, {
        method: 'POST',
        body: formData,
      })
      const payload = await response.json()
      if (!response.ok || payload.code !== 202) {
        throw new Error(payload.msg || '上传失败')
      }

      if (payload.status) {
        applyStatusSnapshot(payload.status, { resumePolling: false })
      } else {
        await fetchStatus({ resumePolling: false })
      }

      const taskId = payload.data?.task_id
      if (taskId) {
        indexingTask.value = {
          id: taskId,
          taskType: 'document_index',
          status: 'queued',
          progress: 0,
          message: payload.msg,
          metadata: { file_name: payload.data?.file_name || file.name },
          result: null,
          error: '',
          updatedAt: Date.now() / 1000,
        }
        pollTask(taskId)
      }
    } catch (error) {
      pushMessage('ai', `<p class="error-text">上传失败：${error.message}</p>`)
    } finally {
      isUploading.value = false
      event.target.value = ''
    }
  }

  async function deleteDocument(file) {
    if (!window.confirm(`确定删除 ${file.name} 吗？这会同时从知识库中移除相关内容。`)) return

    deletingFileName.value = file.name
    try {
      const response = await fetch(`${apiBaseUrl}/api/documents/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: file.name }),
      })
      const payload = await response.json()
      if (!response.ok || payload.code !== 200) {
        throw new Error(payload.msg || '删除失败')
      }

      replaceUploadedFiles(payload.data || [])
      if (payload.status) {
        applyStatusSnapshot(payload.status, { resumePolling: false })
      } else {
        await fetchStatus({ resumePolling: false })
      }
      pushMessage('ai', renderMarkdown(`已删除 **${file.name}**，知识库文献列表已同步更新。`))
    } catch (error) {
      pushMessage('ai', `<p class="error-text">删除失败：${error.message}</p>`)
    } finally {
      deletingFileName.value = ''
    }
  }

  function prepareComparisonQuestion() {
    if (focusedDocumentNames.value.length < 2) {
      pushMessage('ai', '<p class="error-text">请至少聚焦两篇文献后，再生成对比问答。</p>', '请至少聚焦两篇文献后，再生成对比问答。')
      return
    }

    userInput.value = buildComparisonQuestion(focusedDocumentNames.value)
    currentView.value = 'workspace'
  }

  function preparePaperBriefQuestion(file) {
    const documentName = String(file?.name || '').trim()
    if (!documentName) {
      pushMessage('ai', '<p class="error-text">请选择一篇文献后，再生成速览卡。</p>', '请选择一篇文献后，再生成速览卡。')
      return
    }

    linkSourceDocument(documentName)
    userInput.value = buildPaperBriefQuestion(documentName)
    currentView.value = 'workspace'
  }

  async function sendMessage(options = {}) {
    const question = String(options.presetQuestion || userInput.value || '').trim()
    const comparisonMode = Boolean(options.comparisonMode)
    const paperBriefMode = Boolean(options.paperBriefMode)
    const overrideFocusDocuments = normalizeStringList(options.focusDocuments)
    if (!question || isLoading.value || isUploading.value) return

    if (!uploadedFiles.value.length) {
      pushMessage('ai', '<p class="error-text">请先上传至少一篇 PDF 文献，再开始问答。</p>', '请先上传至少一篇 PDF 文献，再开始问答。')
      return
    }

    if (!statusSnapshot.value.rag_ready && statusSnapshot.value.startup_error) {
      pushMessage('ai', `<p class="error-text">系统尚未就绪：${statusSnapshot.value.startup_error}</p>`, `系统尚未就绪：${statusSnapshot.value.startup_error}`)
      return
    }

    if (comparisonMode && paperBriefMode) {
      pushMessage('ai', '<p class="error-text">当前请求不能同时启用多文献对比和论文速览模式。</p>', '当前请求不能同时启用多文献对比和论文速览模式。')
      return
    }

    const currentFocusedDocuments = overrideFocusDocuments.length ? overrideFocusDocuments : [...focusedDocumentNames.value]

    if (comparisonMode && currentFocusedDocuments.length < 2) {
      pushMessage('ai', '<p class="error-text">请至少聚焦两篇文献后，再发起多文献对比。</p>', '请至少聚焦两篇文献后，再发起多文献对比。')
      return
    }

    if (paperBriefMode && currentFocusedDocuments.length !== 1) {
      pushMessage('ai', '<p class="error-text">论文速览卡需要明确指定一篇文献。</p>', '论文速览卡需要明确指定一篇文献。')
      return
    }

    pushMessage('user', question)
    userInput.value = ''
    isLoading.value = true

    const conversation = getActiveConversation()
    if (!conversation) {
      isLoading.value = false
      return
    }

    const aiMessage = sanitizeMessage({
      id: crypto.randomUUID(),
      role: 'ai',
      content: '',
      rawText: '',
      sources: [],
      comparisonMode,
      comparisonBrief: null,
      paperBriefMode,
      paperBrief: null,
      focusedDocuments: currentFocusedDocuments,
    })
    conversation.messages.push(aiMessage)
    touchConversation(conversation)

    try {
      const response = await fetch(`${apiBaseUrl}/api/ask-json/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question,
          focus_documents: currentFocusedDocuments,
          comparison_mode: comparisonMode,
          paper_brief_mode: paperBriefMode,
        }),
      })
      const payload = await response.json()
      if (!response.ok || payload.code !== 200) {
        throw new Error(payload.msg || '问答请求失败')
      }

      const answer = payload.data?.answer || '模型没有返回正文内容。'
      aiMessage.rawText = answer
      aiMessage.content = renderMarkdown(answer)
      aiMessage.sources = Array.isArray(payload.data?.sources) ? payload.data.sources.map((item) => normalizeSource(item)) : []
      aiMessage.comparisonMode = Boolean(payload.data?.comparison_mode)
      aiMessage.comparisonBrief = normalizeComparisonBrief(payload.data?.comparison_brief)
      aiMessage.paperBriefMode = Boolean(payload.data?.paper_brief_mode)
      aiMessage.paperBrief = normalizePaperBrief(payload.data?.paper_brief)
      aiMessage.focusedDocuments = normalizeStringList(payload.data?.focused_documents || currentFocusedDocuments)
      touchConversation(conversation)
    } catch (error) {
      aiMessage.content = `<p class="error-text">请求失败：${error.message}</p>`
      aiMessage.rawText = `请求失败：${error.message}`
      aiMessage.sources = []
      aiMessage.comparisonMode = comparisonMode
      aiMessage.comparisonBrief = null
      aiMessage.paperBriefMode = paperBriefMode
      aiMessage.paperBrief = null
      aiMessage.focusedDocuments = currentFocusedDocuments
      touchConversation(conversation)
    } finally {
      isLoading.value = false
    }
  }

  async function runComparison() {
    if (focusedDocumentNames.value.length < 2) {
      pushMessage('ai', '<p class="error-text">请至少聚焦两篇文献后，再发起多文献对比。</p>', '请至少聚焦两篇文献后，再发起多文献对比。')
      return
    }

    const comparisonQuestion = buildComparisonQuestion(focusedDocumentNames.value)
    await sendMessage({
      presetQuestion: comparisonQuestion,
      comparisonMode: true,
    })
  }

  async function runPaperBriefForDocument(file) {
    const documentName = String(file?.name || '').trim()
    if (!documentName) {
      pushMessage('ai', '<p class="error-text">请选择一篇文献后，再生成速览卡。</p>', '请选择一篇文献后，再生成速览卡。')
      return
    }

    linkSourceDocument(documentName)
    currentView.value = 'workspace'
    await sendMessage({
      presetQuestion: buildPaperBriefQuestion(documentName),
      paperBriefMode: true,
      focusDocuments: [documentName],
    })
  }

  async function refreshWorkspaceData() {
    await Promise.all([fetchDocuments(), fetchStatus()])
  }

  async function refreshSettingsView() {
    await Promise.all([fetchStatus(), fetchSettings()])
  }

  async function saveSettings() {
    if (savingSettings.value) return
    savingSettings.value = true

    try {
      const response = await fetch(`${apiBaseUrl}/api/settings/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ settings: settingsDraft.value }),
      })
      const payload = await response.json()
      if (!response.ok || payload.code !== 200) {
        throw new Error(payload.msg || '保存设置失败')
      }

      const nextItems = Array.isArray(payload.data?.settings) ? payload.data.settings.map((item) => normalizeSettingItem(item)) : []
      settingsItems.value = nextItems
      settingsDraft.value = Object.fromEntries(nextItems.map((item) => [item.key, item.value]))
      settingsError.value = ''
      applyStatusSnapshot(payload.data?.status || {})
    } catch (error) {
      settingsError.value = error.message
    } finally {
      savingSettings.value = false
    }
  }

  function updateSettingDraft(key, value) {
    settingsDraft.value = {
      ...settingsDraft.value,
      [key]: value,
    }
  }

  async function initialize() {
    loadUploadedFilesFromStorage()
    loadConversationsFromStorage()
    loadFocusedDocumentsFromStorage()
    loadViewState()
    if (!activeConversationId.value && conversations.value.length) {
      activeConversationId.value = conversations.value[0].id
    }

    await Promise.all([fetchDocuments(), fetchStatus(), fetchSettings()])
  }

  watch(
    uploadedFiles,
    (files) => {
      saveStorage(uploadedFilesStorageKey, JSON.stringify(files))
    },
    { deep: true },
  )

  watch(
    conversations,
    (items) => {
      saveStorage(conversationsStorageKey, JSON.stringify(items.map((conversation) => sanitizeConversation(conversation))))
    },
    { deep: true },
  )

  watch(
    focusedDocumentNames,
    (items) => {
      saveStorage(focusedDocumentsStorageKey, JSON.stringify(items))
    },
    { deep: true },
  )

  watch(activeConversationId, (id) => {
    if (id) {
      saveStorage(activeConversationStorageKey, id)
    }
  })

  watch(currentView, (view) => {
    saveStorage(currentViewStorageKey, view)
  })

  return {
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
  }
}
















