"""数据管理器 - 整合所有数据源

基于 a-stock-data 的多数据源管理
提供统一的数据获取接口，自动优先级和降级
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from astock_agents.models import StockData, StockPrice
from astock_agents.data.tencent_client_enhanced import TencentClientEnhanced
from astock_agents.data.eastmoney_client import EastmoneyClient
from astock_agents.data.tonghuashun_client import TonghuashunClient
from astock_agents.data.baidu_client import BaiduClient
from astock_agents.data.news_client import NewsClient


class DataManager:
    """数据管理器 - 整合 a-stock-data 所有数据源
    
    数据源优先级:
    1. 腾讯财经 - PE/PB/市值/换手率/涨跌停 (实时，不封IP)
    2. 东方财富 - 研报/龙虎榜/资金流向/融资融券
    3. 同花顺 - 热点强势股/北向资金/行业排名
    4. 百度股市通 - K线(带MA)/概念板块
    5. 新闻公告 - 个股新闻/财联社/巨潮公告
    """
    
    def __init__(
        self,
        use_tencent: bool = True,
        use_eastmoney: bool = True,
        use_tonghuashun: bool = True,
        use_baidu: bool = True,
        use_news: bool = True,
    ):
        """初始化数据管理器
        
        Args:
            use_tencent: 启用腾讯财经
            use_eastmoney: 启用东方财富
            use_tonghuashun: 启用同花顺
            use_baidu: 启用百度股市通
            use_news: 启用新闻公告
        """
        logger.info("初始化数据管理器...")
        
        # 初始化所有数据源
        self.tencent = TencentClientEnhanced(enabled=use_tencent)
        self.eastmoney = EastmoneyClient(enabled=use_eastmoney)
        self.tonghuashun = TonghuashunClient(enabled=use_tonghuashun)
        self.baidu = BaiduClient(enabled=use_baidu)
        self.news = NewsClient(enabled=use_news)
        
        # 数据源列表（按优先级）
        self._clients = [
            ("tencent", self.tencent),
            ("eastmoney", self.eastmoney),
            ("tonghuashun", self.tonghuashun),
            ("baidu", self.baidu),
            ("news", self.news),
        ]
        
        logger.success("数据管理器初始化完成")
    
    def get_stock_data(self, stock_code: str, stock_name: Optional[str] = None) -> Optional[StockData]:
        """获取完整股票数据（整合所有数据源）
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称（可选）
        
        Returns:
            StockData对象
        """
        logger.info(f"[DataManager] 获取股票数据: {stock_code}")
        
        # 标准化代码
        code = stock_code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        
        # 创建StockData对象
        stock = StockData(
            stock_code=stock_code,
            stock_name=stock_name or code,
        )
        
        # 1. 获取基础行情（腾讯）
        self._fetch_basic_quote(stock, code)
        
        # 2. 获取K线数据（百度）
        self._fetch_kline_data(stock, code)
        
        # 3. 获取研报数据（东财）
        self._fetch_report_data(stock, code)
        
        # 4. 获取热点和概念（同花顺+百度）
        self._fetch_concept_data(stock, code)
        
        # 5. 获取新闻公告
        self._fetch_news_data(stock, code)
        
        logger.success(f"[DataManager] {stock_code} 数据获取完成")
        return stock
    
    def _fetch_basic_quote(self, stock: StockData, code: str):
        """获取基础行情数据"""
        try:
            quote = self.tencent.get_batch_quotes([code])
            if quote and code in quote:
                data = quote[code]
                stock.stock_name = data.get("name", stock.stock_name)
                stock.pe_ttm = data.get("pe_ttm")
                stock.pb = data.get("pb")
                stock.market_cap = data.get("mcap_yi")
                
                # 添加最新价格
                if data.get("price"):
                    stock.prices.append(StockPrice(
                        date=datetime.now(),
                        open=data.get("open", 0),
                        high=data.get("high", 0),
                        low=data.get("low", 0),
                        close=data.get("price", 0),
                        volume=0,  # 腾讯不提供成交量
                    ))
                
                logger.debug(f"[DataManager] 腾讯数据: PE={stock.pe_ttm}, PB={stock.pb}")
        except Exception as e:
            logger.warning(f"[DataManager] 获取腾讯数据失败: {e}")
    
    def _fetch_kline_data(self, stock: StockData, code: str):
        """获取K线数据"""
        try:
            klines = self.baidu.get_kline_with_ma(code)
            if klines and klines.get("rows"):
                keys = klines.get("keys", [])
                rows = klines.get("rows", [])
                
                for row in rows[-250:]:  # 最近250天
                    if not row:
                        continue
                    
                    values = row.split(",")
                    if len(values) < len(keys):
                        continue
                    
                    # 构建价格数据
                    price_data = {}
                    for i, key in enumerate(keys):
                        if i < len(values):
                            try:
                                price_data[key] = float(values[i]) if "." in values[i] else int(values[i])
                            except (ValueError, TypeError):
                                price_data[key] = values[i]
                    
                    # 解析时间
                    time_str = str(price_data.get("time", ""))
                    if len(time_str) >= 8:
                        try:
                            date = datetime.strptime(time_str[:8], "%Y%m%d")
                        except (ValueError, TypeError):
                            date = datetime.now()
                    else:
                        date = datetime.now()
                    
                    stock.prices.append(StockPrice(
                        date=date,
                        open=price_data.get("open", 0),
                        high=price_data.get("high", 0),
                        low=price_data.get("low", 0),
                        close=price_data.get("close", 0),
                        volume=price_data.get("volume", 0),
                    ))
                
                logger.debug(f"[DataManager] K线数据: {len(stock.prices)}条")
        except Exception as e:
            logger.warning(f"[DataManager] 获取K线数据失败: {e}")
    
    def _fetch_report_data(self, stock: StockData, code: str):
        """获取研报数据"""
        try:
            reports = self.eastmoney.get_reports(code, max_pages=1)
            if reports:
                latest = reports[0]
                logger.debug(f"[DataManager] 研报数据: {len(reports)}篇, 最新评级={latest.get('emRatingName')}")
        except Exception as e:
            logger.warning(f"[DataManager] 获取研报数据失败: {e}")
    
    def _fetch_concept_data(self, stock: StockData, code: str):
        """获取概念板块数据"""
        try:
            concept = self.baidu.get_concept_blocks(code)
            if concept:
                stock.industry = ", ".join(concept.get("industry", [])) if concept.get("industry") else None
                logger.debug(f"[DataManager] 概念板块: {stock.industry}")
        except Exception as e:
            logger.warning(f"[DataManager] 获取概念数据失败: {e}")
    
    def _fetch_news_data(self, stock: StockData, code: str):
        """获取新闻公告数据"""
        # 获取新闻数据并写入 stock.recent_news
        try:
            news = self.news.get_stock_news(code, limit=5)
            if news:
                stock.recent_news = news
            logger.debug(f"[DataManager] 新闻数据: {len(news) if news else 0}条")
        except Exception as e:
            logger.warning(f"[DataManager] 获取新闻数据失败: {e}")

        # 获取公告数据并写入 stock.recent_announcements
        try:
            announcements = self.news.get_announcements(code, limit=5)
            if announcements:
                stock.recent_announcements = announcements
            logger.debug(f"[DataManager] 公告数据: {len(announcements) if announcements else 0}条")
        except Exception as e:
            logger.warning(f"[DataManager] 获取公告数据失败: {e}")
    
    # ==================== 特色数据接口 ====================
    
    def get_hot_stocks(self) -> List[Dict[str, Any]]:
        """获取热点强势股"""
        return self.tonghuashun.get_hot_stocks()
    
    def get_north_bound_flow(self, market: str = "sh") -> Optional[Dict[str, Any]]:
        """获取北向资金流向"""
        return self.tonghuashun.get_north_bound_flow(market)
    
    def get_industry_ranking(self) -> List[Dict[str, Any]]:
        """获取行业板块排名"""
        return self.tonghuashun.get_industry_ranking()
    
    def get_dragon_tiger(self, stock_code: str) -> List[Dict[str, Any]]:
        """获取龙虎榜数据"""
        code = stock_code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        return self.eastmoney.get_dragon_tiger(code)
    
    def get_margin_trading(self, stock_code: str) -> List[Dict[str, Any]]:
        """获取融资融券数据"""
        code = stock_code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        return self.eastmoney.get_margin_trading(code)
    
    def get_fund_flow(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取资金流向"""
        code = stock_code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        return self.eastmoney.get_fund_flow(code)
    
    def get_concept_blocks(self, stock_code: str) -> Dict[str, Any]:
        """获取概念板块归属"""
        code = stock_code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        return self.baidu.get_concept_blocks(code)
    
    def get_announcements(self, stock_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取公告"""
        code = stock_code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        return self.news.get_announcements(code, limit)
    
    def get_stock_news(self, stock_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取个股新闻"""
        code = stock_code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        return self.news.get_stock_news(code, limit)
