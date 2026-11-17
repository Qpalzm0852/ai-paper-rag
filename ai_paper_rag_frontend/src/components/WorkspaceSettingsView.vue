<script setup>
import { computed } from 'vue'

const props = defineProps({
  statusSnapshot: { type: Object, required: true },
  statusCards: { type: Array, required: true },
  workspaceStatus: { type: String, required: true },
  quickStatusTone: { type: String, required: true },
  statusLoading: { type: Boolean, required: true },
  settingsLoading: { type: Boolean, required: true },
  savingSettings: { type: Boolean, required: true },
  settingsItems: { type: Array, required: true },
  settingsDraft: { type: Object, required: true },
  settingsError: { type: String, default: '' },
  demoMode: { type: Boolean, default: false },
})

const emit = defineEmits(['refresh-settings-view', 'fetch-settings', 'save-settings', 'update-setting'])

const settingsHighlights = computed(() => {
  const snapshot = props.statusSnapshot || {}
  const tasks = Array.isArray(snapshot.recent_tasks) ? snapshot.recent_tasks.length : 0
  return [
    {
      label: '文献库存',
      value: snapshot.document_count || 0,
      note: '已上传并可检索的论文数量',
    },
    {
      label: '向量规模',
      value: snapshot.vector_record_count || 0,
      note: snapshot.collection_name || '默认集合',
    },
    {
      label: '任务记录',
      value: tasks,
      note: '最近异步索引任务条数',
    },
  ]
})

const runtimeStates = computed(() => {
  const states = []
  if (props.statusLoading) {
    states.push({
      id: 'status-loading',
      tone: 'loading',
      title: '系统状态同步中',
      description: '正在拉取最新健康状态和任务快照。',
    })
  }

  if (props.settingsLoading) {
    states.push({
      id: 'settings-loading',
      tone: 'loading',
      title: '配置项加载中',
      description: '正在读取当前配置，请稍候。',
    })
  }

  if (props.settingsError) {
    states.push({
      id: 'settings-error',
      tone: 'error',
      title: '配置读取失败',
      description: props.settingsError,
    })
  }

  return states
})
</script>

<template>
  <main :class="['workspace-main', 'settings', { 'demo-settings': demoMode }]">
    <div class="settings-view">
      <section class="settings-hero premium-settings-hero">
        <div class="settings-hero-copy">
          <p class="eyebrow">Settings & Health</p>
          <h2>设置与系统状态页</h2>
          <p class="settings-copy">
            这里集中展示依赖、模型、索引和文献健康状态，也可以直接修改关键配置，适合演示“系统可管理性”。
          </p>
          <div class="hero-chip-row">
            <span class="hero-chip">状态透明</span>
            <span class="hero-chip">配置可编辑</span>
            <span class="hero-chip subtle">适合答辩展示</span>
          </div>
        </div>
        <div class="settings-hero-aside">
          <span class="status-pill big" :class="quickStatusTone">{{ workspaceStatus }}</span>
          <button class="secondary-action wide" type="button" @click="emit('refresh-settings-view')" :disabled="statusLoading || settingsLoading">
            刷新状态与配置
          </button>
        </div>
      </section>

      <section v-if="demoMode" class="demo-mode-banner settings-demo-banner">
        <span class="mini-tag accent">演示模式</span>
        <p class="panel-hint">设置页保留核心状态指标，便于现场快速展示系统健康度。</p>
      </section>

      <section class="settings-highlight-row">
        <article v-for="item in settingsHighlights" :key="item.label" class="settings-highlight-card">
          <p class="status-label">{{ item.label }}</p>
          <p class="status-value">{{ item.value }}</p>
          <p class="status-note">{{ item.note }}</p>
        </article>
      </section>

      <section v-if="runtimeStates.length" class="state-strip">
        <article v-for="state in runtimeStates" :key="state.id" class="state-block" :class="state.tone">
          <p class="state-title">{{ state.title }}</p>
          <p class="state-description">{{ state.description }}</p>
        </article>
      </section>

      <section class="settings-content">
        <article class="settings-panel elevated">
          <div class="panel-head tight">
            <span>系统状态</span>
            <span class="mini-tag accent">Realtime Snapshot</span>
          </div>
          <div class="status-grid">
            <article v-for="card in statusCards" :key="card.label" class="status-card" :class="card.tone">
              <p class="status-label">{{ card.label }}</p>
              <p class="status-value">{{ card.value }}</p>
              <p class="status-note">{{ card.note }}</p>
            </article>
          </div>
          <div class="status-detail-list">
            <div class="detail-item">
              <span>上传目录</span>
              <code>{{ statusSnapshot.uploads_dir || '-' }}</code>
            </div>
            <div class="detail-item">
              <span>Chroma 路径</span>
              <code>{{ statusSnapshot.chroma_db_path || '-' }}</code>
            </div>
            <div class="detail-item">
              <span>模型</span>
              <code>{{ statusSnapshot.models?.llm || '-' }}</code>
            </div>
            <div class="detail-item">
              <span>Embedding</span>
              <code>{{ statusSnapshot.models?.embedding || '-' }}</code>
            </div>
          </div>
        </article>

        <article class="settings-panel elevated">
          <div class="panel-head tight">
            <span>最近任务</span>
            <span class="mini-tag">{{ (statusSnapshot.recent_tasks || []).length }} 条</span>
          </div>
          <div v-if="statusSnapshot.recent_tasks?.length" class="task-list">
            <article v-for="task in statusSnapshot.recent_tasks" :key="task.id" class="task-card">
              <div class="task-card-head">
                <div>
                  <p class="status-label">{{ task.task_type || 'task' }}</p>
                  <p class="file-name">{{ task.metadata?.file_name || task.id }}</p>
                </div>
                <span class="mini-tag">{{ task.progress }}%</span>
              </div>
              <p class="status-note">{{ task.error || task.message }}</p>
              <div class="progress-track compact">
                <div class="progress-fill" :style="{ width: `${task.progress}%` }"></div>
              </div>
            </article>
          </div>
          <article v-else class="state-block empty">
            <p class="state-title">暂无索引任务记录</p>
            <p class="state-description">上传新论文后，后台任务会在这里展示进度与结果。</p>
          </article>
        </article>

        <article class="settings-panel elevated">
          <div class="panel-head tight">
            <span>配置项</span>
            <button class="text-button" type="button" @click="emit('fetch-settings')" :disabled="settingsLoading">重新加载</button>
          </div>

          <article v-if="settingsLoading" class="state-block loading">
            <p class="state-title">配置项加载中</p>
            <p class="state-description">正在同步环境配置，请稍候。</p>
          </article>

          <form v-else class="settings-form" @submit.prevent="emit('save-settings')">
            <div v-if="settingsItems.length" class="settings-grid">
              <label v-for="item in settingsItems" :key="item.key" class="setting-field">
                <span class="setting-title">{{ item.label }}</span>
                <input
                  :type="item.type"
                  :value="settingsDraft[item.key] ?? ''"
                  :placeholder="item.default"
                  @input="emit('update-setting', item.key, $event.target.value)"
                />
                <small>{{ item.helpText }}</small>
              </label>
            </div>
            <article v-else class="state-block empty">
              <p class="state-title">没有可编辑配置项</p>
              <p class="state-description">当前后端没有返回可写入字段，请检查配置接口定义。</p>
            </article>
            <div class="form-actions">
              <button class="composer-send wide" type="submit" :disabled="savingSettings">
                {{ savingSettings ? '保存中...' : '保存设置' }}
              </button>
            </div>
          </form>
        </article>
      </section>
    </div>
  </main>
</template>
