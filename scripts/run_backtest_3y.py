"""3年A股回测执行脚本

回测方案：
- 选股池：8只代表性A股（覆盖消费/金融/新能源/医药）
- 策略：3种经典技术策略（MA金叉死叉/MACD/RSI超买超卖）
- 时间：2023-06-01 ~ 2026-05-28（3年）
- 基准：买入持有
- 初始资金：100万
"""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO")

STOCK_POOL = [
    ("600519.SH", "贵州茅台"),
    ("600036.SH", "招商银行"),
    ("601318.SH", "中国平安"),
    ("300750.SZ", "宁德时代"),
    ("002594.SZ", "比亚迪"),
    ("000858.SZ", "五粮液"),
    ("603288.SH", "海天味业"),
    ("600276.SH", "恒瑞医药"),
]

INITIAL_CAPITAL = 1000000.0
BACKTEST_DAYS = 750


def download_kline_data(stock_code: str, days: int = 750) -> Optional[List[Dict[str, Any]]]:
    """下载K线数据

    按优先级尝试多个数据源，自动重试和降级

    Args:
        stock_code: 股票代码
        days: 天数

    Returns:
        价格数据列表
    """
    code = stock_code.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")

    # 尝试akshare（带重试）
    for attempt in range(3):
        try:
            import akshare as ak
            logger.info(f"[数据下载] akshare获取: {stock_code} (尝试{attempt + 1}/3)")

            start_date = "20230601"
            end_date = datetime.now().strftime("%Y%m%d")
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
            if df is not None and not df.empty:
                df = df.tail(days)
                prices = []
                for _, row in df.iterrows():
                    date_val = row.get("日期", row.get("date", ""))
                    if isinstance(date_val, str):
                        try:
                            date_val = datetime.strptime(date_val, "%Y-%m-%d")
                        except ValueError:
                            pass
                    prices.append({
                        "date": date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val),
                        "open": float(row.get("开盘", row.get("open", 0))),
                        "high": float(row.get("最高", row.get("high", 0))),
                        "low": float(row.get("最低", row.get("low", 0))),
                        "close": float(row.get("收盘", row.get("close", 0))),
                        "volume": int(row.get("成交量", row.get("volume", 0))),
                    })
                logger.info(f"[数据下载] akshare成功: {stock_code}, {len(prices)}条")
                return prices
        except Exception as e:
            logger.warning(f"[数据下载] akshare失败(尝试{attempt + 1}): {stock_code}, {e}")
            time.sleep(2 * (attempt + 1))

    # 降级到mootdx
    try:
        from mootdx.quotes import Quotes
        api = Quotes.factory(market="std")
        market = 1 if stock_code.endswith(".SH") else 0
        logger.info(f"[数据下载] mootdx获取: {stock_code}")
        df = api.bars(symbol=code, frequency=9, market=market, offset=days)
        if df is not None and not df.empty:
            prices = []
            for idx, row in df.iterrows():
                prices.append({
                    "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": int(row.get("volume", 0)),
                })
            prices = prices[-days:]
            logger.info(f"[数据下载] mootdx成功: {stock_code}, {len(prices)}条")
            return prices
    except Exception as e:
        logger.warning(f"[数据下载] mootdx失败: {stock_code}, {e}")

    # 降级到腾讯财经
    try:
        import requests
        market_prefix = "sh" if stock_code.endswith(".SH") else "sz"
        tencent_code = f"{market_prefix}{code}"
        url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tencent_code},day,,,,{days},qfq"
        logger.info(f"[数据下载] 腾讯财经获取: {stock_code}")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        kline_data = None
        msg_data = data.get("data", {})
        for key in msg_data:
            if key.startswith("qfqday") or key.startswith("day"):
                kline_data = msg_data[key]
                break

        if kline_data:
            prices = []
            for item in kline_data:
                prices.append({
                    "date": item[0],
                    "open": float(item[1]),
                    "high": float(item[3]),
                    "low": float(item[4]),
                    "close": float(item[2]),
                    "volume": int(item[5]) if len(item) > 5 else 0,
                })
            prices = prices[-days:]
            logger.info(f"[数据下载] 腾讯财经成功: {stock_code}, {len(prices)}条")
            return prices
    except Exception as e:
        logger.warning(f"[数据下载] 腾讯财经失败: {stock_code}, {e}")

    # 降级到东财
    try:
        import requests
        secid = f"1.{code}" if stock_code.endswith(".SH") else f"0.{code}"
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
            "klt": "101",
            "fqt": "1",
            "beg": "20230601",
            "end": "20500101",
            "lmt": str(days),
        }
        logger.info(f"[数据下载] 东方财富获取: {stock_code}")
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        klines = data.get("data", {}).get("klines", [])
        if klines:
            prices = []
            for line in klines:
                parts = line.split(",")
                if len(parts) >= 6:
                    prices.append({
                        "date": parts[0],
                        "open": float(parts[1]),
                        "close": float(parts[2]),
                        "high": float(parts[3]),
                        "low": float(parts[4]),
                        "volume": int(parts[5]),
                    })
            prices = prices[-days:]
            logger.info(f"[数据下载] 东方财富成功: {stock_code}, {len(prices)}条")
            return prices
    except Exception as e:
        logger.warning(f"[数据下载] 东方财富失败: {stock_code}, {e}")

    logger.error(f"[数据下载] 所有数据源失败: {stock_code}")
    return None


def generate_ma_signals(prices: List[Dict[str, Any]], short: int = 5, long: int = 20) -> List[Dict[str, str]]:
    """MA金叉死叉策略信号

    短期均线上穿长期均线=买入(金叉)，下穿=卖出(死叉)

    Args:
        prices: 价格数据
        short: 短期均线周期
        long: 长期均线周期

    Returns:
        信号列表
    """
    signals = []
    if len(prices) < long + 1:
        return signals

    closes = [p["close"] for p in prices]

    for i in range(long, len(closes)):
        ma_short = sum(closes[i - short:i]) / short
        ma_short_prev = sum(closes[i - short - 1:i - 1]) / short
        ma_long = sum(closes[i - long:i]) / long
        ma_long_prev = sum(closes[i - long - 1:i - 1]) / long

        if ma_short_prev <= ma_long_prev and ma_short > ma_long:
            signals.append({"date": prices[i]["date"], "action": "buy"})
        elif ma_short_prev >= ma_long_prev and ma_short < ma_long:
            signals.append({"date": prices[i]["date"], "action": "sell"})

    return signals


def generate_macd_signals(
    prices: List[Dict[str, Any]],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> List[Dict[str, str]]:
    """MACD策略信号

    MACD金叉=买入，死叉=卖出

    Args:
        prices: 价格数据
        fast: 快线周期
        slow: 慢线周期
        signal: 信号线周期

    Returns:
        信号列表
    """
    signals = []
    if len(prices) < slow + signal + 1:
        return signals

    closes = [p["close"] for p in prices]

    # 计算EMA
    def ema(data: List[float], period: int) -> List[float]:
        result = [data[0]]
        multiplier = 2 / (period + 1)
        for val in data[1:]:
            result.append(val * multiplier + result[-1] * (1 - multiplier))
        return result

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = ema(dif, signal)
    macd_hist = [(d - e) * 2 for d, e in zip(dif, dea)]

    for i in range(signal + 1, len(macd_hist)):
        if macd_hist[i - 1] <= 0 and macd_hist[i] > 0:
            signals.append({"date": prices[i]["date"], "action": "buy"})
        elif macd_hist[i - 1] >= 0 and macd_hist[i] < 0:
            signals.append({"date": prices[i]["date"], "action": "sell"})

    return signals


def generate_rsi_signals(
    prices: List[Dict[str, Any]],
    period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0,
) -> List[Dict[str, str]]:
    """RSI超买超卖策略信号

    RSI低于超卖线=买入，高于超买线=卖出

    Args:
        prices: 价格数据
        period: RSI周期
        oversold: 超卖阈值
        overbought: 超买阈值

    Returns:
        信号列表
    """
    signals = []
    if len(prices) < period + 1:
        return signals

    closes = [p["close"] for p in prices]

    gains = []
    losses = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    rsi_values = []
    for i in range(period - 1, len(gains)):
        window_gains = gains[i - period + 1:i + 1]
        window_losses = losses[i - period + 1:i + 1]
        avg_gain = sum(window_gains) / period
        avg_loss = sum(window_losses) / period
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - 100 / (1 + rs))

    rsi_start_idx = period
    for i, rsi in enumerate(rsi_values):
        price_idx = rsi_start_idx + i
        if price_idx >= len(prices):
            break
        if rsi < oversold:
            signals.append({"date": prices[price_idx]["date"], "action": "buy"})
        elif rsi > overbought:
            signals.append({"date": prices[price_idx]["date"], "action": "sell"})

    return signals


def run_backtest_for_stock(
    stock_code: str,
    stock_name: str,
    prices: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """对单只股票运行3种策略回测

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        prices: 价格数据

    Returns:
        回测结果字典
    """
    from astock_agents.models.stock_data import StockData, StockPrice
    from astock_agents.services.backtest import BacktestEngine

    stock_prices = []
    for p in prices:
        try:
            stock_prices.append(StockPrice(
                date=datetime.strptime(p["date"], "%Y-%m-%d"),
                open=p["open"],
                high=p["high"],
                low=p["low"],
                close=p["close"],
                volume=p.get("volume", 0),
            ))
        except Exception:
            continue

    stock_data = StockData(
        stock_code=stock_code,
        stock_name=stock_name,
        prices=stock_prices,
    )

    engine = BacktestEngine(initial_capital=INITIAL_CAPITAL)

    strategies = {
        "MA金叉死叉(5/20)": generate_ma_signals(prices, 5, 20),
        "MACD(12/26/9)": generate_macd_signals(prices),
        "RSI超买超卖(14)": generate_rsi_signals(prices),
    }

    results = {}
    for strategy_name, signals in strategies.items():
        if not signals:
            results[strategy_name] = {"error": "无信号生成"}
            continue

        try:
            result = engine.run(
                stock_data=stock_data,
                signals=signals,
                strategy_name=strategy_name,
                position_size_pct=0.2,
                stop_loss_pct=0.07,
                take_profit_pct=0.15,
            )
            results[strategy_name] = {
                "total_return_pct": result.total_return_pct,
                "annual_return_pct": result.annual_return_pct,
                "max_drawdown_pct": result.max_drawdown_pct,
                "sharpe_ratio": result.sharpe_ratio,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "total_trades": result.total_trades,
                "win_trades": result.win_trades,
                "loss_trades": result.loss_trades,
                "avg_holding_days": result.avg_holding_days,
                "benchmark_return_pct": result.benchmark_return_pct,
                "final_capital": result.final_capital,
            }
        except Exception as e:
            results[strategy_name] = {"error": str(e)}

    # 买入持有基准
    if len(stock_prices) >= 2:
        buy_hold_return = (stock_prices[-1].close - stock_prices[0].close) / stock_prices[0].close * 100
        results["买入持有(基准)"] = {
            "total_return_pct": round(buy_hold_return, 2),
            "benchmark_return_pct": round(buy_hold_return, 2),
        }

    return results


def generate_report(all_results: Dict[str, Dict[str, Any]]) -> str:
    """生成专业回测报告

    Args:
        all_results: 所有股票的回测结果

    Returns:
        Markdown格式报告
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# AStockAgents 3年A股回测报告",
        f"",
        f"**生成时间**: {now}",
        f"**回测区间**: 2023-06 ~ 2026-05 (约3年)",
        f"**初始资金**: ¥{INITIAL_CAPITAL:,.0f}",
        f"**选股池**: {len(STOCK_POOL)}只代表性A股",
        f"**策略**: MA金叉死叉 / MACD / RSI超买超卖",
        f"**基准**: 买入持有",
        f"",
        f"---",
        f"",
    ]

    # 汇总表
    lines.append("## 一、策略汇总对比")
    lines.append("")
    lines.append("| 股票 | 策略 | 总收益率 | 年化收益 | 最大回撤 | 夏普比率 | 胜率 | 盈亏比 | 交易次数 | 基准收益 | 超额收益 |")
    lines.append("|------|------|---------|---------|---------|---------|------|--------|---------|---------|---------|")

    strategy_stats: Dict[str, List[float]] = {}

    for stock_key, strategies in all_results.items():
        stock_label = stock_key.split(" ")[0] if " " in stock_key else stock_key
        for strat_name, metrics in strategies.items():
            if "error" in metrics:
                lines.append(f"| {stock_label} | {strat_name} | ❌失败 | - | - | - | - | - | - | - | - |")
                continue

            total_ret = metrics.get("total_return_pct", 0)
            annual_ret = metrics.get("annual_return_pct", 0)
            max_dd = metrics.get("max_drawdown_pct", 0)
            sharpe = metrics.get("sharpe_ratio")
            win_rate = metrics.get("win_rate", 0)
            pf = metrics.get("profit_factor")
            trades = metrics.get("total_trades", 0)
            bench = metrics.get("benchmark_return_pct", 0)
            excess = round(total_ret - (bench or 0), 2)

            sharpe_str = f"{sharpe:.2f}" if sharpe else "N/A"
            pf_str = f"{pf:.2f}" if pf else "N/A"

            lines.append(
                f"| {stock_label} | {strat_name} | {total_ret:+.2f}% | {annual_ret:+.2f}% | "
                f"{max_dd:.2f}% | {sharpe_str} | {win_rate:.1f}% | {pf_str} | {trades} | "
                f"{bench:+.2f}% | {excess:+.2f}% |"
            )

            if strat_name not in ["买入持有(基准)"]:
                if strat_name not in strategy_stats:
                    strategy_stats[strat_name] = {"returns": [], "drawdowns": [], "sharpes": [], "win_rates": [], "excesses": []}
                strategy_stats[strat_name]["returns"].append(total_ret)
                strategy_stats[strat_name]["drawdowns"].append(max_dd)
                if sharpe:
                    strategy_stats[strat_name]["sharpes"].append(sharpe)
                strategy_stats[strat_name]["win_rates"].append(win_rate)
                strategy_stats[strat_name]["excesses"].append(excess)

    # 策略平均表现
    lines.append("")
    lines.append("## 二、策略平均表现")
    lines.append("")
    lines.append("| 策略 | 平均收益率 | 平均最大回撤 | 平均夏普 | 平均胜率 | 平均超额收益 |")
    lines.append("|------|-----------|------------|---------|---------|------------|")

    for strat_name, stats in strategy_stats.items():
        if not stats["returns"]:
            continue
        avg_ret = sum(stats["returns"]) / len(stats["returns"])
        avg_dd = sum(stats["drawdowns"]) / len(stats["drawdowns"])
        avg_sharpe = sum(stats["sharpes"]) / len(stats["sharpes"]) if stats["sharpes"] else 0
        avg_wr = sum(stats["win_rates"]) / len(stats["win_rates"])
        avg_excess = sum(stats["excesses"]) / len(stats["excesses"])
        lines.append(
            f"| {strat_name} | {avg_ret:+.2f}% | {avg_dd:.2f}% | {avg_sharpe:.2f} | "
            f"{avg_wr:.1f}% | {avg_excess:+.2f}% |"
        )

    # 关键发现
    lines.append("")
    lines.append("## 三、关键发现")
    lines.append("")

    best_strat = ""
    best_avg_ret = -999
    for strat_name, stats in strategy_stats.items():
        if not stats["returns"]:
            continue
        avg_ret = sum(stats["returns"]) / len(stats["returns"])
        if avg_ret > best_avg_ret:
            best_avg_ret = avg_ret
            best_strat = strat_name

    if best_strat:
        lines.append(f"1. **最佳策略**: {best_strat}，平均收益率 {best_avg_ret:+.2f}%")

    # 超额收益统计
    positive_excess_count = 0
    total_excess_count = 0
    for stats in strategy_stats.values():
        for e in stats["excesses"]:
            total_excess_count += 1
            if e > 0:
                positive_excess_count += 1

    if total_excess_count > 0:
        beat_ratio = positive_excess_count / total_excess_count * 100
        lines.append(f"2. **战胜基准比例**: {positive_excess_count}/{total_excess_count} = {beat_ratio:.1f}%")

    # 风险分析
    all_drawdowns = []
    for stats in strategy_stats.values():
        all_drawdowns.extend(stats["drawdowns"])
    if all_drawdowns:
        avg_dd = sum(all_drawdowns) / len(all_drawdowns)
        max_dd = max(all_drawdowns)
        lines.append(f"3. **风险水平**: 平均最大回撤 {avg_dd:.2f}%，最大回撤 {max_dd:.2f}%")

    all_sharpes = []
    for stats in strategy_stats.values():
        all_sharpes.extend(stats["sharpes"])
    if all_sharpes:
        avg_sharpe = sum(all_sharpes) / len(all_sharpes)
        lines.append(f"4. **夏普比率**: 平均 {avg_sharpe:.2f}（>1.0为优秀，>0.5为良好）")

    lines.append("")
    lines.append("## 四、免责声明")
    lines.append("")
    lines.append("> 本回测报告基于历史数据，过往表现不代表未来收益。")
    lines.append("> 回测结果受滑点、流动性、数据质量等因素影响，实际交易结果可能存在偏差。")
    lines.append("> 本系统提供的分析结果仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。")

    return "\n".join(lines)


def main():
    """主函数：下载数据 → 生成信号 → 回测 → 输出报告"""
    print("=" * 60)
    print("  AStockAgents 3年A股回测")
    print("=" * 60)
    print(f"  选股池: {len(STOCK_POOL)}只")
    print(f"  策略: MA金叉死叉 / MACD / RSI")
    print(f"  初始资金: ¥{INITIAL_CAPITAL:,.0f}")
    print("=" * 60)

    all_results: Dict[str, Dict[str, Any]] = {}

    for i, (stock_code, stock_name) in enumerate(STOCK_POOL):
        print(f"\n[{i + 1}/{len(STOCK_POOL)}] 处理: {stock_name}({stock_code})")

        # 下载数据
        prices = download_kline_data(stock_code, days=BACKTEST_DAYS)
        if not prices or len(prices) < 100:
            print(f"  ❌ 数据不足: {len(prices) if prices else 0}条")
            all_results[f"{stock_code} {stock_name}"] = {"数据不足": {"error": f"仅{len(prices) if prices else 0}条数据"}}
            continue

        print(f"  ✅ 数据下载成功: {len(prices)}条 ({prices[0]['date']} ~ {prices[-1]['date']})")

        # 运行回测
        results = run_backtest_for_stock(stock_code, stock_name, prices)
        all_results[f"{stock_code} {stock_name}"] = results

        # 打印简要结果
        for strat_name, metrics in results.items():
            if "error" in metrics:
                print(f"  {strat_name}: ❌ {metrics['error']}")
            else:
                ret = metrics.get("total_return_pct", 0)
                dd = metrics.get("max_drawdown_pct", 0)
                sharpe = metrics.get("sharpe_ratio")
                sharpe_str = f", 夏普={sharpe:.2f}" if sharpe else ""
                print(f"  {strat_name}: 收益={ret:+.2f}%, 回撤={dd:.2f}%{sharpe_str}")

        # 避免请求过快
        time.sleep(3)

    # 生成报告
    print("\n" + "=" * 60)
    print("  生成回测报告...")
    report = generate_report(all_results)

    # 保存报告
    report_dir = project_root / "reports"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"backtest_3y_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text(report, encoding="utf-8")

    # 保存原始数据
    data_path = report_dir / f"backtest_3y_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(str(data_path), "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 报告已保存: {report_path}")
    print(f"  ✅ 数据已保存: {data_path}")

    # 打印报告摘要
    print("\n" + report)

    return all_results


if __name__ == "__main__":
    main()
