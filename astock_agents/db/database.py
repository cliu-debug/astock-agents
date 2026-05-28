"""SQLite数据库管理 - 提供持久化存储能力

支持表：
- analysis_results: 分析结果存储
- watchlist: 自选股
- trade_orders: 交易订单
- positions: 持仓
- trade_records: 交易记录（复盘用）
- user_memory: 用户记忆（年轮记忆算法）
- debate_history: 辩论历史记录
"""

import os
import sqlite3
from typing import List, Optional, Dict, Any
from loguru import logger


class Database:
    """SQLite数据库管理器

    通过环境变量 ASTOCK_DB_PATH 设置数据库路径，默认 ./data/astock.db。
    首次连接时自动建表，启用 WAL 模式提升并发性能。
    """

    DEFAULT_DB_PATH = "./data/astock.db"

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径，为空时从环境变量 ASTOCK_DB_PATH 读取，
                     再为空则使用默认值 ./data/astock.db
        """
        self.db_path: str = db_path or os.environ.get("ASTOCK_DB_PATH", self.DEFAULT_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_tables()
        logger.info(f"[DB] 初始化完成: {self.db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接（启用WAL模式和行工厂）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_tables(self):
        """首次连接时自动建表和索引"""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    signal TEXT,
                    confidence INTEGER,
                    report_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_analysis_stock ON analysis_results(stock_code);
                CREATE INDEX IF NOT EXISTS idx_analysis_time ON analysis_results(created_at);

                CREATE TABLE IF NOT EXISTS watchlist (
                    stock_code TEXT PRIMARY KEY,
                    stock_name TEXT NOT NULL,
                    group_name TEXT DEFAULT '默认',
                    tags TEXT DEFAULT '[]',
                    reason TEXT,
                    target_price REAL,
                    stop_loss REAL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_analyzed_at TIMESTAMP,
                    last_signal TEXT,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS trade_orders (
                    order_id TEXT PRIMARY KEY,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    direction TEXT NOT NULL,
                    order_type TEXT DEFAULT '市价单',
                    quantity INTEGER NOT NULL,
                    price REAL,
                    filled_price REAL,
                    filled_quantity INTEGER DEFAULT 0,
                    status TEXT DEFAULT '待成交',
                    commission REAL DEFAULT 0,
                    stamp_tax REAL DEFAULT 0,
                    reason TEXT,
                    signal_source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    filled_at TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS positions (
                    stock_code TEXT PRIMARY KEY,
                    stock_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    available_quantity INTEGER NOT NULL,
                    avg_cost REAL NOT NULL,
                    current_price REAL,
                    realized_pnl REAL DEFAULT 0,
                    first_buy_at TIMESTAMP,
                    last_trade_at TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS trade_records (
                    record_id TEXT PRIMARY KEY,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    buy_price REAL,
                    buy_quantity INTEGER,
                    buy_time TIMESTAMP,
                    buy_reason TEXT,
                    sell_price REAL,
                    sell_quantity INTEGER,
                    sell_time TIMESTAMP,
                    sell_reason TEXT,
                    holding_days INTEGER,
                    realized_pnl REAL,
                    realized_pnl_pct REAL,
                    status TEXT DEFAULT '持有中',
                    signal_at_buy TEXT,
                    signal_at_sell TEXT
                );

                CREATE TABLE IF NOT EXISTS user_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    stock_code TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    signal TEXT,
                    confidence INTEGER,
                    amount REAL,
                    price REAL,
                    industry TEXT,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_user_memory_user ON user_memory(user_id);
                CREATE INDEX IF NOT EXISTS idx_user_memory_stock ON user_memory(user_id, stock_code);
                CREATE INDEX IF NOT EXISTS idx_user_memory_time ON user_memory(created_at);

                CREATE TABLE IF NOT EXISTS debate_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    debate_rounds INTEGER DEFAULT 1,
                    debate_history_json TEXT DEFAULT '[]',
                    votes_json TEXT DEFAULT '{}',
                    cooperation_score REAL DEFAULT 0.5,
                    nash_equilibrium TEXT,
                    winning_side TEXT,
                    debate_summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_debate_history_stock ON debate_history(stock_code);
                CREATE INDEX IF NOT EXISTS idx_debate_history_time ON debate_history(created_at);

                CREATE TABLE IF NOT EXISTS dialogue_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    stock_code TEXT DEFAULT '',
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    intent TEXT DEFAULT 'general',
                    target_agent TEXT DEFAULT 'trader',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_dialogue_session ON dialogue_history(session_id);
                CREATE INDEX IF NOT EXISTS idx_dialogue_time ON dialogue_history(created_at);

                CREATE TABLE IF NOT EXISTS feedback_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    stock_code TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    feedback_text TEXT DEFAULT '',
                    actual_outcome TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_records(user_id);
                CREATE INDEX IF NOT EXISTS idx_feedback_stock ON feedback_records(stock_code);
            """)
            conn.commit()
        finally:
            conn.close()

    # ---- 分析结果 ----

    def save_analysis(
        self,
        stock_code: str,
        stock_name: str,
        signal: str,
        confidence: int,
        report_json: str,
    ) -> None:
        """保存分析结果

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            signal: 信号类型
            confidence: 置信度
            report_json: 完整报告JSON字符串
        """
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO analysis_results (stock_code, stock_name, signal, confidence, report_json) VALUES (?,?,?,?,?)",
                (stock_code, stock_name, signal, confidence, report_json),
            )
            conn.commit()
        finally:
            conn.close()

    def get_analysis_history(self, stock_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取分析历史记录

        Args:
            stock_code: 股票代码
            limit: 返回条数上限

        Returns:
            分析结果字典列表，按时间倒序
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM analysis_results WHERE stock_code=? ORDER BY created_at DESC LIMIT ?",
                (stock_code, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---- 对话历史 ----

    def save_dialogue_history(
        self,
        session_id: str,
        question: str,
        answer: str,
        intent: str = "general",
        target_agent: str = "trader",
        stock_code: str = "",
    ) -> int:
        """保存对话历史

        Args:
            session_id: 会话ID
            question: 用户提问
            answer: 系统回答
            intent: 意图
            target_agent: 目标智能体
            stock_code: 股票代码

        Returns:
            插入记录的ID
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO dialogue_history
                (session_id, stock_code, question, answer, intent, target_agent)
                VALUES (?,?,?,?,?,?)""",
                (session_id, stock_code, question, answer, intent, target_agent),
            )
            conn.commit()
            return cursor.lastrowid or 0
        finally:
            conn.close()

    def get_dialogue_history(
        self,
        session_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取对话历史

        Args:
            session_id: 会话ID
            limit: 返回条数上限

        Returns:
            对话历史字典列表，按时间倒序
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM dialogue_history WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---- 反馈记录 ----

    def save_feedback(
        self,
        user_id: str,
        stock_code: str,
        signal: str,
        feedback_type: str,
        feedback_text: str = "",
        actual_outcome: str = "",
    ) -> int:
        """保存用户反馈

        Args:
            user_id: 用户ID
            stock_code: 股票代码
            signal: 当时的信号
            feedback_type: 反馈类型(agree/disagree/neutral)
            feedback_text: 反馈文本
            actual_outcome: 实际结果

        Returns:
            插入记录的ID
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO feedback_records
                (user_id, stock_code, signal, feedback_type, feedback_text, actual_outcome)
                VALUES (?,?,?,?,?,?)""",
                (user_id, stock_code, signal, feedback_type, feedback_text, actual_outcome),
            )
            conn.commit()
            return cursor.lastrowid or 0
        finally:
            conn.close()

    def get_feedback_history(
        self,
        user_id: str,
        stock_code: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取反馈历史

        Args:
            user_id: 用户ID
            stock_code: 股票代码（可选）
            limit: 返回条数上限

        Returns:
            反馈记录字典列表
        """
        conn = self._get_conn()
        try:
            if stock_code:
                rows = conn.execute(
                    "SELECT * FROM feedback_records WHERE user_id=? AND stock_code=? ORDER BY created_at DESC LIMIT ?",
                    (user_id, stock_code, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM feedback_records WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_feedback_stats(self, user_id: str) -> Dict[str, Any]:
        """获取反馈统计（用于持续学习）

        Args:
            user_id: 用户ID

        Returns:
            反馈统计字典
        """
        conn = self._get_conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM feedback_records WHERE user_id=?",
                (user_id,),
            ).fetchone()

            agree = conn.execute(
                "SELECT COUNT(*) as cnt FROM feedback_records WHERE user_id=? AND feedback_type='agree'",
                (user_id,),
            ).fetchone()

            disagree = conn.execute(
                "SELECT COUNT(*) as cnt FROM feedback_records WHERE user_id=? AND feedback_type='disagree'",
                (user_id,),
            ).fetchone()

            signal_accuracy = conn.execute(
                """SELECT signal, feedback_type, COUNT(*) as cnt
                FROM feedback_records WHERE user_id=?
                GROUP BY signal, feedback_type""",
                (user_id,),
            ).fetchall()

            total_cnt = dict(total).get("cnt", 0) if total else 0
            agree_cnt = dict(agree).get("cnt", 0) if agree else 0
            disagree_cnt = dict(disagree).get("cnt", 0) if disagree else 0

            accuracy = agree_cnt / max(total_cnt, 1) * 100

            signal_stats = {}
            for row in signal_accuracy:
                r = dict(row)
                sig = r.get("signal", "unknown")
                fb = r.get("feedback_type", "unknown")
                cnt = r.get("cnt", 0)
                if sig not in signal_stats:
                    signal_stats[sig] = {}
                signal_stats[sig][fb] = cnt

            return {
                "total_feedbacks": total_cnt,
                "agree_count": agree_cnt,
                "disagree_count": disagree_cnt,
                "accuracy_rate": round(accuracy, 1),
                "signal_accuracy": signal_stats,
            }
        finally:
            conn.close()

    # ---- 自选股 ----

    def get_watchlist(self, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取自选股列表

        Args:
            group: 分组名称，为空时返回全部

        Returns:
            自选股字典列表
        """
        conn = self._get_conn()
        try:
            if group:
                rows = conn.execute("SELECT * FROM watchlist WHERE group_name=?", (group,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM watchlist ORDER BY added_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def add_watchlist(
        self,
        stock_code: str,
        stock_name: str,
        group: str = "默认",
        tags: str = "[]",
        reason: Optional[str] = None,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """添加自选股（已存在则替换）

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            group: 分组名称
            tags: 标签JSON字符串
            reason: 加入自选理由
            target_price: 目标价
            stop_loss: 止损价
            notes: 备注

        Returns:
            是否添加成功
        """
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO watchlist
                (stock_code, stock_name, group_name, tags, reason, target_price, stop_loss, notes)
                VALUES (?,?,?,?,?,?,?,?)""",
                (stock_code, stock_name, group, tags, reason, target_price, stop_loss, notes),
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def remove_watchlist(self, stock_code: str) -> bool:
        """移除自选股

        Args:
            stock_code: 股票代码

        Returns:
            是否移除成功（不存在时返回False）
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM watchlist WHERE stock_code=?", (stock_code,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # update_watchlist 允许更新的列名白名单
    WATCHLIST_UPDATABLE_COLUMNS = {"stock_code", "stock_name", "group_name", "notes", "last_signal"}

    def update_watchlist(self, stock_code: str, updates: Dict[str, Any]) -> bool:
        """更新自选股字段

        Args:
            stock_code: 股票代码
            updates: 需要更新的字段字典

        Returns:
            是否更新成功
        """
        if not updates:
            return False

        # 白名单校验：只允许已知列名，防止SQL注入
        filtered_updates = {
            k: v for k, v in updates.items()
            if k in self.WATCHLIST_UPDATABLE_COLUMNS
        }
        if not filtered_updates:
            logger.warning(f"[DB] update_watchlist: 无合法列名，已拒绝更新 {list(updates.keys())}")
            return False

        conn = self._get_conn()
        try:
            set_clause = ", ".join(f"{k}=?" for k in filtered_updates.keys())
            values = list(filtered_updates.values()) + [stock_code]
            cursor = conn.execute(
                f"UPDATE watchlist SET {set_clause} WHERE stock_code=?",
                values,
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False
        finally:
            conn.close()

    # ---- 交易订单 ----

    def save_order(self, order: Dict[str, Any]) -> bool:
        """保存交易订单（已存在则替换）

        Args:
            order: 订单字典，需包含 order_id 等字段

        Returns:
            是否保存成功
        """
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO trade_orders
                (order_id, stock_code, stock_name, direction, order_type, quantity, price,
                 filled_price, filled_quantity, status, commission, stamp_tax, reason, signal_source, filled_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    order.get("order_id"), order.get("stock_code"), order.get("stock_name"),
                    order.get("direction"), order.get("order_type"), order.get("quantity"),
                    order.get("price"), order.get("filled_price"), order.get("filled_quantity"),
                    order.get("status"), order.get("commission"), order.get("stamp_tax"),
                    order.get("reason"), order.get("signal_source"), order.get("filled_at"),
                ),
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def get_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取交易订单列表

        Args:
            limit: 返回条数上限

        Returns:
            订单字典列表，按创建时间倒序
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM trade_orders ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---- 持仓 ----

    def get_positions(self) -> List[Dict[str, Any]]:
        """获取所有持仓

        Returns:
            持仓字典列表
        """
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM positions").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def upsert_position(self, pos: Dict[str, Any]) -> None:
        """插入或更新持仓

        Args:
            pos: 持仓字典，需包含 stock_code 等字段
        """
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO positions
                (stock_code, stock_name, quantity, available_quantity, avg_cost, current_price, realized_pnl, first_buy_at, last_trade_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    pos.get("stock_code"), pos.get("stock_name"), pos.get("quantity"),
                    pos.get("available_quantity"), pos.get("avg_cost"), pos.get("current_price"),
                    pos.get("realized_pnl", 0), pos.get("first_buy_at"), pos.get("last_trade_at"),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_position(self, stock_code: str) -> None:
        """删除持仓

        Args:
            stock_code: 股票代码
        """
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM positions WHERE stock_code=?", (stock_code,))
            conn.commit()
        finally:
            conn.close()

    # ---- 交易记录 ----

    def save_trade_record(self, record: Dict[str, Any]) -> None:
        """保存交易记录（买入到卖出的完整周期）

        Args:
            record: 交易记录字典，需包含 record_id 等字段
        """
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO trade_records
                (record_id, stock_code, stock_name, buy_price, buy_quantity, buy_time, buy_reason,
                 sell_price, sell_quantity, sell_time, sell_reason, holding_days, realized_pnl,
                 realized_pnl_pct, status, signal_at_buy, signal_at_sell)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.get("record_id"), record.get("stock_code"), record.get("stock_name"),
                    record.get("buy_price"), record.get("buy_quantity"), record.get("buy_time"),
                    record.get("buy_reason"), record.get("sell_price"), record.get("sell_quantity"),
                    record.get("sell_time"), record.get("sell_reason"), record.get("holding_days"),
                    record.get("realized_pnl"), record.get("realized_pnl_pct"), record.get("status"),
                    record.get("signal_at_buy"), record.get("signal_at_sell"),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_trade_records(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取交易记录

        Args:
            status: 状态筛选（如 '持有中'、'已平仓'），为空时返回全部

        Returns:
            交易记录字典列表，按买入时间倒序
        """
        conn = self._get_conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM trade_records WHERE status=?", (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM trade_records ORDER BY buy_time DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---- 用户记忆 ----

    def save_user_memory(
        self,
        user_id: str,
        stock_code: str,
        action_type: str,
        signal: Optional[str] = None,
        confidence: Optional[int] = None,
        amount: Optional[float] = None,
        price: Optional[float] = None,
        industry: Optional[str] = None,
        metadata: Optional[str] = "{}",
    ) -> None:
        """保存用户记忆记录

        Args:
            user_id: 用户ID
            stock_code: 股票代码
            action_type: 行为类型（analysis/trade）
            signal: 信号
            confidence: 置信度
            amount: 交易金额
            price: 交易价格
            industry: 所属行业
            metadata: 附加信息JSON字符串
        """
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO user_memory
                (user_id, stock_code, action_type, signal, confidence, amount, price, industry, metadata)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (user_id, stock_code, action_type, signal, confidence, amount, price, industry, metadata),
            )
            conn.commit()
        finally:
            conn.close()

    def get_user_memories(
        self,
        user_id: str,
        stock_code: Optional[str] = None,
        action_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取用户记忆记录

        Args:
            user_id: 用户ID
            stock_code: 股票代码（可选，为空时返回全部）
            action_type: 行为类型筛选（可选）
            limit: 返回条数上限

        Returns:
            记忆记录字典列表，按时间倒序
        """
        conn = self._get_conn()
        try:
            query = "SELECT * FROM user_memory WHERE user_id=?"
            params: list = [user_id]

            if stock_code:
                query += " AND stock_code=?"
                params.append(stock_code)
            if action_type:
                query += " AND action_type=?"
                params.append(action_type)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_user_industry_stats(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户按行业的分析频率统计

        Args:
            user_id: 用户ID

        Returns:
            行业统计列表，包含 industry 和 count 字段
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT industry, COUNT(*) as count
                FROM user_memory
                WHERE user_id=? AND industry IS NOT NULL AND industry != ''
                GROUP BY industry
                ORDER BY count DESC""",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---- 辩论历史 ----

    def save_debate_history(
        self,
        stock_code: str,
        debate_rounds: int,
        debate_history_json: str,
        votes_json: str,
        cooperation_score: float,
        nash_equilibrium: Optional[str] = None,
        winning_side: Optional[str] = None,
        debate_summary: Optional[str] = None,
    ) -> int:
        """保存辩论历史记录

        Args:
            stock_code: 股票代码
            debate_rounds: 辩论轮数
            debate_history_json: 辩论历史JSON字符串
            votes_json: 投票结果JSON字符串
            cooperation_score: 合作度评分
            nash_equilibrium: 纳什均衡分析
            winning_side: 获胜方
            debate_summary: 辩论总结

        Returns:
            插入记录的ID
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO debate_history
                (stock_code, debate_rounds, debate_history_json, votes_json,
                 cooperation_score, nash_equilibrium, winning_side, debate_summary)
                VALUES (?,?,?,?,?,?,?,?)""",
                (stock_code, debate_rounds, debate_history_json, votes_json,
                 cooperation_score, nash_equilibrium, winning_side, debate_summary),
            )
            conn.commit()
            return cursor.lastrowid or 0
        finally:
            conn.close()

    def get_debate_history(
        self,
        stock_code: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取辩论历史记录

        Args:
            stock_code: 股票代码
            limit: 返回条数上限

        Returns:
            辩论历史字典列表，按时间倒序
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM debate_history WHERE stock_code=? ORDER BY created_at DESC LIMIT ?",
                (stock_code, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
