# src/api/auth.py

from typing import Optional
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import APIKeyHeader
from src import app_globals

# Define API key header
api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)

def verify_api_token(
    api_token_header: Optional[str] = Depends(api_key_header),
    api_token_query: Optional[str] = Query(None, alias="token")
):
    """
    Dependency to verify the API token.
    Reads API_TOKEN from environment variables via Config.
    优先使用请求头 X-API-Token，同时兼容 query 参数 token（用于快速开始 URL）。
    """
    required_token = app_globals.global_config.API_TOKEN
    logger = app_globals.global_logger
    api_token = api_token_header or api_token_query

    if not required_token:
        logger.error("API_TOKEN is not configured in environment variables or config.py.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API token not configured on the server."
        )

    if not api_token or api_token != required_token:
        logger.warning("Unauthorized API access attempt.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token."
        )
    return api_token
