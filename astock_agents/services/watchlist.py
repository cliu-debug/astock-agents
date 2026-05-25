"""自选股管理 - 增删改查、分组管理、SQLite持久化"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from astock_agents.models.portfolio import WatchlistItem, WatchlistGroup, WatchlistGroupInfo
from astock_agents.db.database import Database


class WatchlistManager:
    """
    自选股管理器

    功能：
    1. 自选股增删改查
    2. 分组管理
    3. SQLite持久化
    4. 批量操作
    """

    def __init__(self, db: Optional[Database] = None):
        """
        初始化自选股管理器

        Args:
            db: 数据库实例，为空时自动创建默认实例
        """
        self._db = db or Database()
        self._items: List[WatchlistItem] = []
        self._load()
        logger.info(f"[自选股] 初始化完成, {len(self._items)}只股票")

    def add(self, item: WatchlistItem) -> bool:
        """添加自选股

        Args:
            item: 自选股条目

        Returns:
            是否添加成功
        """
        existing = self.get_by_code(item.stock_code)
        if existing:
            logger.warning(f"[自选股] 已存在: {item.stock_code}")
            return False

        self._items.append(item)
        self._save_item(item)
        logger.info(f"[自选股] 添加: {item.stock_name}({item.stock_code})")
        return True

    def remove(self, stock_code: str) -> bool:
        """移除自选股

        Args:
            stock_code: 股票代码

        Returns:
            是否移除成功
        """
        before = len(self._items)
        self._items = [i for i in self._items if i.stock_code != stock_code]
        if len(self._items) < before:
            self._db.remove_watchlist(stock_code)
            logger.info(f"[自选股] 移除: {stock_code}")
            return True
        return False

    def get_by_code(self, stock_code: str) -> Optional[WatchlistItem]:
        """按代码获取自选股

        Args:
            stock_code: 股票代码

        Returns:
            自选股条目，不存在时返回None
        """
        for item in self._items:
            if item.stock_code == stock_code:
                return item
        return None

    def get_all(self, group: Optional[WatchlistGroup] = None) -> List[WatchlistItem]:
        """获取所有自选股（可按分组筛选）

        Args:
            group: 分组枚举，为空时返回全部

        Returns:
            自选股条目列表
        """
        if group:
            return [i for i in self._items if i.group == group]
        return list(self._items)

    def update(self, stock_code: str, updates: Dict[str, Any]) -> bool:
        """更新自选股信息

        Args:
            stock_code: 股票代码
            updates: 需要更新的字段字典

        Returns:
            是否更新成功
        """
        item = self.get_by_code(stock_code)
        if not item:
            return False

        for key, value in updates.items():
            if hasattr(item, key):
                setattr(item, key, value)

        self._save_item(item)
        logger.info(f"[自选股] 更新: {stock_code}")
        return True

    def update_analysis_result(self, stock_code: str, signal: str) -> bool:
        """更新最近分析结果

        Args:
            stock_code: 股票代码
            signal: 信号类型

        Returns:
            是否更新成功
        """
        return self.update(stock_code, {
            "last_analyzed_at": datetime.now(),
            "last_signal": signal,
        })

    def get_groups(self) -> List[WatchlistGroupInfo]:
        """获取所有分组信息

        Returns:
            分组信息列表
        """
        group_counts: Dict[str, int] = {}
        for item in self._items:
            name = item.group.value
            group_counts[name] = group_counts.get(name, 0) + 1

        groups = []
        for group_enum in WatchlistGroup:
            groups.append(WatchlistGroupInfo(
                name=group_enum.value,
                count=group_counts.get(group_enum.value, 0),
            ))
        return groups

    def move_to_group(self, stock_code: str, group: WatchlistGroup) -> bool:
        """移动到指定分组

        Args:
            stock_code: 股票代码
            group: 目标分组

        Returns:
            是否移动成功
        """
        return self.update(stock_code, {"group": group})

    def search(self, keyword: str) -> List[WatchlistItem]:
        """搜索自选股（按代码或名称）

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的自选股列表
        """
        keyword = keyword.lower()
        return [
            i for i in self._items
            if keyword in i.stock_code.lower() or keyword in i.stock_name.lower()
        ]

    def count(self) -> int:
        """获取自选股总数

        Returns:
            自选股数量
        """
        return len(self._items)

    def _save_item(self, item: WatchlistItem) -> None:
        """保存单条自选股到数据库

        Args:
            item: 自选股条目
        """
        self._db.add_watchlist(
            stock_code=item.stock_code,
            stock_name=item.stock_name,
            group=item.group.value,
            tags=json.dumps(item.tags, ensure_ascii=False),
            reason=item.reason,
            target_price=item.target_price,
            stop_loss=item.stop_loss,
            notes=item.notes,
        )
        # 同步更新 last_analyzed_at 和 last_signal
        updates: Dict[str, Any] = {}
        if item.last_analyzed_at is not None:
            updates["last_analyzed_at"] = item.last_analyzed_at.isoformat()
        if item.last_signal is not None:
            updates["last_signal"] = item.last_signal
        if item.added_at is not None:
            updates["added_at"] = item.added_at.isoformat()
        if updates:
            self._db.update_watchlist(item.stock_code, updates)

    def _load(self) -> None:
        """从数据库加载自选股到内存"""
        try:
            rows = self._db.get_watchlist()
            self._items = []
            for row in rows:
                tags = row.get("tags", "[]")
                if isinstance(tags, str):
                    tags = json.loads(tags)
                self._items.append(WatchlistItem(
                    stock_code=row["stock_code"],
                    stock_name=row["stock_name"],
                    group=WatchlistGroup(row.get("group_name", "默认")),
                    tags=tags,
                    reason=row.get("reason"),
                    target_price=row.get("target_price"),
                    stop_loss=row.get("stop_loss"),
                    added_at=self._parse_datetime(row.get("added_at")),
                    last_analyzed_at=self._parse_datetime(row.get("last_analyzed_at")),
                    last_signal=row.get("last_signal"),
                    notes=row.get("notes"),
                ))
        except Exception as e:
            logger.warning(f"[自选股] 加载失败: {e}, 使用空列表")
            self._items = []

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """解析数据库中的时间字符串

        Args:
            value: 时间字符串

        Returns:
            datetime对象，输入为空时返回None
        """
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            return None
