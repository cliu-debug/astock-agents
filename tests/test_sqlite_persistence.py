"""SQLite持久化存储功能测试"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_database_module():
    """测试 Database 模块基本功能"""
    from astock_agents.db.database import Database

    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_astock.db")
    db = Database(db_path=db_path)
    print(f"数据库创建成功: {db_path}")

    # ---- 自选股 ----
    print("\n--- 自选股 ---")
    assert db.add_watchlist("000001", "平安银行", group="默认", reason="测试")
    rows = db.get_watchlist()
    assert len(rows) == 1
    assert rows[0]["stock_code"] == "000001"
    print("添加自选股成功")

    assert db.add_watchlist("600519", "贵州茅台", group="价值策略")
    rows = db.get_watchlist()
    assert len(rows) == 2
    print(f"添加第二只自选股成功，共 {len(rows)} 只")

    assert db.remove_watchlist("000001")
    rows = db.get_watchlist()
    assert len(rows) == 1
    print(f"删除自选股成功，剩余 {len(rows)} 只")

    assert db.update_watchlist("600519", {"last_signal": "买入", "notes": "测试备注"})
    rows = db.get_watchlist()
    assert rows[0]["last_signal"] == "买入"
    assert rows[0]["notes"] == "测试备注"
    print("更新自选股成功")

    # ---- 分析结果 ----
    print("\n--- 分析结果 ---")
    db.save_analysis("600519", "贵州茅台", "买入", 85, '{"summary": "test"}')
    history = db.get_analysis_history("600519")
    assert len(history) == 1
    assert history[0]["signal"] == "买入"
    print("保存分析结果成功")

    # ---- 交易订单 ----
    print("\n--- 交易订单 ---")
    order = {
        "order_id": "ORD-TEST-001",
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "direction": "买入",
        "order_type": "市价单",
        "quantity": 100,
        "price": 1800.0,
        "filled_price": 1800.5,
        "filled_quantity": 100,
        "status": "已成交",
        "commission": 54.02,
        "stamp_tax": 0,
        "reason": "技术突破",
        "signal_source": "技术分析",
    }
    assert db.save_order(order)
    orders = db.get_orders()
    assert len(orders) == 1
    assert orders[0]["order_id"] == "ORD-TEST-001"
    print("保存订单成功")

    # ---- 持仓 ----
    print("\n--- 持仓 ---")
    pos = {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "quantity": 100,
        "available_quantity": 100,
        "avg_cost": 1800.5,
        "current_price": 1820.0,
        "realized_pnl": 0,
        "first_buy_at": "2025-01-01T10:00:00",
        "last_trade_at": "2025-01-01T10:00:00",
    }
    db.upsert_position(pos)
    positions = db.get_positions()
    assert len(positions) == 1
    assert positions[0]["stock_code"] == "600519"
    print("保存持仓成功")

    db.delete_position("600519")
    positions = db.get_positions()
    assert len(positions) == 0
    print("删除持仓成功")

    # ---- 交易记录 ----
    print("\n--- 交易记录 ---")
    record = {
        "record_id": "REC-001",
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "buy_price": 1800.0,
        "buy_quantity": 100,
        "buy_time": "2025-01-01T10:00:00",
        "buy_reason": "技术突破",
        "status": "持有中",
        "signal_at_buy": "MACD金叉",
    }
    db.save_trade_record(record)
    records = db.get_trade_records()
    assert len(records) == 1
    assert records[0]["record_id"] == "REC-001"
    print("保存交易记录成功")

    records_filtered = db.get_trade_records(status="持有中")
    assert len(records_filtered) == 1
    print("按状态筛选交易记录成功")

    # 清理
    for f in os.listdir(tmp_dir):
        os.remove(os.path.join(tmp_dir, f))
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\n=== Database 模块测试全部通过 ===")


def test_watchlist_manager():
    """测试 WatchlistManager 使用 SQLite"""
    from astock_agents.db.database import Database
    from astock_agents.services.watchlist import WatchlistManager
    from astock_agents.models.portfolio import WatchlistItem, WatchlistGroup

    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_watchlist.db")
    db = Database(db_path=db_path)

    manager = WatchlistManager(db=db)
    print("\n=== 测试 WatchlistManager ===")

    # 添加
    item1 = WatchlistItem(stock_code="000001", stock_name="平安银行", group=WatchlistGroup.DEFAULT)
    assert manager.add(item1)
    assert manager.count() == 1
    print(f"添加自选股成功: {item1.stock_name}")

    # 重复添加
    assert not manager.add(item1)
    print("重复添加被正确拒绝")

    # 查询
    found = manager.get_by_code("000001")
    assert found is not None
    assert found.stock_name == "平安银行"
    print("按代码查询成功")

    # 更新
    assert manager.update("000001", {"target_price": 15.0, "stop_loss": 12.0})
    found = manager.get_by_code("000001")
    assert found.target_price == 15.0
    assert found.stop_loss == 12.0
    print("更新自选股成功")

    # 更新分析结果
    assert manager.update_analysis_result("000001", "买入")
    found = manager.get_by_code("000001")
    assert found.last_signal == "买入"
    print("更新分析结果成功")

    # 删除
    assert manager.remove("000001")
    assert manager.count() == 0
    print("删除自选股成功")

    # 验证持久化：重新创建 manager
    item2 = WatchlistItem(stock_code="600519", stock_name="贵州茅台", group=WatchlistGroup.VALUE)
    manager.add(item2)

    manager2 = WatchlistManager(db=db)
    assert manager2.count() == 1
    assert manager2.get_by_code("600519") is not None
    print("持久化验证成功：重新加载后数据仍在")

    # 清理
    for f in os.listdir(tmp_dir):
        os.remove(os.path.join(tmp_dir, f))
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\n=== WatchlistManager 测试全部通过 ===")


def test_paper_trading_service():
    """测试 PaperTradingService 使用 SQLite"""
    from astock_agents.db.database import Database
    from astock_agents.services.paper_trading import PaperTradingService
    from astock_agents.models.portfolio import TradeDirection, OrderType

    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_trading.db")
    db = Database(db_path=db_path)

    service = PaperTradingService(initial_capital=1000000.0, db=db)
    print("\n=== 测试 PaperTradingService ===")

    # 买入
    order = service.place_order(
        stock_code="600519",
        stock_name="贵州茅台",
        direction=TradeDirection.BUY,
        quantity=100,
        price=1800.0,
        reason="技术突破",
    )
    assert order.filled_price == 1800.0
    print(f"买入成功: {order.order_id}, 成交价 {order.filled_price}")

    # 验证持仓
    portfolio = service.get_portfolio()
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0].stock_code == "600519"
    assert portfolio.positions[0].quantity == 100
    print(f"持仓验证成功: {portfolio.positions[0].stock_name} {portfolio.positions[0].quantity}股")

    # 卖出
    sell_order = service.place_order(
        stock_code="600519",
        stock_name="贵州茅台",
        direction=TradeDirection.SELL,
        quantity=100,
        price=1850.0,
        reason="止盈",
    )
    assert sell_order.filled_price == 1850.0
    print(f"卖出成功: {sell_order.order_id}, 成交价 {sell_order.filled_price}")

    # 验证持仓清空
    portfolio = service.get_portfolio()
    assert len(portfolio.positions) == 0
    print("持仓清空验证成功")

    # 验证订单持久化：重新创建 service
    service2 = PaperTradingService(initial_capital=1000000.0, db=db)
    orders = service2.get_orders()
    assert len(orders) >= 2
    print(f"持久化验证成功：重新加载后订单数 {len(orders)}")

    # 清理
    for f in os.listdir(tmp_dir):
        os.remove(os.path.join(tmp_dir, f))
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\n=== PaperTradingService 测试全部通过 ===")


if __name__ == "__main__":
    test_database_module()
    test_watchlist_manager()
    test_paper_trading_service()
    print("\n" + "=" * 50)
    print("所有测试通过！")
    print("=" * 50)
