"""多轮对话服务 (DialogueService)

支持用户与智能体之间的多轮对话，包括：
1. 上下文记忆 - 记住之前的分析结果和对话内容
2. 追问澄清 - 用户可以追问"为什么买入"、"风险在哪"
3. 智能体协作回答 - 不同智能体回答不同领域的问题
4. 对话历史持久化 - 存储到数据库，支持回溯

对话流程：
  用户提问 → 意图识别 → 路由到对应智能体 → 生成回答 → 更新上下文
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger

from astock_agents.db.database import Database


class DialogueIntent:
    """对话意图常量"""
    WHY_SIGNAL = "why_signal"
    RISK_DETAIL = "risk_detail"
    COMPARE = "compare"
    DEEP_DIVE = "deep_dive"
    CHALLENGE = "challenge"
    FOLLOW_UP = "follow_up"
    GENERAL = "general"


class DialogueService:
    """多轮对话服务

    核心能力：
    - 上下文记忆：记住最近的分析结果和对话历史
    - 意图识别：理解用户追问的意图
    - 智能体路由：将问题路由到最合适的智能体
    - 持久化：对话历史存储到数据库
    """

    INTENT_KEYWORDS: Dict[str, List[str]] = {
        DialogueIntent.WHY_SIGNAL: [
            "为什么", "理由", "原因", "依据", "凭什么",
            "why", "reason", "basis",
        ],
        DialogueIntent.RISK_DETAIL: [
            "风险", "止损", "最大亏损", "回撤", "危险",
            "risk", "stop", "loss", "drawdown",
        ],
        DialogueIntent.COMPARE: [
            "对比", "比较", "区别", "差异", "vs",
            "compare", "versus", "difference",
        ],
        DialogueIntent.DEEP_DIVE: [
            "详细", "深入", "具体", "展开", "分析一下",
            "detail", "deep", "specific", "elaborate",
        ],
        DialogueIntent.CHALLENGE: [
            "不对", "不同意", "反对", "质疑", "真的吗",
            "disagree", "challenge", "doubt",
        ],
        DialogueIntent.FOLLOW_UP: [
            "然后呢", "接下来", "后续", "怎么办",
            "then", "next", "follow",
        ],
    }

    AGENT_ROUTING: Dict[str, str] = {
        DialogueIntent.WHY_SIGNAL: "trader",
        DialogueIntent.RISK_DETAIL: "risk_manager",
        DialogueIntent.COMPARE: "trader",
        DialogueIntent.DEEP_DIVE: "technical_analyst",
        DialogueIntent.CHALLENGE: "bull_researcher",
        DialogueIntent.FOLLOW_UP: "trader",
        DialogueIntent.GENERAL: "trader",
    }

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def classify_intent(self, question: str) -> str:
        """识别用户提问意图

        Args:
            question: 用户提问文本

        Returns:
            意图常量
        """
        question_lower = question.lower()

        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in question_lower:
                    return intent

        return DialogueIntent.GENERAL

    def get_context(
        self,
        session_id: str,
        stock_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取对话上下文

        Args:
            session_id: 会话ID
            stock_code: 股票代码（可选）

        Returns:
            上下文字典
        """
        try:
            history = self.db.get_dialogue_history(session_id, limit=20)
        except Exception:
            history = []

        latest_analysis = None
        if stock_code:
            try:
                records = self.db.get_analysis_results(stock_code=stock_code, limit=1)
                if records:
                    latest_analysis = records[0]
            except Exception:
                pass

        return {
            "session_id": session_id,
            "stock_code": stock_code,
            "history": history,
            "latest_analysis": latest_analysis,
            "turn_count": len(history),
        }

    def generate_response(
        self,
        question: str,
        context: Dict[str, Any],
        analysis_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """生成对话回答

        Args:
            question: 用户提问
            context: 对话上下文
            analysis_result: 最近的分析结果

        Returns:
            回答字典
        """
        intent = self.classify_intent(question)
        target_agent = self.AGENT_ROUTING.get(intent, "trader")

        answer = self._generate_rule_based_answer(
            question=question,
            intent=intent,
            target_agent=target_agent,
            context=context,
            analysis_result=analysis_result,
        )

        response = {
            "question": question,
            "answer": answer,
            "intent": intent,
            "target_agent": target_agent,
            "session_id": context.get("session_id", ""),
            "turn": context.get("turn_count", 0) + 1,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            self.db.save_dialogue_history(
                session_id=context.get("session_id", "default"),
                question=question,
                answer=answer,
                intent=intent,
                target_agent=target_agent,
                stock_code=context.get("stock_code", ""),
            )
        except Exception as e:
            logger.warning(f"[对话] 保存对话历史失败: {e}")

        return response

    def _generate_rule_based_answer(
        self,
        question: str,
        intent: str,
        target_agent: str,
        context: Dict[str, Any],
        analysis_result: Optional[Dict[str, Any]] = None,
    ) -> str:
        """基于规则生成回答（LLM不可用时的降级方案）

        Args:
            question: 用户提问
            intent: 识别的意图
            target_agent: 目标智能体
            context: 对话上下文
            analysis_result: 分析结果

        Returns:
            回答文本
        """
        analysis = analysis_result or context.get("latest_analysis") or {}

        if intent == DialogueIntent.WHY_SIGNAL:
            return self._answer_why_signal(analysis, context)

        if intent == DialogueIntent.RISK_DETAIL:
            return self._answer_risk_detail(analysis, context)

        if intent == DialogueIntent.COMPARE:
            return self._answer_compare(analysis, context)

        if intent == DialogueIntent.DEEP_DIVE:
            return self._answer_deep_dive(analysis, context)

        if intent == DialogueIntent.CHALLENGE:
            return self._answer_challenge(analysis, context)

        if intent == DialogueIntent.FOLLOW_UP:
            return self._answer_follow_up(analysis, context)

        return self._answer_general(question, analysis, context)

    def _answer_why_signal(
        self,
        analysis: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """回答'为什么'类问题"""
        signal = analysis.get("final_signal", "未知")
        confidence = analysis.get("final_confidence", 0)
        debate = analysis.get("debate", {})

        parts = [f"当前信号为【{signal}】，置信度{confidence}%。"]

        tech = analysis.get("technical_analysis", {})
        if tech:
            trend = tech.get("trend", "未知")
            parts.append(f"技术面趋势：{trend}，")

            indicators = tech.get("indicators", {})
            rsi = indicators.get("rsi", {})
            macd = indicators.get("macd", {})
            if rsi:
                parts.append(f"RSI={rsi.get('value', 'N/A')}，")
            if macd:
                parts.append(f"MACD={macd.get('cross_signal', 'N/A')}，")

        fund = analysis.get("fundamental_analysis", {})
        if fund:
            parts.append(f"基本面信号：{fund.get('signal', '未知')}，")
            parts.append(f"置信度：{fund.get('confidence', 0)}%。")

        if debate:
            winner = debate.get("winning_side", "未知")
            winner_cn = {"bull": "多头", "bear": "空头", "neutral": "平局"}.get(winner, winner)
            parts.append(f"多空辩论获胜方：{winner_cn}。")
            cooperation = debate.get("cooperation_score")
            if cooperation is not None:
                parts.append(f"合作度评分：{cooperation:.2f}。")

        decision_info = analysis.get("metadata", {}).get("decision_info", {})
        if decision_info:
            source = decision_info.get("decision_source", "")
            if source == "risk_guard_blocked":
                parts.append("⚠️ 注意：该交易被风控层否决。")
            elif source == "risk_guard_adjusted":
                parts.append("⚡ 注意：该交易被风控层调整。")

        return "".join(parts)

    def _answer_risk_detail(
        self,
        analysis: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """回答风险详情类问题"""
        risk = analysis.get("risk_assessment", {})
        trade = analysis.get("trade_proposal", {})

        parts = ["【风险评估详情】"]

        if risk:
            risk_level = risk.get("risk_level", "未知")
            parts.append(f"风险等级：{risk_level}。")
            parts.append(f"最大亏损：{risk.get('max_loss_pct', 'N/A')}%。")
            parts.append(f"建议仓位：{risk.get('suggested_position_pct', 'N/A')}%。")

        if trade:
            parts.append(f"止损价格：{trade.get('stop_loss_price', '未设置')}。")
            parts.append(f"目标价格：{trade.get('target_price', '未设置')}。")

        decision_info = analysis.get("metadata", {}).get("decision_info", {})
        risk_adjustments = decision_info.get("layer3_risk_adjustments", [])
        risk_blocks = decision_info.get("layer3_risk_blocks", [])

        if risk_blocks:
            parts.append("⚠️ 风控否决原因：")
            for block in risk_blocks:
                parts.append(f"  - {block}")

        if risk_adjustments:
            parts.append("⚡ 风控调整记录：")
            for adj in risk_adjustments:
                parts.append(f"  - {adj}")

        if not risk_blocks and not risk_adjustments:
            parts.append("风控层未发现异常，交易参数在安全范围内。")

        return "".join(parts)

    def _answer_compare(
        self,
        analysis: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """回答对比类问题"""
        return (
            "对比分析需要提供两只股票代码。"
            "您可以通过分别分析两只股票后，"
            "在决策中心查看对比结果。"
        )

    def _answer_deep_dive(
        self,
        analysis: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """回答深入分析类问题"""
        tech = analysis.get("technical_analysis", {})
        parts = ["【技术面深度分析】"]

        if not tech:
            return "暂无技术分析数据，请先进行一次完整分析。"

        indicators = tech.get("indicators", {})
        reasoning_chain = tech.get("reasoning_chain", [])

        if reasoning_chain:
            parts.append("推理链：")
            for step in reasoning_chain:
                parts.append(
                    f"  {step.get('step_name', '')}: "
                    f"{step.get('conclusion', '')} "
                    f"(置信度:{step.get('confidence', 'N/A')})"
                )

        if indicators:
            parts.append("指标详情：")
            for name, data in indicators.items():
                if isinstance(data, dict):
                    value = data.get("value", data.get("signal", "N/A"))
                    parts.append(f"  {name}: {value}")

        reflection = tech.get("reflection", {})
        if reflection:
            quality = reflection.get("quality_score", "N/A")
            recommendation = reflection.get("recommendation", "")
            parts.append(f"自检质量评分：{quality}分。")
            if recommendation:
                parts.append(f"自检建议：{recommendation}")

        return "".join(parts)

    def _answer_challenge(
        self,
        analysis: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """回答质疑类问题 - 提供反方观点"""
        debate = analysis.get("debate", {})
        parts = ["【反方观点】"]

        if debate:
            bear_args = debate.get("bear_arguments", [])
            if bear_args:
                parts.append("空头论据：")
                for arg in bear_args[:5]:
                    parts.append(f"  - {arg}")
            else:
                parts.append("暂无空头论据。")

            bull_args = debate.get("bull_arguments", [])
            if bull_args:
                parts.append("多头论据：")
                for arg in bull_args[:5]:
                    parts.append(f"  - {arg}")
        else:
            parts.append("暂无辩论记录。建议进行完整分析以获取多空辩论结果。")

        return "".join(parts)

    def _answer_follow_up(
        self,
        analysis: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """回答后续操作类问题"""
        signal = analysis.get("final_signal", "未知")
        confidence = analysis.get("final_confidence", 0)

        parts = [f"当前信号【{signal}】，置信度{confidence}%。"]

        if signal in ("买入", "强烈买入"):
            parts.append("建议操作：")
            parts.append("1. 设置止损价（建议不超过入场价下方15%）")
            parts.append("2. 分批建仓，首次买入建议仓位不超过总资金30%")
            parts.append("3. 关注基本面变化和市场情绪波动")
        elif signal in ("卖出", "强烈卖出"):
            parts.append("建议操作：")
            parts.append("1. 如持有仓位，考虑分批减仓")
            parts.append("2. 设置止损价防止反弹")
            parts.append("3. 关注是否有反转信号")
        else:
            parts.append("当前建议持有观望。")
            parts.append("可关注以下触发条件：")
            parts.append("1. 技术面出现明确趋势信号")
            parts.append("2. 基本面发生重大变化")
            parts.append("3. 市场情绪出现极端值")

        return "".join(parts)

    def _answer_general(
        self,
        question: str,
        analysis: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """回答一般性问题"""
        signal = analysis.get("final_signal", "未知")
        confidence = analysis.get("final_confidence", 0)
        stock_code = context.get("stock_code", "")

        return (
            f"关于{stock_code}，当前分析信号为【{signal}】，"
            f"置信度{confidence}%。"
            f"您可以追问：\n"
            f"1. '为什么{signal}？' - 查看信号依据\n"
            f"2. '风险在哪？' - 查看风险评估\n"
            f"3. '详细分析' - 查看推理链\n"
            f"4. '我不同意' - 查看反方观点\n"
            f"5. '接下来怎么办？' - 查看操作建议"
        )
