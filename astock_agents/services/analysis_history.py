"""历史分析对比服务 - 分析历史查询、对比、统计与趋势"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from astock_agents.db.database import Database


class AnalysisHistoryService:
    """
    历史分析对比服务

    功能：
    1. 获取股票分析历史记录
    2. 对比两次分析结果差异
    3. 统计信号分布与置信度
    4. 获取评分趋势时间序列
    5. 搜索分析记录
    """

    def __init__(self, db: Optional[Database] = None):
        """
        初始化历史分析对比服务

        Args:
            db: 数据库实例，为空时自动创建默认实例
        """
        self._db = db or Database()
        self._ensure_table()
        logger.info("[历史分析] 初始化完成")

    def _ensure_table(self) -> None:
        """确保 analysis_results 表存在，不存在则创建"""
        conn = self._db._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    signal TEXT,
                    confidence INTEGER,
                    report_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        except Exception as e:
            logger.error(f"[历史分析] 建表失败: {e}")
        finally:
            conn.close()

    @staticmethod
    def _safe_parse_json(json_str: Optional[str]) -> Dict[str, Any]:
        """
        安全解析 JSON 字符串

        Args:
            json_str: JSON 格式字符串

        Returns:
            解析后的字典，解析失败时返回空字典
        """
        if not json_str:
            return {}
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"[历史分析] JSON解析失败: {e}")
            return {}

    def get_analysis_history(self, stock_code: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取某股票的分析历史

        Args:
            stock_code: 股票代码
            limit: 返回条数上限，默认20

        Returns:
            分析结果字典列表，按分析时间倒序排列，
            每项包含 id, stock_code, stock_name, signal, confidence, analyzed_at, report_json
        """
        try:
            conn = self._db._get_conn()
            rows = conn.execute(
                "SELECT id, stock_code, stock_name, signal, confidence, "
                "created_at AS analyzed_at, report_json "
                "FROM analysis_results WHERE stock_code=? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (stock_code, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[历史分析] 获取分析历史失败: {e}")
            return []
        finally:
            conn.close()

    def compare_analyses(self, analysis_id_1: int, analysis_id_2: int) -> Dict[str, Any]:
        """
        对比两次分析结果

        Args:
            analysis_id_1: 第一次分析的记录ID
            analysis_id_2: 第二次分析的记录ID

        Returns:
            对比结果字典，包含：
            - analysis_1: 第一次分析详情
            - analysis_2: 第二次分析详情
            - changes: 各维度变化（signal_change, confidence_change,
                       technical_changes, fundamental_changes, sentiment_changes）
        """
        empty_result: Dict[str, Any] = {
            "analysis_1": {},
            "analysis_2": {},
            "changes": {},
        }
        try:
            conn = self._db._get_conn()
            row1 = conn.execute(
                "SELECT * FROM analysis_results WHERE id=?", (analysis_id_1,)
            ).fetchone()
            row2 = conn.execute(
                "SELECT * FROM analysis_results WHERE id=?", (analysis_id_2,)
            ).fetchone()
        except Exception as e:
            logger.error(f"[历史分析] 对比分析查询失败: {e}")
            return empty_result
        finally:
            conn.close()

        if not row1 or not row2:
            logger.warning(
                f"[历史分析] 对比分析: 未找到记录 id1={analysis_id_1} id2={analysis_id_2}"
            )
            return empty_result

        analysis_1 = dict(row1)
        analysis_2 = dict(row2)

        report_1 = self._safe_parse_json(analysis_1.get("report_json"))
        report_2 = self._safe_parse_json(analysis_2.get("report_json"))

        # 信号变化
        signal_1 = analysis_1.get("signal", "")
        signal_2 = analysis_2.get("signal", "")
        signal_change = signal_1 != signal_2

        # 置信度变化
        confidence_1 = analysis_1.get("confidence", 0) or 0
        confidence_2 = analysis_2.get("confidence", 0) or 0
        confidence_change = confidence_2 - confidence_1

        # 技术面变化
        technical_changes = self._compare_dimension(
            report_1.get("technical", {}), report_2.get("technical", {})
        )

        # 基本面变化
        fundamental_changes = self._compare_dimension(
            report_1.get("fundamental", {}), report_2.get("fundamental", {})
        )

        # 情绪面变化
        sentiment_changes = self._compare_dimension(
            report_1.get("sentiment", {}), report_2.get("sentiment", {})
        )

        changes: Dict[str, Any] = {
            "signal_change": signal_change,
            "signal_from": signal_1,
            "signal_to": signal_2,
            "confidence_change": confidence_change,
            "confidence_from": confidence_1,
            "confidence_to": confidence_2,
            "technical_changes": technical_changes,
            "fundamental_changes": fundamental_changes,
            "sentiment_changes": sentiment_changes,
        }

        return {
            "analysis_1": analysis_1,
            "analysis_2": analysis_2,
            "changes": changes,
        }

    @staticmethod
    def _compare_dimension(
        dim_1: Dict[str, Any], dim_2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        对比两个维度的数据变化

        提取共有键的值进行对比，标记新增、删除和变化的字段。

        Args:
            dim_1: 第一次分析的维度数据
            dim_2: 第二次分析的维度数据

        Returns:
            维度变化字典，包含 changed, added, removed 详情
        """
        if not dim_1 and not dim_2:
            return {"changed": {}, "added": {}, "removed": {}}

        keys_1 = set(dim_1.keys())
        keys_2 = set(dim_2.keys())

        added = {k: dim_2[k] for k in keys_2 - keys_1}
        removed = {k: dim_1[k] for k in keys_1 - keys_2}

        changed: Dict[str, Any] = {}
        for k in keys_1 & keys_2:
            val_1 = dim_1[k]
            val_2 = dim_2[k]
            if val_1 != val_2:
                changed[k] = {"from": val_1, "to": val_2}

        return {"changed": changed, "added": added, "removed": removed}

    def get_signal_statistics(self, stock_code: str, days: int = 30) -> Dict[str, Any]:
        """
        获取信号统计

        Args:
            stock_code: 股票代码
            days: 统计天数，默认30

        Returns:
            信号统计字典，包含：
            - signal_distribution: 信号分布（买入/持有/卖出各多少次）
            - change_count: 信号变化次数
            - avg_confidence: 平均置信度
            - max_confidence: 最高置信度
            - min_confidence: 最低置信度
        """
        empty_stats: Dict[str, Any] = {
            "signal_distribution": {},
            "change_count": 0,
            "avg_confidence": 0,
            "max_confidence": 0,
            "min_confidence": 0,
        }
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat()
            conn = self._db._get_conn()
            rows = conn.execute(
                "SELECT signal, confidence FROM analysis_results "
                "WHERE stock_code=? AND created_at>=? "
                "ORDER BY created_at ASC, id ASC",
                (stock_code, since),
            ).fetchall()
        except Exception as e:
            logger.error(f"[历史分析] 获取信号统计失败: {e}")
            return empty_stats
        finally:
            conn.close()

        if not rows:
            return empty_stats

        # 信号分布
        signal_distribution: Dict[str, int] = {}
        for row in rows:
            signal = row["signal"] or "未知"
            signal_distribution[signal] = signal_distribution.get(signal, 0) + 1

        # 信号变化次数
        change_count = 0
        prev_signal: Optional[str] = None
        for row in rows:
            current_signal = row["signal"]
            if prev_signal is not None and current_signal != prev_signal:
                change_count += 1
            prev_signal = current_signal

        # 置信度统计
        confidences = [row["confidence"] for row in rows if row["confidence"] is not None]
        if confidences:
            avg_confidence = round(sum(confidences) / len(confidences), 2)
            max_confidence = max(confidences)
            min_confidence = min(confidences)
        else:
            avg_confidence = 0
            max_confidence = 0
            min_confidence = 0

        return {
            "signal_distribution": signal_distribution,
            "change_count": change_count,
            "avg_confidence": avg_confidence,
            "max_confidence": max_confidence,
            "min_confidence": min_confidence,
        }

    def get_score_trend(self, stock_code: str, days: int = 90) -> List[Dict[str, Any]]:
        """
        获取评分趋势

        Args:
            stock_code: 股票代码
            days: 查询天数，默认90

        Returns:
            时间序列列表，每项包含 date, signal, confidence，
            用于前端绘制信号变化时间线图
        """
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat()
            conn = self._db._get_conn()
            rows = conn.execute(
                "SELECT created_at, signal, confidence FROM analysis_results "
                "WHERE stock_code=? AND created_at>=? "
                "ORDER BY created_at ASC, id ASC",
                (stock_code, since),
            ).fetchall()
            return [
                {
                    "date": row["created_at"],
                    "signal": row["signal"],
                    "confidence": row["confidence"],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"[历史分析] 获取评分趋势失败: {e}")
            return []
        finally:
            conn.close()

    def search_analyses(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        搜索分析记录

        支持按股票代码、名称搜索，返回简要信息列表。

        Args:
            query: 搜索关键词（匹配股票代码或名称）
            limit: 返回条数上限，默认50

        Returns:
            分析记录简要信息列表，每项包含 id, stock_code, stock_name, signal, confidence, analyzed_at
        """
        if not query or not query.strip():
            return []
        try:
            keyword = f"%{query.strip()}%"
            conn = self._db._get_conn()
            rows = conn.execute(
                "SELECT id, stock_code, stock_name, signal, confidence, "
                "created_at AS analyzed_at FROM analysis_results "
                "WHERE stock_code LIKE ? OR stock_name LIKE ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (keyword, keyword, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[历史分析] 搜索分析记录失败: {e}")
            return []
        finally:
            conn.close()


# ---- 全局单例 ----

_analysis_history_service: Optional[AnalysisHistoryService] = None


def get_analysis_history_service() -> AnalysisHistoryService:
    """
    获取历史分析对比服务全局单例

    Returns:
        AnalysisHistoryService 实例
    """
    global _analysis_history_service
    if _analysis_history_service is None:
        _analysis_history_service = AnalysisHistoryService()
    return _analysis_history_service
