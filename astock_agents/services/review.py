"""交易复盘与归因分析"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from astock_agents.models.portfolio import TradeRecord, ReviewReport
from astock_agents.db.database import Database


class ReviewService:
    """
    交易复盘服务

    功能：
    1. 交易记录归档
    2. 盈亏归因分析
    3. 胜率/盈亏比统计
    4. 常见错误识别
    5. 改进建议生成
    """

    def __init__(self, db: Optional[Database] = None):
        """
        初始化复盘服务

        Args:
            db: 数据库实例，为空时自动创建默认实例
        """
        self._db = db or Database()
        self.records: List[TradeRecord] = []
        self._load_from_db()
        logger.info(f"[复盘] 初始化完成, 已加载{len(self.records)}条记录")

    def add_record(self, record: TradeRecord):
        """添加交易记录"""
        self.records.append(record)
        logger.info(f"[复盘] 添加记录: {record.stock_name} {record.status}")

    def add_from_trade_history(self, trade_history: List[Dict[str, Any]]):
        """从交易历史构建交易记录"""
        # 按股票分组，配对买卖
        stock_trades: Dict[str, List[Dict]] = {}
        for trade in trade_history:
            code = trade.get("stock_code", "")
            if code not in stock_trades:
                stock_trades[code] = []
            stock_trades[code].append(trade)

        # 配对买卖
        for code, trades in stock_trades.items():
            buys = [t for t in trades if t.get("direction") == "买入"]
            sells = [t for t in trades if t.get("direction") == "卖出"]

            for buy in buys:
                record_id = f"REC-{buy.get('order_id', '')}"
                record = TradeRecord(
                    record_id=record_id,
                    stock_code=code,
                    stock_name=buy.get("stock_name", ""),
                    buy_price=buy.get("price", 0),
                    buy_quantity=buy.get("quantity", 0),
                    buy_time=datetime.fromisoformat(buy["time"]) if "time" in buy else datetime.now(),
                    buy_reason=buy.get("reason"),
                    signal_at_buy=buy.get("signal_source"),
                )

                # 查找对应的卖出
                if sells:
                    sell = sells.pop(0)
                    record.sell_price = sell.get("price")
                    record.sell_quantity = sell.get("quantity")
                    record.sell_time = datetime.fromisoformat(sell["time"]) if "time" in sell else datetime.now()
                    record.sell_reason = sell.get("reason")
                    record.signal_at_sell = sell.get("signal_source")
                    record.status = "已平仓"

                    # 计算盈亏
                    if record.sell_price and record.buy_price:
                        record.realized_pnl = (record.sell_price - record.buy_price) * record.buy_quantity
                        record.realized_pnl_pct = round(
                            (record.sell_price - record.buy_price) / record.buy_price * 100, 2
                        )

                    # 持仓天数
                    if record.buy_time and record.sell_time:
                        record.holding_days = (record.sell_time - record.buy_time).days

                self.records.append(record)

    def generate_report(self, period: Optional[str] = None) -> ReviewReport:
        """
        生成复盘报告

        Args:
            period: 复盘周期（如 "2024-Q1"），为空则全量

        Returns:
            复盘报告
        """
        if not period:
            period = datetime.now().strftime("%Y-%m")

        # 筛选已平仓记录
        closed_records = [r for r in self.records if r.status == "已平仓"]

        if not closed_records:
            return ReviewReport(period=period)

        # 基础统计
        total_trades = len(closed_records)
        win_trades = sum(1 for r in closed_records if r.realized_pnl and r.realized_pnl > 0)
        loss_trades = sum(1 for r in closed_records if r.realized_pnl and r.realized_pnl <= 0)
        win_rate = round(win_trades / total_trades * 100, 1) if total_trades > 0 else 0

        # 盈亏统计
        total_pnl = sum(r.realized_pnl or 0 for r in closed_records)
        avg_pnl = round(total_pnl / total_trades, 2) if total_trades > 0 else 0

        # 持仓天数
        holding_days_list = [r.holding_days for r in closed_records if r.holding_days is not None]
        avg_holding_days = round(sum(holding_days_list) / len(holding_days_list), 1) if holding_days_list else 0

        # 单笔最大盈亏
        pnl_pcts = [r.realized_pnl_pct for r in closed_records if r.realized_pnl_pct is not None]
        max_gain = max(pnl_pcts) if pnl_pcts else None
        max_loss = min(pnl_pcts) if pnl_pcts else None

        # 盈亏比
        total_profit = sum(r.realized_pnl for r in closed_records if r.realized_pnl and r.realized_pnl > 0)
        total_loss = abs(sum(r.realized_pnl for r in closed_records if r.realized_pnl and r.realized_pnl < 0))
        profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else None

        # 最佳/最差标的
        best = max(closed_records, key=lambda r: r.realized_pnl_pct or 0)
        worst = min(closed_records, key=lambda r: r.realized_pnl_pct or 0)

        # 识别常见错误
        mistakes = self._identify_mistakes(closed_records)

        # 生成改进建议
        suggestions = self._generate_suggestions(closed_records, win_rate, profit_factor)

        report = ReviewReport(
            period=period,
            total_trades=total_trades,
            win_trades=win_trades,
            loss_trades=loss_trades,
            win_rate=win_rate,
            total_pnl=round(total_pnl, 2),
            avg_pnl_per_trade=avg_pnl,
            avg_holding_days=avg_holding_days,
            max_single_gain_pct=max_gain,
            max_single_loss_pct=max_loss,
            profit_factor=profit_factor,
            best_stock=f"{best.stock_name}({best.realized_pnl_pct}%)",
            worst_stock=f"{worst.stock_name}({worst.realized_pnl_pct}%)",
            common_mistakes=mistakes,
            improvement_suggestions=suggestions,
            records=closed_records,
        )

        logger.info(f"[复盘] 报告生成: {period}, {total_trades}笔, 胜率{win_rate}%")
        return report

    def _identify_mistakes(self, records: List[TradeRecord]) -> List[str]:
        """识别常见交易错误"""
        mistakes = []

        # 1. 频繁交易（持仓天数过短）
        short_holds = [r for r in records if r.holding_days is not None and r.holding_days <= 2]
        if len(short_holds) > len(records) * 0.3:
            mistakes.append("频繁交易：超过30%的持仓不足3天，可能受情绪驱动")

        # 2. 亏损持仓时间过长
        loss_records = [r for r in records if r.realized_pnl and r.realized_pnl < 0]
        if loss_records:
            avg_loss_days = sum(r.holding_days or 0 for r in loss_records) / len(loss_records)
            win_records = [r for r in records if r.realized_pnl and r.realized_pnl > 0]
            if win_records:
                avg_win_days = sum(r.holding_days or 0 for r in win_records) / len(win_records)
                if avg_loss_days > avg_win_days * 1.5:
                    mistakes.append("截断利润让亏损奔跑：亏损持仓时间远超盈利持仓时间")

        # 3. 单笔亏损过大
        big_losses = [r for r in records if r.realized_pnl_pct and r.realized_pnl_pct < -10]
        if big_losses:
            mistakes.append(f"单笔亏损过大：{len(big_losses)}笔亏损超过10%，止损执行不力")

        # 4. 追涨杀跌
        chase_buys = [r for r in records if r.signal_at_buy and "追涨" in str(r.signal_at_buy)]
        if chase_buys:
            mistakes.append("追涨买入：部分交易在高位追入")

        return mistakes

    def _generate_suggestions(self, records: List[TradeRecord], win_rate: float, profit_factor: Optional[float]) -> List[str]:
        """生成改进建议"""
        suggestions = []

        if win_rate < 40:
            suggestions.append("胜率偏低，建议加强入场条件筛选，提高信号质量")
        elif win_rate < 50:
            suggestions.append("胜率尚可，但可通过更严格的止损提升整体表现")

        if profit_factor and profit_factor < 1.5:
            suggestions.append("盈亏比偏低，建议让盈利单多跑一段，或缩小止损范围")

        # 持仓分析
        short_holds = [r for r in records if r.holding_days is not None and r.holding_days <= 1]
        if len(short_holds) > len(records) * 0.2:
            suggestions.append("日内交易占比过高，建议延长持仓周期捕捉更大趋势")

        # 亏损分析
        loss_records = [r for r in records if r.realized_pnl_pct and r.realized_pnl_pct < -5]
        if loss_records:
            suggestions.append(f"有{len(loss_records)}笔亏损超过5%，建议严格执行止损纪律")

        if not suggestions:
            suggestions.append("交易表现良好，继续保持当前策略")

        return suggestions

    def get_records(self, status: Optional[str] = None) -> List[TradeRecord]:
        """获取交易记录"""
        if status:
            return [r for r in self.records if r.status == status]
        return list(self.records)

    def _load_from_db(self):
        """从数据库加载交易记录"""
        try:
            rows = self._db.get_trade_records()
            for row in rows:
                record = TradeRecord(
                    record_id=row.get("record_id", ""),
                    stock_code=row.get("stock_code", ""),
                    stock_name=row.get("stock_name", ""),
                    buy_price=row.get("buy_price"),
                    buy_quantity=row.get("buy_quantity"),
                    buy_time=self._parse_datetime(row.get("buy_time")),
                    buy_reason=row.get("buy_reason"),
                    sell_price=row.get("sell_price"),
                    sell_quantity=row.get("sell_quantity"),
                    sell_time=self._parse_datetime(row.get("sell_time")),
                    sell_reason=row.get("sell_reason"),
                    holding_days=row.get("holding_days"),
                    realized_pnl=row.get("realized_pnl"),
                    realized_pnl_pct=row.get("realized_pnl_pct"),
                    status=row.get("status", "持有中"),
                    signal_at_buy=row.get("signal_at_buy"),
                    signal_at_sell=row.get("signal_at_sell"),
                )
                self.records.append(record)
        except Exception as e:
            logger.warning(f"[复盘] 从数据库加载记录失败: {e}")

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
