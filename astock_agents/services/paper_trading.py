"""模拟交易系统 - 下单、持仓、盈亏计算、SQLite持久化"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from astock_agents.models.portfolio import (
    TradeOrder, TradeDirection, TradeStatus, OrderType,
    Position, Portfolio
)
from astock_agents.db.database import Database


class PaperTradingService:
    """
    模拟交易服务

    功能：
    1. 模拟下单（市价单/限价单）
    2. 持仓管理
    3. 盈亏计算（含佣金和印花税）
    4. 交易日志
    5. SQLite持久化
    """

    # 交易费率
    COMMISSION_RATE = 0.0003      # 佣金万三
    COMMISSION_MIN = 5.0          # 最低佣金5元
    STAMP_TAX_RATE = 0.001        # 印花税千一（仅卖出）
    STAMP_TAX_MIN = 1.0           # 最低印花税1元

    def __init__(self, initial_capital: float = 1000000.0, db: Optional[Database] = None):
        """
        初始化模拟交易系统

        Args:
            initial_capital: 初始资金
            db: 数据库实例，为空时自动创建默认实例
        """
        self._db = db or Database()
        self.portfolio = Portfolio(
            initial_capital=initial_capital,
            available_cash=initial_capital,
        )
        self.orders: List[TradeOrder] = []
        self.trade_history: List[Dict[str, Any]] = []
        self._load_from_db()
        logger.info(f"[模拟交易] 初始化完成, 资金{initial_capital:,.0f}")

    def place_order(
        self,
        stock_code: str,
        stock_name: str,
        direction: TradeDirection,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        reason: Optional[str] = None,
        signal_source: Optional[str] = None,
    ) -> TradeOrder:
        """
        下单

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            direction: 买入/卖出
            quantity: 数量（股）
            order_type: 市价单/限价单
            price: 限价单价格
            reason: 交易理由
            signal_source: 信号来源

        Returns:
            交易订单
        """
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

        order = TradeOrder(
            order_id=order_id,
            stock_code=stock_code,
            stock_name=stock_name,
            direction=direction,
            order_type=order_type,
            quantity=quantity,
            price=price,
            reason=reason,
            signal_source=signal_source,
        )

        # 市价单立即成交
        if order_type == OrderType.MARKET:
            try:
                fill_price = price or self._get_market_price(stock_code)
                self._fill_order(order, fill_price)
            except ValueError as e:
                order.status = TradeStatus.CANCELLED
                logger.warning(f"[模拟交易] 市价单成交失败: {e}")

        self.orders.append(order)
        self._save_order_to_db(order)
        self._update_portfolio_stats()

        logger.info(
            f"[模拟交易] 下单: {direction.value} {stock_name} "
            f"{quantity}股 @ {order.filled_price or price}"
        )
        return order

    def _fill_order(self, order: TradeOrder, fill_price: float):
        """成交订单

        Args:
            order: 交易订单
            fill_price: 成交价格
        """
        order.filled_price = fill_price
        order.filled_quantity = order.quantity
        order.status = TradeStatus.FILLED
        order.filled_at = datetime.now()

        # 计算费用
        trade_amount = fill_price * order.quantity
        order.commission = max(trade_amount * self.COMMISSION_RATE, self.COMMISSION_MIN)
        if order.direction == TradeDirection.SELL:
            order.stamp_tax = max(trade_amount * self.STAMP_TAX_RATE, self.STAMP_TAX_MIN)

        total_cost = trade_amount + order.commission + order.stamp_tax

        # 更新持仓和资金
        if order.direction == TradeDirection.BUY:
            self._process_buy(order, fill_price, total_cost)
        else:
            self._process_sell(order, fill_price, trade_amount, total_cost)

        # 记录交易历史
        self.trade_history.append({
            "order_id": order.order_id,
            "stock_code": order.stock_code,
            "stock_name": order.stock_name,
            "direction": order.direction.value,
            "price": fill_price,
            "quantity": order.quantity,
            "amount": trade_amount,
            "commission": order.commission,
            "stamp_tax": order.stamp_tax,
            "reason": order.reason,
            "signal_source": order.signal_source,
            "time": datetime.now().isoformat(),
        })

        # 同步写入trade_records表供复盘服务使用
        self._save_trade_record_to_db(order, fill_price)

    def _process_buy(self, order: TradeOrder, price: float, total_cost: float):
        """处理买入

        Args:
            order: 交易订单
            price: 成交价格
            total_cost: 总成本（含费用）
        """
        if total_cost > self.portfolio.available_cash:
            order.status = TradeStatus.CANCELLED
            logger.warning(f"[模拟交易] 资金不足: 需要{total_cost:,.0f}, 可用{self.portfolio.available_cash:,.0f}")
            return

        self.portfolio.available_cash -= total_cost

        # 更新持仓
        existing = self._find_position(order.stock_code)
        if existing:
            new_quantity = existing.quantity + order.quantity
            new_cost = (existing.avg_cost * existing.quantity + price * order.quantity) / new_quantity
            existing.quantity = new_quantity
            existing.available_quantity += order.quantity
            existing.avg_cost = round(new_cost, 3)
            existing.last_trade_at = datetime.now()
            self._save_position_to_db(existing)
        else:
            position = Position(
                stock_code=order.stock_code,
                stock_name=order.stock_name,
                quantity=order.quantity,
                available_quantity=order.quantity,
                avg_cost=price,
                first_buy_at=datetime.now(),
                last_trade_at=datetime.now(),
            )
            self.portfolio.positions.append(position)
            self._save_position_to_db(position)

    def _process_sell(self, order: TradeOrder, price: float, trade_amount: float, total_cost: float):
        """处理卖出

        Args:
            order: 交易订单
            price: 成交价格
            trade_amount: 成交金额
            total_cost: 总成本（含费用）
        """
        position = self._find_position(order.stock_code)
        if not position or position.available_quantity < order.quantity:
            order.status = TradeStatus.CANCELLED
            logger.warning(f"[模拟交易] 持仓不足: {order.stock_code}")
            return

        # 计算盈亏
        cost_basis = position.avg_cost * order.quantity
        realized_pnl = trade_amount - cost_basis - order.commission - order.stamp_tax
        position.realized_pnl += realized_pnl

        # 更新持仓
        position.quantity -= order.quantity
        position.available_quantity -= order.quantity
        position.last_trade_at = datetime.now()

        # 回收资金
        self.portfolio.available_cash += trade_amount - order.commission - order.stamp_tax

        # 清空持仓
        if position.quantity <= 0:
            self.portfolio.positions = [p for p in self.portfolio.positions if p.stock_code != order.stock_code]
            self._db.delete_position(order.stock_code)
        else:
            self._save_position_to_db(position)

    def _find_position(self, stock_code: str) -> Optional[Position]:
        """查找持仓

        Args:
            stock_code: 股票代码

        Returns:
            持仓对象，不存在时返回None
        """
        for pos in self.portfolio.positions:
            if pos.stock_code == stock_code:
                return pos
        return None

    def _get_market_price(self, stock_code: str) -> float:
        """获取市价（从持仓中获取当前价格）

        Args:
            stock_code: 股票代码

        Returns:
            当前市场价格

        Raises:
            ValueError: 无法获取价格时抛出
        """
        position = self._find_position(stock_code)
        if position and position.current_price:
            return position.current_price
        raise ValueError(f"无法获取 {stock_code} 的市价，请提供限价单价格")

    def update_prices(self, price_map: Dict[str, float]):
        """更新持仓股票的当前价格

        Args:
            price_map: 股票代码到价格的映射
        """
        for pos in self.portfolio.positions:
            if pos.stock_code in price_map:
                pos.current_price = price_map[pos.stock_code]
                pos.market_value = pos.current_price * pos.quantity
                pos.unrealized_pnl = (pos.current_price - pos.avg_cost) * pos.quantity
                pos.unrealized_pnl_pct = round(
                    (pos.current_price - pos.avg_cost) / pos.avg_cost * 100, 2
                ) if pos.avg_cost > 0 else 0
                self._save_position_to_db(pos)

        self._update_portfolio_stats()

    def _update_portfolio_stats(self):
        """更新组合统计"""
        total_market_value = sum(p.market_value or 0 for p in self.portfolio.positions)
        total_unrealized = sum(p.unrealized_pnl or 0 for p in self.portfolio.positions)
        total_realized = sum(p.realized_pnl for p in self.portfolio.positions)

        self.portfolio.total_market_value = total_market_value + self.portfolio.available_cash
        self.portfolio.total_pnl = total_unrealized + total_realized
        self.portfolio.total_pnl_pct = round(
            self.portfolio.total_pnl / self.portfolio.initial_capital * 100, 2
        ) if self.portfolio.initial_capital > 0 else 0
        self.portfolio.updated_at = datetime.now()

    def get_portfolio(self) -> Portfolio:
        """获取投资组合

        Returns:
            投资组合对象
        """
        self._update_portfolio_stats()
        return self.portfolio

    def get_orders(self, limit: int = 50) -> List[TradeOrder]:
        """获取交易订单列表

        Args:
            limit: 返回条数上限

        Returns:
            交易订单列表，按创建时间倒序
        """
        return sorted(self.orders, key=lambda o: o.created_at, reverse=True)[:limit]

    def get_trade_history(self) -> List[Dict[str, Any]]:
        """获取交易历史

        Returns:
            交易历史列表，按时间倒序
        """
        return list(reversed(self.trade_history))

    # ---- 数据库持久化方法 ----

    def _save_order_to_db(self, order: TradeOrder) -> None:
        """保存订单到数据库

        Args:
            order: 交易订单
        """
        self._db.save_order({
            "order_id": order.order_id,
            "stock_code": order.stock_code,
            "stock_name": order.stock_name,
            "direction": order.direction.value,
            "order_type": order.order_type.value,
            "quantity": order.quantity,
            "price": order.price,
            "filled_price": order.filled_price,
            "filled_quantity": order.filled_quantity,
            "status": order.status.value,
            "commission": order.commission,
            "stamp_tax": order.stamp_tax,
            "reason": order.reason,
            "signal_source": order.signal_source,
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
        })

    def _save_position_to_db(self, position: Position) -> None:
        """保存持仓到数据库

        Args:
            position: 持仓对象
        """
        self._db.upsert_position({
            "stock_code": position.stock_code,
            "stock_name": position.stock_name,
            "quantity": position.quantity,
            "available_quantity": position.available_quantity,
            "avg_cost": position.avg_cost,
            "current_price": position.current_price,
            "realized_pnl": position.realized_pnl,
            "first_buy_at": position.first_buy_at.isoformat() if position.first_buy_at else None,
            "last_trade_at": position.last_trade_at.isoformat() if position.last_trade_at else None,
        })

    def _load_from_db(self) -> None:
        """从数据库加载订单和持仓"""
        # 加载持仓
        try:
            position_rows = self._db.get_positions()
            self.portfolio.positions = []
            for row in position_rows:
                self.portfolio.positions.append(Position(
                    stock_code=row["stock_code"],
                    stock_name=row["stock_name"],
                    quantity=row["quantity"],
                    available_quantity=row["available_quantity"],
                    avg_cost=row["avg_cost"],
                    current_price=row.get("current_price"),
                    realized_pnl=row.get("realized_pnl", 0),
                    first_buy_at=self._parse_datetime(row.get("first_buy_at")),
                    last_trade_at=self._parse_datetime(row.get("last_trade_at")),
                ))
        except Exception as e:
            logger.warning(f"[模拟交易] 加载持仓失败: {e}")

        # 加载订单
        try:
            order_rows = self._db.get_orders(limit=500)
            self.orders = []
            for row in order_rows:
                self.orders.append(TradeOrder(
                    order_id=row["order_id"],
                    stock_code=row["stock_code"],
                    stock_name=row.get("stock_name"),
                    direction=TradeDirection(row["direction"]),
                    order_type=OrderType(row.get("order_type", "市价单")),
                    quantity=row["quantity"],
                    price=row.get("price"),
                    filled_price=row.get("filled_price"),
                    filled_quantity=row.get("filled_quantity", 0),
                    status=TradeStatus(row.get("status", "待成交")),
                    commission=row.get("commission", 0),
                    stamp_tax=row.get("stamp_tax", 0),
                    reason=row.get("reason"),
                    signal_source=row.get("signal_source"),
                    created_at=self._parse_datetime(row.get("created_at")) or datetime.now(),
                    filled_at=self._parse_datetime(row.get("filled_at")),
                ))
        except Exception as e:
            logger.warning(f"[模拟交易] 加载订单失败: {e}")

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

    def _save_trade_record_to_db(self, order: TradeOrder, fill_price: float) -> None:
        """成交后写入trade_records表供复盘服务使用

        买入时创建新记录（状态：持有中），卖出时更新已有记录（状态：已平仓）

        Args:
            order: 交易订单
            fill_price: 成交价格
        """
        if order.direction == TradeDirection.BUY:
            # 买入：创建新的交易记录
            record_id = f"REC-{order.order_id}"
            self._db.save_trade_record({
                "record_id": record_id,
                "stock_code": order.stock_code,
                "stock_name": order.stock_name,
                "buy_price": fill_price,
                "buy_quantity": order.quantity,
                "buy_time": datetime.now().isoformat(),
                "buy_reason": order.reason,
                "status": "持有中",
                "signal_at_buy": order.signal_source,
            })
        else:
            # 卖出：查找该股票的持有中记录并更新
            existing_records = self._db.get_trade_records(status="持有中")
            matching = [r for r in existing_records if r.get("stock_code") == order.stock_code]
            if matching:
                record = matching[0]
                buy_price = record.get("buy_price", 0)
                buy_quantity = record.get("buy_quantity", 0)
                realized_pnl = (fill_price - buy_price) * buy_quantity if buy_price else None
                realized_pnl_pct = round(
                    (fill_price - buy_price) / buy_price * 100, 2
                ) if buy_price and buy_price > 0 else None
                buy_time_str = record.get("buy_time")
                holding_days = None
                if buy_time_str:
                    try:
                        buy_dt = datetime.fromisoformat(str(buy_time_str))
                        holding_days = (datetime.now() - buy_dt).days
                    except (ValueError, TypeError):
                        pass

                self._db.save_trade_record({
                    "record_id": record.get("record_id"),
                    "stock_code": order.stock_code,
                    "stock_name": order.stock_name,
                    "buy_price": buy_price,
                    "buy_quantity": buy_quantity,
                    "buy_time": buy_time_str,
                    "buy_reason": record.get("buy_reason"),
                    "sell_price": fill_price,
                    "sell_quantity": order.quantity,
                    "sell_time": datetime.now().isoformat(),
                    "sell_reason": order.reason,
                    "holding_days": holding_days,
                    "realized_pnl": realized_pnl,
                    "realized_pnl_pct": realized_pnl_pct,
                    "status": "已平仓",
                    "signal_at_buy": record.get("signal_at_buy"),
                    "signal_at_sell": order.signal_source,
                })
