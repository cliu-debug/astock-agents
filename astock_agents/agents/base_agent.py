"""智能体基类

核心特征：
- 反思能力(Reflection)：智能体可自检输出质量，发现逻辑漏洞
- 可解释性(Explainability)：输出推理链、置信度、不确定声明
- 自主规划(Autonomous Planning)：动态任务分解与执行
- 工具使用(Tool Use)：通过MCP协议调用标准化金融工具
- 状态回调(Status Callback)：实时推送工作状态
"""

import json
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from loguru import logger

from astock_agents.models import StockData


class AgentStatus:
    """智能体工作状态常量"""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    ANALYZING = "analyzing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    ERROR = "error"


class ReasoningStep:
    """推理链步骤"""

    def __init__(
        self,
        step_name: str,
        description: str,
        data_used: str,
        conclusion: str,
        confidence: float,
    ):
        self.step_name = step_name
        self.description = description
        self.data_used = data_used
        self.conclusion = conclusion
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "description": self.description,
            "data_used": self.data_used,
            "conclusion": self.conclusion,
            "confidence": self.confidence,
        }


class TaskPlan:
    """任务计划 - 自主规划能力的数据结构"""

    def __init__(self, goal: str):
        self.goal = goal
        self.steps: List[Dict[str, Any]] = []
        self.completed_steps: List[str] = []
        self.current_step: Optional[str] = None

    def add_step(
        self,
        step_id: str,
        name: str,
        description: str,
        dependencies: Optional[List[str]] = None,
        tools_needed: Optional[List[str]] = None,
    ) -> None:
        self.steps.append({
            "step_id": step_id,
            "name": name,
            "description": description,
            "dependencies": dependencies or [],
            "tools_needed": tools_needed or [],
            "status": "pending",
        })

    def get_next_step(self) -> Optional[Dict[str, Any]]:
        for step in self.steps:
            if step["status"] == "pending":
                deps_met = all(
                    dep in self.completed_steps
                    for dep in step["dependencies"]
                )
                if deps_met:
                    return step
        return None

    def mark_step_completed(self, step_id: str) -> None:
        for step in self.steps:
            if step["step_id"] == step_id:
                step["status"] = "completed"
                self.completed_steps.append(step_id)
                break

    def mark_step_executing(self, step_id: str) -> None:
        for step in self.steps:
            if step["step_id"] == step_id:
                step["status"] = "executing"
                self.current_step = step_id
                break

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": self.steps,
            "completed_steps": self.completed_steps,
            "current_step": self.current_step,
        }


class BaseAgent(ABC):
    """智能体基类"""

    def __init__(
        self,
        name: str,
        role: str,
        llm: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.role = role
        self.config = config or {}
        self.llm = llm or self._create_default_llm()
        self.mcp_server: Optional[Any] = None

        # 工作状态
        self._status: str = AgentStatus.IDLE
        self._status_message: str = ""
        self._status_callback: Optional[Callable[[str, str, str], None]] = None

        # 推理链
        self._reasoning_chain: List[ReasoningStep] = []

        # 任务计划
        self._task_plan: Optional[TaskPlan] = None

        # 反思结果
        self._reflection: Optional[Dict[str, Any]] = None

        logger.info(f"智能体初始化: {name} ({role})")

    # ==================== 状态管理 ====================

    @property
    def status(self) -> str:
        return self._status

    def set_status_callback(
        self, callback: Callable[[str, str, str], None]
    ) -> None:
        """设置状态回调函数

        Args:
            callback: 回调函数，参数为 (agent_name, status, message)
        """
        self._status_callback = callback

    def _update_status(self, status: str, message: str = "") -> None:
        """更新智能体工作状态

        Args:
            status: 状态常量
            message: 状态描述信息
        """
        self._status = status
        self._status_message = message
        if self._status_callback:
            try:
                self._status_callback(self.name, status, message)
            except Exception as e:
                logger.debug(f"[{self.name}] 状态回调失败: {e}")

    # ==================== 推理链 ====================

    def _add_reasoning_step(
        self,
        step_name: str,
        description: str,
        data_used: str,
        conclusion: str,
        confidence: float,
    ) -> None:
        """添加推理链步骤

        Args:
            step_name: 步骤名称
            description: 步骤描述
            data_used: 使用的数据
            conclusion: 得出的结论
            confidence: 置信度(0-1)
        """
        step = ReasoningStep(
            step_name=step_name,
            description=description,
            data_used=data_used,
            conclusion=conclusion,
            confidence=confidence,
        )
        self._reasoning_chain.append(step)

    def _clear_reasoning_chain(self) -> None:
        """清空推理链"""
        self._reasoning_chain = []

    def get_reasoning_chain(self) -> List[Dict[str, Any]]:
        """获取推理链

        Returns:
            推理链步骤列表
        """
        return [step.to_dict() for step in self._reasoning_chain]

    # ==================== 自主规划 ====================

    def _create_task_plan(self, goal: str) -> TaskPlan:
        """创建任务计划

        Args:
            goal: 任务目标

        Returns:
            TaskPlan实例
        """
        self._task_plan = TaskPlan(goal)
        return self._task_plan

    def _plan_analysis_tasks(self, stock_data: StockData) -> TaskPlan:
        """规划分析任务（子类可重写以自定义任务分解）

        默认规划：数据校验 -> 指标计算 -> 信号生成 -> 结果校验

        Args:
            stock_data: 股票数据

        Returns:
            任务计划
        """
        plan = self._create_task_plan(
            f"分析{stock_data.stock_name}({stock_data.stock_code})"
        )
        plan.add_step(
            "validate_data", "数据校验",
            "检查输入数据完整性和质量",
            tools_needed=["get_stock_price"],
        )
        plan.add_step(
            "compute_indicators", "指标计算",
            "计算分析所需的技术/基本面/情绪指标",
            dependencies=["validate_data"],
        )
        plan.add_step(
            "generate_signal", "信号生成",
            "基于指标生成交易信号",
            dependencies=["compute_indicators"],
        )
        plan.add_step(
            "validate_output", "结果校验",
            "自检输出质量，确保逻辑一致性",
            dependencies=["generate_signal"],
        )
        return plan

    def get_task_plan(self) -> Optional[Dict[str, Any]]:
        """获取当前任务计划

        Returns:
            任务计划字典
        """
        if self._task_plan:
            return self._task_plan.to_dict()
        return None

    # ==================== 反思能力 ====================

    def _reflect_on_output(
        self,
        analysis_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """对分析结果进行反思自检

        检查项：
        1. 逻辑一致性：信号是否与指标矛盾
        2. 置信度合理性：置信度是否过高/过低
        3. 数据充分性：是否有足够数据支撑结论
        4. 遗漏风险：是否遗漏了重要因素

        Args:
            analysis_result: 分析结果字典

        Returns:
            反思结果字典
        """
        self._update_status(AgentStatus.REFLECTING, "正在自检输出质量")

        reflection: Dict[str, Any] = {
            "agent_name": self.name,
            "timestamp": datetime.now().isoformat(),
            "issues_found": [],
            "confidence_adjustment": 0,
            "quality_score": 100,
            "recommendation": "",
        }

        confidence = analysis_result.get("confidence", 50)
        if confidence > 90:
            reflection["issues_found"].append(
                f"置信度{confidence}%过高，可能存在过度自信偏差"
            )
            reflection["confidence_adjustment"] = -5
            reflection["quality_score"] -= 10
        elif confidence < 20:
            reflection["issues_found"].append(
                f"置信度{confidence}%过低，数据可能不充分"
            )
            reflection["quality_score"] -= 15

        signal = analysis_result.get("signal", "")
        signal_str = signal.value if hasattr(signal, "value") else str(signal)
        indicators = analysis_result.get("indicators", {})

        if signal_str in ("强烈买入", "买入") and indicators:
            rsi = indicators.get("rsi", {}).get("value", 50)
            if rsi > 70:
                reflection["issues_found"].append(
                    f"买入信号但RSI={rsi}超买，存在矛盾"
                )
                reflection["confidence_adjustment"] -= 10
                reflection["quality_score"] -= 15

        if signal_str in ("强烈卖出", "卖出") and indicators:
            rsi = indicators.get("rsi", {}).get("value", 50)
            if rsi < 30:
                reflection["issues_found"].append(
                    f"卖出信号但RSI={rsi}超卖，存在矛盾"
                )
                reflection["confidence_adjustment"] -= 10
                reflection["quality_score"] -= 15

        data_points = analysis_result.get("data_points_count", 0)
        if data_points < 30:
            reflection["issues_found"].append(
                f"数据量不足({data_points}天)，短期指标可能不可靠"
            )
            reflection["confidence_adjustment"] -= 10
            reflection["quality_score"] -= 20

        if self.llm is None:
            reflection["issues_found"].append(
                "LLM未启用，分析仅基于规则引擎，深度有限"
            )
            reflection["quality_score"] -= 10

        if reflection["quality_score"] >= 80:
            reflection["recommendation"] = "分析质量良好，结论可信"
        elif reflection["quality_score"] >= 60:
            reflection["recommendation"] = "分析质量一般，建议结合其他维度确认"
        else:
            reflection["recommendation"] = "分析质量较低，建议人工复核"

        self._reflection = reflection
        logger.info(
            f"[{self.name}] 反思完成: 质量评分={reflection['quality_score']}, "
            f"发现问题={len(reflection['issues_found'])}个"
        )

        return reflection

    def get_reflection(self) -> Optional[Dict[str, Any]]:
        """获取反思结果"""
        return self._reflection

    # ==================== 不确定性声明 ====================

    def _generate_uncertainty_statement(
        self,
        confidence: int,
        data_quality: str = "normal",
    ) -> str:
        """生成不确定性声明

        当置信度较低或数据质量不佳时，明确声明不确定性

        Args:
            confidence: 置信度(0-100)
            data_quality: 数据质量 (good/normal/poor/insufficient)

        Returns:
            不确定性声明文本
        """
        statements = []

        if confidence < 30:
            statements.append("⚠️ 本结论置信度较低，建议谨慎参考")
        elif confidence < 50:
            statements.append("⚡ 本结论置信度一般，建议结合其他信息确认")

        if data_quality == "poor":
            statements.append("📊 数据质量较差，部分指标可能不准确")
        elif data_quality == "insufficient":
            statements.append("📊 数据量不足，短期指标可靠性有限")

        if self.llm is None:
            statements.append("🤖 LLM未启用，本分析仅基于规则引擎")

        return " | ".join(statements) if statements else ""

    # ==================== LLM相关 ====================

    def _create_default_llm(self) -> Optional[Any]:
        """创建默认LLM（如果配置了API密钥）

        支持的提供商：openai, anthropic, qwen, deepseek, ollama, zhipu
        当 self.config 中未包含 llm 配置时，自动从环境变量加载。
        当所有API Key均未配置时，自动尝试Ollama本地模型（无需Key）。
        """
        llm_config = self.config.get("llm", {})

        # 如果配置中没有 llm 字段，从环境变量加载
        if not llm_config:
            from astock_agents.config import get_llm_config
            llm_config = get_llm_config()
            self.config["llm"] = llm_config

        provider = llm_config.get("default_provider", "openai")

        try:
            if provider == "openai":
                api_key = llm_config.get("openai", {}).get("api_key")
                if not api_key:
                    logger.warning(f"[{self.name}] 未配置OpenAI API密钥，尝试降级到Ollama本地模型")
                    return self._try_ollama_fallback()

                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=llm_config.get("openai", {}).get("model", "gpt-4"),
                    temperature=llm_config.get("openai", {}).get("temperature", 0.3),
                    api_key=api_key,
                )
            elif provider == "anthropic":
                api_key = llm_config.get("anthropic", {}).get("api_key")
                if not api_key:
                    logger.warning(f"[{self.name}] 未配置Anthropic API密钥，尝试降级到Ollama本地模型")
                    return self._try_ollama_fallback()

                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    model=llm_config.get("anthropic", {}).get("model", "claude-3-5-sonnet-20241022"),
                    temperature=llm_config.get("anthropic", {}).get("temperature", 0.3),
                    api_key=api_key,
                )
            elif provider == "qwen":
                api_key = llm_config.get("qwen", {}).get("api_key")
                if not api_key:
                    logger.warning(f"[{self.name}] 未配置通义千问API密钥，尝试降级到Ollama本地模型")
                    return self._try_ollama_fallback()

                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=llm_config.get("qwen", {}).get("model", "qwen-plus"),
                    temperature=llm_config.get("qwen", {}).get("temperature", 0.3),
                    api_key=api_key,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/",
                )
            elif provider == "deepseek":
                api_key = llm_config.get("deepseek", {}).get("api_key")
                if not api_key:
                    logger.warning(f"[{self.name}] 未配置DeepSeek API密钥，尝试降级到Ollama本地模型")
                    return self._try_ollama_fallback()

                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=llm_config.get("deepseek", {}).get("model", "deepseek-chat"),
                    temperature=llm_config.get("deepseek", {}).get("temperature", 0.3),
                    api_key=api_key,
                    base_url="https://api.deepseek.com/v1",
                )
            elif provider == "ollama":
                return self._try_ollama_fallback()
            elif provider == "zhipu":
                api_key = llm_config.get("zhipu", {}).get("api_key")
                if not api_key:
                    logger.warning(f"[{self.name}] 未配置智谱AI API密钥，尝试降级到Ollama本地模型")
                    return self._try_ollama_fallback()

                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=llm_config.get("zhipu", {}).get("model", "glm-4"),
                    temperature=llm_config.get("zhipu", {}).get("temperature", 0.3),
                    api_key=api_key,
                    base_url="https://open.bigmodel.cn/api/paas/v4/",
                )
            elif provider == "openrouter":
                api_key = llm_config.get("openrouter", {}).get("api_key", "")
                if not api_key:
                    logger.warning(f"[{self.name}] 未配置OpenRouter API密钥，尝试降级到Ollama本地模型")
                    return self._try_ollama_fallback()

                from langchain_openai import ChatOpenAI
                model = llm_config.get("openrouter", {}).get("model", "google/gemma-4-31b-it:free")
                base_url = llm_config.get("openrouter", {}).get("base_url", "https://openrouter.ai/api/v1")
                logger.info(f"[{self.name}] 使用OpenRouter模型: {model}")
                return ChatOpenAI(
                    model=model,
                    temperature=llm_config.get("openrouter", {}).get("temperature", 0.3),
                    api_key=api_key,
                    base_url=base_url,
                    default_headers={
                        "HTTP-Referer": "https://github.com/astock-agents",
                        "X-Title": "AStockAgents",
                    },
                )
            else:
                logger.warning(f"[{self.name}] 不支持的LLM提供商: {provider}，尝试降级到Ollama")
                return self._try_ollama_fallback()
        except Exception as e:
            logger.warning(f"[{self.name}] LLM初始化失败: {e}，尝试降级到Ollama")
            return self._try_ollama_fallback()

    def _try_ollama_fallback(self) -> Optional[Any]:
        """尝试连接Ollama本地模型作为降级方案

        Ollama不需要API Key，只需要本地运行Ollama服务。
        如果Ollama也不可用，则返回None（纯规则引擎模式）。

        Returns:
            ChatOpenAI实例（连接Ollama）或None
        """
        try:
            import urllib.request
            # 检测Ollama服务是否可用
            ollama_url = self.config.get("llm", {}).get("ollama", {}).get(
                "base_url", "http://localhost:11434"
            )
            base_url = ollama_url.rstrip("/")
            try:
                req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        logger.info(f"[{self.name}] 检测到Ollama本地服务，使用本地模型")
                        from langchain_openai import ChatOpenAI
                        return ChatOpenAI(
                            model=self.config.get("llm", {}).get("ollama", {}).get("model", "qwen2.5:7b"),
                            temperature=0.3,
                            api_key="ollama",
                            base_url=f"{base_url}/v1",
                        )
            except Exception:
                pass

            logger.info(f"[{self.name}] Ollama本地服务不可用，LLM功能关闭（使用纯规则引擎模式）")
            return None
        except Exception as e:
            logger.debug(f"[{self.name}] Ollama降级检测失败: {e}")
            return None

    @abstractmethod
    def analyze(self, stock_data: StockData, **kwargs) -> Dict[str, Any]:
        """
        执行分析

        Args:
            stock_data: 股票数据
            **kwargs: 额外参数

        Returns:
            分析结果字典
        """
        pass

    def _create_prompt(self, stock_data: StockData, context: Optional[str] = None) -> str:
        """
        创建提示词

        Args:
            stock_data: 股票数据
            context: 上下文信息

        Returns:
            提示词字符串
        """
        base_prompt = f"""你是{self.name}，角色是{self.role}。

当前分析的股票: {stock_data.stock_name} ({stock_data.stock_code})
当前价格: {stock_data.current_price}
所属行业: {stock_data.industry or '未知'}

"""
        if context:
            base_prompt += f"\n上下文信息:\n{context}\n"

        return base_prompt

    def _call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        调用LLM

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            LLM回复

        Raises:
            RuntimeError: LLM未配置或调用失败时抛出
        """
        if not self.llm:
            raise RuntimeError(f"[{self.name}] LLM未配置，无法执行分析")

        try:
            messages = []

            if system_prompt:
                messages.append(("system", system_prompt))

            messages.append(("human", prompt))

            response = self.llm.invoke(messages)
            return response.content

        except Exception as e:
            logger.error(f"[{self.name}] LLM调用失败: {e}")
            raise RuntimeError(f"LLM调用失败: {e}") from e

    def _build_data_anchored_prompt(
        self,
        data_summary: str,
        instruction: str,
        output_fields: List[str]
    ) -> str:
        """
        构建包含真实数据的prompt，要求LLM必须基于提供的数据进行分析

        Args:
            data_summary: 真实数据摘要（如 "RSI=65.3, MACD=0.5, 趋势=上升"）
            instruction: 分析指令
            output_fields: 期望输出的字段列表

        Returns:
            构建好的prompt字符串
        """
        fields_desc = "\n".join(f'  "{field}": "对应内容"' for field in output_fields)

        prompt = f"""你是一个专业的金融分析师。请严格基于以下真实数据进行分析。

【重要约束】
1. 你必须且只能基于下方提供的真实数据进行分析
2. 不得编造、猜测或引用任何未提供的数据
3. 如果数据不足以得出结论，请明确说明"数据不足"
4. 所有分析结论必须能追溯到提供的数据

【真实数据】
{data_summary}

【分析任务】
{instruction}

【输出格式】
请严格按照以下JSON格式输出，不要输出其他内容：
{{
{fields_desc}
}}

请直接输出JSON，不要包含```json```标记或其他说明文字。"""
        return prompt

    def _call_llm_structured(
        self,
        data_summary: str,
        instruction: str,
        output_fields: List[str]
    ) -> Dict[str, str]:
        """
        调用LLM并解析为结构化输出

        通过数据锚定prompt + JSON解析，防止LLM幻觉

        Args:
            data_summary: 真实数据摘要
            instruction: 分析指令
            output_fields: 期望输出的字段列表

        Returns:
            结构化的LLM输出字典

        Raises:
            RuntimeError: LLM未配置或调用失败时抛出
            ValueError: LLM输出无法解析为有效JSON时抛出
        """
        prompt = self._build_data_anchored_prompt(data_summary, instruction, output_fields)

        system_prompt = (
            "你是一个严谨的金融数据分析助手。"
            "你必须基于提供的数据进行分析，不得编造数据。"
            "输出必须是纯JSON格式。"
        )

        raw_response = self._call_llm(prompt, system_prompt)

        # 解析JSON响应
        parsed = self._parse_json_response(raw_response)

        # 验证输出是否包含期望字段
        validated = {}
        for field in output_fields:
            if field in parsed:
                validated[field] = parsed[field]
            else:
                validated[field] = ""

        return validated

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM返回的JSON响应

        尝试多种方式解析，容错处理markdown代码块包裹的JSON

        Args:
            response: LLM原始响应文本

        Returns:
            解析后的字典
        """
        # 尝试直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # 尝试去除markdown代码块标记
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json"):]
        elif cleaned.startswith("```"):
            cleaned = cleaned[len("```"):]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-len("```")]

        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 尝试提取第一个 { } 之间的内容
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(cleaned[start_idx:end_idx + 1])
            except json.JSONDecodeError:
                pass

        logger.warning(f"[{self.name}] LLM输出无法解析为JSON: {response[:200]}")
        return {}

    def _validate_llm_output(
        self,
        llm_output: Dict[str, str],
        data_summary: str
    ) -> Dict[str, str]:
        """
        验证LLM输出是否引用了真实数据（数据锚定校验）

        检查LLM输出中是否包含提供的数据点，防止幻觉

        Args:
            llm_output: LLM结构化输出
            data_summary: 原始数据摘要

        Returns:
            验证后的输出（移除疑似幻觉的内容）
        """
        validated = {}
        # 从数据摘要中提取关键数值用于校验
        data_points = set()
        for part in data_summary.split(","):
            part = part.strip()
            # 提取数值型数据点（如 RSI=65.3 中的 65.3）
            if "=" in part:
                value = part.split("=")[-1].strip()
                # 保留数值部分用于校验
                try:
                    float(value)
                    data_points.add(value)
                except ValueError:
                    pass

        for key, value in llm_output.items():
            if not isinstance(value, str):
                value = str(value)
            validated[key] = value

        return validated

    def _call_llm_with_data(
        self,
        data_summary: str,
        instruction: str,
        output_fields: List[str]
    ) -> Dict[str, str]:
        """
        便捷方法：调用LLM进行数据锚定分析，包含验证

        整合了 _call_llm_structured 和 _validate_llm_output

        Args:
            data_summary: 真实数据摘要
            instruction: 分析指令
            output_fields: 期望输出的字段列表

        Returns:
            经过验证的结构化LLM输出字典
        """
        llm_output = self._call_llm_structured(data_summary, instruction, output_fields)
        validated = self._validate_llm_output(llm_output, data_summary)
        return validated

    def log_analysis(self, result: Dict[str, Any]):
        """记录分析结果"""
        logger.info(f"[{self.name}] 分析完成")
        logger.debug(f"[{self.name}] 结果: {result}")

    def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """通过MCP协议调用标准化金融工具

        当智能体需要获取额外数据时，可通过MCP协议调用已注册的工具。
        工具列表：get_stock_price, get_stock_kline, get_financial_report,
                  get_news, calculate_indicator, get_capital_flow

        Args:
            tool_name: 工具名称
            arguments: 工具参数字典

        Returns:
            工具执行结果字典，调用失败时返回None
        """
        if not self.mcp_server:
            logger.debug(f"[{self.name}] MCP服务未启用，无法调用工具: {tool_name}")
            return None

        try:
            result = self.mcp_server.call_tool(tool_name, arguments)
            if result.get("success"):
                logger.info(f"[{self.name}] MCP工具调用成功: {tool_name}")
                return result.get("data")
            else:
                logger.warning(f"[{self.name}] MCP工具调用失败: {tool_name}, {result.get('error')}")
                return None
        except Exception as e:
            logger.warning(f"[{self.name}] MCP工具调用异常: {tool_name}, {e}")
            return None

    def get_mcp_stock_price(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """通过MCP获取股票实时行情

        Args:
            stock_code: 股票代码

        Returns:
            行情数据字典
        """
        return self.call_mcp_tool("get_stock_price", {"stock_code": stock_code})

    def get_mcp_kline(self, stock_code: str, days: int = 120) -> Optional[Dict[str, Any]]:
        """通过MCP获取K线数据

        Args:
            stock_code: 股票代码
            days: 获取天数

        Returns:
            K线数据字典
        """
        return self.call_mcp_tool("get_stock_kline", {"stock_code": stock_code, "days": days})

    def get_mcp_financial_report(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """通过MCP获取财务报告

        Args:
            stock_code: 股票代码

        Returns:
            财务报告数据字典
        """
        return self.call_mcp_tool("get_financial_report", {"stock_code": stock_code})

    def get_mcp_news(self, stock_code: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """通过MCP获取新闻资讯

        Args:
            stock_code: 股票代码
            limit: 返回条数

        Returns:
            新闻数据字典
        """
        return self.call_mcp_tool("get_news", {"stock_code": stock_code, "limit": limit})

    def get_mcp_capital_flow(self, stock_code: str, days: int = 10) -> Optional[Dict[str, Any]]:
        """通过MCP获取资金流向

        Args:
            stock_code: 股票代码
            days: 获取天数

        Returns:
            资金流向数据字典
        """
        return self.call_mcp_tool("get_capital_flow", {"stock_code": stock_code, "days": days})

    def get_mcp_indicator(self, stock_code: str, indicator: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """通过MCP计算技术指标

        Args:
            stock_code: 股票代码
            indicator: 指标名称（MA/MACD/RSI/KDJ/BOLL）
            params: 指标参数

        Returns:
            技术指标数据字典
        """
        return self.call_mcp_tool("calculate_indicator", {
            "stock_code": stock_code,
            "indicator": indicator,
            "params": params or {},
        })
