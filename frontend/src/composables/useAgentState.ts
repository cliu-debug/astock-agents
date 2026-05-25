/**
 * 智能体状态管理组合式函数
 * 提供智能体颜色、状态文本、日志图标等辅助函数
 */
import type { AgentType, AgentStatus, LogLevel } from '../types/agent.ts';
import { statusColors, agentColors } from '../styles/colors.ts';

/**
 * 根据智能体类型获取主题色
 * @param type - 智能体类型
 * @returns 十六进制颜色值
 */
export function getAgentColor(type: AgentType): string {
  return agentColors[type] ?? '#6b7280';
}

/**
 * 根据智能体状态获取颜色
 * @param status - 智能体状态
 * @returns 十六进制颜色值
 */
export function getStatusColor(status: AgentStatus): string {
  return statusColors[status] ?? '#6b7280';
}

/**
 * 根据智能体状态获取中文文本
 * @param status - 智能体状态
 * @returns 状态中文描述
 */
export function getStatusText(status: AgentStatus): string {
  const statusTextMap: Record<AgentStatus, string> = {
    idle: '空闲',
    init: '初始化',
    running: '运行中',
    waiting: '等待中',
    completed: '已完成',
    failed: '失败',
  };
  return statusTextMap[status] ?? '未知';
}

/**
 * 根据日志级别获取图标名称
 * @param level - 日志级别
 * @returns 图标标识字符串
 */
export function getLogIcon(level: LogLevel): string {
  const logIconMap: Record<LogLevel, string> = {
    debug: 'bug',
    info: 'info',
    success: 'check-circle',
    warning: 'alert-triangle',
    error: 'x-circle',
  };
  return logIconMap[level] ?? 'info';
}

/**
 * 根据消息来源获取颜色
 * @param source - 来源标识（智能体类型或 'system'）
 * @returns 十六进制颜色值
 */
export function getSourceColor(source: AgentType | 'system'): string {
  if (source === 'system') {
    return '#60a5fa';
  }
  return agentColors[source] ?? '#6b7280';
}
