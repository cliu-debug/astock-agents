"""技术分析师智能体 - 增强版

增加的技术指标：
- ATR (Average True Range) - 真实波幅
- OBV (On-Balance Volume) - 能量潮
- WR (Williams %R) - 威廉指标
- CCI (Commodity Channel Index) - 顺势指标
- ADX (Average Directional Index) - 平均趋向指标

增加的K线形态：
- 吞没形态（看涨/看跌）
- 孕线形态
- 早晨之星/黄昏之星
- 双底/双顶
- 头肩顶/头肩底
"""

from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
import numpy as np
from loguru import logger

from astock_agents.agents.base_agent import BaseAgent
from astock_agents.models import StockData, TechnicalAnalysis, Signal


class TechnicalAnalyst(BaseAgent):
    """技术分析师 - 负责技术分析（增强版）"""
    
    # 数值计算精度常量，用于除零保护
    EPS = 1e-10

    # 形态类型定义
    BULLISH_PATTERNS = [
        "看涨吞没", "看涨孕线", "早晨之星", "锤子线", "刺透形态",
        "双底", "头肩底", "上升三角形", "圆弧底"
    ]
    
    BEARISH_PATTERNS = [
        "看跌吞没", "看跌孕线", "黄昏之星", "流星线", "乌云盖顶",
        "双顶", "头肩顶", "下降三角形", "圆弧顶"
    ]
    
    def __init__(self, llm=None, config=None):
        super().__init__(
            name="技术分析师",
            role="通过K线形态、技术指标、趋势分析判断股票走势",
            llm=llm,
            config=config
        )
    
    def analyze(self, stock_data: StockData, **kwargs) -> TechnicalAnalysis:
        """执行技术分析（增强版：含自主规划+推理链+反思）"""
        logger.info(f"[{self.name}] 开始技术分析: {stock_data.stock_code}")

        # 清空上一次的推理链
        self._clear_reasoning_chain()

        # 自主规划：创建任务计划
        plan = self._plan_analysis_tasks(stock_data)

        if not stock_data.prices:
            logger.warning(f"[{self.name}] 无价格数据")
            self._update_status("error", "无价格数据")
            return self._create_empty_analysis()

        # 步骤1：数据校验
        plan.mark_step_executing("validate_data")
        self._update_status("executing", "正在校验数据完整性")
        data_points_count = len(stock_data.prices)
        data_quality = "good" if data_points_count >= 120 else (
            "normal" if data_points_count >= 60 else (
                "poor" if data_points_count >= 30 else "insufficient"
            )
        )
        self._add_reasoning_step(
            "数据校验",
            f"检查{stock_data.stock_name}的价格数据",
            f"数据量={data_points_count}天",
            f"数据质量={data_quality}",
            0.9 if data_points_count >= 60 else 0.5,
        )
        plan.mark_step_completed("validate_data")

        # 步骤2：指标计算
        plan.mark_step_executing("compute_indicators")
        self._update_status("analyzing", "正在计算技术指标")
        df = self._prepare_data(stock_data).copy()
        indicators = self._calculate_all_indicators(df)
        self._add_reasoning_step(
            "指标计算",
            "计算12项技术指标（MA/MACD/RSI/KDJ/BOLL/ATR/OBV/WR/CCI/ADX/成交量/量价）",
            f"数据范围={df['date'].iloc[0]}~{df['date'].iloc[-1]}",
            f"RSI={indicators.get('rsi', {}).get('value', 'N/A')}, "
            f"MACD={indicators.get('macd', {}).get('cross_signal', 'N/A')}",
            0.85,
        )
        plan.mark_step_completed("compute_indicators")

        # 步骤3：形态识别与趋势分析
        plan.mark_step_executing("generate_signal")
        self._update_status("analyzing", "正在识别K线形态和分析趋势")
        patterns = self._identify_all_patterns(df, indicators)
        trend, trend_strength = self._analyze_trend(df, indicators)
        support_levels, resistance_levels = self._calculate_support_resistance(df)
        signal, confidence = self._generate_comprehensive_signal(df, indicators, trend, patterns)
        self._add_reasoning_step(
            "信号生成",
            f"综合{len(patterns)}个形态和趋势分析生成信号",
            f"趋势={trend}, 形态数={len(patterns)}",
            f"信号={signal.value}, 置信度={confidence}%",
            confidence / 100.0,
        )
        plan.mark_step_completed("generate_signal")

        # 生成分析摘要
        summary = self._generate_summary(
            stock_data, trend, indicators, patterns, signal
        )

        # 确保所有numpy类型转为Python原生类型
        indicators = self._sanitize_numpy(indicators)
        support_levels = [float(x) for x in support_levels]
        resistance_levels = [float(x) for x in resistance_levels]
        trend_strength = int(trend_strength)
        confidence = int(confidence)

        # LLM增强分析
        if self.llm:
            try:
                self._update_status("analyzing", "正在使用LLM深度解读")
                llm_insight = self._llm_enhance_analysis(
                    stock_data, trend, indicators, patterns, signal
                )
                if llm_insight.get("summary"):
                    summary = llm_insight["summary"]
            except Exception as e:
                logger.warning(f"[{self.name}] LLM增强分析失败，使用规则引擎结果: {e}")

        # 步骤4：反思自检
        plan.mark_step_executing("validate_output")
        reflection = self._reflect_on_output({
            "signal": signal,
            "confidence": confidence,
            "indicators": indicators,
            "data_points_count": data_points_count,
        })

        # 根据反思结果调整置信度
        if reflection.get("confidence_adjustment", 0) != 0:
            original_confidence = confidence
            confidence = max(5, min(100, confidence + reflection["confidence_adjustment"]))
            if confidence != original_confidence:
                logger.info(
                    f"[{self.name}] 反思调整置信度: {original_confidence}% -> {confidence}%"
                )

        # 生成不确定性声明
        uncertainty = self._generate_uncertainty_statement(confidence, data_quality)
        if uncertainty:
            summary += f"\n\n{uncertainty}"

        plan.mark_step_completed("validate_output")

        analysis = TechnicalAnalysis(
            trend=trend,
            trend_strength=trend_strength,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            indicators=indicators,
            patterns=patterns,
            summary=summary,
            signal=signal,
            confidence=confidence,
            reasoning_chain=self.get_reasoning_chain(),
            uncertainty_statement=uncertainty if uncertainty else None,
            reflection=reflection,
            task_plan=self.get_task_plan(),
        )

        self._update_status("completed", f"技术分析完成: {signal.value}")
        self.log_analysis(analysis.model_dump())
        return analysis
    
    def _prepare_data(self, stock_data: StockData) -> pd.DataFrame:
        """准备数据"""
        data = []
        for price in stock_data.prices:
            data.append({
                'date': price.date,
                'open': price.open,
                'high': price.high,
                'low': price.low,
                'close': price.close,
                'volume': price.volume,
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('date').reset_index(drop=True)
        return df
    
    # ==================== 技术指标计算 ====================
    
    def _calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """计算所有技术指标"""
        indicators = {}
        
        try:
            # 1. 移动平均线系统
            indicators['ma'] = self._calc_ma(df)
            
            # 2. MACD
            indicators['macd'] = self._calc_macd(df)
            
            # 3. RSI
            indicators['rsi'] = self._calc_rsi(df)
            
            # 4. KDJ
            indicators['kdj'] = self._calc_kdj(df)
            
            # 5. 布林带
            indicators['bollinger'] = self._calc_bollinger(df)
            
            # 6. ATR (新增)
            indicators['atr'] = self._calc_atr(df)
            
            # 7. OBV (新增)
            indicators['obv'] = self._calc_obv(df)
            
            # 8. Williams %R (新增)
            indicators['wr'] = self._calc_williams_r(df)
            
            # 9. CCI (新增)
            indicators['cci'] = self._calc_cci(df)
            
            # 10. ADX (新增)
            indicators['adx'] = self._calc_adx(df)
            
            # 11. 成交量分析
            indicators['volume'] = self._calc_volume_analysis(df)
            
            # 12. 量价关系 (新增)
            indicators['volume_price'] = self._calc_volume_price_relation(df)
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
        
        return indicators
    
    def _calc_ma(self, df: pd.DataFrame) -> Dict[str, Any]:
        """计算移动平均线"""
        for period in [5, 10, 20, 60, 120]:
            if len(df) >= period:
                df[f'MA{period}'] = df['close'].rolling(window=period).mean()
        
        result = {}
        for period in [5, 10, 20, 60, 120]:
            if f'MA{period}' in df.columns and not pd.isna(df[f'MA{period}'].iloc[-1]):
                result[f'MA{period}'] = round(df[f'MA{period}'].iloc[-1], 2)
        
        # 均线多头/空头排列
        if all(f'MA{p}' in df.columns for p in [5, 10, 20, 60]):
            ma_values = [df[f'MA{p}'].iloc[-1] for p in [5, 10, 20, 60]]
            if all(ma_values[i] > ma_values[i+1] for i in range(len(ma_values)-1)):
                result['alignment'] = "多头排列"
            elif all(ma_values[i] < ma_values[i+1] for i in range(len(ma_values)-1)):
                result['alignment'] = "空头排列"
            else:
                result['alignment'] = "交叉排列"
        
        return result
    
    def _calc_macd(self, df: pd.DataFrame) -> Dict[str, Any]:
        """计算MACD"""
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd_dif'] = exp1 - exp2
        df['macd_dea'] = df['macd_dif'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = 2 * (df['macd_dif'] - df['macd_dea'])
        
        # MACD金叉/死叉判断
        if len(df) >= 2:
            prev_hist = df['macd_hist'].iloc[-2]
            curr_hist = df['macd_hist'].iloc[-1]
            cross_signal = "金叉" if prev_hist < 0 and curr_hist > 0 else "死叉" if prev_hist > 0 and curr_hist < 0 else "无交叉"
        else:
            cross_signal = "无交叉"
        
        return {
            'dif': round(df['macd_dif'].iloc[-1], 3),
            'dea': round(df['macd_dea'].iloc[-1], 3),
            'histogram': round(df['macd_hist'].iloc[-1], 3),
            'cross_signal': cross_signal,
            'trend': "多头" if df['macd_hist'].iloc[-1] > 0 else "空头"
        }
    
    def _calc_rsi(self, df: pd.DataFrame, period: int = 14) -> Dict[str, Any]:
        """计算RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        rsi_value = df['rsi'].iloc[-1]
        
        # RSI区间判断
        if rsi_value >= 80:
            zone = "严重超买"
        elif rsi_value >= 70:
            zone = "超买"
        elif rsi_value <= 20:
            zone = "严重超卖"
        elif rsi_value <= 30:
            zone = "超卖"
        else:
            zone = "正常"
        
        return {
            'value': round(rsi_value, 2),
            'zone': zone,
            'overbought': rsi_value > 70,
            'oversold': rsi_value < 30,
        }
    
    def _calc_kdj(self, df: pd.DataFrame, n: int = 9) -> Dict[str, Any]:
        """计算KDJ"""
        low_min = df['low'].rolling(window=n).min()
        high_max = df['high'].rolling(window=n).max()
        rsv = 100 * (df['close'] - low_min) / (high_max - low_min + self.EPS)
        df['k'] = rsv.ewm(com=2, adjust=False).mean()
        df['d'] = df['k'].ewm(com=2, adjust=False).mean()
        df['j'] = 3 * df['k'] - 2 * df['d']
        
        k, d, j = df['k'].iloc[-1], df['d'].iloc[-1], df['j'].iloc[-1]
        
        # KDJ信号判断
        if k > d and df['k'].iloc[-2] <= df['d'].iloc[-2]:
            signal = "金叉"
        elif k < d and df['k'].iloc[-2] >= df['d'].iloc[-2]:
            signal = "死叉"
        else:
            signal = "无交叉"
        
        # 超买超卖
        if j > 100:
            zone = "超买区"
        elif j < 0:
            zone = "超卖区"
        else:
            zone = "正常"
        
        return {
            'k': round(k, 2),
            'd': round(d, 2),
            'j': round(j, 2),
            'signal': signal,
            'zone': zone
        }
    
    def _calc_bollinger(self, df: pd.DataFrame, n: int = 20) -> Dict[str, Any]:
        """计算布林带"""
        df['bb_middle'] = df['close'].rolling(window=n).mean()
        bb_std = df['close'].rolling(window=n).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100
        
        upper = df['bb_upper'].iloc[-1]
        lower = df['bb_lower'].iloc[-1]
        middle = df['bb_middle'].iloc[-1]
        close = df['close'].iloc[-1]
        
        # 计算布林带位置 (0-100%)
        position = (close - lower) / (upper - lower) * 100 if upper != lower else 50
        
        # 带宽判断
        width = df['bb_width'].iloc[-1]
        if width > 20:
            width_status = "带宽扩张"
        elif width < 10:
            width_status = "带宽收窄"
        else:
            width_status = "带宽正常"
        
        return {
            'upper': round(upper, 2),
            'middle': round(middle, 2),
            'lower': round(lower, 2),
            'position': round(position, 2),
            'width': round(width, 2),
            'width_status': width_status,
            'signal': "突破上轨" if close > upper else "跌破下轨" if close < lower else "轨内运行"
        }
    
    def _calc_atr(self, df: pd.DataFrame, n: int = 14) -> Dict[str, Any]:
        """计算ATR (Average True Range) - 真实波幅"""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=n).mean()
        
        atr_value = atr.iloc[-1]
        atr_pct = atr_value / df['close'].iloc[-1] * 100
        
        # 波动率判断
        if atr_pct > 5:
            volatility = "高波动"
        elif atr_pct > 2:
            volatility = "中等波动"
        else:
            volatility = "低波动"
        
        return {
            'value': round(atr_value, 3),
            'pct': round(atr_pct, 2),
            'volatility': volatility
        }
    
    def _calc_obv(self, df: pd.DataFrame) -> Dict[str, Any]:
        """计算OBV (On-Balance Volume) - 能量潮"""
        obv = [0]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.append(obv[-1] + df['volume'].iloc[i])
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.append(obv[-1] - df['volume'].iloc[i])
            else:
                obv.append(obv[-1])
        
        df['obv'] = obv
        df['obv_ma'] = df['obv'].rolling(window=20).mean()
        
        # OBV趋势判断
        obv_value = df['obv'].iloc[-1]
        obv_ma = df['obv_ma'].iloc[-1]
        
        if obv_value > obv_ma:
            trend = "资金流入"
        else:
            trend = "资金流出"
        
        # OBV与价格背离（添加数据长度检查，防止越界）
        if len(df) >= 20:
            price_trend = df['close'].iloc[-1] > df['close'].iloc[-20]
            obv_trend = df['obv'].iloc[-1] > df['obv'].iloc[-20]
        else:
            price_trend = True
            obv_trend = True
        
        if price_trend and not obv_trend:
            divergence = "顶背离"
        elif not price_trend and obv_trend:
            divergence = "底背离"
        else:
            divergence = "无背离"
        
        return {
            'value': int(obv_value),
            'trend': trend,
            'divergence': divergence
        }
    
    def _calc_williams_r(self, df: pd.DataFrame, n: int = 14) -> Dict[str, Any]:
        """计算Williams %R - 威廉指标"""
        high_n = df['high'].rolling(window=n).max()
        low_n = df['low'].rolling(window=n).min()
        df['wr'] = (high_n - df['close']) / (high_n - low_n) * -100
        
        wr_value = df['wr'].iloc[-1]
        
        if wr_value > -20:
            zone = "超买"
        elif wr_value < -80:
            zone = "超卖"
        else:
            zone = "正常"
        
        return {
            'value': round(wr_value, 2),
            'zone': zone
        }
    
    def _calc_cci(self, df: pd.DataFrame, n: int = 20) -> Dict[str, Any]:
        """计算CCI (Commodity Channel Index) - 顺势指标"""
        tp = (df['high'] + df['low'] + df['close']) / 3
        ma = tp.rolling(window=n).mean()
        md = (tp - ma).abs().rolling(window=n).mean()
        
        df['cci'] = (tp - ma) / (0.015 * md)
        
        cci_value = df['cci'].iloc[-1]
        
        if cci_value > 100:
            zone = "超买"
        elif cci_value < -100:
            zone = "超卖"
        else:
            zone = "正常"
        
        return {
            'value': round(cci_value, 2),
            'zone': zone
        }
    
    def _calc_adx(self, df: pd.DataFrame, n: int = 14) -> Dict[str, Any]:
        """计算ADX (Average Directional Index) - 平均趋向指标"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # 计算+DM和-DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        # 计算TR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 平滑处理
        atr = tr.rolling(window=n).mean()
        plus_di = 100 * (plus_dm.rolling(window=n).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=n).mean() / atr)
        
        # 计算DX和ADX（添加除零保护）
        di_sum = plus_di + minus_di
        dx = 100 * abs(plus_di - minus_di) / di_sum.replace(0, self.EPS)
        adx = dx.rolling(window=n).mean()
        
        adx_value = adx.iloc[-1]
        pdi = plus_di.iloc[-1]
        mdi = minus_di.iloc[-1]
        
        # 趋势强度判断
        if adx_value > 25:
            trend_strength = "强趋势"
        elif adx_value > 15:
            trend_strength = "中等趋势"
        else:
            trend_strength = "无趋势"
        
        # 趋势方向
        if pdi > mdi:
            direction = "上升趋势"
        else:
            direction = "下降趋势"
        
        return {
            'adx': round(adx_value, 2),
            'pdi': round(pdi, 2),
            'mdi': round(mdi, 2),
            'trend_strength': trend_strength,
            'direction': direction
        }
    
    def _calc_volume_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """成交量分析"""
        df['volume_ma5'] = df['volume'].rolling(window=5).mean()
        df['volume_ma20'] = df['volume'].rolling(window=20).mean()
        
        current_vol = df['volume'].iloc[-1]
        ma5_vol = df['volume_ma5'].iloc[-1]
        ma20_vol = df['volume_ma20'].iloc[-1]
        
        # 量比
        vol_ratio = current_vol / ma5_vol if ma5_vol > 0 else 1
        
        # 放量/缩量判断
        if vol_ratio > 2:
            vol_status = "巨量"
        elif vol_ratio > 1.5:
            vol_status = "放量"
        elif vol_ratio < 0.5:
            vol_status = "地量"
        elif vol_ratio < 0.8:
            vol_status = "缩量"
        else:
            vol_status = "平量"
        
        return {
            'current': int(current_vol),
            'ma5': int(ma5_vol),
            'ma20': int(ma20_vol),
            'ratio': round(vol_ratio, 2),
            'status': vol_status
        }
    
    def _calc_volume_price_relation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """量价关系分析"""
        if len(df) < 5:
            return {'relation': '数据不足'}
        
        recent = df.tail(5)
        
        # 价格变化
        price_change = (recent['close'].iloc[-1] - recent['close'].iloc[0]) / recent['close'].iloc[0]
        
        # 成交量变化
        vol_avg_before = recent['volume'].iloc[:3].mean()
        vol_avg_after = recent['volume'].iloc[-3:].mean()
        vol_change = (vol_avg_after - vol_avg_before) / vol_avg_before if vol_avg_before > 0 else 0
        
        # 量价关系判断
        if price_change > 0 and vol_change > 0:
            relation = "量价齐升"
            signal = "看涨"
        elif price_change > 0 and vol_change < 0:
            relation = "价升量缩"
            signal = "谨慎"
        elif price_change < 0 and vol_change > 0:
            relation = "价跌量增"
            signal = "看跌"
        elif price_change < 0 and vol_change < 0:
            relation = "量价齐跌"
            signal = "观望"
        else:
            relation = "量价平稳"
            signal = "中性"
        
        return {
            'relation': relation,
            'signal': signal,
            'price_change': round(price_change * 100, 2),
            'volume_change': round(vol_change * 100, 2)
        }
    
    # ==================== K线形态识别 ====================
    
    def _identify_all_patterns(self, df: pd.DataFrame, indicators: Dict) -> List[str]:
        """识别所有K线形态"""
        patterns = []
        
        if len(df) < 10:
            return patterns
        
        try:
            # 单根K线形态
            patterns.extend(self._identify_single_candle_patterns(df))
            
            # 双根K线形态
            patterns.extend(self._identify_double_candle_patterns(df))
            
            # 三根K线形态
            patterns.extend(self._identify_triple_candle_patterns(df))
            
            # 多根K线形态
            patterns.extend(self._identify_multi_candle_patterns(df))
            
            # 技术指标形态
            patterns.extend(self._identify_indicator_patterns(df, indicators))
            
        except Exception as e:
            logger.error(f"识别形态失败: {e}")
        
        return patterns
    
    def _identify_single_candle_patterns(self, df: pd.DataFrame) -> List[str]:
        """单根K线形态"""
        patterns = []
        last = df.iloc[-1]
        
        body = abs(last['close'] - last['open'])
        lower_shadow = min(last['open'], last['close']) - last['low']
        upper_shadow = last['high'] - max(last['open'], last['close'])
        total_range = last['high'] - last['low']
        
        # 锤子线（看涨）
        if lower_shadow > 2 * body and upper_shadow < body and body > 0:
            patterns.append("锤子线(看涨)")
        
        # 流星线（看跌）
        if upper_shadow > 2 * body and lower_shadow < body and body > 0:
            patterns.append("流星线(看跌)")
        
        # 十字星
        if body < total_range * 0.1 and total_range > 0:
            # 判断位置
            if last['close'] > df['close'].rolling(10).mean().iloc[-1]:
                patterns.append("高位十字星(看跌)")
            else:
                patterns.append("低位十字星(看涨)")
        
        # 大阳线
        if body > total_range * 0.7 and last['close'] > last['open']:
            patterns.append("大阳线(看涨)")
        
        # 大阴线
        if body > total_range * 0.7 and last['close'] < last['open']:
            patterns.append("大阴线(看跌)")
        
        return patterns
    
    def _identify_double_candle_patterns(self, df: pd.DataFrame) -> List[str]:
        """双根K线形态"""
        patterns = []
        
        if len(df) < 2:
            return patterns
        
        prev = df.iloc[-2]
        curr = df.iloc[-1]
        
        prev_body = abs(prev['close'] - prev['open'])
        curr_body = abs(curr['close'] - curr['open'])
        
        # 看涨吞没
        if (prev['close'] < prev['open'] and  # 前一根是阴线
            curr['close'] > curr['open'] and  # 当前是阳线
            curr['open'] < prev['close'] and  # 当前开盘低于前一根收盘
            curr['close'] > prev['open']):    # 当前收盘高于前一根开盘
            patterns.append("看涨吞没")
        
        # 看跌吞没
        if (prev['close'] > prev['open'] and  # 前一根是阳线
            curr['close'] < curr['open'] and  # 当前是阴线
            curr['open'] > prev['close'] and  # 当前开盘高于前一根收盘
            curr['close'] < prev['open']):    # 当前收盘低于前一根开盘
            patterns.append("看跌吞没")
        
        # 看涨孕线
        if (prev['close'] > prev['open'] and  # 前一根是阳线
            curr['close'] > curr['open'] and  # 当前是阳线
            curr['open'] > prev['open'] and   # 当前开盘在前一根实体内
            curr['close'] < prev['close']):
            patterns.append("看涨孕线")
        
        # 看跌孕线
        if (prev['close'] < prev['open'] and  # 前一根是阴线
            curr['close'] < curr['open'] and  # 当前是阴线
            curr['open'] < prev['open'] and   # 当前开盘在前一根实体内
            curr['close'] > prev['close']):
            patterns.append("看跌孕线")
        
        # 刺透形态
        if (prev['close'] < prev['open'] and  # 前一根是阴线
            curr['close'] > curr['open'] and  # 当前是阳线
            curr['open'] < prev['low'] and    # 当前开盘低于前一根最低
            curr['close'] > (prev['open'] + prev['close']) / 2):  # 收盘超过前一根实体中点
            patterns.append("刺透形态(看涨)")
        
        # 乌云盖顶
        if (prev['close'] > prev['open'] and  # 前一根是阳线
            curr['close'] < curr['open'] and  # 当前是阴线
            curr['open'] > prev['high'] and   # 当前开盘高于前一根最高
            curr['close'] < (prev['open'] + prev['close']) / 2):  # 收盘低于前一根实体中点
            patterns.append("乌云盖顶(看跌)")
        
        return patterns
    
    def _identify_triple_candle_patterns(self, df: pd.DataFrame) -> List[str]:
        """三根K线形态"""
        patterns = []
        
        if len(df) < 3:
            return patterns
        
        c1 = df.iloc[-3]
        c2 = df.iloc[-2]
        c3 = df.iloc[-1]
        
        # 早晨之星
        c1_body = abs(c1['close'] - c1['open'])
        c2_body = abs(c2['close'] - c2['open'])
        c3_body = abs(c3['close'] - c3['open'])
        
        if (c1['close'] < c1['open'] and  # 第一根是阴线
            c2_body < c1_body * 0.3 and   # 第二根是小实体
            c3['close'] > c3['open'] and  # 第三根是阳线
            c3['close'] > (c1['open'] + c1['close']) / 2):  # 第三根收盘超过第一根中点
            patterns.append("早晨之星(看涨)")
        
        # 黄昏之星
        if (c1['close'] > c1['open'] and  # 第一根是阳线
            c2_body < c1_body * 0.3 and   # 第二根是小实体
            c3['close'] < c3['open'] and  # 第三根是阴线
            c3['close'] < (c1['open'] + c1['close']) / 2):  # 第三根收盘低于第一根中点
            patterns.append("黄昏之星(看跌)")
        
        # 三只白兵
        if (c1['close'] > c1['open'] and
            c2['close'] > c2['open'] and
            c3['close'] > c3['open'] and
            c2['close'] > c1['close'] and
            c3['close'] > c2['close']):
            patterns.append("三只白兵(看涨)")
        
        # 三只乌鸦
        if (c1['close'] < c1['open'] and
            c2['close'] < c2['open'] and
            c3['close'] < c3['open'] and
            c2['close'] < c1['close'] and
            c3['close'] < c2['close']):
            patterns.append("三只乌鸦(看跌)")
        
        return patterns
    
    def _identify_multi_candle_patterns(self, df: pd.DataFrame) -> List[str]:
        """多根K线形态（双底、双顶、头肩形态等）"""
        patterns = []
        
        if len(df) < 30:
            return patterns
        
        try:
            # 寻找局部极值点
            highs = df['high'].values
            lows = df['low'].values
            
            # 双底检测
            double_bottom = self._detect_double_bottom(df, lows)
            if double_bottom:
                patterns.append("双底(看涨)")
            
            # 双顶检测
            double_top = self._detect_double_top(df, highs)
            if double_top:
                patterns.append("双顶(看跌)")
            
            # 头肩底检测
            head_shoulder_bottom = self._detect_head_shoulder_bottom(df, lows)
            if head_shoulder_bottom:
                patterns.append("头肩底(看涨)")
            
            # 头肩顶检测
            head_shoulder_top = self._detect_head_shoulder_top(df, highs)
            if head_shoulder_top:
                patterns.append("头肩顶(看跌)")
            
        except Exception as e:
            logger.warning(f"多根K线形态识别失败: {e}")
        
        return patterns
    
    def _detect_double_bottom(self, df: pd.DataFrame, lows: np.ndarray) -> bool:
        """检测双底形态"""
        window = 20
        if len(lows) < window:
            return False
        
        recent_lows = lows[-window:]
        
        # 找两个最低点
        sorted_indices = np.argsort(recent_lows)[:2]
        if len(sorted_indices) == 2:
            idx1, idx2 = sorted(sorted_indices)
            # 两个低点间隔要足够
            if abs(idx2 - idx1) >= 5:
                # 两个低点价格接近
                if abs(recent_lows[idx1] - recent_lows[idx2]) / recent_lows[idx1] < 0.03:
                    return True
        
        return False
    
    def _detect_double_top(self, df: pd.DataFrame, highs: np.ndarray) -> bool:
        """检测双顶形态"""
        window = 20
        if len(highs) < window:
            return False
        
        recent_highs = highs[-window:]
        
        # 找两个最高点
        sorted_indices = np.argsort(recent_highs)[-2:]
        if len(sorted_indices) == 2:
            idx1, idx2 = sorted(sorted_indices)
            if abs(idx2 - idx1) >= 5:
                if abs(recent_highs[idx1] - recent_highs[idx2]) / recent_highs[idx1] < 0.03:
                    return True
        
        return False
    
    def _detect_head_shoulder_bottom(self, df: pd.DataFrame, lows: np.ndarray) -> bool:
        """检测头肩底形态（简化版）"""
        # 简化处理：寻找三个低点，中间最低
        window = 30
        if len(lows) < window:
            return False
        
        recent_lows = lows[-window:]
        
        # 找最低点
        min_idx = np.argmin(recent_lows)
        
        # 在最低点两侧找肩部
        if min_idx > 5 and min_idx < window - 5:
            left_shoulder = np.min(recent_lows[:min_idx])
            right_shoulder = np.min(recent_lows[min_idx+1:])
            
            # 两肩高度接近
            if abs(left_shoulder - right_shoulder) / left_shoulder < 0.05:
                return True
        
        return False
    
    def _detect_head_shoulder_top(self, df: pd.DataFrame, highs: np.ndarray) -> bool:
        """检测头肩顶形态（简化版）"""
        window = 30
        if len(highs) < window:
            return False
        
        recent_highs = highs[-window:]
        
        max_idx = np.argmax(recent_highs)
        
        if max_idx > 5 and max_idx < window - 5:
            left_shoulder = np.max(recent_highs[:max_idx])
            right_shoulder = np.max(recent_highs[max_idx+1:])
            
            if abs(left_shoulder - right_shoulder) / left_shoulder < 0.05:
                return True
        
        return False
    
    def _identify_indicator_patterns(self, df: pd.DataFrame, indicators: Dict) -> List[str]:
        """技术指标形态"""
        patterns = []
        
        # MACD金叉/死叉
        macd_signal = indicators.get('macd', {}).get('cross_signal', '')
        if macd_signal == '金叉':
            patterns.append("MACD金叉")
        elif macd_signal == '死叉':
            patterns.append("MACD死叉")
        
        # KDJ金叉/死叉
        kdj_signal = indicators.get('kdj', {}).get('signal', '')
        if kdj_signal == '金叉':
            patterns.append("KDJ金叉")
        elif kdj_signal == '死叉':
            patterns.append("KDJ死叉")
        
        # 均线金叉/死叉
        ma_alignment = indicators.get('ma', {}).get('alignment', '')
        if ma_alignment == '多头排列':
            patterns.append("均线多头排列")
        elif ma_alignment == '空头排列':
            patterns.append("均线空头排列")
        
        # 布林带突破
        bb_signal = indicators.get('bollinger', {}).get('signal', '')
        if bb_signal:
            patterns.append(f"布林带{bb_signal}")
        
        # OBV背离
        obv_divergence = indicators.get('obv', {}).get('divergence', '')
        if obv_divergence and obv_divergence != '无背离':
            patterns.append(f"OBV{obv_divergence}")
        
        return patterns
    
    # ==================== 趋势分析 ====================
    
    def _analyze_trend(self, df: pd.DataFrame, indicators: Dict) -> Tuple[str, int]:
        """分析趋势"""
        try:
            # 综合多个指标判断趋势
            scores = []
            
            # 1. 均线趋势
            ma_alignment = indicators.get('ma', {}).get('alignment', '')
            if ma_alignment == '多头排列':
                scores.append(80)
            elif ma_alignment == '空头排列':
                scores.append(20)
            else:
                scores.append(50)
            
            # 2. ADX趋势
            adx = indicators.get('adx', {})
            adx_value = adx.get('adx', 0)
            adx_direction = adx.get('direction', '')
            if adx_value > 25:
                if adx_direction == '上升趋势':
                    scores.append(80)
                else:
                    scores.append(20)
            else:
                scores.append(50)
            
            # 3. MACD趋势
            macd_trend = indicators.get('macd', {}).get('trend', '')
            if macd_trend == '多头':
                scores.append(70)
            else:
                scores.append(30)
            
            # 4. 价格与均线关系
            current_price = df['close'].iloc[-1]
            ma20 = indicators.get('ma', {}).get('MA20', current_price)
            if current_price > ma20:
                scores.append(65)
            else:
                scores.append(35)
            
            # 综合评分
            avg_score = sum(scores) / len(scores)
            
            if avg_score >= 65:
                trend = "上升趋势"
                strength = int(avg_score)
            elif avg_score <= 35:
                trend = "下降趋势"
                strength = int(100 - avg_score)
            else:
                trend = "震荡整理"
                strength = 50
            
            return trend, strength
            
        except Exception as e:
            logger.error(f"分析趋势失败: {e}")
            return "未知", 50
    
    # ==================== 支撑阻力位 ====================
    
    def _calculate_support_resistance(self, df: pd.DataFrame) -> Tuple[List[float], List[float]]:
        """计算支撑阻力位"""
        try:
            # 方法1：近期高低点
            recent_highs = df['high'].tail(20).nlargest(5).values
            recent_lows = df['low'].tail(20).nsmallest(5).values
            
            # 方法2：布林带
            bb_upper = df['bb_upper'].iloc[-1] if 'bb_upper' in df.columns else None
            bb_lower = df['bb_lower'].iloc[-1] if 'bb_lower' in df.columns else None
            
            resistance_levels = sorted(set([round(x, 2) for x in recent_highs[:3]]), reverse=True)
            support_levels = sorted(set([round(x, 2) for x in recent_lows[:3]]))
            
            # 添加布林带作为参考
            if bb_upper:
                resistance_levels.append(round(bb_upper, 2))
            if bb_lower:
                support_levels.append(round(bb_lower, 2))
            
            # 去重并排序
            resistance_levels = sorted(list(set(resistance_levels)), reverse=True)[:3]
            support_levels = sorted(list(set(support_levels)))[:3]
            
            return support_levels, resistance_levels
            
        except Exception as e:
            logger.error(f"计算支撑阻力失败: {e}")
            return [], []
    
    # ==================== 信号生成 ====================
    
    def _generate_comprehensive_signal(
        self,
        df: pd.DataFrame,
        indicators: Dict,
        trend: str,
        patterns: List[str]
    ) -> Tuple[Signal, int]:
        """生成综合交易信号"""
        score = 50  # 中性基准
        
        # 1. 趋势得分 (权重30%)
        if trend == "上升趋势":
            score += 15
        elif trend == "下降趋势":
            score -= 15
        
        # 2. 技术指标得分 (权重40%)
        indicator_score = self._calc_indicator_score(indicators)
        score += (indicator_score - 50) * 0.4
        
        # 3. 形态得分 (权重30%)
        pattern_score = self._calc_pattern_score(patterns)
        score += (pattern_score - 50) * 0.3
        
        # 4. 量价关系得分
        vp_signal = indicators.get('volume_price', {}).get('signal', '中性')
        if vp_signal == '看涨':
            score += 5
        elif vp_signal == '看跌':
            score -= 5
        
        # 确定信号
        score = max(0, min(100, score))
        
        if score >= 70:
            signal = Signal.STRONG_BUY
        elif score >= 58:
            signal = Signal.BUY
        elif score <= 30:
            signal = Signal.STRONG_SELL
        elif score <= 42:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD
        
        confidence = min(100, max(10, int(abs(score - 50) * 2)))
        
        return signal, confidence
    
    def _calc_indicator_score(self, indicators: Dict) -> int:
        """计算技术指标综合得分"""
        score = 50
        
        # RSI
        rsi = indicators.get('rsi', {}).get('value', 50)
        if rsi < 30:
            score += 15
        elif rsi < 40:
            score += 8
        elif rsi > 70:
            score -= 15
        elif rsi > 60:
            score -= 8
        
        # MACD
        macd_hist = indicators.get('macd', {}).get('histogram', 0)
        if macd_hist > 0:
            score += 10
        else:
            score -= 10
        
        # KDJ
        kdj = indicators.get('kdj', {})
        j = kdj.get('j', 50)
        if j < 0:
            score += 10
        elif j > 100:
            score -= 10
        
        # ADX
        adx = indicators.get('adx', {})
        if adx.get('direction') == '上升趋势' and adx.get('adx', 0) > 25:
            score += 8
        elif adx.get('direction') == '下降趋势' and adx.get('adx', 0) > 25:
            score -= 8
        
        # 布林带位置
        bb_pos = indicators.get('bollinger', {}).get('position', 50)
        if bb_pos < 20:
            score += 8
        elif bb_pos > 80:
            score -= 8
        
        return max(0, min(100, score))
    
    def _calc_pattern_score(self, patterns: List[str]) -> int:
        """计算形态综合得分"""
        score = 50
        
        for pattern in patterns:
            if any(bull in pattern for bull in self.BULLISH_PATTERNS):
                score += 8
            elif any(bear in pattern for bear in self.BEARISH_PATTERNS):
                score -= 8
        
        return max(0, min(100, score))

    # ==================== 工具方法 ====================

    @staticmethod
    def _sanitize_numpy(obj):
        """递归转换numpy类型为Python原生类型，避免Pydantic序列化失败"""
        import numpy as np
        if isinstance(obj, dict):
            return {k: TechnicalAnalyst._sanitize_numpy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [TechnicalAnalyst._sanitize_numpy(v) for v in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    # ==================== LLM增强分析 ====================

    def _llm_enhance_analysis(
        self,
        stock_data: StockData,
        trend: str,
        indicators: Dict,
        patterns: List[str],
        signal: Signal
    ) -> Dict[str, str]:
        """
        使用LLM对技术指标进行深度解读

        基于已计算的真实指标数据，调用LLM生成深度分析

        Args:
            stock_data: 股票数据
            trend: 趋势判断
            indicators: 技术指标字典
            patterns: 识别的形态列表
            signal: 交易信号

        Returns:
            LLM结构化输出字典
        """
        # 构建数据摘要（只包含真实计算结果）
        data_parts = [
            f"股票={stock_data.stock_name}({stock_data.stock_code})",
            f"当前价格={stock_data.current_price}",
            f"趋势={trend}",
            f"RSI={indicators.get('rsi', {}).get('value', 'N/A')}",
            f"RSI区间={indicators.get('rsi', {}).get('zone', 'N/A')}",
            f"MACD_DIF={indicators.get('macd', {}).get('dif', 'N/A')}",
            f"MACD_DEA={indicators.get('macd', {}).get('dea', 'N/A')}",
            f"MACD柱={indicators.get('macd', {}).get('histogram', 'N/A')}",
            f"MACD交叉={indicators.get('macd', {}).get('cross_signal', 'N/A')}",
            f"KDJ_K={indicators.get('kdj', {}).get('k', 'N/A')}",
            f"KDJ_D={indicators.get('kdj', {}).get('d', 'N/A')}",
            f"KDJ_J={indicators.get('kdj', {}).get('j', 'N/A')}",
            f"布林带位置={indicators.get('bollinger', {}).get('position', 'N/A')}%",
            f"布林带信号={indicators.get('bollinger', {}).get('signal', 'N/A')}",
            f"ATR波动率={indicators.get('atr', {}).get('pct', 'N/A')}%",
            f"ADX={indicators.get('adx', {}).get('adx', 'N/A')}",
            f"ADX趋势强度={indicators.get('adx', {}).get('trend_strength', 'N/A')}",
            f"均线排列={indicators.get('ma', {}).get('alignment', 'N/A')}",
            f"量价关系={indicators.get('volume_price', {}).get('relation', 'N/A')}",
            f"成交量状态={indicators.get('volume', {}).get('status', 'N/A')}",
            f"OBV趋势={indicators.get('obv', {}).get('trend', 'N/A')}",
            f"OBV背离={indicators.get('obv', {}).get('divergence', 'N/A')}",
            f"信号={signal.value}",
        ]

        if patterns:
            data_parts.append(f"形态={', '.join(patterns[:5])}")

        data_summary = ", ".join(data_parts)

        instruction = (
            f"基于以上技术指标数据，对{stock_data.stock_name}的技术面进行深度解读。"
            "请分析：1)当前技术面整体状况；2)关键信号及其含义；3)需要关注的风险点。"
            "所有结论必须基于提供的数据，不得编造指标数值。"
        )

        output_fields = ["summary", "key_signals", "risk_warnings"]

        return self._call_llm_with_data(data_summary, instruction, output_fields)

    # ==================== 报告生成 ====================
    
    def _generate_summary(
        self,
        stock_data: StockData,
        trend: str,
        indicators: Dict,
        patterns: List[str],
        signal: Signal
    ) -> str:
        """生成分析摘要"""
        lines = [
            f"=" * 50,
            f"{stock_data.stock_name}({stock_data.stock_code}) 技术分析报告",
            f"=" * 50,
            f"",
            f"【趋势判断】{trend}",
            f"",
            f"【技术指标】",
            f"• RSI: {indicators.get('rsi', {}).get('value', 'N/A')} ({indicators.get('rsi', {}).get('zone', '')})",
            f"• MACD: DIF={indicators.get('macd', {}).get('dif', 'N/A')}, DEA={indicators.get('macd', {}).get('dea', 'N/A')}",
            f"• KDJ: K={indicators.get('kdj', {}).get('k', 'N/A')}, D={indicators.get('kdj', {}).get('d', 'N/A')}, J={indicators.get('kdj', {}).get('j', 'N/A')}",
            f"• 布林带: 上轨={indicators.get('bollinger', {}).get('upper', 'N/A')}, 下轨={indicators.get('bollinger', {}).get('lower', 'N/A')}",
            f"• ATR: {indicators.get('atr', {}).get('pct', 'N/A')}% ({indicators.get('atr', {}).get('volatility', '')})",
            f"• ADX: {indicators.get('adx', {}).get('adx', 'N/A')} ({indicators.get('adx', {}).get('trend_strength', '')})",
            f"",
            f"【均线系统】",
            f"• MA5={indicators.get('ma', {}).get('MA5', 'N/A')}, MA10={indicators.get('ma', {}).get('MA10', 'N/A')}",
            f"• MA20={indicators.get('ma', {}).get('MA20', 'N/A')}, MA60={indicators.get('ma', {}).get('MA60', 'N/A')}",
            f"• 排列: {indicators.get('ma', {}).get('alignment', '')}",
            f"",
            f"【量价关系】{indicators.get('volume_price', {}).get('relation', '')}",
            f"【成交量】{indicators.get('volume', {}).get('status', '')} (量比{indicators.get('volume', {}).get('ratio', '')})",
            f"",
        ]
        
        if patterns:
            bullish = [p for p in patterns if any(b in p for b in self.BULLISH_PATTERNS)]
            bearish = [p for p in patterns if any(b in p for b in self.BEARISH_PATTERNS)]
            
            lines.append("【形态识别】")
            if bullish:
                lines.append(f"  看涨形态: {', '.join(bullish)}")
            if bearish:
                lines.append(f"  看跌形态: {', '.join(bearish)}")
            lines.append("")
        
        signal_color = "🟢" if "买入" in signal.value else "🔴" if "卖出" in signal.value else "🟡"
        lines.append(f"【技术信号】{signal_color} {signal.value}")
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def _create_empty_analysis(self) -> TechnicalAnalysis:
        """创建空分析结果"""
        return TechnicalAnalysis(
            trend="数据不足",
            trend_strength=0,
            support_levels=[],
            resistance_levels=[],
            indicators={},
            patterns=[],
            summary="缺少价格数据，无法完成技术分析",
            signal=Signal.HOLD,
            confidence=0
        )