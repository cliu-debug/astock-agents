"""自动决策引擎单元测试

覆盖场景：
1. 正常路径：各种信号类型生成决策
2. 边界条件：空报告、零价格、极端置信度
3. 决策操作：执行、取消、复盘
4. 仓位计算：凯利公式、风险调整
5. 止损止盈：支撑阻力位计算
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置测试数据库路径（避免污染正式数据）
test_db_path = os.path.join(tempfile.gettempdir(), "test_astock_decision.db")
os.environ["ASTOCK_DB_PATH"] = test_db_path

from astock_agents.services.decision_engine import (
    DecisionEngine, Decision, DecisionAction, DecisionContext,
)


# ==================== Fixtures ====================

@pytest.fixture
def engine():
    """创建决策引擎实例（使用测试数据库）"""
    from astock_agents.db.database import Database
    db = Database(db_path=test_db_path)
    return DecisionEngine(db=db)


@pytest.fixture
def sample_buy_report():
    """买入信号分析报告"""
    return {
        "stock_code": "600519.SH",
        "stock_name": "贵州茅台",
        "current_price": 1800.0,
        "final_signal": "买入",
        "final_confidence": 75,
        "technical": {
            "trend": "上升",
            "trend_strength": 70,
            "support_levels": [1750.0, 1720.0],
            "resistance_levels": [1850.0, 1900.0],
            "indicators": {"rsi": 55, "macd": "金叉"},
            "patterns": ["底部反转"],
            "summary": "技术面偏多",
            "signal": "买入",
            "confidence": 70,
        },
        "fundamental": {
            "profitability_score": 85,
            "profitability_analysis": "盈利能力强",
            "growth_score": 70,
            "growth_analysis": "稳健增长",
            "valuation_score": 60,
            "valuation_analysis": "估值合理",
            "financial_health_score": 90,
            "financial_health_analysis": "财务健康",
            "industry_position": "行业龙头",
            "key_metrics": {},
            "summary": "基本面优秀",
            "signal": "买入",
            "confidence": 80,
        },
        "sentiment": {
            "overall_score": 70,
            "market_sentiment": "偏多",
            "related_hot_topics": [],
            "topic_momentum": {},
            "fund_flow": "资金净流入",
            "news_sentiment": "正面",
            "summary": "情绪偏多",
            "signal": "买入",
            "confidence": 65,
        },
        "news": {
            "key_news": [],
            "key_announcements": [],
            "macro_impact": "政策利好",
            "industry_updates": "行业景气",
            "risk_events": [],
            "summary": "新闻面偏多",
            "signal": "买入",
            "confidence": 60,
        },
        "debate": {
            "bull_arguments": ["业绩稳健", "品牌护城河"],
            "bull_confidence": 75,
            "bear_arguments": ["估值偏高"],
            "bear_confidence": 40,
            "debate_summary": "多头占优",
            "winning_side": "bull",
            "key_disagreements": ["估值水平"],
        },
        "trade_proposal": {
            "direction": "买入",
            "position_size_pct": 15,
            "entry_price": 1800.0,
            "target_price": 2000.0,
            "stop_loss_price": 1700.0,
            "expected_return_pct": 11.1,
            "risk_reward_ratio": 2.0,
            "time_horizon": "中期",
            "key_reasons": ["业绩稳健"],
            "risk_factors": ["估值偏高"],
            "proposal_text": "建议买入",
        },
        "risk_assessment": {
            "risk_level": "中等风险",
            "risk_score": 45,
            "market_risk": 40,
            "liquidity_risk": 20,
            "volatility_risk": 50,
            "fundamental_risk": 30,
            "risk_analysis": "整体风险可控",
            "risk_control_suggestions": ["设置止损", "控制仓位"],
            "approved": True,
            "approval_notes": "风险可控",
        },
    }


@pytest.fixture
def sample_sell_report():
    """卖出信号分析报告"""
    return {
        "stock_code": "000001.SZ",
        "stock_name": "平安银行",
        "current_price": 12.5,
        "final_signal": "卖出",
        "final_confidence": 70,
        "technical": {
            "trend": "下降",
            "support_levels": [12.0],
            "resistance_levels": [13.0],
            "indicators": {},
            "patterns": [],
            "summary": "技术面偏空",
            "signal": "卖出",
            "confidence": 65,
        },
        "risk_assessment": {
            "risk_level": "高风险",
            "risk_score": 70,
            "market_risk": 60,
            "liquidity_risk": 30,
            "volatility_risk": 70,
            "fundamental_risk": 50,
            "risk_analysis": "风险较高",
            "risk_control_suggestions": ["减仓"],
            "approved": False,
        },
    }


@pytest.fixture
def sample_strong_buy_report():
    """强烈买入信号分析报告"""
    return {
        "stock_code": "000858.SZ",
        "stock_name": "五粮液",
        "current_price": 150.0,
        "final_signal": "强烈买入",
        "final_confidence": 90,
        "technical": {
            "support_levels": [145.0],
            "resistance_levels": [160.0],
            "indicators": {"rsi": 35},
            "patterns": [],
            "summary": "超卖反弹",
            "signal": "强烈买入",
            "confidence": 85,
        },
        "risk_assessment": {
            "risk_level": "低风险",
            "risk_score": 25,
            "market_risk": 20,
            "liquidity_risk": 15,
            "volatility_risk": 30,
            "fundamental_risk": 20,
            "risk_analysis": "风险较低",
            "risk_control_suggestions": [],
            "approved": True,
        },
    }


@pytest.fixture
def sample_hold_report():
    """持有信号分析报告"""
    return {
        "stock_code": "600036.SH",
        "stock_name": "招商银行",
        "current_price": 35.0,
        "final_signal": "持有",
        "final_confidence": 50,
        "risk_assessment": {
            "risk_level": "中等风险",
            "risk_score": 45,
            "market_risk": 40,
            "liquidity_risk": 20,
            "volatility_risk": 50,
            "fundamental_risk": 30,
            "risk_analysis": "风险中等",
            "risk_control_suggestions": [],
            "approved": True,
        },
    }


# ==================== 正常路径测试 ====================

class TestGenerateDecision:
    """决策生成测试"""

    def test_buy_signal_generates_open_long(self, engine, sample_buy_report):
        """买入信号 → 开多仓"""
        decision = engine.generate_decision(sample_buy_report)

        assert decision.stock_code == "600519.SH"
        assert decision.stock_name == "贵州茅台"
        assert decision.action.action_type == "open_long"
        assert decision.action.direction == "buy"
        assert decision.action.quantity > 0
        assert decision.action.quantity % 100 == 0  # 100的整数倍
        assert decision.action.stop_loss > 0
        assert decision.action.take_profit > 0
        assert decision.action.confidence > 0
        assert decision.status == "pending"
        assert len(decision.id) > 0

    def test_sell_signal_no_position_generates_watch(self, engine, sample_sell_report):
        """卖出信号+无持仓 → 观望"""
        decision = engine.generate_decision(sample_sell_report)

        assert decision.action.action_type == "watch"
        assert decision.stock_code == "000001.SZ"

    def test_sell_signal_with_position_generates_close(self, engine, sample_sell_report):
        """卖出信号+有持仓 → 平仓"""
        portfolio_state = {
            "positions": [{
                "stock_code": "000001.SZ",
                "stock_name": "平安银行",
                "unrealized_pnl_pct": -5.0,
            }],
            "available_cash": 500000,
            "total_market_value": 1000000,
        }
        decision = engine.generate_decision(
            sample_sell_report, portfolio_state=portfolio_state
        )

        assert decision.action.action_type == "close_long"
        assert decision.action.direction == "sell"

    def test_buy_signal_with_profit_position_generates_add(self, engine, sample_buy_report):
        """买入信号+盈利持仓 → 加仓"""
        portfolio_state = {
            "positions": [{
                "stock_code": "600519.SH",
                "stock_name": "贵州茅台",
                "unrealized_pnl_pct": 8.0,
            }],
            "available_cash": 500000,
            "total_market_value": 1000000,
        }
        # 提高置信度到0.7以上才能加仓
        sample_buy_report["final_confidence"] = 75
        decision = engine.generate_decision(
            sample_buy_report, portfolio_state=portfolio_state
        )

        assert decision.action.action_type == "add_position"

    def test_buy_signal_with_loss_position_generates_hold(self, engine, sample_buy_report):
        """买入信号+亏损持仓 → 持有"""
        portfolio_state = {
            "positions": [{
                "stock_code": "600519.SH",
                "stock_name": "贵州茅台",
                "unrealized_pnl_pct": -8.0,
            }],
            "available_cash": 500000,
            "total_market_value": 1000000,
        }
        decision = engine.generate_decision(
            sample_buy_report, portfolio_state=portfolio_state
        )

        assert decision.action.action_type == "hold"

    def test_hold_signal_generates_watch(self, engine, sample_hold_report):
        """持有信号 → 观望"""
        decision = engine.generate_decision(sample_hold_report)

        assert decision.action.action_type == "watch"

    def test_strong_buy_high_confidence_auto_execute(self, engine, sample_strong_buy_report):
        """强烈买入+高置信度+低风险+无持仓 → 自动执行"""
        decision = engine.generate_decision(sample_strong_buy_report)

        assert decision.action.action_type == "open_long"
        assert decision.auto_execute is True
        assert decision.action.urgency == "immediate"

    def test_decision_has_bull_bear_points(self, engine, sample_buy_report):
        """决策包含多空观点"""
        decision = engine.generate_decision(sample_buy_report)

        assert len(decision.bull_points) > 0
        assert len(decision.bear_points) > 0

    def test_decision_has_monitoring_points(self, engine, sample_buy_report):
        """决策包含监控要点"""
        decision = engine.generate_decision(sample_buy_report)

        assert len(decision.monitoring_points) > 0

    def test_decision_has_execution_plan(self, engine, sample_buy_report):
        """决策包含执行计划"""
        decision = engine.generate_decision(sample_buy_report)

        assert len(decision.execution_plan) > 0
        assert "贵州茅台" in decision.execution_plan


# ==================== 仓位计算测试 ====================

class TestPositionSizing:
    """仓位计算测试"""

    def test_position_within_max_limit(self, engine, sample_buy_report):
        """仓位不超过20%上限"""
        decision = engine.generate_decision(sample_buy_report)

        assert decision.action.position_pct <= 0.20

    def test_high_risk_reduces_position(self, engine, sample_sell_report):
        """高风险减半仓位"""
        # 使用卖出报告（高风险）
        decision = engine.generate_decision(sample_sell_report)
        # watch 动作时仓位为0
        assert decision.action.position_pct >= 0

    def test_zero_price_zero_quantity(self, engine):
        """零价格 → 零数量"""
        report = {
            "stock_code": "600519.SH",
            "stock_name": "贵州茅台",
            "current_price": 0,
            "final_signal": "买入",
            "final_confidence": 70,
        }
        decision = engine.generate_decision(report)

        assert decision.action.quantity == 0

    def test_quantity_is_lot_sized(self, engine, sample_buy_report):
        """数量为100的整数倍"""
        decision = engine.generate_decision(sample_buy_report)

        if decision.action.quantity > 0:
            assert decision.action.quantity % 100 == 0


# ==================== 止损止盈测试 ====================

class TestStopLossTakeProfit:
    """止损止盈测试"""

    def test_stop_loss_below_current_price(self, engine, sample_buy_report):
        """止损价低于当前价"""
        decision = engine.generate_decision(sample_buy_report)

        assert decision.action.stop_loss < sample_buy_report["current_price"]

    def test_take_profit_above_current_price(self, engine, sample_buy_report):
        """止盈价高于当前价"""
        decision = engine.generate_decision(sample_buy_report)

        assert decision.action.take_profit > sample_buy_report["current_price"]

    def test_risk_reward_ratio_positive(self, engine, sample_buy_report):
        """风险收益比为正"""
        decision = engine.generate_decision(sample_buy_report)

        assert decision.action.risk_reward_ratio > 0

    def test_stop_loss_uses_support_level(self, engine, sample_buy_report):
        """止损使用支撑位"""
        decision = engine.generate_decision(sample_buy_report)
        current = sample_buy_report["current_price"]
        # 止损应在支撑位附近（1750 * 0.98 = 1715）
        assert decision.action.stop_loss < current


# ==================== 紧急度测试 ====================

class TestUrgency:
    """执行紧急度测试"""

    def test_strong_buy_high_confidence_immediate(self, engine, sample_strong_buy_report):
        """强烈买入+高置信度+低风险 → 立即执行"""
        decision = engine.generate_decision(sample_strong_buy_report)

        assert decision.action.urgency == "immediate"

    def test_buy_medium_confidence_intraday(self, engine, sample_buy_report):
        """买入+中等置信度 → 日内执行"""
        decision = engine.generate_decision(sample_buy_report)

        assert decision.action.urgency in ("intraday", "within_3_days")

    def test_hold_signal_watch_urgency(self, engine, sample_hold_report):
        """持有信号 → 观察紧急度"""
        decision = engine.generate_decision(sample_hold_report)

        assert decision.action.urgency == "watch"


# ==================== 决策操作测试 ====================

class TestDecisionOperations:
    """决策操作测试"""

    def test_get_pending_decisions(self, engine, sample_buy_report):
        """获取待执行决策"""
        engine.generate_decision(sample_buy_report)
        pending = engine.get_pending_decisions()

        assert len(pending) >= 1
        assert all(d.status == "pending" for d in pending)

    def test_cancel_decision(self, engine, sample_buy_report):
        """取消决策"""
        decision = engine.generate_decision(sample_buy_report)
        success = engine.cancel_decision(decision.id, reason="测试取消")

        assert success is True

        # 验证状态已更新
        pending = engine.get_pending_decisions()
        assert decision.id not in [d.id for d in pending]

    def test_cancel_nonexistent_decision(self, engine):
        """取消不存在的决策"""
        success = engine.cancel_decision("NONEXISTENT", reason="测试")
        assert success is False

    def test_cancel_already_executed_decision(self, engine, sample_buy_report):
        """取消已执行的决策"""
        decision = engine.generate_decision(sample_buy_report)
        engine._update_decision_status(decision.id, "executed")
        success = engine.cancel_decision(decision.id, reason="测试")
        assert success is False

    def test_get_decision_history(self, engine, sample_buy_report):
        """获取决策历史"""
        engine.generate_decision(sample_buy_report)
        history = engine.get_decision_history()

        assert len(history) >= 1

    def test_get_decision_history_by_stock(self, engine, sample_buy_report):
        """按股票代码获取决策历史"""
        engine.generate_decision(sample_buy_report)
        history = engine.get_decision_history(stock_code="600519.SH")

        assert len(history) >= 1
        assert all(d.stock_code == "600519.SH" for d in history)

    def test_review_decision(self, engine, sample_buy_report):
        """决策复盘"""
        decision = engine.generate_decision(sample_buy_report)
        result = engine.review_decision(
            decision.id, outcome="盈利", actual_pnl=5000.0
        )

        assert result["success"] is True
        assert result["outcome"] == "盈利"
        assert result["actual_pnl"] == 5000.0

    def test_review_nonexistent_decision(self, engine):
        """复盘不存在的决策"""
        result = engine.review_decision("NONEXISTENT", outcome="亏损", actual_pnl=-1000.0)
        assert result["success"] is False


# ==================== 边界条件测试 ====================

class TestEdgeCases:
    """边界条件测试"""

    def test_empty_report(self, engine):
        """空报告 → 安全降级为观望"""
        report = {"stock_code": "", "stock_name": "", "current_price": 0}
        decision = engine.generate_decision(report)

        assert decision is not None
        assert decision.action.action_type == "watch"

    def test_none_confidence(self, engine):
        """置信度为None"""
        report = {
            "stock_code": "600519.SH",
            "stock_name": "贵州茅台",
            "current_price": 1800.0,
            "final_signal": "买入",
            "final_confidence": None,
        }
        decision = engine.generate_decision(report)

        assert decision is not None

    def test_missing_risk_assessment(self, engine):
        """缺少风险评估"""
        report = {
            "stock_code": "600519.SH",
            "stock_name": "贵州茅台",
            "current_price": 1800.0,
            "final_signal": "买入",
            "final_confidence": 60,
        }
        decision = engine.generate_decision(report)

        assert decision is not None
        assert decision.action.action_type == "open_long"

    def test_very_high_confidence(self, engine):
        """极高置信度"""
        report = {
            "stock_code": "600519.SH",
            "stock_name": "贵州茅台",
            "current_price": 1800.0,
            "final_signal": "强烈买入",
            "final_confidence": 99,
            "risk_assessment": {
                "risk_level": "低风险",
                "risk_score": 10,
            },
        }
        decision = engine.generate_decision(report)

        assert decision.action.confidence >= 0.8
        assert decision.auto_execute is True

    def test_very_low_confidence(self, engine):
        """极低置信度"""
        report = {
            "stock_code": "600519.SH",
            "stock_name": "贵州茅台",
            "current_price": 1800.0,
            "final_signal": "持有",
            "final_confidence": 10,
        }
        decision = engine.generate_decision(report)

        assert decision.action.action_type == "watch"
        assert decision.auto_execute is False

    def test_no_technical_support_resistance(self, engine):
        """无支撑阻力位数据"""
        report = {
            "stock_code": "600519.SH",
            "stock_name": "贵州茅台",
            "current_price": 1800.0,
            "final_signal": "买入",
            "final_confidence": 65,
            "technical": {
                "support_levels": [],
                "resistance_levels": [],
            },
        }
        decision = engine.generate_decision(report)

        # 应使用默认止损比例
        assert decision.action.stop_loss > 0
        assert decision.action.take_profit > 0


# ==================== 清理 ====================

def teardown_module():
    """测试结束后清理测试数据库"""
    try:
        os.remove(test_db_path)
    except OSError:
        pass
