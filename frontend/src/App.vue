<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAgentStore } from '@/stores/agentStore'
import { AgentStatus, WorkflowStage, LogLevel } from '@/types/agent'
import type { Agent } from '@/types/agent'

import AgentScene from '@/components/visualization/AgentScene.vue'
import WorkflowGraph from '@/components/workflow/WorkflowGraph.vue'
import AgentCard from '@/components/agents/AgentCard.vue'
import LogConsole from '@/components/dashboard/LogConsole.vue'
import ResultCard from '@/components/dashboard/ResultCard.vue'

const store = useAgentStore()

const stockCode = ref('')
const stockName = ref('')
const selectedAgent = ref<Agent | null>(null)
const show3D = ref(true)
const analysisError = ref<string | null>(null)

const isAnalyzing = computed(() => store.isRunning)
const overallProgress = computed(() => store.overallProgress)

onMounted(() => {
  store.initAgents()
})

/**
 * 启动股票分析
 */
async function startAnalysis(): Promise<void> {
  if (!stockCode.value.trim()) return
  if (store.isRunning) return

  analysisError.value = null
  store.reset()
  store.isRunning = true

  store.addLog({
    id: `log_${Date.now()}`,
    timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
    level: LogLevel.INFO,
    source: 'system',
    sourceName: '系统',
    message: `开始分析 ${stockCode.value}...`,
  })

  try {
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        stock_code: stockCode.value.trim(),
        stock_name: stockName.value.trim() || undefined,
      }),
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || `分析请求失败 (${response.status})`)
    }

    const data = await response.json()

    simulateAgentProgress(data)
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : '未知错误'
    analysisError.value = errorMessage
    store.isRunning = false

    store.addLog({
      id: `log_${Date.now()}`,
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
      level: LogLevel.ERROR,
      source: 'system',
      sourceName: '系统',
      message: `分析失败: ${errorMessage}`,
    })
  }
}

/**
 * 模拟智能体进度更新（基于后端返回数据）
 * 由于后端分析是同步的，这里模拟各阶段进度
 */
function simulateAgentProgress(data: Record<string, unknown>): void {
  const phases = [
    { stage: WorkflowStage.DATA_FETCH, agents: ['data_fetcher'], duration: 800 },
    { stage: WorkflowStage.PARALLEL_ANALYSIS, agents: ['technical', 'fundamental', 'sentiment', 'news'], duration: 2000 },
    { stage: WorkflowStage.DEBATE, agents: ['bull', 'bear'], duration: 1500 },
    { stage: WorkflowStage.RISK_ASSESSMENT, agents: ['risk'], duration: 1000 },
    { stage: WorkflowStage.DECISION, agents: ['trader'], duration: 800 },
  ]

  let delay = 0

  phases.forEach((phase) => {
    setTimeout(() => {
      store.setCurrentPhase(phase.stage)

      phase.agents.forEach((agentId, index) => {
        setTimeout(() => {
          store.updateAgentStatus(agentId, AgentStatus.RUNNING, 10)

          store.addLog({
            id: `log_${Date.now()}_${agentId}`,
            timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
            level: LogLevel.INFO,
            source: agentId as Agent['type'],
            sourceName: store.agents.find(a => a.id === agentId)?.name || agentId,
            message: `开始执行分析任务...`,
          })

          const progressSteps = [30, 50, 70, 90, 100]
          progressSteps.forEach((progress, stepIndex) => {
            setTimeout(() => {
              store.updateAgentProgress(agentId, progress)
              if (progress === 100) {
                store.updateAgentStatus(agentId, AgentStatus.COMPLETED, 100)

                store.addLog({
                  id: `log_${Date.now()}_${agentId}_done`,
                  timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
                  level: LogLevel.SUCCESS,
                  source: agentId as Agent['type'],
                  sourceName: store.agents.find(a => a.id === agentId)?.name || agentId,
                  message: `分析完成`,
                })
              }
            }, (stepIndex + 1) * (phase.duration / 5))
          })
        }, index * 200)
      })
    }, delay)

    delay += phase.duration + phase.agents.length * 200
  })

  setTimeout(() => {
    if (data.final_signal) {
      store.setFinalResult({
        stockCode: data.stock_code as string,
        stockName: data.stock_name as string,
        currentPrice: (data.current_price as number) || 0,
        changePercent: 0,
        signal: data.final_signal as Agent['type'] as any,
        score: (data.final_confidence as number) || 50,
        confidence: (data.final_confidence as number) || 50,
        riskLevel: 'medium' as any,
        summary: (data.full_report as string)?.substring(0, 200) || '分析完成',
        agentViews: [],
      })
    }

    store.addLog({
      id: `log_${Date.now()}_complete`,
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
      level: LogLevel.SUCCESS,
      source: 'system',
      sourceName: '系统',
      message: `✅ ${stockCode.value} 分析完成！信号: ${data.final_signal || '未知'}`,
    })
  }, delay + 1000)
}

/**
 * 点击智能体卡片
 */
function handleAgentClick(agent: Agent): void {
  selectedAgent.value = selectedAgent.value?.id === agent.id ? null : agent
}

/**
 * 填入示例股票代码
 */
function fillExample(code: string, name: string): void {
  stockCode.value = code
  stockName.value = name
}

const exampleStocks = [
  { code: '600519.SH', name: '贵州茅台' },
  { code: '000858.SZ', name: '五粮液' },
  { code: '000001.SZ', name: '平安银行' },
  { code: '600036.SH', name: '招商银行' },
]
</script>

<template>
  <div class="app-container">
    <!-- 顶部导航栏 -->
    <header class="app-header">
      <div class="header-left">
        <div class="logo">
          <span class="logo-icon">🤖</span>
          <span class="logo-text">AStock<span class="logo-accent">Agents</span></span>
        </div>
        <span class="logo-subtitle">多智能体协同股票分析系统</span>
      </div>

      <div class="header-center">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input
            v-model="stockCode"
            type="text"
            placeholder="输入股票代码 (如 600519.SH)"
            class="search-input"
            @keyup.enter="startAnalysis"
            :disabled="isAnalyzing"
          />
          <input
            v-model="stockName"
            type="text"
            placeholder="股票名称 (可选)"
            class="search-input name-input"
            @keyup.enter="startAnalysis"
            :disabled="isAnalyzing"
          />
          <button
            class="analyze-btn"
            :class="{ active: isAnalyzing }"
            @click="startAnalysis"
            :disabled="isAnalyzing || !stockCode.trim()"
          >
            <span v-if="isAnalyzing" class="btn-loading">⏳</span>
            <span v-else>🚀</span>
            {{ isAnalyzing ? '分析中...' : '开始分析' }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="example-tags">
          <button
            v-for="stock in exampleStocks"
            :key="stock.code"
            class="example-tag"
            @click="fillExample(stock.code, stock.name)"
            :disabled="isAnalyzing"
          >
            {{ stock.name }}
          </button>
        </div>
      </div>
    </header>

    <!-- 总进度条 -->
    <div v-if="isAnalyzing" class="global-progress">
      <div class="progress-info">
        <span class="progress-label">总体进度</span>
        <span class="progress-value">{{ overallProgress }}%</span>
      </div>
      <div class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: `${overallProgress}%` }"
        ></div>
      </div>
    </div>

    <!-- 主内容区 -->
    <main class="app-main">
      <!-- 3D 场景区域 -->
      <section class="scene-section" v-if="show3D">
        <AgentScene :agents="store.agents" />
        <button class="toggle-3d-btn" @click="show3D = false">收起3D</button>
      </section>
      <section v-else class="scene-collapsed">
        <button class="toggle-3d-btn" @click="show3D = true">展开3D场景</button>
      </section>

      <!-- 工作流进度 -->
      <section class="workflow-section">
        <WorkflowGraph :agents="store.agents" :current-phase="store.currentPhase" />
      </section>

      <!-- 下方内容区：左侧日志 + 右侧智能体面板 -->
      <div class="content-grid">
        <!-- 左侧：日志控制台 -->
        <div class="left-panel">
          <LogConsole :logs="store.logs" :is-running="isAnalyzing" />
        </div>

        <!-- 右侧：智能体状态面板 -->
        <div class="right-panel">
          <div class="agents-grid">
            <AgentCard
              v-for="agent in store.agents"
              :key="agent.id"
              :agent="agent"
              @click="handleAgentClick"
            />
          </div>

          <!-- 最终决策卡片 -->
          <Transition name="slide">
            <ResultCard
              v-if="store.finalResult"
              :result="store.finalResult"
            />
          </Transition>
        </div>
      </div>

      <!-- 错误提示 -->
      <Transition name="fade">
        <div v-if="analysisError" class="error-banner">
          <span class="error-icon">❌</span>
          <span class="error-text">{{ analysisError }}</span>
          <button class="error-close" @click="analysisError = null">✕</button>
        </div>
      </Transition>
    </main>
  </div>
</template>

<style scoped>
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

/* ===== 顶部导航栏 ===== */
.app-header {
  height: 64px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 24px;
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(12px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-icon {
  font-size: 24px;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.5px;
}

.logo-accent {
  color: #3B82F6;
}

.logo-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-tertiary);
  border-radius: 12px;
  padding: 4px 4px 4px 16px;
  border: 1px solid var(--border-color);
  transition: border-color 0.2s;
}

.search-box:focus-within {
  border-color: var(--border-active);
}

.search-icon {
  font-size: 14px;
  color: var(--text-muted);
}

.search-input {
  background: none;
  border: none;
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  width: 180px;
  padding: 8px 0;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.name-input {
  width: 120px;
  border-left: 1px solid var(--border-color);
  padding-left: 12px;
}

.analyze-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  background: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.analyze-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.4);
}

.analyze-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.analyze-btn.active {
  background: linear-gradient(135deg, #F59E0B 0%, #EAB308 100%);
}

.btn-loading {
  animation: spin 1s linear infinite;
  display: inline-block;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.header-right {
  flex-shrink: 0;
}

.example-tags {
  display: flex;
  gap: 6px;
}

.example-tag {
  padding: 4px 10px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.example-tag:hover:not(:disabled) {
  border-color: #3B82F6;
  color: #3B82F6;
}

.example-tag:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ===== 全局进度条 ===== */
.global-progress {
  padding: 8px 24px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.progress-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.progress-value {
  font-size: 12px;
  color: #3B82F6;
  font-weight: 600;
}

.progress-bar {
  height: 3px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3B82F6, #8B5CF6, #EC4899, #3B82F6);
  background-size: 300% 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
  animation: gradient-shift 3s ease infinite;
}

/* ===== 主内容区 ===== */
.app-main {
  flex: 1;
  padding: 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ===== 3D 场景 ===== */
.scene-section {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.scene-collapsed {
  display: flex;
  justify-content: center;
  padding: 8px;
}

.toggle-3d-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  padding: 6px 12px;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-3d-btn:hover {
  background: rgba(0, 0, 0, 0.7);
  color: var(--text-primary);
}

.scene-collapsed .toggle-3d-btn {
  position: static;
  background: var(--bg-secondary);
}

/* ===== 工作流进度 ===== */
.workflow-section {
  border-radius: 12px;
  overflow: hidden;
}

/* ===== 内容网格 ===== */
.content-grid {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 16px;
  flex: 1;
}

.left-panel {
  min-width: 0;
}

.right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

/* ===== 错误提示 ===== */
.error-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 12px;
}

.error-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.error-text {
  flex: 1;
  color: #EF4444;
  font-size: 13px;
}

.error-close {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  padding: 4px;
}

/* ===== 响应式 ===== */
@media (max-width: 1400px) {
  .agents-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 1024px) {
  .content-grid {
    grid-template-columns: 1fr;
  }

  .agents-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .header-right {
    display: none;
  }
}

@media (max-width: 768px) {
  .app-header {
    padding: 0 12px;
    gap: 12px;
  }

  .logo-subtitle {
    display: none;
  }

  .name-input {
    display: none;
  }

  .search-input {
    width: 120px;
  }

  .agents-grid {
    grid-template-columns: 1fr;
  }

  .app-main {
    padding: 12px;
  }
}
</style>
