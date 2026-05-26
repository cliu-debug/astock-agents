/** 智能体状态枚举 */
export enum AgentStatus {
  IDLE = 'idle',
  INITIALIZING = 'init',
  RUNNING = 'running',
  WAITING = 'waiting',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

/** 智能体类型枚举 */
export enum AgentType {
  DATA_FETCHER = 'data_fetcher',
  TECHNICAL_ANALYST = 'technical',
  FUNDAMENTAL_ANALYST = 'fundamental',
  SENTIMENT_ANALYST = 'sentiment',
  NEWS_ANALYST = 'news',
  CAPITAL_FLOW_ANALYST = 'capital_flow',
  BULL_RESEARCHER = 'bull',
  BEAR_RESEARCHER = 'bear',
  RISK_MANAGER = 'risk',
  TRADER = 'trader',
}

/** 日志级别枚举 */
export enum LogLevel {
  DEBUG = 'debug',
  INFO = 'info',
  SUCCESS = 'success',
  WARNING = 'warning',
  ERROR = 'error',
}

/** 工作流阶段枚举 */
export enum WorkflowStage {
  DATA_FETCH = 'data_fetch',
  PARALLEL_ANALYSIS = 'parallel',
  DEBATE = 'debate',
  RISK_ASSESSMENT = 'risk',
  DECISION = 'decision',
}

/** 交易信号枚举 */
export enum Signal {
  STRONG_BUY = 'strong_buy',
  BUY = 'buy',
  HOLD = 'hold',
  SELL = 'sell',
  STRONG_SELL = 'strong_sell',
}

/** 风险等级枚举 */
export enum RiskLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  EXTREME = 'extreme',
}

/** 智能体定义接口 */
export interface Agent {
  id: string
  type: AgentType
  name: string
  icon: string
  description: string
  color: string
  status: AgentStatus
  progress: number
  currentTask: string
  startTime: string | null
  endTime: string | null
  output: AgentOutput | null
  dependencies: AgentType[]
  dependents: AgentType[]
}

/** 智能体输出接口 */
export interface AgentOutput {
  summary: string
  keyMetrics: Record<string, number | string>
  signal?: Signal
  confidence?: number
  details?: Record<string, unknown>
}

/** 日志条目接口 */
export interface LogEntry {
  id: string
  timestamp: string
  level: LogLevel
  source: AgentType | 'system'
  sourceName: string
  message: string
  details?: Record<string, unknown>
}

/** 工作流节点接口 */
export interface WorkflowNode {
  id: string
  agentId: string
  x: number
  y: number
  status: AgentStatus
  connected: boolean
}

/** 工作流边接口 */
export interface WorkflowEdge {
  id: string
  source: string
  target: string
  active: boolean
  animated: boolean
}

/** 工作流阶段接口 */
export interface WorkflowPhase {
  stage: WorkflowStage
  name: string
  agents: AgentType[]
  status: 'pending' | 'active' | 'completed'
}

/** 分析任务接口 */
export interface AnalysisTask {
  id: string
  stockCode: string
  stockName: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  startTime: string
  endTime?: string
  agents: Agent[]
  phases: WorkflowPhase[]
  logs: LogEntry[]
  finalResult?: FinalResult
}

/** 最终结果接口 */
export interface FinalResult {
  stockCode: string
  stockName: string
  currentPrice: number
  changePercent: number
  signal: Signal
  score: number
  confidence: number
  riskLevel: RiskLevel
  summary: string
  agentViews: AgentOutput[]
}

/** 实时消息类型 */
export type RealtimeMessage =
  | { type: 'agent_status_change'; payload: { agentId: string; status: AgentStatus; progress: number } }
  | { type: 'agent_progress'; payload: { agentId: string; progress: number; message: string } }
  | { type: 'agent_output'; payload: { agentId: string; output: AgentOutput } }
  | { type: 'log'; payload: LogEntry }
  | { type: 'phase_change'; payload: { phase: WorkflowStage; status: string } }
  | { type: 'task_complete'; payload: FinalResult }
  | { type: 'error'; payload: { message: string } }
