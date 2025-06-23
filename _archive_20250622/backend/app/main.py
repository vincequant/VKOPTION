from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
import json
import asyncio
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from .ib_client import get_ib_app, Position, AccountSummary
from .redis_client import redis_client
from .models import get_db, create_tables, PositionHistory, AccountHistory
from .security import (
    optional_api_key, require_permission, sanitize_position_data, 
    sanitize_account_data, security_manager
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

app = FastAPI(
    title="IB Portfolio Monitor API",
    description="Interactive Broker 仓位监控系统 API",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # 移除断开的连接
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# 全局变量存储IB数据
current_positions: List[Dict] = []
current_account: List[Dict] = []

def position_callback(position: Position):
    """仓位更新回调"""
    global current_positions
    position_dict = {
        "account": position.account,
        "symbol": position.symbol,
        "contract_id": position.contract_id,
        "position": position.position,
        "market_price": position.market_price,
        "market_value": position.market_value,
        "avg_cost": position.avg_cost,
        "unrealized_pnl": position.unrealized_pnl,
        "realized_pnl": position.realized_pnl,
        "currency": position.currency,
        "timestamp": position.timestamp
    }
    
    # 更新内存中的数据
    key = f"{position.account}_{position.contract_id}"
    current_positions = [p for p in current_positions if f"{p['account']}_{p['contract_id']}" != key]
    current_positions.append(position_dict)
    
    # 存储到Redis
    redis_client.set_positions({"positions": current_positions, "timestamp": position.timestamp})
    
    # 广播到WebSocket客户端
    asyncio.create_task(manager.broadcast(json.dumps({
        "type": "position_update",
        "data": position_dict
    })))

def account_callback(account: AccountSummary):
    """账户更新回调"""
    global current_account
    account_dict = {
        "account": account.account,
        "total_cash_value": account.total_cash_value,
        "net_liquidation": account.net_liquidation,
        "gross_position_value": account.gross_position_value,
        "buying_power": account.buying_power,
        "currency": account.currency,
        "timestamp": account.timestamp
    }
    
    # 更新内存中的数据
    current_account = [a for a in current_account if a['account'] != account.account]
    current_account.append(account_dict)
    
    # 存储到Redis
    redis_client.set_account_summary({"accounts": current_account, "timestamp": account.timestamp})
    
    # 广播到WebSocket客户端
    asyncio.create_task(manager.broadcast(json.dumps({
        "type": "account_update",
        "data": account_dict
    })))

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    logger.info("Starting IB Portfolio Monitor API...")
    
    # 创建数据库表
    create_tables()
    
    # 初始化IB连接
    ib_app = get_ib_app()
    
    # 添加回调函数
    ib_app.add_position_callback(position_callback)
    ib_app.add_account_callback(account_callback)
    
    # 尝试连接到IB Gateway
    if ib_app.connect():
        logger.info("Connected to IB Gateway successfully")
        # 请求初始数据
        ib_app.request_positions()
        ib_app.request_account_summary()
    else:
        logger.warning("Failed to connect to IB Gateway")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理"""
    logger.info("Shutting down IB Portfolio Monitor API...")
    ib_app = get_ib_app()
    ib_app.disconnect()

# 路由定义
@app.get("/")
async def root():
    return {"message": "IB Portfolio Monitor API is running"}

@app.get("/api/health")
async def health_check():
    ib_app = get_ib_app()
    return {
        "status": "healthy", 
        "service": "ib-portfolio-monitor",
        "ib_connected": ib_app.is_connected,
        "redis_connected": redis_client.client is not None,
        "active_websockets": len(manager.active_connections)
    }

@app.get("/api/positions")
async def get_positions(
    api_key_info: Optional[Dict[str, Any]] = Depends(optional_api_key)
):
    """获取当前仓位数据"""
    global current_positions
    
    # 检查是否允许公开访问
    public_access = os.getenv("PUBLIC_ACCESS", "false").lower() == "true"
    is_public = api_key_info is None and public_access
    
    # 优先从内存获取
    if current_positions:
        positions = current_positions
        if is_public:
            positions = [sanitize_position_data(pos, is_public=True) for pos in positions]
        
        return {
            "positions": positions, 
            "timestamp": datetime.now().isoformat(),
            "source": "memory",
            "is_public": is_public
        }
    
    # 从Redis获取
    redis_data = redis_client.get_positions()
    if redis_data:
        positions = redis_data.get("positions", [])
        if is_public:
            positions = [sanitize_position_data(pos, is_public=True) for pos in positions]
        
        return {
            "positions": positions,
            "timestamp": redis_data.get("timestamp"),
            "source": "redis",
            "is_public": is_public
        }
    
    # 从IB实时获取
    ib_app = get_ib_app()
    if ib_app.is_connected:
        ib_app.request_positions()
        positions = ib_app.get_positions()
        if is_public:
            positions = [sanitize_position_data(pos, is_public=True) for pos in positions]
        
        return {
            "positions": positions,
            "timestamp": datetime.now().isoformat(),
            "source": "ib_realtime",
            "is_public": is_public
        }
    
    return {
        "positions": [], 
        "timestamp": datetime.now().isoformat(), 
        "source": "empty",
        "is_public": is_public
    }

@app.get("/api/account")
async def get_account_info(
    api_key_info: Optional[Dict[str, Any]] = Depends(optional_api_key)
):
    """获取账户信息"""
    global current_account
    
    # 检查是否允许公开访问
    public_access = os.getenv("PUBLIC_ACCESS", "false").lower() == "true"
    is_public = api_key_info is None and public_access
    
    # 优先从内存获取
    if current_account:
        accounts = current_account
        if is_public:
            accounts = [sanitize_account_data(acc, is_public=True) for acc in accounts]
        
        return {
            "accounts": accounts,
            "timestamp": datetime.now().isoformat(),
            "source": "memory",
            "is_public": is_public
        }
    
    # 从Redis获取
    redis_data = redis_client.get_account_summary()
    if redis_data:
        accounts = redis_data.get("accounts", [])
        if is_public:
            accounts = [sanitize_account_data(acc, is_public=True) for acc in accounts]
        
        return {
            "accounts": accounts,
            "timestamp": redis_data.get("timestamp"),
            "source": "redis",
            "is_public": is_public
        }
    
    # 从IB实时获取
    ib_app = get_ib_app()
    if ib_app.is_connected:
        ib_app.request_account_summary()
        accounts = ib_app.get_account_summary()
        if is_public:
            accounts = [sanitize_account_data(acc, is_public=True) for acc in accounts]
        
        return {
            "accounts": accounts,
            "timestamp": datetime.now().isoformat(),
            "source": "ib_realtime",
            "is_public": is_public
        }
    
    return {
        "accounts": [], 
        "timestamp": datetime.now().isoformat(), 
        "source": "empty",
        "is_public": is_public
    }

@app.post("/api/refresh")
async def refresh_data(
    api_key_info: Dict[str, Any] = Depends(require_permission("write"))
):
    """手动刷新数据（需要写权限）"""
    ib_app = get_ib_app()
    if not ib_app.is_connected:
        raise HTTPException(status_code=503, detail="IB Gateway not connected")
    
    ib_app.request_positions()
    ib_app.request_account_summary()
    
    return {
        "message": "Data refresh requested", 
        "timestamp": datetime.now().isoformat(),
        "requested_by": api_key_info.get("key", "unknown")[:8] + "..."
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # 发送当前数据
        if current_positions:
            await websocket.send_text(json.dumps({
                "type": "positions_snapshot",
                "data": current_positions
            }))
        
        if current_account:
            await websocket.send_text(json.dumps({
                "type": "account_snapshot", 
                "data": current_account
            }))
        
        # 保持连接
        while True:
            data = await websocket.receive_text()
            # 处理客户端消息（如订阅特定数据等）
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)