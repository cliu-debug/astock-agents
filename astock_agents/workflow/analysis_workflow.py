"""分析工作流 - 使用LangGraph编排多智能体协作，支持并行执行

增强功能：
- 多轮辩论：支持可配置的辩论轮数，每轮多头和空头回应对方论点
- 投票决策：辩论结束后各分析师投票，加权决定最终信号
- 囚徒困境模型：在多空辩论中引入合作/背叛机制
- 用户记忆系统：自动记录分析行为，根据用户画像调整信号
- MCP工具集成：智能体可通过MCP协议调用标准化金融工具
"""

import json
from typing import Dict, Any, Optional, TypedDict, Annotated, List, Callable
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

    # 用户记忆调整信息
    memory_adjustment: Optional[Dict[str, Any]]

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
            config: 配置字典，支持以下参数：
                - debate_rounds: 辩论轮数，默认2
                - enable_prisoners_dilemma: 是否启用囚徒困境模型，默认True
                - enable_memory: 是否启用用户记忆系统，默认True
                - user_id: 用户ID，用于记忆系统，默认"default"
                - enable_mcp: 是否启用MCP工具，默认True
        """
        self.config = config or {}

        # 辩论配置
        self.debate_rounds: int = self.config.get("debate_rounds", 2)
        self.enable_prisoners_dilemma: bool = self.config.get("enable_prisoners_dilemma", True)

        # 用户记忆配置
        self.enable_memory: bool = self.config.get("enable_memory", True)
        self.user_id: str = self.config.get("user_id", "default")

        # MCP工具配置
        self.enable_mcp: bool = self.config.get("enable_mcp", True)

        # 初始化数据管理器
        self.data_manager = DataManager(config)

        # 初始化用户记忆服务
        self.memory_service = None
        if self.enable_memory:
            try:
                from astock_agents.services.user_memory import UserMemoryService
                self.memory_service = UserMemoryService()
                logger.info("[工作流] 用户记忆系统已启用")
            except Exception as e:
                logger.warning(f"[工作流] 用户记忆系统初始化失败: {e}")

        # 初始化MCP服务
        self.mcp_server = None
        if self.enable_mcp:
            try:
                from astock_agents.services.mcp_server import MCPServer
                self.mcp_server = MCPServer(data_manager=self.data_manager)
                logger.info(f"[工作流] MCP服务已启用，注册 {len(self.mcp_server.list_tools())} 个工具")
            except Exception as e:
                logger.warning(f"[工作流] MCP服务初始化失败: {e}")

        # 初始化各智能体
        self.technical_analyst = TechnicalAnalyst(config=config)
        self.fundamental_analyst = FundamentalAnalyst(config=config)
        self.sentiment_analyst = SentimentAnalyst(config=config)
        self.news_analyst = NewsAnalyst(config=config)
        self.bull_researcher = BullResearcher(config=config)
        self.bear_researcher = BearResearcher(config=config)
        self.trader = Trader(config=config)
        self.risk_manager = RiskManager(config=config)

        # 将MCP服务注入到各智能体
        if self.mcp_server:
            for agent in [
                self.technical_analyst, self.fundamental_analyst,
                self.sentiment_analyst, self.news_analyst,
                self.bull_researcher, self.bear_researcher,
                self.trader, self.risk_manager,
            ]:
                if hasattr(agent, "mcp_server"):
                    agent.mcp_server = self.mcp_server

        # 状态回调（用于WebSocket实时推送）
        self._status_callback: Optional[Callable] = None

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
        workflow.add_node("memory_adjust", self._memory_adjust_node)
        workflow.add_node("generate_proposal", self._generate_proposal_node)
        workflow.add_node("risk_assessment", self._risk_assessment_node)
        workflow.add_node("generate_report", self._generate_report_node)

        # 线性流程：数据获取 -> 并行分析 -> 辩论 -> 记忆调整 -> 提案 -> 风控 -> 报告
        workflow.add_edge("fetch_data", "parallel_analysis")
        workflow.add_edge("parallel_analysis", "debate")
        workflow.add_edge("debate", "memory_adjust")
        workflow.add_edge("memory_adjust", "generate_proposal")
        workflow.add_edge("generate_proposal", "risk_assessment")
        workflow.add_edge("risk_assessment", "generate_report")
        workflow.add_edge("generate_report", END)

        workflow.set_entry_point("fetch_data")

        return workflow.compile()

    def set_status_callback(
        self, callback: Callable[[str, str, str], None]
    ) -> None:
        """设置状态回调函数，注入到所有智能体

        Args:
            callback: 回调函数，参数为 (agent_name, status, message)
        """
        self._status_callback = callback
        for agent in [
            self.technical_analyst, self.fundamental_analyst,
            self.sentiment_analyst, self.news_analyst,
            self.bull_researcher, self.bear_researcher,
            self.trader, self.risk_manager,
        ]:
            if hasattr(agent, "set_status_callback"):
                agent.set_status_callback(callback)

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
        """辩论节点 - 多轮辩论 + 投票决策 + 囚徒困境模型

        流程：
        1. 执行多轮辩论，每轮多头和空头回应对方论点
        2. 辩论结束后，各分析师投票
        3. 计算合作度评分（囚徒困境模型）
        4. 加权投票决定最终信号
        """
        logger.info(f"[工作流] 执行多轮辩论 (轮数: {self.debate_rounds})")

        # 至少需要技术分析和基本面分析才能辩论
        has_min_data = state.get("technical") or state.get("fundamental")
        if not has_min_data:
            logger.warning("[工作流] 缺少核心分析数据，跳过辩论")
            state["errors"] = state.get("errors", []) + ["缺少核心分析数据，跳过辩论"]
            return state

        try:
            # 多轮辩论
            debate_history: List[Dict[str, Any]] = []
            bull_result: Dict[str, Any] = {}
            bear_result: Dict[str, Any] = {}

            for round_num in range(1, self.debate_rounds + 1):
                logger.info(f"[工作流] 辩论第 {round_num}/{self.debate_rounds} 轮")

                # 构建上下文：包含对方上一轮的论点
                bull_context = None
                bear_context = None
                if round_num > 1 and debate_history:
                    prev_round = debate_history[-1]
                    bear_context = prev_round.get("bear_summary", "")
                    bull_context = prev_round.get("bull_summary", "")

                # 多头研究
                bull_result = self.bull_researcher.analyze(
                    stock_data=state["stock_data"],
                    technical=state.get("technical"),
                    fundamental=state.get("fundamental"),
                    sentiment=state.get("sentiment"),
                    news=state.get("news"),
                    opponent_context=bear_context,
                )

                # 空头研究
                bear_result = self.bear_researcher.analyze(
                    stock_data=state["stock_data"],
                    technical=state.get("technical"),
                    fundamental=state.get("fundamental"),
                    sentiment=state.get("sentiment"),
                    news=state.get("news"),
                    opponent_context=bull_context,
                )

                # 记录本轮辩论
                round_record = {
                    "round": round_num,
                    "bull_arguments": bull_result.get("arguments", []),
                    "bull_confidence": bull_result.get("confidence", 50),
                    "bull_summary": bull_result.get("bull_thesis", ""),
                    "bear_arguments": bear_result.get("arguments", []),
                    "bear_confidence": bear_result.get("confidence", 50),
                    "bear_summary": bear_result.get("bear_thesis", ""),
                }
                debate_history.append(round_record)

            # 投票决策
            votes = self._conduct_voting(state, bull_result, bear_result)

            # 囚徒困境模型 - 计算合作度
            cooperation_score = 0.5
            nash_equilibrium = None
            if self.enable_prisoners_dilemma:
                cooperation_score, nash_equilibrium = self._apply_prisoners_dilemma(
                    bull_result, bear_result, debate_history
                )

            # 构建辩论结果
            debate = DebateResult(
                bull_arguments=bull_result.get("arguments", []),
                bull_confidence=bull_result.get("confidence", 50),
                bear_arguments=bear_result.get("arguments", []),
                bear_confidence=bear_result.get("confidence", 50),
                debate_summary=self._summarize_debate(bull_result, bear_result),
                winning_side=self._determine_winner_with_votes(votes, bull_result, bear_result, cooperation_score),
                key_disagreements=self._find_disagreements(bull_result, bear_result),
                bull_thesis=bull_result.get("bull_thesis"),
                bear_thesis=bear_result.get("bear_thesis"),
                debate_rounds=self.debate_rounds,
                debate_history=debate_history,
                votes=votes,
                cooperation_score=cooperation_score,
                nash_equilibrium=nash_equilibrium,
            )

            state["debate_result"] = debate
            logger.info(
                f"[工作流] 辩论完成: 获胜方 {debate.winning_side}, "
                f"合作度 {cooperation_score:.2f}"
            )

            # 保存辩论历史到数据库
            self._save_debate_to_db(state["stock_code"], debate)

        except Exception as e:
            error_msg = f"辩论失败: {str(e)}"
            logger.error(f"[工作流] {error_msg}")
            state["errors"] = state.get("errors", []) + [error_msg]

        return state

    def _conduct_voting(
        self,
        state: WorkflowState,
        bull_result: Dict[str, Any],
        bear_result: Dict[str, Any],
    ) -> Dict[str, str]:
        """各分析师投票

        技术分析师、基本面分析师、情绪分析师、新闻分析师各投一票，
        投票基于各自的分析结果和置信度。

        Args:
            state: 工作流状态
            bull_result: 多头研究结果
            bear_result: 空头研究结果

        Returns:
            投票结果字典，key为分析师名称，value为投票倾向（bull/bear/neutral）
        """
        votes: Dict[str, str] = {}

        # 技术分析师投票
        technical = state.get("technical")
        if technical and hasattr(technical, "signal"):
            signal_value = technical.signal.value if hasattr(technical.signal, "value") else str(technical.signal)
            if signal_value in ("强烈买入", "买入"):
                votes["technical"] = "bull"
            elif signal_value in ("强烈卖出", "卖出"):
                votes["technical"] = "bear"
            else:
                votes["technical"] = "neutral"

        # 基本面分析师投票
        fundamental = state.get("fundamental")
        if fundamental and hasattr(fundamental, "signal"):
            signal_value = fundamental.signal.value if hasattr(fundamental.signal, "value") else str(fundamental.signal)
            if signal_value in ("强烈买入", "买入"):
                votes["fundamental"] = "bull"
            elif signal_value in ("强烈卖出", "卖出"):
                votes["fundamental"] = "bear"
            else:
                votes["fundamental"] = "neutral"

        # 情绪分析师投票
        sentiment = state.get("sentiment")
        if sentiment and hasattr(sentiment, "signal"):
            signal_value = sentiment.signal.value if hasattr(sentiment.signal, "value") else str(sentiment.signal)
            if signal_value in ("强烈买入", "买入"):
                votes["sentiment"] = "bull"
            elif signal_value in ("强烈卖出", "卖出"):
                votes["sentiment"] = "bear"
            else:
                votes["sentiment"] = "neutral"

        # 新闻分析师投票
        news = state.get("news")
        if news and hasattr(news, "signal"):
            signal_value = news.signal.value if hasattr(news.signal, "value") else str(news.signal)
            if signal_value in ("强烈买入", "买入"):
                votes["news"] = "bull"
            elif signal_value in ("强烈卖出", "卖出"):
                votes["news"] = "bear"
            else:
                votes["news"] = "neutral"

        logger.info(f"[工作流] 投票结果: {votes}")
        return votes

    def _apply_prisoners_dilemma(
        self,
        bull_result: Dict[str, Any],
        bear_result: Dict[str, Any],
        debate_history: List[Dict[str, Any]],
    ) -> tuple:
        """应用囚徒困境模型

        判断多空双方是否"合作"（承认对方合理论点）或"背叛"（无视对方论点）：
        - 双方合作：信号置信度提升
        - 一方背叛：该方权重降低
        - 双方背叛：置信度均降低

        纳什均衡点作为最终决策参考。

        Args:
            bull_result: 多头研究结果
            bear_result: 空头研究结果
            debate_history: 辩论历史记录

        Returns:
            (合作度评分, 纳什均衡分析) 元组
        """
        bull_conf = bull_result.get("confidence", 50)
        bear_conf = bear_result.get("confidence", 50)

        # 判断是否合作：置信度差距小表示双方互相认可（合作）
        conf_gap = abs(bull_conf - bear_conf)

        # 分析辩论历史中的回应质量
        bull_cooperates = True
        bear_cooperates = True

        if len(debate_history) > 1:
            # 检查后续轮次是否回应了对方论点
            for i in range(1, len(debate_history)):
                prev_bear_args = debate_history[i - 1].get("bear_arguments", [])
                curr_bull_args = debate_history[i].get("bull_arguments", [])

                prev_bull_args = debate_history[i - 1].get("bull_arguments", [])
                curr_bear_args = debate_history[i].get("bear_arguments", [])

                # 如果后续论据数量明显减少，视为背叛（未认真回应对方）
                if prev_bear_args and len(curr_bull_args) < len(prev_bear_args) * 0.5:
                    bull_cooperates = False
                if prev_bull_args and len(curr_bear_args) < len(prev_bull_args) * 0.5:
                    bear_cooperates = False

        # 计算合作度评分
        if bull_cooperates and bear_cooperates:
            # 双方合作 - 高合作度
            cooperation_score = min(0.5 + (1.0 - conf_gap / 100) * 0.5, 1.0)
            nash_equilibrium = "双方合作 - 置信度可信，信号强度可提升"
        elif bull_cooperates and not bear_cooperates:
            # 空头背叛 - 降低空头权重
            cooperation_score = 0.3
            nash_equilibrium = "空头背叛 - 空头论据可信度降低，多头权重提升"
        elif not bull_cooperates and bear_cooperates:
            # 多头背叛 - 降低多头权重
            cooperation_score = 0.3
            nash_equilibrium = "多头背叛 - 多头论据可信度降低，空头权重提升"
        else:
            # 双方背叛 - 低合作度
            cooperation_score = 0.2
            nash_equilibrium = "双方背叛 - 均未认真回应对方，信号可信度降低"

        logger.info(
            f"[工作流] 囚徒困境: 多头{'合作' if bull_cooperates else '背叛'}, "
            f"空头{'合作' if bear_cooperates else '背叛'}, "
            f"合作度={cooperation_score:.2f}"
        )

        return cooperation_score, nash_equilibrium

    @staticmethod
    def _determine_winner_with_votes(
        votes: Dict[str, str],
        bull_result: Dict[str, Any],
        bear_result: Dict[str, Any],
        cooperation_score: float,
    ) -> str:
        """基于投票和合作度确定获胜方

        投票权重根据各分析师置信度和合作度调整。

        Args:
            votes: 各分析师投票结果
            bull_result: 多头研究结果
            bear_result: 空头研究结果
            cooperation_score: 合作度评分

        Returns:
            获胜方: bull/bear/neutral
        """
        # 基础权重
        base_weights = {
            "technical": 0.35,
            "fundamental": 0.30,
            "sentiment": 0.15,
            "news": 0.20,
        }

        # 计算加权投票
        bull_score = 0.0
        bear_score = 0.0
        total_weight = 0.0

        for analyst, vote in votes.items():
            weight = base_weights.get(analyst, 0.25)
            # 合作度高时，投票权重正常；合作度低时，投票权重降低
            adjusted_weight = weight * (0.5 + cooperation_score * 0.5)

            if vote == "bull":
                bull_score += adjusted_weight
            elif vote == "bear":
                bear_score += adjusted_weight
            total_weight += adjusted_weight

        # 加上原始置信度的影响
        bull_conf = bull_result.get("confidence", 50) / 100.0
        bear_conf = bear_result.get("confidence", 50) / 100.0
        bull_score += bull_conf * 0.3
        bear_score += bear_conf * 0.3

        if bull_score > bear_score + 0.1:
            return "bull"
        elif bear_score > bull_score + 0.1:
            return "bear"
        return "neutral"

    def _save_debate_to_db(self, stock_code: str, debate: DebateResult) -> None:
        """保存辩论历史到数据库

        Args:
            stock_code: 股票代码
            debate: 辩论结果
        """
        try:
            from astock_agents.db.database import Database
            db = Database()
            db.save_debate_history(
                stock_code=stock_code,
                debate_rounds=debate.debate_rounds,
                debate_history_json=json.dumps(debate.debate_history, ensure_ascii=False),
                votes_json=json.dumps(debate.votes, ensure_ascii=False),
                cooperation_score=debate.cooperation_score,
                nash_equilibrium=debate.nash_equilibrium,
                winning_side=debate.winning_side,
                debate_summary=debate.debate_summary,
            )
        except Exception as e:
            logger.warning(f"[工作流] 辩论历史保存失败: {e}")

    def _memory_adjust_node(self, state: WorkflowState) -> WorkflowState:
        """用户记忆调整节点 - 根据用户画像调整分析信号

        读取用户历史偏好（风险偏好、偏好行业、持仓周期），
        对辩论结果和最终信号进行个性化调整。
        """
        logger.info("[工作流] 执行用户记忆调整")

        if not self.memory_service:
            logger.info("[工作流] 用户记忆系统未启用，跳过调整")
            state["memory_adjustment"] = None
            return state

        try:
            stock_code = state["stock_code"]

            # 获取用户画像
            profile = self.memory_service.get_user_profile(self.user_id)
            risk_pref = profile.get("risk_preference", "稳健")
            holding_pref = profile.get("holding_preference", "中线")
            preferred_industries = profile.get("preferred_industries", [])
            dimension_weights = profile.get("dimension_weights", {})

            # 获取该股票的历史记忆
            stock_memory = self.memory_service.get_stock_memory(self.user_id, stock_code)

            # 构建调整信息
            adjustment: Dict[str, Any] = {
                "user_id": self.user_id,
                "risk_preference": risk_pref,
                "holding_preference": holding_pref,
                "preferred_industries": preferred_industries,
                "dimension_weights": dimension_weights,
                "stock_memory": stock_memory,
                "adjustment_reasons": [],
            }

            # 根据辩论结果获取调整后的信号
            debate = state.get("debate_result")
            if debate:
                raw_signal = "买入" if debate.winning_side == "bull" else (
                    "卖出" if debate.winning_side == "bear" else "持有"
                )
                adjusted = self.memory_service.get_preference_adjusted_signal(
                    self.user_id, stock_code, raw_signal
                )
                adjustment["raw_signal"] = raw_signal
                adjustment["adjusted_signal"] = adjusted.get("adjusted_signal", raw_signal)
                adjustment["adjustment_reasons"] = adjusted.get("adjustment_reasons", [])

                # 如果信号被调整，更新辩论获胜方
                if adjusted.get("adjusted_signal") != raw_signal:
                    adj_signal = adjusted["adjusted_signal"]
                    if adj_signal in ("强烈买入", "买入") and debate.winning_side != "bull":
                        logger.info(f"[记忆] 信号调整: {raw_signal} -> {adj_signal} (基于用户偏好)")
                    elif adj_signal in ("强烈卖出", "卖出") and debate.winning_side != "bear":
                        logger.info(f"[记忆] 信号调整: {raw_signal} -> {adj_signal} (基于用户偏好)")

            # 根据用户偏好调整分析维度权重
            if dimension_weights:
                adjustment["weight_adjustment_note"] = (
                    f"基于用户画像，分析维度权重已调整: "
                    f"技术面={dimension_weights.get('technical', 0.35):.0%}, "
                    f"基本面={dimension_weights.get('fundamental', 0.30):.0%}, "
                    f"情绪面={dimension_weights.get('sentiment', 0.15):.0%}, "
                    f"新闻面={dimension_weights.get('news', 0.20):.0%}"
                )

            state["memory_adjustment"] = adjustment
            logger.info(
                f"[工作流] 记忆调整完成: 风险偏好={risk_pref}, "
                f"持仓偏好={holding_pref}, 调整原因={adjustment.get('adjustment_reasons', [])}"
            )

        except Exception as e:
            error_msg = f"用户记忆调整失败: {str(e)}"
            logger.warning(f"[工作流] {error_msg}")
            state["memory_adjustment"] = None

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
        """生成报告节点 - 同时自动记录分析行为到记忆系统"""
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

            # 自动记录分析行为到记忆系统
            if self.memory_service:
                try:
                    signal_str = "未知"
                    if report.final_signal:
                        signal_str = report.final_signal.value if hasattr(report.final_signal, "value") else str(report.final_signal)

                    industry = None
                    if state.get("stock_data") and hasattr(state["stock_data"], "industry"):
                        industry = state["stock_data"].industry

                    self.memory_service.record_analysis(
                        user_id=self.user_id,
                        stock_code=state["stock_code"],
                        signal=signal_str,
                        confidence=report.final_confidence or 50,
                        industry=industry,
                    )
                    logger.info(f"[记忆] 已自动记录分析行为: {state['stock_code']} {signal_str}")
                except Exception as e:
                    logger.warning(f"[记忆] 自动记录分析行为失败: {e}")

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
            "memory_adjustment": None,
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
            lines.append(f"辩论轮数: {debate.debate_rounds}")
            lines.append(f"获胜方: {winner}")
            lines.append(f"多头论据: {len(debate.bull_arguments)}条")
            lines.append(f"空头论据: {len(debate.bear_arguments)}条")
            # 博弈论增强信息
            if debate.votes:
                lines.append(f"投票结果: {debate.votes}")
            if debate.cooperation_score is not None:
                lines.append(f"合作度评分: {debate.cooperation_score:.2f}")
            if debate.nash_equilibrium:
                lines.append(f"纳什均衡: {debate.nash_equilibrium}")
            lines.append("")

        # 用户记忆调整信息
        if state.get("memory_adjustment"):
            mem = state["memory_adjustment"]
            lines.append("【用户画像调整】")
            lines.append(f"风险偏好: {mem.get('risk_preference', '未知')}")
            lines.append(f"持仓偏好: {mem.get('holding_preference', '未知')}")
            if mem.get("adjustment_reasons"):
                for reason in mem["adjustment_reasons"]:
                    lines.append(f"  - {reason}")
            if mem.get("raw_signal") and mem.get("adjusted_signal"):
                lines.append(f"信号调整: {mem['raw_signal']} -> {mem['adjusted_signal']}")
            if mem.get("weight_adjustment_note"):
                lines.append(mem["weight_adjustment_note"])
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
