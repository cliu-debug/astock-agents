"""自动决策引擎 - 从分析到可执行决策的核心引擎

系统核心竞争力：将多智能体分析结果自动转化为可执行的交易决策，
包含动作判断、仓位计算、止损止盈、紧急度评估、监控要点生成等完整决策链路。

核心流程：给数据 → 多智能体分析 → 自动生成可执行决策 → 一键执行 → 自动监控 → 自动复盘
"""

import json
import uuid
import math
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from loguru import logger

from astock_agents.db.database import Database


# ==================== 数据模型 ====================

@dataclass
class DecisionAction:
    """可执行决策动作

    Attributes:
        action_type: 动作类型，如 open_long/close_long/open_short/close_short/add_position/reduce_position/hold/watch
        stock_code: 股票代码
        stock_name: 股票名称
        direction: 交易方向 buy/sell
        quantity: 建议数量（100的整数倍）
        price_range: 建议价格区间 (下限, 上限)
        urgency: 执行紧急度 immediate/intraday/within_3_days/watch
        reason: 决策理由（自然语言）
        confidence: 决策置信度 0-1
        risk_reward_ratio: 风险收益比
        stop_loss: 止损价
        take_profit: 止盈价
        position_pct: 建议仓位占比 0-1
    """
    action_type: str = "watch"
    stock_code: str = ""
    stock_name: str = ""
    direction: str = "buy"
    quantity: int = 0
    price_range: Tuple[float, float] = (0.0, 0.0)
    urgency: str = "watch"
    reason: str = ""
    confidence: float = 0.0
    risk_reward_ratio: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    position_pct: float = 0.0


@dataclass
class Decision:
    """完整决策

    Attributes:
        id: 决策唯一标识
        stock_code: 股票代码
        stock_name: 股票名称
        timestamp: 决策生成时间
        action: 可执行动作
        analysis_summary: 分析摘要
        bull_points: 看多要点
        bear_points: 看空要点
        key_risks: 关键风险
        market_context: 市场环境判断
        execution_plan: 执行计划
        monitoring_points: 监控要点
        auto_execute: 是否自动执行
        status: 决策状态 pending/executed/cancelled/expired
    """
    id: str = ""
    stock_code: str = ""
    stock_name: str = ""
    timestamp: str = ""
    action: DecisionAction = field(default_factory=DecisionAction)
    analysis_summary: str = ""
    bull_points: List[str] = field(default_factory=list)
    bear_points: List[str] = field(default_factory=list)
    key_risks: List[str] = field(default_factory=list)
    market_context: str = ""
    execution_plan: str = ""
    monitoring_points: List[str] = field(default_factory=list)
    auto_execute: bool = False
    status: str = "pending"


@dataclass
class DecisionContext:
    """决策上下文 - 汇总所有分析结果

    Attributes:
        stock_code: 股票代码
        stock_name: 股票名称
        current_price: 当前价格
        analysis_report: 完整分析报告字典
        portfolio_state: 当前持仓状态
        market_sentiment: 市场情绪
        capital_flow: 资金流向
        position_sizing: 仓位建议
    """
    stock_code: str = ""
    stock_name: str = ""
    current_price: float = 0.0
    analysis_report: Dict[str, Any] = field(default_factory=dict)
    portfolio_state: Optional[Dict[str, Any]] = None
    market_sentiment: Optional[Dict[str, Any]] = None
    capital_flow: Optional[Dict[str, Any]] = None
    position_sizing: Optional[Dict[str, Any]] = None


# ==================== 信号映射常量 ====================

# 买入类信号集合
_BUY_SIGNALS = {"强烈买入", "买入"}
# 卖出类信号集合
_SELL_SIGNALS = {"强烈卖出", "卖出"}
# 高风险等级集合
_HIGH_RISK_LEVELS = {"高风险"}
# 中等风险等级集合
_MODERATE_RISK_LEVELS = {"中等风险"}


# ==================== 决策引擎 ====================

class DecisionEngine:
    """自动决策引擎 - 从分析到可执行决策的核心引擎

    核心能力：
    1. 从分析报告自动生成可执行决策（动作+仓位+止损止盈+紧急度）
    2. 结合持仓状态判断动作类型（新开/加仓/减仓/平仓/观望）
    3. 基于凯利公式简化版计算仓位大小
    4. 基于支撑阻力位计算止损止盈
    5. 决策持久化到SQLite
    6. 决策执行/取消/复盘
    """

    # 仓位控制参数
    MAX_SINGLE_POSITION_PCT = 0.20  # 单只股票最大仓位占比
    HALF_KELLY_FACTOR = 0.5         # 半凯利系数（更保守）
    DEFAULT_STOP_LOSS_PCT = 0.07    # 默认止损比例 7%
    DEFAULT_TAKE_PROFIT_RATIO = 2.0 # 默认风险收益比 2:1
    MIN_LOT_SIZE = 100              # 最小交易单位（A股1手=100股）

    def __init__(self, db: Optional[Database] = None):
        """初始化决策引擎

        Args:
            db: 数据库实例，为空时自动创建默认实例
        """
        self._db = db or Database()
        self._init_decision_table()
        logger.info("[决策引擎] 初始化完成")

    def _init_decision_table(self) -> None:
        """创建决策表（如不存在）"""
        conn = self._db._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    timestamp TEXT NOT NULL,
                    action_json TEXT NOT NULL,
                    analysis_summary TEXT,
                    bull_points_json TEXT DEFAULT '[]',
                    bear_points_json TEXT DEFAULT '[]',
                    key_risks_json TEXT DEFAULT '[]',
                    market_context TEXT,
                    execution_plan TEXT,
                    monitoring_points_json TEXT DEFAULT '[]',
                    auto_execute INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    review_outcome TEXT,
                    review_actual_pnl REAL,
                    reviewed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_decisions_stock ON decisions(stock_code);
                CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
                CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp);
            """)
            conn.commit()
        finally:
            conn.close()

    # ==================== 核心方法 ====================

    def generate_decision(
        self,
        analysis_report: Dict[str, Any],
        portfolio_state: Optional[Dict[str, Any]] = None,
        market_sentiment: Optional[Dict[str, Any]] = None,
        capital_flow: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """从分析报告生成可执行决策 - 核心方法

        将多智能体分析结果转化为包含动作、仓位、止损止盈、紧急度的完整决策。

        Args:
            analysis_report: 完整分析报告字典（AnalysisReport.model_dump()）
            portfolio_state: 当前持仓状态（含positions列表和available_cash）
            market_sentiment: 市场情绪数据
            capital_flow: 资金流向数据

        Returns:
            完整决策对象
        """
        try:
            # 1. 构建决策上下文
            context = self._build_context(
                analysis_report, portfolio_state, market_sentiment, capital_flow
            )

            # 2. 提取信号和置信度
            signal, confidence = self._extract_signal_and_confidence(analysis_report)

            # 3. 提取风险等级
            risk_level = self._extract_risk_level(analysis_report)

            # 4. 判断持仓状态
            has_position, position_pnl_pct = self._get_position_info(
                context.stock_code, portfolio_state
            )

            # 5. 确定动作类型
            action_type = self._determine_action_type(
                signal, confidence, has_position, position_pnl_pct
            )

            # 6. 计算仓位大小
            quantity, position_pct = self._calculate_position_size(
                confidence, risk_level, portfolio_state, context.current_price
            )

            # 7. 计算止损止盈
            stop_loss, take_profit = self._calculate_stop_loss_take_profit(
                context.current_price, signal, analysis_report
            )

            # 8. 计算风险收益比
            risk_reward_ratio = self._calculate_risk_reward_ratio(
                context.current_price, stop_loss, take_profit
            )

            # 9. 判断执行紧急度
            urgency = self._determine_urgency(signal, confidence, risk_level)

            # 10. 判断是否自动执行
            auto_execute = self._should_auto_execute(
                confidence, risk_level, has_position
            )

            # 11. 提取多空观点
            bull_points, bear_points = self._extract_debate_points(analysis_report)

            # 12. 提取关键风险
            key_risks = self._extract_key_risks(analysis_report)

            # 13. 生成市场环境判断
            market_context = self._generate_market_context(
                analysis_report, market_sentiment
            )

            # 14. 生成执行计划
            execution_plan = self._generate_execution_plan(
                action_type, context.stock_code, context.stock_name,
                quantity, context.current_price, stop_loss, take_profit, urgency
            )

            # 15. 生成监控要点
            monitoring_points = self._generate_monitoring_points(
                signal, key_risks, analysis_report
            )

            # 16. 生成分析摘要
            analysis_summary = self._generate_analysis_summary(
                context.stock_code, context.stock_name, signal, confidence, risk_level
            )

            # 17. 确定交易方向
            direction = self._determine_direction(action_type)

            # 18. 计算建议价格区间
            price_range = self._calculate_price_range(context.current_price, signal)

            # 19. 生成决策理由
            reason = self._generate_reason(
                action_type, signal, confidence, risk_level, has_position, position_pnl_pct
            )

            # 20. 组装决策对象
            decision_id = f"DEC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
            action = DecisionAction(
                action_type=action_type,
                stock_code=context.stock_code,
                stock_name=context.stock_name,
                direction=direction,
                quantity=quantity,
                price_range=price_range,
                urgency=urgency,
                reason=reason,
                confidence=confidence,
                risk_reward_ratio=risk_reward_ratio,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_pct=position_pct,
            )

            decision = Decision(
                id=decision_id,
                stock_code=context.stock_code,
                stock_name=context.stock_name,
                timestamp=datetime.now().isoformat(),
                action=action,
                analysis_summary=analysis_summary,
                bull_points=bull_points,
                bear_points=bear_points,
                key_risks=key_risks,
                market_context=market_context,
                execution_plan=execution_plan,
                monitoring_points=monitoring_points,
                auto_execute=auto_execute,
                status="pending",
            )

            # 21. 持久化决策
            self._save_decision(decision)
            logger.info(
                f"[决策引擎] 生成决策: {decision_id} | "
                f"{context.stock_name}({context.stock_code}) | "
                f"动作={action_type} | 置信度={confidence:.2f} | "
                f"紧急度={urgency} | 自动执行={auto_execute}"
            )
            return decision

        except Exception as e:
            logger.error(f"[决策引擎] 生成决策失败: {e}")
            # 返回一个安全的观望决策
            return Decision(
                id=f"DEC-ERR-{uuid.uuid4().hex[:8]}",
                stock_code=analysis_report.get("stock_code", ""),
                stock_name=analysis_report.get("stock_name", ""),
                timestamp=datetime.now().isoformat(),
                action=DecisionAction(
                    action_type="watch",
                    stock_code=analysis_report.get("stock_code", ""),
                    stock_name=analysis_report.get("stock_name", ""),
                    direction="buy",
                    reason=f"决策生成异常，建议观望: {e}",
                ),
                analysis_summary="决策生成异常，已降级为观望",
                status="pending",
            )

    # ==================== 信号提取 ====================

    def _extract_signal_and_confidence(
        self, analysis_report: Dict[str, Any]
    ) -> Tuple[str, float]:
        """从分析报告提取最终信号和置信度

        Args:
            analysis_report: 完整分析报告字典

        Returns:
            (信号字符串, 置信度0-1)
        """
        # 优先使用最终信号
        final_signal = analysis_report.get("final_signal")
        final_confidence = analysis_report.get("final_confidence")

        if final_signal:
            signal_str = final_signal if isinstance(final_signal, str) else str(final_signal)
            confidence = (final_confidence or 50) / 100.0
            return signal_str, confidence

        # 回退：从交易提案提取
        trade_proposal = analysis_report.get("trade_proposal")
        if trade_proposal and isinstance(trade_proposal, dict):
            direction = trade_proposal.get("direction", "")
            direction_str = direction if isinstance(direction, str) else str(direction)
            return direction_str, 0.5

        # 默认持有
        return "持有", 0.3

    def _extract_risk_level(self, analysis_report: Dict[str, Any]) -> str:
        """从分析报告提取风险等级

        Args:
            analysis_report: 完整分析报告字典

        Returns:
            风险等级字符串
        """
        risk_assessment = analysis_report.get("risk_assessment")
        if risk_assessment and isinstance(risk_assessment, dict):
            risk_level = risk_assessment.get("risk_level", "中等风险")
            return risk_level if isinstance(risk_level, str) else str(risk_level)
        return "中等风险"

    def _get_position_info(
        self, stock_code: str, portfolio_state: Optional[Dict[str, Any]]
    ) -> Tuple[bool, float]:
        """获取持仓信息

        Args:
            stock_code: 股票代码
            portfolio_state: 持仓状态字典

        Returns:
            (是否持仓, 持仓盈亏比例%)
        """
        if not portfolio_state:
            return False, 0.0

        positions = portfolio_state.get("positions", [])
        for pos in positions:
            if pos.get("stock_code") == stock_code:
                pnl_pct = pos.get("unrealized_pnl_pct", 0.0) or 0.0
                return True, pnl_pct

        return False, 0.0

    # ==================== 动作判断 ====================

    def _determine_action_type(
        self,
        signal: str,
        confidence: float,
        has_position: bool,
        position_pnl_pct: float,
    ) -> str:
        """根据信号+持仓状态确定动作类型

        决策矩阵：
        - 无持仓 + 买入信号 → open_long
        - 无持仓 + 卖出信号 → watch
        - 有持仓盈利 + 买入信号 → add_position
        - 有持仓盈利 + 卖出信号 → close_long (止盈)
        - 有持仓亏损 + 买入信号 → hold (不补仓)
        - 有持仓亏损 + 卖出信号 → close_long (止损)
        - 信号不明确 → watch

        Args:
            signal: 交易信号
            confidence: 置信度
            has_position: 是否持仓
            position_pnl_pct: 持仓盈亏比例%

        Returns:
            动作类型字符串
        """
        is_buy_signal = signal in _BUY_SIGNALS
        is_sell_signal = signal in _SELL_SIGNALS

        # 信号不明确 → 观望
        if not is_buy_signal and not is_sell_signal:
            return "watch"

        # 无持仓
        if not has_position:
            if is_buy_signal:
                return "open_long"
            # 无持仓+卖出信号 → 观望（无法卖出）
            return "watch"

        # 有持仓
        is_profitable = position_pnl_pct > 0

        if is_buy_signal:
            if is_profitable:
                # 盈利中+买入信号 → 加仓（仅高置信度）
                if confidence >= 0.7:
                    return "add_position"
                return "hold"
            # 亏损中+买入信号 → 持有（不补仓）
            return "hold"

        # 卖出信号
        if is_profitable:
            return "close_long"  # 止盈
        return "close_long"  # 止损

    # ==================== 仓位计算 ====================

    def _calculate_position_size(
        self,
        confidence: float,
        risk_level: str,
        portfolio_state: Optional[Dict[str, Any]],
        current_price: float,
    ) -> Tuple[int, float]:
        """计算仓位大小 - 基于凯利公式简化版

        凯利公式: f = (bp - q) / b
        b = 盈亏比, p = 胜率(用置信度近似), q = 1 - p
        实际使用半凯利（更保守）: f = kelly / 2
        最大单只仓位不超过20%
        高风险时减半

        Args:
            confidence: 置信度 0-1
            risk_level: 风险等级
            portfolio_state: 持仓状态
            current_price: 当前价格

        Returns:
            (建议数量股, 仓位占比0-1)
        """
        # 获取组合总价值
        portfolio_value = 1000000.0  # 默认100万
        if portfolio_state:
            portfolio_value = portfolio_state.get(
                "total_market_value",
                portfolio_state.get("available_cash", 1000000.0)
            )
            if not portfolio_value or portfolio_value <= 0:
                portfolio_value = 1000000.0

        # 凯利公式参数
        p = confidence  # 胜率近似
        q = 1 - p
        b = self.DEFAULT_TAKE_PROFIT_RATIO  # 盈亏比

        # 凯利值
        kelly = (b * p - q) / b if b > 0 else 0
        kelly = max(kelly, 0)  # 不允许负仓位

        # 半凯利
        position_pct = kelly * self.HALF_KELLY_FACTOR

        # 高风险减半
        if risk_level in _HIGH_RISK_LEVELS:
            position_pct *= 0.5
        elif risk_level in _MODERATE_RISK_LEVELS:
            position_pct *= 0.75

        # 上限控制
        position_pct = min(position_pct, self.MAX_SINGLE_POSITION_PCT)

        # 价格无效时返回0
        if current_price <= 0:
            return 0, 0.0

        # 计算股数（取整到100的整数倍）
        target_amount = portfolio_value * position_pct
        quantity = int(target_amount / current_price)
        quantity = (quantity // self.MIN_LOT_SIZE) * self.MIN_LOT_SIZE

        return quantity, round(position_pct, 4)

    # ==================== 止损止盈 ====================

    def _calculate_stop_loss_take_profit(
        self,
        current_price: float,
        signal: str,
        technical_data: Dict[str, Any],
    ) -> Tuple[float, float]:
        """计算止损止盈价

        止损：最近支撑位下方2%，或固定5-8%
        止盈：最近阻力位上方2%，或风险收益比2:1

        Args:
            current_price: 当前价格
            signal: 交易信号
            technical_data: 技术分析数据

        Returns:
            (止损价, 止盈价)
        """
        if current_price <= 0:
            return 0.0, 0.0

        # 提取技术分析中的支撑阻力位
        technical = technical_data.get("technical")
        support_levels: List[float] = []
        resistance_levels: List[float] = []

        if technical and isinstance(technical, dict):
            support_levels = technical.get("support_levels", [])
            resistance_levels = technical.get("resistance_levels", [])

        # 计算止损价
        stop_loss = self._calc_stop_loss(current_price, support_levels)

        # 计算止盈价
        take_profit = self._calc_take_profit(current_price, resistance_levels, stop_loss)

        return round(stop_loss, 2), round(take_profit, 2)

    def _calc_stop_loss(
        self, current_price: float, support_levels: List[float]
    ) -> float:
        """计算止损价

        优先使用最近支撑位下方2%，否则使用固定比例7%

        Args:
            current_price: 当前价格
            support_levels: 支撑位列表

        Returns:
            止损价
        """
        # 尝试使用支撑位
        valid_supports = [s for s in support_levels if 0 < s < current_price]
        if valid_supports:
            nearest_support = max(valid_supports)
            stop_loss = nearest_support * 0.98  # 支撑位下方2%
            # 确保止损价不低于当前价的92%（最大止损8%）
            min_stop = current_price * (1 - 0.08)
            stop_loss = max(stop_loss, min_stop)
        else:
            # 无支撑位数据，使用固定7%止损
            stop_loss = current_price * (1 - self.DEFAULT_STOP_LOSS_PCT)

        return stop_loss

    def _calc_take_profit(
        self,
        current_price: float,
        resistance_levels: List[float],
        stop_loss: float,
    ) -> float:
        """计算止盈价

        优先使用最近阻力位上方2%，否则使用风险收益比2:1

        Args:
            current_price: 当前价格
            resistance_levels: 阻力位列表
            stop_loss: 止损价

        Returns:
            止盈价
        """
        # 尝试使用阻力位
        valid_resistances = [r for r in resistance_levels if r > current_price]
        if valid_resistances:
            nearest_resistance = min(valid_resistances)
            take_profit = nearest_resistance * 1.02  # 阻力位上方2%
        else:
            # 无阻力位数据，使用风险收益比
            risk = current_price - stop_loss
            take_profit = current_price + risk * self.DEFAULT_TAKE_PROFIT_RATIO

        return take_profit

    # ==================== 紧急度判断 ====================

    def _determine_urgency(
        self, signal: str, confidence: float, risk_level: str
    ) -> str:
        """判断执行紧急度

        - 强烈买入+高置信度+非高风险 → immediate
        - 买入+中等置信度 → intraday
        - 一般信号 → within_3_days
        - 不明确 → watch

        Args:
            signal: 交易信号
            confidence: 置信度
            risk_level: 风险等级

        Returns:
            紧急度字符串
        """
        is_buy_signal = signal in _BUY_SIGNALS
        is_sell_signal = signal in _SELL_SIGNALS
        is_high_risk = risk_level in _HIGH_RISK_LEVELS

        # 强烈信号+高置信度+风险可控 → 立即执行
        if (signal == "强烈买入" or signal == "强烈卖出") and confidence >= 0.8 and not is_high_risk:
            return "immediate"

        # 买入/卖出+中等置信度 → 日内执行
        if (is_buy_signal or is_sell_signal) and confidence >= 0.6:
            return "intraday"

        # 一般信号 → 3日内
        if is_buy_signal or is_sell_signal:
            return "within_3_days"

        # 不明确 → 观察
        return "watch"

    # ==================== 监控要点 ====================

    def _generate_monitoring_points(
        self,
        signal: str,
        key_risks: List[str],
        technical_data: Dict[str, Any],
    ) -> List[str]:
        """生成监控要点 - 什么情况下需要重新评估

        Args:
            signal: 交易信号
            key_risks: 关键风险列表
            technical_data: 技术分析数据

        Returns:
            监控要点列表
        """
        points: List[str] = []

        # 通用监控点
        points.append("跌破止损价时立即重新评估")
        points.append("成交量异常放大（超过20日均量2倍）时关注")

        # 基于信号类型
        if signal in _BUY_SIGNALS:
            points.append("大盘跌破关键支撑位时需谨慎")
        elif signal in _SELL_SIGNALS:
            points.append("若出现利好消息需重新评估卖出逻辑")

        # 基于风险
        for risk in key_risks[:3]:
            points.append(f"关注风险变化: {risk}")

        # 基于技术指标
        technical = technical_data.get("technical")
        if technical and isinstance(technical, dict):
            indicators = technical.get("indicators", {})
            if indicators and isinstance(indicators, dict):
                rsi = indicators.get("rsi")
                if rsi is not None:
                    try:
                        rsi_val = float(rsi)
                        if rsi_val > 70:
                            points.append("RSI超买区域，注意回调风险")
                        elif rsi_val < 30:
                            points.append("RSI超卖区域，关注反弹机会")
                    except (ValueError, TypeError):
                        pass

        points.append("行业政策发生重大变化时需重新评估")

        return points

    # ==================== 自动执行判断 ====================

    def _should_auto_execute(
        self, confidence: float, risk_level: str, has_position: bool
    ) -> bool:
        """判断是否自动执行

        条件：置信度>0.8 AND 风险等级非高 AND 无持仓(避免重复开仓)

        Args:
            confidence: 置信度
            risk_level: 风险等级
            has_position: 是否已有持仓

        Returns:
            是否自动执行
        """
        if confidence < 0.8:
            return False
        if risk_level in _HIGH_RISK_LEVELS:
            return False
        if has_position:
            return False
        return True

    # ==================== 辅助方法 ====================

    def _build_context(
        self,
        analysis_report: Dict[str, Any],
        portfolio_state: Optional[Dict[str, Any]],
        market_sentiment: Optional[Dict[str, Any]],
        capital_flow: Optional[Dict[str, Any]],
    ) -> DecisionContext:
        """构建决策上下文

        Args:
            analysis_report: 分析报告
            portfolio_state: 持仓状态
            market_sentiment: 市场情绪
            capital_flow: 资金流向

        Returns:
            决策上下文对象
        """
        current_price = analysis_report.get("current_price") or 0.0
        if current_price is None:
            current_price = 0.0

        return DecisionContext(
            stock_code=analysis_report.get("stock_code", ""),
            stock_name=analysis_report.get("stock_name", ""),
            current_price=float(current_price),
            analysis_report=analysis_report,
            portfolio_state=portfolio_state,
            market_sentiment=market_sentiment,
            capital_flow=capital_flow,
        )

    def _extract_debate_points(
        self, analysis_report: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        """提取多空辩论要点

        Args:
            analysis_report: 分析报告

        Returns:
            (看多要点列表, 看空要点列表)
        """
        debate = analysis_report.get("debate")
        if not debate or not isinstance(debate, dict):
            return [], []

        bull_args = debate.get("bull_arguments", [])
        bear_args = debate.get("bear_arguments", [])
        return list(bull_args), list(bear_args)

    def _extract_key_risks(
        self, analysis_report: Dict[str, Any]
    ) -> List[str]:
        """提取关键风险

        Args:
            analysis_report: 分析报告

        Returns:
            关键风险列表
        """
        risks: List[str] = []

        # 从风险评估提取
        risk_assessment = analysis_report.get("risk_assessment")
        if risk_assessment and isinstance(risk_assessment, dict):
            suggestions = risk_assessment.get("risk_control_suggestions", [])
            risks.extend(suggestions)

        # 从新闻分析提取风险事件
        news = analysis_report.get("news")
        if news and isinstance(news, dict):
            risk_events = news.get("risk_events", [])
            for event in risk_events:
                if isinstance(event, dict):
                    desc = event.get("description", event.get("event", ""))
                    if desc:
                        risks.append(str(desc))
                elif isinstance(event, str):
                    risks.append(event)

        return risks[:5]  # 最多5条

    def _generate_market_context(
        self,
        analysis_report: Dict[str, Any],
        market_sentiment: Optional[Dict[str, Any]],
    ) -> str:
        """生成市场环境判断

        Args:
            analysis_report: 分析报告
            market_sentiment: 市场情绪

        Returns:
            市场环境描述
        """
        parts: List[str] = []

        # 从情绪分析提取
        sentiment = analysis_report.get("sentiment")
        if sentiment and isinstance(sentiment, dict):
            market_sent = sentiment.get("market_sentiment", "")
            if market_sent:
                parts.append(f"市场情绪: {market_sent}")

        # 从新闻分析提取宏观影响
        news = analysis_report.get("news")
        if news and isinstance(news, dict):
            macro_impact = news.get("macro_impact", "")
            if macro_impact:
                parts.append(f"宏观影响: {macro_impact}")

        # 外部市场情绪数据
        if market_sentiment and isinstance(market_sentiment, dict):
            overall = market_sentiment.get("overall", "")
            if overall:
                parts.append(f"整体评估: {overall}")

        return " | ".join(parts) if parts else "市场环境数据不足"

    def _generate_execution_plan(
        self,
        action_type: str,
        stock_code: str,
        stock_name: str,
        quantity: int,
        current_price: float,
        stop_loss: float,
        take_profit: float,
        urgency: str,
    ) -> str:
        """生成执行计划

        Args:
            action_type: 动作类型
            stock_code: 股票代码
            stock_name: 股票名称
            quantity: 数量
            current_price: 当前价格
            stop_loss: 止损价
            take_profit: 止盈价
            urgency: 紧急度

        Returns:
            执行计划文本
        """
        urgency_map = {
            "immediate": "立即执行",
            "intraday": "今日内执行",
            "within_3_days": "3个交易日内执行",
            "watch": "持续观察，暂不执行",
        }

        action_map = {
            "open_long": f"开仓买入 {stock_name}({stock_code})",
            "close_long": f"平仓卖出 {stock_name}({stock_code})",
            "add_position": f"加仓买入 {stock_name}({stock_code})",
            "reduce_position": f"减仓卖出 {stock_name}({stock_code})",
            "hold": f"继续持有 {stock_name}({stock_code})",
            "watch": f"观望 {stock_name}({stock_code})",
            "open_short": f"开空 {stock_name}({stock_code})",
            "close_short": f"平空 {stock_name}({stock_code})",
        }

        action_desc = action_map.get(action_type, f"操作 {stock_name}")
        urgency_desc = urgency_map.get(urgency, "待定")

        if action_type in ("watch", "hold"):
            return f"{action_desc}，{urgency_desc}"

        amount = quantity * current_price if quantity > 0 and current_price > 0 else 0

        plan_parts = [
            f"1. {action_desc} {quantity}股",
            f"2. 参考价格: {current_price:.2f}元",
            f"3. 止损价: {stop_loss:.2f}元 (亏损{((current_price - stop_loss) / current_price * 100):.1f}%时止损)",
            f"4. 止盈价: {take_profit:.2f}元 (盈利{((take_profit - current_price) / current_price * 100):.1f}%时止盈)",
            f"5. 预计金额: {amount:,.0f}元",
            f"6. 执行时机: {urgency_desc}",
        ]

        return "\n".join(plan_parts)

    def _generate_analysis_summary(
        self,
        stock_code: str,
        stock_name: str,
        signal: str,
        confidence: float,
        risk_level: str,
    ) -> str:
        """生成分析摘要

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            signal: 信号
            confidence: 置信度
            risk_level: 风险等级

        Returns:
            分析摘要文本
        """
        return (
            f"{stock_name}({stock_code}) 综合信号: {signal}，"
            f"置信度: {confidence:.0%}，风险等级: {risk_level}"
        )

    def _determine_direction(self, action_type: str) -> str:
        """根据动作类型确定交易方向

        Args:
            action_type: 动作类型

        Returns:
            交易方向 buy/sell
        """
        sell_actions = {"close_long", "reduce_position", "close_short"}
        return "sell" if action_type in sell_actions else "buy"

    def _calculate_price_range(
        self, current_price: float, signal: str
    ) -> Tuple[float, float]:
        """计算建议价格区间

        Args:
            current_price: 当前价格
            signal: 交易信号

        Returns:
            (价格下限, 价格上限)
        """
        if current_price <= 0:
            return (0.0, 0.0)

        # 买入信号：当前价-1% 到 当前价+1%
        # 卖出信号：当前价-1% 到 当前价+1%
        lower = round(current_price * 0.99, 2)
        upper = round(current_price * 1.01, 2)
        return (lower, upper)

    def _calculate_risk_reward_ratio(
        self, current_price: float, stop_loss: float, take_profit: float
    ) -> float:
        """计算风险收益比

        Args:
            current_price: 当前价格
            stop_loss: 止损价
            take_profit: 止盈价

        Returns:
            风险收益比
        """
        risk = current_price - stop_loss
        reward = take_profit - current_price
        if risk <= 0:
            return 0.0
        return round(reward / risk, 2)

    def _generate_reason(
        self,
        action_type: str,
        signal: str,
        confidence: float,
        risk_level: str,
        has_position: bool,
        position_pnl_pct: float,
    ) -> str:
        """生成决策理由

        Args:
            action_type: 动作类型
            signal: 信号
            confidence: 置信度
            risk_level: 风险等级
            has_position: 是否持仓
            position_pnl_pct: 持仓盈亏比例

        Returns:
            决策理由文本
        """
        reason_parts = [f"综合信号为【{signal}】"]

        if confidence >= 0.8:
            reason_parts.append("高置信度")
        elif confidence >= 0.6:
            reason_parts.append("中等置信度")
        else:
            reason_parts.append("低置信度，建议谨慎")

        reason_parts.append(f"风险等级{risk_level}")

        if has_position:
            if position_pnl_pct > 0:
                reason_parts.append(f"当前持仓盈利{position_pnl_pct:.1f}%")
            elif position_pnl_pct < 0:
                reason_parts.append(f"当前持仓亏损{abs(position_pnl_pct):.1f}%")
        else:
            reason_parts.append("当前无持仓")

        # 动作特定理由
        action_reasons = {
            "open_long": "建议新开多头仓位",
            "close_long": "建议平仓了结" + ("（止盈）" if position_pnl_pct > 0 else "（止损）"),
            "add_position": "持仓盈利且信号持续偏多，建议加仓",
            "reduce_position": "建议减仓降低风险敞口",
            "hold": "建议继续持有，等待更明确信号",
            "watch": "信号不够明确，建议观望等待",
        }
        action_reason = action_reasons.get(action_type, "")
        if action_reason:
            reason_parts.append(action_reason)

        return "，".join(reason_parts)

    # ==================== 决策持久化 ====================

    def _save_decision(self, decision: Decision) -> None:
        """持久化决策到SQLite

        Args:
            decision: 决策对象
        """
        conn = self._db._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO decisions
                (id, stock_code, stock_name, timestamp, action_json,
                 analysis_summary, bull_points_json, bear_points_json,
                 key_risks_json, market_context, execution_plan,
                 monitoring_points_json, auto_execute, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    decision.id,
                    decision.stock_code,
                    decision.stock_name,
                    decision.timestamp,
                    json.dumps(asdict(decision.action), ensure_ascii=False),
                    decision.analysis_summary,
                    json.dumps(decision.bull_points, ensure_ascii=False),
                    json.dumps(decision.bear_points, ensure_ascii=False),
                    json.dumps(decision.key_risks, ensure_ascii=False),
                    decision.market_context,
                    decision.execution_plan,
                    json.dumps(decision.monitoring_points, ensure_ascii=False),
                    1 if decision.auto_execute else 0,
                    decision.status,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _decision_from_row(self, row: Dict[str, Any]) -> Decision:
        """从数据库行构建Decision对象

        Args:
            row: 数据库行字典

        Returns:
            Decision对象
        """
        action_data = json.loads(row.get("action_json", "{}"))
        action = DecisionAction(
            action_type=action_data.get("action_type", "watch"),
            stock_code=action_data.get("stock_code", ""),
            stock_name=action_data.get("stock_name", ""),
            direction=action_data.get("direction", "buy"),
            quantity=action_data.get("quantity", 0),
            price_range=tuple(action_data.get("price_range", [0.0, 0.0])),
            urgency=action_data.get("urgency", "watch"),
            reason=action_data.get("reason", ""),
            confidence=action_data.get("confidence", 0.0),
            risk_reward_ratio=action_data.get("risk_reward_ratio", 0.0),
            stop_loss=action_data.get("stop_loss", 0.0),
            take_profit=action_data.get("take_profit", 0.0),
            position_pct=action_data.get("position_pct", 0.0),
        )

        return Decision(
            id=row.get("id", ""),
            stock_code=row.get("stock_code", ""),
            stock_name=row.get("stock_name", ""),
            timestamp=row.get("timestamp", ""),
            action=action,
            analysis_summary=row.get("analysis_summary", ""),
            bull_points=json.loads(row.get("bull_points_json", "[]")),
            bear_points=json.loads(row.get("bear_points_json", "[]")),
            key_risks=json.loads(row.get("key_risks_json", "[]")),
            market_context=row.get("market_context", ""),
            execution_plan=row.get("execution_plan", ""),
            monitoring_points=json.loads(row.get("monitoring_points_json", "[]")),
            auto_execute=bool(row.get("auto_execute", 0)),
            status=row.get("status", "pending"),
        )

    # ==================== 决策操作 ====================

    def execute_decision(self, decision_id: str) -> Dict[str, Any]:
        """执行决策 - 调用模拟交易服务

        Args:
            decision_id: 决策ID

        Returns:
            执行结果字典
        """
        try:
            decision = self._get_decision_by_id(decision_id)
            if not decision:
                return {"success": False, "message": f"决策不存在: {decision_id}"}

            if decision.status != "pending":
                return {"success": False, "message": f"决策状态非待执行: {decision.status}"}

            action = decision.action

            # 调用模拟交易服务
            from astock_agents.services.paper_trading import PaperTradingService
            from astock_agents.models.portfolio import TradeDirection

            pt = PaperTradingService(db=self._db)

            if action.quantity <= 0:
                return {"success": False, "message": "建议数量为0，无需执行"}

            direction = TradeDirection.BUY if action.direction == "buy" else TradeDirection.SELL
            order = pt.place_order(
                stock_code=action.stock_code,
                stock_name=action.stock_name,
                direction=direction,
                quantity=action.quantity,
                reason=action.reason,
                signal_source=f"决策引擎-{decision.id}",
            )

            # 更新决策状态
            self._update_decision_status(decision_id, "executed")

            logger.info(
                f"[决策引擎] 执行决策: {decision_id} | "
                f"订单={order.order_id} | {action.direction} "
                f"{action.stock_name} {action.quantity}股"
            )

            return {
                "success": True,
                "message": f"决策已执行，订单号: {order.order_id}",
                "order_id": order.order_id,
                "decision_id": decision_id,
            }

        except Exception as e:
            logger.error(f"[决策引擎] 执行决策失败: {decision_id}, {e}")
            return {"success": False, "message": f"执行失败: {e}"}

    def cancel_decision(self, decision_id: str, reason: str = "") -> bool:
        """取消决策

        Args:
            decision_id: 决策ID
            reason: 取消理由

        Returns:
            是否取消成功
        """
        try:
            decision = self._get_decision_by_id(decision_id)
            if not decision:
                logger.warning(f"[决策引擎] 取消决策失败，决策不存在: {decision_id}")
                return False

            if decision.status != "pending":
                logger.warning(f"[决策引擎] 取消决策失败，状态非待执行: {decision.status}")
                return False

            self._update_decision_status(decision_id, "cancelled")
            logger.info(f"[决策引擎] 取消决策: {decision_id}, 理由: {reason}")
            return True

        except Exception as e:
            logger.error(f"[决策引擎] 取消决策异常: {decision_id}, {e}")
            return False

    def get_pending_decisions(self) -> List[Decision]:
        """获取待执行决策

        Returns:
            待执行决策列表，按时间倒序
        """
        conn = self._db._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM decisions WHERE status='pending' ORDER BY timestamp DESC"
            ).fetchall()
            return [self._decision_from_row(dict(r)) for r in rows]
        except Exception as e:
            logger.error(f"[决策引擎] 获取待执行决策失败: {e}")
            return []
        finally:
            conn.close()

    def get_decision_history(
        self, stock_code: str = "", limit: int = 50
    ) -> List[Decision]:
        """获取决策历史

        Args:
            stock_code: 股票代码筛选，为空时返回全部
            limit: 返回条数上限

        Returns:
            决策历史列表，按时间倒序
        """
        conn = self._db._get_conn()
        try:
            if stock_code:
                rows = conn.execute(
                    "SELECT * FROM decisions WHERE stock_code=? ORDER BY timestamp DESC LIMIT ?",
                    (stock_code, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._decision_from_row(dict(r)) for r in rows]
        except Exception as e:
            logger.error(f"[决策引擎] 获取决策历史失败: {e}")
            return []
        finally:
            conn.close()

    def review_decision(
        self, decision_id: str, outcome: str, actual_pnl: float
    ) -> Dict[str, Any]:
        """决策复盘 - 记录决策结果，用于持续优化

        Args:
            decision_id: 决策ID
            outcome: 决策结果（如"盈利"/"亏损"/"持平"/"未执行"）
            actual_pnl: 实际盈亏金额

        Returns:
            复盘结果字典
        """
        try:
            decision = self._get_decision_by_id(decision_id)
            if not decision:
                return {"success": False, "message": f"决策不存在: {decision_id}"}

            conn = self._db._get_conn()
            try:
                conn.execute(
                    """UPDATE decisions
                    SET review_outcome=?, review_actual_pnl=?, reviewed_at=?
                    WHERE id=?""",
                    (outcome, actual_pnl, datetime.now().isoformat(), decision_id),
                )
                conn.commit()
            finally:
                conn.close()

            logger.info(
                f"[决策引擎] 决策复盘: {decision_id} | "
                f"结果={outcome} | 实际盈亏={actual_pnl:.2f}"
            )

            return {
                "success": True,
                "message": "复盘记录已保存",
                "decision_id": decision_id,
                "outcome": outcome,
                "actual_pnl": actual_pnl,
                "original_confidence": decision.action.confidence,
                "original_action": decision.action.action_type,
            }

        except Exception as e:
            logger.error(f"[决策引擎] 决策复盘失败: {decision_id}, {e}")
            return {"success": False, "message": f"复盘失败: {e}"}

    # ==================== 内部查询 ====================

    def _get_decision_by_id(self, decision_id: str) -> Optional[Decision]:
        """根据ID获取决策

        Args:
            decision_id: 决策ID

        Returns:
            Decision对象，不存在时返回None
        """
        conn = self._db._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM decisions WHERE id=?", (decision_id,)
            ).fetchone()
            if row:
                return self._decision_from_row(dict(row))
            return None
        except Exception as e:
            logger.error(f"[决策引擎] 查询决策失败: {decision_id}, {e}")
            return None
        finally:
            conn.close()

    def _update_decision_status(self, decision_id: str, status: str) -> None:
        """更新决策状态

        Args:
            decision_id: 决策ID
            status: 新状态
        """
        conn = self._db._get_conn()
        try:
            conn.execute(
                "UPDATE decisions SET status=? WHERE id=?",
                (status, decision_id),
            )
            conn.commit()
        finally:
            conn.close()
