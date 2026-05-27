"""分析报告模型"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class Signal(str, Enum):
    """交易信号"""
    STRONG_BUY = "强烈买入"
    BUY = "买入"
    HOLD = "持有"
    SELL = "卖出"
    STRONG_SELL = "强烈卖出"


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "低风险"
    MODERATE = "中等风险"
    HIGH = "高风险"


class TechnicalAnalysis(BaseModel):
    """技术分析结果"""
    trend: str = Field(..., description="趋势判断: 上升/下降/震荡")
    trend_strength: int = Field(..., ge=0, le=100, description="趋势强度 0-100")
    
    # 关键价格
    support_levels: List[float] = Field(default_factory=list, description="支撑位")
    resistance_levels: List[float] = Field(default_factory=list, description="阻力位")
    
    # 技术指标解读
    indicators: Dict[str, Any] = Field(default_factory=dict, description="技术指标数据")
    
    # 形态识别
    patterns: List[str] = Field(default_factory=list, description="识别出的K线形态")
    
    # 分析摘要
    summary: str = Field(..., description="技术分析总结")
    
    # 信号
    signal: Signal = Field(..., description="技术信号")
    confidence: int = Field(..., ge=0, le=100, description="置信度")


class FundamentalAnalysis(BaseModel):
    """基本面分析结果"""
    # 盈利能力
    profitability_score: int = Field(..., ge=0, le=100, description="盈利能力评分")
    profitability_analysis: str = Field(..., description="盈利能力分析")
    
    # 成长性
    growth_score: int = Field(..., ge=0, le=100, description="成长性评分")
    growth_analysis: str = Field(..., description="成长性分析")
    
    # 估值水平
    valuation_score: int = Field(..., ge=0, le=100, description="估值评分")
    valuation_analysis: str = Field(..., description="估值分析")
    
    # 财务健康
    financial_health_score: int = Field(..., ge=0, le=100, description="财务健康评分")
    financial_health_analysis: str = Field(..., description="财务健康分析")
    
    # 行业地位
    industry_position: str = Field(..., description="行业地位")
    
    # 关键财务数据
    key_metrics: Dict[str, Any] = Field(default_factory=dict, description="关键指标")
    
    # 分析摘要
    summary: str = Field(..., description="基本面分析总结")
    
    # 信号
    signal: Signal = Field(..., description="基本面信号")
    confidence: int = Field(..., ge=0, le=100, description="置信度")


class SentimentAnalysis(BaseModel):
    """情绪分析结果"""
    # 情绪评分
    overall_score: int = Field(..., ge=0, le=100, description="整体情绪评分")
    market_sentiment: str = Field(..., description="市场情绪描述")
    
    # 热点相关
    related_hot_topics: List[str] = Field(default_factory=list, description="相关热点")
    topic_momentum: Dict[str, float] = Field(default_factory=dict, description="题材动量")
    
    # 资金流向
    fund_flow: str = Field(..., description="资金流向分析")
    
    # 舆情数据
    news_sentiment: str = Field(..., description="新闻情绪")
    social_sentiment: Optional[str] = None  # 社交媒体情绪
    
    # 分析摘要
    summary: str = Field(..., description="情绪分析总结")
    
    # 信号
    signal: Signal = Field(..., description="情绪信号")
    confidence: int = Field(..., ge=0, le=100, description="置信度")


class NewsAnalysis(BaseModel):
    """新闻分析结果"""
    # 重要新闻
    key_news: List[Dict[str, Any]] = Field(default_factory=list, description="关键新闻")
    
    # 公告解读
    key_announcements: List[Dict[str, Any]] = Field(default_factory=list, description="重要公告")
    
    # 宏观/政策影响
    macro_impact: str = Field(..., description="宏观政策影响")
    
    # 行业动态
    industry_updates: str = Field(..., description="行业动态")
    
    # 风险事件
    risk_events: List[Dict[str, str]] = Field(default_factory=list, description="风险事件（含等级）")
    
    # 分析摘要
    summary: str = Field(..., description="新闻分析总结")
    
    # 信号
    signal: Signal = Field(..., description="新闻信号")
    confidence: int = Field(..., ge=0, le=100, description="置信度")


class DebateResult(BaseModel):
    """辩论结果"""
    # 多头观点
    bull_arguments: List[str] = Field(default_factory=list, description="多头论据")
    bull_confidence: int = Field(..., ge=0, le=100, description="多头置信度")

    # 空头观点
    bear_arguments: List[str] = Field(default_factory=list, description="空头论据")
    bear_confidence: int = Field(..., ge=0, le=100, description="空头置信度")

    # 辩论结论
    debate_summary: str = Field(..., description="辩论总结")
    winning_side: str = Field(..., description="获胜方: bull/bear/neutral")

    # 关键分歧点
    key_disagreements: List[str] = Field(default_factory=list, description="关键分歧")

    # LLM增强字段
    bull_thesis: Optional[str] = Field(default=None, description="LLM生成的多头论证")
    bear_thesis: Optional[str] = Field(default=None, description="LLM生成的空头论证")

    # 博弈论增强字段
    debate_rounds: int = Field(default=1, description="辩论轮数")
    debate_history: List[Dict[str, Any]] = Field(default_factory=list, description="辩论历史记录")
    votes: Dict[str, str] = Field(default_factory=dict, description="各分析师投票结果")
    cooperation_score: float = Field(default=0.5, ge=0.0, le=1.0, description="合作度评分(0-1)")
    nash_equilibrium: Optional[str] = Field(default=None, description="纳什均衡分析")


class TradeProposal(BaseModel):
    """交易提案"""
    # 交易方向
    direction: Signal = Field(..., description="交易方向")
    
    # 仓位建议
    position_size_pct: float = Field(..., description="建议仓位百分比")
    
    # 价格区间
    entry_price: Optional[float] = None  # 入场价格
    target_price: Optional[float] = None  # 目标价格
    stop_loss_price: Optional[float] = None  # 止损价格
    
    # 预期收益/风险
    expected_return_pct: Optional[float] = None  # 预期收益率
    risk_reward_ratio: Optional[float] = None  # 盈亏比
    
    # 时间框架
    time_horizon: str = Field(..., description="时间框架: 短期/中期/长期")
    
    # 核心理由
    key_reasons: List[str] = Field(default_factory=list, description="核心理由")
    
    # 风险提示
    risk_factors: List[str] = Field(default_factory=list, description="风险因素")
    
    # 提案说明
    proposal_text: str = Field(..., description="完整提案文本")

    # LLM增强字段
    rationale: Optional[str] = Field(default=None, description="LLM生成的交易决策逻辑说明")


class RiskAssessment(BaseModel):
    """风险评估"""
    # 风险等级
    risk_level: RiskLevel = Field(..., description="风险等级")
    risk_score: int = Field(..., ge=0, le=100, description="风险评分")
    
    # 各类风险
    market_risk: int = Field(..., ge=0, le=100, description="市场风险")
    liquidity_risk: int = Field(..., ge=0, le=100, description="流动性风险")
    volatility_risk: int = Field(..., ge=0, le=100, description="波动率风险")
    fundamental_risk: int = Field(..., ge=0, le=100, description="基本面风险")
    
    # 风险分析
    risk_analysis: str = Field(..., description="风险分析")
    
    # 风控建议
    risk_control_suggestions: List[str] = Field(default_factory=list, description="风控建议")
    
    # 是否批准交易
    approved: bool = Field(..., description="是否批准")
    approval_notes: Optional[str] = None  # 审批意见

    # LLM增强字段
    qualitative_notes: Optional[str] = Field(default=None, description="LLM生成的定性风险评估说明")


class AnalysisReport(BaseModel):
    """完整分析报告"""
    # 基本信息
    stock_code: str
    stock_name: str
    analysis_date: datetime = Field(default_factory=datetime.now)
    current_price: Optional[float] = None
    
    # 各维度分析
    technical: Optional[TechnicalAnalysis] = None
    fundamental: Optional[FundamentalAnalysis] = None
    sentiment: Optional[SentimentAnalysis] = None
    news: Optional[NewsAnalysis] = None
    
    # 辩论结果
    debate: Optional[DebateResult] = None
    
    # 交易提案
    trade_proposal: Optional[TradeProposal] = None
    
    # 风险评估
    risk_assessment: Optional[RiskAssessment] = None
    
    # 最终决策
    final_signal: Optional[Signal] = None
    final_confidence: Optional[int] = None
    
    # 完整报告文本
    full_report: Optional[str] = None
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # 错误收集
    errors: List[str] = Field(default_factory=list, description="分析过程中的错误/警告")
    
    def generate_summary(self) -> str:
        """生成报告摘要"""
        lines = [
            f"【{self.stock_name} ({self.stock_code})】分析报告",
            f"分析时间: {self.analysis_date.strftime('%Y-%m-%d %H:%M')}",
            f"当前价格: {self.current_price}",
            "",
        ]
        
        if self.final_signal:
            lines.append(f"最终信号: {self.final_signal.value}")
        
        if self.trade_proposal:
            lines.append(f"交易建议: {self.trade_proposal.direction.value}")
            lines.append(f"建议仓位: {self.trade_proposal.position_size_pct}%")
        
        return "\n".join(lines)