"""资金流向分析师智能体 - 追踪主力资金、北向资金、融资融券

核心能力：
1. 主力资金流向分析（大单净流入/流出、主力持仓变化）
2. 北向资金分析（沪股通/深股通净买入、连续买入天数）
3. 融资融券分析（融资余额变化、融券余额变化）
4. 资金共振判断（多路资金同向流入=强信号）
5. 资金背离预警（价格涨但资金流出=危险信号）

当实际数据源不可用时，采用基于量价数据的资金流向推算方法。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

from astock_agents.agents.base_agent import BaseAgent
from astock_agents.models import StockData


@dataclass
class CapitalFlowResult:
    """资金流向分析结果

    Attributes:
        main_force_net_inflow: 主力净流入（万元）
        main_force_direction: 主力资金方向 ("inflow" / "outflow" / "neutral")
        north_bound_net_buy: 北向净买入（万元）
        north_bound_days: 连续净买入天数
        margin_balance_change: 融资余额变化率
        capital_resonance: 资金共振度 0-1（多路资金同向比例）
        price_capital_divergence: 是否存在量价背离
        signal: 资金面信号 ("strong_buy" / "buy" / "hold" / "sell" / "strong_sell")
        score: 资金面评分 0-100
        summary: 自然语言摘要
        key_points: 关键要点列表
    """

    main_force_net_inflow: float = 0.0
    main_force_direction: str = "neutral"
    north_bound_net_buy: float = 0.0
    north_bound_days: int = 0
    margin_balance_change: float = 0.0
    capital_resonance: float = 0.0
    price_capital_divergence: bool = False
    signal: str = "hold"
    score: int = 50
    summary: str = ""
    key_points: List[str] = field(default_factory=list)


class CapitalFlowAnalyst(BaseAgent):
    """资金流向分析师 - 追踪主力资金、北向资金、融资融券

    通过量价数据推算资金流向，判断主力资金方向、北向资金动向、
    融资融券变化，并检测资金共振和量价背离信号。
    """

    # 散户比例与换手率的映射阈值
    TURNOVER_HIGH_THRESHOLD: float = 8.0  # 高换手率阈值（%）
    TURNOVER_LOW_THRESHOLD: float = 2.0   # 低换手率阈值（%）

    # 连续净流入/流出判定天数
    CONSECUTIVE_DAYS: int = 3

    # 数值计算精度常量，用于除零保护
    EPS: float = 1e-10

    def __init__(self, llm: Optional[Any] = None, config: Optional[Dict[str, Any]] = None):
        """初始化资金流向分析师

        Args:
            llm: 语言模型实例（可选）
            config: 配置字典
        """
        super().__init__(
            name="资金流向分析师",
            role="追踪主力资金、北向资金、融资融券，判断资金面信号",
            llm=llm,
            config=config
        )

    def analyze(self, stock_data: StockData, **kwargs) -> Dict[str, Any]:
        """执行资金流向分析

        Args:
            stock_data: 股票数据
            **kwargs: 额外参数

        Returns:
            包含 CapitalFlowResult 字典的分析结果
        """
        logger.info(f"[{self.name}] 开始资金流向分析: {stock_data.stock_code}")

        if not stock_data.prices or len(stock_data.prices) < 5:
            logger.warning(f"[{self.name}] 价格数据不足，无法进行资金流向分析")
            result = self._create_empty_result(stock_data)
            self.log_analysis({"score": result.score, "signal": result.signal})
            return self._result_to_dict(result)

        try:
            # 1. 准备数据
            df = self._prepare_data(stock_data)

            # 2. 计算主力资金净流入（基于量价推算）
            main_force_net_inflow, main_force_direction = self._calc_main_force_flow(df)

            # 3. 推算北向资金动向
            north_bound_net_buy, north_bound_days = self._calc_north_bound_flow(df)

            # 4. 推算融资融券变化
            margin_balance_change = self._calc_margin_change(df)

            # 5. 检测资金背离
            price_capital_divergence = self._detect_price_capital_divergence(df)

            # 6. 计算资金共振度
            capital_resonance = self._calc_capital_resonance(
                main_force_direction, north_bound_net_buy, margin_balance_change
            )

            # 7. 生成信号和评分
            signal, score = self._generate_signal(
                main_force_net_inflow, main_force_direction,
                north_bound_net_buy, north_bound_days,
                margin_balance_change, capital_resonance,
                price_capital_divergence
            )

            # 8. 生成摘要和关键要点
            summary = self._generate_summary(
                stock_data, main_force_net_inflow, main_force_direction,
                north_bound_net_buy, north_bound_days,
                margin_balance_change, capital_resonance,
                price_capital_divergence, signal, score
            )

            key_points = self._generate_key_points(
                main_force_direction, north_bound_net_buy, north_bound_days,
                margin_balance_change, capital_resonance,
                price_capital_divergence
            )

            result = CapitalFlowResult(
                main_force_net_inflow=round(main_force_net_inflow, 2),
                main_force_direction=main_force_direction,
                north_bound_net_buy=round(north_bound_net_buy, 2),
                north_bound_days=north_bound_days,
                margin_balance_change=round(margin_balance_change, 4),
                capital_resonance=round(capital_resonance, 4),
                price_capital_divergence=price_capital_divergence,
                signal=signal,
                score=score,
                summary=summary,
                key_points=key_points,
            )

            self.log_analysis({"score": result.score, "signal": result.signal})
            return self._result_to_dict(result)

        except Exception as e:
            logger.error(f"[{self.name}] 资金流向分析失败: {e}")
            result = self._create_empty_result(stock_data)
            return self._result_to_dict(result)

    def _prepare_data(self, stock_data: StockData) -> pd.DataFrame:
        """准备分析数据，构建DataFrame

        Args:
            stock_data: 股票数据

        Returns:
            包含价格、成交量、成交额、换手率等字段的DataFrame
        """
        data = []
        for price in stock_data.prices:
            row = {
                "date": price.date,
                "open": price.open,
                "high": price.high,
                "low": price.low,
                "close": price.close,
                "volume": price.volume,
                "amount": price.amount if price.amount else price.close * price.volume,
            }
            data.append(row)

        df = pd.DataFrame(data)
        df = df.sort_values("date").reset_index(drop=True)

        # 计算换手率代理（成交额 / 总市值，若无市值则用成交额标准化）
        if stock_data.market_cap and stock_data.market_cap > 0:
            df["turnover_rate"] = df["amount"] / (stock_data.market_cap * 10000) * 100
        else:
            # 无市值数据时，用成交量均值标准化作为代理
            avg_vol = df["volume"].rolling(window=20, min_periods=1).mean()
            df["turnover_rate"] = df["volume"] / (avg_vol + self.EPS) * 3.0  # 近似换手率

        # 计算成交额均线
        df["amount_ma5"] = df["amount"].rolling(window=5, min_periods=1).mean()
        df["amount_ma20"] = df["amount"].rolling(window=20, min_periods=1).mean()

        # 计算价格变化率
        df["pct_change"] = df["close"].pct_change().fillna(0)

        return df

    def _calc_main_force_flow(self, df: pd.DataFrame) -> tuple[float, str]:
        """基于量价数据推算主力资金流向

        推算逻辑：
        - 主力资金 ≈ 大单成交额 = 成交额 × (1 - 散户比例)
        - 散户比例通过换手率推算：高换手率→散户参与度高
        - 连续3日净流入判定为流入方向

        Args:
            df: 包含价格和成交量数据的DataFrame

        Returns:
            (主力净流入万元, 方向字符串) 元组
        """
        try:
            # 推算散户比例：换手率越高，散户参与度越高
            recent_turnover = df["turnover_rate"].tail(self.CONSECUTIVE_DAYS).mean()

            if recent_turnover > self.TURNOVER_HIGH_THRESHOLD:
                retail_ratio = 0.65  # 高换手率，散户占比高
            elif recent_turnover < self.TURNOVER_LOW_THRESHOLD:
                retail_ratio = 0.35  # 低换手率，散户占比低（主力主导）
            else:
                # 线性插值
                retail_ratio = 0.35 + (recent_turnover - self.TURNOVER_LOW_THRESHOLD) / (
                    self.TURNOVER_HIGH_THRESHOLD - self.TURNOVER_LOW_THRESHOLD + self.EPS
                ) * 0.30

            # 计算每日主力净流入
            # 主力净流入 = 成交额 × (1 - 散户比例) × 价格方向因子
            df["main_force_flow"] = df["amount"] * (1 - retail_ratio) * np.sign(df["pct_change"])

            # 近N日主力净流入
            recent_flow = df["main_force_flow"].tail(self.CONSECUTIVE_DAYS).sum()
            # 转换为万元
            main_force_net_inflow = recent_flow / 10000

            # 判断方向：连续3日净流入/流出
            recent_daily_flows = df["main_force_flow"].tail(self.CONSECUTIVE_DAYS).values
            positive_days = sum(1 for f in recent_daily_flows if f > 0)
            negative_days = sum(1 for f in recent_daily_flows if f < 0)

            if positive_days >= self.CONSECUTIVE_DAYS:
                direction = "inflow"
            elif negative_days >= self.CONSECUTIVE_DAYS:
                direction = "outflow"
            else:
                direction = "neutral"

            return main_force_net_inflow, direction

        except Exception as e:
            logger.error(f"[{self.name}] 主力资金计算失败: {e}")
            return 0.0, "neutral"

    def _calc_north_bound_flow(self, df: pd.DataFrame) -> tuple[float, int]:
        """推算北向资金动向

        代理指标逻辑：
        - 尝试通过akshare获取真实北向资金数据
        - 若不可用，用"连续放量+价格上涨"作为北向资金流入的代理指标
        - 北向资金通常表现为：温和放量、持续买入、不追高

        Args:
            df: 包含价格和成交量数据的DataFrame

        Returns:
            (北向净买入万元, 连续净买入天数) 元组
        """
        try:
            # 尝试获取真实北向资金数据
            north_bound_data = self._try_fetch_north_bound_data()
            if north_bound_data is not None:
                return north_bound_data

            # 代理推算：连续放量+价格上涨 → 北向资金流入
            df["vol_ratio"] = df["volume"] / df["volume"].rolling(window=20, min_periods=1).mean()

            # 北向资金流入信号：量比>1.1 且 价格上涨
            df["north_signal"] = ((df["vol_ratio"] > 1.1) & (df["pct_change"] > 0)).astype(int)
            # 北向资金流出信号：量比>1.1 且 价格下跌
            df["north_signal_out"] = ((df["vol_ratio"] > 1.1) & (df["pct_change"] < 0)).astype(int)

            # 计算连续净买入天数
            consecutive_buy_days = 0
            for i in range(len(df) - 1, -1, -1):
                if df["north_signal"].iloc[i] == 1:
                    consecutive_buy_days += 1
                else:
                    break

            # 推算净买入金额：基于放量部分的成交额
            recent_amount = df["amount"].tail(5).mean()
            # 北向资金通常占放量部分的20%-30%
            north_bound_net_buy = recent_amount * 0.25 * consecutive_buy_days / 10000

            return north_bound_net_buy, consecutive_buy_days

        except Exception as e:
            logger.error(f"[{self.name}] 北向资金推算失败: {e}")
            return 0.0, 0

    def _try_fetch_north_bound_data(self) -> Optional[tuple[float, int]]:
        """尝试获取真实北向资金数据

        Returns:
            若成功获取则返回 (净买入万元, 连续买入天数)，否则返回 None
        """
        try:
            import akshare as ak
            # 获取北向资金数据
            df_north = ak.stock_em_hsgt_north_net_flow_in_em(symbol="北向")
            if df_north is not None and not df_north.empty:
                recent = df_north.tail(5)
                net_buy = recent.iloc[-1]["当日净流入"] if "当日净流入" in recent.columns else 0
                # 计算连续净买入天数
                consecutive_days = 0
                for i in range(len(recent) - 1, -1, -1):
                    val = recent.iloc[i].get("当日净流入", 0)
                    if val > 0:
                        consecutive_days += 1
                    else:
                        break
                return float(net_buy), consecutive_days
        except Exception as e:
            logger.debug(f"[{self.name}] 北向资金真实数据获取失败，使用代理推算: {e}")

        return None

    def _calc_margin_change(self, df: pd.DataFrame) -> float:
        """推算融资融券余额变化率

        代理指标逻辑：
        - 融资余额与成交量正相关：融资买入增加→成交量放大
        - 用成交量变化率作为融资余额变化的代理

        Args:
            df: 包含价格和成交量数据的DataFrame

        Returns:
            融资余额变化率（如0.05表示增长5%）
        """
        try:
            if len(df) < 10:
                return 0.0

            # 近5日成交量均值 vs 近20日成交量均值
            vol_ma5 = df["volume"].tail(5).mean()
            vol_ma20 = df["volume"].tail(20).mean()

            if vol_ma20 > 0:
                margin_change = (vol_ma5 - vol_ma20) / vol_ma20
            else:
                margin_change = 0.0

            # 限制在合理范围 [-0.5, 0.5]
            return max(-0.5, min(0.5, margin_change))

        except Exception as e:
            logger.error(f"[{self.name}] 融资融券推算失败: {e}")
            return 0.0

    def _detect_price_capital_divergence(self, df: pd.DataFrame) -> bool:
        """检测价格与资金的背离

        背离类型：
        - 顶背离：价格上涨 + 资金流出（OBV下降）
        - 底背离：价格下跌 + 资金流入（OBV上升）

        Args:
            df: 包含价格和成交量数据的DataFrame

        Returns:
            是否存在量价背离
        """
        try:
            if len(df) < 20:
                return False

            # 计算OBV
            obv = [0.0]
            for i in range(1, len(df)):
                if df["close"].iloc[i] > df["close"].iloc[i - 1]:
                    obv.append(obv[-1] + df["volume"].iloc[i])
                elif df["close"].iloc[i] < df["close"].iloc[i - 1]:
                    obv.append(obv[-1] - df["volume"].iloc[i])
                else:
                    obv.append(obv[-1])

            # 近期价格趋势
            price_trend_up = df["close"].iloc[-1] > df["close"].iloc[-10]
            # 近期OBV趋势
            obv_trend_up = obv[-1] > obv[-10]

            # 顶背离：价格涨但OBV跌
            # 底背离：价格跌但OBV涨
            divergence = (price_trend_up and not obv_trend_up) or (
                not price_trend_up and obv_trend_up
            )

            return divergence

        except Exception as e:
            logger.error(f"[{self.name}] 背离检测失败: {e}")
            return False

    def _calc_capital_resonance(
        self,
        main_force_direction: str,
        north_bound_net_buy: float,
        margin_balance_change: float,
    ) -> float:
        """计算资金共振度

        多路资金同向流入/流出时，共振度高，信号更强。
        共振度 = 同向资金路数 / 总资金路数

        Args:
            main_force_direction: 主力资金方向
            north_bound_net_buy: 北向净买入金额
            margin_balance_change: 融资余额变化率

        Returns:
            资金共振度 0-1
        """
        try:
            directions = []

            # 主力资金方向
            if main_force_direction == "inflow":
                directions.append(1)
            elif main_force_direction == "outflow":
                directions.append(-1)
            else:
                directions.append(0)

            # 北向资金方向
            if north_bound_net_buy > 0:
                directions.append(1)
            elif north_bound_net_buy < 0:
                directions.append(-1)
            else:
                directions.append(0)

            # 融资融券方向
            if margin_balance_change > 0.02:
                directions.append(1)
            elif margin_balance_change < -0.02:
                directions.append(-1)
            else:
                directions.append(0)

            # 计算共振度
            non_zero = [d for d in directions if d != 0]
            if not non_zero:
                return 0.0

            # 同向比例
            positive_count = sum(1 for d in non_zero if d > 0)
            negative_count = sum(1 for d in non_zero if d < 0)
            same_direction_count = max(positive_count, negative_count)

            resonance = same_direction_count / len(non_zero)
            return resonance

        except Exception as e:
            logger.error(f"[{self.name}] 共振度计算失败: {e}")
            return 0.0

    def _generate_signal(
        self,
        main_force_net_inflow: float,
        main_force_direction: str,
        north_bound_net_buy: float,
        north_bound_days: int,
        margin_balance_change: float,
        capital_resonance: float,
        price_capital_divergence: bool,
    ) -> tuple[str, int]:
        """生成资金面信号和评分

        Args:
            main_force_net_inflow: 主力净流入（万元）
            main_force_direction: 主力资金方向
            north_bound_net_buy: 北向净买入（万元）
            north_bound_days: 连续净买入天数
            margin_balance_change: 融资余额变化率
            capital_resonance: 资金共振度
            price_capital_divergence: 是否存在量价背离

        Returns:
            (信号字符串, 评分0-100) 元组
        """
        score = 50  # 中性基准

        # 1. 主力资金方向评分（权重35%）
        if main_force_direction == "inflow":
            score += 18
        elif main_force_direction == "outflow":
            score -= 18

        # 2. 北向资金评分（权重25%）
        if north_bound_net_buy > 0 and north_bound_days >= 3:
            score += 12
        elif north_bound_net_buy > 0:
            score += 6
        elif north_bound_net_buy < 0:
            score -= 8

        # 3. 融资融券评分（权重15%）
        if margin_balance_change > 0.05:
            score += 8
        elif margin_balance_change > 0:
            score += 4
        elif margin_balance_change < -0.05:
            score -= 8
        elif margin_balance_change < 0:
            score -= 4

        # 4. 资金共振度评分（权重15%）
        if capital_resonance >= 0.8:
            score += 8
        elif capital_resonance >= 0.6:
            score += 4
        elif capital_resonance < 0.3:
            score -= 4

        # 5. 背离预警（权重10%）
        if price_capital_divergence:
            score -= 10

        # 限制评分范围
        score = max(0, min(100, int(score)))

        # 生成信号
        if score >= 75:
            signal = "strong_buy"
        elif score >= 60:
            signal = "buy"
        elif score <= 25:
            signal = "strong_sell"
        elif score <= 40:
            signal = "sell"
        else:
            signal = "hold"

        return signal, score

    def _generate_summary(
        self,
        stock_data: StockData,
        main_force_net_inflow: float,
        main_force_direction: str,
        north_bound_net_buy: float,
        north_bound_days: int,
        margin_balance_change: float,
        capital_resonance: float,
        price_capital_divergence: bool,
        signal: str,
        score: int,
    ) -> str:
        """生成资金流向分析摘要

        Args:
            stock_data: 股票数据
            main_force_net_inflow: 主力净流入
            main_force_direction: 主力资金方向
            north_bound_net_buy: 北向净买入
            north_bound_days: 连续净买入天数
            margin_balance_change: 融资余额变化率
            capital_resonance: 资金共振度
            price_capital_divergence: 是否存在量价背离
            signal: 信号
            score: 评分

        Returns:
            分析摘要字符串
        """
        direction_map = {"inflow": "流入", "outflow": "流出", "neutral": "均衡"}
        signal_map = {
            "strong_buy": "强烈买入",
            "buy": "买入",
            "hold": "持有",
            "sell": "卖出",
            "strong_sell": "强烈卖出",
        }

        lines = [
            f"{'=' * 50}",
            f"{stock_data.stock_name}({stock_data.stock_code}) 资金流向分析报告",
            f"{'=' * 50}",
            f"",
            f"【主力资金】净流入 {main_force_net_inflow:.0f} 万元，方向：{direction_map.get(main_force_direction, '未知')}",
            f"【北向资金】净买入 {north_bound_net_buy:.0f} 万元，连续买入 {north_bound_days} 天",
            f"【融资融券】余额变化率 {margin_balance_change * 100:.2f}%",
            f"【资金共振度】{capital_resonance * 100:.1f}%",
            f"【量价背离】{'存在' if price_capital_divergence else '无'}",
            f"",
            f"【资金面信号】{signal_map.get(signal, signal)}（评分: {score}）",
            f"{'=' * 50}",
        ]

        return "\n".join(lines)

    def _generate_key_points(
        self,
        main_force_direction: str,
        north_bound_net_buy: float,
        north_bound_days: int,
        margin_balance_change: float,
        capital_resonance: float,
        price_capital_divergence: bool,
    ) -> List[str]:
        """生成关键要点

        Args:
            main_force_direction: 主力资金方向
            north_bound_net_buy: 北向净买入
            north_bound_days: 连续净买入天数
            margin_balance_change: 融资余额变化率
            capital_resonance: 资金共振度
            price_capital_divergence: 是否存在量价背离

        Returns:
            关键要点列表
        """
        points: List[str] = []

        if main_force_direction == "inflow":
            points.append("主力资金连续净流入，资金面偏多")
        elif main_force_direction == "outflow":
            points.append("主力资金连续净流出，资金面偏空")

        if north_bound_net_buy > 0 and north_bound_days >= 3:
            points.append(f"北向资金连续{north_bound_days}天净买入，外资看好")
        elif north_bound_net_buy < 0:
            points.append("北向资金净卖出，外资偏谨慎")

        if margin_balance_change > 0.05:
            points.append("融资余额明显增加，杠杆资金积极")
        elif margin_balance_change < -0.05:
            points.append("融资余额明显减少，杠杆资金撤退")

        if capital_resonance >= 0.8:
            points.append("多路资金同向流入，共振信号强烈")
        elif capital_resonance < 0.3:
            points.append("资金方向分歧较大，信号不明确")

        if price_capital_divergence:
            points.append("⚠️ 量价背离预警：价格与资金流向不一致，需警惕")

        if not points:
            points.append("资金面整体均衡，无明显方向性信号")

        return points

    def _create_empty_result(self, stock_data: StockData) -> CapitalFlowResult:
        """创建空的分析结果

        Args:
            stock_data: 股票数据

        Returns:
            默认的 CapitalFlowResult 实例
        """
        return CapitalFlowResult(
            main_force_net_inflow=0.0,
            main_force_direction="neutral",
            north_bound_net_buy=0.0,
            north_bound_days=0,
            margin_balance_change=0.0,
            capital_resonance=0.0,
            price_capital_divergence=False,
            signal="hold",
            score=50,
            summary=f"{stock_data.stock_name}({stock_data.stock_code}) 数据不足，无法完成资金流向分析",
            key_points=["数据不足，无法进行资金流向分析"],
        )

    def _result_to_dict(self, result: CapitalFlowResult) -> Dict[str, Any]:
        """将 CapitalFlowResult 转换为字典

        Args:
            result: 资金流向分析结果

        Returns:
            结果字典
        """
        from dataclasses import asdict
        return asdict(result)
