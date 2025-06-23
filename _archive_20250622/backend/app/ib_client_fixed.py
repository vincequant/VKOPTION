import asyncio
import threading
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Position:
    account: str
    symbol: str
    contract_id: int
    position: float
    market_price: float
    market_value: float
    avg_cost: float
    unrealized_pnl: float
    realized_pnl: float
    currency: str
    timestamp: str

@dataclass
class AccountSummary:
    account: str
    total_cash_value: float
    net_liquidation: float
    gross_position_value: float
    buying_power: float
    currency: str
    timestamp: str

class IBWrapper(EWrapper):
    def __init__(self):
        EWrapper.__init__(self)
        self.positions: Dict[str, Position] = {}
        self.account_summary: Dict[str, AccountSummary] = {}
        self.position_callbacks: List[Callable] = []
        self.account_callbacks: List[Callable] = []
        self.connected = False
        self.next_order_id = None
        self.connection_time = None

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        logger.error(f"IB Error {errorCode}: {errorString}")
        # 不阻塞启动的错误码
        non_blocking_errors = [2104, 2106, 2158]
        if errorCode not in non_blocking_errors:
            logger.warning(f"Non-critical error: {errorCode}")

    def connectAck(self):
        logger.info("✅ IB Gateway connection acknowledged")
        self.connection_time = time.time()

    def connectionClosed(self):
        logger.info("❌ IB Gateway connection closed")
        self.connected = False

    def nextValidId(self, orderId: int):
        self.next_order_id = orderId
        self.connected = True
        logger.info(f"✅ IB Gateway connected successfully! Next order ID: {orderId}")

    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """接收实时仓位数据"""
        key = f"{account}_{contract.conId}"
        
        # 创建或更新仓位数据
        pos = Position(
            account=account,
            symbol=contract.symbol,
            contract_id=contract.conId,
            position=position,
            market_price=0.0,  # 需要从市场数据获取
            market_value=position * avgCost if position != 0 else 0.0,
            avg_cost=avgCost,
            unrealized_pnl=0.0,  # 需要计算
            realized_pnl=0.0,
            currency=contract.currency or "USD",
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        self.positions[key] = pos
        logger.info(f"📊 Position update: {account} {contract.symbol} {position}")
        
        # 通知所有回调函数
        for callback in self.position_callbacks:
            try:
                callback(pos)
            except Exception as e:
                logger.error(f"Position callback error: {e}")

    def positionEnd(self):
        """仓位数据传输完成"""
        logger.info(f"📋 Position data complete. Total positions: {len(self.positions)}")

    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """接收账户摘要数据"""
        if account not in self.account_summary:
            self.account_summary[account] = AccountSummary(
                account=account,
                total_cash_value=0.0,
                net_liquidation=0.0,
                gross_position_value=0.0,
                buying_power=0.0,
                currency=currency,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
            )
        
        summary = self.account_summary[account]
        
        # 更新对应的字段
        try:
            if tag == "TotalCashValue":
                summary.total_cash_value = float(value)
            elif tag == "NetLiquidation":
                summary.net_liquidation = float(value)
            elif tag == "GrossPositionValue":
                summary.gross_position_value = float(value)
            elif tag == "BuyingPower":
                summary.buying_power = float(value)
        except ValueError:
            logger.warning(f"Cannot convert {tag}={value} to float")
        
        # 通知回调函数
        for callback in self.account_callbacks:
            try:
                callback(summary)
            except Exception as e:
                logger.error(f"Account callback error: {e}")

    def accountSummaryEnd(self, reqId: int):
        """账户摘要数据传输完成"""
        logger.info(f"💰 Account summary complete. Accounts: {list(self.account_summary.keys())}")

class IBClient(EClient):
    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)
        self.wrapper = wrapper

class IBApp:
    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self.wrapper = IBWrapper()
        self.client = IBClient(self.wrapper)
        self.host = host
        self.port = port
        self.client_id = client_id
        self.thread = None
        self.running = False
        self.connection_timeout = 10  # 10秒连接超时

    def connect(self) -> bool:
        """非阻塞连接到IB Gateway"""
        try:
            logger.info(f"🔌 Attempting to connect to IB Gateway at {self.host}:{self.port}")
            
            # 尝试连接
            self.client.connect(self.host, self.port, self.client_id)
            
            # 启动消息处理线程
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            
            # 非阻塞等待连接（最多等待连接超时时间）
            start_time = time.time()
            while not self.wrapper.connected and (time.time() - start_time) < self.connection_timeout:
                time.sleep(0.1)
            
            if self.wrapper.connected:
                logger.info("✅ Successfully connected to IB Gateway")
                return True
            else:
                logger.warning("⚠️ IB Gateway connection timeout - continuing without real data")
                return False
                
        except Exception as e:
            logger.error(f"❌ IB Gateway connection error: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        self.running = False
        if self.client.isConnected():
            self.client.disconnect()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def _run_loop(self):
        """消息处理循环"""
        self.running = True
        try:
            while self.running and self.client.isConnected():
                self.client.run()
        except Exception as e:
            logger.error(f"IB client run error: {e}")
        finally:
            self.running = False

    def request_positions(self):
        """请求仓位数据"""
        if self.wrapper.connected:
            self.client.reqPositions()
            logger.info("📊 Requested position data")
        else:
            logger.warning("⚠️ Cannot request positions - not connected to IB Gateway")

    def request_account_summary(self):
        """请求账户摘要"""
        if self.wrapper.connected:
            tags = "TotalCashValue,NetLiquidation,GrossPositionValue,BuyingPower"
            self.client.reqAccountSummary(9001, "All", tags)
            logger.info("💰 Requested account summary")
        else:
            logger.warning("⚠️ Cannot request account summary - not connected to IB Gateway")

    def add_position_callback(self, callback: Callable):
        """添加仓位数据回调函数"""
        self.wrapper.position_callbacks.append(callback)

    def add_account_callback(self, callback: Callable):
        """添加账户数据回调函数"""
        self.wrapper.account_callbacks.append(callback)

    def get_positions(self) -> List[Dict]:
        """获取当前所有仓位"""
        return [asdict(pos) for pos in self.wrapper.positions.values()]

    def get_account_summary(self) -> List[Dict]:
        """获取账户摘要"""
        return [asdict(summary) for summary in self.wrapper.account_summary.values()]

    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.wrapper.connected and self.client.isConnected()

# 全局IB应用实例
ib_app: Optional[IBApp] = None

def get_ib_app() -> IBApp:
    """获取IB应用实例"""
    global ib_app
    if ib_app is None:
        import os
        host = os.getenv("IB_HOST", "127.0.0.1")
        port = int(os.getenv("IB_PORT", "7497"))
        client_id = int(os.getenv("IB_CLIENT_ID", "1"))
        ib_app = IBApp(host, port, client_id)
    return ib_app