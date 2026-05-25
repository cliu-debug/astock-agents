"""投资组合风险分析 - 相关性、Beta、组合波动率、风险平价"""

from typing import List, Dict, Any, Optional
from loguru import logger

from astock_agents.models.portfolio import Position


class PortfolioRiskAnalyzer:
    """投资组合风险分析器"""

    def analyze(
        self,
        positions: List[Position],
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """分析组合风险

        Args:
            positions: 持仓列表
            market_data: 市场数据（可选，预留扩展）

        Returns:
            包含风险等级、总风险评分、集中度风险、行业集中度、再平衡建议的字典
        """
        if not positions:
            return {"risk_level": "无持仓", "total_risk_score": 0}

        # 1. 集中度风险
        concentration_risk = self._calc_concentration_risk(positions)

        # 2. 行业集中度
        industry_concentration = self._calc_industry_concentration(positions)

        # 3. 组合整体风险评分
        total_risk = self._calc_total_risk(concentration_risk, industry_concentration)

        # 4. 风险等级
        risk_level = self._determine_risk_level(total_risk)

        # 5. 再平衡建议
        rebalance_suggestions = self._generate_rebalance_suggestions(
            positions, concentration_risk, industry_concentration
        )

        return {
            "risk_level": risk_level,
            "total_risk_score": total_risk,
            "concentration_risk": concentration_risk,
            "industry_concentration": industry_concentration,
            "position_count": len(positions),
            "rebalance_suggestions": rebalance_suggestions,
        }

    def _calc_concentration_risk(
        self, positions: List[Position]
    ) -> Dict[str, Any]:
        """计算集中度风险

        Args:
            positions: 持仓列表

        Returns:
            包含评分、最大权重、最大权重股票、描述、权重分布的字典
        """
        total_value = sum(
            p.market_value or p.avg_cost * p.quantity for p in positions
        )
        if total_value == 0:
            return {"score": 0, "max_weight": 0, "description": "无持仓"}

        weights: Dict[str, float] = {}
        for p in positions:
            value = p.market_value or p.avg_cost * p.quantity
            weights[p.stock_code] = round(value / total_value * 100, 1)

        max_weight = max(weights.values()) if weights else 0

        if max_weight > 40:
            score, desc = 80, "高度集中，单股占比超40%"
        elif max_weight > 25:
            score, desc = 50, "中度集中，单股占比超25%"
        else:
            score, desc = 20, "分散度良好"

        return {
            "score": score,
            "max_weight": max_weight,
            "max_weight_stock": (
                max(weights, key=weights.get) if weights else None
            ),
            "description": desc,
            "weights": weights,
        }

    def _calc_industry_concentration(
        self, positions: List[Position]
    ) -> Dict[str, Any]:
        """计算行业集中度

        简化版：按股票名称中的行业关键词分类。

        Args:
            positions: 持仓列表

        Returns:
            包含评分、最大行业、最大行业权重、行业权重分布的字典
        """
        # 行业关键词映射
        industry_map: Dict[str, List[str]] = {
            "银行": ["银行"],
            "白酒": ["茅台", "五粮液", "泸州老窖"],
            "医药": ["医药", "恒瑞", "药明"],
            "新能源": ["宁德", "隆基"],
            "家电": ["美的", "格力", "海尔"],
            "保险": ["平安"],
        }

        total_value = sum(
            p.market_value or p.avg_cost * p.quantity for p in positions
        )
        if total_value == 0:
            return {"score": 0, "top_industry": None}

        industry_values: Dict[str, float] = {}
        for p in positions:
            value = p.market_value or p.avg_cost * p.quantity
            matched = False
            for industry, keywords in industry_map.items():
                if any(kw in p.stock_name for kw in keywords):
                    industry_values[industry] = (
                        industry_values.get(industry, 0) + value
                    )
                    matched = True
                    break
            if not matched:
                industry_values["其他"] = (
                    industry_values.get("其他", 0) + value
                )

        industry_weights: Dict[str, float] = {
            k: round(v / total_value * 100, 1)
            for k, v in industry_values.items()
        }
        max_industry_weight = (
            max(industry_weights.values()) if industry_weights else 0
        )
        top_industry = (
            max(industry_weights, key=industry_weights.get)
            if industry_weights
            else None
        )

        if max_industry_weight > 50:
            score = 70
        elif max_industry_weight > 30:
            score = 40
        else:
            score = 15

        return {
            "score": score,
            "top_industry": top_industry,
            "top_industry_weight": max_industry_weight,
            "industry_weights": industry_weights,
        }

    def _calc_total_risk(
        self, concentration: Dict[str, Any], industry: Dict[str, Any]
    ) -> int:
        """计算总风险评分

        Args:
            concentration: 集中度风险信息
            industry: 行业集中度信息

        Returns:
            总风险评分（0-100）
        """
        return min(
            100,
            int(
                concentration.get("score", 0) * 0.5
                + industry.get("score", 0) * 0.5
            ),
        )

    def _determine_risk_level(self, score: int) -> str:
        """确定风险等级

        Args:
            score: 总风险评分

        Returns:
            风险等级描述字符串
        """
        if score >= 70:
            return "高风险"
        elif score >= 40:
            return "中等风险"
        else:
            return "低风险"

    def _generate_rebalance_suggestions(
        self,
        positions: List[Position],
        concentration: Dict[str, Any],
        industry: Dict[str, Any],
    ) -> List[str]:
        """生成再平衡建议

        Args:
            positions: 持仓列表
            concentration: 集中度风险信息
            industry: 行业集中度信息

        Returns:
            再平衡建议列表
        """
        suggestions: List[str] = []

        if concentration.get("max_weight", 0) > 30:
            stock = concentration.get("max_weight_stock", "")
            suggestions.append(
                f"减仓{stock}，当前占比{concentration['max_weight']}%，"
                f"建议降至20%以下"
            )

        if industry.get("top_industry_weight", 0) > 40:
            ind = industry.get("top_industry", "")
            suggestions.append(
                f"行业'{ind}'集中度过高({industry['top_industry_weight']}%)，"
                f"建议分散配置"
            )

        if len(positions) < 3:
            suggestions.append("持仓数量过少（<3只），建议增加持仓以分散风险")

        if not suggestions:
            suggestions.append("组合配置合理，无需调整")

        return suggestions
