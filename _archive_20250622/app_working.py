#!/usr/bin/env python3
"""
IB Portfolio Monitor - Working Version with Manual Fallback
IB 倉位監控系統 - 帶手動輸入備份的工作版本
"""

from flask import Flask, jsonify, send_file, render_template_string, request
import json
import os
import threading
import time
import logging
from pathlib import Path
from datetime import datetime

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
    'SERVER_PORT': 8080,
    'DATA_FILE': 'portfolio_data.json',
    'DASHBOARD_FILE': 'dashboard_simple.html'
}

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
    """API: 更新持倉數據"""
    try:
        # 嘗試從 IB API 獲取數據
        logger.info("Attempting to connect to TWS...")
        
        # 檢查是否有 ibapi 模塊
        try:
            from ibapi.client import EClient
            from ibapi.wrapper import EWrapper
            from ibapi.contract import Contract
            
            # 嘗試連接
            success = try_ib_connection()
            if success:
                return jsonify({
                    "success": True,
                    "message": "成功從 TWS 更新數據",
                    "timestamp": datetime.now().isoformat()
                })
        except ImportError:
            logger.warning("ibapi module not available")
        except Exception as e:
            logger.error(f"IB connection failed: {e}")
        
        # 如果 IB 連接失敗，返回錯誤但提供手動輸入選項
        return jsonify({
            "success": False,
            "error": "Cannot connect to TWS",
            "message": "無法連接到 TWS，請檢查 TWS 是否運行並已啟用 API",
            "manual_update_available": True
        }), 503
        
    except Exception as e:
        logger.error(f"Update error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "更新失敗"
        }), 500

@app.route('/api/manual_update', methods=['POST'])
def manual_update():
    """API: 手動更新持倉數據"""
    try:
        data = request.get_json()
        
        if not data or 'positions' not in data:
            return jsonify({
                "success": False,
                "error": "Invalid data",
                "message": "請提供持倉數據"
            }), 400
        
        # 處理手動輸入的數據
        positions = data['positions']
        positions_data = []
        
        for pos in positions:
            position_data = {
                'account': 'Manual',
                'symbol': pos.get('symbol', ''),
                'sec_type': pos.get('type', 'STK'),
                'position': float(pos.get('quantity', 0)),
                'avg_cost': float(pos.get('avgCost', 0)),
                'currency': 'USD',
                'exchange': 'SMART',
                'timestamp': datetime.now().isoformat(),
            }
            
            # 計算市值
            if position_data['sec_type'] == 'OPT':
                multiplier = 100
                position_data['market_value'] = abs(position_data['position'] * position_data['avg_cost'] * multiplier)
            else:
                position_data['market_value'] = abs(position_data['position'] * position_data['avg_cost'])
            
            position_data['unrealized_pnl'] = 0
            positions_data.append(position_data)
        
        # 計算統計
        options_count = len([p for p in positions_data if p['sec_type'] == 'OPT'])
        stocks_count = len([p for p in positions_data if p['sec_type'] in ['STK', 'CASH']])
        total_market_value = sum(p.get('market_value', 0) for p in positions_data)
        
        # 保存數據
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
                'net_liquidation': total_market_value,
                'day_change': 0,
                'day_change_percent': 0
            },
            'source': 'manual_input',
            'status': 'updated'
        }
        
        # 保存到文件
        with open(CONFIG['DATA_FILE'], 'w', encoding='utf-8') as f:
            json.dump(portfolio_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            "success": True,
            "message": f"成功手動更新 {len(positions_data)} 個持倉",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Manual update error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "手動更新失敗"
        }), 500

@app.route('/api/status')
def get_status():
    """API: 獲取系統狀態"""
    # 檢查數據文件
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
    
    # 檢查 TWS 連接（簡單檢查）
    tws_available = False
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 7496))
        sock.close()
        tws_available = (result == 0)
    except:
        pass
    
    return jsonify({
        "status": "running",
        "tws_available": tws_available,
        "has_data": has_data,
        "last_update": last_update,
        "data_source": source,
        "server_time": datetime.now().isoformat(),
        "manual_update_available": True
    })

def try_ib_connection():
    """嘗試 IB 連接（簡化版本）"""
    try:
        # 這裡應該是實際的 IB 連接代碼
        # 但由於連接問題，我們暫時返回 False
        return False
    except:
        return False

def main():
    """主函數 - 啟動應用"""
    print("=" * 60)
    print("IB Portfolio Monitor - 倉位監控系統")
    print("=" * 60)
    print(f"📁 Working Directory: {os.getcwd()}")
    print(f"📊 Data File: {CONFIG['DATA_FILE']}")
    print(f"🖥️  Dashboard: {CONFIG['DASHBOARD_FILE']}")
    print("=" * 60)
    print(f"🚀 Starting server on port {CONFIG['SERVER_PORT']}...")
    print(f"🌐 Access the dashboard at: http://localhost:{CONFIG['SERVER_PORT']}")
    print(f"📱 API endpoints:")
    print(f"   GET  /api/portfolio     - Get portfolio data")
    print(f"   POST /api/update        - Update via TWS (if available)")
    print(f"   POST /api/manual_update - Manual update")
    print(f"   GET  /api/status        - Get system status")
    print("=" * 60)
    print("⚠️  Note: TWS connection may not work. Manual update is available.")
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
    except Exception as e:
        logger.error(f"Server error: {e}")
        print(f"\n❌ Server error: {e}")

if __name__ == "__main__":
    main()