"""智能仓位管理 - 基于风险预算的仓位配置

核心能力：
1. 凯利公式计算最优仓位
2. 半凯利保守策略
3. 风险平价模型（基于波动率分配）
4. 最大回撤约束
5. 相关性调整（高相关股票减仓）
6. 组合级仓位建议
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from loguru import logger


@dataclass
class PositionSizingResult:
    """仓位计算结果

    Attributes:
        stock_code: 股票代码
        recommended_pct: 建议仓位占比 0-1
        recommended_amount: 建议金额
        recommended_shares: 建议股数（100整数倍）
        max_pct: 最大允许仓位
        kelly_pct: 凯利公式计算值
        half_kelly_pct: 半凯利值
        risk_contribution: 风险贡献度
        reasoning: 仓位计算理由
    """

    stock_code: str = ""
    recommended_pct: float = 0.0
    recommended_amount: float = 0.0
    recommended_shares: int = 0
    max_pct: float = 0.25
    kelly_pct: float = 0.0
    half_kelly_pct: float = 0.0
    risk_contribution: float = 0.0
    reasoning: str = ""


class PositionSizingService:
    """智能仓位管理 - 基于风险预算的仓位配置

    通过凯利公式、半凯利策略、风险平价模型等方法，
    结合信号强度、置信度、风险等级等因素，计算最优仓位配置。
    """

    # 默认参数
    DEFAULT_MAX_POSITION: float = 0.25      # 单只股票最大仓位25%
    DEFAULT_MAX_PORTFOLIO: float = 0.95     # 组合最大总仓位95%
    DEFAULT_RISK_FREE_RATE: float = 0.03    # 无风险利率3%
    DEFAULT_STOP_LOSS: float = 0.07         # 默认止损比例7%

    # 信号到胜率的映射
    SIGNAL_WIN_RATE_MAP: Dict[str, float] = {
        "strong_buy": 0.70,
        "buy": 0.60,
        "hold": 0.50,
        "sell": 0.35,
        "strong_sell": 0.25,
    }

    # 信号到盈亏比的映射
    SIGNAL_WIN_LOSS_RATIO_MAP: Dict[str, float] = {
        "strong_buy": 3.0,
        "buy": 2.0,
        "hold": 1.0,
        "sell": 0.8,
        "strong_sell": 0.5,
    }

    # 风险等级到仓位调整系数的映射
    RISK_LEVEL_ADJUST_MAP: Dict[str, float] = {
        "low": 1.2,
        "moderate": 1.0,
        "high": 0.6,
        "extreme": 0.3,
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化仓位管理服务

        Args:
            config: 配置字典（可选）
        """
        self.config = config or {}
        self.max_position = self.config.get("max_position", self.DEFAULT_MAX_POSITION)
        self.max_portfolio = self.config.get("max_portfolio", self.DEFAULT_MAX_PORTFOLIO)
        logger.info("[PositionSizing] 智能仓位管理服务初始化完成")

    def calculate_position(
        self,
        signal: str,
        confidence: float,
        risk_level: str,
        portfolio_value: float,
        stop_loss_pct: float,
        current_positions: Optional[List[Dict[str, Any]]] = None,
        stock_code: str = "",
        current_price: Optional[float] = None,
    ) -> PositionSizingResult:
        """计算单只股票的建议仓位

        Args:
            signal: 交易信号 ("strong_buy" / "buy" / "hold" / "sell" / "strong_sell")
            confidence: 信号置信度 0-100
            risk_level: 风险等级 ("low" / "moderate" / "high" / "extreme")
            portfolio_value: 组合总价值
            stop_loss_pct: 止损比例 0-1
            current_positions: 当前持仓列表
            stock_code: 股票代码
            current_price: 当前股价

        Returns:
            PositionSizingResult 仓位计算结果
        """
        logger.info(
            f"[PositionSizing] 计算仓位: {stock_code}, 信号={signal}, "
            f"置信度={confidence}, 风险={risk_level}"
        )

        try:
            # 1. 计算凯利公式值
            win_rate = self._estimate_win_rate(signal, confidence)
            win_loss_ratio = self._estimate_win_loss_ratio(signal, confidence)
            kelly_pct = self._kelly_criterion(win_rate, win_loss_ratio)

            # 2. 半凯利策略（保守）
            half_kelly_pct = kelly_pct / 2

            # 3. 风险等级调整
            risk_adjust = self.RISK_LEVEL_ADJUST_MAP.get(risk_level, 1.0)

            # 4. 止损约束：基于风险的仓位 = 可承受亏损 / 止损比例
            max_risk_pct = 0.02  # 单笔最大亏损2%组合价值
            risk_based_pct = max_risk_pct / stop_loss_pct if stop_loss_pct > 0 else self.max_position

            # 5. 综合确定建议仓位
            # 取半凯利和风险约束中的较小值，再乘以风险调整系数
            base_pct = min(half_kelly_pct, risk_based_pct) * risk_adjust

            # 6. 最大仓位约束
            max_pct = self.max_position
            recommended_pct = max(0.0, min(base_pct, max_pct))

            # 7. 已有持仓调整
            if current_positions:
                existing_pct = self._calc_existing_position_pct(
                    stock_code, current_positions, portfolio_value
                )
                available_pct = max(0.0, max_pct - existing_pct)
                recommended_pct = min(recommended_pct, available_pct)

            # 8. 组合总仓位约束
            if current_positions:
                total_existing_pct = sum(
                    p.get("pct", 0) for p in current_positions
                )
                remaining_pct = self.max_portfolio - total_existing_pct
                recommended_pct = max(0.0, min(recommended_pct, remaining_pct))

            # 9. 信号方向过滤：卖出信号仓位为0
            if signal in ("sell", "strong_sell"):
                recommended_pct = 0.0

            # 10. 计算具体金额和股数
            recommended_amount = recommended_pct * portfolio_value
            recommended_shares = 0
            if current_price and current_price > 0:
                raw_shares = recommended_amount / current_price
                # A股最小交易单位100股
                recommended_shares = max(0, int(raw_shares // 100) * 100)

            # 11. 计算风险贡献度
            risk_contribution = recommended_pct * stop_loss_pct

            # 12. 生成仓位计算理由
            reasoning = self._generate_reasoning(
                signal, confidence, risk_level, win_rate, win_loss_ratio,
                kelly_pct, half_kelly_pct, risk_adjust, risk_based_pct,
                recommended_pct, stop_loss_pct
            )

            result = PositionSizingResult(
                stock_code=stock_code,
                recommended_pct=round(recommended_pct, 4),
                recommended_amount=round(recommended_amount, 2),
                recommended_shares=recommended_shares,
                max_pct=round(max_pct, 4),
                kelly_pct=round(kelly_pct, 4),
                half_kelly_pct=round(half_kelly_pct, 4),
                risk_contribution=round(risk_contribution, 4),
                reasoning=reasoning,
            )

            logger.info(
                f"[PositionSizing] 仓位计算完成: {stock_code}, "
                f"建议仓位={result.recommended_pct * 100:.1f}%, "
                f"建议金额={result.recommended_amount:.0f}, "
                f"建议股数={result.recommended_shares}"
            )
            return result

        except Exception as e:
            logger.error(f"[PositionSizing] 仓位计算失败: {e}")
            return PositionSizingResult(
                stock_code=stock_code,
                reasoning=f"仓位计算失败: {e}",
            )

    def calculate_portfolio_allocation(
        self,
        signals: List[Dict[str, Any]],
        portfolio_value: float,
        current_positions: Optional[List[Dict[str, Any]]] = None,
    ) -> List[PositionSizingResult]:
        """计算组合级仓位配置

        基于风险平价模型，根据各股票的波动率分配仓位，
        确保每只股票的风险贡献大致相等。

        Args:
            signals: 信号列表，每项包含 stock_code, signal, confidence, risk_level, stop_loss_pct 等
            portfolio_value: 组合总价值
            current_positions: 当前持仓列表

        Returns:
            各股票的 PositionSizingResult 列表
        """
        logger.info(f"[PositionSizing] 计算组合级仓位配置，共{len(signals)}只股票")

        try:
            if not signals:
                return []

            # 1. 过滤出买入信号
            buy_signals = [
                s for s in signals
                if s.get("signal") in ("strong_buy", "buy")
            ]

            if not buy_signals:
                logger.info("[PositionSizing] 无买入信号，组合仓位为空")
                return []

            # 2. 计算各股票的初始仓位
            results: List[PositionSizingResult] = []
            for sig in buy_signals:
                result = self.calculate_position(
                    signal=sig.get("signal", "hold"),
                    confidence=sig.get("confidence", 50),
                    risk_level=sig.get("risk_level", "moderate"),
                    portfolio_value=portfolio_value,
                    stop_loss_pct=sig.get("stop_loss_pct", self.DEFAULT_STOP_LOSS),
                    current_positions=current_positions,
                    stock_code=sig.get("stock_code", ""),
                    current_price=sig.get("current_price"),
                )
                results.append(result)

            # 3. 风险平价调整：确保各股票风险贡献均衡
            results = self._apply_risk_parity(results)

            # 4. 组合总仓位约束
            total_pct = sum(r.recommended_pct for r in results)
            if total_pct > self.max_portfolio:
                scale_factor = self.max_portfolio / total_pct
                for r in results:
                    r.recommended_pct = round(r.recommended_pct * scale_factor, 4)
                    r.recommended_amount = round(r.recommended_pct * portfolio_value, 2)
                    if r.recommended_pct > 0:
                        # 重新计算股数（需要价格信息）
                        pass

            # 5. 相关性调整（简化版：同行业股票减仓）
            results = self._apply_correlation_adjustment(results, signals)

            logger.info(
                f"[PositionSizing] 组合仓位配置完成，"
                f"总仓位={sum(r.recommended_pct for r in results) * 100:.1f}%"
            )
            return results

        except Exception as e:
            logger.error(f"[PositionSizing] 组合仓位计算失败: {e}")
            return []

    def _kelly_criterion(self, win_rate: float, win_loss_ratio: float) -> float:
        """凯利公式: f = (p * b - q) / b

        其中 p = 胜率, q = 1 - p, b = 盈亏比

        Args:
            win_rate: 胜率 0-1
            win_loss_ratio: 盈亏比

        Returns:
            凯利公式计算的最优仓位比例，最大25%
        """
        p = win_rate
        q = 1 - p
        b = win_loss_ratio

        if b <= 0:
            return 0.0

        f = (p * b - q) / b
        # 限制最大仓位25%，最小0
        return max(0.0, min(f, 0.25))

    def _estimate_win_rate(self, signal: str, confidence: float) -> float:
        """根据信号和置信度估算胜率

        Args:
            signal: 交易信号
            confidence: 置信度 0-100

        Returns:
            估算胜率 0-1
        """
        base_rate = self.SIGNAL_WIN_RATE_MAP.get(signal, 0.50)
        # 置信度调整：高置信度提升胜率，低置信度降低胜率
        confidence_adjust = (confidence - 50) / 200  # 范围 -0.25 ~ +0.25
        return max(0.1, min(0.9, base_rate + confidence_adjust))

    def _estimate_win_loss_ratio(self, signal: str, confidence: float) -> float:
        """根据信号和置信度估算盈亏比

        Args:
            signal: 交易信号
            confidence: 置信度 0-100

        Returns:
            估算盈亏比
        """
        base_ratio = self.SIGNAL_WIN_LOSS_RATIO_MAP.get(signal, 1.0)
        # 置信度调整
        confidence_adjust = (confidence - 50) / 100  # 范围 -0.5 ~ +0.5
        return max(0.3, base_ratio + confidence_adjust)

    def _calc_existing_position_pct(
        self,
        stock_code: str,
        current_positions: List[Dict[str, Any]],
        portfolio_value: float,
    ) -> float:
        """计算已有持仓占比

        Args:
            stock_code: 股票代码
            current_positions: 当前持仓列表
            portfolio_value: 组合总价值

        Returns:
            已有持仓占比 0-1
        """
        if not current_positions or portfolio_value <= 0:
            return 0.0

        for pos in current_positions:
            if pos.get("stock_code") == stock_code:
                market_value = pos.get("market_value", 0)
                return market_value / portfolio_value

        return 0.0

    def _apply_risk_parity(
        self, results: List[PositionSizingResult]
    ) -> List[PositionSizingResult]:
        """应用风险平价模型调整仓位

        确保各股票的风险贡献大致相等。

        Args:
            results: 初始仓位结果列表

        Returns:
            调整后的仓位结果列表
        """
        if not results:
            return results

        try:
            # 计算各股票的风险贡献
            total_risk = sum(r.risk_contribution for r in results)
            if total_risk <= 0:
                return results

            # 目标：每只股票的风险贡献相等
            target_risk_per_stock = total_risk / len(results)

            for r in results:
                if r.risk_contribution > 0:
                    # 调整仓位使风险贡献趋近目标
                    adjust_ratio = target_risk_per_stock / r.risk_contribution
                    # 平滑调整，避免剧烈变化
                    smooth_ratio = 1.0 + (adjust_ratio - 1.0) * 0.5
                    r.recommended_pct = round(
                        max(0.0, min(r.recommended_pct * smooth_ratio, r.max_pct)), 4
                    )
                    r.risk_contribution = round(r.recommended_pct * 0.07, 4)  # 默认止损7%

            return results

        except Exception as e:
            logger.error(f"[PositionSizing] 风险平价调整失败: {e}")
            return results

    def _apply_correlation_adjustment(
        self,
        results: List[PositionSizingResult],
        signals: List[Dict[str, Any]],
    ) -> List[PositionSizingResult]:
        """应用相关性调整（简化版）

        同行业股票减仓，避免行业集中度过高。

        Args:
            results: 仓位结果列表
            signals: 信号列表（含行业信息）

        Returns:
            调整后的仓位结果列表
        """
        if not results:
            return results

        try:
            # 按行业分组
            industry_stocks: Dict[str, List[str]] = {}
            for sig in signals:
                stock_code = sig.get("stock_code", "")
                industry = sig.get("industry", "未知")
                if stock_code not in industry_stocks:
                    industry_stocks.setdefault(industry, []).append(stock_code)

            # 同行业股票减仓
            for industry, stocks in industry_stocks.items():
                if len(stocks) > 2:
                    # 同行业超过2只股票，每只减仓20%
                    for r in results:
                        if r.stock_code in stocks:
                            r.recommended_pct = round(r.recommended_pct * 0.8, 4)
                            r.reasoning += f" | 同行业({industry}){len(stocks)}只股票，减仓20%"

            return results

        except Exception as e:
            logger.error(f"[PositionSizing] 相关性调整失败: {e}")
            return results

    def _generate_reasoning(
        self,
        signal: str,
        confidence: float,
        risk_level: str,
        win_rate: float,
        win_loss_ratio: float,
        kelly_pct: float,
        half_kelly_pct: float,
        risk_adjust: float,
        risk_based_pct: float,
        recommended_pct: float,
        stop_loss_pct: float,
    ) -> str:
        """生成仓位计算理由

        Args:
            signal: 交易信号
            confidence: 置信度
            risk_level: 风险等级
            win_rate: 胜率
            win_loss_ratio: 盈亏比
            kelly_pct: 凯利公式值
            half_kelly_pct: 半凯利值
            risk_adjust: 风险调整系数
            risk_based_pct: 基于风险的仓位
            recommended_pct: 最终建议仓位
            stop_loss_pct: 止损比例

        Returns:
            仓位计算理由字符串
        """
        parts: List[str] = []

        parts.append(f"信号={signal}, 置信度={confidence:.0f}%")
        parts.append(f"胜率={win_rate:.1%}, 盈亏比={win_loss_ratio:.2f}")
        parts.append(f"凯利值={kelly_pct:.1%}, 半凯利={half_kelly_pct:.1%}")
        parts.append(f"风险等级={risk_level}, 调整系数={risk_adjust:.2f}")
        parts.append(f"风险约束仓位={risk_based_pct:.1%}, 止损={stop_loss_pct:.1%}")
        parts.append(f"最终建议仓位={recommended_pct:.1%}")

        return " | ".join(parts)
