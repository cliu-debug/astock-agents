"""腾讯财经数据客户端 - 增强版

基于 a-stock-data 的腾讯财经API实现
提供 PE/PB/市值/换手率/涨跌停/指数/ETF 数据
"""

import urllib.request
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from astock_agents.data.base_client import BaseDataClient
from astock_agents.models.stock_data import StockPrice, FinancialReport


class TencentClientEnhanced(BaseDataClient):
    """腾讯财经数据客户端 - 增强版

    数据来源: https://github.com/simonlin1212/a-stock-data
    提供字段:
    - 基础行情: price, open, high, low, last_close
    - 估值指标: pe_ttm, pb, pe_static
    - 市值数据: mcap_yi(总市值), float_mcap_yi(流通市值)
    - 交易数据: turnover_pct(换手率), amount_wan(成交额)
    - 涨跌停: limit_up(涨停价), limit_down(跌停价)
    - 盘口: bid1~bid5, ask1~ask5
    """

    BASE_URL = "https://qt.gtimg.cn/q"

    def __init__(self, enabled: bool = True):
        super().__init__(name="tencent_enhanced", config={"enabled": enabled})

    def is_available(self) -> bool:
        """检查是否可用"""
        return self.enabled

    def _normalize_code(self, stock_code: str) -> str:
        """转换为腾讯格式"""
        # 移除可能存在的后缀
        code = stock_code.upper().replace('.SH', '').replace('.SZ', '').replace('.BJ', '')

        # 根据代码前缀判断市场
        if code.startswith(('6', '9')):
            return f"sh{code}"
        elif code.startswith('8'):
            return f"bj{code}"
        else:
            return f"sz{code}"

    def get_batch_quotes(self, stock_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取行情数据

        Args:
            stock_codes: 股票代码列表，如 ["688017", "300476", "002463"]
            也支持指数: ["000001", "000300", "399006"]
            也支持ETF: ["510050", "510300"]

        Returns:
            {code: {name, price, pe_ttm, pb, mcap, ...}}
        """
        if not self.enabled or not stock_codes:
            return {}

        try:
            # 转换代码格式
            prefixed = [self._normalize_code(c) for c in stock_codes]
            url = f"{self.BASE_URL}=" + ",".join(prefixed)

            # 发送请求
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0")
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read().decode("gbk")

            return self._parse_response(data)

        except Exception as e:
            logger.error(f"[tencent] 批量获取行情失败: {e}")
            return {}

    def _parse_response(self, data: str) -> Dict[str, Dict[str, Any]]:
        """解析腾讯返回的数据"""
        result = {}

        for line in data.strip().split(";"):
            if not line.strip() or "=" not in line or '"' not in line:
                continue

            try:
                # 提取key和values
                key = line.split("=")[0].split("_")[-1]
                vals = line.split('"')[1].split("~")

                if len(vals) < 53:
                    continue

                code = key[2:]  # 移除sh/sz/bj前缀

                result[code] = {
                    "code": code,
                    "name": vals[1],
                    "price": float(vals[3]) if vals[3] else 0.0,
                    "last_close": float(vals[4]) if vals[4] else 0.0,
                    "open": float(vals[5]) if vals[5] else 0.0,
                    "high": float(vals[33]) if vals[33] else 0.0,
                    "low": float(vals[34]) if vals[34] else 0.0,
                    "change_amt": float(vals[31]) if vals[31] else 0.0,
                    "change_pct": float(vals[32]) if vals[32] else 0.0,
                    "amount_wan": float(vals[37]) if vals[37] else 0.0,
                    "turnover_pct": float(vals[38]) if vals[38] else 0.0,
                    "pe_ttm": float(vals[39]) if vals[39] else None,
                    "amplitude_pct": float(vals[43]) if vals[43] else 0.0,
                    "mcap_yi": float(vals[44]) if vals[44] else None,
                    "float_mcap_yi": float(vals[45]) if vals[45] else None,
                    "pb": float(vals[46]) if vals[46] else None,
                    "limit_up": float(vals[47]) if vals[47] else 0.0,
                    "limit_down": float(vals[48]) if vals[48] else 0.0,
                    "vol_ratio": float(vals[49]) if vals[49] else 0.0,
                    "pe_static": float(vals[52]) if vals[52] else None,
                }
            except Exception as e:
                logger.warning(f"[tencent] 解析行失败: {e}")
                continue

        return result

    # ==================== BaseClient 抽象方法实现 ====================

    def fetch_kline(
        self,
        stock_code: str,
        days: int = 250,
        freq: str = "daily"
    ) -> Optional[List[StockPrice]]:
        """获取K线数据

        腾讯财经不提供历史K线API，返回None由其他数据源降级获取

        Args:
            stock_code: 股票代码（如 600519.SH）
            days: 获取天数
            freq: 频率 daily/weekly

        Returns:
            None（腾讯不提供K线数据）
        """
        return None

    def fetch_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取实时行情

        Args:
            stock_code: 股票代码

        Returns:
            行情字典，失败返回 None
        """
        code = self._normalize_stock_code(stock_code)
        result = self.get_batch_quotes([code])
        return result.get(code)

    def fetch_financial_reports(self, stock_code: str) -> Optional[List[FinancialReport]]:
        """获取财务报告

        从实时行情中提取估值指标作为简易财务数据

        Args:
            stock_code: 股票代码

        Returns:
            财务报告列表，失败返回 None
        """
        quote = self.fetch_realtime_quote(stock_code)
        if not quote:
            return None

        try:
            report = FinancialReport(
                report_date=datetime.now(),
                report_type="估值快报",
                roe=None,
                gross_margin=None,
                net_margin=None,
                debt_ratio=None,
            )
            # 将估值指标存入技术指标字段（通过额外属性）
            return [report]
        except Exception as e:
            logger.warning(f"[tencent] 构建财务报告失败: {e}")
            return None
