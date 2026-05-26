"""百度股市通数据客户端

基于 a-stock-data 的百度股市通API实现
提供K线(带MA)、概念板块、资金流向等数据
"""

import requests
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from astock_agents.data.base_client import BaseDataClient


class BaiduClient(BaseDataClient):
    """百度股市通数据客户端
    
    数据来源: https://github.com/simonlin1212/a-stock-data
    提供:
    - K线数据(自带MA5/MA10/MA20)
    - 概念板块归属
    - 资金流向(分钟级)
    """
    
    # API endpoints
    KLINE_URL = "https://finance.pae.baidu.com/selfselect/getstockquotation"
    CONCEPT_URL = "https://gushitong.baidu.com/opendata"
    
    def __init__(self, enabled: bool = True):
        super().__init__(name="baidu", enabled=enabled)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        })
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self.enabled
    
    # ==================== K线数据 ====================
    
    def get_kline_with_ma(self, stock_code: str, start_time: str = "") -> Dict[str, Any]:
        """获取K线数据（自带MA5/MA10/MA20）
        
        核心价值: 返回时自带均线数据，无需本地计算
        
        Args:
            stock_code: 股票代码
            start_time: 开始时间
        
        Returns:
            K线数据，包含ma5avgprice, ma10avgprice, ma20avgprice
        """
        if not self.enabled:
            return {}
        
        try:
            params = {
                "all": "1",
                "isIndex": "false",
                "isBk": "false",
                "isBlock": "false",
                "isFutures": "false",
                "isStock": "true",
                "newFormat": "1",
                "group": "quotation_kline_ab",
                "finClientType": "pc",
                "code": stock_code,
                "start_time": start_time,
                "ktype": "1",
            }
            
            r = self._session.get(self.KLINE_URL, params=params, timeout=10)
            d = r.json()
            
            result = d.get("Result", {})
            md = result.get("newMarketData", {})
            
            keys = md.get("keys", [])  # 包含: ma5avgprice, ma10avgprice, ma20avgprice
            rows = md.get("marketData", "").split(";") if md.get("marketData") else []
            
            return {
                "keys": keys,
                "rows": rows,
                "stock_code": stock_code,
            }
            
        except Exception as e:
            logger.warning(f"[baidu] 获取K线失败: {e}")
        
        return {}
    
    # ==================== 概念板块 ====================
    
    def get_concept_blocks(self, stock_code: str) -> Dict[str, Any]:
        """获取概念板块归属
        
        Args:
            stock_code: 股票代码
        
        Returns:
            行业/概念/地域三维归属
        """
        if not self.enabled:
            return {}
        
        try:
            params = {
                "resource_id": "6017",
                "query": "股票关联板块",
                "code": stock_code,
            }
            
            r = self._session.get(self.CONCEPT_URL, params=params, timeout=10)
            d = r.json()
            
            if d.get("ResultCode") in [0, "0"] and d.get("Result"):
                data = d["Result"]
                return {
                    "industry": data.get("industry", []),  # 行业
                    "concept": data.get("concept", []),    # 概念
                    "region": data.get("region", []),      # 地域
                    "stock_code": stock_code,
                }
            
        except Exception as e:
            logger.warning(f"[baidu] 获取概念板块失败: {e}")
        
        return {}
    
    # ==================== BaseClient接口实现 ====================
    
    def _fetch_kline(self, stock_code: str, period: str,
                     start_date: Optional[datetime], end_date: Optional[datetime],
                     limit: int) -> List[Dict[str, Any]]:
        """获取K线数据"""
        data = self.get_kline_with_ma(stock_code)
        
        if not data or not data.get("rows"):
            return []
        
        # 解析K线数据
        keys = data.get("keys", [])
        rows = data.get("rows", [])
        
        klines = []
        for row in rows:
            if not row:
                continue
            
            values = row.split(",")
            if len(values) < len(keys):
                continue
            
            # 构建字典
            item = {}
            for i, key in enumerate(keys):
                if i < len(values):
                    try:
                        # 尝试转换为数字
                        item[key] = float(values[i]) if "." in values[i] else int(values[i])
                    except (ValueError, TypeError):
                        item[key] = values[i]
            
            klines.append(item)
        
        return klines
    
    def _fetch_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取实时行情"""
        # 从K线数据中获取最新一条
        klines = self._fetch_kline(stock_code, "daily", None, None, 1)
        
        if klines:
            latest = klines[-1]
            return {
                "code": stock_code,
                "price": latest.get("close"),
                "open": latest.get("open"),
                "high": latest.get("high"),
                "low": latest.get("low"),
                "volume": latest.get("volume"),
                "ma5": latest.get("ma5avgprice"),
                "ma10": latest.get("ma10avgprice"),
                "ma20": latest.get("ma20avgprice"),
            }
        
        return None
    
    def _fetch_financial_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取财务数据"""
        # 百度不提供财务数据
        return None
