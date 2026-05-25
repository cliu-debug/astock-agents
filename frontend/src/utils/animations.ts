/**
 * 动画工具
 * 提供过渡动画配置和动画应用函数
 */

/** 过渡动画配置 */
export const transitions = {
  /** 卡片进入动画 */
  cardEnter: {
    duration: 300,
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
    fill: 'forwards' as FillMode,
    keyframes: [
      { opacity: 0, transform: 'translateY(10px) scale(0.98)' },
      { opacity: 1, transform: 'translateY(0) scale(1)' },
    ],
  },
  /** 状态变更动画 */
  statusChange: {
    duration: 400,
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
    fill: 'forwards' as FillMode,
    keyframes: [
      { transform: 'scale(1)' },
      { transform: 'scale(1.15)' },
      { transform: 'scale(1)' },
    ],
  },
  /** 进度更新动画 */
  progressUpdate: {
    duration: 600,
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
    fill: 'forwards' as FillMode,
  },
} as const;

/**
 * 将过渡动画配置应用到指定元素
 * @param element - 目标 DOM 元素
 * @param transitionConfig - 过渡动画配置
 * @param customKeyframes - 自定义关键帧（可选，覆盖配置中的关键帧）
 * @returns Web Animation API 动画实例
 */
export function applyTransition(
  element: HTMLElement,
  transitionConfig: {
    duration: number;
    easing: string;
    fill: FillMode;
    keyframes?: Keyframe[];
  },
  customKeyframes?: Keyframe[],
): Animation {
  const keyframes = customKeyframes ?? transitionConfig.keyframes ?? [];
  return element.animate(keyframes, {
    duration: transitionConfig.duration,
    easing: transitionConfig.easing,
    fill: transitionConfig.fill,
  });
}
