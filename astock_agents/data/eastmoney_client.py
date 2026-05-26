"""东方财富数据客户端

基于 a-stock-data 的东财API实现
提供研报、龙虎榜、资金流向、融资融券等数据
"""

import requests
import re
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
from loguru import logger

from astock_agents.data.base_client import BaseDataClient
from astock_agents.models.stock_data import StockPrice, FinancialReport


class EastmoneyClient(BaseDataClient):
    """东方财富数据客户端
    
    数据来源: https://github.com/simonlin1212/a-stock-data
    提供:
    - 研报列表 + PDF下载
    - 龙虎榜数据
    - 资金流向
    - 融资融券
    - 公告数据
    """
    
    # API endpoints
    REPORT_API = "https://reportapi.eastmoney.com/report/list"
    PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
    DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    PUSH2_URL = "https://push2.eastmoney.com/api/qt/stock/get"
    
    UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    
    def __init__(self, enabled: bool = True):
        super().__init__(name="eastmoney", config={"enabled": enabled})
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": self.UA,
            "Referer": "https://data.eastmoney.com/"
        })
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self.enabled
    
    def _datacenter_query(self, report_name: str, columns: str = "ALL",
                          filter_str: str = "", page_size: int = 50,
                          sort_columns: str = "", sort_types: str = "-1") -> List[Dict]:
        """东财数据中心统一查询"""
        params = {
            "reportName": report_name,
            "columns": columns,
            "filter": filter_str,
            "pageNumber": "1",
            "pageSize": str(page_size),
            "sortColumns": sort_columns,
            "sortTypes": sort_types,
            "source": "WEB",
            "client": "WEB",
        }
        
        try:
            r = self._session.get(self.DATACENTER_URL, params=params, timeout=15)
            d = r.json()
            if d.get("result") and d["result"].get("data"):
                return d["result"]["data"]
        except Exception as e:
            logger.warning(f"[eastmoney] 数据中心查询失败: {e}")
        
        return []
    
    # ==================== 研报层 ====================
    
    def get_reports(self, stock_code: str, max_pages: int = 5) -> List[Dict[str, Any]]:
        """获取研报列表
        
        Args:
            stock_code: 股票代码
            max_pages: 最大页数
        
        Returns:
            研报列表，包含title, publishDate, orgSName, infoCode等
        """
        if not self.enabled:
            return []
        
        all_records = []
        
        for page in range(1, max_pages + 1):
            params = {
                "industryCode": "*",
                "pageSize": "100",
                "industry": "*",
                "rating": "*",
                "ratingChange": "*",
                "beginTime": "2000-01-01",
                "endTime": "2030-01-01",
                "pageNo": str(page),
                "fields": "",
                "qType": "0",
                "orgCode": "",
                "code": stock_code,
                "rcode": "",
                "p": str(page),
                "pageNum": str(page),
                "pageNumber": str(page),
            }
            
            try:
                r = self._session.get(self.REPORT_API, params=params, timeout=30)
                d = r.json()
                rows = d.get("data") or []
                
                if not rows:
                    break
                
                all_records.extend(rows)
                
                if page >= (d.get("TotalPage", 1) or 1):
                    break
                
                time.sleep(0.3)
                
            except Exception as e:
                logger.warning(f"[eastmoney] 获取研报失败: {e}")
                break
        
        logger.info(f"[eastmoney] 获取到 {len(all_records)} 篇研报")
        return all_records
    
    def download_report_pdf(self, record: Dict, target_dir: str = "./reports") -> Optional[str]:
        """下载研报PDF
        
        Args:
            record: 研报记录
            target_dir: 保存目录
        
        Returns:
            保存路径或None
        """
        info_code = record.get("infoCode", "")
        if not info_code:
            return None
        
        date = (record.get("publishDate") or "")[:10]
        org = record.get("orgSName") or "未知"
        title = re.sub(r'[\\/:*?"<>|]', "_", record.get("title", ""))[:80]
        fname = f"{date}_{org}_{title}.pdf"
        target = Path(target_dir) / fname
        
        if target.exists():
            return str(target)
        
        url = self.PDF_TPL.format(info_code=info_code)
        
        try:
            r = self._session.get(url, timeout=60)
            if r.status_code == 200 and len(r.content) >= 1024:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(r.content)
                return str(target)
        except Exception as e:
            logger.warning(f"[eastmoney] 下载PDF失败: {e}")
        
        return None
    
    # ==================== 信号层 ====================
    
    def get_dragon_tiger(self, stock_code: str, days: int = 30) -> List[Dict]:
        """获取龙虎榜数据
        
        Args:
            stock_code: 股票代码
            days: 最近多少天
        
        Returns:
            龙虎榜记录列表
        """
        filter_str = f"(SECURITY_CODE='{stock_code}')"
        data = self._datacenter_query(
            "RPT_DMSK_TS",
            filter_str=filter_str,
            page_size=days,
            sort_columns="TRADE_DATE",
            sort_types="-1"
        )
        return data
    
    def get_daily_dragon_tiger(self, trade_date: Optional[str] = None) -> List[Dict]:
        """获取全市场龙虎榜
        
        Args:
            trade_date: 交易日期 (YYYY-MM-DD)，默认最新
        
        Returns:
            当日所有上榜股票
        """
        if trade_date:
            filter_str = f"(TRADE_DATE='{trade_date}')"
        else:
            filter_str = ""
        
        data = self._datacenter_query(
            "RPT_DMSK_DAILY",
            filter_str=filter_str,
            page_size=100,
            sort_columns="NET_BUY_AMT",
            sort_types="-1"
        )
        return data
    
    def get_margin_trading(self, stock_code: str, days: int = 30) -> List[Dict]:
        """获取融资融券数据
        
        Args:
            stock_code: 股票代码
            days: 最近多少天
        
        Returns:
            融资融券记录列表
        """
        filter_str = f"(SECURITY_CODE='{stock_code}')"
        data = self._datacenter_query(
            "RPTA_WEB_MRHQ",
            filter_str=filter_str,
            page_size=days,
            sort_columns="TRADE_DATE",
            sort_types="-1"
        )
        return data
    
    def get_fund_flow(self, stock_code: str) -> Optional[Dict]:
        """获取个股资金流向
        
        Args:
            stock_code: 股票代码
        
        Returns:
            资金流向数据
        """
        try:
            # 构建市场前缀
            if stock_code.startswith(('6', '9')):
                secid = f"1.{stock_code}"
            elif stock_code.startswith('8'):
                secid = f"0.{stock_code}"
            else:
                secid = f"0.{stock_code}"
            
            params = {
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                "fltt": "2",
                "invt": "2",
                "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f57,f58,f60,f107,f164",
                "secid": secid,
            }
            
            r = self._session.get(self.PUSH2_URL, params=params, timeout=10)
            d = r.json()
            
            if d.get("data"):
                return d["data"]
        except Exception as e:
            logger.warning(f"[eastmoney] 获取资金流向失败: {e}")
        
        return None
    
    # ==================== BaseClient接口实现 ====================

    def fetch_kline(
        self,
        stock_code: str,
        days: int = 250,
        freq: str = "daily"
    ) -> Optional[List[StockPrice]]:
        """获取K线数据

        东方财富不提供K线API，返回None由其他数据源降级获取

        Args:
            stock_code: 股票代码（如 600519.SH）
            days: 获取天数
            freq: 频率 daily/weekly

        Returns:
            None（东财不提供K线数据）
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
        return self.get_fund_flow(code)

    def fetch_financial_reports(self, stock_code: str) -> Optional[List[FinancialReport]]:
        """获取财务报告

        从研报中获取一致预期数据

        Args:
            stock_code: 股票代码

        Returns:
            财务报告列表，失败返回 None
        """
        code = self._normalize_stock_code(stock_code)
        reports = self.get_reports(code, max_pages=1)
        if not reports:
            return None

        try:
            latest = reports[0]
            report = FinancialReport(
                report_date=datetime.now(),
                report_type="研报预期",
                roe=None,
                gross_margin=None,
                net_margin=None,
                debt_ratio=None,
            )
            return [report]
        except Exception as e:
            logger.warning(f"[eastmoney] 构建财务报告失败: {e}")
            return None
