#!/usr/bin/env python3
"""
測試程序：診斷 PnL 和 Greeks 數據為何顯示為 0
"""

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time
import logging

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PnLGreeksTester(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.nextOrderId = 1
        self.account = None
        self.positions = []
        self.test_complete = threading.Event()
        
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """處理錯誤"""
        if errorCode in [2104, 2106, 2107, 2108, 2158, 2119, 2110]:
            return
        logger.error(f"Error {errorCode}: {errorString} (reqId: {reqId})")
        
    def nextValidId(self, orderId):
        """TWS 連接就緒"""
        self.nextOrderId = orderId
        logger.info(f"Connected to TWS, nextOrderId: {orderId}")
        self.connected = True
        
    def managedAccounts(self, accountsList):
        """接收賬戶列表"""
        self.account = accountsList.split(',')[0] if accountsList else None
        logger.info(f"Account: {self.account}")
        
    def position(self, account, contract, position, avgCost):
        """接收持倉信息"""
        if position != 0:
            self.positions.append({
                'account': account,
                'contract': contract,
                'position': position,
                'avgCost': avgCost
            })
            logger.info(f"Position: {contract.symbol} {contract.secType} {position} @ {avgCost}")
            
    def positionEnd(self):
        """持倉信息結束"""
        logger.info(f"Total positions: {len(self.positions)}")
        
    def pnlSingle(self, reqId, pos, dailyPnL, unrealizedPnL, realizedPnL, value):
        """接收單個持倉的盈虧"""
        logger.info(f"PnL for reqId {reqId}: Position={pos}, DailyPnL={dailyPnL}, "
                   f"UnrealizedPnL={unrealizedPnL}, RealizedPnL={realizedPnL}, Value={value}")
        
    def tickOptionComputation(self, reqId, tickType, tickAttrib, impliedVol, delta, 
                            optPrice, pvDividend, gamma, vega, theta, undPrice):
        """接收期權希臘值"""
        logger.info(f"Greeks for reqId {reqId}: IV={impliedVol:.4f}, Delta={delta:.4f}, "
                   f"Gamma={gamma:.4f}, Theta={theta:.4f}, Vega={vega:.4f}")
        
    def tickPrice(self, reqId, tickType, price, attrib):
        """接收價格數據"""
        tick_names = {
            1: "BID", 2: "ASK", 4: "LAST", 6: "HIGH", 
            7: "LOW", 9: "CLOSE", 14: "OPEN"
        }
        tick_name = tick_names.get(tickType, str(tickType))
        if price > 0:
            logger.info(f"Price for reqId {reqId}: {tick_name}={price}")
            
    def tickSize(self, reqId, tickType, size):
        """接收大小數據"""
        size_names = {
            0: "BID_SIZE", 3: "ASK_SIZE", 5: "LAST_SIZE", 8: "VOLUME"
        }
        size_name = size_names.get(tickType, str(tickType))
        if tickType in size_names and size > 0:
            logger.info(f"Size for reqId {reqId}: {size_name}={size}")

def test_pnl_and_greeks():
    """測試 PnL 和 Greeks 數據獲取"""
    app = PnLGreeksTester()
    
    # 連接到 TWS
    app.connect("127.0.0.1", 7496, 999)
    
    # 啟動消息處理線程
    api_thread = threading.Thread(target=app.run)
    api_thread.daemon = True
    api_thread.start()
    
    # 等待連接
    time.sleep(2)
    
    if not app.connected:
        logger.error("Failed to connect to TWS")
        return
    
    # 請求持倉
    logger.info("\n=== Requesting Positions ===")
    app.reqPositions()
    time.sleep(3)
    
    # 為每個持倉請求數據
    req_id = 1000
    
    for pos_data in app.positions[:3]:  # 只測試前3個持倉
        contract = pos_data['contract']
        logger.info(f"\n=== Testing {contract.symbol} {contract.secType} ===")
        
        # 1. 請求 PnL
        if app.account:
            logger.info(f"Requesting PnL for {contract.symbol}")
            app.reqPnLSingle(req_id, app.account, "", contract.conId)
            req_id += 1
            time.sleep(2)
        
        # 2. 請求市場數據（包括希臘值）
        logger.info(f"Requesting market data for {contract.symbol}")
        
        # 對於期權，請求希臘值相關的 tick types
        if contract.secType == "OPT":
            # 請求模型數據（包括希臘值）
            app.reqMktData(req_id, contract, "", False, False, [])
            
            # 具體請求希臘值相關的 tick types
            # 10: Bid Option Computation
            # 11: Ask Option Computation
            # 12: Last Option Computation
            # 13: Model Option Computation
            logger.info("Requesting option computation ticks...")
            
        else:
            # 非期權只請求基本市場數據
            app.reqMktData(req_id, contract, "", False, False, [])
        
        req_id += 1
        time.sleep(5)  # 給市場數據更多時間
        
        # 3. 測試不同的請求方式
        if contract.secType == "OPT":
            logger.info(f"Testing calculated option price for {contract.symbol}")
            
            # 嘗試請求計算的期權價格
            app.reqCalculateOptionPrice(
                req_id,
                contract,
                390,  # 標的價格（示例）
                0.25  # 隱含波動率（示例）
            )
            req_id += 1
            time.sleep(2)
    
    # 等待數據
    logger.info("\n=== Waiting for data... ===")
    time.sleep(10)
    
    # 取消所有請求
    for i in range(1000, req_id):
        try:
            app.cancelMktData(i)
            app.cancelPnLSingle(i)
        except:
            pass
    
    # 斷開連接
    app.disconnect()
    
    logger.info("\n=== Test Complete ===")
    logger.info("Check the logs above to see which data was successfully received.")
    logger.info("\nPossible issues if data is missing:")
    logger.info("1. PnL data requires proper account permissions")
    logger.info("2. Greeks require real-time option data subscription")
    logger.info("3. Some data may only be available during market hours")
    logger.info("4. Contract specifications must be exact")

if __name__ == "__main__":
    logger.info("Starting PnL and Greeks Data Test")
    logger.info("Make sure TWS is running and API is enabled")
    logger.info("This will test the first 3 positions in your account")
    
    test_pnl_and_greeks()