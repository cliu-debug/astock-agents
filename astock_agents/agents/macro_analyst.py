"""宏观分析师智能体 - 经济周期定位、政策解读、宏观风险评估"""

from typing import Dict, Any, Optional
from loguru import logger

from astock_agents.agents.base_agent import BaseAgent
from astock_agents.models import StockData, Signal


class MacroAnalyst(BaseAgent):
    """宏观分析师 - 从宏观经济角度评估市场环境"""

    # 美林时钟行业配置建议
    MERRILL_CLOCK_CONFIG: Dict[str, Dict[str, Any]] = {
        "复苏": {
            "description": "经济上行+通胀下行",
            "favorable_sectors": ["科技", "消费", "金融"],
            "unfavorable_sectors": ["公用事业", "债券"],
            "signal": Signal.BUY,
        },
        "过热": {
            "description": "经济上行+通胀上行",
            "favorable_sectors": ["大宗商品", "能源", "原材料"],
            "unfavorable_sectors": ["科技", "消费"],
            "signal": Signal.HOLD,
        },
        "滞胀": {
            "description": "经济下行+通胀上行",
            "favorable_sectors": ["医药", "公用事业", "黄金"],
            "unfavorable_sectors": ["科技", "金融", "消费"],
            "signal": Signal.SELL,
        },
        "衰退": {
            "description": "经济下行+通胀下行",
            "favorable_sectors": ["债券", "公用事业", "高股息"],
            "unfavorable_sectors": ["周期股", "大宗商品"],
            "signal": Signal.STRONG_SELL,
        },
    }

    def __init__(self, llm: Optional[Any] = None, config: Optional[Dict[str, Any]] = None):
        """初始化宏观分析师

        Args:
            llm: 语言模型实例（可选）
            config: 配置字典
        """
        super().__init__(
            name="宏观分析师",
            role="从宏观经济周期、货币政策、财政政策角度评估市场环境",
            llm=llm,
            config=config
        )

    def analyze(self, stock_data: StockData, **kwargs) -> Dict[str, Any]:
        """执行宏观分析

        Args:
            stock_data: 股票数据
            **kwargs: 额外参数

        Returns:
            包含经济周期、行业适配度、政策环境、市场估值、信号等信息的字典
        """
        logger.info(f"[{self.name}] 开始宏观分析: {stock_data.stock_code}")

        # 1. 经济周期定位
        cycle = self._identify_economic_cycle(stock_data)

        # 2. 行业适配度
        industry_fit = self._assess_industry_fit(stock_data, cycle)

        # 3. 政策环境评估
        policy_env = self._assess_policy_environment(stock_data)

        # 4. 市场整体估值水平
        market_valuation = self._assess_market_valuation(stock_data)

        # 5. 生成信号
        signal, confidence = self._generate_signal(
            cycle, industry_fit, policy_env, market_valuation
        )

        result = {
            "economic_cycle": cycle,
            "industry_fit": industry_fit,
            "policy_environment": policy_env,
            "market_valuation": market_valuation,
            "signal": signal,
            "confidence": confidence,
            "summary": self._generate_summary(stock_data, cycle, industry_fit, signal),
        }

        self.log_analysis(result)
        return result

    def _identify_economic_cycle(self, stock_data: StockData) -> Dict[str, Any]:
        """识别经济周期（基于可获取的数据推断）

        简化版：基于行业表现和市场数据推断。
        实际生产环境应接入GDP/CPI/PMI等宏观数据。

        Args:
            stock_data: 股票数据

        Returns:
            包含当前经济周期阶段、描述、有利/不利行业的字典
        """
        industry = stock_data.industry or ""

        # 默认假设为"温和复苏"
        cycle_name = "复苏"

        # 基于行业特征推断（简化）
        cyclical_industries = ["钢铁", "煤炭", "有色金属", "化工"]
        defensive_industries = ["医药", "公用事业", "食品饮料"]

        if industry in cyclical_industries:
            cycle_name = "过热"  # 周期股活跃通常在经济过热期
        elif industry in defensive_industries:
            cycle_name = "衰退"  # 防御股活跃通常在衰退期

        config = self.MERRILL_CLOCK_CONFIG.get(
            cycle_name, self.MERRILL_CLOCK_CONFIG["复苏"]
        )

        return {
            "current_phase": cycle_name,
            "description": config["description"],
            "favorable_sectors": config["favorable_sectors"],
            "unfavorable_sectors": config["unfavorable_sectors"],
        }

    def _assess_industry_fit(
        self, stock_data: StockData, cycle: Dict[str, Any]
    ) -> Dict[str, Any]:
        """评估行业与经济周期的适配度

        Args:
            stock_data: 股票数据
            cycle: 经济周期信息字典

        Returns:
            包含行业名称、适配等级、评分、有利行业的字典
        """
        industry = stock_data.industry or ""
        favorable = cycle.get("favorable_sectors", [])
        unfavorable = cycle.get("unfavorable_sectors", [])

        is_favorable = any(s in industry or industry in s for s in favorable)
        is_unfavorable = any(s in industry or industry in s for s in unfavorable)

        if is_favorable:
            fit_level = "有利"
            score = 75
        elif is_unfavorable:
            fit_level = "不利"
            score = 30
        else:
            fit_level = "中性"
            score = 50

        return {
            "industry": industry,
            "fit_level": fit_level,
            "score": score,
            "favorable_sectors": favorable,
        }

    def _assess_policy_environment(self, stock_data: StockData) -> Dict[str, Any]:
        """评估政策环境

        Args:
            stock_data: 股票数据

        Returns:
            包含政策立场和评分的字典
        """
        industry = stock_data.industry or ""

        # 政策支持行业
        supported = ["新能源", "半导体", "人工智能", "科技", "高端制造", "数字经济"]
        regulated = ["房地产", "教育", "互联网", "游戏"]

        is_supported = any(s in industry for s in supported)
        is_regulated = any(s in industry for s in regulated)

        if is_supported:
            policy_stance = "政策支持"
            score = 75
        elif is_regulated:
            policy_stance = "政策收紧"
            score = 30
        else:
            policy_stance = "政策中性"
            score = 50

        return {
            "policy_stance": policy_stance,
            "score": score,
        }

    def _assess_market_valuation(self, stock_data: StockData) -> Dict[str, Any]:
        """评估市场整体估值水平

        Args:
            stock_data: 股票数据

        Returns:
            包含估值水平、PE值和评分的字典
        """
        pe = stock_data.pe_ttm

        if pe is None:
            return {"level": "数据不足", "score": 50}

        if pe < 15:
            level, score = "低估", 80
        elif pe < 25:
            level, score = "合理", 55
        elif pe < 40:
            level, score = "偏高", 35
        else:
            level, score = "高估", 20

        return {"level": level, "pe": pe, "score": score}

    def _generate_signal(
        self,
        cycle: Dict[str, Any],
        industry_fit: Dict[str, Any],
        policy_env: Dict[str, Any],
        market_valuation: Dict[str, Any],
    ) -> tuple:
        """生成宏观信号

        Args:
            cycle: 经济周期信息
            industry_fit: 行业适配度信息
            policy_env: 政策环境信息
            market_valuation: 市场估值信息

        Returns:
            (Signal, confidence) 元组
        """
        cycle_score_map = {"复苏": 70, "过热": 50, "滞胀": 30, "衰退": 20}

        scores = [
            industry_fit.get("score", 50) * 0.35,
            policy_env.get("score", 50) * 0.25,
            market_valuation.get("score", 50) * 0.25,
            cycle_score_map.get(cycle.get("current_phase"), 50) * 0.15,
        ]
        total = sum(scores)

        if total >= 65:
            signal = Signal.BUY
        elif total >= 45:
            signal = Signal.HOLD
        else:
            signal = Signal.SELL

        confidence = min(100, max(10, int(abs(total - 50) * 2)))
        return signal, confidence

    def _generate_summary(
        self,
        stock_data: StockData,
        cycle: Dict[str, Any],
        industry_fit: Dict[str, Any],
        signal: Signal,
    ) -> str:
        """生成摘要

        Args:
            stock_data: 股票数据
            cycle: 经济周期信息
            industry_fit: 行业适配度信息
            signal: 交易信号

        Returns:
            分析摘要字符串
        """
        return (
            f"{stock_data.stock_name}宏观分析："
            f"当前经济周期{cycle.get('current_phase', '未知')}，"
            f"行业适配度{industry_fit.get('fit_level', '未知')}，"
            f"宏观信号{signal.value}"
        )
