"""同花顺数据客户端

基于 a-stock-data 的同花顺API实现
提供热点强势股、北向资金、概念板块等数据
"""

import requests
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from astock_agents.data.base_client import BaseDataClient
from astock_agents.models.stock_data import StockPrice, FinancialReport


class TonghuashunClient(BaseDataClient):
    """同花顺数据客户端
    
    数据来源: https://github.com/simonlin1212/a-stock-data
    提供:
    - 热点强势股 + 题材归因
    - 北向资金实时/历史
    - 行业板块排名
    """
    
    # API endpoints
    HOT_STOCKS_URL = "https://dq.10jqka.com.cn/fuyao/hotlist/v2/data/hot_list"
    NORTH_BOUND_URL = "https://data.10jqka.com.cn/ifmarket/northbound/history"
    INDUSTRY_URL = "https://data.10jqka.com.cn/rank/yzyy/"
    
    UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    
    def __init__(self, enabled: bool = True, cache_dir: str = "./cache"):
        super().__init__(name="tonghuashun", config={"enabled": enabled})
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": self.UA,
            "Referer": "https://data.10jqka.com.cn/"
        })
        self._cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self.enabled
    
    # ==================== 热点强势股 ====================
    
    def get_hot_stocks(self) -> List[Dict[str, Any]]:
        """获取当日热点强势股 + 题材归因
        
        Returns:
            热点股票列表，包含题材标签
        """
        if not self.enabled:
            return []
        
        try:
            params = {
                "type": "1",
                "size": "100",
                "date_type": "1",
                "page": "1",
            }
            
            r = self._session.get(self.HOT_STOCKS_URL, params=params, timeout=10)
            d = r.json()
            
            if d.get("data"):
                stocks = []
                for item in d["data"]:
                    stock = {
                        "code": item.get("code"),
                        "name": item.get("name"),
                        "price": item.get("price"),
                        "change_pct": item.get("change_percent"),
                        "reason": item.get("reason", ""),  # 题材归因
                        "hot_rank": item.get("rank"),
                    }
                    stocks.append(stock)
                
                logger.info(f"[tonghuashun] 获取到 {len(stocks)} 只热点股")
                return stocks
                
        except Exception as e:
            logger.warning(f"[tonghuashun] 获取热点股失败: {e}")
        
        return []
    
    # ==================== 北向资金 ====================
    
    def get_north_bound_flow(self, market: str = "sh") -> Optional[Dict[str, Any]]:
        """获取北向资金实时流向
        
        Args:
            market: 'sh'=沪股通, 'sz'=深股通
        
        Returns:
            资金流向数据
        """
        if not self.enabled:
            return None
        
        try:
            params = {
                "market": market,
                "type": "1",  # 1=实时
            }
            
            r = self._session.get(self.NORTH_BOUND_URL, params=params, timeout=10)
            d = r.json()
            
            if d.get("data"):
                return {
                    "market": "沪股通" if market == "sh" else "深股通",
                    "net_inflow": d["data"].get("net_inflow"),
                    "buy_amount": d["data"].get("buy_amount"),
                    "sell_amount": d["data"].get("sell_amount"),
                    "timestamp": d["data"].get("timestamp"),
                }
                
        except Exception as e:
            logger.warning(f"[tonghuashun] 获取北向资金失败: {e}")
        
        return None
    
    def get_north_bound_history(self, days: int = 20) -> List[Dict[str, Any]]:
        """获取北向资金历史流向（本地缓存）
        
        Args:
            days: 获取天数
        
        Returns:
            历史资金流向列表
        """
        cache_file = os.path.join(self._cache_dir, "north_bound_history.json")
        
        # 尝试读取缓存
        cached_data = []
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        
        if not self.enabled:
            return cached_data
        
        # 获取新数据并更新缓存
        try:
            params = {
                "market": "sh",
                "type": "2",  # 2=历史
                "days": str(days),
            }
            
            r = self._session.get(self.NORTH_BOUND_URL, params=params, timeout=10)
            d = r.json()
            
            if d.get("data") and d["data"].get("list"):
                new_data = d["data"]["list"]
                
                # 合并并去重
                all_data = {item["date"]: item for item in cached_data}
                for item in new_data:
                    all_data[item["date"]] = item
                
                # 保存缓存
                result = list(all_data.values())
                with open(cache_file, 'w') as f:
                    json.dump(result, f)
                
                return result
                
        except Exception as e:
            logger.warning(f"[tonghuashun] 获取北向历史失败: {e}")
        
        return cached_data
    
    # ==================== 行业板块 ====================
    
    def get_industry_ranking(self) -> List[Dict[str, Any]]:
        """获取行业板块涨跌排名
        
        Returns:
            行业排名列表
        """
        if not self.enabled:
            return []
        
        try:
            params = {
                "type": "1",
                "page": "1",
                "size": "100",
            }
            
            r = self._session.get(self.INDUSTRY_URL, params=params, timeout=10)
            d = r.json()
            
            if d.get("data"):
                industries = []
                for item in d["data"]:
                    industry = {
                        "name": item.get("name"),
                        "change_pct": item.get("change_percent"),
                        "leader": item.get("leader_name"),
                        "leader_change": item.get("leader_change"),
                    }
                    industries.append(industry)
                
                return industries
                
        except Exception as e:
            logger.warning(f"[tonghuashun] 获取行业排名失败: {e}")
        
        return []
    
    # ==================== BaseClient接口实现 ====================

    def fetch_kline(
        self,
        stock_code: str,
        days: int = 250,
        freq: str = "daily"
    ) -> Optional[List[StockPrice]]:
        """获取K线数据

        同花顺不提供K线API，返回None由其他数据源降级获取

        Args:
            stock_code: 股票代码（如 600519.SH）
            days: 获取天数
            freq: 频率 daily/weekly

        Returns:
            None（同花顺不提供K线数据）
        """
        return None

    def fetch_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取实时行情

        从热点列表中查找目标股票

        Args:
            stock_code: 股票代码

        Returns:
            行情字典，失败返回 None
        """
        hot_stocks = self.get_hot_stocks()
        code = self._normalize_stock_code(stock_code)

        for stock in hot_stocks:
            if stock.get("code") == code:
                return stock

        return None

    def fetch_financial_reports(self, stock_code: str) -> Optional[List[FinancialReport]]:
        """获取财务报告

        同花顺不提供财务数据，返回None

        Args:
            stock_code: 股票代码

        Returns:
            None
        """
        return None
