"""WebSocket、追踪服务、历史分析服务集成测试"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json


# ==================== WebSocket测试 ====================

class TestWebSocket:
    """WebSocket实时推送模块测试"""

    def test_message_creation(self):
        """测试消息创建函数"""
        from astock_agents.web.websocket import (
            create_agent_status_msg,
            create_progress_msg,
            create_log_msg,
            create_signal_change_msg,
            create_complete_msg,
            create_error_msg,
        )

        msg = create_agent_status_msg("technical", "running", 50, "计算RSI")
        assert msg["type"] == "agent_status"
        assert msg["agent_id"] == "technical"
        assert msg["status"] == "running"

        msg = create_progress_msg("600519.SH", "parallel", 35, "technical")
        assert msg["type"] == "analysis_progress"
        assert msg["stock_code"] == "600519.SH"

        msg = create_log_msg("info", "technical", "RSI=65")
        assert msg["type"] == "log"
        assert msg["level"] == "info"

        msg = create_signal_change_msg("600519.SH", "买入", "持有", 0.65)
        assert msg["type"] == "signal_change"
        assert msg["old_signal"] == "买入"

        msg = create_complete_msg("600519.SH", "买入", 72, 5.3)
        assert msg["type"] == "analysis_complete"
        assert msg["duration"] == 5.3

        msg = create_error_msg("timeout", "数据源超时")
        assert msg["type"] == "error"
        assert msg["error_type"] == "timeout"

    def test_connection_manager_singleton(self):
        """测试连接管理器单例"""
        from astock_agents.web.websocket import get_connection_manager
        m1 = get_connection_manager()
        m2 = get_connection_manager()
        assert m1 is m2

    def test_connection_manager_initial_state(self):
        """测试连接管理器初始状态"""
        from astock_agents.web.websocket import ConnectionManager
        manager = ConnectionManager()
        assert manager.get_active_count() == 0
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self):
        """测试WebSocket连接和断开"""
        from astock_agents.web.websocket import ConnectionManager
        manager = ConnectionManager()
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        client_id = await manager.connect(mock_ws)
        assert manager.get_active_count() == 1
        assert client_id in manager.active_connections

        manager.disconnect(client_id)
        assert manager.get_active_count() == 0

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """测试广播消息"""
        from astock_agents.web.websocket import ConnectionManager
        manager = ConnectionManager()
        mock_ws1 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        await manager.connect(mock_ws1)
        await manager.connect(mock_ws2)

        await manager.broadcast({"type": "test", "message": "hello"})
        assert mock_ws1.send_json.called
        assert mock_ws2.send_json.called

        # 清理
        for cid in list(manager.active_connections.keys()):
            manager.disconnect(cid)


# ==================== 追踪服务测试 ====================

class TestTrackerService:
    """单股票追踪服务测试"""

    def test_investment_thesis_creation(self):
        """测试投资逻辑创建"""
        from astock_agents.services.tracker import InvestmentThesis
        thesis = InvestmentThesis(
            reasons=["品牌溢价", "高ROE"],
            watch_indicators=["批价", "营收增速"],
            exit_conditions=["营收下滑>5%"],
            stop_loss_price=1250.0,
            profit_target_price=1500.0,
        )
        assert len(thesis.reasons) == 2
        assert thesis.stop_loss_price == 1250.0

    def test_signal_change_creation(self):
        """测试信号变化记录创建"""
        from astock_agents.services.tracker import SignalChange
        sc = SignalChange(
            date="2026-05-25",
            old_signal="买入",
            new_signal="持有",
            score_change=-14,
            reason="RSI超买",
            is_noise=True,
            impact_level="medium",
        )
        assert sc.is_noise is True
        assert sc.impact_level == "medium"

    def test_analysis_snapshot_creation(self):
        """测试分析快照创建"""
        from astock_agents.services.tracker import AnalysisSnapshot
        snap = AnalysisSnapshot(
            date="2026-05-25",
            signal="买入",
            score=72,
            confidence=0.68,
            technical_summary="均线多头排列",
            fundamental_summary="估值合理",
            sentiment_summary="偏多",
            key_changes=["MACD金叉", "主力净流入"],
        )
        assert snap.score == 72
        assert len(snap.key_changes) == 2

    def test_tracker_service_init(self):
        """测试追踪服务初始化"""
        from astock_agents.services.tracker import TrackerService
        with patch("astock_agents.services.tracker.Database"):
            service = TrackerService()
            assert service is not None

    def test_create_tracker(self):
        """测试创建追踪"""
        from astock_agents.services.tracker import TrackerService, InvestmentThesis
        with patch("astock_agents.services.tracker.Database") as MockDB:
            mock_db = MagicMock()
            # 模拟已存在追踪检查返回None（不存在）
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_db.execute.return_value = mock_cursor
            MockDB.return_value = mock_db

            service = TrackerService()
            thesis = InvestmentThesis(
                reasons=["品牌溢价"],
                watch_indicators=["批价"],
                exit_conditions=[],
            )
            tracker = service.create_tracker("600519.SH", "贵州茅台", thesis)
            # 由于mock的局限性，只验证不抛异常
            # 实际创建逻辑在集成测试中验证

    def test_analyze_signal_change_high_impact(self):
        """测试信号变化分析 - 高影响"""
        from astock_agents.services.tracker import TrackerService, AnalysisSnapshot
        with patch("astock_agents.services.tracker.Database"):
            service = TrackerService()
            old = AnalysisSnapshot(
                date="2026-05-24", signal="买入", score=72, confidence=0.7,
                technical_summary="", fundamental_summary="",
                sentiment_summary="", key_changes=[],
            )
            new = AnalysisSnapshot(
                date="2026-05-25", signal="卖出", score=45, confidence=0.5,
                technical_summary="", fundamental_summary="",
                sentiment_summary="", key_changes=["RSI超买"],
            )
            change = service.analyze_signal_change(old, new)
            assert change.impact_level == "high"
            assert change.old_signal == "买入"
            assert change.new_signal == "卖出"

    def test_analyze_signal_change_medium_impact(self):
        """测试信号变化分析 - 中影响"""
        from astock_agents.services.tracker import TrackerService, AnalysisSnapshot
        with patch("astock_agents.services.tracker.Database"):
            service = TrackerService()
            old = AnalysisSnapshot(
                date="2026-05-24", signal="买入", score=72, confidence=0.7,
                technical_summary="", fundamental_summary="",
                sentiment_summary="", key_changes=[],
            )
            new = AnalysisSnapshot(
                date="2026-05-25", signal="持有", score=58, confidence=0.6,
                technical_summary="", fundamental_summary="",
                sentiment_summary="", key_changes=["RSI偏高"],
            )
            change = service.analyze_signal_change(old, new)
            assert change.impact_level == "medium"

    def test_analyze_signal_change_noise(self):
        """测试噪音判断 - 短期技术指标变化"""
        from astock_agents.services.tracker import TrackerService, AnalysisSnapshot
        with patch("astock_agents.services.tracker.Database"):
            service = TrackerService()
            old = AnalysisSnapshot(
                date="2026-05-24", signal="买入", score=72, confidence=0.7,
                technical_summary="", fundamental_summary="",
                sentiment_summary="", key_changes=[],
            )
            new = AnalysisSnapshot(
                date="2026-05-25", signal="持有", score=65, confidence=0.65,
                technical_summary="", fundamental_summary="",
                sentiment_summary="", key_changes=["RSI从65到75", "KDJ超买"],
            )
            change = service.analyze_signal_change(old, new)
            assert change.is_noise is True


# ==================== 历史分析服务测试 ====================

class TestAnalysisHistoryService:
    """历史分析对比服务测试"""

    def test_service_init(self):
        """测试服务初始化"""
        from astock_agents.services.analysis_history import AnalysisHistoryService
        with patch("astock_agents.services.analysis_history.Database"):
            service = AnalysisHistoryService()
            assert service is not None

    def test_get_analysis_history_empty(self):
        """测试获取空分析历史"""
        from astock_agents.services.analysis_history import AnalysisHistoryService
        with patch("astock_agents.services.analysis_history.Database") as MockDB:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_db.execute.return_value = mock_cursor
            MockDB.return_value = mock_db

            service = AnalysisHistoryService()
            result = service.get_analysis_history("600519.SH")
            assert isinstance(result, list)

    def test_get_signal_statistics_empty(self):
        """测试获取空信号统计"""
        from astock_agents.services.analysis_history import AnalysisHistoryService
        with patch("astock_agents.services.analysis_history.Database") as MockDB:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_db.execute.return_value = mock_cursor
            MockDB.return_value = mock_db

            service = AnalysisHistoryService()
            result = service.get_signal_statistics("600519.SH")
            assert "signal_distribution" in result
            assert "change_count" in result

    def test_compare_analyses_missing(self):
        """测试对比不存在的分析"""
        from astock_agents.services.analysis_history import AnalysisHistoryService
        with patch("astock_agents.services.analysis_history.Database") as MockDB:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_db.execute.return_value = mock_cursor
            MockDB.return_value = mock_db

            service = AnalysisHistoryService()
            result = service.compare_analyses(1, 2)
            # 当记录不存在时，返回包含空分析的对比结果
            assert isinstance(result, dict)

    def test_safe_parse_json(self):
        """测试JSON安全解析"""
        from astock_agents.services.analysis_history import AnalysisHistoryService
        with patch("astock_agents.services.analysis_history.Database"):
            service = AnalysisHistoryService()
            assert service._safe_parse_json('{"key": "value"}') == {"key": "value"}
            assert service._safe_parse_json("invalid") == {}
            assert service._safe_parse_json(None) == {}


# ==================== Web API集成测试 ====================

class TestNewWebAPI:
    """新增Web API集成测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi.testclient import TestClient
        from astock_agents.web.app import app
        return TestClient(app)

    def test_ws_status(self, client):
        """测试WebSocket状态API"""
        response = client.get("/api/ws/status")
        assert response.status_code == 200
        data = response.json()
        assert "active_connections" in data

    def test_trackers_list(self, client):
        """测试追踪列表API"""
        response = client.get("/api/trackers")
        assert response.status_code == 200

    def test_analysis_history(self, client):
        """测试分析历史API"""
        response = client.get("/api/analysis/history/600519.SH")
        assert response.status_code == 200

    def test_analysis_statistics(self, client):
        """测试信号统计API"""
        response = client.get("/api/analysis/statistics/600519.SH")
        assert response.status_code == 200

    def test_analysis_trend(self, client):
        """测试评分趋势API"""
        response = client.get("/api/analysis/trend/600519.SH")
        assert response.status_code == 200

    def test_analysis_search(self, client):
        """测试分析搜索API"""
        response = client.get("/api/analysis/search", params={"q": "茅台"})
        assert response.status_code == 200
