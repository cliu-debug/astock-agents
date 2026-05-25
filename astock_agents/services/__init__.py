"""投资系统服务层 - 选股、自选股、模拟交易、复盘、回测、组合风险分析"""

from astock_agents.services.screener import StockScreener
from astock_agents.services.watchlist import WatchlistManager
from astock_agents.services.paper_trading import PaperTradingService
from astock_agents.services.review import ReviewService
from astock_agents.services.backtest import BacktestEngine
from astock_agents.services.portfolio_risk import PortfolioRiskAnalyzer

__all__ = [
    "StockScreener",
    "WatchlistManager",
    "PaperTradingService",
    "ReviewService",
    "BacktestEngine",
    "PortfolioRiskAnalyzer",
]
