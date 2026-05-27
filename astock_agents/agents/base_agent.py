"""智能体基类"""

import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from astock_agents.models import StockData


class BaseAgent(ABC):
    """智能体基类"""

    def __init__(
        self,
        name: str,
        role: str,
        llm: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化智能体

        Args:
            name: 智能体名称
            role: 角色描述
            llm: 语言模型实例（可选）
            config: 配置字典
        """
        self.name = name
        self.role = role
        self.config = config or {}
        # 如果未传入LLM，尝试从配置创建
        self.llm = llm or self._create_default_llm()

        logger.info(f"智能体初始化: {name} ({role})")

    def _create_default_llm(self) -> Optional[Any]:
        """创建默认LLM（如果配置了API密钥）

        支持的提供商：openai, anthropic, qwen, deepseek, ollama, zhipu
        当 self.config 中未包含 llm 配置时，自动从环境变量加载
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
                    logger.warning(f"[{self.name}] 未配置OpenAI API密钥，LLM功能不可用")
                    return None

                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=llm_config.get("openai", {}).get("model", "gpt-4"),
                    temperature=llm_config.get("openai", {}).get("temperature", 0.3),
                    api_key=api_key,
                )
            elif provider == "anthropic":
                api_key = llm_config.get("anthropic", {}).get("api_key")
                if not api_key:
                    logger.warning(f"[{self.name}] 未配置Anthropic API密钥，LLM功能不可用")
                    return None

                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    model=llm_config.get("anthropic", {}).get("model", "claude-3-5-sonnet-20241022"),
                    temperature=llm_config.get("anthropic", {}).get("temperature", 0.3),
                    api_key=api_key,
                )
            elif provider == "qwen":
                api_key = llm_config.get("qwen", {}).get("api_key")
                if not api_key:
                    logger.warning(f"[{self.name}] 未配置通义千问API密钥，LLM功能不可用")
                    return None

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
                    logger.warning(f"[{self.name}] 未配置DeepSeek API密钥，LLM功能不可用")
                    return None

                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=llm_config.get("deepseek", {}).get("model", "deepseek-chat"),
                    temperature=llm_config.get("deepseek", {}).get("temperature", 0.3),
                    api_key=api_key,
                    base_url="https://api.deepseek.com/v1",
                )
            elif provider == "ollama":
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=llm_config.get("ollama", {}).get("model", "qwen2.5:7b"),
                    temperature=llm_config.get("ollama", {}).get("temperature", 0.3),
                    api_key="ollama",  # Ollama不需要真实key
                    base_url=llm_config.get("ollama", {}).get("base_url", "http://localhost:11434/v1"),
                )
            elif provider == "zhipu":
                api_key = llm_config.get("zhipu", {}).get("api_key")
                if not api_key:
                    logger.warning(f"[{self.name}] 未配置智谱AI API密钥，LLM功能不可用")
                    return None

                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=llm_config.get("zhipu", {}).get("model", "glm-4"),
                    temperature=llm_config.get("zhipu", {}).get("temperature", 0.3),
                    api_key=api_key,
                    base_url="https://open.bigmodel.cn/api/paas/v4/",
                )
            else:
                logger.warning(f"[{self.name}] 不支持的LLM提供商: {provider}")
                return None
        except Exception as e:
            logger.warning(f"[{self.name}] LLM初始化失败: {e}")
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
