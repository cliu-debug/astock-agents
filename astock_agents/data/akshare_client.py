"""Akshare 数据源客户端 - 提供基本面数据和财务报告"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from astock_agents.data.base_client import BaseDataClient
from astock_agents.data.circuit_breaker import get_circuit_breaker, with_retry
from astock_agents.models.stock_data import StockPrice, FinancialReport


class AkshareClient(BaseDataClient):
    """Akshare 数据源客户端 - 提供财务数据、估值指标和历史数据"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="akshare", config=config)
        self._circuit_breaker = get_circuit_breaker("akshare")

    def fetch_kline(
        self,
        stock_code: str,
        days: int = 250,
        freq: str = "daily"
    ) -> Optional[List[StockPrice]]:
        """
        获取K线数据（带断路器保护）

        Args:
            stock_code: 股票代码（如 600519.SH）
            days: 获取天数
            freq: 频率 daily/weekly/monthly

        Returns:
            价格列表，失败返回 None
        """
        if not self._enabled:
            return None
        if self._circuit_breaker.is_open:
            logger.warning("[akshare] 断路器已断开，跳过K线请求")
            return None
        try:
            result = self._fetch_kline_impl(stock_code, days, freq)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"[akshare] 获取K线失败: {stock_code}, {e}")
            return None

    @with_retry(max_attempts=2, wait_min=1.0, wait_max=5.0)
    def _fetch_kline_impl(
        self,
        stock_code: str,
        days: int,
        freq: str
    ) -> Optional[List[StockPrice]]:
        """
        K线数据获取实现（带重试）

        Args:
            stock_code: 股票代码
            days: 获取天数
            freq: 频率

        Returns:
            价格列表，失败抛出异常

        Raises:
            Exception: API调用失败时抛出
        """
        import akshare as ak

        code = self._normalize_stock_code(stock_code)
        market = self._determine_market(stock_code)

        # akshare 股票代码格式
        ak_code = code

        # 频率映射
        period_map = {"daily": "daily", "weekly": "weekly", "monthly": "monthly"}
        period = period_map.get(freq, "daily")

        df = ak.stock_zh_a_hist(
            symbol=ak_code,
            period=period,
            adjust="qfq"  # 前复权
        )

        if df is None or df.empty:
            logger.warning(f"[akshare] 无K线数据: {stock_code}")
            return None

        # 截取最近 days 天
        df = df.tail(days)

        prices = []
        for _, row in df.iterrows():
            date_val = row.get("日期", row.get("date", ""))
            if isinstance(date_val, str):
                date_val = datetime.strptime(date_val, "%Y-%m-%d")

            price = StockPrice(
                date=date_val,
                open=float(row.get("开盘", row.get("open", 0))),
                high=float(row.get("最高", row.get("high", 0))),
                low=float(row.get("最低", row.get("low", 0))),
                close=float(row.get("收盘", row.get("close", 0))),
                volume=int(row.get("成交量", row.get("volume", 0))),
                amount=float(row.get("成交额", row.get("amount", 0))),
            )
            prices.append(price)

        logger.info(f"[akshare] 获取K线成功: {stock_code}, {len(prices)}条")
        return prices

    def fetch_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情（带断路器保护）

        Args:
            stock_code: 股票代码

        Returns:
            行情字典，失败返回 None
        """
        if not self._enabled:
            return None
        if self._circuit_breaker.is_open:
            logger.warning("[akshare] 断路器已断开，跳过实时行情请求")
            return None
        try:
            result = self._fetch_realtime_quote_impl(stock_code)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"[akshare] 获取实时行情失败: {stock_code}, {e}")
            return None

    @with_retry(max_attempts=2, wait_min=1.0, wait_max=5.0)
    def _fetch_realtime_quote_impl(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        实时行情获取实现（带重试）

        Args:
            stock_code: 股票代码

        Returns:
            行情字典，失败抛出异常

        Raises:
            Exception: API调用失败时抛出
        """
        import akshare as ak

        code = self._normalize_stock_code(stock_code)

        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return None

        row = df[df["代码"] == code]
        if row.empty:
            return None

        row = row.iloc[0]
        return {
            "stock_code": stock_code,
            "stock_name": str(row.get("名称", "")),
            "price": float(row.get("最新价", 0)),
            "open": float(row.get("今开", 0)),
            "high": float(row.get("最高", 0)),
            "low": float(row.get("最低", 0)),
            "close": float(row.get("最新价", 0)),
            "volume": int(row.get("成交量", 0)),
            "amount": float(row.get("成交额", 0)),
            "change_pct": float(row.get("涨跌幅", 0)),
            "pe_ttm": float(row.get("市盈率-动态", 0)) if row.get("市盈率-动态") else None,
            "pb": float(row.get("市净率", 0)) if row.get("市净率") else None,
            "market_cap": float(row.get("总市值", 0)) if row.get("总市值") else None,
        }

    def fetch_financial_reports(self, stock_code: str) -> Optional[List[FinancialReport]]:
        """
        获取财务报告（带断路器保护）

        Args:
            stock_code: 股票代码

        Returns:
            财务报告列表，失败返回 None
        """
        if not self._enabled:
            return None
        if self._circuit_breaker.is_open:
            logger.warning("[akshare] 断路器已断开，跳过财务报告请求")
            return None
        try:
            result = self._fetch_financial_reports_impl(stock_code)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"[akshare] 获取财务报告失败: {stock_code}, {e}")
            return None

    @with_retry(max_attempts=2, wait_min=1.0, wait_max=5.0)
    def _fetch_financial_reports_impl(self, stock_code: str) -> Optional[List[FinancialReport]]:
        """
        财务报告获取实现（带重试）

        Args:
            stock_code: 股票代码

        Returns:
            财务报告列表，失败抛出异常

        Raises:
            Exception: API调用失败时抛出
        """
        import akshare as ak

        code = self._normalize_stock_code(stock_code)
        reports = []

        # 获取主要财务指标
        try:
            df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
            if df is not None and not df.empty:
                for _, row in df.head(3).iterrows():
                    # 解析报告期日期（可能是 "2024" 或 "2024-01-01" 等格式）
                    date_str = str(row.get("报告期", ""))[:10]
                    try:
                        if len(date_str) >= 10:
                            report_date = datetime.strptime(date_str, "%Y-%m-%d")
                        elif len(date_str) >= 4:
                            report_date = datetime(int(date_str[:4]), 1, 1)
                        else:
                            report_date = datetime.now()
                    except (ValueError, TypeError):
                        report_date = datetime.now()

                    report = FinancialReport(
                        report_date=report_date,
                        report_type="年报",
                        revenue=self._safe_float(row.get("营业总收入")),
                        net_profit=self._safe_float(row.get("净利润")),
                        roe=self._safe_float(row.get("净资产收益率")),
                        gross_margin=self._safe_float(row.get("销售毛利率")),
                        debt_ratio=self._safe_float(row.get("资产负债率")),
                    )
                    reports.append(report)
        except Exception as e:
            logger.debug(f"[akshare] 获取财务摘要失败: {e}")

        logger.info(f"[akshare] 获取财务报告: {stock_code}, {len(reports)}条")
        return reports if reports else None

    def fetch_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基本信息

        Args:
            stock_code: 股票代码

        Returns:
            基本信息字典
        """
        if not self._enabled:
            return None

        try:
            import akshare as ak

            code = self._normalize_stock_code(stock_code)
            df = ak.stock_individual_info_em(symbol=code)

            if df is None or df.empty:
                return None

            info = {}
            for _, row in df.iterrows():
                key = str(row.iloc[0])
                value = row.iloc[1]
                info[key] = value

            return {
                "stock_name": info.get("股票简称", ""),
                "industry": info.get("行业", ""),
                "list_date": info.get("上市时间", ""),
                "total_share": info.get("总市值", None),
            }

        except Exception as e:
            logger.error(f"[akshare] 获取股票信息失败: {stock_code}, {e}")
            return None

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """安全转换为浮点数"""
        if value is None:
            return None
        try:
            # 处理百分比字符串
            if isinstance(value, str):
                value = value.replace("%", "").replace("亿", "").strip()
            return float(value)
        except (ValueError, TypeError):
            return None
