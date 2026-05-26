/**
 * 智能体状态管理 Store
 * 管理多智能体协作分析系统的全局状态，包括智能体列表、日志、任务进度等
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type {
  Agent,
  LogEntry,
  AnalysisTask,
  FinalResult,
  RealtimeMessage,
  AgentOutput,
} from '@/types/agent';
import {
  AgentStatus,
  AgentType,
  LogLevel,
  WorkflowStage,
} from '@/types/agent';
import { agentColors } from '@/styles/colors';

/** 智能体初始配置 */
const AGENT_CONFIGS: Array<{
  type: AgentType;
  name: string;
  icon: string;
  description: string;
  dependencies: AgentType[];
}> = [
  {
    type: AgentType.DATA_FETCHER,
    name: '数据获取',
    icon: '🔍',
    description: '获取股票行情、财务数据和市场信息',
    dependencies: [],
  },
  {
    type: AgentType.TECHNICAL_ANALYST,
    name: '技术分析师',
    icon: '📊',
    description: '基于技术指标分析价格走势和交易信号',
    dependencies: [AgentType.DATA_FETCHER],
  },
  {
    type: AgentType.FUNDAMENTAL_ANALYST,
    name: '基本面分析师',
    icon: '📋',
    description: '分析公司财务状况、估值和盈利能力',
    dependencies: [AgentType.DATA_FETCHER],
  },
  {
    type: AgentType.SENTIMENT_ANALYST,
    name: '情绪分析师',
    icon: '💭',
    description: '分析市场情绪和投资者心理',
    dependencies: [AgentType.DATA_FETCHER],
  },
  {
    type: AgentType.NEWS_ANALYST,
    name: '新闻分析师',
    icon: '📰',
    description: '分析最新新闻资讯对股价的影响',
    dependencies: [AgentType.DATA_FETCHER],
  },
  {
    type: AgentType.CAPITAL_FLOW_ANALYST,
    name: '资金流向分析师',
    icon: '💰',
    description: '分析主力资金、北向资金和融资融券动向',
    dependencies: [AgentType.DATA_FETCHER],
  },
  {
    type: AgentType.BULL_RESEARCHER,
    name: '多头研究员',
    icon: '🐂',
    description: '从看多角度论证买入理由',
    dependencies: [AgentType.TECHNICAL_ANALYST, AgentType.FUNDAMENTAL_ANALYST, AgentType.SENTIMENT_ANALYST, AgentType.NEWS_ANALYST, AgentType.CAPITAL_FLOW_ANALYST],
  },
  {
    type: AgentType.BEAR_RESEARCHER,
    name: '空头研究员',
    icon: '🐻',
    description: '从看空角度论证卖出理由',
    dependencies: [AgentType.TECHNICAL_ANALYST, AgentType.FUNDAMENTAL_ANALYST, AgentType.SENTIMENT_ANALYST, AgentType.NEWS_ANALYST, AgentType.CAPITAL_FLOW_ANALYST],
  },
  {
    type: AgentType.RISK_MANAGER,
    name: '风险管理器',
    icon: '🛡️',
    description: '评估投资风险并制定风控策略',
    dependencies: [AgentType.BULL_RESEARCHER, AgentType.BEAR_RESEARCHER],
  },
  {
    type: AgentType.TRADER,
    name: '交易决策',
    icon: '⚖️',
    description: '综合所有分析结果做出最终交易决策',
    dependencies: [AgentType.RISK_MANAGER],
  },
];

/**
 * 根据智能体类型查找其被依赖关系
 * @param agentType - 当前智能体类型
 * @returns 依赖当前智能体的类型列表
 */
function findDependents(agentType: AgentType): AgentType[] {
  return AGENT_CONFIGS
    .filter((config) => config.dependencies.includes(agentType))
    .map((config) => config.type);
}

export const useAgentStore = defineStore('agent', () => {
  const agents = ref<Agent[]>([]);
  const logs = ref<LogEntry[]>([]);
  const currentTask = ref<AnalysisTask | null>(null);
  const currentPhase = ref<WorkflowStage>(WorkflowStage.DATA_FETCH);
  const isRunning = ref<boolean>(false);
  const finalResult = ref<FinalResult | null>(null);

  const completedAgents = computed(() =>
    agents.value.filter((a) => a.status === AgentStatus.COMPLETED).length,
  );

  const runningAgents = computed(() =>
    agents.value.filter((a) => a.status === AgentStatus.RUNNING).length,
  );

  const overallProgress = computed(() => {
    if (agents.value.length === 0) return 0;
    const total = agents.value.reduce((sum, a) => sum + a.progress, 0);
    return Math.round(total / agents.value.length);
  });

  /**
   * 初始化所有智能体
   */
  function initAgents(): void {
    agents.value = AGENT_CONFIGS.map((config) => ({
      id: config.type,
      type: config.type,
      name: config.name,
      icon: config.icon,
      description: config.description,
      color: agentColors[config.type] ?? '#64748B',
      status: AgentStatus.IDLE,
      progress: 0,
      currentTask: '',
      startTime: null,
      endTime: null,
      output: null,
      dependencies: config.dependencies,
      dependents: findDependents(config.type),
    }));
  }

  /**
   * 处理实时消息
   * 根据消息类型分发到对应的处理逻辑
   */
  function handleRealtimeMessage(message: RealtimeMessage): void {
    switch (message.type) {
      case 'agent_status_change': {
        const { agentId, status, progress } = message.payload;
        updateAgentStatus(agentId, status, progress);
        break;
      }
      case 'agent_progress': {
        const { agentId, progress, message: msg } = message.payload;
        updateAgentProgress(agentId, progress, msg);
        break;
      }
      case 'agent_output': {
        const { agentId, output } = message.payload;
        setAgentOutput(agentId, output);
        break;
      }
      case 'log':
        addLog(message.payload);
        break;
      case 'phase_change':
        setCurrentPhase(message.payload.phase as WorkflowStage);
        break;
      case 'task_complete':
        setFinalResult(message.payload);
        break;
      case 'error':
        addLog({
          id: `log_${Date.now()}`,
          timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
          level: LogLevel.ERROR,
          source: 'system',
          sourceName: '系统',
          message: message.payload.message,
        });
        break;
    }
  }

  /**
   * 更新智能体状态
   */
  function updateAgentStatus(
    agentId: string,
    status: AgentStatus,
    progress: number = 0,
  ): void {
    const agent = agents.value.find((a) => a.id === agentId);
    if (!agent) return;

    agent.status = status;
    agent.progress = progress;

    if (status === AgentStatus.RUNNING && !agent.startTime) {
      agent.startTime = new Date().toISOString();
    }
    if (status === AgentStatus.COMPLETED || status === AgentStatus.FAILED) {
      agent.endTime = new Date().toISOString();
      if (status === AgentStatus.COMPLETED) {
        agent.progress = 100;
      }
    }
  }

  /**
   * 更新智能体进度
   */
  function updateAgentProgress(
    agentId: string,
    progress: number,
    taskMessage?: string,
  ): void {
    const agent = agents.value.find((a) => a.id === agentId);
    if (!agent) return;

    agent.progress = Math.min(100, Math.max(0, progress));
    if (taskMessage) {
      agent.currentTask = taskMessage;
    }
  }

  /**
   * 设置智能体输出结果
   */
  function setAgentOutput(agentId: string, output: AgentOutput): void {
    const agent = agents.value.find((a) => a.id === agentId);
    if (!agent) return;
    agent.output = output;
  }

  /**
   * 添加日志条目
   */
  function addLog(entry: LogEntry): void {
    logs.value.push(entry);
    if (logs.value.length > 500) {
      logs.value = logs.value.slice(-300);
    }
  }

  /**
   * 设置当前工作流阶段
   */
  function setCurrentPhase(phase: WorkflowStage): void {
    currentPhase.value = phase;
  }

  /**
   * 设置最终分析结果
   */
  function setFinalResult(result: FinalResult): void {
    finalResult.value = result;
    isRunning.value = false;
  }

  /**
   * 重置所有状态
   */
  function reset(): void {
    initAgents();
    logs.value = [];
    currentTask.value = null;
    currentPhase.value = WorkflowStage.DATA_FETCH;
    isRunning.value = false;
    finalResult.value = null;
  }

  return {
    agents,
    logs,
    currentTask,
    currentPhase,
    isRunning,
    finalResult,
    completedAgents,
    runningAgents,
    overallProgress,
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
