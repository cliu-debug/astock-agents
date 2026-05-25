"""
AStockAgents Web界面

基于FastAPI的交互式分析界面，接入核心工作流引擎
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import yaml
import asyncio
from loguru import logger

from astock_agents.web.auth import auth_middleware, generate_jwt_token, is_auth_enabled
from astock_agents.web.validators import validate_stock_code, validate_quantity, validate_price

# 创建限流器实例
limiter = Limiter(key_func=get_remote_address)

# 创建FastAPI应用
app = FastAPI(
    title="AStockAgents",
    description="多智能体协同股票分析系统",
    version="1.0.0"
)

# 将限流器绑定到应用状态
app.state.limiter = limiter


# 限流超出异常处理器
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """处理限流超出异常，返回429状态码"""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "请求过于频繁，请稍后再试",
            "retry_after": exc.detail,
        },
    )


# CORS配置 - 收紧为合理范围
ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 认证中间件（在CORS之后添加）
app.middleware("http")(auth_middleware)

# 延迟初始化工作流（避免导入时连接数据源）
_workflow = None

# 当前文件所在目录（兼容 python -m 启动方式）
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_config() -> Dict[str, Any]:
    """加载配置文件"""
    config_path = os.environ.get("ASTOCK_CONFIG", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _get_workflow():
    """懒加载工作流实例"""
    global _workflow
    if _workflow is None:
        try:
            from astock_agents.workflow.analysis_workflow import AnalysisWorkflow
            config = _load_config()
            _workflow = AnalysisWorkflow(config=config)
            logger.info("[Web] 工作流引擎初始化完成")
        except Exception as e:
            logger.error(f"[Web] 工作流引擎初始化失败: {e}")
            raise
    return _workflow


# ==================== 数据模型 ====================

class AnalysisRequest(BaseModel):
    """分析请求"""
    stock_code: str = Field(..., description="股票代码，如 600519.SH")
    stock_name: Optional[str] = Field(None, description="股票名称")
    days: Optional[int] = Field(120, description="分析天数")


class AnalysisResponse(BaseModel):
    """分析响应"""
    stock_code: str
    stock_name: str
    current_price: Optional[float] = None
    final_signal: Optional[str] = None
    final_confidence: Optional[int] = None
    technical_analysis: Optional[Dict[str, Any]] = None
    fundamental_analysis: Optional[Dict[str, Any]] = None
    sentiment_analysis: Optional[Dict[str, Any]] = None
    news_analysis: Optional[Dict[str, Any]] = None
    debate: Optional[Dict[str, Any]] = None
    trade_proposal: Optional[Dict[str, Any]] = None
    risk_assessment: Optional[Dict[str, Any]] = None
    price_data: Optional[List[Dict[str, Any]]] = None
    full_report: Optional[str] = None
    timestamp: str


class BacktestSignal(BaseModel):
    """回测交易信号"""
    date: str = Field(..., description="交易日期，格式 YYYY-MM-DD")
    action: str = Field(..., description="交易动作: buy / sell")


class BacktestRequest(BaseModel):
    """回测请求"""
    stock_code: str = Field(..., description="股票代码，如 600519.SH")
    strategy_name: str = Field("自定义策略", description="策略名称")
    signals: List[BacktestSignal] = Field(..., description="交易信号列表")
    position_size_pct: float = Field(0.2, description="每次开仓占总资金比例")
    stop_loss_pct: float = Field(0.07, description="止损比例")
    take_profit_pct: float = Field(0.15, description="止盈比例")


# ==================== API路由 ====================

@app.get("/", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def root(request: Request):
    """返回主页"""
    html_path = os.path.join(_CURRENT_DIR, "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(
        "<h1>AStockAgents</h1>"
        "<p>API文档: <a href='/docs'>/docs</a></p>"
        "<p>分析接口: POST /api/analyze</p>"
    )


@app.get("/api/health")
async def health_check(request: Request):
    """健康检查 - 包含断路器状态"""
    from astock_agents.data.circuit_breaker import get_all_circuit_breaker_stats

    cb_stats = get_all_circuit_breaker_stats()
    open_breakers = [name for name, stats in cb_stats.items() if stats["state"] == "OPEN"]
    healthy = len(open_breakers) == 0

    return {
        "status": "healthy" if healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "workflow_ready": _workflow is not None,
        "circuit_breakers": cb_stats,
        "open_breakers": open_breakers,
    }


@app.get("/api/system/circuit-breakers")
@limiter.limit("30/minute")
async def get_circuit_breakers(request: Request):
    """获取所有断路器状态"""
    from astock_agents.data.circuit_breaker import get_all_circuit_breaker_stats
    return {"circuit_breakers": get_all_circuit_breaker_stats()}


# ==================== 认证API ====================

class TokenRequest(BaseModel):
    """Token请求"""
    api_key: str = Field(..., description="API Key")


class TokenResponse(BaseModel):
    """Token响应"""
    token: str = Field(..., description="JWT Token")
    expires_in: int = Field(..., description="有效期（秒）")


@app.post("/api/auth/token", response_model=TokenResponse)
@limiter.limit("10/minute")
async def get_token(request: Request, body: TokenRequest):
    """
    获取JWT Token

    通过API Key换取JWT Token，后续请求使用Bearer Token认证。
    限流: 每分钟10次请求
    """
    if not is_auth_enabled():
        raise HTTPException(status_code=400, detail="认证未启用，无需获取Token")

    try:
        token = generate_jwt_token(body.api_key)
        return TokenResponse(
            token=token,
            expires_in=24 * 3600,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="API Key无效")


@app.post("/api/analyze", response_model=AnalysisResponse)
@limiter.limit("5/minute")
async def analyze_stock(request: Request, body: AnalysisRequest):
    """
    分析股票 - 调用核心工作流引擎

    执行完整的多智能体协同分析流程
    限流: 每分钟5次请求
    """
    try:
        # 验证股票代码格式
        validated_code = validate_stock_code(body.stock_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        workflow = _get_workflow()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"工作流引擎不可用: {str(e)}")

    try:
        # 在线程池中执行同步的工作流分析，避免阻塞事件循环
        loop = asyncio.get_event_loop()
        report = await loop.run_in_executor(
            None,
            lambda: workflow.analyze(
                stock_code=validated_code,
                stock_name=body.stock_name
            )
        )

        # 构建响应
        # 提取价格数据用于K线图
        price_data = None
        if report.technical and hasattr(report, 'stock_data_ref'):
            stock_ref = report.stock_data_ref
            if stock_ref and stock_ref.prices:
                price_data = [
                    {
                        "date": p.date.strftime("%Y-%m-%d"),
                        "open": p.open,
                        "high": p.high,
                        "low": p.low,
                        "close": p.close,
                        "volume": p.volume,
                    }
                    for p in stock_ref.prices[-120:]
                ]

        response = AnalysisResponse(
            stock_code=report.stock_code,
            stock_name=report.stock_name,
            current_price=report.current_price,
            final_signal=report.final_signal.value if report.final_signal else None,
            final_confidence=report.final_confidence,
            technical_analysis=report.technical.model_dump() if report.technical else None,
            fundamental_analysis=report.fundamental.model_dump() if report.fundamental else None,
            sentiment_analysis=report.sentiment.model_dump() if report.sentiment else None,
            news_analysis=report.news.model_dump() if report.news else None,
            debate=report.debate.model_dump() if report.debate else None,
            trade_proposal=report.trade_proposal.model_dump() if report.trade_proposal else None,
            risk_assessment=report.risk_assessment.model_dump() if report.risk_assessment else None,
            price_data=price_data,
            full_report=report.full_report,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        return response

    except Exception as e:
        logger.error(f"[Web] 分析失败: {body.stock_code}, {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@app.get("/api/analyze")
@limiter.limit("5/minute")
async def analyze_stock_get(request: Request, stock_code: str, stock_name: Optional[str] = None):
    """GET方式分析股票（便捷接口） - 限流: 每分钟5次"""
    body = AnalysisRequest(stock_code=stock_code, stock_name=stock_name)
    return await analyze_stock(request, body)


@app.get("/api/stocks/popular")
@limiter.limit("30/minute")
async def get_popular_stocks(request: Request):
    """获取热门股票列表 - 限流: 每分钟30次"""
    return {
        "stocks": [
            {"code": "600519.SH", "name": "贵州茅台", "industry": "白酒"},
            {"code": "000858.SZ", "name": "五粮液", "industry": "白酒"},
            {"code": "000001.SZ", "name": "平安银行", "industry": "银行"},
            {"code": "600036.SH", "name": "招商银行", "industry": "银行"},
            {"code": "000333.SZ", "name": "美的集团", "industry": "家电"},
            {"code": "600276.SH", "name": "恒瑞医药", "industry": "医药"},
        ]
    }


# ==================== 投资系统API ====================

# 全局服务实例
_screener = None
_watchlist = None
_paper_trading = None
_review = None


def _get_screener():
    """懒加载选股器"""
    global _screener
    if _screener is None:
        from astock_agents.services.screener import StockScreener
        _screener = StockScreener()
    return _screener


def _get_watchlist():
    """懒加载自选股管理器"""
    global _watchlist
    if _watchlist is None:
        from astock_agents.services.watchlist import WatchlistManager
        _watchlist = WatchlistManager()
    return _watchlist


def _get_paper_trading():
    """懒加载模拟交易"""
    global _paper_trading
    if _paper_trading is None:
        from astock_agents.services.paper_trading import PaperTradingService
        _paper_trading = PaperTradingService()
    return _paper_trading


def _get_review():
    """懒加载复盘服务"""
    global _review
    if _review is None:
        from astock_agents.services.review import ReviewService
        _review = ReviewService()
    return _review


_backtest_engine = None


def _get_backtest_engine():
    """懒加载回测引擎"""
    global _backtest_engine
    if _backtest_engine is None:
        from astock_agents.services.backtest import BacktestEngine
        _backtest_engine = BacktestEngine()
    return _backtest_engine


_data_manager = None


def _get_data_manager():
    """懒加载数据管理器"""
    global _data_manager
    if _data_manager is None:
        from astock_agents.data.data_manager import DataManager
        _data_manager = DataManager()
    return _data_manager


_macro_analyst = None


def _get_macro_analyst():
    """懒加载宏观分析师"""
    global _macro_analyst
    if _macro_analyst is None:
        from astock_agents.agents.macro_analyst import MacroAnalyst
        _macro_analyst = MacroAnalyst()
    return _macro_analyst


_portfolio_risk_analyzer = None


def _get_portfolio_risk_analyzer():
    """懒加载投资组合风险分析器"""
    global _portfolio_risk_analyzer
    if _portfolio_risk_analyzer is None:
        from astock_agents.services.portfolio_risk import PortfolioRiskAnalyzer
        _portfolio_risk_analyzer = PortfolioRiskAnalyzer()
    return _portfolio_risk_analyzer


# ---------- 选股器 ----------

@app.get("/api/screener/presets")
@limiter.limit("30/minute")
async def get_screener_presets(request: Request):
    """获取选股预设方案列表"""
    screener = _get_screener()
    presets = screener.get_presets()
    return {"presets": [p.model_dump() for p in presets]}


@app.post("/api/screener/scan")
@limiter.limit("5/minute")
async def screener_scan(request: Request, body: Optional[Dict[str, Any]] = None):
    """执行选股扫描"""
    screener = _get_screener()
    body = body or {}

    preset_name = body.get("preset_name")
    conditions = body.get("conditions")

    if conditions:
        from astock_agents.models.portfolio import ScreenerCondition
        conditions = [ScreenerCondition(**c) for c in conditions]

    result = screener.scan(preset_name=preset_name, conditions=conditions)
    return result.model_dump()


# ---------- 自选股 ----------

@app.get("/api/watchlist")
@limiter.limit("30/minute")
async def get_watchlist(request: Request, group: Optional[str] = None):
    """获取自选股列表"""
    wl = _get_watchlist()
    from astock_agents.models.portfolio import WatchlistGroup
    group_enum = None
    if group:
        try:
            group_enum = WatchlistGroup(group)
        except ValueError:
            pass
    items = wl.get_all(group=group_enum)
    return {"items": [i.model_dump() for i in items], "total": len(items)}


@app.post("/api/watchlist/add")
@limiter.limit("10/minute")
async def add_to_watchlist(request: Request, body: Dict[str, Any]):
    """添加自选股"""
    from astock_agents.models.portfolio import WatchlistItem
    wl = _get_watchlist()
    item = WatchlistItem(**body)
    success = wl.add(item)
    if not success:
        raise HTTPException(status_code=409, detail="该股票已在自选列表中")
    return {"success": True, "message": f"已添加 {item.stock_name}"}


@app.delete("/api/watchlist/{stock_code}")
@limiter.limit("10/minute")
async def remove_from_watchlist(request: Request, stock_code: str):
    """移除自选股"""
    wl = _get_watchlist()
    success = wl.remove(stock_code)
    if not success:
        raise HTTPException(status_code=404, detail="未找到该股票")
    return {"success": True}


@app.get("/api/watchlist/groups")
@limiter.limit("30/minute")
async def get_watchlist_groups(request: Request):
    """获取自选股分组"""
    wl = _get_watchlist()
    groups = wl.get_groups()
    return {"groups": [g.model_dump() for g in groups]}


# ---------- 模拟交易 ----------

@app.get("/api/trading/portfolio")
@limiter.limit("30/minute")
async def get_portfolio(request: Request):
    """获取投资组合"""
    pt = _get_paper_trading()
    portfolio = pt.get_portfolio()
    return portfolio.model_dump()


@app.post("/api/trading/order")
@limiter.limit("10/minute")
async def place_order(request: Request, body: Dict[str, Any]):
    """下单"""
    from astock_agents.models.portfolio import TradeDirection, OrderType
    pt = _get_paper_trading()

    # 验证股票代码
    try:
        validated_code = validate_stock_code(body.get("stock_code", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 验证交易数量
    try:
        validated_quantity = validate_quantity(body.get("quantity", 100))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 验证价格
    try:
        validated_price = validate_price(body.get("price"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        direction = TradeDirection(body.get("direction", "买入"))
        order_type = OrderType(body.get("order_type", "市价单"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"参数错误: {e}")

    order = pt.place_order(
        stock_code=validated_code,
        stock_name=body.get("stock_name", ""),
        direction=direction,
        quantity=validated_quantity,
        order_type=order_type,
        price=validated_price,
        reason=body.get("reason"),
        signal_source=body.get("signal_source"),
    )

    if order.status.value == "已取消":
        raise HTTPException(status_code=400, detail="下单失败：资金不足或持仓不足")

    return order.model_dump()


@app.get("/api/trading/orders")
@limiter.limit("30/minute")
async def get_orders(request: Request, limit: int = 50):
    """获取交易订单"""
    pt = _get_paper_trading()
    orders = pt.get_orders(limit=limit)
    return {"orders": [o.model_dump() for o in orders]}


@app.get("/api/trading/history")
@limiter.limit("30/minute")
async def get_trade_history(request: Request):
    """获取交易历史"""
    pt = _get_paper_trading()
    return {"history": pt.get_trade_history()}


# ---------- 交易复盘 ----------

@app.get("/api/review/report")
@limiter.limit("10/minute")
async def get_review_report(request: Request, period: Optional[str] = None):
    """获取复盘报告"""
    review = _get_review()
    report = review.generate_report(period=period)
    return report.model_dump()


@app.get("/api/review/records")
@limiter.limit("30/minute")
async def get_review_records(request: Request, status: Optional[str] = None):
    """获取交易记录"""
    review = _get_review()
    records = review.get_records(status=status)
    return {"records": [r.model_dump() for r in records]}


# ---------- 回测引擎 ----------

@app.post("/api/backtest/run")
@limiter.limit("5/minute")
async def run_backtest(request: Request, body: BacktestRequest):
    """
    执行回测

    基于历史数据和交易信号模拟交易，计算策略收益和风险指标。
    限流: 每分钟5次请求

    请求体示例:
    {
        "stock_code": "600519.SH",
        "strategy_name": "均线策略",
        "signals": [
            {"date": "2024-01-15", "action": "buy"},
            {"date": "2024-02-20", "action": "sell"}
        ],
        "position_size_pct": 0.2,
        "stop_loss_pct": 0.07,
        "take_profit_pct": 0.15
    }
    """
    # 验证股票代码格式
    try:
        validated_code = validate_stock_code(body.stock_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 验证交易信号
    if not body.signals:
        raise HTTPException(status_code=400, detail="交易信号列表不能为空")

    for sig in body.signals:
        if sig.action not in ("buy", "sell"):
            raise HTTPException(
                status_code=400,
                detail=f"无效的交易动作: {sig.action}，仅支持 buy/sell"
            )

    # 获取股票历史数据
    try:
        dm = _get_data_manager()
        stock_data = dm.get_stock_data(validated_code)
    except Exception as e:
        logger.error(f"[Web] 回测获取数据失败: {validated_code}, {e}")
        raise HTTPException(status_code=503, detail=f"获取股票数据失败: {str(e)}")

    if not stock_data or not stock_data.prices:
        raise HTTPException(status_code=404, detail=f"未找到 {validated_code} 的历史数据")

    # 执行回测
    try:
        engine = _get_backtest_engine()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: engine.run(
                stock_data=stock_data,
                signals=[{"date": s.date, "action": s.action} for s in body.signals],
                strategy_name=body.strategy_name,
                position_size_pct=body.position_size_pct,
                stop_loss_pct=body.stop_loss_pct,
                take_profit_pct=body.take_profit_pct,
            )
        )

        # 将 dataclass 转为可序列化的字典
        from dataclasses import asdict
        return asdict(result)

    except Exception as e:
        logger.error(f"[Web] 回测执行失败: {validated_code}, {e}")
        raise HTTPException(status_code=500, detail=f"回测执行失败: {str(e)}")


# ---------- 宏观分析 ----------

class MacroAnalysisRequest(BaseModel):
    """宏观分析请求"""
    stock_code: str = Field(..., description="股票代码，如 600519.SH")
    stock_name: Optional[str] = Field(None, description="股票名称")
    industry: Optional[str] = Field(None, description="所属行业")
    pe_ttm: Optional[float] = Field(None, description="市盈率TTM")


@app.post("/api/macro/analyze")
@limiter.limit("10/minute")
async def macro_analyze(request: Request, body: MacroAnalysisRequest):
    """
    宏观分析 - 经济周期定位、政策解读、宏观风险评估

    限流: 每分钟10次请求
    """
    try:
        validated_code = validate_stock_code(body.stock_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        from astock_agents.models import StockData
        stock_data = StockData(
            stock_code=validated_code,
            stock_name=body.stock_name or validated_code,
            industry=body.industry,
            pe_ttm=body.pe_ttm,
        )

        analyst = _get_macro_analyst()
        result = analyst.analyze(stock_data)

        # 将Signal枚举转为字符串以便JSON序列化
        if "signal" in result and hasattr(result["signal"], "value"):
            result["signal"] = result["signal"].value

        return {"success": True, "data": result}

    except Exception as e:
        logger.error(f"[Web] 宏观分析失败: {body.stock_code}, {e}")
        raise HTTPException(status_code=500, detail=f"宏观分析失败: {str(e)}")


# ---------- 投资组合风险分析 ----------

@app.get("/api/portfolio/risk")
@limiter.limit("10/minute")
async def portfolio_risk_analysis(request: Request):
    """
    投资组合风险分析 - 集中度风险、行业集中度、再平衡建议

    基于当前模拟交易持仓进行风险分析。
    限流: 每分钟10次请求
    """
    try:
        pt = _get_paper_trading()
        portfolio = pt.get_portfolio()
        positions = portfolio.positions

        analyzer = _get_portfolio_risk_analyzer()
        result = analyzer.analyze(positions)

        return {"success": True, "data": result}

    except Exception as e:
        logger.error(f"[Web] 组合风险分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"组合风险分析失败: {str(e)}")


# ==================== 启动函数 ====================

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """启动Web服务器"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
