#!/usr/bin/env python3
"""
測試程序：查找香港股票期權的正確合約規格
測試 700 (騰訊) 和 1024 (快手) 的期權合約
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

class HKOptionTester(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.nextOrderId = 1
        self.found_contracts = []
        self.test_complete = threading.Event()
        
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """處理錯誤"""
        if errorCode in [2104, 2106, 2107, 2108, 2158, 2119, 2110]:
            # 忽略資訊性消息
            return
        logger.error(f"Error {errorCode}: {errorString} (reqId: {reqId})")
        
    def nextValidId(self, orderId):
        """TWS 連接就緒"""
        self.nextOrderId = orderId
        logger.info(f"Connected to TWS, nextOrderId: {orderId}")
        self.connected = True
        
    def contractDetails(self, reqId, contractDetails):
        """接收合約詳情"""
        contract = contractDetails.contract
        logger.info(f"Found Contract - Symbol: {contract.symbol}, LocalSymbol: {contract.localSymbol}, "
                   f"Exchange: {contract.exchange}, ConId: {contract.conId}, "
                   f"Strike: {contract.strike}, Right: {contract.right}, Expiry: {contract.lastTradeDateOrContractMonth}")
        self.found_contracts.append(contractDetails)
        
    def contractDetailsEnd(self, reqId):
        """合約詳情查詢結束"""
        logger.info(f"Contract details search completed for reqId: {reqId}")
        if reqId == 1002:  # 最後一個測試完成
            self.test_complete.set()

def test_hk_stock_options():
    """測試不同的香港股票期權合約格式"""
    app = HKOptionTester()
    
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
    
    # 測試不同的合約格式
    test_configs = [
        # 騰訊 (700.HK) 的不同格式
        {"symbol": "700", "desc": "Tencent - numeric symbol"},
        {"symbol": "0700", "desc": "Tencent - padded symbol"},
        {"symbol": "700.HK", "desc": "Tencent - with .HK suffix"},
        {"symbol": "TCH", "desc": "Tencent - trading class"},
        
        # 快手 (1024.HK) 的不同格式
        {"symbol": "1024", "desc": "Kuaishou - numeric symbol"},
        {"symbol": "01024", "desc": "Kuaishou - padded symbol"},
        {"symbol": "1024.HK", "desc": "Kuaishou - with .HK suffix"},
        {"symbol": "KST", "desc": "Kuaishou - trading class"},
    ]
    
    req_id = 1001
    
    for config in test_configs:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {config['desc']}")
        logger.info(f"Symbol: {config['symbol']}")
        logger.info(f"{'='*60}")
        
        # 創建期權合約查詢
        contract = Contract()
        contract.symbol = config['symbol']
        contract.secType = "OPT"
        contract.exchange = "SMART"
        contract.currency = "HKD"
        
        # 請求合約詳情
        app.reqContractDetails(req_id, contract)
        time.sleep(1)  # 給每個查詢一些時間
        
        # 也嘗試 HKFE 交易所
        contract_hkfe = Contract()
        contract_hkfe.symbol = config['symbol']
        contract_hkfe.secType = "OPT"
        contract_hkfe.exchange = "HKFE"
        contract_hkfe.currency = "HKD"
        
        req_id += 1
        app.reqContractDetails(req_id, contract_hkfe)
        time.sleep(1)
        
        req_id += 1
    
    # 最後測試使用具體的合約參數
    logger.info(f"\n{'='*60}")
    logger.info("Testing specific contract with known parameters")
    logger.info(f"{'='*60}")
    
    # 測試具體的騰訊期權合約
    specific_contract = Contract()
    specific_contract.symbol = "TCH"  # 使用 trading class
    specific_contract.secType = "OPT"
    specific_contract.exchange = "HKFE"
    specific_contract.currency = "HKD"
    specific_contract.lastTradeDateOrContractMonth = "20250919"  # 根據您的持倉
    specific_contract.strike = 410  # 一個示例行使價
    specific_contract.right = "P"  # Put
    
    app.reqContractDetails(1002, specific_contract)
    
    # 等待所有測試完成
    app.test_complete.wait(timeout=30)
    
    # 顯示結果摘要
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY OF FINDINGS")
    logger.info(f"{'='*60}")
    logger.info(f"Total contracts found: {len(app.found_contracts)}")
    
    # 按 symbol 分組顯示
    symbols = {}
    for cd in app.found_contracts:
        symbol = cd.contract.symbol
        if symbol not in symbols:
            symbols[symbol] = []
        symbols[symbol].append(cd)
    
    for symbol, contracts in symbols.items():
        logger.info(f"\nSymbol: {symbol}")
        logger.info(f"Number of contracts: {len(contracts)}")
        if len(contracts) > 0:
            # 顯示第一個合約的詳細信息作為示例
            c = contracts[0].contract
            logger.info(f"  Example - LocalSymbol: {c.localSymbol}, Exchange: {c.exchange}, "
                       f"TradingClass: {c.tradingClass}, ConId: {c.conId}")
    
    # 斷開連接
    app.disconnect()
    
    # 生成建議
    logger.info(f"\n{'='*60}")
    logger.info("RECOMMENDATIONS")
    logger.info(f"{'='*60}")
    
    if "TCH" in symbols:
        logger.info("✓ For Tencent (700.HK) options, use symbol='TCH'")
    elif "700" in symbols:
        logger.info("✓ For Tencent (700.HK) options, use symbol='700'")
    else:
        logger.info("✗ Could not find Tencent options - check TWS permissions")
    
    if "KST" in symbols:
        logger.info("✓ For Kuaishou (1024.HK) options, use symbol='KST'")
    elif "1024" in symbols:
        logger.info("✓ For Kuaishou (1024.HK) options, use symbol='1024'")
    else:
        logger.info("✗ Could not find Kuaishou options - check TWS permissions")
    
    logger.info("\nNote: Make sure you have Hong Kong derivatives data subscription if needed.")

if __name__ == "__main__":
    logger.info("Starting Hong Kong Options Contract Test")
    logger.info("Make sure TWS is running and API is enabled")
    logger.info("Testing Tencent (700.HK) and Kuaishou (1024.HK) options...")
    
    test_hk_stock_options()