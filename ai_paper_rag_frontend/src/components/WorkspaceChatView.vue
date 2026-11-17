<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  activeConversation: { type: Object, default: null },
  activeMessages: { type: Array, required: true },
  statusSnapshot: { type: Object, required: true },
  focusedDocuments: { type: Array, required: true },
  linkedDocumentName: { type: String, default: '' },
  workspaceAlerts: { type: Array, required: true },
  isLoading: { type: Boolean, required: true },
  isUploading: { type: Boolean, required: true },
  deletingFileName: { type: String, required: true },
  userInput: { type: String, required: true },
  demoMode: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:userInput',
  'send-message',
  'prepare-comparison-question',
  'run-comparison',
  'link-source-document',
  'focus-source-document',
])
const messagesEl = ref(null)
const expandedSourceKeys = ref({})
const copiedSourceKey = ref('')
let copyResetTimer = null

const inputModel = computed({
  get: () => props.userInput,
  set: (value) => emit('update:userInput', value),
})

const headerOperationState = computed(() => {
  if (props.isLoading) {
    return {
      tone: 'loading',
      text: 'AI 正在生成回答，请稍候。',
    }
  }

  if (props.isUploading) {
    return {
      tone: 'loading',
      text: '文献上传已提交，后台正在建立索引。',
    }
  }

  if (props.deletingFileName) {
    return {
      tone: 'warning',
      text: `正在删除文献：${props.deletingFileName}`,
    }
  }

  if (!props.statusSnapshot.rag_ready) {
    return {
      tone: 'warning',
      text: '系统尚未完全就绪，回答可能缺少来源卡片。',
    }
  }

  return null
})
const summaryCards = computed(() => [
  {
    label: '已收录文献',
    value: props.statusSnapshot.document_count || 0,
    note: '当前知识库中的 PDF 数量',
  },
  {
    label: '向量条目',
    value: props.statusSnapshot.vector_record_count || 0,
    note: props.statusSnapshot.collection_name || 'ai_paper',
  },
  {
    label: '对话模型',
    value: props.statusSnapshot.models?.llm || '-',
    note: '当前问答使用的模型',
  },
])

const showcaseFeatureCards = computed(() => [
  {
    title: '可解释回答',
    detail: '每次回答都尽量落到具体文献、页码和证据片段。',
  },
  {
    title: '多文献对比',
    detail: '围绕多篇论文输出结构化差异，而不是泛泛总结。',
  },
  {
    title: '论文速览卡',
    detail: '把单篇论文整理成更适合讲解和截图展示的成果卡。',
  },
])

const heroProofItems = computed(() => [
  `来源追踪 ${props.statusSnapshot.document_count || 0} 篇文献`,
  `状态透明 ${props.statusSnapshot.vector_record_count || 0} 条向量`,
  `演示就绪 ${props.statusSnapshot.models?.llm || '模型待配置'}`,
])

const paperBriefTitles = ['研究问题', '核心方法', '实验设计', '主要结论', '价值与局限']

function buildSourceKey(messageId, index) {
  return `${messageId}-${index}`
}

function toggleSourceCard(messageId, index) {
  const key = buildSourceKey(messageId, index)
  expandedSourceKeys.value = {
    ...expandedSourceKeys.value,
    [key]: !expandedSourceKeys.value[key],
  }
}

function isSourceExpanded(messageId, index) {
  return Boolean(expandedSourceKeys.value[buildSourceKey(messageId, index)])
}

function isFocusedSource(source) {
  return props.focusedDocuments.some((item) => item.name === source.fileName)
}

function isLinkedSource(source) {
  return props.linkedDocumentName === source.fileName
}

function isRequestFailure(message) {
  return (message.rawText || '').startsWith('请求失败：')
}

function shouldShowSourceEmpty(message) {
  return message.role === 'ai' && Boolean(message.rawText) && !message.sources?.length && !isRequestFailure(message)
}

function hasComparisonBrief(message) {
  return message.role === 'ai' && Boolean(message.comparisonMode) && Boolean(message.comparisonBrief?.documents?.length)
}

function hasPaperBrief(message) {
  return message.role === 'ai' && Boolean(message.paperBriefMode) && Boolean(message.paperBrief?.document)
}

function escapePattern(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function buildPaperBriefSections(rawText) {
  const normalized = String(rawText || '').replace(/\r/g, '').trim()
  if (!normalized) return []

  const sections = []
  for (let index = 0; index < paperBriefTitles.length; index += 1) {
    const title = paperBriefTitles[index]
    const nextTitles = paperBriefTitles.slice(index + 1).map((item) => escapePattern(item)).join('|')
    const nextHeadingPattern = nextTitles ? `(?=\n##\s*(?:${nextTitles})\s*\n|$)` : '$'
    const pattern = new RegExp(`(?:^|\n)##\s*${escapePattern(title)}\s*\n([\\s\\S]*?)${nextHeadingPattern}`)
    const match = normalized.match(pattern)
    if (!match) continue

    const body = match[1].trim()
    if (!body) continue
    sections.push({ title, body })
  }
  return sections
}

function getSourceMetadataEntries(source) {
  return Object.entries(source.metadata || {})
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .filter(([key]) => !['source_file', 'file_name'].includes(key))
}

function buildSourceSummary(source) {
  const parts = [source.fileName]
  if (source.pageLabel) {
    parts.push(`第 ${source.pageLabel} 页`)
  }
  if (source.score !== null) {
    parts.push(`分数 ${source.score}`)
  }
  if (source.snippet) {
    parts.push(source.snippet)
  }
  return parts.join(' | ')
}

function buildComparisonEvidenceSummary(item) {
  const segments = [`命中 ${item.sourceCount} 条证据`]
  if (item.bestScore !== null) {
    segments.push(`最高分 ${item.bestScore}`)
  }
  if (item.pageLabels?.length) {
    segments.push(`页码 ${item.pageLabels.join(' / ')}`)
  }
  return segments.join(' · ')
}

async function copySourceSummary(messageId, index, source) {
  const key = buildSourceKey(messageId, index)
  const text = buildSourceSummary(source)

  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.setAttribute('readonly', 'true')
      textarea.style.position = 'absolute'
      textarea.style.left = '-9999px'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }

    copiedSourceKey.value = key
    if (copyResetTimer) {
      window.clearTimeout(copyResetTimer)
    }
    copyResetTimer = window.setTimeout(() => {
      copiedSourceKey.value = ''
    }, 1800)
  } catch {
    copiedSourceKey.value = ''
  }
}

function countUniqueSourceFiles(message) {
  return new Set((message.sources || []).map((source) => source.fileName)).size
}

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

watch(
  () => props.activeMessages,
  async () => {
    await scrollToBottom()
  },
  { deep: true, immediate: true },
)

watch(
  () => props.activeConversation?.id,
  async () => {
    expandedSourceKeys.value = {}
    copiedSourceKey.value = ''
    await scrollToBottom()
  },
)
</script>

<template>
  <main :class="['workspace-main', 'workspace', { 'demo-chat': demoMode }]">
    <section v-if="demoMode" class="demo-mode-banner">
      <span class="mini-tag accent">演示模式</span>
      <p class="panel-hint">当前视图已聚焦对话和来源证据，适合现场展示与录屏。</p>
    </section>
    <section v-if="!demoMode" class="workspace-hero premium-hero">
      <div class="workspace-hero-copy premium-hero-copy">
        <p class="eyebrow">Grounded Answers</p>
        <h2>{{ activeConversation?.title || '对话与来源追踪' }}</h2>
        <p class="hero-copy-text lead-copy">
          这不是普通聊天页面，而是一套围绕论文阅读、复试展示和作品集讲解而设计的文献工作台。
        </p>
        <div class="hero-chip-row">
          <span class="hero-chip">来源卡片化展示</span>
          <span class="hero-chip">文献详情可追踪</span>
          <span class="hero-chip">多文献对比</span>
          <span class="hero-chip subtle">论文速览卡</span>
        </div>
        <div class="hero-proof-strip">
          <span v-for="item in heroProofItems" :key="item" class="hero-proof-pill">{{ item }}</span>
        </div>
        <div v-if="focusedDocuments.length" class="focus-summary-panel hero-focus-panel elevated-panel">
          <div class="panel-head tight">
            <span>当前问答仅围绕这些文献</span>
            <span class="mini-tag accent">{{ focusedDocuments.length }} 篇</span>
          </div>
          <div class="selection-pill-group">
            <span v-for="file in focusedDocuments" :key="file.id" class="selection-pill">{{ file.name }}</span>
          </div>
        </div>
        <div v-if="focusedDocuments.length >= 2" class="comparison-ready-panel elevated-panel">
          <div class="panel-head tight">
            <span>多文献对比模式已就绪</span>
            <span class="mini-tag accent">对比 {{ focusedDocuments.length }} 篇</span>
          </div>
          <p class="panel-hint">
            这一步更适合展示“不是普通聊天框”，而是能围绕多篇论文做结构化对比分析。
          </p>
          <div class="source-card-toolbar">
            <button class="text-button" type="button" :disabled="isLoading || isUploading || !!deletingFileName" @click="emit('prepare-comparison-question')">
              生成对比提问模板
            </button>
            <button class="text-button accent-button" type="button" :disabled="isLoading || isUploading || !!deletingFileName" @click="emit('run-comparison')">
              一键对比这几篇
            </button>
          </div>
        </div>
      </div>
      <div class="hero-aside-column">
        <div class="hero-summary-grid">
          <article v-for="card in summaryCards" :key="card.label" class="hero-summary-card premium-summary-card">
            <p class="hero-summary-label">{{ card.label }}</p>
            <p class="hero-summary-value">{{ card.value }}</p>
            <p class="hero-summary-note">{{ card.note }}</p>
          </article>
        </div>
        <div class="hero-feature-grid">
          <article v-for="item in showcaseFeatureCards" :key="item.title" class="hero-feature-card">
            <p class="source-kicker">作品亮点</p>
            <h3>{{ item.title }}</h3>
            <p class="hero-feature-copy">{{ item.detail }}</p>
          </article>
        </div>
      </div>
    </section>

    <section v-if="!demoMode && workspaceAlerts.length" class="alert-stack">
      <article v-for="alert in workspaceAlerts" :key="alert.id" class="alert-card" :class="alert.tone">
        <p class="alert-title">{{ alert.title }}</p>
        <p class="alert-copy">{{ alert.description }}</p>
      </article>
    </section>

    <section class="conversation-shell">
      <header class="main-header conversation-header">
        <div>
          <p class="eyebrow">Conversation Feed</p>
          <h2>{{ activeConversation?.title || '对话流' }}</h2>
        </div>
        <div class="header-actions">
          <div v-if="demoMode" class="header-badge subtle">演示模式</div>
          <div class="header-badge">{{ statusSnapshot.rag_ready ? 'Source Cards Ready' : 'Need Setup' }}</div>
          <div class="header-badge subtle">{{ Math.max(activeMessages.length - 1, 0) }} 条记录</div>
        </div>
      </header>

      <section v-if="headerOperationState" class="state-strip compact">
        <article class="state-block" :class="headerOperationState.tone">
          <p class="state-title">{{ headerOperationState.text }}</p>
        </article>
      </section>

      <section ref="messagesEl" class="message-board">
        <article v-for="message in activeMessages" :key="message.id" :class="['message-row', message.role, { 'row-with-sources': message.role === 'ai' && message.sources?.length }]">
          <div class="avatar">{{ message.role === 'ai' ? 'AI' : 'ME' }}</div>
          <div class="message-stack">
            <div :class="['bubble', message.role === 'ai' ? 'bubble-ai' : 'bubble-user']">
              <div v-if="message.role === 'ai' && isLoading && message.content === ''" class="typing-state">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <div v-else-if="message.role === 'ai'" v-html="message.content"></div>
              <div v-else>{{ message.content }}</div>
            </div>

            <div v-if="hasPaperBrief(message)" class="paper-brief-card premium-brief-card">
              <div class="paper-brief-head">
                <div>
                  <p class="source-kicker">论文速览卡</p>
                  <h3>{{ message.paperBrief.document }}</h3>
                </div>
                <span class="mini-tag accent">{{ message.paperBrief.sourceCount }} 条证据</span>
              </div>
              <p class="paper-brief-summary">{{ message.paperBrief.summary }}</p>
              <div class="paper-brief-meta-row">
                <span class="mini-tag subtle">页码 {{ message.paperBrief.pageLabels?.length ? message.paperBrief.pageLabels.join(' / ') : '未标注' }}</span>
                <span class="mini-tag subtle">聚焦文献 {{ message.focusedDocuments?.length || 1 }} 篇</span>
              </div>
              <div v-if="buildPaperBriefSections(message.rawText).length" class="paper-brief-grid">
                <article v-for="section in buildPaperBriefSections(message.rawText)" :key="`${message.id}-${section.title}`" class="paper-brief-section">
                  <p class="source-kicker">{{ section.title }}</p>
                  <p class="paper-brief-copy">{{ section.body }}</p>
                </article>
              </div>
              <blockquote v-else-if="message.paperBrief.topSnippets?.length" class="source-quote">
                {{ message.paperBrief.topSnippets[0] }}
              </blockquote>
            </div>

            <div v-if="hasComparisonBrief(message)" class="comparison-brief-card premium-brief-card">
              <div class="comparison-brief-head">
                <div>
                  <p class="source-kicker">多文献对比</p>
                  <h3>当前回答按对比模式组织</h3>
                </div>
                <span class="mini-tag accent">{{ message.comparisonBrief.documents.length }} 篇文献</span>
              </div>
              <p class="comparison-brief-copy">{{ message.comparisonBrief.summary }}</p>
              <div class="selection-pill-group">
                <span v-for="documentName in message.comparisonBrief.documents" :key="`${message.id}-${documentName}`" class="selection-pill comparison-pill">
                  {{ documentName }}
                </span>
              </div>
              <p v-if="message.comparisonBrief.missingDocuments?.length" class="comparison-missing-copy">
                当前证据未直接命中：{{ message.comparisonBrief.missingDocuments.join('、') }}
              </p>
              <div v-if="message.comparisonBrief.evidence?.length" class="comparison-evidence-grid">
                <article v-for="evidence in message.comparisonBrief.evidence" :key="`${message.id}-${evidence.fileName}`" class="comparison-evidence-card">
                  <p class="source-kicker">对比证据</p>
                  <h3>{{ evidence.fileName }}</h3>
                  <p class="comparison-evidence-copy">{{ buildComparisonEvidenceSummary(evidence) }}</p>
                  <p v-if="evidence.topSnippets?.length" class="comparison-evidence-copy muted">
                    {{ evidence.topSnippets[0] }}
                  </p>
                </article>
              </div>
            </div>

            <div v-if="shouldShowSourceEmpty(message)" class="source-empty-card premium-source-empty">
              <p class="source-kicker">来源提示</p>
              <p class="source-empty-copy">本次回答没有返回来源卡片。通常表示当前文献证据不足、模型回答较泛化，或系统尚未完成稳定检索。</p>
            </div>

            <template v-if="message.role === 'ai' && message.sources?.length">
              <div class="source-summary-bar premium-source-summary">
                <span class="source-summary-pill">{{ message.sources.length }} 条证据</span>
                <span class="source-summary-pill subtle">{{ countUniqueSourceFiles(message) }} 篇文献</span>
                <span class="source-summary-pill subtle">支持展开元数据</span>
              </div>

              <div class="source-card-grid premium-source-grid">
                <article v-for="(source, index) in message.sources" :key="`${message.id}-${index}`" :class="['source-card', 'evidence-card', 'premium-source-card', { linked: isLinkedSource(source) }]">
                  <div class="source-card-head">
                    <div>
                      <p class="source-kicker">来源 {{ index + 1 }}</p>
                      <h3>{{ source.fileName }}</h3>
                    </div>
                    <span v-if="source.score !== null" class="mini-tag">分数 {{ source.score }}</span>
                  </div>
                  <div class="source-meta-row">
                    <span v-if="source.pageLabel" class="mini-tag">第 {{ source.pageLabel }} 页</span>
                    <span class="mini-tag subtle">可追溯引用</span>
                    <span v-if="isLinkedSource(source)" class="mini-tag link-tag">已定位到左侧</span>
                  </div>
                  <blockquote class="source-quote">{{ source.snippet || '当前来源未返回摘要片段。' }}</blockquote>
                  <div class="source-card-toolbar">
                    <button class="text-button" type="button" @click="emit('link-source-document', source.fileName)">
                      定位文献
                    </button>
                    <button class="text-button" type="button" @click="emit('focus-source-document', source.fileName)">
                      {{ isFocusedSource(source) ? '已在聚焦范围' : '加入聚焦' }}
                    </button>
                    <button class="text-button" type="button" @click="toggleSourceCard(message.id, index)">
                      {{ isSourceExpanded(message.id, index) ? '收起细节' : '展开细节' }}
                    </button>
                    <button class="text-button" type="button" @click="copySourceSummary(message.id, index, source)">
                      {{ copiedSourceKey === buildSourceKey(message.id, index) ? '已复制' : '复制依据' }}
                    </button>
                  </div>
                  <div v-if="isSourceExpanded(message.id, index)" class="source-meta-list">
                    <div class="source-meta-item">
                      <span>文献名称</span>
                      <code>{{ source.fileName }}</code>
                    </div>
                    <div v-if="source.pageLabel" class="source-meta-item">
                      <span>页码</span>
                      <code>{{ source.pageLabel }}</code>
                    </div>
                    <div v-if="source.score !== null" class="source-meta-item">
                      <span>相关性分数</span>
                      <code>{{ source.score }}</code>
                    </div>
                    <div v-for="([metaKey, metaValue], metaIndex) in getSourceMetadataEntries(source)" :key="`${message.id}-${index}-${metaIndex}`" class="source-meta-item">
                      <span>{{ metaKey }}</span>
                      <code>{{ metaValue }}</code>
                    </div>
                  </div>
                </article>
              </div>
            </template>
          </div>
        </article>
      </section>

      <footer class="composer-shell">
        <div v-if="focusedDocuments.length >= 2" class="composer-quick-actions">
          <button class="text-button" type="button" :disabled="isLoading || isUploading || !!deletingFileName" @click="emit('prepare-comparison-question')">
            填入对比问题模板
          </button>
          <button class="text-button accent-button" type="button" :disabled="isLoading || isUploading || !!deletingFileName" @click="emit('run-comparison')">
            直接发起多文献对比
          </button>
        </div>
        <div class="composer">
          <input
            v-model="inputModel"
            class="composer-input"
            type="text"
            :placeholder="focusedDocuments.length ? `例如：这 ${focusedDocuments.length} 篇文献分别解决了什么问题？` : '例如：这篇论文解决了什么问题？与另外一篇文献相比有什么区别？'"
            :disabled="isLoading || isUploading || !!deletingFileName"
            @keyup.enter="emit('send-message')"
          />
          <button class="composer-send" type="button" :disabled="isLoading || isUploading || !!deletingFileName || !userInput.trim()" @click="emit('send-message')">
            {{ isLoading ? '生成中...' : '发送' }}
          </button>
        </div>
      </footer>
    </section>
  </main>
</template>





