"""新闻和公告数据客户端

基于 a-stock-data 的新闻API实现
提供个股新闻、财联社快讯、公告数据等
"""

import requests
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from astock_agents.data.base_client import BaseDataClient
from astock_agents.models.stock_data import StockPrice, FinancialReport


class NewsClient(BaseDataClient):
    """新闻和公告数据客户端
    
    数据来源: https://github.com/simonlin1212/a-stock-data
    提供:
    - 个股新闻 (东财)
    - 财联社快讯
    - 巨潮公告
    """
    
    # API endpoints
    STOCK_NEWS_URL = "https://searchapi.eastmoney.com/api/suggest/get"
    CLS_NEWS_URL = "https://www.cls.cn/nodeapi/telegraphs"
    CNINFO_URL = "http://www.cninfo.com.cn/new/information/topSearch/query"
    CNINFO_ANNOUNCE_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    
    UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    
    def __init__(self, enabled: bool = True):
        super().__init__(name="news", config={"enabled": enabled})
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.UA})
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self.enabled
    
    # ==================== 个股新闻 ====================
    
    def get_stock_news(self, stock_code: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取个股相关新闻
        
        Args:
            stock_code: 股票代码
            limit: 数量限制
        
        Returns:
            新闻列表
        """
        if not self.enabled:
            return []
        
        try:
            params = {
                "input": stock_code,
                "type": "14",  # 14=个股新闻
                "count": str(limit),
            }
            
            r = self._session.get(self.STOCK_NEWS_URL, params=params, timeout=10)
            d = r.json()
            
            if d.get("QuotationCodeTable") and d["QuotationCodeTable"].get("Data"):
                news_list = []
                for item in d["QuotationCodeTable"]["Data"]:
                    news = {
                        "title": item.get("Title"),
                        "url": item.get("Url"),
                        "time": item.get("ShowTime"),
                        "source": item.get("SourceName"),
                    }
                    news_list.append(news)
                
                return news_list
                
        except Exception as e:
            logger.warning(f"[news] 获取个股新闻失败: {e}")
        
        return []
    
    # ==================== 财联社快讯 ====================
    
    def get_cls_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取财联社快讯
        
        Args:
            limit: 数量限制
        
        Returns:
            快讯列表
        """
        if not self.enabled:
            return []
        
        try:
            params = {
                "app": "CailianpressWeb",
                "os": "web",
                "sv": "8.4.6",
                "sign": "",
            }
            
            r = self._session.get(self.CLS_NEWS_URL, params=params, timeout=10)
            d = r.json()
            
            if d.get("data") and d["data"].get("roll_data"):
                news_list = []
                for item in d["data"]["roll_data"][:limit]:
                    news = {
                        "title": item.get("title"),
                        "content": item.get("content"),
                        "time": item.get("ctime"),
                        "source": "财联社",
                    }
                    news_list.append(news)
                
                return news_list
                
        except Exception as e:
            logger.warning(f"[news] 获取财联社快讯失败: {e}")
        
        return []
    
    # ==================== 巨潮公告 ====================
    
    def get_announcements(self, stock_code: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取巨潮公告
        
        Args:
            stock_code: 股票代码
            limit: 数量限制
        
        Returns:
            公告列表
        """
        if not self.enabled:
            return []
        
        try:
            # 先获取orgId
            search_params = {
                "keyWord": stock_code,
                "maxNum": "10",
            }

            r = self._session.post(self.CNINFO_URL, data=search_params, timeout=10)
            d = r.json()

            # 巨潮搜索API直接返回列表
            if isinstance(d, list) and len(d) > 0:
                company = d[0]
            elif isinstance(d, dict) and d.get("data"):
                company = d["data"][0]
            else:
                return []

            # 提取orgId
            if isinstance(company, dict):
                org_id = company.get("orgId")
            elif isinstance(company, list):
                org_id = company[0] if len(company) > 0 else None
            else:
                org_id = None

            if not org_id:
                logger.debug(f"[news] 未获取到orgId: {stock_code}")
                return []
            
            # 获取公告
            announce_params = {
                "pageNum": "1",
                "pageSize": str(limit),
                "tabName": "fulltext",
                "column": "sse" if stock_code.startswith("6") else "szse",
                "stock": stock_code,
                "searchkey": "",
                "secid": "",
                "plate": "sh" if stock_code.startswith("6") else "sz",
                "category": "category_all",
                "trade": "",
                "columnTitle": "历年公告",
                "orgId": org_id,
            }
            
            r = self._session.post(self.CNINFO_ANNOUNCE_URL, data=announce_params, timeout=10)
            d = r.json()
            
            if d.get("announcements"):
                announcements = []
                for item in d["announcements"]:
                    ann = {
                        "title": item.get("announcementTitle"),
                        "time": item.get("announcementTime"),
                        "type": item.get("announcementType"),
                        "url": f"http://static.cninfo.com.cn/{item.get('adjunctUrl')}",
                    }
                    announcements.append(ann)
                
                return announcements
                
        except Exception as e:
            logger.warning(f"[news] 获取公告失败: {e}")
        
        return []
    
    # ==================== BaseClient接口实现 ====================

    def fetch_kline(
        self,
        stock_code: str,
        days: int = 250,
        freq: str = "daily"
    ) -> Optional[List[StockPrice]]:
        """获取K线数据

        新闻客户端不提供K线数据，返回None

        Args:
            stock_code: 股票代码（如 600519.SH）
            days: 获取天数
            freq: 频率 daily/weekly

        Returns:
            None
        """
        return None

    def fetch_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取实时行情

        新闻客户端不提供行情数据，返回None

        Args:
            stock_code: 股票代码

        Returns:
            None
        """
        return None

    def fetch_financial_reports(self, stock_code: str) -> Optional[List[FinancialReport]]:
        """获取财务报告

        新闻客户端不提供财务数据，返回None

        Args:
            stock_code: 股票代码

        Returns:
            None
        """
        return None
