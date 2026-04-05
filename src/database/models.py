# src/database/models.py

from typing import Optional, Any
from pydantic import BaseModel, Field, computed_field

class Proxy(BaseModel): # 让 Proxy 继承 BaseModel
    """
    代理数据模型。
    包含代理的 IP、端口、协议、国家代码、匿名度、
    最后检查时间、响应时间、成功次数、失败次数等信息。
    """
    ip: str
    port: int
    protocol: str = Field("http", pattern="^(http|https|socks4|socks5)$") # 添加协议正则校验
    country_code: str = "Unknown"
    anonymity_level: str = "Unknown"
    last_check_time: Optional[float] = None  # 使用 Unix 时间戳 (float) 而非 datetime
    response_time: Optional[float] = None
    success_count: int = 0
    fail_count: int = 0
    score: int = 0          # 评分 0-100
    grade: str = ''         # 等级 S/A/B/C/D

    class Config:
        pass  # 保留 Config 类以便后续扩展
        # allow_population_by_field_name = True # 允许通过字段名称赋值

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization hook to handle custom logic like protocol lowercasing."""
        self.protocol = self.protocol.lower()

    @computed_field # 将 full_proxy_string 定义为 computed field
    @property
    def full_proxy_string(self) -> str:
        return f"{self.protocol}://{self.ip}:{self.port}"

    # 保留 to_dict 和 from_dict 方法，以兼容旧有代码和 RedisManager
    def to_dict(self) -> dict:
        """将 Proxy 对象转换为字典，并过滤掉 None 值，确保兼容 Redis HSET"""
        data = self.model_dump()
        cleaned_data = {}
        for k, v in data.items():
            if v is not None:
                # 转换 float 到字符串 (Redis HSET 存储需要字符串)
                if isinstance(v, float):
                    cleaned_data[k] = str(v)
                else:
                    cleaned_data[k] = v
        return cleaned_data

    @staticmethod
    def from_dict(data: dict):
        """从字典创建 Proxy 对象"""
        last_check_time_val = data.get("last_check_time")
        if last_check_time_val is not None and last_check_time_val != "":
            try:
                # 直接保持为 float (Unix 时间戳)
                last_check_time_val = float(last_check_time_val)
            except (ValueError, TypeError):
                last_check_time_val = None
        else:
            last_check_time_val = None

        response_time_val = data.get("response_time")
        if response_time_val is not None and response_time_val != "":
            try:
                response_time_val = float(response_time_val)
            except ValueError:
                response_time_val = None
        else:
            response_time_val = None

        # 解析 score
        score_val = data.get("score", 0)
        if score_val is not None and score_val != "":
            try:
                score_val = int(score_val)
            except (ValueError, TypeError):
                score_val = 0
        else:
            score_val = 0
        
        # 解析 grade
        grade_val = data.get("grade", "")
        if grade_val is None:
            grade_val = ""
        
        # 使用 Pydantic 的创建方法
        return Proxy(
            ip=data["ip"],
            port=int(data["port"]), # 确保 port 是整数
            protocol=data.get("protocol", "http"),
            country_code=data.get("country_code", "Unknown"),
            anonymity_level=data.get("anonymity_level", "Unknown"),
            last_check_time=last_check_time_val,
            response_time=response_time_val,
            success_count=int(data.get("success_count", 0)),
            fail_count=int(data.get("fail_count", 0)),
            score=score_val,
            grade=grade_val
        )

    # __repr__, __eq__, __hash__ 可以依靠 Pydantic 自动生成或根据需要自定义
    # 但为了兼容性，保留原来的
    def __repr__(self):
        return f"<Proxy {self.protocol}://{self.ip}:{self.port} - {self.country_code} ({self.anonymity_level})>"

    def __eq__(self, other):
        if not isinstance(other, Proxy):
            return NotImplemented
        return self.ip == other.ip and self.port == other.port and self.protocol == other.protocol

    def __hash__(self):
        return hash((self.ip, self.port, self.protocol))
