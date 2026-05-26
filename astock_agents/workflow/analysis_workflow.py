"""分析工作流 - 使用LangGraph编排多智能体协作，支持并行执行"""

from typing import Dict, Any, Optional, TypedDict, Annotated, List
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

from langgraph.graph import StateGraph, END

from astock_agents.data import DataManager
from astock_agents.agents import (
    TechnicalAnalyst, FundamentalAnalyst, SentimentAnalyst, NewsAnalyst,
    BullResearcher, BearResearcher, Trader, RiskManager
)
from astock_agents.models import (
    StockData, AnalysisReport, TechnicalAnalysis, FundamentalAnalysis,
    SentimentAnalysis, NewsAnalysis, DebateResult, TradeProposal, RiskAssessment
)


class WorkflowState(TypedDict):
    """工作流状态"""
    stock_code: str
    stock_name: str
    stock_data: Optional[StockData]

    # 各维度分析结果
    technical: Optional[TechnicalAnalysis]
    fundamental: Optional[FundamentalAnalysis]
    sentiment: Optional[SentimentAnalysis]
    news: Optional[NewsAnalysis]

    # 辩论结果
    debate_result: Optional[DebateResult]

    # 交易提案
    trade_proposal: Optional[TradeProposal]

    # 风险评估
    risk_assessment_result: Optional[RiskAssessment]

    # 最终报告
    report: Optional[AnalysisReport]

    # 错误收集
    errors: List[str]


class AnalysisWorkflow:
    """
    分析工作流 - 编排多智能体协作完成股票分析

    架构：
    1. 数据获取 -> 2. 并行分析(技术/基本面/情绪/新闻) -> 3. 多空辩论
    -> 4. 交易提案 -> 5. 风险评估 -> 6. 生成报告
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化分析工作流

        Args:
            config: 配置字典
        """
        self.config = config or {}

        # 初始化数据管理器
        self.data_manager = DataManager(config)

        # 初始化各智能体
        self.technical_analyst = TechnicalAnalyst(config=config)
        self.fundamental_analyst = FundamentalAnalyst(config=config)
        self.sentiment_analyst = SentimentAnalyst(config=config)
        self.news_analyst = NewsAnalyst(config=config)
        self.bull_researcher = BullResearcher(config=config)
        self.bear_researcher = BearResearcher(config=config)
        self.trader = Trader(config=config)
        self.risk_manager = RiskManager(config=config)

        # 并行执行线程池
        self._executor = ThreadPoolExecutor(max_workers=4)

        # 构建工作流图
        self.workflow = self._build_workflow()

        logger.info("分析工作流初始化完成")

    def _build_workflow(self) -> StateGraph:
        """构建工作流图 - 使用 fan-out/fan-in 实现并行"""
        workflow = StateGraph(WorkflowState)

        # 添加节点
        workflow.add_node("fetch_data", self._fetch_data_node)
        workflow.add_node("parallel_analysis", self._parallel_analysis_node)
        workflow.add_node("debate", self._debate_node)
        workflow.add_node("generate_proposal", self._generate_proposal_node)
        workflow.add_node("risk_assessment", self._risk_assessment_node)
        workflow.add_node("generate_report", self._generate_report_node)

        # 线性流程：数据获取 -> 并行分析 -> 辩论 -> 提案 -> 风控 -> 报告
        workflow.add_edge("fetch_data", "parallel_analysis")
        workflow.add_edge("parallel_analysis", "debate")
        workflow.add_edge("debate", "generate_proposal")
        workflow.add_edge("generate_proposal", "risk_assessment")
        workflow.add_edge("risk_assessment", "generate_report")
        workflow.add_edge("generate_report", END)

        workflow.set_entry_point("fetch_data")

        return workflow.compile()

    def _fetch_data_node(self, state: WorkflowState) -> WorkflowState:
        """数据获取节点"""
        logger.info(f"[工作流] 获取数据: {state['stock_code']}")

        try:
            stock_data = self.data_manager.get_stock_data(
                stock_code=state["stock_code"],
                stock_name=state["stock_name"],
                days=250
            )

            state["stock_data"] = stock_data
            if stock_data:
                state["stock_name"] = stock_data.stock_name

            logger.info(
                f"[工作流] 数据获取完成: "
                f"{stock_data.stock_name if stock_data else '失败'}"
            )

        except Exception as e:
            error_msg = f"数据获取失败: {str(e)}"
            logger.error(f"[工作流] {error_msg}")
            state["errors"] = state.get("errors", []) + [error_msg]

        return state

    def _parallel_analysis_node(self, state: WorkflowState) -> WorkflowState:
        """
        并行分析节点 - 使用线程池同时执行四个维度的分析

        技术分析、基本面分析、情绪分析、新闻分析互不依赖，
        可以并行执行以提升响应速度
        """
        stock_data = state.get("stock_data")

        if not stock_data:
            error_msg = "无股票数据，跳过并行分析"
            logger.warning(f"[工作流] {error_msg}")
            state["errors"] = state.get("errors", []) + [error_msg]
            return state

        logger.info("[工作流] 开始并行分析（技术/基本面/情绪/新闻）")

        # 定义分析任务
        analysis_tasks = {
            "technical": (self.technical_analyst.analyze, stock_data),
            "fundamental": (self.fundamental_analyst.analyze, stock_data),
            "sentiment": (self.sentiment_analyst.analyze, stock_data),
            "news": (self.news_analyst.analyze, stock_data),
        }

        # 并行执行
        futures = {}
        for name, (func, data) in analysis_tasks.items():
            future = self._executor.submit(func, data)
            futures[future] = name

        # 收集结果
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result(timeout=60)  # 单个分析最多60秒
                state[name] = result
                signal = result.signal.value if hasattr(result, "signal") else "N/A"
                logger.info(f"[工作流] {name} 分析完成: {signal}")
            except Exception as e:
                error_msg = f"{name} 分析失败: {str(e)}"
                logger.error(f"[工作流] {error_msg}")
                state["errors"] = state.get("errors", []) + [error_msg]
                state[name] = None

        completed = sum(1 for k in ["technical", "fundamental", "sentiment", "news"] if state.get(k))
        logger.info(f"[工作流] 并行分析完成: {completed}/4 个维度成功")

        return state

    def _debate_node(self, state: WorkflowState) -> WorkflowState:
        """辩论节点 - 多空辩论"""
        logger.info("[工作流] 执行多空辩论")

        # 至少需要技术分析和基本面分析才能辩论
        has_min_data = state.get("technical") or state.get("fundamental")
        if not has_min_data:
            logger.warning("[工作流] 缺少核心分析数据，跳过辩论")
            state["errors"] = state.get("errors", []) + ["缺少核心分析数据，跳过辩论"]
            return state

        try:
            # 多头研究
            bull_result = self.bull_researcher.analyze(
                stock_data=state["stock_data"],
                technical=state.get("technical"),
                fundamental=state.get("fundamental"),
                sentiment=state.get("sentiment"),
                news=state.get("news")
            )

            # 空头研究
            bear_result = self.bear_researcher.analyze(
                stock_data=state["stock_data"],
                technical=state.get("technical"),
                fundamental=state.get("fundamental"),
                sentiment=state.get("sentiment"),
                news=state.get("news")
            )

            # 构建辩论结果
            debate = DebateResult(
                bull_arguments=bull_result.get("arguments", []),
                bull_confidence=bull_result.get("confidence", 50),
                bear_arguments=bear_result.get("arguments", []),
                bear_confidence=bear_result.get("confidence", 50),
                debate_summary=self._summarize_debate(bull_result, bear_result),
                winning_side=self._determine_winner(bull_result, bear_result),
                key_disagreements=self._find_disagreements(bull_result, bear_result)
            )

            state["debate_result"] = debate
            logger.info(f"[工作流] 辩论完成: 获胜方 {debate.winning_side}")

        except Exception as e:
            error_msg = f"辩论失败: {str(e)}"
            logger.error(f"[工作流] {error_msg}")
            state["errors"] = state.get("errors", []) + [error_msg]

        return state

    def _generate_proposal_node(self, state: WorkflowState) -> WorkflowState:
        """生成交易提案节点"""
        logger.info("[工作流] 生成交易提案")

        if not state.get("debate_result"):
            logger.warning("[工作流] 缺少辩论结果，尝试基于已有数据生成提案")

        try:
            proposal = self.trader.analyze(
                stock_data=state["stock_data"],
                technical=state.get("technical"),
                fundamental=state.get("fundamental"),
                sentiment=state.get("sentiment"),
                news=state.get("news"),
                debate=state.get("debate_result")
            )

            state["trade_proposal"] = proposal
            direction = proposal.direction.value if hasattr(proposal, "direction") else "N/A"
            logger.info(f"[工作流] 交易提案完成: {direction}")

        except Exception as e:
            error_msg = f"交易提案失败: {str(e)}"
            logger.error(f"[工作流] {error_msg}")
            state["errors"] = state.get("errors", []) + [error_msg]

        return state

    def _risk_assessment_node(self, state: WorkflowState) -> WorkflowState:
        """风险评估节点"""
        logger.info("[工作流] 执行风险评估")

        if not state.get("trade_proposal"):
            logger.warning("[工作流] 缺少交易提案，跳过风险评估")
            return state

        try:
            assessment = self.risk_manager.analyze(
                stock_data=state["stock_data"],
                trade_proposal=state["trade_proposal"]
            )

            state["risk_assessment_result"] = assessment
            risk_level = assessment.risk_level.value if hasattr(assessment, "risk_level") else "N/A"
            approved = assessment.approved if hasattr(assessment, "approved") else False
            logger.info(f"[工作流] 风险评估完成: {risk_level}, 批准: {approved}")

        except Exception as e:
            error_msg = f"风险评估失败: {str(e)}"
            logger.error(f"[工作流] {error_msg}")
            state["errors"] = state.get("errors", []) + [error_msg]

        return state

    def _generate_report_node(self, state: WorkflowState) -> WorkflowState:
        """生成报告节点"""
        logger.info("[工作流] 生成分析报告")

        try:
            report = AnalysisReport(
                stock_code=state["stock_code"],
                stock_name=state["stock_name"],
                current_price=(
                    state["stock_data"].current_price
                    if state.get("stock_data") else None
                ),
                technical=state.get("technical"),
                fundamental=state.get("fundamental"),
                sentiment=state.get("sentiment"),
                news=state.get("news"),
                debate=state.get("debate_result"),
                trade_proposal=state.get("trade_proposal"),
                risk_assessment=state.get("risk_assessment_result"),
                final_signal=(
                    state["trade_proposal"].direction
                    if state.get("trade_proposal") else None
                ),
                final_confidence=self._calculate_final_confidence(state),
                full_report=self._generate_full_report_text(state),
                errors=state.get("errors", [])
            )

            state["report"] = report
            logger.info("[工作流] 分析报告生成完成")

        except Exception as e:
            error_msg = f"生成报告失败: {str(e)}"
            logger.error(f"[工作流] {error_msg}")
            state["errors"] = state.get("errors", []) + [error_msg]

        return state

    def analyze(self, stock_code: str, stock_name: Optional[str] = None) -> AnalysisReport:
        """
        执行完整分析

        Args:
            stock_code: 股票代码
            stock_name: 股票名称

        Returns:
            分析报告
        """
        logger.info(f"{'=' * 50}")
        logger.info(f"开始分析: {stock_code} {stock_name or ''}")
        logger.info(f"{'=' * 50}")

        # 初始化状态
        initial_state: WorkflowState = {
            "stock_code": stock_code,
            "stock_name": stock_name or "",
            "stock_data": None,
            "technical": None,
            "fundamental": None,
            "sentiment": None,
            "news": None,
            "debate_result": None,
            "trade_proposal": None,
            "risk_assessment_result": None,
            "report": None,
            "errors": []
        }

        # 执行工作流
        final_state = self.workflow.invoke(initial_state)

        # 返回报告
        if final_state.get("report"):
            return final_state["report"]

        # 生成错误报告
        return AnalysisReport(
            stock_code=stock_code,
            stock_name=stock_name or stock_code,
            errors=final_state.get("errors", ["未知错误"])
        )

    # ==================== 辅助方法 ====================

    @staticmethod
    def _summarize_debate(bull_result: Dict, bear_result: Dict) -> str:
        """总结辩论"""
        bull_count = len(bull_result.get("arguments", []))
        bear_count = len(bear_result.get("arguments", []))
        bull_conf = bull_result.get("confidence", 50)
        bear_conf = bear_result.get("confidence", 50)

        return (
            f"多头提出{bull_count}条论据(置信度{bull_conf}%)，"
            f"空头提出{bear_count}条论据(置信度{bear_conf}%)"
        )

    @staticmethod
    def _determine_winner(bull_result: Dict, bear_result: Dict) -> str:
        """确定获胜方"""
        bull_conf = bull_result.get("confidence", 50)
        bear_conf = bear_result.get("confidence", 50)

        if bull_conf > bear_conf + 10:
            return "bull"
        elif bear_conf > bull_conf + 10:
            return "bear"
        return "neutral"

    @staticmethod
    def _find_disagreements(bull_result: Dict, bear_result: Dict) -> List[str]:
        """找出分歧点"""
        return ["技术面与基本面信号可能存在分歧"]

    @staticmethod
    def _calculate_final_confidence(state: WorkflowState) -> int:
        """计算最终置信度 - 加权平均"""
        weights = {
            "technical": 0.35,
            "fundamental": 0.30,
            "sentiment": 0.15,
            "news": 0.20,
        }

        total_weight = 0.0
        weighted_sum = 0.0

        for key, weight in weights.items():
            analysis = state.get(key)
            if analysis and hasattr(analysis, "confidence"):
                weighted_sum += analysis.confidence * weight
                total_weight += weight

        if total_weight > 0:
            return int(weighted_sum / total_weight)
        return 50

    @staticmethod
    def _generate_full_report_text(state: WorkflowState) -> str:
        """生成完整报告文本"""
        lines = [
            "=" * 60,
            "AStockAgents 分析报告",
            f"股票: {state['stock_name']} ({state['stock_code']})",
            f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            ""
        ]

        # 技术分析
        if state.get("technical"):
            lines.append(state["technical"].summary)
            lines.append("")

        # 基本面分析
        if state.get("fundamental"):
            lines.append(state["fundamental"].summary)
            lines.append("")

        # 情绪分析
        if state.get("sentiment"):
            lines.append(state["sentiment"].summary)
            lines.append("")

        # 新闻分析
        if state.get("news"):
            lines.append(state["news"].summary)
            lines.append("")

        # 辩论结果
        if state.get("debate_result"):
            debate = state["debate_result"]
            winner = {"bull": "多头", "bear": "空头", "neutral": "平局"}.get(
                debate.winning_side, "平局"
            )
            lines.append("【多空辩论】")
            lines.append(f"获胜方: {winner}")
            lines.append(f"多头论据: {len(debate.bull_arguments)}条")
            lines.append(f"空头论据: {len(debate.bear_arguments)}条")
            lines.append("")

        # 交易提案
        if state.get("trade_proposal"):
            lines.append(state["trade_proposal"].proposal_text)
            lines.append("")

        # 风险评估
        if state.get("risk_assessment_result"):
            risk = state["risk_assessment_result"]
            risk_level = risk.risk_level.value if hasattr(risk, "risk_level") else "N/A"
            risk_score = risk.risk_score if hasattr(risk, "risk_score") else "N/A"
            approved = risk.approved if hasattr(risk, "approved") else False
            lines.append(f"【风险评估】{risk_level}")
            lines.append(f"风险评分: {risk_score}/100")
            lines.append(f"审批结果: {'通过' if approved else '未通过'}")
            lines.append("")

        # 错误信息
        errors = state.get("errors", [])
        if errors:
            lines.append("【警告】")
            for err in errors:
                lines.append(f"  - {err}")
            lines.append("")

        lines.append("=" * 60)
        lines.append("报告生成完毕")
        lines.append("=" * 60)

        return "\n".join(lines)
