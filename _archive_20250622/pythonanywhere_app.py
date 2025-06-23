#!/usr/bin/env python3
"""
PythonAnywhere Backend for IB Portfolio Monitor
IB 倉位監控系統 - PythonAnywhere 後端應用

部署說明：
1. 在 PythonAnywhere 創建新的 Web 應用
2. 上傳此文件作為主應用
3. 設置環境變量 API_SECRET_KEY
4. 配置 SQLite 數據庫
"""

from flask import Flask, jsonify, request, render_template_string
from datetime import datetime
import json
import sqlite3
import os
import hashlib
import hmac
from functools import wraps

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 配置
CONFIG = {
    'DATABASE': 'portfolio_data.db',
    'API_SECRET_KEY': os.environ.get('API_SECRET_KEY', 'your-secret-key-here'),
    'MAX_DATA_AGE_HOURS': 24  # 數據過期時間
}

# 初始化數據庫
def init_db():
    """初始化 SQLite 數據庫"""
    conn = sqlite3.connect(CONFIG['DATABASE'])
    cursor = conn.cursor()
    
    # 創建主數據表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            data TEXT NOT NULL,
            data_hash TEXT,
            source TEXT,
            upload_ip TEXT
        )
    ''')
    
    # 創建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON portfolio_data(timestamp)')
    
    conn.commit()
    conn.close()

# 初始化數據庫
init_db()

# API 認證裝飾器
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization header'}), 401
        
        token = auth_header.split(' ')[1]
        if token != CONFIG['API_SECRET_KEY']:
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

# 主頁
@app.route('/')
def index():
    """顯示系統狀態頁面"""
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>IB Portfolio Monitor - Cloud Backend</title>
        <meta charset="utf-8">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .status-card {
                background: white;
                border-radius: 8px;
                padding: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            .status-ok { color: #28a745; }
            .status-warning { color: #ffc107; }
            .status-error { color: #dc3545; }
            h1 { color: #333; }
            .timestamp { color: #666; font-size: 0.9em; }
            .api-endpoint {
                background: #f8f9fa;
                padding: 10px;
                border-radius: 4px;
                margin: 10px 0;
                font-family: monospace;
            }
        </style>
    </head>
    <body>
        <h1>IB Portfolio Monitor - Cloud Backend</h1>
        
        <div class="status-card">
            <h2>系統狀態</h2>
            <p>後端服務: <span class="status-ok">✓ 運行中</span></p>
            <p>當前時間: <span class="timestamp">{{ current_time }}</span></p>
            <p>最後數據更新: <span class="timestamp" id="last-update">檢查中...</span></p>
        </div>
        
        <div class="status-card">
            <h2>API 端點</h2>
            <div class="api-endpoint">GET /api/portfolio - 獲取最新倉位數據</div>
            <div class="api-endpoint">POST /api/portfolio - 更新倉位數據 (需要認證)</div>
            <div class="api-endpoint">GET /api/status - 獲取系統狀態</div>
            <div class="api-endpoint">GET /api/last_update - 獲取最後更新時間</div>
        </div>
        
        <script>
            // 獲取最後更新時間
            fetch('/api/last_update')
                .then(response => response.json())
                .then(data => {
                    const element = document.getElementById('last-update');
                    if (data.last_update) {
                        const date = new Date(data.last_update);
                        element.textContent = date.toLocaleString('zh-TW');
                        element.className = 'timestamp status-ok';
                    } else {
                        element.textContent = '無數據';
                        element.className = 'timestamp status-warning';
                    }
                })
                .catch(error => {
                    document.getElementById('last-update').textContent = '錯誤';
                });
        </script>
    </body>
    </html>
    '''
    
    return render_template_string(html_template, current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

# API: 獲取最新倉位數據
@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """獲取最新的倉位數據"""
    conn = sqlite3.connect(CONFIG['DATABASE'])
    cursor = conn.cursor()
    
    # 獲取最新的數據
    cursor.execute('''
        SELECT data, timestamp FROM portfolio_data 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''')
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({
            'error': 'No data available',
            'message': '尚無倉位數據'
        }), 404
    
    try:
        data = json.loads(row[0])
        data['retrieved_at'] = datetime.now().isoformat()
        data['data_timestamp'] = row[1]
        
        # 檢查數據新鮮度
        data_time = datetime.fromisoformat(row[1].replace(' ', 'T'))
        age_hours = (datetime.now() - data_time).total_seconds() / 3600
        data['data_age_hours'] = round(age_hours, 2)
        data['data_fresh'] = age_hours < CONFIG['MAX_DATA_AGE_HOURS']
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': 'Data parsing error', 'message': str(e)}), 500

# API: 更新倉位數據
@app.route('/api/portfolio', methods=['POST'])
@require_api_key
def update_portfolio():
    """更新倉位數據（需要認證）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # 計算數據哈希
        data_str = json.dumps(data, sort_keys=True)
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]
        
        # 存儲到數據庫
        conn = sqlite3.connect(CONFIG['DATABASE'])
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO portfolio_data (data, data_hash, source, upload_ip)
            VALUES (?, ?, ?, ?)
        ''', (
            data_str,
            data_hash,
            data.get('source', 'unknown'),
            request.remote_addr
        ))
        
        conn.commit()
        conn.close()
        
        # 清理舊數據（保留最近100條）
        cleanup_old_data()
        
        return jsonify({
            'success': True,
            'message': '數據更新成功',
            'data_hash': data_hash,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': 'Update failed',
            'message': str(e)
        }), 500

# API: 獲取系統狀態
@app.route('/api/status')
def get_status():
    """獲取系統狀態"""
    conn = sqlite3.connect(CONFIG['DATABASE'])
    cursor = conn.cursor()
    
    # 獲取記錄數
    cursor.execute('SELECT COUNT(*) FROM portfolio_data')
    record_count = cursor.fetchone()[0]
    
    # 獲取最後更新時間
    cursor.execute('SELECT timestamp FROM portfolio_data ORDER BY timestamp DESC LIMIT 1')
    last_update_row = cursor.fetchone()
    
    conn.close()
    
    status = {
        'status': 'running',
        'database': 'connected',
        'record_count': record_count,
        'last_update': last_update_row[0] if last_update_row else None,
        'server_time': datetime.now().isoformat(),
        'max_data_age_hours': CONFIG['MAX_DATA_AGE_HOURS']
    }
    
    return jsonify(status)

# API: 獲取最後更新時間
@app.route('/api/last_update')
def get_last_update():
    """獲取最後更新時間"""
    conn = sqlite3.connect(CONFIG['DATABASE'])
    cursor = conn.cursor()
    
    cursor.execute('SELECT timestamp FROM portfolio_data ORDER BY timestamp DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return jsonify({
            'last_update': row[0],
            'age_seconds': int((datetime.now() - datetime.fromisoformat(row[0].replace(' ', 'T'))).total_seconds())
        })
    else:
        return jsonify({'last_update': None})

# 清理舊數據
def cleanup_old_data():
    """保留最近的100條記錄"""
    conn = sqlite3.connect(CONFIG['DATABASE'])
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM portfolio_data 
        WHERE id NOT IN (
            SELECT id FROM portfolio_data 
            ORDER BY timestamp DESC 
            LIMIT 100
        )
    ''')
    
    conn.commit()
    conn.close()

# CORS 支持
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

if __name__ == '__main__':
    app.run(debug=True)