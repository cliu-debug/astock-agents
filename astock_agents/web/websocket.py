"""
WebSocket 实时推送模块

提供 WebSocket 连接管理和实时消息推送能力，支持智能体状态变化、
分析进度、实时日志、信号变化、分析完成及错误消息的推送。

使用方式:
    from astock_agents.web.websocket import get_connection_manager, create_progress_msg

    manager = get_connection_manager()
    await manager.broadcast(create_progress_msg("600519.SH", "技术分析", 50, "technical_analyst"))
"""

import asyncio
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, Optional

from fastapi import WebSocket
from loguru import logger


# ==================== 消息类型定义 ====================

@dataclass(frozen=True)
class AgentStatusMessage:
    """智能体状态变化消息

    Attributes:
        type: 消息类型标识，固定为 "agent_status"
        agent_id: 智能体唯一标识
        status: 智能体当前状态（如 "idle" / "running" / "completed" / "error"）
        progress: 任务进度百分比，0~100
        message: 状态描述信息
    """
    type: str = field(default="agent_status", init=False)
    agent_id: str = ""
    status: str = ""
    progress: int = 0
    message: str = ""


@dataclass(frozen=True)
class AnalysisProgressMessage:
    """分析进度消息

    Attributes:
        type: 消息类型标识，固定为 "analysis_progress"
        stock_code: 股票代码，如 "600519.SH"
        phase: 当前分析阶段（如 "技术分析" / "基本面分析"）
        progress: 分析进度百分比，0~100
        current_agent: 当前执行的智能体标识
    """
    type: str = field(default="analysis_progress", init=False)
    stock_code: str = ""
    phase: str = ""
    progress: int = 0
    current_agent: str = ""


@dataclass(frozen=True)
class LogMessage:
    """实时日志消息

    Attributes:
        type: 消息类型标识，固定为 "log"
        level: 日志级别（如 "DEBUG" / "INFO" / "WARNING" / "ERROR"）
        source: 日志来源模块或智能体
        message: 日志内容
        timestamp: 日志时间戳，ISO 8601 格式
    """
    type: str = field(default="log", init=False)
    level: str = "INFO"
    source: str = ""
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(frozen=True)
class SignalChangeMessage:
    """信号变化消息

    Attributes:
        type: 消息类型标识，固定为 "signal_change"
        stock_code: 股票代码
        old_signal: 变化前的信号（如 "买入" / "持有" / "卖出"）
        new_signal: 变化后的信号
        confidence: 信号置信度，0~100
    """
    type: str = field(default="signal_change", init=False)
    stock_code: str = ""
    old_signal: str = ""
    new_signal: str = ""
    confidence: int = 0


@dataclass(frozen=True)
class AnalysisCompleteMessage:
    """分析完成消息

    Attributes:
        type: 消息类型标识，固定为 "analysis_complete"
        stock_code: 股票代码
        signal: 最终信号（如 "买入" / "持有" / "卖出"）
        confidence: 信号置信度，0~100
        duration: 分析耗时，单位秒
    """
    type: str = field(default="analysis_complete", init=False)
    stock_code: str = ""
    signal: str = ""
    confidence: int = 0
    duration: float = 0.0


@dataclass(frozen=True)
class ErrorMessage:
    """错误消息

    Attributes:
        type: 消息类型标识，固定为 "error"
        error_type: 错误类型（如 "connection" / "analysis" / "data_source"）
        message: 错误描述信息
    """
    type: str = field(default="error", init=False)
    error_type: str = ""
    message: str = ""


# ==================== 便捷消息创建函数 ====================

def create_agent_status_msg(
    agent_id: str,
    status: str,
    progress: int = 0,
    message: str = "",
) -> Dict[str, object]:
    """创建智能体状态变化消息

    Args:
        agent_id: 智能体唯一标识
        status: 智能体当前状态
        progress: 任务进度百分比，0~100
        message: 状态描述信息

    Returns:
        可 JSON 序列化的消息字典
    """
    return asdict(AgentStatusMessage(
        agent_id=agent_id,
        status=status,
        progress=progress,
        message=message,
    ))


def create_progress_msg(
    stock_code: str,
    phase: str,
    progress: int,
    current_agent: str,
) -> Dict[str, object]:
    """创建分析进度消息

    Args:
        stock_code: 股票代码
        phase: 当前分析阶段
        progress: 分析进度百分比，0~100
        current_agent: 当前执行的智能体标识

    Returns:
        可 JSON 序列化的消息字典
    """
    return asdict(AnalysisProgressMessage(
        stock_code=stock_code,
        phase=phase,
        progress=progress,
        current_agent=current_agent,
    ))


def create_log_msg(
    level: str,
    source: str,
    message: str,
) -> Dict[str, object]:
    """创建实时日志消息

    Args:
        level: 日志级别
        source: 日志来源模块或智能体
        message: 日志内容

    Returns:
        可 JSON 序列化的消息字典
    """
    return asdict(LogMessage(
        level=level,
        source=source,
        message=message,
    ))


def create_signal_change_msg(
    stock_code: str,
    old_signal: str,
    new_signal: str,
    confidence: int,
) -> Dict[str, object]:
    """创建信号变化消息

    Args:
        stock_code: 股票代码
        old_signal: 变化前的信号
        new_signal: 变化后的信号
        confidence: 信号置信度，0~100

    Returns:
        可 JSON 序列化的消息字典
    """
    return asdict(SignalChangeMessage(
        stock_code=stock_code,
        old_signal=old_signal,
        new_signal=new_signal,
        confidence=confidence,
    ))


def create_complete_msg(
    stock_code: str,
    signal: str,
    confidence: int,
    duration: float,
) -> Dict[str, object]:
    """创建分析完成消息

    Args:
        stock_code: 股票代码
        signal: 最终信号
        confidence: 信号置信度，0~100
        duration: 分析耗时，单位秒

    Returns:
        可 JSON 序列化的消息字典
    """
    return asdict(AnalysisCompleteMessage(
        stock_code=stock_code,
        signal=signal,
        confidence=confidence,
        duration=duration,
    ))


def create_error_msg(
    error_type: str,
    message: str,
) -> Dict[str, object]:
    """创建错误消息

    Args:
        error_type: 错误类型
        message: 错误描述信息

    Returns:
        可 JSON 序列化的消息字典
    """
    return asdict(ErrorMessage(
        error_type=error_type,
        message=message,
    ))


# ==================== 连接管理器 ====================

class ConnectionManager:
    """WebSocket 连接管理器

    管理所有活跃的 WebSocket 连接，提供单播和广播消息推送能力。
    使用 asyncio.Lock 保证并发操作的线程安全。

    Usage:
        manager = ConnectionManager()
        # 在 WebSocket 路由中
        await manager.connect(websocket, client_id)
        # 发送消息
        await manager.send_message(client_id, create_progress_msg(...))
        # 广播消息
        await manager.broadcast(create_log_msg(...))
        # 断开连接
        manager.disconnect(client_id)
    """

    def __init__(self) -> None:
        """初始化连接管理器"""
        self._active_connections: Dict[str, WebSocket] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def active_connections(self) -> Dict[str, WebSocket]:
        """获取所有活跃连接的只读视图

        Returns:
            客户端ID到WebSocket连接的映射字典
        """
        return dict(self._active_connections)

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """接受 WebSocket 连接并注册到管理器

        Args:
            websocket: FastAPI WebSocket 连接对象
            client_id: 可选的客户端标识，未提供时自动生成 UUID

        Returns:
            注册成功的客户端ID
        """
        if client_id is None:
            client_id = str(uuid.uuid4())

        await websocket.accept()

        async with self._lock:
            self._active_connections[client_id] = websocket

        logger.info(
            f"[WebSocket] 客户端连接: {client_id}，"
            f"当前活跃连接数: {len(self._active_connections)}"
        )
        return client_id

    def disconnect(self, client_id: str) -> None:
        """断开指定客户端连接并从管理器中移除

        Args:
            client_id: 要断开的客户端标识
        """
        removed = self._active_connections.pop(client_id, None)
        if removed is not None:
            logger.info(
                f"[WebSocket] 客户端断开: {client_id}，"
                f"当前活跃连接数: {len(self._active_connections)}"
            )
        else:
            logger.warning(f"[WebSocket] 尝试断开不存在的客户端: {client_id}")

    async def send_message(self, client_id: str, message: Dict[str, object]) -> bool:
        """向指定客户端发送 JSON 消息

        Args:
            client_id: 目标客户端标识
            message: 可 JSON 序列化的消息字典

        Returns:
            发送成功返回 True，客户端不存在或发送失败返回 False
        """
        websocket = self._active_connections.get(client_id)
        if websocket is None:
            logger.warning(f"[WebSocket] 发送消息失败，客户端不存在: {client_id}")
            return False

        try:
            await websocket.send_json(message)
            return True
        except Exception as exc:
            logger.error(f"[WebSocket] 发送消息异常: client_id={client_id}, error={exc}")
            self.disconnect(client_id)
            return False

    async def broadcast(self, message: Dict[str, object]) -> int:
        """向所有活跃客户端广播 JSON 消息

        自动清理发送失败的连接，确保广播不会因单个连接异常而中断。

        Args:
            message: 可 JSON 序列化的消息字典

        Returns:
            成功接收消息的客户端数量
        """
        if not self._active_connections:
            return 0

        failed_client_ids: list[str] = []
        success_count: int = 0

        for client_id, websocket in self._active_connections.items():
            try:
                await websocket.send_json(message)
                success_count += 1
            except Exception as exc:
                logger.error(
                    f"[WebSocket] 广播消息异常: client_id={client_id}, error={exc}"
                )
                failed_client_ids.append(client_id)

        # 清理发送失败的连接
        for client_id in failed_client_ids:
            self.disconnect(client_id)

        logger.debug(
            f"[WebSocket] 广播完成: 成功={success_count}, 失败={len(failed_client_ids)}"
        )
        return success_count

    def get_active_count(self) -> int:
        """获取当前活跃连接数

        Returns:
            活跃 WebSocket 连接的数量
        """
        return len(self._active_connections)


# ==================== 全局单例 ====================

_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """获取全局 WebSocket 连接管理器单例

    首次调用时创建实例，后续调用返回同一实例。

    Returns:
        ConnectionManager 全局单例
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
        logger.info("[WebSocket] 全局连接管理器已初始化")
    return _connection_manager
