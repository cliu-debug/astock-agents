# AStockAgents 🤖

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-CC%20BY--NC%204.0-blue)](LICENSE)
[![Stars](https://img.shields.io/github/stars/astock-agents/astock-agents?style=social)](https://github.com/astock-agents/astock-agents)
[![GitHub Release](https://img.shields.io/github/v/release/astock-agents/astock-agents)](https://github.com/astock-agents/astock-agents/releases)

**Multi-Agent Collaborative Stock Analysis System for A-Share Market**

A comprehensive AI-driven stock analysis framework built on LangGraph, featuring 10 specialized agents for technical analysis, fundamental analysis, sentiment analysis, bull/bear debate, risk management, and more.

[Quick Start](#quick-start) · [Features](#features) · [Architecture](#architecture) · [LLM Support](#multi-llm-support) · [API Docs](#api-docs)

</div>

---

## 📖 Introduction

AStockAgents is an intelligent quantitative analysis system for the **A-Share market (China)**, using a multi-agent collaborative architecture that simulates the workflow of professional investment research teams.

### 🎯 Core Innovations

| Innovation | Description |
|------------|-------------|
| **10 Specialized Agents** | Technical/Fundamental/Sentiment/News/CapitalFlow/BullBear/Trading/Risk |
| **Three-Layer Hybrid Architecture** | Rule Engine + LLM Enhancement + Risk Control |
| **Annual Ring Memory System** | Investment Profile, Preference Learning, Continuous Evolution |
| **Game Theory Debate** | Nash Equilibrium, Prisoner's Dilemma, Multi-round Confrontation |
| **Financial Compliance Design** | Disclaimer Injection, FOMO Detection, Audit Trail |
| **Multi-Source Data Fallback** | mootdx→akshare→Tencent→Eastmoney→Baidu→Cninfo |

### 👥 Agent Team

```
Data Acquisition ─┬── Technical Analyst ──┐
                  ├── Fundamental Analyst ──┤
                  ├── Sentiment Analyst   ──┤
                  ├── News Analyst       ──┤
                  ├── Capital Flow Analyst ──┤
                  └── Macro Analyst      ──┘
                                      │
                    Bull Researcher ←──→ Bear Researcher
                           (Game Theory Debate)
                                │
                    Trader ←────→ Risk Manager
                                ↓
                         Decision Output
```

---

## ✨ Features

### Core Functions

- 🔥 **Multi-Source Data Integration**: 6-level fallback, full A-Share coverage
- 📊 **Comprehensive Technical Analysis**: 10+ indicators, 15+ candlestick patterns
- 🤖 **LLM Intelligence Enhancement**: Local models/OpenRouter free/Chinese LLMs
- ⚖️ **Game Theory Debate**: Multi-round confrontation, Nash equilibrium
- 📈 **Complete Backtesting System**: 3-year A-Share backtest, Sharpe/MaxDD/Win Rate
- 🛡️ **Financial Compliance Design**: Disclaimer, FOMO detection, audit trail
- 🧠 **Annual Ring Memory System**: Investment profile, preference learning
- 🔌 **MCP Protocol Support**: 6 standardized financial tool interfaces

### Technical Indicators

| Indicator | Description |
|-----------|-------------|
| MA(5,10,20,60,120) | Moving Average System |
| MACD | Moving Average Convergence Divergence |
| RSI | Relative Strength Index |
| KDJ | Stochastic Indicator |
| Bollinger | Bollinger Bands |
| ATR | Average True Range |
| OBV | On-Balance Volume |
| Williams %R | Williams Percent Range |
| CCI | Commodity Channel Index |
| ADX | Average Directional Index |

### Candlestick Patterns

- Engulfing (Bullish/Bearish)
- Harami
- Morning/Evening Star
- Hammer/Shooting Star
- Double Bottom/Double Top
- Head and Shoulders
- Three White Soldiers/Three Black Crows

---

## 🚀 Quick Start

### Requirements

- Python 3.10+
- Windows/Linux/macOS

### Installation

```bash
# Clone the project
git clone https://github.com/astock-agents/astock-agents.git
cd astock-agents

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install package
pip install -e .
```

### Configuration

```bash
# Copy config template
cp .env.example .env

# Edit config (at least one LLM provider required)
# LLM_PROVIDER=local  # Local model
# LLM_PROVIDER=openrouter  # OpenRouter free models
# LLM_PROVIDER=qwen  # Tongyi Qianwen
```

### Running

```bash
# CLI Demo
python examples/demo.py --code 600519.SH --name "Kweichow Moutai"

# Web Interface
python -m astock_agents.web.app
# Visit http://localhost:8000
```

### Docker Deployment

```bash
# Using Docker Compose
docker-compose up -d
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        AStockAgents                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│  │  Data Layer  │   │ Agent Layer  │   │  App Layer   │   │
│  │              │   │              │   │              │   │
│  │ • Mootdx     │   │ • Technical  │   │ • CLI        │   │
│  │ • Akshare    │   │ • Fundamental│   │ • Web UI     │   │
│  │ • Tencent    │   │ • Sentiment  │   │ • REST API   │   │
│  │ • Eastmoney  │   │ • News       │   │ • WebSocket  │   │
│  │ • Baidu      │   │ • Bull/Bear  │   │              │   │
│  │ • Cninfo     │   │ • CapitalFlow│   │              │   │
│  │              │   │ • Risk       │   │              │   │
│  └──────────────┘   └──────────────┘   └──────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Workflow Orchestration (LangGraph)        │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐ │   │
│  │  │  Data   │→│ Analyst │→│ Debate  │→│ Trading │ │   │
│  │  │  Node   │  │  Node   │  │  Node   │  │  Node   │ │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    Service Layer                      │   │
│  │  • Compliance • FOMO Guard • Backtest • Risk Mgmt    │   │
│  │  • Position Sizing • Notification • Scheduler        │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

For detailed architecture, see [ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 🔌 Multi-LLM Support

### Supported Providers

| Provider | Free Tier | Example Models |
|----------|-----------|----------------|
| **Local Models** | Completely Free | gemma4, llama3, Qwen |
| **OpenRouter** | Daily Free | google/gemma-4-31b-it:free |
| **Tongyi Qianwen** | Has Free Tier | qwen-turbo |
| **DeepSeek** | Has Free Tier | deepseek-chat |
| **Zhipu AI** | Has Free Tier | glm-4 |
| **OpenAI** | Paid | GPT-4o |
| **Anthropic** | Paid | Claude-3.5 |

### Configuration Examples

```bash
# .env

# Local model (recommended: gemma4)
LLM_PROVIDER=local
LOCAL_LLM_BASE_URL=http://127.0.0.1:8080/v1
LOCAL_LLM_MODEL=gemma4

# Or use OpenRouter free models
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key
OPENROUTER_MODEL=google/gemma-4-31b-it:free
```

---

## 📚 Usage Guide

### Python API

```python
from astock_agents.workflow.analysis_workflow import AnalysisWorkflow

# Create workflow
workflow = AnalysisWorkflow()

# Run analysis
result = workflow.run(stock_code="600519.SH", stock_name="Kweichow Moutai")

print(f"Final Signal: {result.final_signal}")
print(f"Confidence: {result.final_confidence}%")
print(f"Technical Analysis: {result.technical_analysis.summary}")
print(f"Bull/Bear Debate: {result.debate.bull_thesis}")
```

### REST API

```bash
# Analyze stock
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{"stock_code": "600519.SH", "stock_name": "Kweichow Moutai"}'

# Get popular stocks
curl "http://localhost:8000/api/stocks/popular"

# Stock comparison
curl "http://localhost:8000/api/compare?stock_codes=600519.SH,000858.SZ"

# Strategy backtest
curl -X POST "http://localhost:8000/api/backtest" \
  -H "Content-Type: application/json" \
  -d '{"strategy": "MACD", "stock_code": "000001.SZ"}'
```

For detailed usage, see [USER_GUIDE.md](docs/USER_GUIDE.md)

---

## 📖 API Docs

After starting the web service, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=astock_agents --cov-report=html

# Run specific tests
pytest tests/test_agents_layer.py -v
```

---

## 📁 Project Structure

```
astock-agents/
├── astock_agents/           # Main package
│   ├── agents/              # 10 agents
│   │   ├── technical_analyst.py
│   │   ├── fundamental_analyst.py
│   │   ├── sentiment_analyst.py
│   │   ├── news_analyst.py
│   │   ├── capital_flow_analyst.py
│   │   ├── macro_analyst.py
│   │   ├── bull_researcher.py
│   │   ├── bear_researcher.py
│   │   ├── trader.py
│   │   └── risk_manager.py
│   ├── data/                # 6-level data sources
│   │   ├── mootdx_client.py
│   │   ├── akshare_client.py
│   │   ├── tencent_client.py
│   │   ├── eastmoney_client.py
│   │   └── data_manager.py
│   ├── services/            # 22 services
│   │   ├── compliance.py
│   │   ├── fomo_guard.py
│   │   ├── backtest.py
│   │   ├── user_memory.py
│   │   └── ...
│   ├── workflow/            # LangGraph workflow
│   ├── models/             # Pydantic models
│   ├── web/                # FastAPI web service
│   └── config.py           # Configuration
├── frontend/                # Vue3 frontend
│   └── src/
│       ├── views/          # 14 pages
│       ├── components/     # Visualization components
│       └── services/       # API services
├── tests/                  # Unit tests
├── scripts/                # Backtest scripts
├── docs/                   # Documentation
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

For guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 License

This project is licensed under **CC BY-NC 4.0** (Creative Commons Attribution-NonCommercial 4.0).

**Allowed**:
- Personal use, study, and research
- Modification and redistribution

**Forbidden**:
- Commercial use
- SaaS products
- Revenue-generating services

See [LICENSE](LICENSE) for details.

---

## ⚠️ Disclaimer

**The analysis results provided by this system are for reference only and do not constitute any investment advice.**

The stock market involves risks; invest with caution. The developers are not responsible for any losses incurred from investment decisions made using this system. Please make independent investment decisions based on your own risk tolerance.

---

## 🙏 Acknowledgments

- [LangChain](https://github.com/langchain-ai/langchain) - LLM Application Framework
- [LangGraph](https://github.com/langchain-ai/langgraph) - Workflow Orchestration
- [Akshare](https://github.com/akfamily/akshare) - Financial Data Interface
- [Mootdx](https://github.com/moomindesigns/mootdx) - Tongdaxin Interface
- [TradingAgents](https://github.com/TauricResearch/TradingAgents) - Multi-Agent Framework Reference

---

<div align="center">

If you find this project helpful, please give it a ⭐️ Star!

Made with ❤️ by AStockAgents Team

</div>
