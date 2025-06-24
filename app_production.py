#!/usr/bin/env python3
"""
IB Portfolio Monitor - Production Version (No TWS Connection)
用於 Railway 部署的生產版本
"""

from flask import Flask, jsonify, send_from_directory, request
import json
import os
import logging
from pathlib import Path
from datetime import datetime
import requests
from dotenv import load_dotenv

# 加載環境變量
load_dotenv()

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
    'SERVER_PORT': int(os.environ.get('PORT', '8080')),
    'DATA_FILE': 'portfolio_data_enhanced.json',
    'FMP_API_KEY': os.environ.get('FMP_API_KEY', ''),
    'ENVIRONMENT': 'production'
}

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
    return send_from_directory('static', 'dashboard_new.html')

@app.route('/test')
def test_page():
    """測試頁面"""
    return send_from_directory('static', 'test_api_data.html')

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
    """API: 更新持倉數據（生產環境不支持）"""
    return jsonify({
        "success": False,
        "error": "Not available in production",
        "message": "Railway 環境無法連接到 TWS。請在本地環境更新數據後上傳。"
    }), 503

@app.route('/api/status')
def get_status():
    """API: 獲取系統狀態"""
    data_file = Path(CONFIG['DATA_FILE'])
    has_data = data_file.exists()
    last_update = None
    
    if has_data:
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                last_update = data.get('last_update')
        except:
            pass
    
    return jsonify({
        "status": "running",
        "environment": CONFIG['ENVIRONMENT'],
        "tws_connected": False,
        "has_data": has_data,
        "last_update": last_update,
        "source": "production",
        "message": "生產環境 - 使用靜態數據文件"
    })

# Railway 部署時會使用 gunicorn，開發時使用 Flask 內建服務器
if __name__ == "__main__":
    print("=" * 60)
    print("IB Portfolio Monitor - Production Version")
    print("=" * 60)
    print(f"🌍 Environment: {CONFIG['ENVIRONMENT']}")
    print(f"📊 Data File: {CONFIG['DATA_FILE']}")
    print(f"🚀 Starting server on port {CONFIG['SERVER_PORT']}...")
    print("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=CONFIG['SERVER_PORT'],
        debug=False
    )