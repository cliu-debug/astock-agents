# AStockAgents v0.1.0 - 首发版本

## 项目简介

**AStockAgents** 是一个面向A股市场的多智能体协同股票分析系统，基于LangGraph构建，模拟专业投资研究团队的工作流程。

## 核心功能

- **10个专业智能体**: 技术/基本面/情绪/新闻/资金流向/多空辩论/交易/风控
- **三层混合决策架构**: 规则引擎+LLM增强+风控强制
- **年轮记忆系统**: 投资画像、偏好学习、持续进化
- **博弈论辩论**: 纳什均衡、囚徒困境、多轮对抗
- **金融合规设计**: 免责声明注入、FOMO检测、审计日志
- **多源数据降级**: mootdx→akshare→腾讯→东财→百度→巨潮
- **完整回测系统**: 3年A股回测、Sharpe/最大回撤/胜率
- **多LLM支持**: 本地模型/OpenRouter免费/国产LLM
- **MCP协议支持**: 6个标准化金融工具接口
- **Vue3可视化**: 3D智能体场景/K线图/工作流图

## 快速开始

```bash
git clone https://github.com/cliu-debug/astock-agents.git
cd astock-agents
pip install -r requirements.txt
python -m astock_agents.web.app
```

## 许可证

CC BY-NC 4.0 (允许个人用，禁止商用)

## 免责声明

本系统提供的分析结果仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。
