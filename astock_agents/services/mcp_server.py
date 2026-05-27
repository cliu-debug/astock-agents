"""MCP (Model Context Protocol) 服务

提供标准化的工具调用接口，让LLM Agent能够调用专业金融工具。
每个工具定义包含名称、描述和输入参数Schema，遵循MCP协议规范。
"""

import json
from typing import Dict, Any, List, Optional
from loguru import logger

from astock_agents.data.manager import DataManager


class MCPTool:
    """MCP工具定义

    Attributes:
        name: 工具名称
        description: 工具描述
        input_schema: 输入参数JSON Schema
    """

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
    ):
        """
        初始化MCP工具定义

        Args:
            name: 工具名称
            description: 工具描述
            input_schema: 输入参数JSON Schema
        """
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class MCPServer:
    """MCP服务 - 管理和执行金融工具调用

    提供标准化的工具注册、发现和调用机制，
    让LLM Agent能够通过MCP协议调用专业金融工具。
    """

    def __init__(self, data_manager: Optional[DataManager] = None):
        """
        初始化MCP服务

        Args:
            data_manager: 数据管理器实例，为空时自动创建
        """
        self.data_manager = data_manager or DataManager()
        self._tools: Dict[str, MCPTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """注册默认的金融工具集"""
        tools = [
            MCPTool(
                name="get_stock_price",
                description="获取A股实时行情数据，包括当前价格、涨跌幅、成交量等",
                input_schema={
                    "type": "object",
                    "properties": {
                        "stock_code": {
                            "type": "string",
                            "description": "股票代码，如 600519",
                        },
                    },
                    "required": ["stock_code"],
                },
            ),
            MCPTool(
                name="get_stock_kline",
                description="获取股票K线数据，支持日K、周K、月K",
                input_schema={
                    "type": "object",
                    "properties": {
                        "stock_code": {
                            "type": "string",
                            "description": "股票代码，如 600519",
                        },
                        "period": {
                            "type": "string",
                            "description": "K线周期: daily/weekly/monthly",
                            "default": "daily",
                        },
                        "days": {
                            "type": "integer",
                            "description": "获取天数",
                            "default": 120,
                        },
                    },
                    "required": ["stock_code"],
                },
            ),
            MCPTool(
                name="get_financial_report",
                description="获取股票财务报告数据，包括营收、净利润、ROE等关键指标",
                input_schema={
                    "type": "object",
                    "properties": {
                        "stock_code": {
                            "type": "string",
                            "description": "股票代码，如 600519",
                        },
                        "report_type": {
                            "type": "string",
                            "description": "报告类型: summary/detail",
                            "default": "summary",
                        },
                    },
                    "required": ["stock_code"],
                },
            ),
            MCPTool(
                name="get_news",
                description="获取股票相关新闻资讯，包括公司新闻、行业动态、政策解读",
                input_schema={
                    "type": "object",
                    "properties": {
                        "stock_code": {
                            "type": "string",
                            "description": "股票代码，如 600519",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回条数",
                            "default": 10,
                        },
                    },
                    "required": ["stock_code"],
                },
            ),
            MCPTool(
                name="calculate_indicator",
                description="计算技术指标，支持MA、MACD、RSI、KDJ、BOLL等常用指标",
                input_schema={
                    "type": "object",
                    "properties": {
                        "stock_code": {
                            "type": "string",
                            "description": "股票代码，如 600519",
                        },
                        "indicator": {
                            "type": "string",
                            "description": "指标名称: MA/MACD/RSI/KDJ/BOLL",
                        },
                        "params": {
                            "type": "object",
                            "description": "指标参数，如 {\"period\": 14}",
                            "default": {},
                        },
                    },
                    "required": ["stock_code", "indicator"],
                },
            ),
            MCPTool(
                name="get_capital_flow",
                description="获取资金流向数据，包括主力资金、北向资金、融资融券等",
                input_schema={
                    "type": "object",
                    "properties": {
                        "stock_code": {
                            "type": "string",
                            "description": "股票代码，如 600519",
                        },
                        "days": {
                            "type": "integer",
                            "description": "获取天数",
                            "default": 10,
                        },
                    },
                    "required": ["stock_code"],
                },
            ),
        ]

        for tool in tools:
            self._tools[tool.name] = tool

        logger.info(f"[MCP] 已注册 {len(tools)} 个默认工具")

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有可用工具

        Returns:
            工具定义字典列表
        """
        return [tool.to_dict() for tool in self._tools.values()]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数字典

        Returns:
            工具执行结果字典

        Raises:
            ValueError: 工具不存在时抛出
        """
        if tool_name not in self._tools:
            raise ValueError(f"工具不存在: {tool_name}")

        tool = self._tools[tool_name]
        logger.info(f"[MCP] 调用工具: {tool_name}, 参数: {arguments}")

        try:
            # 根据工具名称路由到对应的执行方法
            handler = getattr(self, f"_handle_{tool_name}", None)
            if handler is None:
                return {
                    "success": False,
                    "error": f"工具处理器未实现: {tool_name}",
                }

            result = handler(arguments)
            return {"success": True, "data": result}

        except Exception as e:
            logger.error(f"[MCP] 工具调用失败: {tool_name}, {e}")
            return {"success": False, "error": str(e)}

    # ==================== 工具处理器 ====================

    def _handle_get_stock_price(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理获取股票实时行情

        Args:
            args: 包含 stock_code 的参数字典

        Returns:
            股票实时行情数据
        """
        stock_code = args.get("stock_code", "")
        stock_data = self.data_manager.get_stock_data(stock_code)

        if not stock_data:
            return {"error": f"未找到股票数据: {stock_code}"}

        return {
            "stock_code": stock_data.stock_code,
            "stock_name": stock_data.stock_name,
            "current_price": stock_data.current_price,
            "industry": stock_data.industry,
            "pe_ttm": stock_data.pe_ttm,
        }

    def _handle_get_stock_kline(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理获取K线数据

        Args:
            args: 包含 stock_code, period, days 的参数字典

        Returns:
            K线数据
        """
        stock_code = args.get("stock_code", "")
        days = args.get("days", 120)

        stock_data = self.data_manager.get_stock_data(stock_code, days=days)

        if not stock_data or not stock_data.prices:
            return {"error": f"未找到K线数据: {stock_code}"}

        kline_data = [
            {
                "date": p.date.strftime("%Y-%m-%d"),
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume,
            }
            for p in stock_data.prices[-days:]
        ]

        return {
            "stock_code": stock_data.stock_code,
            "stock_name": stock_data.stock_name,
            "period": args.get("period", "daily"),
            "kline": kline_data,
        }

    def _handle_get_financial_report(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理获取财务报告

        Args:
            args: 包含 stock_code, report_type 的参数字典

        Returns:
            财务报告数据
        """
        stock_code = args.get("stock_code", "")
        report_type = args.get("report_type", "summary")

        stock_data = self.data_manager.get_stock_data(stock_code)

        if not stock_data:
            return {"error": f"未找到股票数据: {stock_code}"}

        result: Dict[str, Any] = {
            "stock_code": stock_data.stock_code,
            "stock_name": stock_data.stock_name,
        }

        # 添加财务指标
        if stock_data.financials:
            if report_type == "summary":
                fin = stock_data.financials[0] if stock_data.financials else None
                if fin:
                    result["financial_summary"] = {
                        "report_date": fin.report_date.strftime("%Y-%m-%d") if fin.report_date else None,
                        "revenue": fin.revenue,
                        "net_profit": fin.net_profit,
                        "roe": fin.roe,
                        "eps": fin.eps,
                    }
            else:
                result["financials"] = [
                    {
                        "report_date": f.report_date.strftime("%Y-%m-%d") if f.report_date else None,
                        "revenue": f.revenue,
                        "net_profit": f.net_profit,
                        "roe": f.roe,
                        "eps": f.eps,
                    }
                    for f in stock_data.financials
                ]
        else:
            result["financial_summary"] = None

        return result

    def _handle_get_news(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理获取新闻

        Args:
            args: 包含 stock_code, limit 的参数字典

        Returns:
            新闻数据
        """
        stock_code = args.get("stock_code", "")
        limit = args.get("limit", 10)

        try:
            from astock_agents.data.news_client import NewsClient
            news_client = NewsClient()
            news_list = news_client.get_stock_news(stock_code, limit=limit)
            return {
                "stock_code": stock_code,
                "news": news_list if news_list else [],
            }
        except Exception as e:
            logger.warning(f"[MCP] 获取新闻失败: {e}")
            return {
                "stock_code": stock_code,
                "news": [],
                "error": f"新闻获取失败: {str(e)}",
            }

    def _handle_calculate_indicator(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理计算技术指标

        Args:
            args: 包含 stock_code, indicator, params 的参数字典

        Returns:
            技术指标计算结果
        """
        stock_code = args.get("stock_code", "")
        indicator = args.get("indicator", "").upper()
        params = args.get("params", {})

        stock_data = self.data_manager.get_stock_data(stock_code)

        if not stock_data or not stock_data.prices:
            return {"error": f"未找到股票数据: {stock_code}"}

        prices = stock_data.prices
        closes = [p.close for p in prices]

        result: Dict[str, Any] = {
            "stock_code": stock_data.stock_code,
            "indicator": indicator,
        }

        if indicator == "MA":
            period = params.get("period", 5)
            if len(closes) >= period:
                ma_value = sum(closes[-period:]) / period
                result["value"] = round(ma_value, 2)
                result["period"] = period
        elif indicator == "RSI":
            period = params.get("period", 14)
            result["value"] = self._calculate_rsi(closes, period)
            result["period"] = period
        elif indicator == "MACD":
            macd_data = self._calculate_macd(closes)
            result.update(macd_data)
        elif indicator == "KDJ":
            kdj_data = self._calculate_kdj(prices)
            result.update(kdj_data)
        elif indicator == "BOLL":
            boll_data = self._calculate_boll(closes)
            result.update(boll_data)
        else:
            result["error"] = f"不支持的指标: {indicator}"

        return result

    def _handle_get_capital_flow(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理获取资金流向

        Args:
            args: 包含 stock_code, days 的参数字典

        Returns:
            资金流向数据
        """
        stock_code = args.get("stock_code", "")
        days = args.get("days", 10)

        try:
            from astock_agents.data.akshare_client import AkshareClient
            akshare = AkshareClient()
            flow_data = akshare.get_capital_flow(stock_code, days=days)
            return {
                "stock_code": stock_code,
                "capital_flow": flow_data if flow_data else [],
            }
        except Exception as e:
            logger.warning(f"[MCP] 获取资金流向失败: {e}")
            return {
                "stock_code": stock_code,
                "capital_flow": [],
                "error": f"资金流向获取失败: {str(e)}",
            }

    # ==================== 技术指标计算 ====================

    @staticmethod
    def _calculate_rsi(closes: List[float], period: int = 14) -> float:
        """计算RSI指标

        Args:
            closes: 收盘价列表
            period: RSI周期

        Returns:
            RSI值
        """
        if len(closes) < period + 1:
            return 50.0

        gains = []
        losses = []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

    @staticmethod
    def _calculate_macd(
        closes: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Dict[str, Any]:
        """计算MACD指标

        Args:
            closes: 收盘价列表
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期

        Returns:
            MACD指标字典
        """
        if len(closes) < slow:
            return {"dif": None, "dea": None, "macd": None}

        # 简化EMA计算
        def ema(data: List[float], period: int) -> List[float]:
            multiplier = 2 / (period + 1)
            result = [data[0]]
            for price in data[1:]:
                result.append(price * multiplier + result[-1] * (1 - multiplier))
            return result

        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        dif = [f - s for f, s in zip(ema_fast, ema_slow)]

        if len(dif) < signal:
            return {"dif": None, "dea": None, "macd": None}

        dea = ema(dif, signal)
        macd_line = [2 * (d - e) for d, e in zip(dif, dea)]

        return {
            "dif": round(dif[-1], 4),
            "dea": round(dea[-1], 4),
            "macd": round(macd_line[-1], 4),
        }

    @staticmethod
    def _calculate_kdj(prices: list, n: int = 9) -> Dict[str, Any]:
        """计算KDJ指标

        Args:
            prices: StockPrice对象列表
            n: KDJ周期

        Returns:
            KDJ指标字典
        """
        if len(prices) < n:
            return {"k": None, "d": None, "j": None}

        recent = prices[-n:]
        high_n = max(p.high for p in recent)
        low_n = min(p.low for p in recent)
        close = recent[-1].close

        if high_n == low_n:
            rsv = 50.0
        else:
            rsv = (close - low_n) / (high_n - low_n) * 100

        # 简化KDJ计算
        k = rsv
        d = k
        j = 3 * k - 2 * d

        return {
            "k": round(k, 2),
            "d": round(d, 2),
            "j": round(j, 2),
        }

    @staticmethod
    def _calculate_boll(closes: List[float], period: int = 20) -> Dict[str, Any]:
        """计算布林带指标

        Args:
            closes: 收盘价列表
            period: 布林带周期

        Returns:
            布林带指标字典
        """
        if len(closes) < period:
            return {"upper": None, "middle": None, "lower": None}

        recent = closes[-period:]
        middle = sum(recent) / period
        variance = sum((x - middle) ** 2 for x in recent) / period
        std_dev = variance ** 0.5

        return {
            "upper": round(middle + 2 * std_dev, 2),
            "middle": round(middle, 2),
            "lower": round(middle - 2 * std_dev, 2),
        }
