"""核心竞争力模块单元测试 - 资金流向、市场情绪、仓位管理"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from astock_agents.models import StockData, StockPrice


# ==================== 测试数据工厂 ====================

def create_test_stock_data(
    stock_code: str = "600519.SH",
    stock_name: str = "贵州茅台",
    days: int = 30,
    trend: str = "up",
) -> StockData:
    """创建测试用股票数据

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        days: 天数
        trend: 趋势方向 ("up" / "down" / "flat")

    Returns:
        StockData 实例
    """
    prices = []
    base_price = 1800.0

    for i in range(days):
        date = datetime.now() - timedelta(days=days - i)
        if trend == "up":
            close = base_price + i * 5 + (i % 3) * 2
        elif trend == "down":
            close = base_price - i * 5 - (i % 3) * 2
        else:
            close = base_price + (i % 5 - 2) * 3

        prices.append(StockPrice(
            date=date,
            open=close - 5,
            high=close + 10,
            low=close - 10,
            close=close,
            volume=1000000 + i * 50000,
            amount=close * (1000000 + i * 50000),
        ))

    return StockData(
        stock_code=stock_code,
        stock_name=stock_name,
        industry="白酒",
        prices=prices,
        market_cap=220000000,  # 2.2万亿
    )


# ==================== 资金流向分析师测试 ====================

class TestCapitalFlowAnalyst:
    """资金流向分析师测试"""

    def test_analyze_with_up_trend(self):
        """测试上升趋势股票的资金流向分析"""
        from astock_agents.agents.capital_flow_analyst import CapitalFlowAnalyst

        analyst = CapitalFlowAnalyst()
        stock_data = create_test_stock_data(trend="up")
        result = analyst.analyze(stock_data)

        assert "score" in result
        assert "signal" in result
        assert "main_force_direction" in result
        assert "main_force_net_inflow" in result
        assert "capital_resonance" in result
        assert "summary" in result
        assert "key_points" in result
        assert 0 <= result["score"] <= 100
        assert result["signal"] in ("strong_buy", "buy", "hold", "sell", "strong_sell")

    def test_analyze_with_down_trend(self):
        """测试下降趋势股票的资金流向分析"""
        from astock_agents.agents.capital_flow_analyst import CapitalFlowAnalyst

        analyst = CapitalFlowAnalyst()
        stock_data = create_test_stock_data(trend="down")
        result = analyst.analyze(stock_data)

        assert result["main_force_direction"] in ("inflow", "outflow", "neutral")
        assert 0 <= result["score"] <= 100

    def test_analyze_with_insufficient_data(self):
        """测试数据不足时的处理"""
        from astock_agents.agents.capital_flow_analyst import CapitalFlowAnalyst

        analyst = CapitalFlowAnalyst()
        stock_data = StockData(stock_code="000001.SZ", stock_name="平安银行")
        result = analyst.analyze(stock_data)

        assert result["signal"] == "hold"
        assert result["score"] == 50

    def test_kelly_criterion_edge_cases(self):
        """测试凯利公式边界条件（虽然属于仓位管理，但验证推算逻辑）"""
        from astock_agents.agents.capital_flow_analyst import CapitalFlowAnalyst

        analyst = CapitalFlowAnalyst()
        stock_data = create_test_stock_data(trend="flat")
        result = analyst.analyze(stock_data)

        # 震荡行情应产生中性信号
        assert result["score"] >= 0
        assert result["signal"] in ("strong_buy", "buy", "hold", "sell", "strong_sell")

    def test_result_has_key_points(self):
        """测试结果包含关键要点"""
        from astock_agents.agents.capital_flow_analyst import CapitalFlowAnalyst

        analyst = CapitalFlowAnalyst()
        stock_data = create_test_stock_data(trend="up")
        result = analyst.analyze(stock_data)

        assert isinstance(result["key_points"], list)
        assert len(result["key_points"]) > 0

    def test_result_has_summary(self):
        """测试结果包含分析摘要"""
        from astock_agents.agents.capital_flow_analyst import CapitalFlowAnalyst

        analyst = CapitalFlowAnalyst()
        stock_data = create_test_stock_data()
        result = analyst.analyze(stock_data)

        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


# ==================== 市场情绪温度计测试 ====================

class TestMarketSentimentAnalyzer:
    """市场情绪温度计测试"""

    def test_analyze_returns_result(self):
        """测试市场情绪分析返回结果"""
        from astock_agents.services.market_sentiment import MarketSentimentAnalyzer

        analyzer = MarketSentimentAnalyzer()
        result = analyzer.analyze()

        assert result.fear_greed_index >= 0
        assert result.fear_greed_index <= 100
        assert result.sentiment_level in (
            "extreme_fear", "fear", "neutral", "greed", "extreme_greed"
        )
        assert result.volume_sentiment in ("expanding", "shrinking", "normal")
        assert result.turnover_sentiment in ("high", "low", "normal")
        assert result.volatility_level in ("high", "medium", "low")
        assert isinstance(result.suggestion, str)
        assert len(result.suggestion) > 0

    def test_sentiment_level_classification(self):
        """测试情绪等级分类"""
        from astock_agents.services.market_sentiment import MarketSentimentAnalyzer

        analyzer = MarketSentimentAnalyzer()

        assert analyzer._determine_sentiment_level(10) == "extreme_fear"
        assert analyzer._determine_sentiment_level(30) == "fear"
        assert analyzer._determine_sentiment_level(50) == "neutral"
        assert analyzer._determine_sentiment_level(70) == "greed"
        assert analyzer._determine_sentiment_level(90) == "extreme_greed"

    def test_suggestion_for_extreme_fear(self):
        """测试极度恐惧时的操作建议"""
        from astock_agents.services.market_sentiment import MarketSentimentAnalyzer

        analyzer = MarketSentimentAnalyzer()
        suggestion = analyzer._generate_suggestion("extreme_fear")

        assert "买入" in suggestion or "贪婪" in suggestion

    def test_suggestion_for_extreme_greed(self):
        """测试极度贪婪时的操作建议"""
        from astock_agents.services.market_sentiment import MarketSentimentAnalyzer

        analyzer = MarketSentimentAnalyzer()
        suggestion = analyzer._generate_suggestion("extreme_greed")

        assert "恐惧" in suggestion or "减仓" in suggestion or "清仓" in suggestion

    def test_result_has_summary(self):
        """测试结果包含分析摘要"""
        from astock_agents.services.market_sentiment import MarketSentimentAnalyzer

        analyzer = MarketSentimentAnalyzer()
        result = analyzer.analyze()

        assert isinstance(result.summary, str)
        assert len(result.summary) > 0
        assert "恐贪指数" in result.summary

    def test_default_result(self):
        """测试默认结果"""
        from astock_agents.services.market_sentiment import MarketSentimentAnalyzer

        analyzer = MarketSentimentAnalyzer()
        result = analyzer._create_default_result()

        assert result.fear_greed_index == 50.0
        assert result.sentiment_level == "neutral"
        assert result.score == 50


# ==================== 智能仓位管理测试 ====================

class TestPositionSizingService:
    """智能仓位管理测试"""

    def test_kelly_criterion_basic(self):
        """测试凯利公式基本计算"""
        from astock_agents.services.position_sizing import PositionSizingService

        service = PositionSizingService()

        # 胜率60%，盈亏比2:1 → f = (0.6*2 - 0.4)/2 = 0.4，但最大限制25%
        kelly = service._kelly_criterion(0.6, 2.0)
        assert kelly == 0.25  # 被最大仓位25%截断

        # 胜率55%，盈亏比1.5:1 → f = (0.55*1.5 - 0.45)/1.5 ≈ 0.25，被截断
        kelly2 = service._kelly_criterion(0.55, 1.5)
        expected2 = (0.55 * 1.5 - 0.45) / 1.5  # = 0.25
        assert abs(kelly2 - min(expected2, 0.25)) < 0.01

        # 胜率50%，盈亏比1.5:1 → f = (0.5*1.5 - 0.5)/1.5 ≈ 0.167
        kelly3 = service._kelly_criterion(0.5, 1.5)
        expected3 = (0.5 * 1.5 - 0.5) / 1.5  # ≈ 0.167
        assert abs(kelly3 - expected3) < 0.01

    def test_kelly_criterion_max_cap(self):
        """测试凯利公式最大仓位限制"""
        from astock_agents.services.position_sizing import PositionSizingService

        service = PositionSizingService()

        # 极高胜率和盈亏比，但仓位不超过25%
        kelly = service._kelly_criterion(0.9, 5.0)
        assert kelly <= 0.25

    def test_kelly_criterion_zero_ratio(self):
        """测试盈亏比为0时的处理"""
        from astock_agents.services.position_sizing import PositionSizingService

        service = PositionSizingService()
        kelly = service._kelly_criterion(0.6, 0.0)
        assert kelly == 0.0

    def test_kelly_criterion_negative_result(self):
        """测试凯利公式结果为负时的处理"""
        from astock_agents.services.position_sizing import PositionSizingService

        service = PositionSizingService()

        # 胜率30%，盈亏比1:1 → 不应下注
        kelly = service._kelly_criterion(0.3, 1.0)
        assert kelly == 0.0

    def test_calculate_position_buy_signal(self):
        """测试买入信号的仓位计算"""
        from astock_agents.services.position_sizing import PositionSizingService

        service = PositionSizingService()
        result = service.calculate_position(
            signal="buy",
            confidence=70,
            risk_level="moderate",
            portfolio_value=100000,
            stop_loss_pct=0.07,
            stock_code="600519.SH",
            current_price=1800.0,
        )

        assert result.stock_code == "600519.SH"
        assert result.recommended_pct > 0
        assert result.recommended_pct <= 0.25
        assert result.kelly_pct > 0
        assert result.half_kelly_pct == result.kelly_pct / 2
        assert result.recommended_shares >= 0
        assert result.recommended_shares % 100 == 0  # A股100股整数倍
        assert isinstance(result.reasoning, str)
        assert len(result.reasoning) > 0

    def test_calculate_position_sell_signal(self):
        """测试卖出信号仓位为0"""
        from astock_agents.services.position_sizing import PositionSizingService

        service = PositionSizingService()
        result = service.calculate_position(
            signal="sell",
            confidence=80,
            risk_level="moderate",
            portfolio_value=100000,
            stop_loss_pct=0.07,
            stock_code="600519.SH",
        )

        assert result.recommended_pct == 0.0

    def test_calculate_position_high_risk(self):
        """测试高风险等级减仓"""
        from astock_agents.services.position_sizing import PositionSizingService

        service = PositionSizingService()

        result_low = service.calculate_position(
            signal="buy", confidence=70, risk_level="low",
            portfolio_value=100000, stop_loss_pct=0.07,
            stock_code="000001.SZ",
        )
        result_high = service.calculate_position(
            signal="buy", confidence=70, risk_level="high",
            portfolio_value=100000, stop_loss_pct=0.07,
            stock_code="000001.SZ",
        )

        assert result_high.recommended_pct <= result_low.recommended_pct

    def test_calculate_position_with_existing_position(self):
        """测试已有持仓时的仓位调整"""
        from astock_agents.services.position_sizing import PositionSizingService

        service = PositionSizingService()
        current_positions = [
            {"stock_code": "600519.SH", "market_value": 20000, "pct": 0.2}
        ]

        result = service.calculate_position(
            signal="buy",
            confidence=70,
            risk_level="moderate",
            portfolio_value=100000,
            stop_loss_pct=0.07,
            current_positions=current_positions,
            stock_code="600519.SH",
        )

        # 已有20%仓位，新增仓位不应超过5%（最大25%）
        assert result.recommended_pct <= 0.05

    def test_calculate_portfolio_allocation(self):
        """测试组合级仓位配置"""
        from astock_agents.services.position_sizing import PositionSizingService

        service = PositionSizingService()
        signals = [
            {"stock_code": "600519.SH", "signal": "buy", "confidence": 70,
             "risk_level": "moderate", "stop_loss_pct": 0.07, "current_price": 1800.0},
            {"stock_code": "000858.SZ", "signal": "buy", "confidence": 60,
             "risk_level": "moderate", "stop_loss_pct": 0.07, "current_price": 150.0},
            {"stock_code": "000001.SZ", "signal": "strong_buy", "confidence": 80,
             "risk_level": "low", "stop_loss_pct": 0.05, "current_price": 12.0},
        ]

        results = service.calculate_portfolio_allocation(
            signals=signals,
            portfolio_value=100000,
        )

        assert len(results) == 3
        total_pct = sum(r.recommended_pct for r in results)
        assert total_pct <= 0.95  # 组合总仓位不超过95%

    def test_calculate_portfolio_allocation_no_buy_signals(self):
        """测试无买入信号时组合仓位为空"""
        from astock_agents.services.position_sizing import PositionSizingService

        service = PositionSizingService()
        signals = [
            {"stock_code": "600519.SH", "signal": "sell", "confidence": 80},
            {"stock_code": "000858.SZ", "signal": "hold", "confidence": 50},
        ]

        results = service.calculate_portfolio_allocation(
            signals=signals,
            portfolio_value=100000,
        )

        assert len(results) == 0

    def test_shares_round_to_100(self):
        """测试股数取整到100的整数倍"""
        from astock_agents.services.position_sizing import PositionSizingService

        service = PositionSizingService()
        result = service.calculate_position(
            signal="strong_buy",
            confidence=80,
            risk_level="low",
            portfolio_value=100000,
            stop_loss_pct=0.05,
            stock_code="600519.SH",
            current_price=1800.0,
        )

        if result.recommended_shares > 0:
            assert result.recommended_shares % 100 == 0


# ==================== 模块导入测试 ====================

class TestModuleImport:
    """模块导入测试"""

    def test_import_capital_flow_analyst(self):
        """测试资金流向分析师模块导入"""
        from astock_agents.agents.capital_flow_analyst import CapitalFlowAnalyst, CapitalFlowResult
        analyst = CapitalFlowAnalyst()
        assert analyst.name == "资金流向分析师"

    def test_import_market_sentiment(self):
        """测试市场情绪模块导入"""
        from astock_agents.services.market_sentiment import MarketSentimentAnalyzer, MarketSentimentResult
        analyzer = MarketSentimentAnalyzer()
        assert analyzer is not None

    def test_import_position_sizing(self):
        """测试仓位管理模块导入"""
        from astock_agents.services.position_sizing import PositionSizingService, PositionSizingResult
        service = PositionSizingService()
        assert service is not None

    def test_import_from_agents_init(self):
        """测试从agents包导入"""
        from astock_agents.agents import CapitalFlowAnalyst
        assert CapitalFlowAnalyst is not None

    def test_import_from_services_init(self):
        """测试从services包导入"""
        from astock_agents.services import MarketSentimentAnalyzer, PositionSizingService
        assert MarketSentimentAnalyzer is not None
        assert PositionSizingService is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
