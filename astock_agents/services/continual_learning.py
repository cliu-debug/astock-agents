"""持续学习服务 (ContinualLearningService)

从用户反馈中改进分析策略，适应新环境。
核心能力：
1. 反馈收集 - 用户对分析结果的评价
2. 策略调整 - 根据反馈调整分析权重和阈值
3. 偏差修正 - 识别系统性偏差并修正
4. 适应学习 - 根据市场环境变化调整参数
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

from astock_agents.db.database import Database


class ContinualLearningService:
    """持续学习服务

    通过用户反馈和历史准确率，动态调整分析策略参数。
    """

    # 信号准确率权重调整映射
    SIGNAL_WEIGHT_ADJUSTMENTS = {
        "买入": {"agree": 0.02, "disagree": -0.05},
        "强烈买入": {"agree": 0.03, "disagree": -0.08},
        "卖出": {"agree": 0.02, "disagree": -0.05},
        "强烈卖出": {"agree": 0.03, "disagree": -0.08},
        "持有": {"agree": 0.01, "disagree": -0.02},
    }

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def record_feedback(
        self,
        user_id: str,
        stock_code: str,
        signal: str,
        feedback_type: str,
        feedback_text: str = "",
        actual_outcome: str = "",
    ) -> Dict[str, Any]:
        """记录用户反馈

        Args:
            user_id: 用户ID
            stock_code: 股票代码
            signal: 当时的信号
            feedback_type: 反馈类型(agree/disagree/neutral)
            feedback_text: 反馈文本
            actual_outcome: 实际结果

        Returns:
            反馈记录和策略调整结果
        """
        self.db.save_feedback(
            user_id=user_id,
            stock_code=stock_code,
            signal=signal,
            feedback_type=feedback_type,
            feedback_text=feedback_text,
            actual_outcome=actual_outcome,
        )

        adjustment = self._compute_adjustment(user_id, signal, feedback_type)

        logger.info(
            f"[持续学习] 反馈记录: user={user_id}, stock={stock_code}, "
            f"signal={signal}, feedback={feedback_type}"
        )

        return {
            "feedback_recorded": True,
            "signal": signal,
            "feedback_type": feedback_type,
            "adjustment": adjustment,
        }

    def get_learning_state(self, user_id: str) -> Dict[str, Any]:
        """获取当前学习状态

        Args:
            user_id: 用户ID

        Returns:
            学习状态字典
        """
        stats = self.db.get_feedback_stats(user_id)

        bias = self._detect_bias(stats)
        params = self._get_adjusted_params(user_id, stats)

        return {
            "user_id": user_id,
            "stats": stats,
            "detected_bias": bias,
            "adjusted_params": params,
            "learning_progress": self._compute_learning_progress(stats),
        }

    def get_adjusted_weights(self, user_id: str) -> Dict[str, float]:
        """获取调整后的分析维度权重

        基于用户历史反馈的准确率，动态调整各维度的分析权重。
        如果技术面信号经常被用户否定，降低技术面权重。

        Args:
            user_id: 用户ID

        Returns:
            调整后的权重字典
        """
        stats = self.db.get_feedback_stats(user_id)
        return self._get_adjusted_params(user_id, stats).get("dimension_weights", {
            "technical": 0.35,
            "fundamental": 0.30,
            "sentiment": 0.15,
            "news": 0.20,
        })

    def _compute_adjustment(
        self,
        user_id: str,
        signal: str,
        feedback_type: str,
    ) -> Dict[str, Any]:
        """计算反馈导致的策略调整

        Args:
            user_id: 用户ID
            signal: 信号
            feedback_type: 反馈类型

        Returns:
            调整结果字典
        """
        adjustments = self.SIGNAL_WEIGHT_ADJUSTMENTS.get(signal, {})
        delta = adjustments.get(feedback_type, 0)

        if delta == 0:
            return {"changed": False, "reason": "无调整"}

        direction = "提升" if delta > 0 else "降低"

        return {
            "changed": True,
            "signal": signal,
            "feedback": feedback_type,
            "weight_delta": delta,
            "direction": direction,
            "description": f"信号'{signal}'的反馈为'{feedback_type}'，{direction}该信号权重{abs(delta):.0%}",
        }

    def _detect_bias(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """检测系统性偏差

        Args:
            stats: 反馈统计

        Returns:
            偏差检测结果
        """
        biases = []
        signal_accuracy = stats.get("signal_accuracy", {})

        for signal, fb_counts in signal_accuracy.items():
            agree = fb_counts.get("agree", 0)
            disagree = fb_counts.get("disagree", 0)
            total = agree + disagree

            if total < 3:
                continue

            accuracy = agree / max(total, 1)

            if accuracy < 0.3 and total >= 5:
                biases.append({
                    "type": "over_confident",
                    "signal": signal,
                    "accuracy": round(accuracy * 100, 1),
                    "description": f"信号'{signal}'准确率仅{accuracy:.0%}，可能存在过度自信偏差",
                })

            if accuracy > 0.9 and total >= 5:
                biases.append({
                    "type": "well_calibrated",
                    "signal": signal,
                    "accuracy": round(accuracy * 100, 1),
                    "description": f"信号'{signal}'准确率{accuracy:.0%}，校准良好",
                })

        return {
            "biases_found": len(biases),
            "details": biases,
        }

    def _get_adjusted_params(
        self,
        user_id: str,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """根据反馈统计调整分析参数

        Args:
            user_id: 用户ID
            stats: 反馈统计

        Returns:
            调整后的参数字典
        """
        base_weights = {
            "technical": 0.35,
            "fundamental": 0.30,
            "sentiment": 0.15,
            "news": 0.20,
        }

        confidence_offset = 0
        signal_accuracy = stats.get("signal_accuracy", {})

        # 根据买入信号准确率调整
        buy_agree = signal_accuracy.get("买入", {}).get("agree", 0)
        buy_disagree = signal_accuracy.get("买入", {}).get("disagree", 0)
        buy_total = buy_agree + buy_disagree

        if buy_total >= 5:
            buy_accuracy = buy_agree / max(buy_total, 1)
            if buy_accuracy < 0.4:
                confidence_offset = -10
                base_weights["fundamental"] += 0.05
                base_weights["technical"] -= 0.05
            elif buy_accuracy > 0.7:
                confidence_offset = 5

        # 根据卖出信号准确率调整
        sell_agree = signal_accuracy.get("卖出", {}).get("agree", 0)
        sell_disagree = signal_accuracy.get("卖出", {}).get("disagree", 0)
        sell_total = sell_agree + sell_disagree

        if sell_total >= 5:
            sell_accuracy = sell_agree / max(sell_total, 1)
            if sell_accuracy < 0.4:
                confidence_offset -= 5
                base_weights["sentiment"] += 0.05
                base_weights["news"] -= 0.05

        # 归一化权重
        total_weight = sum(base_weights.values())
        if total_weight > 0:
            base_weights = {k: round(v / total_weight, 2) for k, v in base_weights.items()}

        return {
            "dimension_weights": base_weights,
            "confidence_offset": confidence_offset,
            "risk_guard_overrides": {
                "min_confidence": max(20, 30 + confidence_offset),
                "warn_confidence": max(40, 50 + confidence_offset),
            },
        }

    def _compute_learning_progress(self, stats: Dict[str, Any]) -> str:
        """计算学习进度

        Args:
            stats: 反馈统计

        Returns:
            学习进度描述
        """
        total = stats.get("total_feedbacks", 0)
        accuracy = stats.get("accuracy_rate", 0)

        if total < 5:
            return "初始阶段：数据不足，需要更多反馈"
        if total < 20:
            return f"学习阶段：已收集{total}条反馈，准确率{accuracy}%"
        if total < 50:
            return f"成长阶段：已收集{total}条反馈，准确率{accuracy}%，策略开始调整"
        return f"成熟阶段：已收集{total}条反馈，准确率{accuracy}%，策略已优化"
