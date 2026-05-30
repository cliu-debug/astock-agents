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
import json
import yaml
import asyncio

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from dataclasses import asdict
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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 认证中间件（在CORS之后添加）
app.middleware("http")(auth_middleware)

# 延迟初始化工作流（避免导入时连接数据源）
_workflow = None
_db = None

# 当前文件所在目录（兼容 python -m 启动方式）
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_config() -> Dict[str, Any]:
    """加载配置文件"""
    config_path = os.environ.get("ASTOCK_CONFIG", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _get_db():
    """懒加载数据库实例（单例模式）"""
    global _db
    if _db is None:
        from astock_agents.db.database import Database
        _db = Database()
    return _db


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
    data_sources_used: Optional[Dict[str, str]] = Field(
        default=None, description="各数据类型实际使用的数据源"
    )
    data_sources_unavailable: Optional[List[str]] = Field(
        default=None, description="不可用的数据源列表"
    )
    data_quality_warnings: Optional[List[str]] = Field(
        default=None, description="数据质量警告"
    )
    disclaimer: str = Field(
        default="本系统提供的分析结果仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。",
        description="免责声明"
    )
    risk_notice: Optional[str] = Field(
        default=None, description="针对当前信号的风险提示"
    )


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
    """返回主页 - 生产模式下返回Vue构建产物，开发模式下返回提示"""
    _FRONTEND_DIST = os.path.join(_CURRENT_DIR, "..", "..", "frontend", "dist")
    index_path = os.path.join(_FRONTEND_DIST, "index.html")
    if os.path.exists(index_path) and not os.environ.get("ASTOCK_DEV_MODE"):
        from fastapi.responses import FileResponse
        return FileResponse(index_path)
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


@app.get("/metrics")
@limiter.limit("30/minute")
async def metrics_endpoint(request: Request):
    """Prometheus 指标端点 - 供 Prometheus 拉取"""
    from astock_agents.services.metrics import generate_metrics
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        generate_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


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

    import time as _time
    _start_time = _time.time()

    # 设置智能体状态回调，实时推送到WebSocket
    try:
        from astock_agents.web.websocket import get_connection_manager
        _ws_manager = get_connection_manager()

        def _agent_status_callback(agent_name: str, status: str, message: str):
            """智能体状态回调 - 实时推送到所有WebSocket客户端"""
            try:
                import asyncio as _asyncio
                loop = _asyncio.get_event_loop()
                if loop.is_running():
                    _asyncio.ensure_future(
                        _ws_manager.broadcast({
                            "type": "agent_status",
                            "agent": agent_name,
                            "status": status,
                            "message": message,
                            "stock_code": validated_code,
                            "timestamp": _time.time(),
                        })
                    )
            except Exception:
                pass

        workflow.set_status_callback(_agent_status_callback)
    except Exception:
        pass

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
        # 优先从 stock_data_ref 获取
        if hasattr(report, 'stock_data_ref') and report.stock_data_ref and report.stock_data_ref.prices:
            price_data = [
                {
                    "date": p.date.strftime("%Y-%m-%d"),
                    "open": p.open,
                    "high": p.high,
                    "low": p.low,
                    "close": p.close,
                    "volume": p.volume,
                }
                for p in report.stock_data_ref.prices[-120:]
            ]
        # 降级：从DataManager获取
        elif report.current_price:
            try:
                dm = _get_data_manager()
                stock_info_result = dm.get_stock_data(validated_code)
                stock_info = stock_info_result[0] if isinstance(stock_info_result, tuple) else stock_info_result
                if stock_info and stock_info.prices:
                    price_data = [
                        {
                            "date": p.date.strftime("%Y-%m-%d"),
                            "open": p.open,
                            "high": p.high,
                            "low": p.low,
                            "close": p.close,
                            "volume": p.volume,
                        }
                        for p in stock_info.prices[-120:]
                    ]
            except Exception as e:
                logger.warning(f"[Web] 获取K线数据失败: {e}")

        # 构建合规信息
        from astock_agents.services.compliance import ComplianceGuard, SIGNAL_RISK_NOTICES
        _compliance = ComplianceGuard()
        _signal_value = report.final_signal.value if report.final_signal else None
        _risk_notice = SIGNAL_RISK_NOTICES.get(_signal_value, "ℹ️ 提示：本信号为系统分析结果，不构成投资建议。") if _signal_value else None

        # 构建数据源标注
        _data_sources_used = report.data_sources_used if hasattr(report, 'data_sources_used') else {}
        _data_sources_unavailable = report.data_sources_unavailable if hasattr(report, 'data_sources_unavailable') else []
        _data_quality_warnings = report.data_quality_warnings if hasattr(report, 'data_quality_warnings') else []

        # 补充数据源信息（从断路器状态推断不可用数据源）
        try:
            from astock_agents.data.circuit_breaker import get_all_circuit_breaker_stats
            cb_stats = get_all_circuit_breaker_stats()
            for name, stats in cb_stats.items():
                if stats.get("state") == "OPEN" and name not in _data_sources_unavailable:
                    _data_sources_unavailable.append(name)
        except Exception:
            pass

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
            data_sources_used=_data_sources_used or None,
            data_sources_unavailable=_data_sources_unavailable or None,
            data_quality_warnings=_data_quality_warnings or None,
            risk_notice=_risk_notice,
        )

        # 记录分析指标
        try:
            from astock_agents.services.metrics import get_metrics_collector
            _duration = _time.time() - _start_time
            _signal = report.final_signal.value if report.final_signal else "unknown"
            get_metrics_collector().record_analysis(
                stock_code=validated_code, signal=_signal, duration=_duration
            )
        except Exception:
            pass  # 指标记录不应影响主流程

        # 持久化分析结果到数据库
        try:
            _db = _get_db()
            _db.save_analysis(
                stock_code=validated_code,
                stock_name=report.stock_name,
                signal=report.final_signal.value if report.final_signal else "未知",
                confidence=report.final_confidence or 0,
                report_json=report.model_dump_json(),
            )
        except Exception as e:
            logger.warning(f"[Web] 分析结果持久化失败: {e}")

        # 决策引擎已集成到工作流内部（三层架构：规则为主+LLM补充+风控强制）
        # 从报告的metadata中提取决策信息
        response_dict = response.model_dump()
        if response_dict.get("metadata", {}).get("decision_info"):
            logger.info(
                f"[Web] 混合决策完成: "
                f"来源={response_dict['metadata']['decision_info'].get('decision_source', 'unknown')}"
            )

        return response_dict

    except Exception as e:
        logger.error(f"[Web] 分析失败: {body.stock_code}, {e}")

        # 记录分析错误指标
        try:
            from astock_agents.services.metrics import get_metrics_collector
            get_metrics_collector().record_analysis_error("api_error")
        except Exception:
            pass

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
    """懒加载选股器（注入DataManager实例）"""
    global _screener
    if _screener is None:
        from astock_agents.services.screener import StockScreener
        from astock_agents.data.manager import DataManager
        dm = DataManager()
        _screener = StockScreener(data_manager=dm)
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
    """懒加载复盘服务（注入Database实例）"""
    global _review
    if _review is None:
        from astock_agents.services.review import ReviewService
        from astock_agents.db.database import Database
        db = Database()
        _review = ReviewService(db=db)
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


_decision_engine = None


def _get_decision_engine():
    """懒加载自动决策引擎"""
    global _decision_engine
    if _decision_engine is None:
        from astock_agents.services.decision_engine import DecisionEngine
        _decision_engine = DecisionEngine()
    return _decision_engine


_sector_rotation_analyzer = None


def _get_sector_rotation_analyzer():
    """懒加载行业轮动分析器"""
    global _sector_rotation_analyzer
    if _sector_rotation_analyzer is None:
        from astock_agents.services.sector_rotation import SectorRotationAnalyzer
        _sector_rotation_analyzer = SectorRotationAnalyzer()
    return _sector_rotation_analyzer


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
    portfolio_data = portfolio.model_dump()
    # 字段映射：后端字段名 → 前端期望的字段名
    portfolio_data["cash"] = portfolio_data.pop("available_cash", 0)
    portfolio_data["total_value"] = portfolio_data.pop("total_market_value", 0)
    portfolio_data["total_return_pct"] = portfolio_data.pop("total_pnl_pct", 0)
    return portfolio_data


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
        stock_data_result = dm.get_stock_data(validated_code)
        stock_data = stock_data_result[0] if isinstance(stock_data_result, tuple) else stock_data_result
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
        return asdict(result)

    except Exception as e:
        logger.error(f"[Web] 回测执行失败: {validated_code}, {e}")
        raise HTTPException(status_code=500, detail=f"回测执行失败: {str(e)}")


class StrategyBacktestRequest(BaseModel):
    """策略自动回测请求"""
    stock_code: str = Field(..., description="股票代码")
    strategy_id: str = Field(..., description="策略ID: ma/macd/rsi/boll/kdj/combo")
    strategy_params: Optional[Dict[str, Any]] = Field(default=None, description="策略参数")
    position_size_pct: float = Field(default=0.2, description="每次交易仓位比例")
    stop_loss_pct: float = Field(default=0.07, description="止损比例")
    take_profit_pct: float = Field(default=0.15, description="止盈比例")


@app.get("/api/backtest/strategies")
@limiter.limit("30/minute")
async def get_backtest_strategies(request: Request):
    """获取所有可用的回测策略列表"""
    from astock_agents.services.strategy_signals import get_available_strategies
    strategies = get_available_strategies()
    return {"success": True, "data": strategies}


@app.post("/api/backtest/strategy-run")
@limiter.limit("5/minute")
async def run_strategy_backtest(request: Request, body: StrategyBacktestRequest):
    """策略自动回测

    根据策略ID自动生成交易信号并执行回测，无需手动输入信号。
    支持策略: ma(均线)/macd/rsi/boll(布林带)/kdj/combo(组合投票)
    """
    try:
        validated_code = validate_stock_code(body.stock_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 获取股票数据
    try:
        dm = _get_data_manager()
        stock_data_result = dm.get_stock_data(validated_code)
        stock_data = stock_data_result[0] if isinstance(stock_data_result, tuple) else stock_data_result
    except Exception as e:
        logger.error(f"[Web] 策略回测获取数据失败: {validated_code}, {e}")
        raise HTTPException(status_code=503, detail=f"获取股票数据失败: {str(e)}")

    if not stock_data or not stock_data.prices:
        raise HTTPException(status_code=404, detail=f"未找到 {validated_code} 的历史数据")

    # 将StockPrice转为字典列表供策略使用
    prices = []
    for p in stock_data.prices:
        prices.append({
            "date": p.date.strftime("%Y-%m-%d") if hasattr(p.date, "strftime") else str(p.date),
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
            "volume": p.volume,
        })

    # 生成策略信号
    try:
        from astock_agents.services.strategy_signals import generate_strategy_signals
        signals = generate_strategy_signals(
            strategy_id=body.strategy_id,
            prices=prices,
            params=body.strategy_params,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Web] 策略信号生成失败: {body.strategy_id}, {e}")
        raise HTTPException(status_code=500, detail=f"策略信号生成失败: {str(e)}")

    if not signals:
        raise HTTPException(status_code=404, detail=f"策略 {body.strategy_id} 未生成任何交易信号")

    # 执行回测
    try:
        engine = _get_backtest_engine()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: engine.run(
                stock_data=stock_data,
                signals=signals,
                strategy_name=body.strategy_id,
                position_size_pct=body.position_size_pct,
                stop_loss_pct=body.stop_loss_pct,
                take_profit_pct=body.take_profit_pct,
            )
        )

        result_dict = asdict(result)
        result_dict["strategy_id"] = body.strategy_id
        result_dict["signal_count"] = len(signals)
        result_dict["buy_signals"] = sum(1 for s in signals if s["action"] == "buy")
        result_dict["sell_signals"] = sum(1 for s in signals if s["action"] == "sell")
        return {"success": True, "data": result_dict}

    except Exception as e:
        logger.error(f"[Web] 策略回测执行失败: {validated_code}, {e}")
        raise HTTPException(status_code=500, detail=f"策略回测执行失败: {str(e)}")


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


# ---------- 行业轮动分析 ----------

@app.get("/api/sector/rotation")
@limiter.limit("10/minute")
async def sector_rotation(request: Request):
    """行业轮动分析 - 经济周期定位、行业推荐、轮动信号

    限流: 每分钟10次请求
    """
    try:
        analyzer = _get_sector_rotation_analyzer()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, analyzer.analyze)

        # 将dataclass转为可序列化的字典
        return {"success": True, "data": asdict(result)}

    except Exception as e:
        logger.error(f"[Web] 行业轮动分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"行业轮动分析失败: {str(e)}")


@app.get("/api/sector/heatmap")
@limiter.limit("10/minute")
async def sector_heatmap(request: Request):
    """行业热力图数据 - 28个申万一级行业涨跌幅、量比、资金流向、热度评分

    限流: 每分钟10次请求
    """
    try:
        analyzer = _get_sector_rotation_analyzer()
        loop = asyncio.get_event_loop()
        heatmap_items = await loop.run_in_executor(None, analyzer.get_sector_heatmap)

        return {"success": True, "data": [asdict(item) for item in heatmap_items]}

    except Exception as e:
        logger.error(f"[Web] 行业热力图获取失败: {e}")
        raise HTTPException(status_code=500, detail=f"行业热力图获取失败: {str(e)}")


# ==================== 调度器API ====================

_scheduler_service = None


def _get_scheduler_service():
    """懒加载调度器服务"""
    global _scheduler_service
    if _scheduler_service is None:
        from astock_agents.services.scheduler import SchedulerService
        _scheduler_service = SchedulerService()
    return _scheduler_service


@app.get("/api/scheduler/status")
@limiter.limit("30/minute")
async def scheduler_status(request: Request):
    """获取调度器状态"""
    scheduler = _get_scheduler_service()
    return {
        "enabled": scheduler.is_running,
        "jobs": scheduler.get_jobs() if scheduler.is_running else [],
    }


@app.post("/api/scheduler/start")
@limiter.limit("10/minute")
async def scheduler_start(request: Request):
    """启动调度器"""
    scheduler = _get_scheduler_service()
    if scheduler.is_running:
        return {"success": True, "message": "调度器已在运行中"}
    try:
        scheduler.start()
        return {"success": True, "message": "调度器已启动"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动调度器失败: {str(e)}")


@app.post("/api/scheduler/stop")
@limiter.limit("10/minute")
async def scheduler_stop(request: Request):
    """停止调度器"""
    scheduler = _get_scheduler_service()
    if not scheduler.is_running:
        return {"success": True, "message": "调度器未在运行"}
    try:
        scheduler.stop()
        return {"success": True, "message": "调度器已停止"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止调度器失败: {str(e)}")


# ==================== 通知API ====================

@app.get("/api/notifications/history")
@limiter.limit("30/minute")
async def notification_history(request: Request, limit: int = 20):
    """获取通知历史"""
    from astock_agents.services.notification import get_notification_service
    service = get_notification_service()
    history = service.get_history(limit=limit)
    return {
        "notifications": [n.to_dict() for n in history],
        "total": len(history),
    }


@app.get("/api/notifications/channels")
@limiter.limit("30/minute")
async def notification_channels(request: Request):
    """获取通知通道状态"""
    from astock_agents.services.notification import get_notification_service, NotificationChannel
    service = get_notification_service()
    return {
        "channels": {
            ch.value: service.is_enabled(ch)
            for ch in NotificationChannel
        }
    }


@app.post("/api/notifications/test")
@limiter.limit("5/minute")
async def notification_test(request: Request):
    """发送测试通知"""
    from astock_agents.services.notification import get_notification_service, NotificationMessage
    service = get_notification_service()
    message = NotificationMessage(
        title="测试通知",
        body="这是一条来自AStockAgents的测试通知，如果您收到此消息，说明通知服务配置正确。",
        level="info",
    )
    success = service.send(message)
    return {"success": success, "message": "测试通知已发送" if success else "测试通知发送失败"}


# ==================== 多轮对话 ====================

class DialogueRequest(BaseModel):
    """对话请求"""
    question: str = Field(..., description="用户提问")
    session_id: str = Field(default="default", description="会话ID")
    stock_code: Optional[str] = Field(default=None, description="股票代码")


@app.post("/api/dialogue/ask")
async def dialogue_ask(request: DialogueRequest):
    """多轮对话 - 用户追问

    支持的意图：
    - why_signal: 为什么买入/卖出？
    - risk_detail: 风险在哪？
    - compare: 对比分析
    - deep_dive: 详细分析
    - challenge: 我不同意
    - follow_up: 接下来怎么办？
    """
    try:
        from astock_agents.services.dialogue_service import DialogueService
        service = DialogueService()

        context = service.get_context(
            session_id=request.session_id,
            stock_code=request.stock_code,
        )

        analysis_result = None
        if request.stock_code:
            try:
                records = Database().get_analysis_results(
                    stock_code=request.stock_code, limit=1
                )
                if records:
                    report_json = records[0].get("report_json", "{}")
                    analysis_result = json.loads(report_json) if isinstance(report_json, str) else report_json
            except Exception:
                pass

        response = service.generate_response(
            question=request.question,
            context=context,
            analysis_result=analysis_result,
        )

        return response

    except Exception as e:
        logger.error(f"[对话] 处理失败: {e}")
        return {"error": str(e), "question": request.question, "answer": "对话处理失败，请稍后重试"}


@app.get("/api/dialogue/history/{session_id}")
async def dialogue_history(session_id: str, limit: int = 20):
    """获取对话历史"""
    try:
        db = Database()
        history = db.get_dialogue_history(session_id=session_id, limit=limit)
        return {"session_id": session_id, "history": history, "count": len(history)}
    except Exception as e:
        return {"error": str(e), "history": []}


# ==================== 持续学习（反馈） ====================

class FeedbackRequest(BaseModel):
    """反馈请求"""
    stock_code: str = Field(..., description="股票代码")
    signal: str = Field(..., description="当时的信号")
    feedback_type: str = Field(..., description="反馈类型: agree/disagree/neutral")
    feedback_text: str = Field(default="", description="反馈文本")
    actual_outcome: str = Field(default="", description="实际结果")
    user_id: str = Field(default="default", description="用户ID")


@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest):
    """提交用户反馈 - 用于持续学习

    用户对分析结果的评价会被记录，系统据此调整策略参数：
    - agree: 信号准确，提升该信号权重
    - disagree: 信号不准确，降低该信号权重
    - neutral: 中立，不调整
    """
    try:
        from astock_agents.services.continual_learning import ContinualLearningService
        service = ContinualLearningService()

        result = service.record_feedback(
            user_id=request.user_id,
            stock_code=request.stock_code,
            signal=request.signal,
            feedback_type=request.feedback_type,
            feedback_text=request.feedback_text,
            actual_outcome=request.actual_outcome,
        )

        return result

    except Exception as e:
        logger.error(f"[反馈] 处理失败: {e}")
        return {"error": str(e), "feedback_recorded": False}


@app.get("/api/learning/state")
async def learning_state(user_id: str = "default"):
    """获取持续学习状态"""
    try:
        from astock_agents.services.continual_learning import ContinualLearningService
        service = ContinualLearningService()
        return service.get_learning_state(user_id)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/learning/weights")
async def learning_weights(user_id: str = "default"):
    """获取调整后的分析维度权重"""
    try:
        from astock_agents.services.continual_learning import ContinualLearningService
        service = ContinualLearningService()
        return {"user_id": user_id, "weights": service.get_adjusted_weights(user_id)}
    except Exception as e:
        return {"error": str(e)}


# ==================== WebSocket实时推送 ====================

from fastapi import WebSocket, WebSocketDisconnect


@app.websocket("/ws")
@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str = ""):
    """WebSocket实时推送端点 - 分析进度、智能体状态、信号变化"""
    from astock_agents.web.websocket import get_connection_manager
    manager = get_connection_manager()
    client_id = await manager.connect(websocket)
    try:
        while True:
            # 保持连接，接收客户端消息（心跳等）
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"[WebSocket] 连接异常: {e}")
        manager.disconnect(client_id)


@app.get("/api/ws/status")
async def websocket_status(request: Request):
    """获取WebSocket连接状态"""
    from astock_agents.web.websocket import get_connection_manager
    manager = get_connection_manager()
    return {"active_connections": manager.get_active_count()}


# ==================== 追踪中心API ====================

_tracker_service = None


def _get_tracker_service():
    """懒加载追踪服务"""
    global _tracker_service
    if _tracker_service is None:
        from astock_agents.services.tracker import TrackerService
        _tracker_service = TrackerService()
    return _tracker_service


@app.post("/api/trackers")
@limiter.limit("10/minute")
async def create_tracker(request: Request):
    """创建股票追踪"""
    body = await request.json()
    stock_code = body.get("stock_code", "")
    stock_name = body.get("stock_name", "")
    thesis_data = body.get("thesis")

    if not stock_code or not stock_name:
        raise HTTPException(status_code=400, detail="股票代码和名称不能为空")

    try:
        service = _get_tracker_service()
        thesis = None
        if thesis_data:
            from astock_agents.services.tracker import InvestmentThesis
            thesis = InvestmentThesis(
                reasons=thesis_data.get("reasons", []),
                watch_indicators=thesis_data.get("watch_indicators", []),
                exit_conditions=thesis_data.get("exit_conditions", []),
                stop_loss_price=thesis_data.get("stop_loss_price"),
                profit_target_price=thesis_data.get("profit_target_price"),
            )
        tracker = service.create_tracker(stock_code, stock_name, thesis)
        return {"success": True, "data": tracker.__dict__ if hasattr(tracker, '__dict__') else str(tracker)}
    except Exception as e:
        logger.error(f"[Web] 创建追踪失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建追踪失败: {str(e)}")


@app.get("/api/trackers")
@limiter.limit("30/minute")
async def list_trackers(request: Request, active_only: bool = True):
    """获取追踪列表"""
    service = _get_tracker_service()
    trackers = service.list_trackers(active_only=active_only)
    return {"success": True, "data": [t.__dict__ if hasattr(t, '__dict__') else str(t) for t in trackers]}


@app.get("/api/trackers/{tracker_id}")
@limiter.limit("30/minute")
async def get_tracker(request: Request, tracker_id: str):
    """获取追踪详情"""
    service = _get_tracker_service()
    tracker = service.get_tracker(tracker_id)
    if not tracker:
        raise HTTPException(status_code=404, detail="追踪不存在")
    return {"success": True, "data": tracker.__dict__ if hasattr(tracker, '__dict__') else str(tracker)}


@app.put("/api/trackers/{tracker_id}/thesis")
@limiter.limit("10/minute")
async def update_thesis(request: Request, tracker_id: str):
    """更新投资逻辑"""
    body = await request.json()
    from astock_agents.services.tracker import InvestmentThesis
    thesis = InvestmentThesis(
        reasons=body.get("reasons", []),
        watch_indicators=body.get("watch_indicators", []),
        exit_conditions=body.get("exit_conditions", []),
        stop_loss_price=body.get("stop_loss_price"),
        profit_target_price=body.get("profit_target_price"),
    )
    service = _get_tracker_service()
    success = service.update_thesis(tracker_id, thesis)
    if not success:
        raise HTTPException(status_code=404, detail="追踪不存在")
    return {"success": True}


@app.get("/api/trackers/{tracker_id}/timeline")
@limiter.limit("30/minute")
async def get_signal_timeline(request: Request, tracker_id: str, days: int = 30):
    """获取信号变化时间线"""
    service = _get_tracker_service()
    timeline = service.get_signal_timeline(tracker_id, days=days)
    return {"success": True, "data": [sc.__dict__ if hasattr(sc, '__dict__') else str(sc) for sc in timeline]}


@app.post("/api/trackers/{tracker_id}/deactivate")
@limiter.limit("10/minute")
async def deactivate_tracker(request: Request, tracker_id: str):
    """停止追踪"""
    service = _get_tracker_service()
    success = service.deactivate_tracker(tracker_id)
    if not success:
        raise HTTPException(status_code=404, detail="追踪不存在")
    return {"success": True}


@app.delete("/api/trackers/{tracker_id}")
@limiter.limit("10/minute")
async def delete_tracker(request: Request, tracker_id: str):
    """删除追踪"""
    service = _get_tracker_service()
    success = service.delete_tracker(tracker_id)
    if not success:
        raise HTTPException(status_code=404, detail="追踪不存在")
    return {"success": True}


# ==================== 历史分析API ====================

_history_service = None


def _get_history_service():
    """懒加载历史分析服务"""
    global _history_service
    if _history_service is None:
        from astock_agents.services.analysis_history import AnalysisHistoryService
        _history_service = AnalysisHistoryService()
    return _history_service


@app.get("/api/analysis/history/{stock_code}")
@limiter.limit("30/minute")
async def get_analysis_history(request: Request, stock_code: str, limit: int = 20):
    """获取股票分析历史"""
    service = _get_history_service()
    history = service.get_analysis_history(stock_code, limit=limit)
    return {"success": True, "data": history}


@app.get("/api/analysis/compare")
@limiter.limit("10/minute")
async def compare_analyses(request: Request, id1: int, id2: int):
    """对比两次分析结果"""
    service = _get_history_service()
    result = service.compare_analyses(id1, id2)
    if not result:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return {"success": True, "data": result}


@app.get("/api/analysis/statistics/{stock_code}")
@limiter.limit("30/minute")
async def get_signal_statistics(request: Request, stock_code: str, days: int = 30):
    """获取信号统计"""
    service = _get_history_service()
    stats = service.get_signal_statistics(stock_code, days=days)
    return {"success": True, "data": stats}


@app.get("/api/analysis/trend/{stock_code}")
@limiter.limit("30/minute")
async def get_score_trend(request: Request, stock_code: str, days: int = 90):
    """获取评分趋势"""
    service = _get_history_service()
    trend = service.get_score_trend(stock_code, days=days)
    return {"success": True, "data": trend}


@app.get("/api/analysis/search")
@limiter.limit("30/minute")
async def search_analyses(request: Request, q: str = "", limit: int = 50):
    """搜索分析记录"""
    service = _get_history_service()
    results = service.search_analyses(q, limit=limit)
    return {"success": True, "data": results}


# ==================== 自动决策引擎API ====================

@app.get("/api/decisions/pending")
@limiter.limit("30/minute")
async def get_pending_decisions(request: Request):
    """获取待执行决策"""
    try:
        engine = _get_decision_engine()
        decisions = engine.get_pending_decisions()
        return {
            "success": True,
            "decisions": [asdict(d) for d in decisions],
            "total": len(decisions),
        }
    except Exception as e:
        logger.error(f"[Web] 获取待执行决策失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取待执行决策失败: {str(e)}")


@app.get("/api/decisions/history")
@limiter.limit("30/minute")
async def get_decision_history(request: Request, stock_code: str = "", limit: int = 50):
    """获取决策历史"""
    try:
        engine = _get_decision_engine()
        decisions = engine.get_decision_history(stock_code=stock_code, limit=limit)
        return {
            "success": True,
            "decisions": [asdict(d) for d in decisions],
            "total": len(decisions),
        }
    except Exception as e:
        logger.error(f"[Web] 获取决策历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取决策历史失败: {str(e)}")


@app.post("/api/decisions/{decision_id}/execute")
@limiter.limit("10/minute")
async def execute_decision(request: Request, decision_id: str):
    """执行决策"""
    try:
        engine = _get_decision_engine()
        result = engine.execute_decision(decision_id)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message", "执行失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Web] 执行决策失败: {decision_id}, {e}")
        raise HTTPException(status_code=500, detail=f"执行决策失败: {str(e)}")


@app.post("/api/decisions/{decision_id}/cancel")
@limiter.limit("10/minute")
async def cancel_decision(request: Request, decision_id: str):
    """取消决策"""
    try:
        body = await request.json() if request.headers.get("content-type") else {}
    except Exception:
        body = {}

    reason = body.get("reason", "") if isinstance(body, dict) else ""

    try:
        engine = _get_decision_engine()
        success = engine.cancel_decision(decision_id, reason=reason)
        if not success:
            raise HTTPException(status_code=400, detail="取消失败，决策不存在或状态不允许")
        return {"success": True, "message": "决策已取消"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Web] 取消决策失败: {decision_id}, {e}")
        raise HTTPException(status_code=500, detail=f"取消决策失败: {str(e)}")


@app.post("/api/decisions/{decision_id}/review")
@limiter.limit("10/minute")
async def review_decision(request: Request, decision_id: str):
    """决策复盘"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体解析失败")

    outcome = body.get("outcome", "")
    actual_pnl = body.get("actual_pnl", 0.0)

    if not outcome:
        raise HTTPException(status_code=400, detail="复盘结果(outcome)不能为空")

    try:
        engine = _get_decision_engine()
        result = engine.review_decision(decision_id, outcome=outcome, actual_pnl=float(actual_pnl))
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message", "复盘失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Web] 决策复盘失败: {decision_id}, {e}")
        raise HTTPException(status_code=500, detail=f"决策复盘失败: {str(e)}")


# ==================== 核心竞争力API ====================

_capital_flow_analyst = None
_market_sentiment_analyzer = None
_position_sizing_service = None


def _get_capital_flow_analyst():
    """懒加载资金流向分析师"""
    global _capital_flow_analyst
    if _capital_flow_analyst is None:
        from astock_agents.agents.capital_flow_analyst import CapitalFlowAnalyst
        _capital_flow_analyst = CapitalFlowAnalyst()
    return _capital_flow_analyst


def _get_market_sentiment_analyzer():
    """懒加载市场情绪分析器"""
    global _market_sentiment_analyzer
    if _market_sentiment_analyzer is None:
        from astock_agents.services.market_sentiment import MarketSentimentAnalyzer
        _market_sentiment_analyzer = MarketSentimentAnalyzer()
    return _market_sentiment_analyzer


def _get_position_sizing_service():
    """懒加载仓位管理服务"""
    global _position_sizing_service
    if _position_sizing_service is None:
        from astock_agents.services.position_sizing import PositionSizingService
        _position_sizing_service = PositionSizingService()
    return _position_sizing_service


class CapitalFlowRequest(BaseModel):
    """资金流向分析请求"""
    stock_code: str = Field(..., description="股票代码，如 600519.SH")
    stock_name: Optional[str] = Field(None, description="股票名称")


@app.post("/api/capital-flow/analyze")
@limiter.limit("10/minute")
async def capital_flow_analyze(request: Request, body: CapitalFlowRequest):
    """
    资金流向分析 - 主力资金、北向资金、融资融券、资金共振、量价背离

    限流: 每分钟10次请求
    """
    try:
        validated_code = validate_stock_code(body.stock_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        # 获取股票数据
        dm = _get_data_manager()
        stock_data_result = dm.get_stock_data(validated_code)
        stock_data = stock_data_result[0] if isinstance(stock_data_result, tuple) else stock_data_result
        if not stock_data:
            # 无数据时创建基础StockData
            from astock_agents.models import StockData as SD
            stock_data = SD(
                stock_code=validated_code,
                stock_name=body.stock_name or validated_code,
            )

        analyst = _get_capital_flow_analyst()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: analyst.analyze(stock_data)
        )

        return {"success": True, "data": result}

    except Exception as e:
        logger.error(f"[Web] 资金流向分析失败: {body.stock_code}, {e}")
        raise HTTPException(status_code=500, detail=f"资金流向分析失败: {str(e)}")


@app.get("/api/market/sentiment")
@limiter.limit("10/minute")
async def market_sentiment(request: Request):
    """
    市场情绪温度计 - 恐贪指数、市场宽度、成交量情绪、波动率水平

    限流: 每分钟10次请求
    """
    try:
        analyzer = _get_market_sentiment_analyzer()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: analyzer.analyze()
        )

        return {"success": True, "data": asdict(result)}

    except Exception as e:
        logger.error(f"[Web] 市场情绪分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"市场情绪分析失败: {str(e)}")


class PositionSizingRequest(BaseModel):
    """仓位计算请求"""
    stock_code: str = Field(..., description="股票代码")
    signal: str = Field(..., description="交易信号: strong_buy/buy/hold/sell/strong_sell")
    confidence: float = Field(50, ge=0, le=100, description="信号置信度 0-100")
    risk_level: str = Field("moderate", description="风险等级: low/moderate/high/extreme")
    portfolio_value: float = Field(100000, gt=0, description="组合总价值")
    stop_loss_pct: float = Field(0.07, gt=0, lt=1, description="止损比例")
    current_price: Optional[float] = Field(None, gt=0, description="当前股价")


class PortfolioSizingRequest(BaseModel):
    """组合仓位计算请求"""
    signals: List[Dict[str, Any]] = Field(..., description="信号列表")
    portfolio_value: float = Field(100000, gt=0, description="组合总价值")
    current_positions: Optional[List[Dict[str, Any]]] = Field(None, description="当前持仓")


@app.post("/api/position-sizing")
@limiter.limit("10/minute")
async def calculate_position(request: Request, body: PositionSizingRequest):
    """
    计算仓位建议 - 凯利公式、半凯利策略、风险约束

    限流: 每分钟10次请求
    """
    try:
        service = _get_position_sizing_service()
        result = service.calculate_position(
            signal=body.signal,
            confidence=body.confidence,
            risk_level=body.risk_level,
            portfolio_value=body.portfolio_value,
            stop_loss_pct=body.stop_loss_pct,
            stock_code=body.stock_code,
            current_price=body.current_price,
        )

        return {"success": True, "data": asdict(result)}

    except Exception as e:
        logger.error(f"[Web] 仓位计算失败: {e}")
        raise HTTPException(status_code=500, detail=f"仓位计算失败: {str(e)}")


@app.post("/api/position-sizing/portfolio")
@limiter.limit("5/minute")
async def calculate_portfolio_allocation(request: Request, body: PortfolioSizingRequest):
    """
    计算组合级仓位配置 - 风险平价、相关性调整

    限流: 每分钟5次请求
    """
    try:
        service = _get_position_sizing_service()
        results = service.calculate_portfolio_allocation(
            signals=body.signals,
            portfolio_value=body.portfolio_value,
            current_positions=body.current_positions,
        )

        return {"success": True, "data": [asdict(r) for r in results]}

    except Exception as e:
        logger.error(f"[Web] 组合仓位计算失败: {e}")
        raise HTTPException(status_code=500, detail=f"组合仓位计算失败: {str(e)}")


# ==================== Vue前端静态文件服务（生产模式） ====================

_FRONTEND_DIST = os.path.join(_CURRENT_DIR, "..", "..", "frontend", "dist")

# ==================== LLM配置API ====================

_user_memory_service = None
_mcp_server = None


def _get_user_memory_service():
    """懒加载用户记忆服务"""
    global _user_memory_service
    if _user_memory_service is None:
        from astock_agents.services.user_memory import UserMemoryService
        _user_memory_service = UserMemoryService()
    return _user_memory_service


def _get_mcp_server():
    """懒加载MCP服务"""
    global _mcp_server
    if _mcp_server is None:
        from astock_agents.services.mcp_server import MCPServer
        _mcp_server = MCPServer()
    return _mcp_server


@app.get("/api/llm/config")
@limiter.limit("30/minute")
async def get_llm_config(request: Request):
    """获取当前LLM配置（隐藏API Key）

    返回脱敏后的LLM提供商配置信息，API Key仅显示前4位和后4位。
    """
    from astock_agents.config import get_safe_llm_config
    config = get_safe_llm_config()
    return {"success": True, "data": config}


class LLMTestRequest(BaseModel):
    """LLM连接测试请求"""
    provider: str = Field(..., description="LLM提供商: openai/anthropic/qwen/deepseek/ollama/zhipu")
    prompt: str = Field("你好，请回复'连接成功'", description="测试提示词")


@app.post("/api/llm/test")
@limiter.limit("5/minute")
async def test_llm_connection(request: Request, body: LLMTestRequest):
    """测试LLM连接是否正常

    向指定的LLM提供商发送一条测试消息，验证连接和认证是否正常。
    限流: 每分钟5次请求
    """
    try:
        from astock_agents.config import get_llm_config
        from astock_agents.agents.base_agent import BaseAgent

        llm_config = get_llm_config()
        llm_config["default_provider"] = body.provider

        # 创建临时智能体测试LLM连接
        class _TestAgent(BaseAgent):
            def analyze(self, stock_data, **kwargs):
                return {}

        agent = _TestAgent(
            name="LLM测试",
            role="连接测试",
            config={"llm": llm_config},
        )

        if not agent.llm:
            return {
                "success": False,
                "provider": body.provider,
                "error": "LLM初始化失败，请检查API Key配置",
            }

        # 发送测试消息
        response = agent._call_llm(body.prompt)
        return {
            "success": True,
            "provider": body.provider,
            "response_preview": response[:200] if response else "",
        }

    except Exception as e:
        logger.error(f"[Web] LLM连接测试失败: {body.provider}, {e}")
        return {
            "success": False,
            "provider": body.provider,
            "error": str(e),
        }


# ==================== 用户记忆API ====================

@app.get("/api/memory/profile")
@limiter.limit("30/minute")
async def get_user_profile(request: Request, user_id: str = "default"):
    """获取用户投资画像

    基于历史行为数据，返回用户的投资偏好画像，包括偏好行业、风险偏好、持仓周期等。
    """
    service = _get_user_memory_service()
    profile = service.get_user_profile(user_id)
    return {"success": True, "data": profile}


@app.get("/api/memory/stock/{stock_code}")
@limiter.limit("30/minute")
async def get_stock_memory(request: Request, stock_code: str, user_id: str = "default"):
    """获取股票历史记忆

    返回用户对指定股票的历史分析和交易记录。
    """
    service = _get_user_memory_service()
    memory = service.get_stock_memory(user_id, stock_code)
    return {"success": True, "data": memory}


class MemoryRecordRequest(BaseModel):
    """记忆记录请求"""
    user_id: str = Field("default", description="用户ID")
    action_type: str = Field(..., description="行为类型: analysis/trade")
    stock_code: str = Field(..., description="股票代码")
    signal: Optional[str] = Field(None, description="信号")
    confidence: Optional[int] = Field(None, ge=0, le=100, description="置信度")
    amount: Optional[float] = Field(None, description="交易金额")
    price: Optional[float] = Field(None, description="交易价格")
    industry: Optional[str] = Field(None, description="所属行业")


@app.post("/api/memory/record")
@limiter.limit("30/minute")
async def record_memory(request: Request, body: MemoryRecordRequest):
    """记录用户行为

    记录用户的分析或交易行为，用于构建投资画像。
    """
    service = _get_user_memory_service()

    if body.action_type == "analysis":
        success = service.record_analysis(
            user_id=body.user_id,
            stock_code=body.stock_code,
            signal=body.signal or "",
            confidence=body.confidence or 50,
            industry=body.industry,
        )
    elif body.action_type == "trade":
        success = service.record_trade(
            user_id=body.user_id,
            stock_code=body.stock_code,
            action=body.signal or "buy",
            amount=body.amount or 0,
            price=body.price or 0,
            industry=body.industry,
        )
    else:
        raise HTTPException(status_code=400, detail=f"不支持的行为类型: {body.action_type}")

    return {"success": success}


# ==================== MCP协议API ====================

@app.get("/api/mcp/tools")
@limiter.limit("30/minute")
async def list_mcp_tools(request: Request):
    """列出所有可用的MCP工具

    返回所有已注册的金融工具定义，包括名称、描述和输入参数Schema。
    """
    server = _get_mcp_server()
    tools = server.list_tools()
    return {"success": True, "tools": tools, "total": len(tools)}


class MCPCallRequest(BaseModel):
    """MCP工具调用请求"""
    tool_name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="工具参数")


@app.post("/api/mcp/call")
@limiter.limit("10/minute")
async def call_mcp_tool(request: Request, body: MCPCallRequest):
    """调用MCP工具

    调用指定的金融工具并返回结果。
    限流: 每分钟10次请求
    """
    server = _get_mcp_server()

    try:
        result = server.call_tool(body.tool_name, body.arguments)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "工具调用失败"))
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== 辩论配置API ====================

class DebateConfigRequest(BaseModel):
    """辩论配置请求"""
    debate_rounds: int = Field(2, ge=1, le=5, description="辩论轮数(1-5)")
    enable_prisoners_dilemma: bool = Field(True, description="是否启用囚徒困境模型")


@app.post("/api/debate/config")
@limiter.limit("10/minute")
async def configure_debate(request: Request, body: DebateConfigRequest):
    """配置辩论参数

    设置辩论轮数和是否启用囚徒困境模型。
    注意：此配置影响后续所有分析请求的辩论过程。
    """
    global _workflow

    try:
        # 更新工作流配置
        if _workflow is not None:
            _workflow.debate_rounds = body.debate_rounds
            _workflow.enable_prisoners_dilemma = body.enable_prisoners_dilemma
            logger.info(
                f"[Web] 辩论配置已更新: 轮数={body.debate_rounds}, "
                f"囚徒困境={'启用' if body.enable_prisoners_dilemma else '禁用'}"
            )
        else:
            # 工作流未初始化，更新配置缓存
            config = _load_config()
            config["debate_rounds"] = body.debate_rounds
            config["enable_prisoners_dilemma"] = body.enable_prisoners_dilemma

        return {
            "success": True,
            "config": {
                "debate_rounds": body.debate_rounds,
                "enable_prisoners_dilemma": body.enable_prisoners_dilemma,
            },
        }
    except Exception as e:
        logger.error(f"[Web] 辩论配置更新失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置更新失败: {str(e)}")


@app.get("/api/debate/history/{stock_code}")
@limiter.limit("30/minute")
async def get_debate_history(request: Request, stock_code: str, limit: int = 20):
    """获取辩论历史

    返回指定股票的历史辩论记录，包括辩论轮数、投票结果、合作度评分等。
    """
    try:
        db = _get_db()
        history = db.get_debate_history(stock_code, limit=limit)

        # 解析JSON字段
        for record in history:
            if isinstance(record.get("debate_history_json"), str):
                try:
                    record["debate_history"] = json.loads(record["debate_history_json"])
                except (json.JSONDecodeError, TypeError):
                    record["debate_history"] = []
            if isinstance(record.get("votes_json"), str):
                try:
                    record["votes"] = json.loads(record["votes_json"])
                except (json.JSONDecodeError, TypeError):
                    record["votes"] = {}

        return {"success": True, "data": history, "total": len(history)}
    except Exception as e:
        logger.error(f"[Web] 获取辩论历史失败: {stock_code}, {e}")
        raise HTTPException(status_code=500, detail=f"获取辩论历史失败: {str(e)}")


# ==================== 合规/审计/FOMO/风险确认 API ====================

@app.get("/api/compliance/check")
@limiter.limit("30/minute")
async def compliance_check(request: Request, content: str = ""):
    """合规内容审查

    检查指定内容是否包含违规用语，返回审查结果。
    """
    from astock_agents.services.compliance import ComplianceGuard
    guard = ComplianceGuard()
    result = guard.audit_content(content) if content else {"compliant": True, "violations": [], "sanitized_content": content}
    return {"success": True, "data": result}


@app.get("/api/compliance/log")
@limiter.limit("30/minute")
async def get_compliance_log(request: Request, limit: int = 50):
    """获取合规审查日志"""
    from astock_agents.services.compliance import ComplianceGuard
    guard = ComplianceGuard()
    logs = guard.get_compliance_log(limit=limit)
    return {"success": True, "data": logs, "total": len(logs)}


@app.get("/api/audit/logs")
@limiter.limit("30/minute")
async def get_audit_logs(
    request: Request,
    log_type: Optional[str] = None,
    stock_code: Optional[str] = None,
    limit: int = 100,
):
    """获取审计日志

    支持按类型和股票代码过滤，返回风控/决策/合规等审计记录。
    """
    try:
        db = _get_db()
        logs = db.get_audit_logs(log_type=log_type, stock_code=stock_code, limit=limit)
        return {"success": True, "data": logs, "total": len(logs)}
    except Exception as e:
        logger.error(f"[Web] 获取审计日志失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取审计日志失败: {str(e)}")


@app.get("/api/datasource/status")
@limiter.limit("30/minute")
async def get_datasource_status(request: Request):
    """获取数据源状态

    返回各数据源的最新可用状态，包括数据类型、状态和消息。
    """
    try:
        db = _get_db()
        status = db.get_latest_data_source_status()
        return {"success": True, "data": status}
    except Exception as e:
        logger.error(f"[Web] 获取数据源状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据源状态失败: {str(e)}")


@app.post("/api/fomo/detect")
@limiter.limit("30/minute")
async def fomo_detect(request: Request, body: dict):
    """FOMO行为检测

    检测追高行为和过度交易倾向，返回检测结果和警告。
    """
    from astock_agents.services.fomo_guard import FOMODetector
    detector = FOMODetector()

    detect_type = body.get("type", "chasing_high")
    result: Dict[str, Any] = {}

    if detect_type == "chasing_high":
        result = detector.detect_chasing_high(
            stock_code=body.get("stock_code", ""),
            current_price=float(body.get("current_price", 0)),
            recent_high=float(body.get("recent_high", 0)),
            position_pct=float(body.get("position_pct", 0)),
        )
    elif detect_type == "overtrading":
        result = detector.detect_overtrading(user_id=body.get("user_id", "default"))

    return {"success": True, "data": result}


@app.post("/api/fomo/record-trade")
@limiter.limit("30/minute")
async def fomo_record_trade(request: Request, body: dict):
    """记录交易行为（用于FOMO检测）"""
    from astock_agents.services.fomo_guard import FOMODetector
    detector = FOMODetector()
    detector.record_trade(body)
    return {"success": True, "message": "交易记录已保存"}


@app.post("/api/emotion/calibrate")
@limiter.limit("30/minute")
async def emotion_calibrate(request: Request, body: dict):
    """情绪隔离 - 信号校准

    根据市场恐贪指数校准交易信号，防止情绪驱动决策。
    """
    from astock_agents.services.fomo_guard import EmotionIsolationLayer
    layer = EmotionIsolationLayer()
    result = layer.calibrate_signal(
        signal=body.get("signal", "持有"),
        confidence=int(body.get("confidence", 50)),
        fear_greed_index=float(body.get("fear_greed_index", 50)),
    )
    return {"success": True, "data": result}


@app.post("/api/stop-loss/calculate")
@limiter.limit("30/minute")
async def calculate_stop_loss(request: Request, body: dict):
    """计算动态止损位

    基于ATR计算动态止损价格，支持追踪止损。
    """
    from astock_agents.services.position_sizing import DynamicStopLossService
    service = DynamicStopLossService()
    result = service.calculate_stop_loss(
        entry_price=float(body.get("entry_price", 0)),
        prices=body.get("prices", []),
        direction=body.get("direction", "buy"),
        current_profit_pct=float(body.get("current_profit_pct", 0)),
    )
    return {"success": True, "data": result}


@app.get("/api/risk/acknowledgment")
@limiter.limit("30/minute")
async def check_risk_acknowledgment(request: Request, user_id: str = "default"):
    """检查用户是否已确认风险告知"""
    try:
        db = _get_db()
        acknowledged = db.is_risk_acknowledged(user_id)
        return {"success": True, "acknowledged": acknowledged, "user_id": user_id}
    except Exception as e:
        logger.error(f"[Web] 检查风险确认状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/risk/acknowledge")
@limiter.limit("10/minute")
async def acknowledge_risk(request: Request, body: dict):
    """用户确认风险告知

    用户首次使用系统时需确认风险告知，记录确认时间和版本。
    """
    try:
        db = _get_db()
        user_id = body.get("user_id", "default")
        version = body.get("version", "1.0")
        success = db.acknowledge_risk(user_id, version)
        if success:
            return {"success": True, "message": "风险确认已记录"}
        else:
            raise HTTPException(status_code=500, detail="风险确认记录失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Web] 记录风险确认失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/risk/disclaimer")
@limiter.limit("60/minute")
async def get_disclaimer(request: Request):
    """获取免责声明文本"""
    from astock_agents.services.compliance import DISCLAIMER_TEXT
    return {"success": True, "disclaimer": DISCLAIMER_TEXT}


# ==================== OpenRouter / LLM配置 API ====================

@app.get("/api/llm/providers")
@limiter.limit("30/minute")
async def get_llm_providers(request: Request):
    """获取所有LLM提供商配置状态

    返回各提供商的配置状态（API Key是否已设置），不暴露Key内容。
    """
    from astock_agents.config import get_llm_config, mask_api_key, OPENROUTER_FREE_MODELS
    config = get_llm_config()

    providers = []
    provider_names = ["openrouter", "openai", "anthropic", "qwen", "deepseek", "zhipu", "ollama"]
    for name in provider_names:
        pconfig = config.get(name, {})
        api_key = pconfig.get("api_key", "")
        providers.append({
            "id": name,
            "name": {
                "openrouter": "OpenRouter (免费模型)",
                "openai": "OpenAI",
                "anthropic": "Anthropic",
                "qwen": "通义千问",
                "deepseek": "DeepSeek",
                "zhipu": "智谱AI",
                "ollama": "Ollama (本地)",
            }.get(name, name),
            "configured": bool(api_key) if name != "ollama" else True,
            "model": pconfig.get("model", ""),
            "masked_key": mask_api_key(api_key) if api_key else "未配置",
        })

    return {
        "success": True,
        "default_provider": config.get("default_provider", "openrouter"),
        "providers": providers,
        "openrouter_free_models": OPENROUTER_FREE_MODELS,
    }


@app.post("/api/llm/test")
@limiter.limit("3/minute")
async def test_llm_connection(request: Request, body: dict):
    """测试LLM连接

    尝试用指定提供商发送一个简单请求，验证API Key和模型是否可用。
    """
    provider = body.get("provider", "openrouter")
    model = body.get("model")

    try:
        from astock_agents.config import get_llm_config
        from astock_agents.agents.base_agent import BaseAgent

        config = get_llm_config()
        if model:
            config.setdefault(provider, {})["model"] = model

        agent_config = {"llm": config}
        agent = BaseAgent(
            name="test_agent",
            role="测试",
            config=agent_config,
        )

        llm = agent._init_llm()
        if llm is None:
            return {"success": False, "error": "LLM初始化失败，无可用的LLM提供商"}

        response = llm.invoke([("human", "请回复'连接成功'四个字")])
        content = response.content if hasattr(response, "content") else str(response)

        return {
            "success": True,
            "provider": provider,
            "model": model or config.get(provider, {}).get("model", "unknown"),
            "response_preview": content[:200],
        }
    except Exception as e:
        return {"success": False, "provider": provider, "error": str(e)}


@app.get("/api/llm/openrouter/models")
@limiter.limit("10/minute")
async def get_openrouter_free_models(request: Request):
    """获取OpenRouter免费模型列表"""
    from astock_agents.config import OPENROUTER_FREE_MODELS
    return {"success": True, "models": OPENROUTER_FREE_MODELS}


if os.path.isdir(_FRONTEND_DIST) and not os.environ.get("ASTOCK_DEV_MODE"):
    from fastapi.staticfiles import StaticFiles

    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str):
        """SPA fallback - 所有非API路由返回index.html"""
        from fastapi.responses import FileResponse
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))


# ==================== 启动函数 ====================

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """启动Web服务器"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
