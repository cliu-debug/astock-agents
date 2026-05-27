"""用户记忆系统 - 年轮记忆算法

像树的年轮一样，记录用户投资行为轨迹，形成个性化投资画像。
核心功能：
1. 记录每次分析/交易行为
2. 构建用户投资偏好画像
3. 分析时调用历史记忆提供个性化建议
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

from astock_agents.db.database import Database


class UserMemoryService:
    """用户记忆服务 - 年轮记忆算法实现

    通过记录用户分析/交易行为，构建投资画像，
    并根据历史偏好调整信号输出，实现个性化投研体验。
    """

    # 风险偏好阈值
    _RISK_THRESHOLDS = {
        "aggressive": 0.7,   # 激进：高频交易、大额买入
        "moderate": 0.4,     # 稳健：中等频率、适度仓位
        "conservative": 0.0, # 保守：低频交易、小仓位
    }

    # 持仓周期阈值（天）
    _HOLDING_PERIOD_THRESHOLDS = {
        "short_term": 5,    # 短线：5天以内
        "mid_term": 20,     # 中线：5-20天
        "long_term": 999,   # 长线：20天以上
    }

    def __init__(self, db: Optional[Database] = None):
        """
        初始化用户记忆服务

        Args:
            db: 数据库实例，为空时自动创建
        """
        self.db = db or Database()

    def record_analysis(
        self,
        user_id: str,
        stock_code: str,
        signal: str,
        confidence: int,
        industry: Optional[str] = None,
    ) -> bool:
        """记录分析行为

        Args:
            user_id: 用户ID
            stock_code: 股票代码
            signal: 分析信号（如 买入/卖出/持有）
            confidence: 置信度 0-100
            industry: 所属行业

        Returns:
            是否记录成功
        """
        try:
            self.db.save_user_memory(
                user_id=user_id,
                stock_code=stock_code,
                action_type="analysis",
                signal=signal,
                confidence=confidence,
                industry=industry,
            )
            logger.info(f"[记忆] 记录分析行为: user={user_id}, stock={stock_code}, signal={signal}")
            return True
        except Exception as e:
            logger.error(f"[记忆] 记录分析行为失败: {e}")
            return False

    def record_trade(
        self,
        user_id: str,
        stock_code: str,
        action: str,
        amount: float,
        price: float,
        industry: Optional[str] = None,
    ) -> bool:
        """记录交易行为

        Args:
            user_id: 用户ID
            stock_code: 股票代码
            action: 交易动作（buy/sell）
            amount: 交易金额
            price: 交易价格
            industry: 所属行业

        Returns:
            是否记录成功
        """
        try:
            self.db.save_user_memory(
                user_id=user_id,
                stock_code=stock_code,
                action_type="trade",
                signal=action,
                amount=amount,
                price=price,
                industry=industry,
                metadata=json.dumps({"action": action}),
            )
            logger.info(f"[记忆] 记录交易行为: user={user_id}, stock={stock_code}, action={action}")
            return True
        except Exception as e:
            logger.error(f"[记忆] 记录交易行为失败: {e}")
            return False

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """获取用户投资画像

        基于历史行为数据，计算用户的投资偏好画像，包括：
        - 偏好行业（基于分析频率）
        - 风险偏好（激进/稳健/保守）
        - 持仓周期偏好（短线/中线/长线）
        - 分析维度权重调整

        Args:
            user_id: 用户ID

        Returns:
            用户投资画像字典
        """
        # 获取所有记忆记录
        memories = self.db.get_user_memories(user_id=user_id, limit=500)
        if not memories:
            return self._default_profile()

        # 计算偏好行业
        industry_stats = self.db.get_user_industry_stats(user_id)
        preferred_industries = [
            {"industry": s["industry"], "weight": s["count"]}
            for s in industry_stats[:5]
        ]

        # 计算风险偏好
        risk_preference = self._calculate_risk_preference(memories)

        # 计算持仓周期偏好
        holding_preference = self._calculate_holding_preference(memories)

        # 计算分析维度权重
        dimension_weights = self._calculate_dimension_weights(memories)

        # 统计摘要
        analysis_count = sum(1 for m in memories if m["action_type"] == "analysis")
        trade_count = sum(1 for m in memories if m["action_type"] == "trade")
        stock_set = set(m["stock_code"] for m in memories)

        return {
            "user_id": user_id,
            "preferred_industries": preferred_industries,
            "risk_preference": risk_preference,
            "holding_preference": holding_preference,
            "dimension_weights": dimension_weights,
            "stats": {
                "total_analyses": analysis_count,
                "total_trades": trade_count,
                "unique_stocks": len(stock_set),
            },
            "updated_at": datetime.now().isoformat(),
        }

    def get_stock_memory(self, user_id: str, stock_code: str) -> Dict[str, Any]:
        """获取某股票的历史记忆

        Args:
            user_id: 用户ID
            stock_code: 股票代码

        Returns:
            股票历史记忆字典
        """
        memories = self.db.get_user_memories(user_id=user_id, stock_code=stock_code, limit=50)
        if not memories:
            return {"stock_code": stock_code, "has_memory": False, "records": []}

        # 统计信号分布
        signal_counts: Dict[str, int] = {}
        for m in memories:
            if m.get("signal"):
                signal_counts[m["signal"]] = signal_counts.get(m["signal"], 0) + 1

        # 最近一次分析
        last_analysis = None
        for m in memories:
            if m["action_type"] == "analysis":
                last_analysis = {
                    "signal": m.get("signal"),
                    "confidence": m.get("confidence"),
                    "time": m.get("created_at"),
                }
                break

        # 交易记录
        trade_records = [
            {
                "action": m.get("signal"),
                "amount": m.get("amount"),
                "price": m.get("price"),
                "time": m.get("created_at"),
            }
            for m in memories
            if m["action_type"] == "trade"
        ]

        return {
            "stock_code": stock_code,
            "has_memory": True,
            "total_records": len(memories),
            "signal_distribution": signal_counts,
            "last_analysis": last_analysis,
            "trade_records": trade_records,
        }

    def get_preference_adjusted_signal(
        self,
        user_id: str,
        stock_code: str,
        raw_signal: str,
    ) -> Dict[str, Any]:
        """根据用户偏好调整信号

        基于用户历史行为和偏好，对原始信号进行个性化调整：
        - 保守型用户：降低买入信号的置信度
        - 激进型用户：提升买入信号的置信度
        - 历史偏好行业：适度提升置信度
        - 历史回避行业：适度降低置信度

        Args:
            user_id: 用户ID
            stock_code: 股票代码
            raw_signal: 原始信号（如 买入/卖出/持有）

        Returns:
            调整后的信号字典，包含原始信号、调整后信号和调整说明
        """
        profile = self.get_user_profile(user_id)
        stock_memory = self.get_stock_memory(user_id, stock_code)

        adjusted_signal = raw_signal
        adjustment_reasons: List[str] = []

        # 根据风险偏好调整
        risk_pref = profile.get("risk_preference", "稳健")
        if risk_pref == "保守" and raw_signal in ("强烈买入", "买入"):
            adjusted_signal = self._downgrade_signal(raw_signal)
            adjustment_reasons.append(f"用户风险偏好保守，降低买入信号强度")
        elif risk_pref == "激进" and raw_signal in ("买入", "强烈买入"):
            adjusted_signal = self._upgrade_signal(raw_signal)
            adjustment_reasons.append(f"用户风险偏好激进，提升买入信号强度")

        # 根据历史记忆调整
        if stock_memory.get("has_memory"):
            signal_dist = stock_memory.get("signal_distribution", {})
            # 如果历史多次对同一股票发出相反信号，降低置信度
            if raw_signal in ("买入", "强烈买入") and signal_dist.get("卖出", 0) > 2:
                adjustment_reasons.append("历史多次卖出该股票，建议谨慎")
            elif raw_signal in ("卖出", "强烈卖出") and signal_dist.get("买入", 0) > 2:
                adjustment_reasons.append("历史多次买入该股票，建议谨慎")

        return {
            "raw_signal": raw_signal,
            "adjusted_signal": adjusted_signal,
            "adjustment_reasons": adjustment_reasons,
            "risk_preference": risk_pref,
        }

    # ==================== 私有方法 ====================

    @staticmethod
    def _default_profile() -> Dict[str, Any]:
        """返回默认画像（无历史数据时）"""
        return {
            "user_id": "",
            "preferred_industries": [],
            "risk_preference": "稳健",
            "holding_preference": "中线",
            "dimension_weights": {
                "technical": 0.35,
                "fundamental": 0.30,
                "sentiment": 0.15,
                "news": 0.20,
            },
            "stats": {
                "total_analyses": 0,
                "total_trades": 0,
                "unique_stocks": 0,
            },
            "updated_at": datetime.now().isoformat(),
        }

    def _calculate_risk_preference(self, memories: List[Dict[str, Any]]) -> str:
        """根据交易行为计算风险偏好

        评估维度：
        - 交易频率
        - 单笔交易金额占比
        - 买入信号占比

        Args:
            memories: 用户记忆列表

        Returns:
            风险偏好字符串：激进/稳健/保守
        """
        trade_memories = [m for m in memories if m["action_type"] == "trade"]
        if not trade_memories:
            return "稳健"

        # 计算交易频率（近30天交易次数）
        trade_count = len(trade_memories)

        # 计算买入占比
        buy_count = sum(1 for m in trade_memories if m.get("signal") == "buy")
        buy_ratio = buy_count / max(trade_count, 1)

        # 计算平均交易金额
        amounts = [m.get("amount", 0) or 0 for m in trade_memories]
        avg_amount = sum(amounts) / max(len(amounts), 1)

        # 综合评分
        risk_score = 0.0
        if trade_count > 20:
            risk_score += 0.3
        elif trade_count > 10:
            risk_score += 0.15

        if buy_ratio > 0.7:
            risk_score += 0.3
        elif buy_ratio > 0.5:
            risk_score += 0.15

        if avg_amount > 50000:
            risk_score += 0.3
        elif avg_amount > 20000:
            risk_score += 0.15

        if risk_score >= self._RISK_THRESHOLDS["aggressive"]:
            return "激进"
        elif risk_score >= self._RISK_THRESHOLDS["moderate"]:
            return "稳健"
        return "保守"

    def _calculate_holding_preference(self, memories: List[Dict[str, Any]]) -> str:
        """根据交易行为计算持仓周期偏好

        Args:
            memories: 用户记忆列表

        Returns:
            持仓周期偏好字符串：短线/中线/长线
        """
        # 基于交易频率推断持仓周期
        trade_memories = [m for m in memories if m["action_type"] == "trade"]
        if not trade_memories:
            return "中线"

        trade_count = len(trade_memories)
        # 简化逻辑：交易频率高 -> 短线，频率低 -> 长线
        if trade_count > 30:
            return "短线"
        elif trade_count > 10:
            return "中线"
        return "长线"

    @staticmethod
    def _calculate_dimension_weights(memories: List[Dict[str, Any]]) -> Dict[str, float]:
        """根据用户行为计算分析维度权重

        Args:
            memories: 用户记忆列表

        Returns:
            分析维度权重字典
        """
        # 默认权重
        weights = {
            "technical": 0.35,
            "fundamental": 0.30,
            "sentiment": 0.15,
            "news": 0.20,
        }

        # 根据置信度分布微调
        analysis_memories = [m for m in memories if m["action_type"] == "analysis"]
        if not analysis_memories:
            return weights

        # 计算平均置信度
        confidences = [m.get("confidence", 50) or 50 for m in analysis_memories]
        avg_confidence = sum(confidences) / max(len(confidences), 1)

        # 高置信度用户更偏重技术面
        if avg_confidence > 70:
            weights["technical"] += 0.05
            weights["sentiment"] -= 0.05
        elif avg_confidence < 40:
            weights["fundamental"] += 0.05
            weights["technical"] -= 0.05

        return weights

    @staticmethod
    def _upgrade_signal(signal: str) -> str:
        """升级信号强度

        Args:
            signal: 原始信号

        Returns:
            升级后的信号
        """
        upgrade_map = {
            "买入": "强烈买入",
            "持有": "买入",
            "卖出": "持有",
        }
        return upgrade_map.get(signal, signal)

    @staticmethod
    def _downgrade_signal(signal: str) -> str:
        """降级信号强度

        Args:
            signal: 原始信号

        Returns:
            降级后的信号
        """
        downgrade_map = {
            "强烈买入": "买入",
            "买入": "持有",
            "强烈卖出": "卖出",
        }
        return downgrade_map.get(signal, signal)
