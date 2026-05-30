"""全局配置 - 从环境变量加载LLM配置

支持以下LLM提供商：
- OpenAI (默认)
- Anthropic
- 通义千问 (Qwen)
- DeepSeek
- Ollama 本地模型
- 智谱AI (GLM)
- OpenRouter (聚合平台，支持免费模型)
"""

import os
from typing import Dict, Any


OPENROUTER_FREE_MODELS = [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "openrouter/free",
    "deepseek/deepseek-v4-flash:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-120b:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "moonshotai/kimi-k2.6:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
]


def get_llm_config() -> Dict[str, Any]:
    """从环境变量获取LLM配置

    Returns:
        包含所有LLM提供商配置的字典，default_provider 指定默认提供商
    """
    return {
        "default_provider": os.getenv("LLM_PROVIDER", "openrouter"),
        "openai": {
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "model": os.getenv("OPENAI_MODEL", "gpt-4"),
            "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.3")),
        },
        "anthropic": {
            "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
            "model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            "temperature": float(os.getenv("ANTHROPIC_TEMPERATURE", "0.3")),
        },
        "qwen": {
            "api_key": os.getenv("QWEN_API_KEY", ""),
            "model": os.getenv("QWEN_MODEL", "qwen-plus"),
            "temperature": float(os.getenv("QWEN_TEMPERATURE", "0.3")),
        },
        "deepseek": {
            "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            "temperature": float(os.getenv("DEEPSEEK_TEMPERATURE", "0.3")),
        },
        "ollama": {
            "model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.3")),
        },
        "zhipu": {
            "api_key": os.getenv("ZHIPU_API_KEY", ""),
            "model": os.getenv("ZHIPU_MODEL", "glm-4"),
            "temperature": float(os.getenv("ZHIPU_TEMPERATURE", "0.3")),
        },
        "openrouter": {
            "api_key": os.getenv("OPENROUTER_API_KEY", ""),
            "model": os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free"),
            "base_url": "https://openrouter.ai/api/v1",
            "temperature": float(os.getenv("OPENROUTER_TEMPERATURE", "0.3")),
        },
    }


def mask_api_key(api_key: str) -> str:
    """隐藏API Key的中间部分，仅显示前4位和后4位

    Args:
        api_key: 原始API Key

    Returns:
        隐藏中间部分的API Key，如 "sk-a****1234"
    """
    if not api_key or len(api_key) <= 8:
        return "****" if api_key else ""
    return f"{api_key[:4]}****{api_key[-4:]}"


def get_safe_llm_config() -> Dict[str, Any]:
    """获取脱敏后的LLM配置（隐藏API Key）

    Returns:
        脱敏后的LLM配置字典，API Key仅显示前4位和后4位
    """
    config = get_llm_config()
    safe_config: Dict[str, Any] = {"default_provider": config["default_provider"]}

    for provider, settings in config.items():
        if provider == "default_provider":
            continue
        safe_settings = {}
        for key, value in settings.items():
            if key == "api_key":
                safe_settings[key] = mask_api_key(str(value))
            else:
                safe_settings[key] = value
        safe_config[provider] = safe_settings

    return safe_config
