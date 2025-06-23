#!/usr/bin/env python3
"""
IB Portfolio Monitor - Main Application Server (Fixed Version)
IB 倉位監控系統 - 主應用服務器（修復版）
"""

from flask import Flask, jsonify, send_file, render_template_string
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
app.config['JSON_AS_ASCII'] = False  # 支持中文

# 應用配置
CONFIG = {
    'TWS_HOST': '127.0.0.1',
    'TWS_PORT': 7496,
    'CLIENT_ID': 999,
    'SERVER_PORT': 8080,
    'DATA_FILE': 'portfolio_data.json',
    'DASHBOARD_FILE': 'dashboard_simple.html'
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
        # 忽略信息性消息
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
            
            # 期權特定信息
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
            
        # 處理數據格式
        positions_data = []
        for pos in self.positions:
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
            
            # 期權數據處理
            if pos['secType'] == 'OPT':
                position_data.update({
                    'strike': pos['strike'],
                    'right': pos['right'],
                    'expiry': pos['expiry'],
                    'multiplier': pos['multiplier'],
                    'market_value': abs(pos['position'] * pos['avgCost'] * int(pos['multiplier'])),
                    'market_price': pos['avgCost'],
                    'expiry_formatted': f"{pos['expiry'][:4]}-{pos['expiry'][4:6]}-{pos['expiry'][6:8]}",
                    'option_type_name': '看漲期權' if pos['right'] == 'C' else '看跌期權',
                    'name': f"{pos['symbol']} {pos['expiry'][:4]}/{pos['expiry'][4:6]}/{pos['expiry'][6:8]} ${pos['strike']:.0f} {pos['right']}"
                })
                
                # 計算到期天數
                try:
                    from datetime import date
                    expiry_date = date(int(pos['expiry'][:4]), int(pos['expiry'][4:6]), int(pos['expiry'][6:8]))
                    position_data['days_to_expiry'] = (expiry_date - date.today()).days
                except:
                    position_data['days_to_expiry'] = 0
            else:
                # 股票數據處理
                position_data['name'] = f"{pos['symbol']} - {'股票' if pos['secType'] == 'STK' else pos['secType']}"
                position_data['market_value'] = abs(pos['position'] * pos['avgCost'])
                position_data['market_price'] = pos['avgCost']
                
            position_data['unrealized_pnl'] = 0  # 需要實時價格才能計算
            positions_data.append(position_data)
        
        # 計算統計數據
        options_count = len([p for p in positions_data if p['sec_type'] == 'OPT'])
        stocks_count = len([p for p in positions_data if p['sec_type'] in ['STK', 'CASH']])
        total_market_value = sum(p.get('market_value', 0) for p in positions_data if p['sec_type'] != 'CASH')
        
        # 組裝完整數據
        portfolio_data = {
            'timestamp': datetime.now().isoformat(),
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'positions': positions_data,
            'summary': {
                'total_positions': len(positions_data),
                'options_count': options_count,
                'stocks_count': stocks_count,
                'total_market_value': total_market_value,
                'total_unrealized_pnl': 0,
                'net_liquidation': total_market_value,  # 簡化處理
                'day_change': 0,
                'day_change_percent': 0
            },
            'source': 'ib_api',
            'status': 'updated'
        }
        
        # 保存到文件
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
        # 如果找不到文件，返回簡單的錯誤頁面
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error</title>
            <meta charset="UTF-8">
        </head>
        <body style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h1>找不到儀表板文件</h1>
            <p>請確保 {{ dashboard_file }} 存在</p>
        </body>
        </html>
        """, dashboard_file=CONFIG['DASHBOARD_FILE'])

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
            # 返回空數據
            return jsonify({
                "error": "No data available",
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_positions": 0,
                    "total_market_value": 0,
                    "total_unrealized_pnl": 0
                },
                "positions": []
            })
    except Exception as e:
        logger.error(f"Error reading portfolio data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/update', methods=['POST'])
def update_portfolio():
    """API: 手動更新持倉數據"""
    global ib_client
    
    with update_lock:
        try:
            logger.info("Starting portfolio update...")
            
            # 創建新的客戶端連接
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
            
            # 等待連接就緒
            if not ib_client.connection_ready.wait(timeout=5):
                logger.error("Connection timeout - did not receive nextValidId")
                return jsonify({
                    "success": False,
                    "error": "Connection timeout",
                    "message": "無法連接到 TWS，請確保 TWS 正在運行並已啟用 API"
                }), 503
            
            # 清空舊數據並請求新數據
            ib_client.positions = []
            ib_client.update_complete.clear()
            
            logger.info("Requesting positions...")
            ib_client.reqPositions()
            
            # 等待更新完成
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
    
    # 檢查數據文件
    data_file = Path(CONFIG['DATA_FILE'])
    has_data = data_file.exists()
    last_update = None
    
    if has_data:
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
                last_update = data.get('last_update')
        except:
            pass
    
    return jsonify({
        "status": "running",
        "tws_connected": tws_connected,
        "has_data": has_data,
        "last_update": last_update,
        "server_time": datetime.now().isoformat(),
        "config": {
            "tws_host": CONFIG['TWS_HOST'],
            "tws_port": CONFIG['TWS_PORT'],
            "client_id": CONFIG['CLIENT_ID']
        }
    })

@app.route('/health')
def health_check():
    """健康檢查端點"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

def main():
    """主函數 - 啟動應用"""
    print("=" * 60)
    print("IB Portfolio Monitor - 倉位監控系統 (Fixed)")
    print("=" * 60)
    print(f"📁 Working Directory: {os.getcwd()}")
    print(f"📊 Data File: {CONFIG['DATA_FILE']}")
    print(f"🖥️  Dashboard: {CONFIG['DASHBOARD_FILE']}")
    print(f"🔌 TWS Connection: {CONFIG['TWS_HOST']}:{CONFIG['TWS_PORT']}")
    print(f"🆔 Client ID: {CONFIG['CLIENT_ID']}")
    print("=" * 60)
    print(f"🚀 Starting server on port {CONFIG['SERVER_PORT']}...")
    print(f"🌐 Access the dashboard at: http://localhost:{CONFIG['SERVER_PORT']}")
    print(f"📱 API endpoints:")
    print(f"   GET  /api/portfolio - Get portfolio data")
    print(f"   POST /api/update    - Update portfolio data")
    print(f"   GET  /api/status    - Get system status")
    print("=" * 60)
    print("💡 Press Ctrl+C to stop the server")
    
    try:
        # 啟動 Flask 服務器
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