#!/usr/bin/env python3
"""
IB Portfolio Monitor - Fixed Version
IB 倉位監控系統 - 修復版本
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
    'DATA_FILE': 'portfolio_data.json',
    'DASHBOARD_FILE': 'dashboard_new.html'
}

# 全局變量
ib_client = None
update_lock = threading.Lock()

class IBPortfolioClient(EWrapper, EClient):
    """IB API 客戶端 - 獲取持倉數據"""
    
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.positions = []
        self.nextOrderId = 1
        self._thread = None
        self.update_complete = threading.Event()
        self.connection_ready = threading.Event()
        
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """錯誤處理"""
        if errorCode in [2104, 2106, 2107, 2108, 2158]:
            return
        logger.error(f"IB API Error {errorCode}: {errorString}")
    
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
            pos_info = {
                'account': account,
                'symbol': contract.symbol,
                'secType': contract.secType,
                'position': position,
                'avgCost': avgCost,
                'currency': contract.currency or 'USD',
                'exchange': contract.exchange or 'SMART'
            }
            
            if contract.secType == 'OPT':
                pos_info.update({
                    'strike': contract.strike,
                    'right': contract.right,
                    'expiry': contract.lastTradeDateOrContractMonth,
                    'multiplier': contract.multiplier or '100'
                })
                
            self.positions.append(pos_info)
            logger.info(f"Received position: {contract.symbol} {position}")
            
    def positionEnd(self):
        """持倉數據接收完成"""
        logger.info(f"Received {len(self.positions)} positions")
        self.save_positions()
        self.update_complete.set()
        
    def save_positions(self):
        """保存持倉數據到文件"""
        if not self.positions:
            logger.warning("No positions to save")
            return
            
        positions_data = []
        for pos in self.positions:
            # 過濾現金持倉
            if pos['secType'] == 'CASH':
                continue
                
            position_data = {
                'account': pos['account'],
                'symbol': pos['symbol'],
                'sec_type': pos['secType'],
                'position': pos['position'],
                'avg_cost': pos['avgCost'],
                'currency': pos['currency'],
                'exchange': pos['exchange'],
                'timestamp': datetime.now().isoformat(),
            }
            
            if pos['secType'] == 'OPT':
                # 期權的平均成本需要除以100顯示單位價格
                position_data['avg_cost'] = pos['avgCost'] / 100
                position_data.update({
                    'strike': pos['strike'],
                    'right': pos['right'],
                    'expiry': pos['expiry'],
                    'multiplier': pos['multiplier'],
                    'market_value': pos['position'] * pos['avgCost'],  # 保留正負值
                    'expiry_formatted': f"{pos['expiry'][:4]}-{pos['expiry'][4:6]}-{pos['expiry'][6:8]}",
                    'option_type_name': '看漲期權' if pos['right'] == 'C' else '看跌期權',
                })
                
                try:
                    from datetime import date
                    expiry_date = date(int(pos['expiry'][:4]), int(pos['expiry'][4:6]), int(pos['expiry'][6:8]))
                    position_data['days_to_expiry'] = (expiry_date - date.today()).days
                except:
                    position_data['days_to_expiry'] = 0
            else:
                position_data['market_value'] = pos['position'] * pos['avgCost']
                
            positions_data.append(position_data)
        
        # 計算統計數據
        options_count = len([p for p in positions_data if p['sec_type'] == 'OPT'])
        stocks_count = len([p for p in positions_data if p['sec_type'] == 'STK'])
        total_market_value = sum(p.get('market_value', 0) for p in positions_data)
        
        # 按到期日計算期權價值
        options_by_expiry = {}
        for pos in positions_data:
            if pos['sec_type'] == 'OPT':
                expiry = pos['expiry']
                if expiry not in options_by_expiry:
                    options_by_expiry[expiry] = {
                        'expiry': expiry,
                        'expiry_formatted': pos['expiry_formatted'],
                        'days_to_expiry': pos['days_to_expiry'],
                        'total_value': 0,
                        'count': 0
                    }
                options_by_expiry[expiry]['total_value'] += pos['market_value']
                options_by_expiry[expiry]['count'] += 1
        
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
            'options_by_expiry': list(options_by_expiry.values()),
            'source': 'ib_api',
            'status': 'updated'
        }
        
        try:
            temp_file = CONFIG['DATA_FILE'] + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(portfolio_data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, CONFIG['DATA_FILE'])
            logger.info(f"Portfolio data saved to {CONFIG['DATA_FILE']}")
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
            logger.info("Starting portfolio update...")
            
            if ib_client:
                try:
                    ib_client.disconnect()
                except:
                    pass
                time.sleep(1)
            
            ib_client = IBPortfolioClient()
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
            
            ib_client.positions = []
            ib_client.update_complete.clear()
            
            logger.info("Requesting positions...")
            ib_client.reqPositions()
            
            if ib_client.update_complete.wait(timeout=10):
                logger.info("Update completed successfully")
                return jsonify({
                    "success": True,
                    "message": f"成功更新 {len(ib_client.positions)} 個持倉",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                logger.error("Update timeout - did not receive positionEnd")
                return jsonify({
                    "success": False,
                    "error": "Update timeout",
                    "message": "獲取持倉數據超時，請稍後再試"
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

def initial_tws_update():
    """啟動時嘗試連接 TWS 並更新數據"""
    global ib_client
    
    print("\n🔄 正在連接 TWS 並獲取持倉數據...")
    
    max_attempts = 5
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        print(f"\n📡 第 {attempt}/{max_attempts} 次嘗試連接...")
        
        with update_lock:
            try:
                if ib_client:
                    try:
                        ib_client.disconnect()
                    except:
                        pass
                    time.sleep(1)
                
                ib_client = IBPortfolioClient()
                ib_client.connection_ready.clear()
                ib_client.update_complete.clear()
                
                client_id = CONFIG['CLIENT_ID'] + attempt - 1
                print(f"   使用 Client ID: {client_id}")
                
                ib_client.connect(CONFIG['TWS_HOST'], CONFIG['TWS_PORT'], clientId=client_id)
                
                if not ib_client.connection_ready.wait(timeout=5):
                    print("   ❌ 連接超時 - 未收到 nextValidId")
                    print("   請檢查：")
                    print("   1. TWS 是否正在運行")
                    print("   2. API 設置是否啟用 (File → Global Configuration → API → Settings)")
                    print("   3. Socket port 是否為 7496")
                    if attempt < max_attempts:
                        print(f"   ⏳ 等待 3 秒後重試...")
                        time.sleep(3)
                    continue
                
                ib_client.positions = []
                ib_client.update_complete.clear()
                
                print("   📊 請求持倉數據...")
                ib_client.reqPositions()
                
                if ib_client.update_complete.wait(timeout=10):
                    print(f"   ✅ 成功獲取 {len(ib_client.positions)} 個持倉！")
                    return True
                else:
                    print("   ❌ 獲取數據超時")
                    if attempt < max_attempts:
                        print(f"   ⏳ 等待 3 秒後重試...")
                        time.sleep(3)
                    
            except Exception as e:
                print(f"   ❌ 連接錯誤: {e}")
                if attempt < max_attempts:
                    print(f"   ⏳ 等待 3 秒後重試...")
                    time.sleep(3)
    
    print("\n❌ 無法連接到 TWS，請檢查以下設置：")
    print("1. 確保 TWS 正在運行")
    print("2. 確保已啟用 API：File → Global Configuration → API → Settings")
    print("3. 確保 'Enable ActiveX and Socket Clients' 已勾選")
    print("4. 確保 Socket port 設置為 7496")
    print("5. 嘗試重啟 TWS")
    return False

def main():
    """主函數 - 啟動應用"""
    print("=" * 60)
    print("IB Portfolio Monitor - 倉位監控系統")
    print("=" * 60)
    print(f"📁 Working Directory: {os.getcwd()}")
    print(f"📊 Data File: {CONFIG['DATA_FILE']}")
    print(f"🔌 TWS Connection: {CONFIG['TWS_HOST']}:{CONFIG['TWS_PORT']}")
    print("=" * 60)
    
    # 先嘗試連接 TWS 並獲取數據
    success = initial_tws_update()
    
    if success:
        print("\n✅ TWS 連接成功！")
        print("=" * 60)
        print(f"🚀 正在啟動服務器...")
        print(f"🌐 請訪問: http://localhost:{CONFIG['SERVER_PORT']}")
        print("=" * 60)
        print("💡 按 Ctrl+C 停止服務器")
    else:
        print("\n⚠️  TWS 連接失敗，但服務器仍將啟動")
        print("🔧 您可以在網頁上點擊'更新持倉'按鈕重試")
        print("=" * 60)
        print(f"🚀 正在啟動服務器...")
        print(f"🌐 請訪問: http://localhost:{CONFIG['SERVER_PORT']}")
        print("=" * 60)
        print("💡 按 Ctrl+C 停止服務器")
    
    try:
        # 在後台線程中啟動 Flask
        server_thread = threading.Thread(
            target=lambda: app.run(
                host='0.0.0.0',
                port=CONFIG['SERVER_PORT'],
                debug=False,
                use_reloader=False
            ),
            daemon=True
        )
        server_thread.start()
        
        # 如果初始連接失敗，在後台持續嘗試
        if not success:
            print("\n🔄 在後台持續嘗試連接 TWS...")
            retry_count = 0
            while True:
                time.sleep(30)  # 每30秒重試一次
                retry_count += 1
                print(f"\n🔄 後台重試 #{retry_count}...")
                
                with update_lock:
                    try:
                        if ib_client:
                            try:
                                ib_client.disconnect()
                            except:
                                pass
                        
                        ib_client = IBPortfolioClient()
                        ib_client.connection_ready.clear()
                        ib_client.update_complete.clear()
                        
                        ib_client.connect(CONFIG['TWS_HOST'], CONFIG['TWS_PORT'], clientId=CONFIG['CLIENT_ID'])
                        
                        if ib_client.connection_ready.wait(timeout=5):
                            ib_client.positions = []
                            ib_client.update_complete.clear()
                            ib_client.reqPositions()
                            
                            if ib_client.update_complete.wait(timeout=10):
                                print(f"✅ 後台連接成功！獲取到 {len(ib_client.positions)} 個持倉")
                                break
                    except Exception as e:
                        print(f"❌ 後台連接失敗: {e}")
        
        # 保持主線程運行
        server_thread.join()
        
    except KeyboardInterrupt:
        print("\n🛑 服務器已停止")
        if ib_client and ib_client.isConnected():
            ib_client.disconnect()
    except Exception as e:
        logger.error(f"Server error: {e}")
        print(f"\n❌ 服務器錯誤: {e}")

if __name__ == "__main__":
    main()