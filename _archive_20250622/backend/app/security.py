import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)

# 密码加密配置
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT配置
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# API密钥配置
API_KEY_HEADER = "X-API-Key"
ALLOWED_API_KEYS = os.getenv("ALLOWED_API_KEYS", "").split(",")

# 安全认证方案
security = HTTPBearer()

class SecurityManager:
    def __init__(self):
        self.api_keys: Dict[str, Dict[str, Any]] = {}
        self.rate_limits: Dict[str, list] = {}
        self.load_api_keys()

    def load_api_keys(self):
        """加载API密钥配置"""
        for key in ALLOWED_API_KEYS:
            if key.strip():
                key_hash = self.hash_api_key(key.strip())
                self.api_keys[key_hash] = {
                    "key": key.strip(),
                    "created_at": datetime.now(),
                    "last_used": None,
                    "permissions": ["read", "write"],  # 可配置权限
                    "rate_limit": 100  # 每分钟请求次数限制
                }

    def hash_api_key(self, api_key: str) -> str:
        """对API密钥进行哈希处理"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """验证API密钥"""
        key_hash = self.hash_api_key(api_key)
        if key_hash in self.api_keys:
            key_info = self.api_keys[key_hash]
            key_info["last_used"] = datetime.now()
            return key_info
        return None

    def check_rate_limit(self, api_key: str, limit: int = 100) -> bool:
        """检查请求频率限制"""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        if api_key not in self.rate_limits:
            self.rate_limits[api_key] = []
        
        # 清理过期记录
        self.rate_limits[api_key] = [
            timestamp for timestamp in self.rate_limits[api_key]
            if timestamp > minute_ago
        ]
        
        # 检查是否超出限制
        if len(self.rate_limits[api_key]) >= limit:
            return False
        
        # 记录当前请求
        self.rate_limits[api_key].append(now)
        return True

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """创建JWT访问令牌"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证JWT令牌"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.PyJWTError:
            return None

# 全局安全管理器实例
security_manager = SecurityManager()

def get_current_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
    """获取当前API密钥信息"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 验证API密钥
    key_info = security_manager.verify_api_key(credentials.credentials)
    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查频率限制
    if not security_manager.check_rate_limit(credentials.credentials, key_info["rate_limit"]):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    
    return key_info

def require_permission(permission: str):
    """要求特定权限的装饰器"""
    def permission_dependency(key_info: Dict[str, Any] = Depends(get_current_api_key)):
        if permission not in key_info.get("permissions", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return key_info
    return permission_dependency

# 可选的安全验证（用于公开接口）
def optional_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> Optional[Dict[str, Any]]:
    """可选的API密钥验证"""
    if not credentials:
        return None
    
    try:
        return get_current_api_key(credentials)
    except HTTPException:
        return None

def generate_api_key() -> str:
    """生成新的API密钥"""
    return secrets.token_urlsafe(32)

def hash_password(password: str) -> str:
    """加密密码"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def create_hmac_signature(data: str, secret: str) -> str:
    """创建HMAC签名"""
    return hmac.new(
        secret.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def verify_hmac_signature(data: str, signature: str, secret: str) -> bool:
    """验证HMAC签名"""
    expected_signature = create_hmac_signature(data, secret)
    return hmac.compare_digest(expected_signature, signature)

# 数据脱敏工具
def sanitize_position_data(position_data: Dict[str, Any], is_public: bool = False) -> Dict[str, Any]:
    """脱敏仓位数据"""
    if not is_public:
        return position_data
    
    # 公开展示时隐藏敏感信息
    sanitized = position_data.copy()
    
    # 隐藏具体金额，只保留相对比例
    if "market_value" in sanitized:
        sanitized["market_value"] = "***"
    if "avg_cost" in sanitized:
        sanitized["avg_cost"] = "***"
    if "unrealized_pnl" in sanitized:
        # 只显示正负，不显示具体数值
        pnl = sanitized["unrealized_pnl"]
        sanitized["unrealized_pnl"] = "+" if pnl > 0 else "-" if pnl < 0 else "0"
    
    return sanitized

def sanitize_account_data(account_data: Dict[str, Any], is_public: bool = False) -> Dict[str, Any]:
    """脱敏账户数据"""
    if not is_public:
        return account_data
    
    # 公开展示时隐藏所有具体金额
    sanitized = account_data.copy()
    sensitive_fields = [
        "total_cash_value", "net_liquidation", 
        "gross_position_value", "buying_power"
    ]
    
    for field in sensitive_fields:
        if field in sanitized:
            sanitized[field] = "***"
    
    return sanitized