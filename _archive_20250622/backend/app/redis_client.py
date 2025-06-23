import redis
import json
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        try:
            self.client = redis.from_url(redis_url, decode_responses=True)
            # 测试连接
            self.client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None

    def set_positions(self, positions: Dict[str, Any]):
        """存储仓位数据"""
        if self.client:
            try:
                self.client.set("positions", json.dumps(positions))
                self.client.expire("positions", 300)  # 5分钟过期
            except Exception as e:
                logger.error(f"Failed to set positions in Redis: {e}")

    def get_positions(self) -> Optional[Dict[str, Any]]:
        """获取仓位数据"""
        if self.client:
            try:
                data = self.client.get("positions")
                return json.loads(data) if data else None
            except Exception as e:
                logger.error(f"Failed to get positions from Redis: {e}")
        return None

    def set_account_summary(self, summary: Dict[str, Any]):
        """存储账户摘要"""
        if self.client:
            try:
                self.client.set("account_summary", json.dumps(summary))
                self.client.expire("account_summary", 300)  # 5分钟过期
            except Exception as e:
                logger.error(f"Failed to set account summary in Redis: {e}")

    def get_account_summary(self) -> Optional[Dict[str, Any]]:
        """获取账户摘要"""
        if self.client:
            try:
                data = self.client.get("account_summary")
                return json.loads(data) if data else None
            except Exception as e:
                logger.error(f"Failed to get account summary from Redis: {e}")
        return None

    def publish_position_update(self, position_data: Dict[str, Any]):
        """发布仓位更新消息"""
        if self.client:
            try:
                self.client.publish("position_updates", json.dumps(position_data))
            except Exception as e:
                logger.error(f"Failed to publish position update: {e}")

    def publish_account_update(self, account_data: Dict[str, Any]):
        """发布账户更新消息"""
        if self.client:
            try:
                self.client.publish("account_updates", json.dumps(account_data))
            except Exception as e:
                logger.error(f"Failed to publish account update: {e}")

    def subscribe_to_updates(self, callback):
        """订阅更新消息"""
        if self.client:
            try:
                pubsub = self.client.pubsub()
                pubsub.subscribe("position_updates", "account_updates")
                return pubsub
            except Exception as e:
                logger.error(f"Failed to subscribe to updates: {e}")
        return None

# 全局Redis客户端实例
redis_client = RedisClient()