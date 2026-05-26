<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAgentStore } from '@/stores/agentStore'
import { AgentStatus, WorkflowStage, LogLevel, Signal, RiskLevel } from '@/types/agent'
import type { Agent, AgentOutput } from '@/types/agent'
import { analyzeStock, getPopularStocks, getAnalysisHistory, type AnalyzeResponse, type PopularStock } from '@/services/api'
import { getSectorRotation, type SectorRotationResult } from '@/services/api'

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
const popularStocks = ref<PopularStock[]>([])
const sectorRotation = ref<SectorRotationResult | null>(null)
const sectorLoading = ref(false)
const analysisHistory = ref<Array<Record<string, unknown>>>([])
const historyLoading = ref(false)

const isAnalyzing = computed(() => store.isRunning)
const overallProgress = computed(() => store.overallProgress)

onMounted(async () => {
  store.initAgents()
  await loadPopularStocks()
})

async function loadPopularStocks() {
  try {
    const res = await getPopularStocks()
    popularStocks.value = res.stocks
  } catch {
    popularStocks.value = [
      { code: '600519.SH', name: '贵州茅台', industry: '白酒' },
      { code: '000858.SZ', name: '五粮液', industry: '白酒' },
      { code: '000001.SZ', name: '平安银行', industry: '银行' },
      { code: '600036.SH', name: '招商银行', industry: '银行' },
    ]
  }
}

/** 信号字符串映射 */
const signalMap: Record<string, Signal> = {
  strong_buy: Signal.STRONG_BUY,
  buy: Signal.BUY,
  hold: Signal.HOLD,
  sell: Signal.SELL,
  strong_sell: Signal.STRONG_SELL,
}

/** 风险等级映射 */
function mapRiskLevel(riskData: Record<string, unknown> | null): RiskLevel {
  if (!riskData) return RiskLevel.MEDIUM
  const level = riskData.risk_level as string || riskData.level as string || 'medium'
  if (level.includes('低') || level === 'low') return RiskLevel.LOW
  if (level.includes('高') || level === 'high') return RiskLevel.HIGH
  if (level.includes('极') || level === 'extreme') return RiskLevel.EXTREME
  return RiskLevel.MEDIUM
}

/** 从后端分析结果提取智能体输出 */
function extractAgentOutput(_key: string, data: Record<string, unknown> | null): AgentOutput | null {
  if (!data) return null
  const summary = (data.summary as string) || (data.analysis as string) || JSON.stringify(data).substring(0, 200)
  const metrics: Record<string, number | string> = {}

  const metricKeys = ['signal', 'confidence', 'score', 'recommendation', 'trend', 'pe_ratio', 'pb_ratio', 'sentiment_score']
  for (const mk of metricKeys) {
    if (data[mk] !== undefined && data[mk] !== null) {
      const val = data[mk]
      metrics[mk] = typeof val === 'object' ? JSON.stringify(val) : String(val)
    }
  }

  const signal = data.signal ? signalMap[data.signal as string] : undefined
  const confidence = typeof data.confidence === 'number' ? data.confidence : undefined

  return { summary, keyMetrics: metrics, signal, confidence }
}

/**
 * 启动股票分析 - 调用后端 API
 */
async function startAnalysis(): Promise<void> {
  if (!stockCode.value.trim()) return
  if (store.isRunning) return

  analysisError.value = null
  store.reset()
  store.isRunning = true

  addSystemLog(`开始分析 ${stockCode.value}...`)

  const progressController = startProgressSimulation()

  try {
    const response = await analyzeStock({
      stock_code: stockCode.value.trim(),
      stock_name: stockName.value.trim() || undefined,
    })

    progressController.stop()
    completeAllAgents()
    updateAgentOutputs(response)
    setFinalResultFromResponse(response)

    addSystemLog(`${response.stock_name} 分析完成，信号: ${response.final_signal || '未知'}`)

    // 自动加载该股票的分析历史
    loadAnalysisHistory(response.stock_code)
  } catch (err) {
    progressController.stop()
    const errorMessage = err instanceof Error ? err.message : '未知错误'
    analysisError.value = errorMessage
    store.isRunning = false
    addSystemLog(`分析失败: ${errorMessage}`, LogLevel.ERROR)

    store.agents.forEach((agent) => {
      if (agent.status === AgentStatus.RUNNING || agent.status === AgentStatus.INITIALIZING) {
        store.updateAgentStatus(agent.id, AgentStatus.FAILED, agent.progress)
      }
    })
  }
}

/**
 * 进度模拟控制器
 * 后端同步执行，前端模拟各阶段进度
 */
function startProgressSimulation(): { stop: () => void } {
  let stopped = false

  const phases = [
    { stage: WorkflowStage.DATA_FETCH, agents: ['data_fetcher'], duration: 1500 },
    { stage: WorkflowStage.PARALLEL_ANALYSIS, agents: ['technical', 'fundamental', 'sentiment', 'news', 'capital_flow'], duration: 3000 },
    { stage: WorkflowStage.DEBATE, agents: ['bull', 'bear'], duration: 2000 },
    { stage: WorkflowStage.RISK_ASSESSMENT, agents: ['risk'], duration: 1500 },
    { stage: WorkflowStage.DECISION, agents: ['trader'], duration: 1000 },
  ]

  let delay = 0

  phases.forEach((phase) => {
    setTimeout(() => {
      if (stopped) return
      store.setCurrentPhase(phase.stage)

      phase.agents.forEach((agentId, index) => {
        setTimeout(() => {
          if (stopped) return
          store.updateAgentStatus(agentId, AgentStatus.RUNNING, 10)
          store.updateAgentProgress(agentId, 10, '正在分析...')

          addAgentLog(agentId, '开始执行分析任务...')

          const progressInterval = setInterval(() => {
            if (stopped) { clearInterval(progressInterval); return }
            const agent = store.agents.find(a => a.id === agentId)
            if (!agent || agent.status !== AgentStatus.RUNNING) { clearInterval(progressInterval); return }
            const newProgress = Math.min(agent.progress + Math.random() * 15, 90)
            store.updateAgentProgress(agentId, newProgress)
          }, 300)

          setTimeout(() => clearInterval(progressInterval), phase.duration + 2000)
        }, index * 200)
      })
    }, delay)

    delay += phase.duration + phase.agents.length * 200
  })

  return {
    stop: () => { stopped = true },
  }
}

/** 将所有智能体标记为完成 */
function completeAllAgents(): void {
  store.agents.forEach((agent) => {
    if (agent.status !== AgentStatus.COMPLETED && agent.status !== AgentStatus.FAILED) {
      store.updateAgentStatus(agent.id, AgentStatus.COMPLETED, 100)
      store.updateAgentProgress(agent.id, 100, '分析完成')
    }
  })
  store.setCurrentPhase(WorkflowStage.DECISION)
}

/** 从后端响应更新各智能体输出 */
function updateAgentOutputs(response: AnalyzeResponse): void {
  const outputMap: Record<string, Record<string, unknown> | null> = {
    data_fetcher: null,
    technical: response.technical_analysis,
    fundamental: response.fundamental_analysis,
    sentiment: response.sentiment_analysis,
    news: response.news_analysis,
    capital_flow: null, // 资金流向通过独立API获取
    bull: response.debate,
    bear: response.debate,
    risk: response.risk_assessment,
    trader: response.trade_proposal,
  }

  for (const [agentId, data] of Object.entries(outputMap)) {
    const output = extractAgentOutput(agentId, data)
    if (output) {
      store.setAgentOutput(agentId, output)
    }
  }
}

/** 从后端响应设置最终结果 */
function setFinalResultFromResponse(response: AnalyzeResponse): void {
  const signal = signalMap[response.final_signal || 'hold'] || Signal.HOLD
  const confidence = response.final_confidence || 50
  const riskLevel = mapRiskLevel(response.risk_assessment)

  const agentViews: AgentOutput[] = []
  const viewMap: Array<[string, Record<string, unknown> | null]> = [
    ['technical', response.technical_analysis],
    ['fundamental', response.fundamental_analysis],
    ['sentiment', response.sentiment_analysis],
    ['news', response.news_analysis],
  ]
  for (const [key, data] of viewMap) {
    const output = extractAgentOutput(key, data)
    if (output) agentViews.push(output)
  }

  store.setFinalResult({
    stockCode: response.stock_code,
    stockName: response.stock_name,
    currentPrice: response.current_price || 0,
    changePercent: 0,
    signal,
    score: confidence,
    confidence,
    riskLevel,
    summary: response.full_report ? response.full_report.substring(0, 300) : '分析完成',
    agentViews,
  })
}

/** 添加系统日志 */
function addSystemLog(message: string, level: LogLevel = LogLevel.INFO): void {
  store.addLog({
    id: `log_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
    timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
    level,
    source: 'system',
    sourceName: '系统',
    message,
  })
}

/** 添加智能体日志 */
function addAgentLog(agentId: string, message: string): void {
  const agent = store.agents.find(a => a.id === agentId)
  store.addLog({
    id: `log_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
    timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
    level: LogLevel.INFO,
    source: agentId as Agent['type'],
    sourceName: agent?.name || agentId,
    message,
  })
}

function handleAgentClick(agent: Agent): void {
  selectedAgent.value = selectedAgent.value?.id === agent.id ? null : agent
}

function fillStock(code: string, name: string): void {
  stockCode.value = code
  stockName.value = name
}

/** 加载行业轮动决策建议 */
async function loadSectorRotation(): Promise<void> {
  sectorLoading.value = true
  try {
    const res = await getSectorRotation()
    sectorRotation.value = res.data
  } catch (e) {
    addSystemLog(`行业轮动数据加载失败: ${e instanceof Error ? e.message : '未知错误'}`, LogLevel.WARNING)
  } finally {
    sectorLoading.value = false
  }
}

/** 加载分析历史记录 */
async function loadAnalysisHistory(stockCode: string): Promise<void> {
  historyLoading.value = true
  try {
    const res = await getAnalysisHistory(stockCode, 10)
    if (res.success && res.data) {
      analysisHistory.value = Array.isArray(res.data) ? res.data : []
    }
  } catch {
    analysisHistory.value = []
  } finally {
    historyLoading.value = false
  }
}

/** 格式化日期 */
function formatDate(dateStr: string | unknown): string {
  if (!dateStr) return '-'
  try {
    const d = new Date(String(dateStr))
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return String(dateStr)
  }
}

/** 信号颜色 */
function signalColor(signal: string | unknown): string {
  const s = String(signal || '').toLowerCase()
  if (s.includes('buy') || s.includes('买入')) return 'var(--color-positive)'
  if (s.includes('sell') || s.includes('卖出')) return 'var(--color-negative)'
  if (s.includes('hold') || s.includes('持有')) return 'var(--color-text-secondary)'
  return 'var(--color-text-muted)'
}
</script>

<template>
  <div class="analysis-view">
    <!-- 顶部搜索栏 -->
    <header class="search-header">
      <div class="search-box">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
        </svg>
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
          class="btn-primary analyze-btn"
          @click="startAnalysis"
          :disabled="isAnalyzing || !stockCode.trim()"
        >
          {{ isAnalyzing ? '分析中...' : '开始分析' }}
        </button>
      </div>

      <div class="popular-stocks">
        <span class="popular-label">热门:</span>
        <button
          v-for="stock in popularStocks"
          :key="stock.code"
          class="popular-tag"
          @click="fillStock(stock.code, stock.name)"
          :disabled="isAnalyzing"
        >
          {{ stock.name }}
        </button>
      </div>
    </header>

    <!-- 总进度条 -->
    <div v-if="isAnalyzing" class="global-progress">
      <div class="progress-info">
        <span class="progress-label">总体进度</span>
        <span class="progress-value">{{ overallProgress }}%</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: `${overallProgress}%` }"></div>
      </div>
    </div>

    <!-- 3D 场景 -->
    <section class="scene-section" v-if="show3D">
      <AgentScene :agents="store.agents" />
      <button class="toggle-3d-btn" @click="show3D = false">收起</button>
    </section>
    <section v-else class="scene-collapsed">
      <button class="toggle-3d-btn" @click="show3D = true">展开场景</button>
    </section>

    <!-- 工作流进度 -->
    <section class="workflow-section">
      <WorkflowGraph :agents="store.agents" :current-phase="store.currentPhase" />
    </section>

    <!-- 下方内容区 -->
    <div class="content-grid">
      <div class="left-panel">
        <LogConsole :logs="store.logs" :is-running="isAnalyzing" />
      </div>
      <div class="right-panel">
        <div class="agents-grid">
          <AgentCard
            v-for="agent in store.agents"
            :key="agent.id"
            :agent="agent"
            @click="handleAgentClick"
          />
        </div>
        <Transition name="slide">
          <ResultCard v-if="store.finalResult" :result="store.finalResult" />
        </Transition>

        <!-- 决策建议面板 -->
        <div v-if="store.finalResult" class="decision-panel">
          <div class="decision-header">
            <h3 class="decision-title">决策建议</h3>
            <button class="btn-secondary btn-sm" @click="loadSectorRotation" :disabled="sectorLoading">
              {{ sectorLoading ? '加载中...' : '获取行业建议' }}
            </button>
          </div>

          <div v-if="sectorRotation" class="decision-content">
            <!-- 经济周期 -->
            <div class="cycle-badge">
              <span class="cycle-label">当前周期</span>
              <span class="cycle-value">{{ sectorRotation.current_cycle }}</span>
            </div>

            <!-- 轮动信号 -->
            <div class="rotation-signal">
              <span class="signal-label">轮动信号</span>
              <span class="signal-text">{{ sectorRotation.rotation_signal }}</span>
            </div>

            <!-- 推荐行业列表 -->
            <div v-if="sectorRotation.recommendations.length" class="recommendation-list">
              <div
                v-for="rec in sectorRotation.recommendations"
                :key="rec.sector_name"
                class="recommendation-item"
              >
                <div class="rec-rank">{{ rec.rank }}</div>
                <div class="rec-info">
                  <div class="rec-name">{{ rec.sector_name }}</div>
                  <div class="rec-reason">{{ rec.reason }}</div>
                  <div class="rec-stocks" v-if="rec.matching_stocks.length">
                    <span class="stock-tag" v-for="code in rec.matching_stocks.slice(0, 3)" :key="code">{{ code }}</span>
                  </div>
                </div>
                <div class="rec-weight">{{ (rec.weight * 100).toFixed(0) }}%</div>
              </div>
            </div>

            <div v-else class="empty-recommendation">暂无推荐行业</div>
          </div>

          <div v-else-if="!sectorLoading" class="decision-empty">
            点击"获取行业建议"查看当前经济周期下的行业配置建议
          </div>
        </div>

        <!-- 分析历史记录面板 -->
        <div v-if="store.finalResult" class="history-panel">
          <div class="history-header">
            <h3 class="history-title">分析历史</h3>
            <span v-if="historyLoading" class="history-loading">加载中...</span>
          </div>

          <div v-if="analysisHistory.length > 0" class="history-list">
            <div
              v-for="(record, idx) in analysisHistory"
              :key="idx"
              class="history-item"
            >
              <div class="history-left">
                <span class="history-time">{{ formatDate(record.created_at || record.timestamp) }}</span>
                <span class="history-signal" :style="{ color: signalColor(record.signal) }">
                  {{ record.signal || '-' }}
                </span>
              </div>
              <div class="history-right">
                <span class="history-confidence">
                  置信度: {{ record.confidence != null ? record.confidence + '%' : '-' }}
                </span>
                <span class="history-price">
                  价格: {{ record.current_price ? '¥' + record.current_price : '-' }}
                </span>
              </div>
            </div>
          </div>

          <div v-else-if="!historyLoading" class="history-empty">
            暂无历史分析记录
          </div>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <Transition name="fade">
      <div v-if="analysisError" class="error-banner">
        <span class="error-text">{{ analysisError }}</span>
        <button class="error-close" @click="analysisError = null">&times;</button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.analysis-view {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 100vh;
}

.search-header {
  background: var(--color-bg-card);
  border-radius: var(--radius);
  padding: 14px 16px;
  border: 1px solid var(--color-border);
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--color-bg-input);
  border-radius: 2px;
  padding: 2px 2px 2px 12px;
  border: 1px solid var(--color-border);
  transition: border-color 0.2s;
}

.search-box:focus-within {
  border-color: var(--color-accent);
}

.search-icon {
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.search-input {
  background: none;
  border: none;
  color: var(--color-text-primary);
  font-size: 14px;
  outline: none;
  width: 180px;
  padding: 8px 0;
}

.search-input::placeholder { color: var(--color-text-muted); }

.name-input {
  width: 120px;
  border-left: 1px solid var(--color-border);
  padding-left: 12px;
}

.analyze-btn {
  flex-shrink: 0;
}

.popular-stocks {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.popular-label { font-size: 12px; color: var(--color-text-muted); }

.popular-tag {
  padding: 3px 10px;
  background: var(--color-bg-hover);
  border: 1px solid var(--color-border);
  border-radius: 2px;
  color: var(--color-text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.popular-tag:hover:not(:disabled) { border-color: var(--color-accent); color: var(--color-accent); }
.popular-tag:disabled { opacity: 0.5; cursor: not-allowed; }

.global-progress { padding: 6px 0; }
.progress-info { display: flex; justify-content: space-between; margin-bottom: 4px; }
.progress-label { font-size: 12px; color: var(--color-text-secondary); }
.progress-value { font-size: 12px; color: var(--color-accent); font-weight: 600; }
.progress-bar { height: 2px; background: var(--color-bg-hover); border-radius: 1px; overflow: hidden; }
.progress-fill {
  height: 100%;
  background: var(--color-accent);
  border-radius: 1px;
  transition: width 0.5s ease;
}

.scene-section { position: relative; border-radius: var(--radius); overflow: hidden; border: 1px solid var(--color-border); }
.scene-collapsed { display: flex; justify-content: center; padding: 6px; }
.toggle-3d-btn {
  position: absolute; top: 8px; right: 8px; z-index: 10;
  padding: 4px 10px; background: rgba(0,0,0,0.6); backdrop-filter: blur(8px);
  border: 1px solid var(--color-border); border-radius: 2px;
  color: var(--color-text-secondary); font-size: 12px; cursor: pointer; transition: all 0.15s;
}
.toggle-3d-btn:hover { background: rgba(0,0,0,0.8); color: var(--color-text-primary); }
.scene-collapsed .toggle-3d-btn { position: static; background: var(--color-bg-card); }

.workflow-section { border-radius: var(--radius); overflow: hidden; }

.content-grid { display: grid; grid-template-columns: 1fr 1.5fr; gap: 12px; flex: 1; }
.left-panel { min-width: 0; }
.right-panel { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.agents-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }

.error-banner {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; background: rgba(245, 34, 45, 0.08);
  border: 1px solid rgba(245, 34, 45, 0.2); border-radius: var(--radius);
}
.error-text { flex: 1; color: var(--color-negative); font-size: 13px; }
.error-close { background: none; border: none; color: var(--color-text-muted); cursor: pointer; font-size: 16px; padding: 2px 6px; }

/* 决策建议面板 */
.decision-panel {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 16px;
}

.decision-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.decision-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.btn-sm {
  padding: 4px 12px;
  font-size: 12px;
}

.decision-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cycle-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(37, 99, 235, 0.08);
  border: 1px solid rgba(37, 99, 235, 0.2);
  border-radius: var(--radius);
}

.cycle-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.cycle-value {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-accent);
}

.rotation-signal {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  background: var(--color-bg-primary);
  border-radius: var(--radius);
}

.signal-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.signal-text {
  font-size: 13px;
  color: var(--color-text-primary);
  line-height: 1.5;
}

.recommendation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recommendation-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.rec-rank {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-accent);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.rec-info {
  flex: 1;
  min-width: 0;
}

.rec-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 2px;
}

.rec-reason {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.4;
  margin-bottom: 4px;
}

.rec-stocks {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.stock-tag {
  padding: 1px 6px;
  background: var(--color-bg-hover);
  border: 1px solid var(--color-border);
  border-radius: 2px;
  font-size: 11px;
  color: var(--color-text-muted);
}

.rec-weight {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-accent);
  flex-shrink: 0;
}

.empty-recommendation,
.decision-empty {
  text-align: center;
  color: var(--color-text-muted);
  font-size: 13px;
  padding: 16px 0;
}

/* 分析历史面板 */
.history-panel {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 16px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.history-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.history-loading {
  font-size: 12px;
  color: var(--color-text-muted);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.history-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.history-time {
  font-size: 12px;
  color: var(--color-text-muted);
}

.history-signal {
  font-size: 13px;
  font-weight: 600;
}

.history-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.history-confidence,
.history-price {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.history-empty {
  text-align: center;
  color: var(--color-text-muted);
  font-size: 13px;
  padding: 16px 0;
}

@media (max-width: 1400px) { .agents-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 1024px) {
  .content-grid { grid-template-columns: 1fr; }
  .agents-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .analysis-view { padding: 10px; }
  .name-input { display: none; }
  .search-input { width: 120px; }
  .agents-grid { grid-template-columns: 1fr; }
}
</style>
