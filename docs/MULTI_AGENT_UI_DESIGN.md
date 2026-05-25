# AStockAgents 多智能体可视化界面设计方案

## 一、项目概述

### 1.1 设计目标

让用户直观感受到8个AI智能体在协同工作分析股票，通过可视化界面展示：
- 智能体的运行状态（空闲/运行中/已完成/失败）
- 智能体之间的数据流动
- 每个智能体的分析进度和输出
- 实时日志输出
- 最终决策结果的生成过程

### 1.2 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | Vue 3 + TypeScript | 组件化开发，响应式 |
| UI组件 | TailwindCSS + 自定义组件 | 现代化样式 |
| 3D渲染 | Three.js + React Three Fiber | 3D智能体展示 |
| 状态管理 | Pinia | 全局状态管理 |
| 实时通信 | WebSocket / SSE | 实时推送 |
| 后端接口 | FastAPI | 分析服务API |
| 构建工具 | Vite | 快速构建 |

### 1.3 目录结构

```
astock-agents-web/
├── src/
│   ├── components/
│   │   ├── agents/                    # 智能体相关组件
│   │   │   ├── AgentCard.vue          # 智能体卡片
│   │   │   ├── AgentStatusBadge.vue   # 状态徽章
│   │   │   ├── AgentProgress.vue      # 进度条
│   │   │   └── AgentOutput.vue        # 输出展示
│   │   ├── workflow/                  # 工作流可视化
│   │   │   ├── WorkflowGraph.vue      # 2D流程图
│   │   │   ├── WorkflowNode.vue       # 流程节点
│   │   │   └── WorkflowEdge.vue       # 流程连线
│   │   ├── visualization/             # 3D可视化
│   │   │   ├── AgentScene.vue         # 3D场景
│   │   │   ├── AgentOrb.vue           # 智能体球体
│   │   │   └── DataFlow.vue           # 数据流粒子
│   │   ├── dashboard/                 # 仪表盘
│   │   │   ├── StatusPanel.vue        # 状态面板
│   │   │   ├── LogConsole.vue         # 日志控制台
│   │   │   └── ResultCard.vue         # 结果卡片
│   │   └── common/                    # 通用组件
│   │       ├── LoadingSpinner.vue
│   │       └── ProgressRing.vue
│   ├── composables/                   # 组合式函数
│   │   ├── useAgentState.ts          # 智能体状态管理
│   │   ├── useWorkflow.ts            # 工作流控制
│   │   └── useWebSocket.ts           # WebSocket连接
│   ├── stores/
│   │   ├── agentStore.ts            # 智能体状态store
│   │   └── workflowStore.ts          # 工作流store
│   ├── types/
│   │   └── agent.ts                  # 类型定义
│   ├── utils/
│   │   └── animations.ts             # 动画工具
│   ├── App.vue
│   └── main.ts
├── public/
│   └── favicon.ico
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

---

## 二、数据结构设计

### 2.1 TypeScript 类型定义

```typescript
// src/types/agent.ts

// ===== 枚举定义 =====

/** 智能体状态 */
export enum AgentStatus {
  IDLE = 'idle',           // 空闲 🟢
  INITIALIZING = 'init',   // 初始化 🔵
  RUNNING = 'running',     // 运行中 🔄
  WAITING = 'waiting',     // 等待中 ⏳
  COMPLETED = 'completed',  // 已完成 ✅
  FAILED = 'failed',       // 失败 ❌
}

/** 智能体类型 */
export enum AgentType {
  DATA_FETCHER = 'data_fetcher',     // 数据获取
  TECHNICAL_ANALYST = 'technical',   // 技术分析师
  FUNDAMENTAL_ANALYST = 'fundamental', // 基本面分析师
  SENTIMENT_ANALYST = 'sentiment',   // 情绪分析师
  NEWS_ANALYST = 'news',            // 新闻分析师
  BULL_RESEARCHER = 'bull',          // 多头研究员
  BEAR_RESEARCHER = 'bear',          // 空头研究员
  RISK_MANAGER = 'risk',            // 风险管理器
  TRADER = 'trader',                // 交易员
}

/** 日志级别 */
export enum LogLevel {
  DEBUG = 'debug',
  INFO = 'info',
  SUCCESS = 'success',
  WARNING = 'warning',
  ERROR = 'error',
}

/** 工作流阶段 */
export enum WorkflowStage {
  DATA_FETCH = 'data_fetch',       // 数据获取
  PARALLEL_ANALYSIS = 'parallel', // 并行分析
  DEBATE = 'debate',              // 多空辩论
  RISK_ASSESSMENT = 'risk',        // 风险评估
  DECISION = 'decision',           // 最终决策
}

// ===== 接口定义 =====

/** 智能体定义 */
export interface Agent {
  id: string;                      // 唯一标识
  type: AgentType;                 // 类型
  name: string;                    // 名称
  icon: string;                    // 图标emoji
  description: string;             // 描述
  color: string;                   // 主题色
  status: AgentStatus;             // 当前状态
  progress: number;                // 进度 0-100
  currentTask: string;             // 当前任务描述
  startTime: string | null;        // 开始时间
  endTime: string | null;          // 结束时间
  output: AgentOutput | null;      // 分析输出
  dependencies: AgentType[];       // 依赖的智能体
  dependents: AgentType[];         // 依赖此智能体的
}

/** 智能体输出 */
export interface AgentOutput {
  summary: string;                 // 输出摘要
  keyMetrics: Record<string, number | string>; // 关键指标
  signal?: Signal;                 // 交易信号
  confidence?: number;             // 置信度
  details?: Record<string, any>;    // 详细数据
}

/** 交易信号 */
export enum Signal {
  STRONG_BUY = 'strong_buy',       // 强烈买入
  BUY = 'buy',                     // 买入
  HOLD = 'hold',                   // 持有
  SELL = 'sell',                   // 卖出
  STRONG_SELL = 'strong_sell',     // 强烈卖出
}

/** 日志条目 */
export interface LogEntry {
  id: string;                      // 唯一ID
  timestamp: string;               // 时间戳 HH:mm:ss
  level: LogLevel;                 // 日志级别
  source: AgentType | 'system';    // 来源
  sourceName: string;              // 来源名称
  message: string;                 // 日志内容
  details?: Record<string, any>;    // 详细信息
}

/** 工作流节点 */
export interface WorkflowNode {
  id: string;
  agentId: string;
  x: number;                       // x坐标
  y: number;                       // y坐标
  status: AgentStatus;
  connected: boolean;              // 是否连接
}

/** 工作流边（连线） */
export interface WorkflowEdge {
  id: string;
  source: string;                  // 源节点ID
  target: string;                  // 目标节点ID
  active: boolean;                 // 是否激活
  animated: boolean;               // 是否动画
}

/** 工作流阶段 */
export interface WorkflowPhase {
  stage: WorkflowStage;
  name: string;
  agents: AgentType[];
  status: 'pending' | 'active' | 'completed';
}

/** 分析任务 */
export interface AnalysisTask {
  id: string;
  stockCode: string;
  stockName: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  startTime: string;
  endTime?: string;
  agents: Agent[];
  phases: WorkflowPhase[];
  logs: LogEntry[];
  finalResult?: FinalResult;
}

/** 最终结果 */
export interface FinalResult {
  stockCode: string;
  stockName: string;
  currentPrice: number;
  changePercent: number;
  signal: Signal;
  score: number;                   // 综合评分 0-100
  confidence: number;              // 置信度
  riskLevel: RiskLevel;
  summary: string;
  agentViews: AgentOutput[];        // 各智能体观点
}

/** 风险等级 */
export enum RiskLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  EXTREME = 'extreme',
}

/** 实时消息类型 */
export type RealtimeMessage =
  | { type: 'agent_status_change'; payload: { agentId: string; status: AgentStatus; progress: number } }
  | { type: 'agent_progress'; payload: { agentId: string; progress: number; message: string } }
  | { type: 'agent_output'; payload: { agentId: string; output: AgentOutput } }
  | { type: 'log'; payload: LogEntry }
  | { type: 'phase_change'; payload: { phase: WorkflowStage; status: string } }
  | { type: 'task_complete'; payload: FinalResult }
  | { type: 'error'; payload: { message: string } };
```

---

## 三、界面布局设计

### 3.1 整体布局

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  HEADER: Logo + 股票搜索框 + 分析按钮                                        │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    3D 智能体协作场景 (可交互)                            │   │
│  │         [点击球体查看详情] [拖拽旋转视角] [滚轮缩放]                      │   │
│  │                                                                              │   │
│  │              ● ─── ● ─── ● ─── ● ─── ● ─── ● ─── ● ─── ●              │   │
│  │              │   │   │   │   │   │   │   │   │   │                      │   │
│  │            [数据] [技术] [基本面] [情绪] [新闻] [多头] [空头] [风险]      │   │
│  │                                                                              │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                │
│  ┌───────────────────────┐  ┌─────────────────────────────────────────────┐    │
│  │   工作流阶段进度条      │  │                                             │    │
│  │  [1.数据]→[2.分析]→...│  │          智能体状态面板 (2x4网格)           │    │
│  └───────────────────────┘  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │    │
│                              │  │ 技术 │ │ 基本 │ │ 情绪 │ │ 新闻 │       │    │
│  ┌───────────────────────┐  │  └──────┘ └──────┘ └──────┘ └──────┘       │    │
│  │                       │  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │    │
│  │    日志控制台          │  │  │ 多头 │ │ 空头 │ │ 风险 │ │ 交易 │       │    │
│  │    (滚动自动跟新)      │  │  └──────┘ └──────┘ └──────┘ └──────┘       │    │
│  │                       │  └─────────────────────────────────────────────┘    │
│  │                       │                                                      │
│  └───────────────────────┘  ┌─────────────────────────────────────────────┐    │
│                              │                  最终决策卡片                    │    │
│                              │  信号: 买入 ⬆️  评分: 68  置信度: 72%        │    │
│                              └─────────────────────────────────────────────┘    │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 响应式断点

```css
/* 响应式布局 */
@media (max-width: 1400px) {
  /* 大屏：3D场景占满，内容分两列 */
}

@media (max-width: 1024px) {
  /* 平板：3D场景缩小，智能体面板变2x2 */
}

@media (max-width: 768px) {
  /* 手机：垂直堆叠，3D场景可折叠 */
}
```

### 3.3 颜色系统

```typescript
// src/styles/colors.ts

export const colors = {
  // 状态颜色
  status: {
    idle: '#10B981',        // 空闲 - 绿色
    initializing: '#3B82F6', // 初始化 - 蓝色
    running: '#F59E0B',     // 运行中 - 橙色
    waiting: '#8B5CF6',     // 等待中 - 紫色
    completed: '#22C55E',    // 已完成 - 亮绿色
    failed: '#EF4444',      // 失败 - 红色
  },
  
  // 智能体主题色
  agents: {
    data_fetcher: '#06B6D4',    // 青色
    technical: '#3B82F6',       // 蓝色
    fundamental: '#8B5CF6',     // 紫色
    sentiment: '#EC4899',       // 粉色
    news: '#F97316',           // 橙色
    bull: '#22C55E',           // 绿色
    bear: '#EF4444',           // 红色
    risk: '#EAB308',           // 黄色
    trader: '#6366F1',         // 靛蓝
  },
  
  // 背景
  background: {
    primary: '#0F172A',        // 主背景 - 深蓝黑
    secondary: '#1E293B',      // 次背景
    card: '#334155',           // 卡片背景
    hover: '#475569',          // 悬停
  },
  
  // 文字
  text: {
    primary: '#F8FAFC',       // 主文字 - 白色
    secondary: '#94A3B8',      // 次文字 - 灰色
    muted: '#64748B',         // 弱文字
  },
  
  // 渐变
  gradient: {
    primary: 'linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%)',
    success: 'linear-gradient(135deg, #22C55E 0%, #10B981 100%)',
    warning: 'linear-gradient(135deg, #F59E0B 0%, #EAB308 100%)',
    danger: 'linear-gradient(135deg, #EF4444 0%, #DC2626 100%)',
  },
};
```

---

## 四、组件详细设计

### 4.1 智能体卡片组件 (AgentCard.vue)

```vue
<template>
  <div 
    class="agent-card"
    :class="[`status-${agent.status}`, { 'is-active': isActive }]"
    @click="handleCardClick"
  >
    <!-- 头部：图标 + 名称 + 状态 -->
    <div class="agent-header">
      <div class="agent-icon" :style="{ background: agentColor }">
        {{ agent.icon }}
      </div>
      <div class="agent-info">
        <div class="agent-name">{{ agent.name }}</div>
        <AgentStatusBadge :status="agent.status" />
      </div>
    </div>
    
    <!-- 进度条 -->
    <div class="agent-progress" v-if="agent.status !== 'idle'">
      <div class="progress-bar">
        <div 
          class="progress-fill" 
          :style="{ width: `${agent.progress}%`, background: agentColor }"
        ></div>
      </div>
      <span class="progress-text">{{ agent.progress }}%</span>
    </div>
    
    <!-- 当前任务 -->
    <div class="agent-task" v-if="agent.currentTask">
      <span class="task-icon">📌</span>
      <span class="task-text">{{ agent.currentTask }}</span>
    </div>
    
    <!-- 输出摘要 -->
    <div class="agent-output" v-if="agent.output && agent.status === 'completed'">
      <div class="output-summary">{{ agent.output.summary }}</div>
      <div class="output-metrics" v-if="agent.output.keyMetrics">
        <span 
          v-for="(value, key) in agent.output.keyMetrics" 
          :key="key"
          class="metric-tag"
        >
          {{ key }}: {{ value }}
        </span>
      </div>
    </div>
    
    <!-- 运行动画 -->
    <div class="running-animation" v-if="agent.status === 'running'">
      <div class="pulse-ring"></div>
      <div class="pulse-ring delay-1"></div>
      <div class="pulse-ring delay-2"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { Agent, AgentStatus, AgentType } from '@/types/agent';
import AgentStatusBadge from './AgentStatusBadge.vue';

const props = defineProps<{
  agent: Agent;
}>();

const emit = defineEmits<{
  (e: 'click', agent: Agent): void;
}>();

const agentColor = computed(() => {
  const colorMap: Record<AgentType, string> = {
    [AgentType.DATA_FETCHER]: '#06B6D4',
    [AgentType.TECHNICAL_ANALYST]: '#3B82F6',
    [AgentType.FUNDAMENTAL_ANALYST]: '#8B5CF6',
    [AgentType.SENTIMENT_ANALYST]: '#EC4899',
    [AgentType.NEWS_ANALYST]: '#F97316',
    [AgentType.BULL_RESEARCHER]: '#22C55E',
    [AgentType.BEAR_RESEARCHER]: '#EF4444',
    [AgentType.RISK_MANAGER]: '#EAB308',
    [AgentType.TRADER]: '#6366F1',
  };
  return colorMap[props.agent.type] || '#64748B';
});

const isActive = computed(() => 
  props.agent.status === 'running' || props.agent.status === 'initializing'
);

const handleCardClick = () => {
  emit('click', props.agent);
};
</script>

<style scoped>
.agent-card {
  background: v-bind('background.secondary');
  border-radius: 16px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid transparent;
  position: relative;
  overflow: hidden;
}

.agent-card:hover {
  transform: translateY(-2px);
  border-color: v-bind('agentColor');
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.agent-card.status-running {
  border-color: v-bind('agentColor');
  box-shadow: 0 0 20px v-bind('agentColor + "40"');
}

.agent-card.status-completed {
  border-color: #22C55E;
}

.agent-card.status-failed {
  border-color: #EF4444;
}

/* 脉冲动画 */
.running-animation {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.pulse-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 16px;
  border: 2px solid v-bind('agentColor');
  animation: pulse 2s ease-out infinite;
  opacity: 0;
}

.pulse-ring.delay-1 { animation-delay: 0.5s; }
.pulse-ring.delay-2 { animation-delay: 1s; }

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 0.6;
  }
  100% {
    transform: scale(1.3);
    opacity: 0;
  }
}

/* 进度条 */
.progress-bar {
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}
</style>
```

### 4.2 状态徽章组件 (AgentStatusBadge.vue)

```vue
<template>
  <span class="status-badge" :class="`status-${status}`">
    <span class="status-dot"></span>
    <span class="status-text">{{ statusText }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { AgentStatus } from '@/types/agent';

const props = defineProps<{
  status: AgentStatus;
}>();

const statusText = computed(() => {
  const map: Record<AgentStatus, string> = {
    [AgentStatus.IDLE]: '空闲',
    [AgentStatus.INITIALIZING]: '初始化',
    [AgentStatus.RUNNING]: '运行中',
    [AgentStatus.WAITING]: '等待中',
    [AgentStatus.COMPLETED]: '已完成',
    [AgentStatus.FAILED]: '失败',
  };
  return map[props.status] || props.status;
});

const statusColor = computed(() => {
  const map: Record<AgentStatus, string> = {
    [AgentStatus.IDLE]: '#10B981',
    [AgentStatus.INITIALIZING]: '#3B82F6',
    [AgentStatus.RUNNING]: '#F59E0B',
    [AgentStatus.WAITING]: '#8B5CF6',
    [AgentStatus.COMPLETED]: '#22C55E',
    [AgentStatus.FAILED]: '#EF4444',
  };
  return map[props.status] || '#64748B';
});
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.1);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.status-running .status-dot {
  animation: blink 1s ease-in-out infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
</style>
```

### 4.3 日志控制台组件 (LogConsole.vue)

```vue
<template>
  <div class="log-console" ref="consoleRef">
    <div class="console-header">
      <span class="console-title">📝 分析日志</span>
      <div class="console-actions">
        <button @click="clearLogs" class="btn-icon">🗑️</button>
        <button @click="toggleAutoScroll" class="btn-icon" :class="{ active: autoScroll }">
          {{ autoScroll ? '🔒' : '🔓' }}
        </button>
      </div>
    </div>
    
    <div class="console-body">
      <TransitionGroup name="log">
        <div 
          v-for="log in visibleLogs" 
          :key="log.id"
          class="log-entry"
          :class="`level-${log.level}`"
        >
          <span class="log-time">{{ log.timestamp }}</span>
          <span class="log-source" :style="{ color: getSourceColor(log.source) }">
            [{{ log.sourceName }}]
          </span>
          <span class="log-icon">{{ getLogIcon(log.level) }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </TransitionGroup>
      
      <div v-if="isRunning" class="typing-indicator">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue';
import type { LogEntry, AgentType, LogLevel } from '@/types/agent';

const props = defineProps<{
  logs: LogEntry[];
  maxLogs?: number;
  isRunning?: boolean;
}>();

const consoleRef = ref<HTMLElement>();
const autoScroll = ref(true);

const visibleLogs = computed(() => {
  if (props.maxLogs) {
    return props.logs.slice(-props.maxLogs);
  }
  return props.logs;
});

watch(visibleLogs, async () => {
  if (autoScroll.value) {
    await nextTick();
    scrollToBottom();
  }
});

const scrollToBottom = () => {
  if (consoleRef.value) {
    consoleRef.value.scrollTop = consoleRef.value.scrollHeight;
  }
};

const clearLogs = () => {
  // 触发清空事件
};

const toggleAutoScroll = () => {
  autoScroll.value = !autoScroll.value;
};

const getSourceColor = (source: AgentType | 'system'): string => {
  const colors: Record<string, string> = {
    data_fetcher: '#06B6D4',
    technical: '#3B82F6',
    fundamental: '#8B5CF6',
    sentiment: '#EC4899',
    news: '#F97316',
    bull: '#22C55E',
    bear: '#EF4444',
    risk: '#EAB308',
    trader: '#6366F1',
    system: '#94A3B8',
  };
  return colors[source] || '#94A3B8';
};

const getLogIcon = (level: LogLevel): string => {
  const icons: Record<LogLevel, string> = {
    debug: '🔍',
    info: 'ℹ️',
    success: '✅',
    warning: '⚠️',
    error: '❌',
  };
  return icons[level] || 'ℹ️';
};
</script>

<style scoped>
.log-console {
  background: #0D1117;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.console-body {
  max-height: 300px;
  overflow-y: auto;
  padding: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.log-entry {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.log-entry:last-child {
  border-bottom: none;
}

.log-time {
  color: #64748B;
  flex-shrink: 0;
}

.log-source {
  flex-shrink: 0;
  font-weight: 500;
}

.log-icon {
  flex-shrink: 0;
}

.log-message {
  color: #E2E8F0;
  word-break: break-word;
}

/* 日志级别颜色 */
.level-success .log-message { color: #22C55E; }
.level-warning .log-message { color: #F59E0B; }
.level-error .log-message { color: #EF4444; }

/* 过渡动画 */
.log-enter-active {
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.typing-indicator .dot {
  width: 6px;
  height: 6px;
  background: #64748B;
  border-radius: 50%;
  animation: bounce 1.4s ease-in-out infinite;
}

.typing-indicator .dot:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}
</style>
```

### 4.4 3D智能体场景组件 (AgentScene.vue)

```vue
<template>
  <div class="agent-scene" ref="containerRef">
    <canvas ref="canvasRef"></canvas>
    
    <!-- 交互提示 -->
    <div class="scene-hints">
      <span>🖱️ 拖拽旋转</span>
      <span>🔍 滚轮缩放</span>
      <span>👆 点击智能体查看详情</span>
    </div>
    
    <!-- 选中的智能体信息 -->
    <Transition name="fade">
      <div v-if="selectedAgent" class="agent-detail-panel">
        <div class="detail-header">
          <span class="detail-icon">{{ selectedAgent.icon }}</span>
          <span class="detail-name">{{ selectedAgent.name }}</span>
          <button @click="selectedAgent = null" class="close-btn">✕</button>
        </div>
        <div class="detail-body">
          <div class="detail-status">
            <span class="label">状态:</span>
            <AgentStatusBadge :status="selectedAgent.status" />
          </div>
          <div class="detail-progress">
            <span class="label">进度:</span>
            <div class="progress-ring">
              <svg viewBox="0 0 100 100">
                <circle
                  class="progress-bg"
                  cx="50" cy="50" r="45"
                  fill="none"
                  stroke="rgba(255,255,255,0.1)"
                  stroke-width="8"
                />
                <circle
                  class="progress-fill"
                  cx="50" cy="50" r="45"
                  fill="none"
                  :stroke="getAgentColor(selectedAgent.type)"
                  stroke-width="8"
                  stroke-linecap="round"
                  :stroke-dasharray="283"
                  :stroke-dashoffset="283 - (283 * selectedAgent.progress / 100)"
                  transform="rotate(-90 50 50)"
                />
              </svg>
              <span class="progress-value">{{ selectedAgent.progress }}%</span>
            </div>
          </div>
          <div v-if="selectedAgent.currentTask" class="detail-task">
            <span class="label">当前任务:</span>
            <span>{{ selectedAgent.currentTask }}</span>
          </div>
          <div v-if="selectedAgent.output" class="detail-output">
            <span class="label">输出摘要:</span>
            <p>{{ selectedAgent.output.summary }}</p>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { Agent, AgentType } from '@/types/agent';

const props = defineProps<{
  agents: Agent[];
}>();

const containerRef = ref<HTMLElement>();
const canvasRef = ref<HTMLCanvasElement>();
const selectedAgent = ref<Agent | null>(null);

let scene: THREE.Scene;
let camera: THREE.PerspectiveCamera;
let renderer: THREE.WebGLRenderer;
let controls: OrbitControls;
let agentMeshes: Map<string, THREE.Mesh> = new Map();
let animationFrameId: number;

// 初始化3D场景
const initScene = () => {
  if (!canvasRef.value || !containerRef.value) return;

  // 场景
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0F172A);
  
  // 相机
  const aspect = containerRef.value.clientWidth / containerRef.value.clientHeight;
  camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 1000);
  camera.position.set(0, 5, 15);
  
  // 渲染器
  renderer = new THREE.WebGLRenderer({ 
    canvas: canvasRef.value,
    antialias: true,
    alpha: true,
  });
  renderer.setSize(containerRef.value.clientWidth, containerRef.value.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  
  // 控制器
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.minDistance = 8;
  controls.maxDistance = 30;
  
  // 光照
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
  scene.add(ambientLight);
  
  const pointLight = new THREE.PointLight(0xffffff, 1);
  pointLight.position.set(10, 10, 10);
  scene.add(pointLight);
  
  // 添加智能体球体
  createAgentOrbs();
  
  // 添加连接线
  createConnections();
  
  // 添加粒子背景
  createParticles();
  
  // 动画循环
  animate();
};

// 创建智能体球体
const createAgentOrbs = () => {
  const positions = getAgentPositions();
  
  props.agents.forEach((agent, index) => {
    const { x, y } = positions[index];
    const color = getAgentColor(agent.type);
    
    // 几何体
    const geometry = new THREE.SphereGeometry(0.6, 32, 32);
    
    // 材质
    const material = new THREE.MeshPhongMaterial({
      color: color,
      emissive: color,
      emissiveIntensity: agent.status === 'running' ? 0.5 : 0.2,
      transparent: true,
      opacity: 0.9,
    });
    
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(x, y, 0);
    mesh.userData = { agentId: agent.id };
    
    // 添加光晕
    const glowGeometry = new THREE.SphereGeometry(0.8, 32, 32);
    const glowMaterial = new THREE.MeshBasicMaterial({
      color: color,
      transparent: true,
      opacity: 0.2,
    });
    const glowMesh = new THREE.Mesh(glowGeometry, glowMaterial);
    mesh.add(glowMesh);
    
    // 添加标签
    const label = createTextSprite(agent.icon + '\n' + agent.name);
    label.position.set(0, -1, 0);
    mesh.add(label);
    
    scene.add(mesh);
    agentMeshes.set(agent.id, mesh);
  });
};

// 创建连接线
const createConnections = () => {
  const lineMaterial = new THREE.LineBasicMaterial({ 
    color: 0x475569,
    transparent: true,
    opacity: 0.3,
  });
  
  const positions = getAgentPositions();
  
  // 从中心到各智能体
  positions.forEach(pos => {
    const points = [
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(pos.x, pos.y, 0),
    ];
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const line = new THREE.Line(geometry, lineMaterial);
    scene.add(line);
  });
  
  // 智能体之间的连接
  const connections = [
    [0, 1], [1, 2], [2, 3], [3, 4], // 数据 -> 分析
    [4, 5], [4, 6], // -> 多空
    [5, 7], [6, 7], // -> 风险
    [7, 8], // -> 交易
  ];
  
  connections.forEach(([from, to]) => {
    const points = [
      new THREE.Vector3(positions[from].x, positions[from].y, 0),
      new THREE.Vector3(positions[to].x, positions[to].y, 0),
    ];
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const line = new THREE.Line(geometry, lineMaterial.clone());
    scene.add(line);
  });
};

// 创建粒子背景
const createParticles = () => {
  const particleCount = 200;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount * 3);
  
  for (let i = 0; i < particleCount; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 50;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 30;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 20 - 10;
  }
  
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  
  const material = new THREE.PointsMaterial({
    color: 0x3B82F6,
    size: 0.1,
    transparent: true,
    opacity: 0.6,
  });
  
  const particles = new THREE.Points(geometry, material);
  scene.add(particles);
};

// 创建文字精灵
const createTextSprite = (text: string): THREE.Sprite => {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d')!;
  canvas.width = 256;
  canvas.height = 64;
  
  context.fillStyle = 'rgba(0, 0, 0, 0.5)';
  context.roundRect(0, 0, canvas.width, canvas.height, 8);
  context.fill();
  
  context.font = 'bold 24px Arial';
  context.fillStyle = 'white';
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  
  const lines = text.split('\n');
  lines.forEach((line, i) => {
    context.fillText(line, canvas.width / 2, canvas.height / 2 + (i - (lines.length - 1) / 2) * 28);
  });
  
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(2, 0.5, 1);
  
  return sprite;
};

// 获取智能体位置（环形布局）
const getAgentPositions = (): { x: number; y: number }[] => {
  const count = props.agents.length;
  const radius = 5;
  
  return props.agents.map((_, index) => {
    // 从顶部开始，顺时针排列
    const angle = (index / count) * Math.PI * 2 - Math.PI / 2;
    return {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
    };
  });
};

// 获取智能体颜色
const getAgentColor = (type: AgentType): string => {
  const colors: Record<AgentType, string> = {
    [AgentType.DATA_FETCHER]: '#06B6D4',
    [AgentType.TECHNICAL_ANALYST]: '#3B82F6',
    [AgentType.FUNDAMENTAL_ANALYST]: '#8B5CF6',
    [AgentType.SENTIMENT_ANALYST]: '#EC4899',
    [AgentType.NEWS_ANALYST]: '#F97316',
    [AgentType.BULL_RESEARCHER]: '#22C55E',
    [AgentType.BEAR_RESEARCHER]: '#EF4444',
    [AgentType.RISK_MANAGER]: '#EAB308',
    [AgentType.TRADER]: '#6366F1',
  };
  return colors[type] || '#64748B';
};

// 动画循环
const animate = () => {
  animationFrameId = requestAnimationFrame(animate);
  
  // 旋转所有智能体球体
  agentMeshes.forEach((mesh, id) => {
    mesh.rotation.y += 0.01;
    
    // 运行中的球体上下浮动
    const agent = props.agents.find(a => a.id === id);
    if (agent?.status === 'running') {
      mesh.position.y += Math.sin(Date.now() * 0.003) * 0.01;
      
      // 更新发光强度
      const material = mesh.material as THREE.MeshPhongMaterial;
      material.emissiveIntensity = 0.3 + Math.sin(Date.now() * 0.005) * 0.2;
    }
  });
  
  controls.update();
  renderer.render(scene, camera);
};

// 更新智能体状态
const updateAgent = (agentId: string) => {
  const mesh = agentMeshes.get(agentId);
  const agent = props.agents.find(a => a.id === agentId);
  
  if (!mesh || !agent) return;
  
  const material = mesh.material as THREE.MeshPhongMaterial;
  
  switch (agent.status) {
    case 'running':
      material.emissiveIntensity = 0.5;
      break;
    case 'completed':
      material.emissiveIntensity = 0.2;
      material.color.setHex(0x22C55E);
      break;
    case 'failed':
      material.emissiveIntensity = 0.5;
      material.color.setHex(0xEF4444);
      break;
    default:
      material.emissiveIntensity = 0.2;
  }
};

// 监听agents变化
watch(() => props.agents, (newAgents) => {
  newAgents.forEach(agent => {
    updateAgent(agent.id);
  });
}, { deep: true });

// 窗口调整
const handleResize = () => {
  if (!containerRef.value) return;
  
  camera.aspect = containerRef.value.clientWidth / containerRef.value.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(containerRef.value.clientWidth, containerRef.value.clientHeight);
};

onMounted(() => {
  initScene();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  cancelAnimationFrame(animationFrameId);
  renderer?.dispose();
});
</script>

<style scoped>
.agent-scene {
  position: relative;
  width: 100%;
  height: 400px;
  background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
  border-radius: 16px;
  overflow: hidden;
}

canvas {
  display: block;
}

.scene-hints {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #64748B;
  background: rgba(0, 0, 0, 0.5);
  padding: 8px 16px;
  border-radius: 20px;
}

.agent-detail-panel {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 280px;
  background: rgba(30, 41, 59, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
}

.detail-icon {
  font-size: 24px;
}

.detail-name {
  flex: 1;
  font-weight: 600;
  font-size: 16px;
}

.close-btn {
  background: none;
  border: none;
  color: #64748B;
  cursor: pointer;
  font-size: 18px;
}

.detail-body {
  padding: 16px;
}

.detail-status,
.detail-progress,
.detail-task {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.label {
  color: #64748B;
  font-size: 13px;
  min-width: 60px;
}

.progress-ring {
  position: relative;
  width: 60px;
  height: 60px;
}

.progress-ring svg {
  transform: rotate(-90deg);
}

.progress-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 14px;
  font-weight: 600;
}

.detail-output {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.detail-output p {
  margin-top: 8px;
  font-size: 13px;
  color: #94A3B8;
  line-height: 1.5;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
```

---

## 五、后端API设计

### 5.1 API端点

```python
# src/api/routes.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import asyncio
import json
import uuid
from datetime import datetime

router = APIRouter()

# WebSocket连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        self.active_connections[task_id] = websocket
    
    def disconnect(self, task_id: str):
        if task_id in self.active_connections:
            del self.active_connections[task_id]
    
    async def send_message(self, task_id: str, message: dict):
        if task_id in self.active_connections:
            await self.active_connections[task_id].send_json(message)

manager = ConnectionManager()

@router.post("/api/analyze")
async def start_analysis(request: AnalysisRequest):
    """
    启动股票分析任务
    """
    task_id = str(uuid.uuid4())
    
    # 创建任务
    task = AnalysisTask(
        id=task_id,
        stockCode=request.stock_code,
        stockName=request.stock_name,
        status="pending",
        startTime=datetime.now().isoformat(),
    )
    
    # 异步启动分析
    asyncio.create_task(run_analysis(task_id, request))
    
    return {"task_id": task_id, "status": "started"}

@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket实时推送
    """
    await manager.connect(websocket, task_id)
    
    try:
        while True:
            # 保持连接
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(task_id)

@router.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """
    获取任务状态
    """
    # 从存储中获取任务状态
    return get_task_from_storage(task_id)

@router.get("/api/task/{task_id}/result")
async def get_task_result(task_id: str):
    """
    获取任务最终结果
    """
    return get_result_from_storage(task_id)
```

### 5.2 分析引擎（带实时推送）

```python
# src/engine/analysis_engine.py

from typing import AsyncGenerator
from loguru import logger
import asyncio

class AnalysisEngine:
    def __init__(self, task_id: str, stock_code: str, stock_name: str):
        self.task_id = task_id
        self.stock_code = stock_code
        self.stock_name = stock_name
        self.agents = self._init_agents()
        self.logs: List[LogEntry] = []
    
    async def run(self) -> AsyncGenerator[dict, None]:
        """运行完整分析流程"""
        
        # ===== 阶段1: 数据获取 =====
        yield await self._emit_phase_change("data_fetch", "active")
        yield await self._run_data_fetcher()
        
        # ===== 阶段2: 并行分析 =====
        yield await self._emit_phase_change("parallel", "active")
        await asyncio.gather(
            self._run_technical_analyst(),
            self._run_fundamental_analyst(),
            self._run_sentiment_analyst(),
            self._run_news_analyst(),
        )
        
        # ===== 阶段3: 多空辩论 =====
        yield await self._emit_phase_change("debate", "active")
        await asyncio.gather(
            self._run_bull_researcher(),
            self._run_bear_researcher(),
        )
        
        # ===== 阶段4: 风险评估 =====
        yield await self._emit_phase_change("risk", "active")
        yield await self._run_risk_manager()
        
        # ===== 阶段5: 最终决策 =====
        yield await self._emit_phase_change("decision", "active")
        result = await self._run_trader()
        
        # 完成
        yield await self._emit_complete(result)
    
    async def _emit_log(self, level: str, source: str, source_name: str, message: str):
        """发送日志"""
        log = {
            "type": "log",
            "payload": {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "level": level,
                "source": source,
                "sourceName": source_name,
                "message": message,
            }
        }
        self.logs.append(log["payload"])
        return log
    
    async def _emit_agent_status(self, agent_id: str, status: str, progress: int = 0):
        """发送智能体状态变化"""
        return {
            "type": "agent_status_change",
            "payload": {
                "agentId": agent_id,
                "status": status,
                "progress": progress,
            }
        }
    
    async def _run_data_fetcher(self):
        """运行数据获取智能体"""
        agent = self.agents["data_fetcher"]
        
        # 状态: 初始化
        yield await self._emit_agent_status(agent["id"], "initializing")
        yield await self._emit_log("info", "data_fetcher", "数据获取", "开始获取股票数据...")
        
        await asyncio.sleep(0.5)  # 模拟处理
        
        # 获取数据
        data = self.data_manager.get_stock_data(self.stock_code)
        
        # 状态: 运行中
        yield await self._emit_agent_status(agent["id"], "running", 30)
        yield await self._emit_log("info", "data_fetcher", "数据获取", f"获取到 {len(data.prices)} 条K线数据")
        
        await asyncio.sleep(0.3)
        
        # 状态: 完成
        yield await self._emit_agent_status(agent["id"], "completed", 100, data)
        yield await self._emit_log("success", "data_fetcher", "数据获取", "数据获取完成")
        
        return data
    
    async def _run_technical_analyst(self):
        """运行技术分析师"""
        agent = self.agents["technical"]
        
        yield await self._emit_agent_status(agent["id"], "running", 0)
        yield await self._emit_log("info", "technical", "技术分析师", "开始技术分析...")
        
        # 模拟计算过程
        for i in [20, 40, 60, 80, 100]:
            await asyncio.sleep(0.2)
            yield await self._emit_agent_status(agent["id"], "running", i)
            
            if i == 20:
                yield await self._emit_log("debug", "technical", "技术分析师", "计算RSI指标...")
            elif i == 40:
                yield await self._emit_log("debug", "technical", "技术分析师", "计算MACD指标...")
            elif i == 60:
                yield await self._emit_log("debug", "technical", "技术分析师", "识别K线形态...")
            elif i == 80:
                yield await self._emit_log("debug", "technical", "技术分析师", "判断趋势...")
        
        # 输出结果
        output = {
            "summary": "技术面偏多，均线多头排列",
            "keyMetrics": {"RSI": 65, "MACD": "金叉", "趋势": "上升"},
            "signal": "buy",
            "confidence": 72,
        }
        
        yield await self._emit_agent_output(agent["id"], output)
        yield await self._emit_agent_status(agent["id"], "completed", 100)
        yield await self._emit_log("success", "technical", "技术分析师", f"技术分析完成，信号: 买入")
    
    # ... 其他智能体的实现类似 ...
```

---

## 六、状态管理 (Pinia Store)

```typescript
// src/stores/agentStore.ts

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { 
  Agent, 
  AgentStatus, 
  LogEntry, 
  AnalysisTask, 
  FinalResult,
  WorkflowStage,
  RealtimeMessage,
} from '@/types/agent';

export const useAgentStore = defineStore('agent', () => {
  // ===== 状态 =====
  const agents = ref<Agent[]>([]);
  const logs = ref<LogEntry[]>([]);
  const currentTask = ref<AnalysisTask | null>(null);
  const currentPhase = ref<WorkflowStage>(WorkflowStage.DATA_FETCH);
  const isRunning = ref(false);
  const finalResult = ref<FinalResult | null>(null);
  
  // ===== 计算属性 =====
  const completedAgents = computed(() => 
    agents.value.filter(a => a.status === AgentStatus.COMPLETED)
  );
  
  const runningAgents = computed(() =>
    agents.value.filter(a => a.status === AgentStatus.RUNNING)
  );
  
  const overallProgress = computed(() => {
    if (agents.value.length === 0) return 0;
    const total = agents.value.reduce((sum, a) => sum + a.progress, 0);
    return Math.round(total / agents.value.length);
  });
  
  // ===== Actions =====
  
  function initAgents() {
    agents.value = [
      {
        id: 'data_fetcher',
        type: 'data_fetcher',
        name: '数据获取',
        icon: '🔍',
        description: '获取股票数据',
        color: '#06B6D4',
        status: 'idle',
        progress: 0,
        currentTask: null,
        startTime: null,
        endTime: null,
        output: null,
        dependencies: [],
        dependents: ['technical', 'fundamental', 'sentiment', 'news'],
      },
      {
        id: 'technical',
        type: 'technical',
        name: '技术分析师',
        icon: '📊',
        description: '技术指标分析',
        color: '#3B82F6',
        status: 'idle',
        progress: 0,
        currentTask: null,
        startTime: null,
        endTime: null,
        output: null,
        dependencies: ['data_fetcher'],
        dependents: ['bull', 'bear'],
      },
      // ... 其他智能体初始化
    ];
  }
  
  function handleRealtimeMessage(message: RealtimeMessage) {
    switch (message.type) {
      case 'agent_status_change':
        updateAgentStatus(
          message.payload.agentId,
          message.payload.status,
          message.payload.progress
        );
        break;
      
      case 'agent_progress':
        updateAgentProgress(message.payload.agentId, message.payload.progress);
        break;
      
      case 'agent_output':
        setAgentOutput(message.payload.agentId, message.payload.output);
        break;
      
      case 'log':
        addLog(message.payload);
        break;
      
      case 'phase_change':
        setCurrentPhase(message.payload.phase);
        break;
      
      case 'task_complete':
        setFinalResult(message.payload);
        isRunning.value = false;
        break;
    }
  }
  
  function updateAgentStatus(agentId: string, status: AgentStatus, progress: number = 0) {
    const agent = agents.value.find(a => a.id === agentId);
    if (agent) {
      agent.status = status;
      agent.progress = progress;
      
      if (status === 'running' && !agent.startTime) {
        agent.startTime = new Date().toISOString();
      }
      if (status === 'completed') {
        agent.endTime = new Date().toISOString();
      }
    }
  }
  
  function updateAgentProgress(agentId: string, progress: number, message?: string) {
    const agent = agents.value.find(a => a.id === agentId);
    if (agent) {
      agent.progress = progress;
      if (message) {
        agent.currentTask = message;
      }
    }
  }
  
  function setAgentOutput(agentId: string, output: any) {
    const agent = agents.value.find(a => a.id === agentId);
    if (agent) {
      agent.output = output;
    }
  }
  
  function addLog(log: LogEntry) {
    logs.value.push(log);
    // 保持最多500条日志
    if (logs.value.length > 500) {
      logs.value = logs.value.slice(-500);
    }
  }
  
  function setCurrentPhase(phase: WorkflowStage) {
    currentPhase.value = phase;
  }
  
  function setFinalResult(result: FinalResult) {
    finalResult.value = result;
  }
  
  function reset() {
    initAgents();
    logs.value = [];
    currentTask.value = null;
    currentPhase.value = WorkflowStage.DATA_FETCH;
    isRunning.value = false;
    finalResult.value = null;
  }
  
  return {
    // 状态
    agents,
    logs,
    currentTask,
    currentPhase,
    isRunning,
    finalResult,
    
    // 计算属性
    completedAgents,
    runningAgents,
    overallProgress,
    
    // Actions
    initAgents,
    handleRealtimeMessage,
    updateAgentStatus,
    updateAgentProgress,
    setAgentOutput,
    addLog,
    setCurrentPhase,
    setFinalResult,
    reset,
  };
});
```

---

## 七、实时通信 (WebSocket Hook)

```typescript
// src/composables/useWebSocket.ts

import { ref, onUnmounted } from 'vue';
import { useAgentStore } from '@/stores/agentStore';
import type { RealtimeMessage } from '@/types/agent';

export function useWebSocket(taskId: string) {
  const ws = ref<WebSocket | null>(null);
  const isConnected = ref(false);
  const error = ref<string | null>(null);
  
  const agentStore = useAgentStore();
  
  function connect() {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/${taskId}`;
    
    ws.value = new WebSocket(wsUrl);
    
    ws.value.onopen = () => {
      isConnected.value = true;
      error.value = null;
      console.log('WebSocket connected');
    };
    
    ws.value.onmessage = (event) => {
      try {
        const message: RealtimeMessage = JSON.parse(event.data);
        agentStore.handleRealtimeMessage(message);
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    };
    
    ws.value.onerror = (e) => {
      error.value = 'WebSocket error';
      console.error('WebSocket error:', e);
    };
    
    ws.value.onclose = () => {
      isConnected.value = false;
      console.log('WebSocket disconnected');
    };
  }
  
  function disconnect() {
    if (ws.value) {
      ws.value.close();
      ws.value = null;
    }
  }
  
  function send(data: any) {
    if (ws.value && isConnected.value) {
      ws.value.send(JSON.stringify(data));
    }
  }
  
  onUnmounted(() => {
    disconnect();
  });
  
  return {
    isConnected,
    error,
    connect,
    disconnect,
    send,
  };
}
```

---

## 八、动画效果设计

### 8.1 智能体脉冲动画

```css
/* src/styles/animations.css */

/* 运行中智能体脉冲 */
@keyframes pulse-glow {
  0% {
    box-shadow: 0 0 5px var(--agent-color);
  }
  50% {
    box-shadow: 0 0 20px var(--agent-color), 0 0 40px var(--agent-color);
  }
  100% {
    box-shadow: 0 0 5px var(--agent-color);
  }
}

.agent-card.status-running {
  animation: pulse-glow 2s ease-in-out infinite;
}

/* 数据流动画 */
@keyframes data-flow {
  0% {
    stroke-dashoffset: 100%;
  }
  100% {
    stroke-dashoffset: 0%;
  }
}

.data-flow-line.active {
  stroke-dasharray: 10, 5;
  animation: data-flow 1s linear infinite;
}

/* 完成状态庆祝 */
@keyframes celebrate {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
}

.agent-card.status-completed {
  animation: celebrate 0.5s ease-out;
}

/* 进度条渐变 */
@keyframes gradient-shift {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

.progress-fill.animated {
  background: linear-gradient(90deg, #3B82F6, #8B5CF6, #EC4899, #3B82F6);
  background-size: 300% 100%;
  animation: gradient-shift 3s ease infinite;
}

/* 日志打字效果 */
@keyframes typing {
  from {
    width: 0;
  }
  to {
    width: 100%;
  }
}

.log-message.typing {
  overflow: hidden;
  white-space: nowrap;
  animation: typing 1s steps(40, end);
}
```

### 8.2 过渡动画

```typescript
// src/utils/animations.ts

export const transitions = {
  // 卡片进入
  cardEnter: {
    duration: 300,
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
    keyframes: [
      { opacity: 0, transform: 'translateY(20px) scale(0.95)' },
      { opacity: 1, transform: 'translateY(0) scale(1)' },
    ],
  },
  
  // 状态变化
  statusChange: {
    duration: 200,
    easing: 'ease-out',
    keyframes: [
      { transform: 'scale(1)' },
      { transform: 'scale(1.1)' },
      { transform: 'scale(1)' },
    ],
  },
  
  // 进度更新
  progressUpdate: {
    duration: 400,
    easing: 'ease-in-out',
  },
};

// 应用过渡
export function applyTransition(
  element: HTMLElement,
  transition: keyof typeof transitions,
  onComplete?: () => void
) {
  const config = transitions[transition];
  element.style.transition = `all ${config.duration}ms ${config.easing}`;
  
  if (config.keyframes) {
    let currentFrame = 0;
    const animate = () => {
      if (currentFrame < config.keyframes!.length) {
        const frame = config.keyframes![currentFrame];
        Object.assign(element.style, frame);
        currentFrame++;
        requestAnimationFrame(animate);
      } else if (onComplete) {
        onComplete();
      }
    };
    animate();
  }
}
```

---

## 九、交互设计细节

### 9.1 智能体卡片交互

| 交互 | 行为 | 视觉反馈 |
|------|------|----------|
| 悬停 | 高亮卡片，显示更多信息 | 边框发光，轻微上浮 |
| 点击 | 展开详情面板 | 缩放动画 |
| 双击 | 聚焦3D场景中对应球体 | 相机移动动画 |
| 右键 | 显示快捷菜单 | 上下文菜单 |

### 9.2 3D场景交互

| 交互 | 行为 |
|------|------|
| 拖拽 | 旋转视角 |
| 滚轮 | 缩放 |
| 点击球体 | 选中智能体，显示详情 |
| 双击球体 | 放大该智能体视图 |
| 点击空白 | 取消选中 |

### 9.3 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Space` | 暂停/继续分析 |
| `R` | 重新开始分析 |
| `L` | 清空日志 |
| `1-8` | 快速选中第N个智能体 |
| `Esc` | 关闭详情面板 |

---

## 十、性能优化

### 10.1 前端优化

```typescript
// 使用虚拟滚动处理大量日志
const virtualLogList = computed(() => {
  return useVirtualList(logs.value, {
    itemHeight: 32,
    overscan: 10,
  });
});

// 3D场景按需渲染
const renderQuality = ref<'low' | 'medium' | 'high'>('medium');

watch(renderQuality, (quality) => {
  switch (quality) {
    case 'low':
      renderer.setPixelRatio(1);
      break;
    case 'medium':
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
      break;
    case 'high':
      renderer.setPixelRatio(window.devicePixelRatio);
      break;
  }
});
```

### 10.2 内存管理

```typescript
// 组件卸载时清理
onUnmounted(() => {
  // 取消动画帧
  cancelAnimationFrame(animationFrameId);
  
  // 清理Three.js资源
  renderer?.dispose();
  scene?.traverse((object) => {
    if (object instanceof THREE.Mesh) {
      object.geometry?.dispose();
      if (Array.isArray(object.material)) {
        object.material.forEach(m => m.dispose());
      } else {
        object.material?.dispose();
      }
    }
  });
  
  // 清理WebSocket
  ws.value?.close();
});
```

---

## 十一、可访问性 (A11y)

```vue
<!-- 键盘导航 -->
<div class="agent-grid" role="list" aria-label="智能体列表">
  <div 
    v-for="agent in agents"
    :key="agent.id"
    class="agent-card"
    role="listitem"
    tabindex="0"
    :aria-label="`${agent.name}，状态${agent.status}`"
    @keydown.enter="handleSelect(agent)"
  >
    <!-- ... -->
  </div>
</div>

<!-- 状态播报 -->
<LiveRegion>
  <template v-if="latestLog">
    {{ latestLog.sourceName }}: {{ latestLog.message }}
  </template>
</LiveRegion>

<!-- 进度播报 -->
<div 
  role="progressbar" 
  :aria-valuenow="overallProgress" 
  aria-valuemin="0" 
  aria-valuemax="100"
>
  {{ overallProgress }}%
</div>
```

---

## 十二、测试策略

```typescript
// src/components/__tests__/AgentCard.spec.ts

import { describe, it, expect } from 'vitest';
import { render, fireEvent } from '@testing-library/vue';
import AgentCard from '../AgentCard.vue';

describe('AgentCard', () => {
  it('renders agent name and status', () => {
    const { getByText } = render(AgentCard, {
      props: {
        agent: {
          id: 'technical',
          name: '技术分析师',
          icon: '📊',
          status: 'running',
          progress: 50,
          currentTask: '计算RSI...',
        },
      },
    });
    
    expect(getByText('技术分析师')).toBeInTheDocument();
    expect(getByText('运行中')).toBeInTheDocument();
    expect(getByText('50%')).toBeInTheDocument();
  });
  
  it('emits click event when clicked', async () => {
    const { getByRole, emitted } = render(AgentCard, {
      props: { agent: mockAgent },
    });
    
    await fireEvent.click(getByRole('button'));
    expect(emitted().click).toBeTruthy();
  });
});
```

---

## 十三、开发清单

### 前端
- [ ] 项目初始化 (Vite + Vue3 + TypeScript + TailwindCSS)
- [ ] 安装依赖 (Three.js, Pinia, VueUse)
- [ ] 类型定义 (types/agent.ts)
- [ ] 状态管理 (stores/agentStore.ts)
- [ ] WebSocket Hook (composables/useWebSocket.ts)
- [ ] 通用组件 (StatusBadge, ProgressRing, LoadingSpinner)
- [ ] AgentCard组件
- [ ] AgentDetailPanel组件
- [ ] LogConsole组件
- [ ] 2D WorkflowGraph组件
- [ ] 3D AgentScene组件 (Three.js)
- [ ] MainDashboard页面
- [ ] 动画效果 (animations.css)
- [ ] 响应式适配
- [ ] 可访问性优化

### 后端
- [ ] FastAPI项目初始化
- [ ] WebSocket连接管理
- [ ] 分析任务API
- [ ] 实时消息推送
- [ ] 分析引擎实现
- [ ] 错误处理
- [ ] 日志记录

### 集成
- [ ] 前后端联调
- [ ] 性能测试
- [ ] 浏览器兼容性测试
- [ ] 部署配置

---

## 十四、预计工作量

| 模块 | 预计工时 |
|------|----------|
| 项目初始化 + 配置 | 2h |
| 类型定义 + Store | 4h |
| 组件开发 (AgentCard, LogConsole等) | 8h |
| 3D场景 (Three.js) | 12h |
| 后端API + WebSocket | 8h |
| 分析引擎 | 16h |
| 联调 + 优化 | 8h |
| 测试 | 4h |
| **总计** | **~62h** |

---

*文档版本: v1.0*
*最后更新: 2026-05-25*
