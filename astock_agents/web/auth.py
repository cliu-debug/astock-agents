"""认证中间件 - API Key + JWT"""

import os
import time
from typing import Optional

from loguru import logger
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import jwt

# JWT配置
JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    import secrets
    JWT_SECRET = secrets.token_hex(32)
    logger.warning("[安全] JWT_SECRET 未设置，已自动生成临时密钥。生产环境请设置环境变量 JWT_SECRET")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_HOURS: int = 24

# API Key
API_KEY: str = os.environ.get("ASTOCK_API_KEY", "")

security = HTTPBearer(auto_error=False)


def is_auth_enabled() -> bool:
    """
    认证是否启用

    当 ASTOCK_API_KEY 环境变量未设置或设置为 "disabled" 时，不启用认证（开发模式）。

    Returns:
        bool: 是否启用认证
    """
    return bool(API_KEY) and API_KEY != "disabled"


def generate_jwt_token(api_key: str) -> str:
    """
    生成JWT Token

    Args:
        api_key: 用于验证身份的API Key

    Returns:
        str: 生成的JWT Token字符串

    Raises:
        ValueError: API Key无效时抛出
    """
    if api_key != API_KEY:
        raise ValueError("Invalid API Key")

    payload: dict[str, int | str] = {
        "sub": "astock-user",
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_HOURS * 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(credentials: Optional[HTTPAuthorizationCredentials]) -> bool:
    """
    验证请求凭证

    支持两种方式：API Key 直接验证 或 JWT Token 验证。

    Args:
        credentials: HTTP Bearer认证凭证

    Returns:
        bool: 验证是否通过
    """
    if not is_auth_enabled():
        return True

    if credentials is None:
        return False

    token: str = credentials.credentials

    # 尝试API Key方式
    if token == API_KEY:
        return True

    # 尝试JWT方式
    try:
        payload: dict = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub") == "astock-user"
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False


async def auth_middleware(request: Request, call_next):
    """
    认证中间件

    对非公开路径进行认证校验，支持 X-API-Key 请求头和 Bearer Token 两种方式。
    当认证未启用时（ASTOCK_API_KEY 未设置或为 "disabled"），所有请求直接放行。

    Args:
        request: FastAPI请求对象
        call_next: 下一个中间件/路由处理函数

    Returns:
        响应对象

    Raises:
        HTTPException: 认证失败时返回401
    """
    # 不需要认证的路径
    public_paths: list[str] = [
        "/", "/api/health", "/docs", "/openapi.json", "/redoc",
        "/api/auth/token",
    ]

    if not is_auth_enabled():
        return await call_next(request)

    if request.url.path in public_paths:
        return await call_next(request)

    # 静态文件不需要认证
    if request.url.path.startswith("/static"):
        return await call_next(request)

    # 检查API Key（请求头）
    api_key: Optional[str] = request.headers.get("X-API-Key")
    if api_key and api_key == API_KEY:
        return await call_next(request)

    # 检查JWT Bearer Token
    auth_header: Optional[str] = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token: str = auth_header[7:]

        # 先尝试API Key直接匹配
        if token == API_KEY:
            return await call_next(request)

        # 再尝试JWT解码
        try:
            payload: dict = jwt.decode(
                token, JWT_SECRET, algorithms=[JWT_ALGORITHM]
            )
            if payload.get("sub") == "astock-user":
                return await call_next(request)
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass

    return JSONResponse(
        status_code=401,
        content={"detail": "未授权访问，请提供有效的API Key或JWT Token"},
    )
