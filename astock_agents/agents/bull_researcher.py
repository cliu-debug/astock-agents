"""多头研究员智能体"""

from typing import Dict, Any, List
from loguru import logger

from astock_agents.agents.base_agent import BaseAgent
from astock_agents.models import (
    StockData, TechnicalAnalysis, FundamentalAnalysis,
    SentimentAnalysis, NewsAnalysis, DebateResult
)


class BullResearcher(BaseAgent):
    """多头研究员 - 负责构建看多逻辑"""
    
    def __init__(self, llm=None, config=None):
        super().__init__(
            name="多头研究员",
            role="从分析师报告中寻找买入理由，构建看多逻辑",
            llm=llm,
            config=config
        )
    
    def analyze(
        self,
        stock_data: StockData,
        technical: TechnicalAnalysis,
        fundamental: FundamentalAnalysis,
        sentiment: SentimentAnalysis,
        news: NewsAnalysis,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行多头研究
        
        从各维度分析中提取看多论据
        """
        logger.info(f"[{self.name}] 开始多头研究: {stock_data.stock_code}")
        
        arguments = []
        confidence = 50
        
        # 技术面看多论据
        tech_args = self._extract_bullish_technical(technical)
        arguments.extend(tech_args)
        
        # 基本面看多论据
        fund_args = self._extract_bullish_fundamental(fundamental)
        arguments.extend(fund_args)
        
        # 情绪面看多论据
        sent_args = self._extract_bullish_sentiment(sentiment)
        arguments.extend(sent_args)
        
        # 新闻面看多论据
        news_args = self._extract_bullish_news(news)
        arguments.extend(news_args)
        
        # 计算置信度
        confidence = self._calculate_confidence(
            technical, fundamental, sentiment, news
        )
        
        result = {
            "arguments": arguments,
            "confidence": confidence,
            "argument_count": len(arguments)
        }

        # LLM增强分析：从看多角度论证买入理由
        if self.llm:
            try:
                opponent_context = kwargs.get("opponent_context")
                llm_thesis = self._llm_generate_bull_thesis(
                    stock_data, technical, fundamental, sentiment, news, arguments,
                    opponent_context=opponent_context
                )
                if llm_thesis.get("bull_thesis"):
                    result["bull_thesis"] = llm_thesis["bull_thesis"]
            except Exception as e:
                logger.warning(f"[{self.name}] LLM增强分析失败，使用规则引擎结果: {e}")

        logger.info(f"[{self.name}] 多头研究完成，发现{len(arguments)}条看多论据")
        return result
    
    def _extract_bullish_technical(self, technical: TechnicalAnalysis) -> List[str]:
        """提取技术面看多论据"""
        args = []
        
        if technical.signal.value in ["买入", "强烈买入"]:
            args.append(f"技术指标发出{technical.signal.value}信号")
        
        if technical.trend == "上升趋势":
            args.append(f"处于{technical.trend}，趋势强度{technical.trend_strength}%")
        
        if technical.patterns:
            bullish_patterns = [p for p in technical.patterns if "金叉" in p or "突破" in p or "底部" in p]
            for pattern in bullish_patterns:
                args.append(f"技术形态: {pattern}")
        
        # RSI
        rsi = technical.indicators.get('rsi', {}).get('value')
        if rsi and rsi < 30:
            args.append(f"RSI超卖({rsi})，存在反弹机会")
        
        # MACD
        macd_hist = technical.indicators.get('macd', {}).get('histogram', 0)
        if macd_hist > 0:
            args.append("MACD柱状图为正，动能向上")
        
        return args
    
    def _extract_bullish_fundamental(self, fundamental: FundamentalAnalysis) -> List[str]:
        """提取基本面看多论据"""
        args = []
        
        if fundamental.signal.value in ["买入", "强烈买入"]:
            args.append(f"基本面发出{fundamental.signal.value}信号")
        
        # 盈利能力
        if fundamental.profitability_score >= 70:
            args.append(f"盈利能力优秀({fundamental.profitability_score}分)")
        
        # 估值
        if fundamental.valuation_score >= 70:
            args.append(f"估值具有吸引力({fundamental.valuation_score}分)")
        
        # 财务健康
        if fundamental.financial_health_score >= 70:
            args.append(f"财务状况稳健({fundamental.financial_health_score}分)")
        
        # 关键指标
        metrics = fundamental.key_metrics
        pe = metrics.get('pe_ttm')
        if pe and pe < 15:
            args.append(f"PE估值较低({pe:.1f})，安全边际充足")
        
        pb = metrics.get('pb')
        if pb and pb < 1:
            args.append(f"PB破净({pb:.2f})，价值被低估")
        
        roe = metrics.get('roe')
        if roe and roe > 15:
            args.append(f"ROE优秀({roe:.1f}%)，股东回报高")
        
        return args
    
    def _extract_bullish_sentiment(self, sentiment: SentimentAnalysis) -> List[str]:
        """提取情绪面看多论据"""
        args = []
        
        if sentiment.signal.value in ["买入", "强烈买入"]:
            args.append(f"市场情绪支持{sentiment.signal.value}")
        
        if sentiment.overall_score >= 70:
            args.append(f"市场情绪高涨({sentiment.overall_score}分)")
        
        if sentiment.related_hot_topics:
            args.append(f"涉及{len(sentiment.related_hot_topics)}个热点题材")
        
        if "流入" in sentiment.fund_flow:
            args.append(f"资金面向好: {sentiment.fund_flow}")
        
        return args
    
    def _extract_bullish_news(self, news: NewsAnalysis) -> List[str]:
        """提取新闻面看多论据"""
        args = []
        
        if news.signal.value in ["买入", "强烈买入"]:
            args.append(f"新闻面发出{news.signal.value}信号")
        
        # 公告活跃
        if len(news.key_announcements) > 5:
            args.append(f"公司公告活跃({len(news.key_announcements)}条)，透明度高")
        
        # 无重大风险
        if not news.risk_events:
            args.append("未发现重大风险事件")
        
        return args
    
    def _calculate_confidence(
        self,
        technical: TechnicalAnalysis,
        fundamental: FundamentalAnalysis,
        sentiment: SentimentAnalysis,
        news: NewsAnalysis
    ) -> int:
        """计算看多置信度"""
        # 所有维度的置信度（无论信号方向）
        all_confidences = [
            technical.confidence,
            fundamental.confidence,
            sentiment.confidence,
            news.confidence,
        ]

        # 买入信号的置信度
        buy_confidences = [
            technical.confidence if technical.signal.value in ["买入", "强烈买入"] else 0,
            fundamental.confidence if fundamental.signal.value in ["买入", "强烈买入"] else 0,
            sentiment.confidence if sentiment.signal.value in ["买入", "强烈买入"] else 0,
            news.confidence if news.signal.value in ["买入", "强烈买入"] else 0,
        ]

        # 基础分：所有维度置信度均值的30%
        base_score = sum(all_confidences) / len(all_confidences) * 0.3

        # 买入信号加权
        buy_score = sum(buy_confidences) / len(buy_confidences) * 0.5

        # 信号数量加权
        buy_signals = sum(1 for s in [technical.signal, fundamental.signal, sentiment.signal, news.signal]
                         if s.value in ["买入", "强烈买入"])
        bonus = buy_signals * 5

        return min(100, int(base_score + buy_score + bonus))

    def _llm_generate_bull_thesis(
        self,
        stock_data: StockData,
        technical: TechnicalAnalysis,
        fundamental: FundamentalAnalysis,
        sentiment: SentimentAnalysis,
        news: NewsAnalysis,
        arguments: List[str],
        opponent_context: str = None
    ) -> Dict[str, str]:
        """
        使用LLM从看多角度论证买入理由

        LLM必须引用其他智能体的具体数据

        Args:
            stock_data: 股票数据
            technical: 技术分析结果
            fundamental: 基本面分析结果
            sentiment: 情绪分析结果
            news: 新闻分析结果
            arguments: 规则引擎已提取的看多论据
            opponent_context: 对手（空头）上一轮的论点摘要

        Returns:
            LLM结构化输出字典
        """
        # 构建数据摘要（引用其他智能体的具体数据）
        data_parts = [
            f"股票={stock_data.stock_name}({stock_data.stock_code})",
            f"当前价格={stock_data.current_price}",
            f"技术信号={technical.signal.value}",
            f"趋势={technical.trend}",
            f"趋势强度={technical.trend_strength}",
            f"RSI={technical.indicators.get('rsi', {}).get('value', 'N/A')}",
            f"MACD趋势={technical.indicators.get('macd', {}).get('trend', 'N/A')}",
            f"基本面信号={fundamental.signal.value}",
            f"盈利能力评分={fundamental.profitability_score}",
            f"估值评分={fundamental.valuation_score}",
            f"PE={fundamental.key_metrics.get('pe_ttm', 'N/A')}",
            f"ROE={fundamental.key_metrics.get('roe', 'N/A')}",
            f"情绪信号={sentiment.signal.value}",
            f"情绪评分={sentiment.overall_score}",
            f"资金流向={sentiment.fund_flow}",
            f"新闻信号={news.signal.value}",
            f"风险事件数={len(news.risk_events)}",
        ]

        if arguments:
            data_parts.append(f"已有看多论据={'；'.join(arguments[:5])}")

        # 添加对手论点上下文（多轮辩论时使用）
        if opponent_context:
            data_parts.append(f"空头上一轮论点={opponent_context}")

        data_summary = ", ".join(data_parts)

        instruction = (
            f"基于以上各分析师的具体数据，从看多角度为{stock_data.stock_name}构建买入论证。"
        )
        if opponent_context:
            instruction += "请回应空头的论点，指出其不足或遗漏之处。"
        instruction += (
            "请引用具体数据（如'技术指标RSI=30超卖'、'PE=12估值偏低'等），"
            "给出有说服力的看多逻辑。所有论据必须基于提供的数据，不得编造。"
        )

        output_fields = ["bull_thesis", "key_data_references", "risk_acknowledgment"]

        return self._call_llm_with_data(data_summary, instruction, output_fields)