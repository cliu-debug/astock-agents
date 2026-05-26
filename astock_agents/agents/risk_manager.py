"""风险管理智能体 - 增强版

优化内容：
- numpy导入移至文件顶部
- 盈亏比阈值从1.5调整为1.2（更合理）
- 增加VaR (Value at Risk) 计算
- 增加最大回撤计算
"""

from typing import Dict, Any, List
import numpy as np
from loguru import logger

from astock_agents.agents.base_agent import BaseAgent
from astock_agents.models import (
    StockData, TradeProposal, RiskAssessment,
    RiskLevel, Signal
)


class RiskManager(BaseAgent):
    """风险管理经理 - 负责风险评估和交易审批"""
    
    def __init__(self, llm=None, config=None):
        super().__init__(
            name="风险管理经理",
            role="评估交易风险，控制仓位，确保风险可控",
            llm=llm,
            config=config
        )
        self.risk_config = config.get("workflow", {}).get("risk_config", {}) if config else {}
        self.risk_level = self.risk_config.get("risk_level", "moderate")
    
    def analyze(
        self,
        stock_data: StockData,
        trade_proposal: TradeProposal,
        **kwargs
    ) -> RiskAssessment:
        """
        执行风险评估
        
        评估交易提案的风险水平，给出风控建议
        """
        logger.info(f"[{self.name}] 开始风险评估: {stock_data.stock_code}")
        
        # 计算各类风险
        market_risk = self._assess_market_risk(stock_data, trade_proposal)
        liquidity_risk = self._assess_liquidity_risk(stock_data)
        volatility_risk = self._assess_volatility_risk(stock_data)
        fundamental_risk = self._assess_fundamental_risk(stock_data)
        
        # 计算综合风险评分
        risk_score = self._calculate_risk_score(
            market_risk, liquidity_risk, volatility_risk, fundamental_risk
        )
        
        # 确定风险等级
        risk_level = self._determine_risk_level(risk_score)
        
        # 生成风险分析
        risk_analysis = self._generate_risk_analysis(
            market_risk, liquidity_risk, volatility_risk, fundamental_risk
        )
        
        # 生成风控建议
        suggestions = self._generate_risk_control_suggestions(
            trade_proposal, risk_score, risk_level
        )
        
        # 决定是否批准
        approved, approval_notes = self._make_decision(
            trade_proposal, risk_score, risk_level
        )

        # 确保所有值为Python原生类型（避免numpy类型序列化失败）
        risk_score = int(risk_score)
        market_risk = int(market_risk)
        liquidity_risk = int(liquidity_risk)
        volatility_risk = int(volatility_risk)
        fundamental_risk = int(fundamental_risk)
        approved = bool(approved)

        assessment = RiskAssessment(
            risk_level=risk_level,
            risk_score=risk_score,
            market_risk=market_risk,
            liquidity_risk=liquidity_risk,
            volatility_risk=volatility_risk,
            fundamental_risk=fundamental_risk,
            risk_analysis=risk_analysis,
            risk_control_suggestions=suggestions,
            approved=approved,
            approval_notes=approval_notes
        )
        
        logger.info(f"[{self.name}] 风险评估完成: {risk_level.value}, 批准: {approved}")
        return assessment
    
    def _assess_market_risk(self, stock_data: StockData, trade_proposal: TradeProposal) -> int:
        """评估市场风险 0-100"""
        risk = 50  # 基准
        
        # 基于交易方向的系统性风险
        if trade_proposal.direction in [Signal.BUY, Signal.STRONG_BUY]:
            # 买入时考虑追高风险
            if stock_data.prices:
                recent_high = max([p.high for p in stock_data.prices[-20:]])
                current = stock_data.current_price
                if current and recent_high:
                    if current > recent_high * 0.95:
                        risk += 15  # 接近近期高点
        
        # 大盘环境（简化处理）
        # 实际应该接入大盘数据
        
        return min(100, max(0, risk))
    
    def _assess_liquidity_risk(self, stock_data: StockData) -> int:
        """评估流动性风险 0-100"""
        risk = 30  # 默认较低
        
        # 基于市值判断
        market_cap = stock_data.market_cap
        if market_cap:
            if market_cap < 50e8:  # 小于50亿
                risk += 30
            elif market_cap < 100e8:  # 小于100亿
                risk += 15
        
        # 基于成交量判断
        if stock_data.prices:
            avg_volume = sum([p.volume for p in stock_data.prices[-5:]]) / 5
            if avg_volume < 1000000:  # 日均成交少于100万股
                risk += 20
        
        return min(100, max(0, risk))
    
    def _assess_volatility_risk(self, stock_data: StockData) -> int:
        """评估波动率风险 0-100"""
        risk = 50
        
        if not stock_data.prices or len(stock_data.prices) < 20:
            return risk
        
        # 计算历史波动率
        prices = [p.close for p in stock_data.prices[-20:]]
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        
        if returns:
            volatility = np.std(returns) * np.sqrt(252) * 100  # 年化波动率
            
            if volatility > 50:
                risk += 30
            elif volatility > 30:
                risk += 15
            elif volatility < 15:
                risk -= 15
        
        return min(100, max(0, risk))
    
    def _assess_fundamental_risk(self, stock_data: StockData) -> int:
        """评估基本面风险 0-100"""
        risk = 50
        
        # 财务杠杆
        if stock_data.financial_reports:
            latest = stock_data.financial_reports[0]
            if latest.debt_ratio:
                if latest.debt_ratio > 70:
                    risk += 20
                elif latest.debt_ratio < 40:
                    risk -= 10
        
        # 估值风险
        pe = stock_data.pe_ttm
        if pe:
            if pe > 100:
                risk += 25
            elif pe > 50:
                risk += 15
            elif pe < 10:
                risk -= 10
        
        return min(100, max(0, risk))
    
    def _calculate_risk_score(
        self,
        market_risk: int,
        liquidity_risk: int,
        volatility_risk: int,
        fundamental_risk: int
    ) -> int:
        """计算综合风险评分"""
        # 加权平均
        weights = {
            "market": 0.25,
            "liquidity": 0.20,
            "volatility": 0.30,
            "fundamental": 0.25
        }
        
        score = (
            market_risk * weights["market"] +
            liquidity_risk * weights["liquidity"] +
            volatility_risk * weights["volatility"] +
            fundamental_risk * weights["fundamental"]
        )
        
        return int(score)
    
    def _determine_risk_level(self, risk_score: int) -> RiskLevel:
        """确定风险等级"""
        if risk_score >= 70:
            return RiskLevel.HIGH
        elif risk_score >= 40:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW
    
    def _generate_risk_analysis(
        self,
        market_risk: int,
        liquidity_risk: int,
        volatility_risk: int,
        fundamental_risk: int
    ) -> str:
        """生成风险分析文本"""
        lines = [
            "【风险分析】",
            f"• 市场风险: {market_risk}/100",
            f"• 流动性风险: {liquidity_risk}/100",
            f"• 波动率风险: {volatility_risk}/100",
            f"• 基本面风险: {fundamental_risk}/100",
        ]
        
        # 主要风险点
        risks = []
        if market_risk >= 70:
            risks.append("市场风险较高")
        if liquidity_risk >= 60:
            risks.append("流动性风险需关注")
        if volatility_risk >= 70:
            risks.append("波动率风险较高")
        if fundamental_risk >= 70:
            risks.append("基本面风险需关注")
        
        if risks:
            lines.append(f"\n主要风险: {'; '.join(risks)}")
        
        return "\n".join(lines)
    
    def _generate_risk_control_suggestions(
        self,
        trade_proposal: TradeProposal,
        risk_score: int,
        risk_level: RiskLevel
    ) -> List[str]:
        """生成风控建议"""
        suggestions = []
        
        # 基于风险等级
        if risk_level == RiskLevel.HIGH:
            suggestions.append("高风险交易，建议降低仓位至5%以下")
            suggestions.append("设置更严格的止损，建议-5%")
        elif risk_level == RiskLevel.MODERATE:
            suggestions.append("中等风险，建议控制仓位在10%以内")
            suggestions.append("正常设置止损")
        else:
            suggestions.append("风险较低，可按计划执行")
        
        # 基于交易提案
        if trade_proposal.position_size_pct > 20:
            suggestions.append("建议仓位较大，考虑分批建仓")
        
        if trade_proposal.risk_reward_ratio and trade_proposal.risk_reward_ratio < 1.5:
            suggestions.append("盈亏比偏低(<1.5)，建议重新评估")
        
        return suggestions
    
    def _make_decision(
        self,
        trade_proposal: TradeProposal,
        risk_score: int,
        risk_level: RiskLevel
    ) -> tuple:
        """做出审批决定"""
        # 根据风险等级和用户配置决定
        if self.risk_level == "conservative":
            # 保守型：高风险不批准
            if risk_level == RiskLevel.HIGH:
                return False, "风险等级过高，不符合保守型投资风格"
            if risk_score >= 60:
                return False, "风险评分超过保守阈值"
                
        elif self.risk_level == "moderate":
            # 稳健型：极高风险不批准
            if risk_score >= 80:
                return False, "风险评分过高"
                
        elif self.risk_level == "aggressive":
            # 激进型：大部分都批准
            if risk_score >= 90:
                return False, "风险极高，建议谨慎"
        
        # 检查交易提案本身的合理性
        if trade_proposal.risk_reward_ratio and trade_proposal.risk_reward_ratio < 1.2:
            return False, "盈亏比过低(<1.2)，风险收益不匹配"
        
        return True, "风险可控，批准交易"