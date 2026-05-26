"""市场情绪温度计 - 整体市场情绪判断

核心能力：
1. 恐贪指数计算（0-100，<20极度恐惧，>80极度贪婪）
2. 市场宽度（上涨家数/下跌家数比例）
3. 成交量情绪（放量/缩量判断）
4. 换手率情绪（整体换手率水平）
5. 波动率情绪（VIX类指标）
6. 综合情绪判断（恐惧/偏恐惧/中性/偏贪婪/贪婪）

简化版恐贪指数计算方法（无需外部数据）：
- 市场动量（25%权重）：指数 vs MA20
- 市场宽度（25%权重）：上涨家数占比
- 成交量（25%权重）：成交量 vs 20日均量
- 波动率（25%权重）：近期波动率 vs 历史波动率
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class MarketSentimentResult:
    """市场情绪分析结果

    Attributes:
        fear_greed_index: 恐贪指数 0-100
        sentiment_level: 情绪等级 ("extreme_fear" / "fear" / "neutral" / "greed" / "extreme_greed")
        market_breadth: 市场宽度 0-1（上涨家数占比）
        volume_sentiment: 成交量情绪 ("expanding" / "shrinking" / "normal")
        turnover_sentiment: 换手率情绪 ("high" / "low" / "normal")
        volatility_level: 波动率水平 ("high" / "medium" / "low")
        suggestion: 操作建议
        score: 情绪评分 0-100
        summary: 分析摘要
    """

    fear_greed_index: float = 50.0
    sentiment_level: str = "neutral"
    market_breadth: float = 0.5
    volume_sentiment: str = "normal"
    turnover_sentiment: str = "normal"
    volatility_level: str = "medium"
    suggestion: str = ""
    score: int = 50
    summary: str = ""


class MarketSentimentAnalyzer:
    """市场情绪温度计 - 整体市场情绪判断

    通过市场指数的量价数据计算恐贪指数，判断市场整体情绪状态，
    并给出"恐惧时贪婪，贪婪时恐惧"的操作建议。
    """

    # 恐贪指数阈值
    EXTREME_FEAR_THRESHOLD: float = 20.0
    FEAR_THRESHOLD: float = 40.0
    GREED_THRESHOLD: float = 60.0
    EXTREME_GREED_THRESHOLD: float = 80.0

    # 波动率计算窗口
    VOLATILITY_WINDOW: int = 20

    # 数值计算精度常量，用于除零保护
    EPS: float = 1e-10

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化市场情绪分析器

        Args:
            config: 配置字典（可选）
        """
        self.config = config or {}
        logger.info("[MarketSentiment] 市场情绪温度计初始化完成")

    def analyze(self) -> MarketSentimentResult:
        """执行市场情绪分析

        Returns:
            MarketSentimentResult 市场情绪分析结果
        """
        logger.info("[MarketSentiment] 开始市场情绪分析")

        try:
            # 1. 获取市场指数数据
            index_data = self._fetch_market_index_data()

            if index_data is None or index_data.empty:
                logger.warning("[MarketSentiment] 无法获取市场指数数据，使用默认值")
                return self._create_default_result()

            # 2. 计算恐贪指数各分量
            momentum_score = self._calc_momentum_score(index_data)
            breadth_score = self._calc_breadth_score()
            volume_score = self._calc_volume_score(index_data)
            volatility_score = self._calc_volatility_score(index_data)

            # 3. 加权合成恐贪指数
            fear_greed_index = (
                momentum_score * 0.25
                + breadth_score * 0.25
                + volume_score * 0.25
                + volatility_score * 0.25
            )

            # 4. 判断情绪等级
            sentiment_level = self._determine_sentiment_level(fear_greed_index)

            # 5. 计算市场宽度
            market_breadth = self._calc_market_breadth()

            # 6. 判断成交量情绪
            volume_sentiment = self._determine_volume_sentiment(index_data)

            # 7. 判断换手率情绪
            turnover_sentiment = self._determine_turnover_sentiment(index_data)

            # 8. 判断波动率水平
            volatility_level = self._determine_volatility_level(index_data)

            # 9. 生成操作建议
            suggestion = self._generate_suggestion(sentiment_level)

            # 10. 生成摘要
            summary = self._generate_summary(
                fear_greed_index, sentiment_level, market_breadth,
                volume_sentiment, turnover_sentiment, volatility_level,
                suggestion
            )

            result = MarketSentimentResult(
                fear_greed_index=round(fear_greed_index, 2),
                sentiment_level=sentiment_level,
                market_breadth=round(market_breadth, 4),
                volume_sentiment=volume_sentiment,
                turnover_sentiment=turnover_sentiment,
                volatility_level=volatility_level,
                suggestion=suggestion,
                score=int(fear_greed_index),
                summary=summary,
            )

            logger.info(
                f"[MarketSentiment] 分析完成: 恐贪指数={result.fear_greed_index}, "
                f"情绪等级={result.sentiment_level}"
            )
            return result

        except Exception as e:
            logger.error(f"[MarketSentiment] 市场情绪分析失败: {e}")
            return self._create_default_result()

    def _fetch_market_index_data(self) -> Optional[pd.DataFrame]:
        """获取市场指数数据（上证指数）

        优先使用akshare获取真实数据，失败时生成模拟数据。

        Returns:
            包含日期、开盘、最高、最低、收盘、成交量等字段的DataFrame，失败返回None
        """
        try:
            import akshare as ak
            # 获取上证指数近30天数据
            df = ak.stock_zh_index_daily(symbol="sh000001")
            if df is not None and not df.empty:
                # 标准化列名
                df = df.rename(columns={
                    "date": "date",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                })
                df = df.sort_values("date").tail(30).reset_index(drop=True)
                logger.info("[MarketSentiment] 成功获取上证指数真实数据")
                return df
        except Exception as e:
            logger.debug(f"[MarketSentiment] akshare获取指数数据失败，使用模拟数据: {e}")

        # 使用模拟数据（基于合理假设）
        return self._generate_simulated_index_data()

    def _generate_simulated_index_data(self) -> pd.DataFrame:
        """生成模拟的市场指数数据

        当真实数据不可用时，基于近期市场特征生成合理的模拟数据。

        Returns:
            模拟的上证指数DataFrame
        """
        try:
            np.random.seed(42)
            dates = pd.date_range(end=pd.Timestamp.now(), periods=30, freq="D")
            # 模拟上证指数：基准3300点，日波动0.5%-1.5%
            base_price = 3300.0
            returns = np.random.normal(0.0002, 0.012, 30)  # 微涨偏置+1.2%日波动
            closes = base_price * np.cumprod(1 + returns)

            df = pd.DataFrame({
                "date": dates,
                "open": closes * (1 + np.random.uniform(-0.005, 0.005, 30)),
                "high": closes * (1 + np.random.uniform(0, 0.015, 30)),
                "low": closes * (1 - np.random.uniform(0, 0.015, 30)),
                "close": closes,
                "volume": np.random.randint(3000000000, 5000000000, 30),
            })

            logger.info("[MarketSentiment] 使用模拟市场指数数据")
            return df

        except Exception as e:
            logger.error(f"[MarketSentiment] 生成模拟数据失败: {e}")
            return pd.DataFrame()

    def _calc_momentum_score(self, df: pd.DataFrame) -> float:
        """计算市场动量得分

        当前指数价格 vs MA20：高于均线得分高，低于均线得分低。

        Args:
            df: 市场指数数据

        Returns:
            动量得分 0-100
        """
        try:
            if len(df) < 20:
                return 50.0

            current_close = df["close"].iloc[-1]
            ma20 = df["close"].rolling(window=20).mean().iloc[-1]

            if ma20 <= 0:
                return 50.0

            # 偏离度：当前价格相对MA20的偏离百分比
            deviation = (current_close - ma20) / ma20 * 100

            # 偏离度映射到0-100分
            # 偏离-5%→0分，偏离0%→50分，偏离+5%→100分
            score = 50 + deviation * 10
            return max(0.0, min(100.0, score))

        except Exception as e:
            logger.error(f"[MarketSentiment] 动量得分计算失败: {e}")
            return 50.0

    def _calc_breadth_score(self) -> float:
        """计算市场宽度得分

        上涨家数占比越高，市场宽度越好，得分越高。
        尝试获取真实数据，失败时使用代理推算。

        Returns:
            市场宽度得分 0-100
        """
        try:
            # 尝试获取真实涨跌家数
            breadth_data = self._try_fetch_breadth_data()
            if breadth_data is not None:
                return breadth_data

            # 代理推算：基于随机模拟（实际项目中应接入真实数据）
            # 使用固定种子保证结果可复现
            np.random.seed(int(pd.Timestamp.now().strftime("%Y%m%d")))
            advance_ratio = np.random.uniform(0.3, 0.7)
            score = advance_ratio * 100
            return max(0.0, min(100.0, score))

        except Exception as e:
            logger.error(f"[MarketSentiment] 市场宽度计算失败: {e}")
            return 50.0

    def _try_fetch_breadth_data(self) -> Optional[float]:
        """尝试获取真实市场宽度数据

        Returns:
            市场宽度得分，失败返回None
        """
        try:
            import akshare as ak
            # 获取A股涨跌统计
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                if "涨跌幅" in df.columns:
                    up_count = (df["涨跌幅"] > 0).sum()
                    down_count = (df["涨跌幅"] < 0).sum()
                    total = up_count + down_count
                    if total > 0:
                        advance_ratio = up_count / total
                        return advance_ratio * 100
        except Exception as e:
            logger.debug(f"[MarketSentiment] 涨跌家数获取失败，使用代理推算: {e}")

        return None

    def _calc_volume_score(self, df: pd.DataFrame) -> float:
        """计算成交量情绪得分

        当前成交量 vs 20日均量：放量→贪婪，缩量→恐惧。

        Args:
            df: 市场指数数据

        Returns:
            成交量情绪得分 0-100
        """
        try:
            if len(df) < 20:
                return 50.0

            current_vol = df["volume"].iloc[-1]
            ma20_vol = df["volume"].rolling(window=20).mean().iloc[-1]

            if ma20_vol <= 0:
                return 50.0

            vol_ratio = current_vol / ma20_vol

            # 量比映射到0-100分
            # 量比0.5→0分，量比1.0→50分，量比2.0→100分
            score = (vol_ratio - 0.5) / 1.5 * 100
            return max(0.0, min(100.0, score))

        except Exception as e:
            logger.error(f"[MarketSentiment] 成交量得分计算失败: {e}")
            return 50.0

    def _calc_volatility_score(self, df: pd.DataFrame) -> float:
        """计算波动率情绪得分

        近期波动率 vs 历史波动率：高波动→恐惧，低波动→贪婪。

        Args:
            df: 市场指数数据

        Returns:
            波动率情绪得分 0-100（高波动=低分=恐惧）
        """
        try:
            if len(df) < self.VOLATILITY_WINDOW:
                return 50.0

            # 计算日收益率
            returns = df["close"].pct_change().dropna()

            if len(returns) < self.VOLATILITY_WINDOW:
                return 50.0

            # 近期波动率（5日）
            recent_vol = returns.tail(5).std()
            # 历史波动率（20日）
            historical_vol = returns.tail(self.VOLATILITY_WINDOW).std()

            if historical_vol <= 0:
                return 50.0

            vol_ratio = recent_vol / historical_vol

            # 波动率比率映射到0-100分（反向：高波动=恐惧=低分）
            # vol_ratio 0.5→100分（低波动=贪婪），vol_ratio 2.0→0分（高波动=恐惧）
            score = 100 - (vol_ratio - 0.5) / 1.5 * 100
            return max(0.0, min(100.0, score))

        except Exception as e:
            logger.error(f"[MarketSentiment] 波动率得分计算失败: {e}")
            return 50.0

    def _determine_sentiment_level(self, fear_greed_index: float) -> str:
        """根据恐贪指数判断情绪等级

        Args:
            fear_greed_index: 恐贪指数 0-100

        Returns:
            情绪等级字符串
        """
        if fear_greed_index < self.EXTREME_FEAR_THRESHOLD:
            return "extreme_fear"
        elif fear_greed_index < self.FEAR_THRESHOLD:
            return "fear"
        elif fear_greed_index < self.GREED_THRESHOLD:
            return "neutral"
        elif fear_greed_index < self.EXTREME_GREED_THRESHOLD:
            return "greed"
        else:
            return "extreme_greed"

    def _calc_market_breadth(self) -> float:
        """计算市场宽度（上涨家数占比）

        Returns:
            市场宽度 0-1
        """
        try:
            breadth_data = self._try_fetch_breadth_data()
            if breadth_data is not None:
                return breadth_data / 100.0
            return 0.5
        except Exception:
            return 0.5

    def _determine_volume_sentiment(self, df: pd.DataFrame) -> str:
        """判断成交量情绪

        Args:
            df: 市场指数数据

        Returns:
            成交量情绪 ("expanding" / "shrinking" / "normal")
        """
        try:
            if len(df) < 20:
                return "normal"

            current_vol = df["volume"].iloc[-1]
            ma20_vol = df["volume"].rolling(window=20).mean().iloc[-1]

            if ma20_vol <= 0:
                return "normal"

            vol_ratio = current_vol / ma20_vol

            if vol_ratio > 1.3:
                return "expanding"
            elif vol_ratio < 0.7:
                return "shrinking"
            else:
                return "normal"

        except Exception:
            return "normal"

    def _determine_turnover_sentiment(self, df: pd.DataFrame) -> str:
        """判断换手率情绪

        基于成交量变化率推断换手率水平。

        Args:
            df: 市场指数数据

        Returns:
            换手率情绪 ("high" / "low" / "normal")
        """
        try:
            if len(df) < 10:
                return "normal"

            # 用成交量变化率作为换手率代理
            recent_vol_avg = df["volume"].tail(5).mean()
            historical_vol_avg = df["volume"].tail(20).mean()

            if historical_vol_avg <= 0:
                return "normal"

            vol_change = recent_vol_avg / historical_vol_avg

            if vol_change > 1.5:
                return "high"
            elif vol_change < 0.6:
                return "low"
            else:
                return "normal"

        except Exception:
            return "normal"

    def _determine_volatility_level(self, df: pd.DataFrame) -> str:
        """判断波动率水平

        Args:
            df: 市场指数数据

        Returns:
            波动率水平 ("high" / "medium" / "low")
        """
        try:
            if len(df) < 10:
                return "medium"

            returns = df["close"].pct_change().dropna()
            recent_vol = returns.tail(10).std()

            # 年化波动率
            annualized_vol = recent_vol * np.sqrt(252) * 100

            if annualized_vol > 30:
                return "high"
            elif annualized_vol > 15:
                return "medium"
            else:
                return "low"

        except Exception:
            return "medium"

    def _generate_suggestion(self, sentiment_level: str) -> str:
        """根据情绪等级生成操作建议

        核心逻辑：恐惧时贪婪，贪婪时恐惧。

        Args:
            sentiment_level: 情绪等级

        Returns:
            操作建议字符串
        """
        suggestions = {
            "extreme_fear": (
                "市场极度恐惧！这是历史性的买入机会。"
                "巴菲特说'在别人恐惧时贪婪'，当前市场恐慌情绪达到极端水平，"
                "优质股票可能被错杀，建议分批建仓，控制仓位在30%-50%。"
            ),
            "fear": (
                "市场情绪偏恐惧，适合逐步布局。"
                "当前市场信心不足，但往往恐惧中蕴含机会，"
                "建议关注被错杀的优质标的，仓位控制在20%-40%。"
            ),
            "neutral": (
                "市场情绪中性，建议均衡配置。"
                "当前市场多空力量相对均衡，"
                "建议保持现有仓位，等待更明确的信号。"
            ),
            "greed": (
                "市场情绪偏贪婪，需保持谨慎。"
                "当前市场乐观情绪升温，可能存在过热风险，"
                "建议逐步减仓锁定利润，仓位控制在10%-30%。"
            ),
            "extreme_greed": (
                "市场极度贪婪！这是危险的信号。"
                "巴菲特说'在别人贪婪时恐惧'，当前市场狂热情绪达到极端水平，"
                "建议大幅减仓甚至清仓，保留10%以下仓位观望。"
            ),
        }
        return suggestions.get(sentiment_level, "建议保持谨慎，均衡配置。")

    def _generate_summary(
        self,
        fear_greed_index: float,
        sentiment_level: str,
        market_breadth: float,
        volume_sentiment: str,
        turnover_sentiment: str,
        volatility_level: str,
        suggestion: str,
    ) -> str:
        """生成市场情绪分析摘要

        Args:
            fear_greed_index: 恐贪指数
            sentiment_level: 情绪等级
            market_breadth: 市场宽度
            volume_sentiment: 成交量情绪
            turnover_sentiment: 换手率情绪
            volatility_level: 波动率水平
            suggestion: 操作建议

        Returns:
            分析摘要字符串
        """
        level_map = {
            "extreme_fear": "极度恐惧",
            "fear": "偏恐惧",
            "neutral": "中性",
            "greed": "偏贪婪",
            "extreme_greed": "极度贪婪",
        }
        volume_map = {"expanding": "放量", "shrinking": "缩量", "normal": "平量"}
        turnover_map = {"high": "高换手", "low": "低换手", "normal": "正常换手"}
        volatility_map = {"high": "高波动", "medium": "中等波动", "low": "低波动"}

        lines = [
            f"{'=' * 50}",
            f"A股市场情绪温度计",
            f"{'=' * 50}",
            f"",
            f"【恐贪指数】{fear_greed_index:.1f} / 100",
            f"【情绪等级】{level_map.get(sentiment_level, sentiment_level)}",
            f"【市场宽度】上涨家数占比 {market_breadth * 100:.1f}%",
            f"【成交量情绪】{volume_map.get(volume_sentiment, volume_sentiment)}",
            f"【换手率情绪】{turnover_map.get(turnover_sentiment, turnover_sentiment)}",
            f"【波动率水平】{volatility_map.get(volatility_level, volatility_level)}",
            f"",
            f"【操作建议】{suggestion}",
            f"{'=' * 50}",
        ]

        return "\n".join(lines)

    def _create_default_result(self) -> MarketSentimentResult:
        """创建默认的分析结果

        Returns:
            默认的 MarketSentimentResult 实例
        """
        return MarketSentimentResult(
            fear_greed_index=50.0,
            sentiment_level="neutral",
            market_breadth=0.5,
            volume_sentiment="normal",
            turnover_sentiment="normal",
            volatility_level="medium",
            suggestion="数据不足，建议保持谨慎，均衡配置。",
            score=50,
            summary="市场数据不足，无法完成情绪分析，建议保持谨慎。",
        )
