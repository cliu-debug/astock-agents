# AStockAgents 🤖

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-CC%20BY--NC%204.0-blue)](LICENSE)
[![Stars](https://img.shields.io/github/stars/astock-agents/astock-agents?style=social)](https://github.com/astock-agents/astock-agents)

**多智能体协同股票分析系统**

基于 LangGraph 构建的多智能体协同分析框架，实现技术分析、基本面分析、情绪分析、多空辩论和风险评估的全流程自动化分析。

[快速开始](#快速开始) · [功能特性](#功能特性) · [架构设计](#架构设计) · [API文档](#api文档)

</div>

---

## 📖 项目简介

AStockAgents 是一个面向A股市场的智能分析系统，采用多智能体协同架构，模拟专业投资研究团队的工作流程：

- **技术分析师**: 技术指标计算、K线形态识别、趋势判断
- **基本面分析师**: 财务数据分析、估值评估、成长性判断
- **情绪分析师**: 市场情绪、热点题材、资金流向
- **多空研究员**: 多空观点辩论、论据支撑
- **风险管理器**: 风险评估、仓位建议、止损策略

## ✨ 功能特性

### 核心功能

- 🔥 **多源数据整合**: 通达信、腾讯财经、Akshare多数据源自动切换
- 📊 **全面技术分析**: 10+技术指标、15+K线形态识别
- 🤖 **智能体协同**: LangGraph工作流编排，多智能体协作
- ⚖️ **多空辩论机制**: 模拟多空观点对抗，提供决策参考
- 📈 **风险评估**: 三维度风险评估，提供投资建议

### 技术指标

| 指标 | 说明 |
|------|------|
| MA(5,10,20,60,120) | 移动平均线系统 |
| MACD | 指数平滑异同移动平均线 |
| RSI | 相对强弱指标 |
| KDJ | 随机指标 |
| Bollinger | 布林带 |
| ATR | 真实波幅 |
| OBV | 能量潮 |
| Williams %R | 威廉指标 |
| CCI | 顺势指标 |
| ADX | 平均趋向指标 |

### K线形态

- 吞没形态（看涨/看跌）
- 孕线形态
- 早晨之星/黄昏之星
- 锤子线/流星线
- 双底/双顶
- 头肩顶/头肩底
- 三只白兵/三只乌鸦

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/astock-agents/astock-agents.git
cd astock-agents

# 安装依赖
pip install -r requirements.txt

# 安装项目
pip install -e .
```

### 运行Demo

```bash
# 命令行Demo
python examples/demo.py --code 600519.SH --name 贵州茅台

# Web界面
python -m astock_agents.web.app
# 访问 http://localhost:8000
```

### Docker部署

```bash
# 使用Docker Compose
docker-compose up -d
```

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                     AStockAgents                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐    │
│  │   数据层    │   │  智能体层   │   │   应用层    │    │
│  │             │   │             │   │             │    │
│  │ - Mootdx    │   │ - Technical │   │ - CLI       │    │
│  │ - Tencent   │   │ - Fundament │   │ - Web UI    │    │
│  │ - Akshare   │   │ - Sentiment │   │ - API       │    │
│  │             │   │ - Bull/Bear │   │             │    │
│  │             │   │ - Risk      │   │             │    │
│  └─────────────┘   └─────────────┘   └─────────────┘    │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │              工作流编排 (LangGraph)                │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

详细架构请参考 [架构文档](docs/ARCHITECTURE.md)

## 📚 使用指南

### Python API

```python
from astock_agents.agents.technical_analyst import TechnicalAnalyst
from astock_agents.models.stock_data import StockData

# 创建分析师
analyst = TechnicalAnalyst()

# 执行分析
result = analyst.analyze(stock_data)

print(f"趋势: {result.trend}")
print(f"信号: {result.signal.value}")
print(f"置信度: {result.confidence}%")
```

### REST API

```bash
# 分析股票
curl "http://localhost:8000/api/analyze?stock_code=600519.SH&stock_name=贵州茅台"

# 获取热门股票
curl "http://localhost:8000/api/stocks/popular"

# 多股对比
curl "http://localhost:8000/api/compare?stock_codes=600519.SH,000858.SZ"
```

详细使用请参考 [使用指南](docs/USER_GUIDE.md)

## 📖 API文档

启动Web服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🧪 测试

```bash
# 运行所有测试
pytest

# 带覆盖率报告
pytest --cov=astock_agents

# 运行特定测试
pytest tests/test_agents_layer.py -v
```

## 📁 项目结构

```
astock-agents/
├── astock_agents/           # 主包
│   ├── agents/              # 智能体模块
│   │   ├── technical_analyst.py
│   │   ├── fundamental_analyst.py
│   │   ├── sentiment_analyst.py
│   │   ├── bull_researcher.py
│   │   ├── bear_researcher.py
│   │   ├── trader.py
│   │   └── risk_manager.py
│   ├── data/                # 数据模块
│   │   ├── base_client.py
│   │   ├── mootdx_client.py
│   │   ├── tencent_client.py
│   │   ├── akshare_client.py
│   │   └── data_manager.py
│   ├── models/              # 数据模型
│   ├── workflow/            # 工作流
│   ├── web/                 # Web界面
│   └── utils/               # 工具函数
├── tests/                   # 测试文件
├── examples/                # 示例代码
├── docs/                    # 文档
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## ⚠️ 免责声明

**本系统提供的分析结果仅供参考，不构成任何投资建议。**

股市有风险，投资需谨慎。使用本系统进行投资决策造成的任何损失，开发者不承担任何责任。请结合自身风险承受能力，独立做出投资决策。

## 🙏 致谢

- [LangChain](https://github.com/langchain-ai/langchain) - LLM应用框架
- [LangGraph](https://github.com/langchain-ai/langgraph) - 工作流编排
- [Akshare](https://github.com/akfamily/akshare) - 金融数据接口
- [Mootdx](https://github.com/moomindesigns/mootdx) - 通达信接口

---

<div align="center">

如果这个项目对你有帮助，请给一个 ⭐️ Star 支持一下！

Made with ❤️ by AStockAgents Team

</div>
