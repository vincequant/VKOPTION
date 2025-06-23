#!/usr/bin/env python3
"""
IB Portfolio Monitor - Enhanced Version with All Available Data
IB 倉位監控系統 - 增強版（獲取所有可用數據）
"""

from flask import Flask, jsonify, send_file, render_template_string, request
import json
import os
import threading
import time
import logging
from pathlib import Path
from datetime import datetime
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import queue

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask 應用
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 應用配置
CONFIG = {
    'TWS_HOST': '127.0.0.1',
    'TWS_PORT': 7496,
    'CLIENT_ID': 999,
    'SERVER_PORT': 8080,
    'DATA_FILE': 'portfolio_data_enhanced.json',
    'DASHBOARD_FILE': 'dashboard_new.html'
}

# 全局變量
ib_client = None
update_lock = threading.Lock()

class EnhancedIBClient(EWrapper, EClient):
    """增強版 IB API 客戶端 - 獲取所有可用數據"""
    
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.positions = {}  # 使用字典存儲，key為symbol
        self.contracts = {}  # 存儲完整的contract對象
        self.market_data = {}  # 市場數據
        self.account_summary = {}  # 賬戶摘要
        self.account_values = {}  # 賬戶價值
        self.pnl = {}  # 盈虧數據
        self.options_data = {}  # 期權特定數據
        self.historical_data = {}  # 歷史數據
        
        self.nextOrderId = 1
        self._thread = None
        self.update_complete = threading.Event()
        self.connection_ready = threading.Event()
        self.market_data_ready = threading.Event()
        self.account_data_ready = threading.Event()
        
        # 請求ID管理
        self.req_id_counter = 1000
        self.req_id_map = {}  # reqId -> symbol mapping
        
    def nextReqId(self):
        """生成下一個請求ID"""
        self.req_id_counter += 1
        return self.req_id_counter
        
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """錯誤處理"""
        if errorCode in [2104, 2106, 2107, 2108, 2158]:
            return
        logger.error(f"IB API Error {errorCode}: {errorString} (reqId: {reqId})")
    
    def connectAck(self):
        """連接確認"""
        super().connectAck()
        self.connected = True
        logger.info("Connected to TWS")
        if not self._thread or not self._thread.is_alive():
            self._thread = threading.Thread(target=self.run, daemon=True)
            self._thread.start()
    
    def connectionClosed(self):
        """連接關閉"""
        super().connectionClosed()
        self.connected = False
        logger.info("Disconnected from TWS")
    
    def nextValidId(self, orderId: int):
        """接收下一個有效訂單ID"""
        super().nextValidId(orderId)
        self.nextOrderId = orderId
        logger.info(f"Next Valid Order ID: {orderId}")
        self.connection_ready.set()
        
    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """接收持倉數據"""
        if position != 0:
            symbol = contract.symbol
            
            # 存儲完整的contract對象
            self.contracts[symbol] = contract
            
            # 存儲持倉信息
            self.positions[symbol] = {
                'account': account,
                'symbol': symbol,
                'secType': contract.secType,
                'position': position,
                'avgCost': avgCost,
                'currency': contract.currency or 'USD',
                'exchange': contract.exchange or 'SMART',
                'primaryExchange': contract.primaryExchange,
                'conId': contract.conId,
                'localSymbol': contract.localSymbol,
                'tradingClass': contract.tradingClass
            }
            
            # 期權特定信息
            if contract.secType == 'OPT':
                self.positions[symbol].update({
                    'strike': contract.strike,
                    'right': contract.right,
                    'expiry': contract.lastTradeDateOrContractMonth,
                    'multiplier': contract.multiplier or '100'
                })
                
            logger.info(f"Received position: {symbol} {position}")
            
    def positionEnd(self):
        """持倉數據接收完成"""
        logger.info(f"Received {len(self.positions)} positions")
        # 請求額外數據
        self.requestAdditionalData()
        
    def requestAdditionalData(self):
        """請求所有額外數據"""
        logger.info("Requesting additional data...")
        
        # 1. 請求賬戶摘要
        self.reqAccountSummary(9001, "All", 
            "NetLiquidation,TotalCashValue,SettledCash,AccruedCash,BuyingPower,"
            "EquityWithLoanValue,PreviousEquityWithLoanValue,GrossPositionValue,"
            "InitMarginReq,MaintMarginReq,AvailableFunds,ExcessLiquidity,Cushion,"
            "DayTradesRemaining,Leverage,Currency")
        
        # 2. 請求賬戶更新
        self.reqAccountUpdates(True, "")
        
        # 3. 請求PnL數據
        self.reqPnL(9002, "", "")
        
        # 4. 為每個持倉請求市場數據
        for symbol, pos_data in self.positions.items():
            contract = self.contracts[symbol]
            req_id = self.nextReqId()
            self.req_id_map[req_id] = symbol
            
            # 請求實時市場數據
            if contract.secType == 'OPT':
                # 期權需要特殊的tick類型
                self.reqMktData(req_id, contract, 
                    "100,101,104,105,106,107,125,221,225,233,236,258,293,294,295,318",  # 期權相關tick
                    False, False, [])
            else:
                # 股票的標準tick類型
                self.reqMktData(req_id, contract, "", False, False, [])
            
            # 為每個持倉請求單獨的PnL
            pnl_req_id = self.nextReqId()
            self.req_id_map[pnl_req_id] = symbol
            self.reqPnLSingle(pnl_req_id, "", "", contract.conId)
            
            # 請求歷史數據（最近5天）
            hist_req_id = self.nextReqId()
            self.req_id_map[hist_req_id] = symbol
            self.reqHistoricalData(
                hist_req_id, contract, "", "5 D", "1 day", 
                "MIDPOINT", 1, 1, False, []
            )
            
        # 設置超時，等待數據收集
        threading.Timer(10.0, self.dataCollectionComplete).start()
    
    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """接收賬戶摘要"""
        self.account_summary[tag] = {
            'value': value,
            'currency': currency,
            'account': account
        }
        logger.info(f"Account Summary - {tag}: {value} {currency}")
    
    def accountSummaryEnd(self, reqId: int):
        """賬戶摘要結束"""
        logger.info("Account summary completed")
        self.account_data_ready.set()
    
    def updateAccountValue(self, key: str, val: str, currency: str, accountName: str):
        """更新賬戶價值"""
        self.account_values[key] = {
            'value': val,
            'currency': currency,
            'account': accountName
        }
        
    def updatePortfolio(self, contract: Contract, position: float, marketPrice: float, 
                       marketValue: float, averageCost: float, unrealizedPNL: float, 
                       realizedPNL: float, accountName: str):
        """更新持倉組合（來自reqAccountUpdates）"""
        symbol = contract.symbol
        if symbol in self.positions:
            self.positions[symbol].update({
                'marketPrice': marketPrice,
                'marketValue': marketValue,
                'unrealizedPNL': unrealizedPNL,
                'realizedPNL': realizedPNL,
                'accountName': accountName
            })
            logger.info(f"Portfolio Update - {symbol}: Price={marketPrice}, PnL={unrealizedPNL}")
    
    def tickPrice(self, reqId, tickType, price, attrib):
        """接收價格數據"""
        if reqId in self.req_id_map:
            symbol = self.req_id_map[reqId]
            if symbol not in self.market_data:
                self.market_data[symbol] = {}
            
            # 記錄不同類型的價格
            price_types = {
                1: 'bid',
                2: 'ask',
                4: 'last',
                6: 'high',
                7: 'low',
                9: 'close',
                14: 'open',
                37: 'markPrice',
                68: 'histVolatility',
                72: 'indexFuturePremium'
            }
            
            if tickType in price_types:
                self.market_data[symbol][price_types[tickType]] = price
                logger.info(f"Price Update - {symbol} {price_types[tickType]}: {price}")
    
    def tickSize(self, reqId, tickType, size):
        """接收數量數據"""
        if reqId in self.req_id_map:
            symbol = self.req_id_map[reqId]
            if symbol not in self.market_data:
                self.market_data[symbol] = {}
            
            size_types = {
                0: 'bidSize',
                3: 'askSize',
                5: 'lastSize',
                8: 'volume',
                21: 'avgVolume',
                27: 'callOpenInterest',
                28: 'putOpenInterest',
                86: 'shortableShares'
            }
            
            if tickType in size_types:
                self.market_data[symbol][size_types[tickType]] = size
    
    def tickGeneric(self, reqId, tickType, value):
        """接收通用tick數據"""
        if reqId in self.req_id_map:
            symbol = self.req_id_map[reqId]
            if symbol not in self.market_data:
                self.market_data[symbol] = {}
            
            generic_types = {
                23: 'optionHistoricalVolatility',
                24: 'optionImpliedVolatility',
                31: 'indexFuturePremium',
                49: 'halted',
                54: 'tradeCount',
                55: 'tradeRate',
                56: 'volumeRate',
                58: 'rtHistoricalVolatility'
            }
            
            if tickType in generic_types:
                self.market_data[symbol][generic_types[tickType]] = value
    
    def tickOptionComputation(self, reqId, tickType, tickAttrib, impliedVol, delta, 
                            optPrice, pvDividend, gamma, vega, theta, undPrice):
        """接收期權計算數據（希臘值）"""
        if reqId in self.req_id_map:
            symbol = self.req_id_map[reqId]
            if symbol not in self.options_data:
                self.options_data[symbol] = {}
            
            # 存儲希臘值
            greeks = {
                'impliedVolatility': impliedVol,
                'delta': delta,
                'optionPrice': optPrice,
                'pvDividend': pvDividend,
                'gamma': gamma,
                'vega': vega,
                'theta': theta,
                'underlyingPrice': undPrice
            }
            
            # 根據tickType確定是哪種計算
            if tickType == 10:  # BID
                self.options_data[symbol]['bidGreeks'] = greeks
            elif tickType == 11:  # ASK
                self.options_data[symbol]['askGreeks'] = greeks
            elif tickType == 12:  # LAST
                self.options_data[symbol]['lastGreeks'] = greeks
            elif tickType == 13:  # MODEL
                self.options_data[symbol]['modelGreeks'] = greeks
                
            logger.info(f"Greeks Update - {symbol}: Delta={delta}, Gamma={gamma}, Theta={theta}, Vega={vega}")
    
    def pnl(self, reqId: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float):
        """接收賬戶級別PnL"""
        self.pnl['account'] = {
            'dailyPnL': dailyPnL,
            'unrealizedPnL': unrealizedPnL,
            'realizedPnL': realizedPnL
        }
        logger.info(f"Account PnL - Daily: {dailyPnL}, Unrealized: {unrealizedPnL}, Realized: {realizedPnL}")
    
    def pnlSingle(self, reqId: int, pos: int, dailyPnL: float, unrealizedPnL: float, 
                  realizedPnL: float, value: float):
        """接收單個持倉的PnL"""
        if reqId in self.req_id_map:
            symbol = self.req_id_map[reqId]
            self.pnl[symbol] = {
                'position': pos,
                'dailyPnL': dailyPnL,
                'unrealizedPnL': unrealizedPnL,
                'realizedPnL': realizedPnL,
                'marketValue': value
            }
            logger.info(f"Position PnL - {symbol}: Daily={dailyPnL}, Unrealized={unrealizedPnL}")
    
    def historicalData(self, reqId: int, bar):
        """接收歷史數據"""
        if reqId in self.req_id_map:
            symbol = self.req_id_map[reqId]
            if symbol not in self.historical_data:
                self.historical_data[symbol] = []
            
            self.historical_data[symbol].append({
                'date': bar.date,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume,
                'average': bar.average,
                'barCount': bar.barCount
            })
    
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """歷史數據結束"""
        if reqId in self.req_id_map:
            symbol = self.req_id_map[reqId]
            logger.info(f"Historical data completed for {symbol}")
    
    def dataCollectionComplete(self):
        """數據收集完成"""
        logger.info("Data collection complete, saving all data...")
        self.save_all_data()
        self.update_complete.set()
        
    def save_all_data(self):
        """保存所有數據到文件"""
        positions_data = []
        
        for symbol, pos in self.positions.items():
            position_data = pos.copy()
            
            # 添加市場數據
            if symbol in self.market_data:
                position_data['market_data'] = self.market_data[symbol]
            
            # 添加PnL數據
            if symbol in self.pnl:
                position_data['pnl_data'] = self.pnl[symbol]
            
            # 添加期權希臘值
            if symbol in self.options_data:
                position_data['options_data'] = self.options_data[symbol]
            
            # 添加歷史數據
            if symbol in self.historical_data:
                position_data['historical_data'] = self.historical_data[symbol]
            
            # 計算一些衍生數據
            if pos['secType'] == 'OPT':
                # 期權的市值計算
                avg_cost = pos['avgCost'] / 100  # 轉換為單位價格
                position_data['avg_cost'] = avg_cost
                position_data['market_value'] = pos['position'] * pos['avgCost']
                
                # 格式化到期日
                expiry = pos['expiry']
                position_data['expiry_formatted'] = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}"
                
                # 計算到期天數
                try:
                    from datetime import date
                    expiry_date = date(int(expiry[:4]), int(expiry[4:6]), int(expiry[6:8]))
                    position_data['days_to_expiry'] = (expiry_date - date.today()).days
                except:
                    position_data['days_to_expiry'] = 0
            else:
                position_data['market_value'] = pos['position'] * pos['avgCost']
                
            positions_data.append(position_data)
        
        # 計算統計數據
        options_count = len([p for p in positions_data if p['secType'] == 'OPT'])
        stocks_count = len([p for p in positions_data if p['secType'] == 'STK'])
        total_market_value = sum(p.get('market_value', 0) for p in positions_data)
        
        # 按到期日計算期權價值
        options_by_expiry = {}
        for pos in positions_data:
            if pos['secType'] == 'OPT':
                expiry = pos['expiry']
                if expiry not in options_by_expiry:
                    options_by_expiry[expiry] = {
                        'expiry': expiry,
                        'expiry_formatted': pos['expiry_formatted'],
                        'days_to_expiry': pos['days_to_expiry'],
                        'total_value': 0,
                        'count': 0,
                        'positions': []
                    }
                options_by_expiry[expiry]['total_value'] += pos['market_value']
                options_by_expiry[expiry]['count'] += 1
                options_by_expiry[expiry]['positions'].append(pos['symbol'])
        
        # 組裝完整數據
        portfolio_data = {
            'timestamp': datetime.now().isoformat(),
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'positions': positions_data,
            'summary': {
                'total_positions': len(positions_data),
                'options_count': options_count,
                'stocks_count': stocks_count,
                'total_market_value': total_market_value
            },
            'account_summary': self.account_summary,
            'account_values': self.account_values,
            'account_pnl': self.pnl.get('account', {}),
            'options_by_expiry': list(options_by_expiry.values()),
            'source': 'ib_api_enhanced',
            'status': 'updated'
        }
        
        # 保存到文件
        try:
            temp_file = CONFIG['DATA_FILE'] + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(portfolio_data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, CONFIG['DATA_FILE'])
            logger.info(f"Enhanced portfolio data saved to {CONFIG['DATA_FILE']}")
        except Exception as e:
            logger.error(f"Failed to save portfolio data: {e}")

# Flask 路由
@app.after_request
def after_request(response):
    """添加 CORS 支持"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

@app.route('/')
def index():
    """主頁 - 返回儀表板"""
    dashboard_path = Path(CONFIG['DASHBOARD_FILE'])
    if dashboard_path.exists():
        return send_file(dashboard_path)
    else:
        return "Dashboard file not found", 404

@app.route('/test')
def test_page():
    """測試頁面 - 顯示所有可用數據"""
    test_path = Path('test_api_data.html')
    if test_path.exists():
        return send_file(test_path)
    else:
        return "Test page not found", 404

@app.route('/api/portfolio')
def get_portfolio():
    """API: 獲取持倉數據"""
    try:
        data_file = Path(CONFIG['DATA_FILE'])
        if data_file.exists():
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({
                "error": "No data available",
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_positions": 0,
                    "total_market_value": 0
                },
                "positions": []
            })
    except Exception as e:
        logger.error(f"Error reading portfolio data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/update', methods=['POST'])
def update_portfolio():
    """API: 更新持倉數據"""
    global ib_client
    
    with update_lock:
        try:
            logger.info("Starting enhanced portfolio update...")
            
            if ib_client:
                try:
                    ib_client.disconnect()
                except:
                    pass
                time.sleep(1)
            
            ib_client = EnhancedIBClient()
            ib_client.connection_ready.clear()
            ib_client.update_complete.clear()
            
            logger.info(f"Connecting to TWS at {CONFIG['TWS_HOST']}:{CONFIG['TWS_PORT']}")
            ib_client.connect(CONFIG['TWS_HOST'], CONFIG['TWS_PORT'], clientId=CONFIG['CLIENT_ID'])
            
            if not ib_client.connection_ready.wait(timeout=5):
                logger.error("Connection timeout - did not receive nextValidId")
                return jsonify({
                    "success": False,
                    "error": "Connection timeout",
                    "message": "無法連接到 TWS，請確保 TWS 正在運行並已啟用 API"
                }), 503
            
            # 清空舊數據
            ib_client.positions = {}
            ib_client.contracts = {}
            ib_client.market_data = {}
            ib_client.account_summary = {}
            ib_client.pnl = {}
            ib_client.options_data = {}
            ib_client.historical_data = {}
            
            logger.info("Requesting positions...")
            ib_client.reqPositions()
            
            # 等待所有數據收集完成（增加超時時間）
            if ib_client.update_complete.wait(timeout=20):
                logger.info("Enhanced update completed successfully")
                return jsonify({
                    "success": True,
                    "message": f"成功更新 {len(ib_client.positions)} 個持倉及所有市場數據",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                logger.error("Update timeout")
                return jsonify({
                    "success": False,
                    "error": "Update timeout",
                    "message": "獲取數據超時，部分數據可能不完整"
                }), 504
                
        except Exception as e:
            logger.error(f"Update error: {e}")
            return jsonify({
                "success": False,
                "error": str(e),
                "message": "更新失敗"
            }), 500

@app.route('/api/status')
def get_status():
    """API: 獲取系統狀態"""
    global ib_client
    
    tws_connected = ib_client and ib_client.isConnected()
    
    data_file = Path(CONFIG['DATA_FILE'])
    has_data = data_file.exists()
    last_update = None
    source = None
    
    if has_data:
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
                last_update = data.get('last_update')
                source = data.get('source', 'unknown')
        except:
            pass
    
    return jsonify({
        "status": "running",
        "tws_connected": tws_connected,
        "has_data": has_data,
        "last_update": last_update,
        "data_source": source,
        "server_time": datetime.now().isoformat(),
        "config": {
            "tws_host": CONFIG['TWS_HOST'],
            "tws_port": CONFIG['TWS_PORT'],
            "client_id": CONFIG['CLIENT_ID']
        }
    })

def main():
    """主函數 - 啟動應用"""
    print("=" * 60)
    print("IB Portfolio Monitor - Enhanced Version")
    print("=" * 60)
    print(f"📁 Working Directory: {os.getcwd()}")
    print(f"📊 Data File: {CONFIG['DATA_FILE']}")
    print(f"🔌 TWS Connection: {CONFIG['TWS_HOST']}:{CONFIG['TWS_PORT']}")
    print("=" * 60)
    print(f"🚀 Starting server on port {CONFIG['SERVER_PORT']}...")
    print(f"🌐 Access the dashboard at: http://localhost:{CONFIG['SERVER_PORT']}")
    print(f"🧪 Access the test page at: http://localhost:{CONFIG['SERVER_PORT']}/test")
    print("=" * 60)
    print("💡 Press Ctrl+C to stop the server")
    
    try:
        app.run(
            host='0.0.0.0',
            port=CONFIG['SERVER_PORT'],
            debug=False,
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        if ib_client and ib_client.isConnected():
            ib_client.disconnect()
    except Exception as e:
        logger.error(f"Server error: {e}")
        print(f"\n❌ Server error: {e}")

if __name__ == "__main__":
    main()