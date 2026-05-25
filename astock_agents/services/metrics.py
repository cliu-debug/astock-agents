"""Prometheus 监控指标模块 - 采集和暴露系统运行指标

提供基于 prometheus-client 的指标定义和采集器，覆盖分析流程、数据源调用、
断路器状态、交易订单、投资组合等核心业务场景。无需 Pushgateway，直接通过
HTTP 暴露 /metrics 端点供 Prometheus 拉取。
"""

from typing import Optional

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CollectorRegistry,
    REGISTRY,
)


# ---------------------------------------------------------------------------
# 指标定义
# ---------------------------------------------------------------------------

#: 分析请求总数，按股票代码和信号类型分类
ANALYSIS_TOTAL = Counter(
    "astock_analysis_total",
    "分析请求总数",
    ["stock_code", "signal"],
)

#: 分析耗时分布（秒）
ANALYSIS_DURATION_SECONDS = Histogram(
    "astock_analysis_duration_seconds",
    "分析耗时分布",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float("inf")),
)

#: 分析错误数，按错误类型分类
ANALYSIS_ERRORS_TOTAL = Counter(
    "astock_analysis_errors_total",
    "分析错误数",
    ["error_type"],
)

#: 数据源请求总数，按来源和状态分类
DATA_SOURCE_REQUESTS_TOTAL = Counter(
    "astock_data_source_requests_total",
    "数据源请求总数",
    ["source", "status"],
)

#: 数据源请求耗时分布（秒），按来源分类
DATA_SOURCE_DURATION_SECONDS = Histogram(
    "astock_data_source_duration_seconds",
    "数据源请求耗时分布",
    ["source"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, float("inf")),
)

#: 断路器状态 (0=CLOSED, 1=OPEN, 2=HALF_OPEN)
CIRCUIT_BREAKER_STATE = Gauge(
    "astock_circuit_breaker_state",
    "断路器状态 (0=CLOSED, 1=OPEN, 2=HALF_OPEN)",
    ["name"],
)

#: 交易订单总数，按方向和状态分类
TRADING_ORDERS_TOTAL = Counter(
    "astock_trading_orders_total",
    "交易订单总数",
    ["direction", "status"],
)

#: 投资组合总值
PORTFOLIO_VALUE = Gauge(
    "astock_portfolio_value",
    "投资组合总值",
)

#: 当前持仓数量
ACTIVE_POSITIONS = Gauge(
    "astock_active_positions",
    "当前持仓数量",
)

#: 自选股数量
WATCHLIST_COUNT = Gauge(
    "astock_watchlist_count",
    "自选股数量",
)


# ---------------------------------------------------------------------------
# 断路器状态枚举映射
# ---------------------------------------------------------------------------

_CIRCUIT_BREAKER_STATE_MAP: dict[str, int] = {
    "CLOSED": 0,
    "OPEN": 1,
    "HALF_OPEN": 2,
}


class MetricsCollector:
    """指标采集器 - 封装所有 Prometheus 指标的记录方法

    提供类型安全的指标记录接口，屏蔽底层 prometheus-client 的标签细节。
    全局通过 get_metrics_collector() 获取单例实例。
    """

    def record_analysis(
        self,
        stock_code: str,
        signal: str,
        duration: float,
    ) -> None:
        """记录一次分析请求

        Args:
            stock_code: 股票代码，如 "000001.SZ"
            signal: 信号类型，如 "buy" / "sell" / "hold"
            duration: 本次分析耗时（秒）
        """
        ANALYSIS_TOTAL.labels(stock_code=stock_code, signal=signal).inc()
        ANALYSIS_DURATION_SECONDS.observe(duration)

    def record_analysis_error(self, error_type: str) -> None:
        """记录一次分析错误

        Args:
            error_type: 错误类型，如 "timeout" / "data_unavailable" / "llm_error"
        """
        ANALYSIS_ERRORS_TOTAL.labels(error_type=error_type).inc()

    def record_data_source_request(
        self,
        source: str,
        status: str,
        duration: float,
    ) -> None:
        """记录一次数据源请求

        Args:
            source: 数据源名称，如 "tencent" / "akshare" / "eastmoney"
            status: 请求状态，如 "success" / "error" / "timeout"
            duration: 请求耗时（秒）
        """
        DATA_SOURCE_REQUESTS_TOTAL.labels(source=source, status=status).inc()
        DATA_SOURCE_DURATION_SECONDS.labels(source=source).observe(duration)

    def update_circuit_breaker_state(self, name: str, state: str) -> None:
        """更新断路器状态

        Args:
            name: 断路器名称，如 "tencent_api" / "akshare_api"
            state: 断路器状态，取值 "CLOSED" / "OPEN" / "HALF_OPEN"
        """
        state_value: int = _CIRCUIT_BREAKER_STATE_MAP.get(state, 0)
        CIRCUIT_BREAKER_STATE.labels(name=name).set(state_value)

    def record_trading_order(self, direction: str, status: str) -> None:
        """记录一笔交易订单

        Args:
            direction: 交易方向，如 "buy" / "sell"
            status: 订单状态，如 "filled" / "pending" / "cancelled" / "rejected"
        """
        TRADING_ORDERS_TOTAL.labels(direction=direction, status=status).inc()

    def update_portfolio_value(self, value: float) -> None:
        """更新投资组合总值

        Args:
            value: 投资组合总值（元）
        """
        PORTFOLIO_VALUE.set(value)

    def update_active_positions(self, count: int) -> None:
        """更新当前持仓数量

        Args:
            count: 当前持仓数量
        """
        ACTIVE_POSITIONS.set(count)

    def update_watchlist_count(self, count: int) -> None:
        """更新自选股数量

        Args:
            count: 自选股数量
        """
        WATCHLIST_COUNT.set(count)


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标采集器单例

    Returns:
        MetricsCollector: 全局唯一的指标采集器实例
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def generate_metrics(registry: Optional[CollectorRegistry] = None) -> str:
    """生成 Prometheus 格式的指标文本

    可直接用于 HTTP /metrics 端点的响应体，例如：

        from astock_agents.services.metrics import generate_metrics

        @app.route("/metrics")
        def metrics():
            return generate_metrics(), 200, {"Content-Type": "text/plain; charset=utf-8"}

    Args:
        registry: 指标注册表，默认使用全局 REGISTRY

    Returns:
        str: Prometheus 文本格式的指标数据
    """
    return generate_latest(registry or REGISTRY).decode("utf-8")
