/**
 * 颜色系统定义
 * 统一管理状态颜色、智能体颜色、背景颜色、文本颜色和渐变色
 * 与 MULTI_AGENT_UI_DESIGN.md 设计规范保持一致
 */

/** 智能体状态颜色映射 */
export const statusColors: Record<string, string> = {
  idle: '#10B981',
  init: '#3B82F6',
  running: '#F59E0B',
  waiting: '#8B5CF6',
  completed: '#22C55E',
  failed: '#EF4444',
};

/** 智能体类型颜色映射 */
export const agentColors: Record<string, string> = {
  data_fetcher: '#06B6D4',
  technical: '#3B82F6',
  fundamental: '#8B5CF6',
  sentiment: '#EC4899',
  news: '#F97316',
  capital_flow: '#14B8A6',
  bull: '#22C55E',
  bear: '#EF4444',
  risk: '#EAB308',
  trader: '#6366F1',
};

/** 背景颜色映射 */
export const backgroundColors: Record<string, string> = {
  primary: '#0F172A',
  secondary: '#1E293B',
  tertiary: '#334155',
  card: '#334155',
  cardHover: '#475569',
  surface: '#0F172A',
  overlay: 'rgba(0, 0, 0, 0.6)',
};

/** 文本颜色映射 */
export const textColors: Record<string, string> = {
  primary: '#F8FAFC',
  secondary: '#94A3B8',
  tertiary: '#64748B',
  muted: '#64748B',
  inverse: '#0F172A',
  link: '#60A5FA',
};

/** 渐变色映射 */
export const gradients: Record<string, string> = {
  primary: 'linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%)',
  success: 'linear-gradient(135deg, #22C55E 0%, #10B981 100%)',
  warning: 'linear-gradient(135deg, #F59E0B 0%, #EAB308 100%)',
  danger: 'linear-gradient(135deg, #EF4444 0%, #DC2626 100%)',
  bull: 'linear-gradient(135deg, #22C55E 0%, #34D399 100%)',
  bear: 'linear-gradient(135deg, #EF4444 0%, #F87171 100%)',
  neutral: 'linear-gradient(135deg, #64748B 0%, #94A3B8 100%)',
  background: 'linear-gradient(180deg, #0F172A 0%, #1E293B 100%)',
};
