#!/usr/bin/env python3
"""
測試 TWS 連接
"""

import time
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading

class TestApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.data = []
        
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        print(f"Error {errorCode}: {errorString}")
        
    def connectAck(self):
        print("Connected to TWS")
        self.connected = True
        
    def nextValidId(self, orderId: int):
        print(f"NextValidId: {orderId}")
        # 立即請求持倉
        self.reqPositions()
        
    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        print(f"Position: {contract.symbol} {position} @ {avgCost}")
        self.data.append({
            'symbol': contract.symbol,
            'position': position,
            'avgCost': avgCost
        })
        
    def positionEnd(self):
        print(f"Position End - Total: {len(self.data)} positions")
        self.disconnect()

def test_connection():
    app = TestApp()
    
    # 連接
    print("Connecting to TWS...")
    app.connect("127.0.0.1", 7496, clientId=9999)
    
    # 運行客戶端線程
    api_thread = threading.Thread(target=app.run, daemon=True)
    api_thread.start()
    
    # 等待測試完成
    time.sleep(10)
    
    if app.connected:
        print("Test passed!")
        return True
    else:
        print("Test failed!")
        return False

if __name__ == "__main__":
    test_connection()