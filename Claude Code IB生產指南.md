# Claude Code IB生產指南

## 概述

本指南詳細介紹如何使用Claude Code開發基於Interactive Brokers (IB) TWS API的量化交易工具。基於實際生產環境中的IB Cloud項目經驗，提供完整的開發、部署和維護指南。

## 目錄

1. [IB TWS API基礎](#ib-tws-api基礎)
2. [開發環境設置](#開發環境設置)
3. [核心架構設計](#核心架構設計)
4. [TWS API集成實踐](#tws-api集成實踐)
5. [市場數據處理](#市場數據處理)
6. [賬戶和持倉管理](#賬戶和持倉管理)
7. [Web界面開發](#web界面開發)
8. [生產環境部署](#生產環境部署)
9. [監控和維護](#監控和維護)
10. [故障排除](#故障排除)
11. [最佳實踐](#最佳實踐)

---

## IB TWS API基礎

### API概述

Interactive Brokers TWS API是一個強大的接口，允許客戶自動化交易策略：

- **目標用戶**: 有經驗的專業開發者
- **功能**: 自動化TWS手動操作
- **限制**: 每秒最多50條消息（所有連接客戶端共享）
- **架構**: 基於TCP/IP的消息傳遞系統

### 系統要求

```
最低要求:
- TWS Build 952.x 或更高版本
- Python 3.11.0+ (推薦)
- 網絡連接到TWS或IB Gateway
- 紙交易賬戶（測試用）或實盤賬戶

推薦配置:
- Python 3.11+ 虛擬環境
- TWS或IB Gateway運行在本地或專用服務器
- 穩定的網絡連接
- 充足的內存（至少4GB）
```

### API架構核心組件

#### EClient和EWrapper模式
```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

class MyIBClient(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        # 初始化數據存儲
        
    def error(self, reqId, errorCode, errorString):
        # 錯誤處理
        
    def nextValidId(self, orderId):
        # 接收有效訂單ID
        
    def position(self, account, contract, position, avgCost):
        # 接收持倉數據
```

---

## 開發環境設置

### 1. Python環境準備

```bash
# 創建虛擬環境
python3.11 -m venv ib_env
source ib_env/bin/activate  # Linux/Mac
# 或 ib_env\Scripts\activate  # Windows

# 安裝IB API
pip install ibapi

# 安裝其他依賴
pip install flask pandas numpy requests python-dotenv
```

### 2. TWS/IB Gateway配置

```
TWS API設置:
1. 啟動TWS或IB Gateway
2. 進入 API → Settings → Enable ActiveX and Socket Clients
3. 設置Socket port (默認: 7496 for TWS, 4001 for Gateway)
4. 勾選 "Read-Only API"（生產環境推薦）
5. 設置Trusted IP addresses
6. Master API client ID設置
```

### 3. 項目結構

```
ib_quantool/
├── app.py                    # 主應用文件
├── config.py                 # 配置管理
├── ib_client.py             # IB API客戶端
├── models/
│   ├── portfolio.py         # 持倉模型
│   ├── market_data.py       # 市場數據模型
│   └── account.py           # 賬戶模型
├── static/
│   ├── css/                 # 樣式文件
│   ├── js/                  # JavaScript文件
│   └── dashboard.html       # 主界面
├── templates/               # 模板文件
├── utils/
│   ├── data_processor.py    # 數據處理工具
│   └── helpers.py           # 輔助函數
├── tests/                   # 測試文件
├── requirements.txt         # 依賴清單
├── .env                     # 環境變量
├── start.sh                 # 啟動腳本
└── README.md               # 項目說明
```

---

## 核心架構設計

### 多繼承適配器模式

基於IB Cloud項目的成功實踐，推薦使用多繼承模式結合EWrapper和EClient：

```python
class EnhancedIBClient(EWrapper, EClient):
    """增強版 IB API 客戶端"""
    
    def __init__(self):
        EClient.__init__(self, self)
        
        # 連接狀態管理
        self.connected = False
        self.account = None
        
        # 數據存儲
        self.positions = {}
        self.contracts = {}
        self.market_data = {}
        self.account_summary = {}
        
        # 線程同步
        self.connection_ready = threading.Event()
        self.update_complete = threading.Event()
        self.market_data_ready = threading.Event()
        
        # 請求ID管理
        self.req_id_counter = 1
        self.req_id_map = {}
        
        # 錯誤追蹤
        self.errors = []
        self.subscription_errors = {}
```

### 線程模型設計

```python
import threading
import time

class ApplicationManager:
    def __init__(self):
        self.ib_client = EnhancedIBClient()
        self.update_lock = threading.Lock()
        self.auto_update_thread = None
        self.stop_auto_update = threading.Event()
        
    def start_ib_connection(self):
        """啟動IB連接"""
        # 啟動API線程
        api_thread = threading.Thread(target=self.ib_client.run, daemon=True)
        api_thread.start()
        
        # 連接到TWS
        self.ib_client.connect('127.0.0.1', 7496, clientId=9999)
        
        # 等待連接建立
        if self.ib_client.connection_ready.wait(timeout=10):
            logger.info("TWS連接成功")
            return True
        else:
            logger.error("TWS連接超時")
            return False
    
    def start_auto_update(self, interval=300):
        """啟動自動更新線程"""
        def update_loop():
            while not self.stop_auto_update.is_set():
                if self.stop_auto_update.wait(interval):
                    break
                try:
                    self.update_portfolio_data()
                except Exception as e:
                    logger.error(f"自動更新錯誤: {e}")
        
        self.auto_update_thread = threading.Thread(target=update_loop, daemon=True)
        self.auto_update_thread.start()
```

### 請求ID管理系統

```python
def nextReqId(self):
    """生成下一個請求ID"""
    req_id = self.req_id_counter
    self.req_id_counter += 1
    return req_id

def map_request(self, req_id, symbol, request_type):
    """映射請求ID到符號"""
    self.req_id_map[req_id] = {
        'symbol': symbol,
        'type': request_type,
        'timestamp': time.time()
    }

def get_symbol_from_reqid(self, req_id):
    """從請求ID獲取符號"""
    return self.req_id_map.get(req_id, {}).get('symbol')
```

---

## TWS API集成實踐

### 1. 連接管理

```python
def connectAck(self):
    """連接確認回調"""
    logger.info("Connected to TWS")
    self.connected = True
    
    # 啟動API消息循環
    api_thread = threading.Thread(target=self.run, daemon=True)
    api_thread.start()

def nextValidId(self, orderId: int):
    """接收有效訂單ID"""
    logger.info(f"Next Valid Order ID: {orderId}")
    self.connection_ready.set()

def connectionClosed(self):
    """連接關閉回調"""
    logger.warning("TWS connection closed")
    self.connected = False
    self.connection_ready.clear()
```

### 2. 錯誤處理策略

```python
def error(self, reqId, errorCode, errorString):
    """統一錯誤處理"""
    
    # 忽略的信息性錯誤
    info_codes = {2103, 2105, 2106, 2158}
    if errorCode in info_codes:
        return
    
    # 預期的市場數據錯誤
    expected_errors = {162, 200, 354, 10090}
    if errorCode in expected_errors:
        symbol = self.get_symbol_from_reqid(reqId)
        if symbol:
            self.subscription_errors[symbol] = {
                'error_code': errorCode,
                'message': '需要付費訂閱市場數據',
                'error_string': errorString
            }
        logger.warning(f"Expected error {errorCode}: {errorString} (reqId: {reqId})")
        return
    
    # 記錄真正的錯誤
    error_info = {
        'reqId': reqId,
        'errorCode': errorCode,
        'errorString': errorString,
        'timestamp': datetime.now().isoformat(),
        'symbol': self.get_symbol_from_reqid(reqId),
        'level': 'error'
    }
    self.errors.append(error_info)
    logger.error(f"IB API Error {errorCode}: {errorString} (reqId: {reqId})")
```

### 3. 賬戶管理

```python
def managedAccounts(self, accountsList: str):
    """處理託管賬戶列表"""
    accounts = [acc.strip() for acc in accountsList.split(',') if acc.strip()]
    
    # 優先使用環境變量指定的目標賬戶
    target_account = CONFIG.get('TARGET_ACCOUNT')
    if target_account and target_account in accounts:
        self.account = target_account
        logger.info(f"Using target account: {target_account[:2]}******")
    elif accounts:
        self.account = accounts[0]
        logger.info(f"Using first available account: {self.account[:2]}******")
    else:
        logger.warning(f"No valid accounts found")
```

---

## 市場數據處理

### 1. 市場數據訂閱

```python
def subscribe_market_data(self, contract, symbol):
    """訂閱市場數據"""
    req_id = self.nextReqId()
    self.map_request(req_id, symbol, 'market_data')
    
    # 訂閱實時數據，包括期權Greeks
    generic_tick_list = "233"  # 包括RTVolume和期權計算
    self.reqMktData(req_id, contract, generic_tick_list, False, False, [])
    
    logger.info(f"Subscribing to market data: {symbol} (reqId: {req_id})")

def tickPrice(self, reqId, tickType, price, attrib):
    """處理價格tick數據"""
    symbol = self.get_symbol_from_reqid(reqId)
    if not symbol:
        return
    
    if symbol not in self.market_data:
        self.market_data[symbol] = {}
    
    # 映射tick類型到字段名
    tick_map = {
        1: 'bid',           # BID
        2: 'ask',           # ASK  
        4: 'last',          # LAST
        6: 'high',          # HIGH
        7: 'low',           # LOW
        9: 'close',         # CLOSE
        14: 'open',         # OPEN
        15: 'low_13_week',  # LOW_13_WEEK
        16: 'high_13_week', # HIGH_13_WEEK
        17: 'low_26_week',  # LOW_26_WEEK
        18: 'high_26_week', # HIGH_26_WEEK
        19: 'low_52_week',  # LOW_52_WEEK
        20: 'high_52_week', # HIGH_52_WEEK
        21: 'avg_volume'    # AVG_VOLUME
    }
    
    if tickType in tick_map:
        field_name = tick_map[tickType]
        self.market_data[symbol][field_name] = price
        
        # 更新當前價格
        if tickType in [1, 2, 4]:  # bid, ask, last
            self.market_data[symbol]['currentPrice'] = price
            
        logger.debug(f"Price Update - {symbol} {field_name}: {price}")

def tickOptionComputation(self, reqId, tickType, impliedVol, delta, optPrice, pvDividend, 
                         gamma, vega, theta, undPrice):
    """處理期權Greeks數據"""
    symbol = self.get_symbol_from_reqid(reqId)
    if not symbol:
        return
    
    if symbol not in self.market_data:
        self.market_data[symbol] = {}
    
    # 期權Greeks映射
    greeks_map = {
        10: 'bidGreeks',      # BID_OPTION_COMPUTATION
        11: 'askGreeks',      # ASK_OPTION_COMPUTATION
        12: 'lastGreeks',     # LAST_OPTION_COMPUTATION
        13: 'modelGreeks'     # MODEL_OPTION_COMPUTATION
    }
    
    if tickType in greeks_map:
        greeks_type = greeks_map[tickType]
        
        greeks_data = {
            'impliedVolatility': impliedVol if impliedVol != -1 else None,
            'delta': delta if delta != -2 else None,
            'optionPrice': optPrice if optPrice != -1 else None,
            'pvDividend': pvDividend if pvDividend != -1 else None,
            'gamma': gamma if gamma != -2 else None,
            'vega': vega if vega != -2 else None,
            'theta': theta if theta != -2 else None,
            'underlyingPrice': undPrice if undPrice != -1 else None
        }
        
        if 'options_data' not in self.market_data[symbol]:
            self.market_data[symbol]['options_data'] = {}
            
        self.market_data[symbol]['options_data'][greeks_type] = greeks_data
        
        logger.debug(f"Greeks Update - {symbol}: Delta={delta}, Gamma={gamma}, "
                    f"Theta={theta}, Vega={vega}")
```

### 2. 歷史數據處理

```python
def request_historical_data(self, contract, symbol, duration="5 D", bar_size="1 day"):
    """請求歷史數據"""
    req_id = self.nextReqId()
    self.map_request(req_id, symbol, 'historical_data')
    
    self.reqHistoricalData(
        req_id, contract, "", duration, bar_size, 
        "MIDPOINT", 1, 1, False, []
    )
    
    logger.info(f"Requesting historical data: {symbol}")

def historicalData(self, reqId, bar):
    """處理歷史數據"""
    symbol = self.get_symbol_from_reqid(reqId)
    if not symbol:
        return
    
    if symbol not in self.market_data:
        self.market_data[symbol] = {}
    
    # 存儲最近的收盤價
    if bar.close > 0:
        self.market_data[symbol]['historical_close'] = bar.close
        
    logger.debug(f"Historical data - {symbol}: {bar.date} Close: {bar.close}")
```

---

## 賬戶和持倉管理

### 1. 持倉數據處理

```python
def position(self, account: str, contract: Contract, position: float, avgCost: float):
    """接收持倉數據"""
    # 只處理目標賬戶的持倉
    if self.account and account != self.account:
        return
        
    if position != 0:
        symbol = contract.symbol
        
        # 期權需要完整標識符
        if contract.secType == 'OPT':
            symbol = f"{contract.symbol}_{contract.lastTradeDateOrContractMonth}_{contract.right}_{contract.strike}"
        
        # 存儲完整的contract對象
        self.contracts[symbol] = contract
        
        # 存儲持倉信息
        position_data = {
            'account': account,
            'symbol': contract.symbol,
            'secType': contract.secType,
            'position': position,
            'avgCost': avgCost,
            'currency': contract.currency or 'USD',
            'exchange': contract.exchange or 'SMART',
            'conId': contract.conId,
            'localSymbol': contract.localSymbol,
            'tradingClass': contract.tradingClass
        }
        
        # 期權特定信息
        if contract.secType == 'OPT':
            position_data.update({
                'strike': contract.strike,
                'right': contract.right,
                'expiry': contract.lastTradeDateOrContractMonth,
                'multiplier': contract.multiplier or '100'
            })
            
            # 設置正確的交易所
            if contract.currency == "HKD":
                contract.exchange = "HKFE"
            else:
                contract.exchange = "SMART"
        
        self.positions[symbol] = position_data
        logger.info(f"Received position: {symbol} {position}")

def positionEnd(self):
    """持倉數據接收完成"""
    logger.info(f"Received {len(self.positions)} positions")
    # 觸發額外數據請求
    self.requestAdditionalData()
```

### 2. 賬戶摘要處理

```python
def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
    """處理賬戶摘要數據"""
    if account not in self.account_summary:
        self.account_summary[account] = {}
    
    self.account_summary[account][tag] = {
        'value': value,
        'currency': currency,
        'account': account
    }
    
    logger.debug(f"Account Summary - {account} {tag}: {value} {currency}")

def accountSummaryEnd(self, reqId: int):
    """賬戶摘要接收完成"""
    logger.info("Account summary data received")
```

### 3. PnL數據處理

```python
def pnl(self, reqId: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float):
    """處理賬戶級別PnL數據"""
    self.account_pnl = {
        'daily_pnl': dailyPnL,
        'unrealized_pnl': unrealizedPnL,
        'realized_pnl': realizedPnL,
        'timestamp': datetime.now().isoformat()
    }
    
    logger.debug(f"Account PnL - Daily: {dailyPnL}, Unrealized: {unrealizedPnL}, "
                f"Realized: {realizedPnL}")

def pnlSingle(self, reqId: int, pos: int, dailyPnL: float, unrealizedPnL: float, 
              realizedPnL: float, value: float):
    """處理單個持倉PnL數據"""
    symbol = self.get_symbol_from_reqid(reqId)
    if not symbol or symbol not in self.positions:
        return
    
    self.positions[symbol].update({
        'pnl': unrealizedPnL,
        'daily_pnl': dailyPnL,
        'realized_pnl': realizedPnL,
        'market_value': value,
        'has_pnl_data': True
    })
    
    logger.debug(f"Position PnL - {symbol}: Unrealized={unrealizedPnL}, "
                f"Daily={dailyPnL}, Market Value={value}")
```

---

## Web界面開發

### 1. Flask應用架構

```python
from flask import Flask, jsonify, render_template, request
import json
from datetime import datetime

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 全局變量
ib_client = None
update_lock = threading.Lock()

@app.route('/')
def index():
    """主儀表板頁面"""
    dashboard_path = Path('dashboard.html')
    if dashboard_path.exists():
        return send_file(dashboard_path)
    else:
        return "Dashboard file not found", 404

@app.route('/api/portfolio')
def get_portfolio():
    """獲取持倉數據API"""
    try:
        with open('portfolio_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        logger.error(f"獲取持倉數據錯誤: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/update', methods=['POST'])
def update_portfolio():
    """手動更新持倉數據"""
    global ib_client
    
    with update_lock:
        try:
            if ib_client and ib_client.connected:
                ib_client.update_portfolio_data()
                return jsonify({'status': 'success', 'message': '數據更新成功'})
            else:
                return jsonify({'status': 'error', 'message': 'TWS未連接'}), 503
        except Exception as e:
            logger.error(f"更新數據錯誤: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/status')
def get_status():
    """獲取系統狀態"""
    status = {
        'tws_connected': ib_client.connected if ib_client else False,
        'last_update': None,
        'positions_count': len(ib_client.positions) if ib_client else 0,
        'server_time': datetime.now().isoformat()
    }
    
    try:
        with open('portfolio_data.json', 'r') as f:
            data = json.load(f)
            status['last_update'] = data.get('last_update')
    except:
        pass
    
    return jsonify(status)
```

### 2. 前端JavaScript開發

```javascript
class IBDashboard {
    constructor() {
        this.updateInterval = 30000; // 30秒更新一次
        this.isUpdating = false;
        this.lastUpdateTime = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.startAutoUpdate();
        this.updateDashboard();
    }
    
    setupEventListeners() {
        // 手動更新按鈕
        document.getElementById('updateButton').addEventListener('click', () => {
            this.manualUpdate();
        });
        
        // 標籤切換
        document.querySelectorAll('.position-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });
    }
    
    async updateDashboard() {
        if (this.isUpdating) return;
        
        this.isUpdating = true;
        this.showLoading(true);
        
        try {
            const response = await fetch('/api/portfolio');
            const data = await response.json();
            
            if (response.ok) {
                this.renderPortfolioData(data);
                this.updateStatusInfo(data);
                this.lastUpdateTime = new Date();
            } else {
                this.showError('獲取數據失敗: ' + data.error);
            }
        } catch (error) {
            this.showError('網絡錯誤: ' + error.message);
        } finally {
            this.isUpdating = false;
            this.showLoading(false);
        }
    }
    
    renderPortfolioData(data) {
        // 更新賬戶摘要
        this.updateAccountSummary(data.summary);
        
        // 更新持倉表格
        this.updatePositionsTable(data.positions);
        
        // 更新圖表
        this.updateCharts(data);
    }
    
    updatePositionsTable(positions) {
        const usOptions = positions.filter(p => p.secType === 'OPT' && p.currency === 'USD');
        const hkOptions = positions.filter(p => p.secType === 'OPT' && p.currency === 'HKD');
        const stocks = positions.filter(p => p.secType === 'STK');
        
        this.renderOptionsTable('us-options-table', usOptions);
        this.renderOptionsTable('hk-options-table', hkOptions);
        this.renderStocksTable('stocks-table', stocks);
    }
    
    renderOptionsTable(tableId, positions) {
        const table = document.getElementById(tableId);
        const tbody = table.querySelector('tbody');
        
        tbody.innerHTML = '';
        
        positions.forEach(position => {
            const row = document.createElement('tr');
            
            // 添加狀態類別
            if (position.pnl > 0) {
                row.classList.add('profit');
            } else if (position.pnl < 0) {
                row.classList.add('loss');
            }
            
            row.innerHTML = `
                <td>${position.symbol}</td>
                <td>${position.strike}</td>
                <td>${position.right}</td>
                <td>${position.expiry_formatted}</td>
                <td>${position.position}</td>
                <td>${this.formatCurrency(position.avg_cost)}</td>
                <td class="${position.has_market_data ? 'has-data' : 'no-data'}">
                    ${this.formatCurrency(position.current_price)}
                </td>
                <td>${this.formatCurrency(position.market_value)}</td>
                <td class="${position.pnl >= 0 ? 'profit' : 'loss'}">
                    ${this.formatCurrency(position.pnl)}
                </td>
                <td>${position.days_to_expiry}</td>
                <td>${this.formatPercent(position.distance_percent)}</td>
            `;
            
            tbody.appendChild(row);
        });
    }
    
    async manualUpdate() {
        try {
            const response = await fetch('/api/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess('數據更新成功');
                // 延遲一秒後更新界面，確保數據已保存
                setTimeout(() => this.updateDashboard(), 1000);
            } else {
                this.showError('更新失敗: ' + result.message);
            }
        } catch (error) {
            this.showError('更新錯誤: ' + error.message);
        }
    }
    
    formatCurrency(value, currency = 'USD') {
        if (value === null || value === undefined) return 'N/A';
        
        const formatter = new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 2
        });
        
        return formatter.format(value);
    }
    
    formatPercent(value) {
        if (value === null || value === undefined) return 'N/A';
        return `${value.toFixed(2)}%`;
    }
    
    startAutoUpdate() {
        setInterval(() => {
            if (!this.isUpdating) {
                this.updateDashboard();
            }
        }, this.updateInterval);
    }
}

// 初始化儀表板
document.addEventListener('DOMContentLoaded', () => {
    new IBDashboard();
});
```

### 3. 響應式CSS設計

```css
/* 主佈局 */
.dashboard-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 1rem;
}

/* 賬戶摘要卡片 */
.account-summary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 1rem;
    padding: 2rem;
    color: white;
    margin-bottom: 2rem;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
}

.summary-item {
    text-align: center;
}

.summary-label {
    font-size: 0.875rem;
    opacity: 0.8;
    margin-bottom: 0.5rem;
}

.summary-value {
    font-size: 1.5rem;
    font-weight: 600;
}

/* 持倉表格 */
.positions-container {
    background: white;
    border-radius: 1rem;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    overflow: hidden;
}

.tab-navigation {
    display: flex;
    background: #f8f9fa;
    border-bottom: 1px solid #dee2e6;
}

.position-tab {
    flex: 1;
    padding: 1rem;
    background: none;
    border: none;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.2s;
}

.position-tab.active {
    background: white;
    border-bottom: 2px solid #007bff;
    color: #007bff;
}

.table-container {
    overflow-x: auto;
    max-height: 600px;
}

.positions-table {
    width: 100%;
    border-collapse: collapse;
}

.positions-table th {
    background: #f8f9fa;
    padding: 0.75rem;
    text-align: left;
    font-weight: 600;
    border-bottom: 2px solid #dee2e6;
    position: sticky;
    top: 0;
    z-index: 10;
}

.positions-table td {
    padding: 0.75rem;
    border-bottom: 1px solid #dee2e6;
}

/* 狀態指示器 */
.profit {
    color: #28a745;
}

.loss {
    color: #dc3545;
}

.has-data {
    background-color: rgba(40, 167, 69, 0.1);
}

.no-data {
    background-color: rgba(220, 53, 69, 0.1);
    font-style: italic;
}

/* 響應式設計 */
@media (max-width: 768px) {
    .dashboard-container {
        padding: 0.5rem;
    }
    
    .summary-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    
    .positions-table {
        font-size: 0.875rem;
    }
    
    .positions-table th,
    .positions-table td {
        padding: 0.5rem;
    }
}

/* 載入動畫 */
.loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.loading-spinner {
    width: 50px;
    height: 50px;
    border: 3px solid rgba(255, 255, 255, 0.3);
    border-top: 3px solid white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
```

---

## 生產環境部署

### 1. 系統配置

```bash
# Ubuntu/Debian服務器配置
sudo apt update
sudo apt install python3.11 python3.11-venv nginx supervisor redis-server

# 創建應用目錄
sudo mkdir -p /opt/ib_quantool
sudo chown $USER:$USER /opt/ib_quantool

# 克隆項目
cd /opt/ib_quantool
git clone <your-repo-url> .

# 設置虛擬環境
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 環境變量配置

```bash
# .env文件
TWS_HOST=127.0.0.1
TWS_PORT=7496
CLIENT_ID=9999
TARGET_ACCOUNT=U1234567

# Flask配置
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
PORT=8080

# 外部API
FMP_API_KEY=your-fmp-api-key

# 監控配置
LOG_LEVEL=INFO
AUTO_UPDATE_INTERVAL=300

# 安全配置
ALLOWED_HOSTS=your-domain.com,127.0.0.1
```

### 3. Supervisor配置

```ini
# /etc/supervisor/conf.d/ib_quantool.conf
[program:ib_quantool]
command=/opt/ib_quantool/venv/bin/python app.py
directory=/opt/ib_quantool
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/ib_quantool.log
environment=PATH="/opt/ib_quantool/venv/bin"

[program:ib_gateway]
command=/opt/ibc/IBCLinux-3.8.2/scripts/ibcstart.sh
directory=/opt/ibc/IBCLinux-3.8.2
user=ib
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/ib_gateway.log
```

### 4. Nginx反向代理

```nginx
# /etc/nginx/sites-available/ib_quantool
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # 靜態文件
    location /static/ {
        alias /opt/ib_quantool/static/;
        expires 1d;
    }
    
    # 安全頭
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
}
```

### 5. SSL配置

```bash
# 使用Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com

# 自動續期
sudo crontab -e
# 添加：0 2 * * * /usr/bin/certbot renew --quiet
```

---

## 監控和維護

### 1. 日誌管理

```python
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    """設置日誌配置"""
    
    # 創建logs目錄
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # 設置日誌格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 應用日誌
    app_handler = RotatingFileHandler(
        'logs/app.log', 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    app_handler.setFormatter(formatter)
    app_handler.setLevel(logging.INFO)
    
    # IB API日誌
    ib_handler = RotatingFileHandler(
        'logs/ib_api.log',
        maxBytes=10*1024*1024,
        backupCount=5
    )
    ib_handler.setFormatter(formatter)
    ib_handler.setLevel(logging.DEBUG)
    
    # 錯誤日誌
    error_handler = RotatingFileHandler(
        'logs/error.log',
        maxBytes=10*1024*1024,
        backupCount=10
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    
    # 配置logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(app_handler)
    logger.addHandler(error_handler)
    
    # IB API特定logger
    ib_logger = logging.getLogger('ibapi')
    ib_logger.addHandler(ib_handler)
    ib_logger.setLevel(logging.INFO)
    
    return logger
```

### 2. 健康檢查

```python
@app.route('/health')
def health_check():
    """健康檢查端點"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'checks': {}
    }
    
    # TWS連接檢查
    if ib_client and ib_client.connected:
        health_status['checks']['tws_connection'] = 'OK'
    else:
        health_status['checks']['tws_connection'] = 'FAILED'
        health_status['status'] = 'unhealthy'
    
    # 數據文件檢查
    data_file = Path('portfolio_data.json')
    if data_file.exists():
        # 檢查文件是否太舊
        file_age = time.time() - data_file.stat().st_mtime
        if file_age < 3600:  # 1小時內
            health_status['checks']['data_freshness'] = 'OK'
        else:
            health_status['checks']['data_freshness'] = 'STALE'
            health_status['status'] = 'degraded'
    else:
        health_status['checks']['data_file'] = 'MISSING'
        health_status['status'] = 'unhealthy'
    
    # 內存使用檢查
    import psutil
    memory_percent = psutil.virtual_memory().percent
    if memory_percent < 80:
        health_status['checks']['memory_usage'] = 'OK'
    else:
        health_status['checks']['memory_usage'] = 'HIGH'
        health_status['status'] = 'degraded'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code
```

### 3. 性能監控

```python
import time
import psutil
from functools import wraps

def monitor_performance(func):
    """性能監控裝飾器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss
        
        try:
            result = func(*args, **kwargs)
            status = 'success'
            error = None
        except Exception as e:
            result = None
            status = 'error'
            error = str(e)
            raise
        finally:
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss
            
            # 記錄性能數據
            performance_data = {
                'function': func.__name__,
                'execution_time': end_time - start_time,
                'memory_delta': end_memory - start_memory,
                'status': status,
                'error': error,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Performance: {json.dumps(performance_data)}")
        
        return result
    return wrapper

# 使用示例
@monitor_performance
def update_portfolio_data():
    """更新持倉數據"""
    # 實際更新邏輯
    pass
```

### 4. 警報系統

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class AlertManager:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.alert_recipients = os.getenv('ALERT_RECIPIENTS', '').split(',')
        
    def send_alert(self, subject, message, alert_level='WARNING'):
        """發送警報郵件"""
        if not all([self.smtp_server, self.smtp_username, self.smtp_password]):
            logger.warning("SMTP配置不完整，無法發送郵件警報")
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = ', '.join(self.alert_recipients)
            msg['Subject'] = f"[{alert_level}] IB量化工具警報: {subject}"
            
            body = f"""
            警報級別: {alert_level}
            時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            主題: {subject}
            
            詳細信息:
            {message}
            
            ---
            IB量化工具監控系統
            """
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            text = msg.as_string()
            server.sendmail(self.smtp_username, self.alert_recipients, text)
            server.quit()
            
            logger.info(f"警報郵件已發送: {subject}")
            
        except Exception as e:
            logger.error(f"發送警報郵件失敗: {e}")

# 使用示例
alert_manager = AlertManager()

def check_connection_health():
    """檢查連接健康狀態"""
    if not ib_client or not ib_client.connected:
        alert_manager.send_alert(
            "TWS連接斷開",
            "IB TWS API連接已斷開，請檢查TWS狀態和網絡連接。",
            "CRITICAL"
        )
```

---

## 故障排除

### 1. 常見連接問題

#### TWS連接失敗
```python
def diagnose_connection_issues():
    """診斷連接問題"""
    issues = []
    
    # 檢查TWS是否運行
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 7496))
        sock.close()
        
        if result != 0:
            issues.append("TWS未運行或端口7496未開放")
    except Exception as e:
        issues.append(f"網絡檢查失敗: {e}")
    
    # 檢查Client ID衝突
    if hasattr(ib_client, 'last_error') and '326' in str(ib_client.last_error):
        issues.append("Client ID衝突，請更改CLIENT_ID配置")
    
    # 檢查API設置
    issues.append("請確認TWS中已啟用API：API → Settings → Enable ActiveX and Socket Clients")
    
    return issues
```

#### 市場數據訂閱錯誤
```python
def handle_market_data_errors():
    """處理市場數據錯誤"""
    
    error_solutions = {
        162: "需要BATS市場數據訂閱，請聯繫IB或使用延遲數據",
        200: "證券定義未找到，請檢查合約參數",
        354: "需要付費市場數據訂閱",
        10090: "需要付費期權數據訂閱"
    }
    
    for symbol, error_info in ib_client.subscription_errors.items():
        error_code = error_info.get('error_code')
        solution = error_solutions.get(error_code, "未知錯誤，請查看IB文檔")
        
        logger.warning(f"市場數據錯誤 {symbol}: {error_code} - {solution}")
```

### 2. 性能優化

#### 減少API調用頻率
```python
class RateLimiter:
    def __init__(self, max_calls=50, time_window=1.0):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    def wait_if_needed(self):
        """如果需要，等待以避免超過速率限制"""
        now = time.time()
        
        # 清理舊的調用記錄
        self.calls = [call_time for call_time in self.calls 
                     if now - call_time < self.time_window]
        
        # 如果達到限制，等待
        if len(self.calls) >= self.max_calls:
            sleep_time = self.time_window - (now - self.calls[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
                self.calls = []
        
        self.calls.append(now)

# 使用示例
rate_limiter = RateLimiter()

def subscribe_market_data_with_limit(contract, symbol):
    """帶速率限制的市場數據訂閱"""
    rate_limiter.wait_if_needed()
    ib_client.subscribe_market_data(contract, symbol)
```

#### 內存管理
```python
def cleanup_old_data():
    """清理舊數據以釋放內存"""
    current_time = time.time()
    
    # 清理舊的請求映射（保留1小時）
    old_requests = [req_id for req_id, info in ib_client.req_id_map.items()
                   if current_time - info.get('timestamp', 0) > 3600]
    
    for req_id in old_requests:
        del ib_client.req_id_map[req_id]
    
    # 清理舊的錯誤記錄（保留24小時）
    ib_client.errors = [error for error in ib_client.errors
                       if current_time - datetime.fromisoformat(error['timestamp']).timestamp() < 86400]
    
    logger.info(f"清理了 {len(old_requests)} 個舊請求和錯誤記錄")
```

### 3. 數據一致性檢查

```python
def validate_position_data():
    """驗證持倉數據的一致性"""
    issues = []
    
    for symbol, position in ib_client.positions.items():
        # 檢查必需字段
        required_fields = ['symbol', 'secType', 'position', 'avgCost']
        missing_fields = [field for field in required_fields if field not in position]
        if missing_fields:
            issues.append(f"{symbol}: 缺少字段 {missing_fields}")
        
        # 檢查數據合理性
        if position.get('position') == 0:
            issues.append(f"{symbol}: 持倉為0但仍在列表中")
        
        if position.get('avgCost', 0) < 0:
            issues.append(f"{symbol}: 平均成本為負數")
        
        # 檢查期權數據
        if position.get('secType') == 'OPT':
            if not position.get('strike') or not position.get('expiry'):
                issues.append(f"{symbol}: 期權缺少執行價或到期日")
    
    if issues:
        logger.warning(f"發現 {len(issues)} 個數據問題: {issues}")
    
    return issues
```

---

## 最佳實踐

### 1. 安全實踐

#### API密鑰管理
```python
import os
from cryptography.fernet import Fernet

class SecureConfig:
    def __init__(self):
        self.cipher_suite = None
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """初始化加密"""
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            # 生成新密鑰（僅在首次運行時）
            key = Fernet.generate_key()
            print(f"請將此加密密鑰設置為環境變量 ENCRYPTION_KEY: {key.decode()}")
        else:
            key = key.encode()
        
        self.cipher_suite = Fernet(key)
    
    def encrypt_sensitive_data(self, data):
        """加密敏感數據"""
        return self.cipher_suite.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data):
        """解密敏感數據"""
        return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
    
    def get_secure_config(self, key, default=None):
        """獲取加密配置"""
        encrypted_value = os.getenv(f"ENCRYPTED_{key}")
        if encrypted_value:
            return self.decrypt_sensitive_data(encrypted_value)
        return os.getenv(key, default)
```

#### 賬戶信息保護
```python
def mask_sensitive_info(data):
    """遮蔽敏感信息"""
    if isinstance(data, dict):
        masked_data = {}
        for key, value in data.items():
            if key.lower() in ['account', 'accountid', 'account_number']:
                if isinstance(value, str) and len(value) > 4:
                    masked_data[key] = value[:2] + '*' * (len(value) - 4) + value[-2:]
                else:
                    masked_data[key] = '*' * len(str(value))
            else:
                masked_data[key] = mask_sensitive_info(value)
        return masked_data
    elif isinstance(data, list):
        return [mask_sensitive_info(item) for item in data]
    else:
        return data
```

### 2. 代碼組織

#### 模塊化設計
```python
# models/position.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Position:
    symbol: str
    sec_type: str
    position: float
    avg_cost: float
    currency: str = 'USD'
    exchange: str = 'SMART'
    
    # 期權特定字段
    strike: Optional[float] = None
    right: Optional[str] = None
    expiry: Optional[str] = None
    
    # 市場數據字段
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    pnl: Optional[float] = None
    
    # 元數據
    has_market_data: bool = False
    has_pnl_data: bool = False
    last_updated: Optional[datetime] = None
    
    def calculate_market_value(self):
        """計算市場價值"""
        if self.current_price and self.position:
            multiplier = 100 if self.sec_type == 'OPT' else 1
            self.market_value = self.position * self.current_price * multiplier
        return self.market_value
    
    def calculate_pnl(self):
        """計算盈虧"""
        if self.market_value and self.avg_cost:
            multiplier = 100 if self.sec_type == 'OPT' else 1
            cost = self.position * self.avg_cost * multiplier
            self.pnl = self.market_value - cost
        return self.pnl
```

#### 配置管理
```python
# config.py
import os
from typing import Dict, Any
from pathlib import Path

class Config:
    """配置管理類"""
    
    def __init__(self):
        self.load_config()
    
    def load_config(self):
        """載入配置"""
        self.TWS_HOST = os.getenv('TWS_HOST', '127.0.0.1')
        self.TWS_PORT = int(os.getenv('TWS_PORT', 7496))
        self.CLIENT_ID = int(os.getenv('CLIENT_ID', 9999))
        self.TARGET_ACCOUNT = os.getenv('TARGET_ACCOUNT')
        
        self.SERVER_PORT = int(os.getenv('PORT', 8080))
        self.AUTO_UPDATE_INTERVAL = int(os.getenv('AUTO_UPDATE_INTERVAL', 300))
        
        self.FMP_API_KEY = os.getenv('FMP_API_KEY', '')
        
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
        
        # 文件路徑
        self.DATA_FILE = 'portfolio_data.json'
        self.LOG_DIR = Path('logs')
        self.LOG_DIR.mkdir(exist_ok=True)
    
    def is_production(self) -> bool:
        """是否為生產環境"""
        return self.ENVIRONMENT.lower() == 'production'
    
    def get_log_file(self, name: str) -> Path:
        """獲取日誌文件路徑"""
        return self.LOG_DIR / f"{name}.log"

# 全局配置實例
config = Config()
```

### 3. 測試策略

#### 單元測試
```python
# tests/test_ib_client.py
import unittest
from unittest.mock import Mock, patch
from ib_client import EnhancedIBClient

class TestEnhancedIBClient(unittest.TestCase):
    
    def setUp(self):
        self.client = EnhancedIBClient()
    
    def test_next_req_id(self):
        """測試請求ID生成"""
        req_id1 = self.client.nextReqId()
        req_id2 = self.client.nextReqId()
        
        self.assertEqual(req_id1, 1)
        self.assertEqual(req_id2, 2)
        self.assertNotEqual(req_id1, req_id2)
    
    def test_position_processing(self):
        """測試持倉數據處理"""
        from ibapi.contract import Contract
        
        # 創建模擬合約
        contract = Contract()
        contract.symbol = 'AAPL'
        contract.secType = 'STK'
        contract.currency = 'USD'
        contract.exchange = 'NASDAQ'
        
        # 設置目標賬戶
        self.client.account = 'U1234567'
        
        # 處理持倉
        self.client.position('U1234567', contract, 100, 150.0)
        
        # 驗證結果
        self.assertIn('AAPL', self.client.positions)
        position = self.client.positions['AAPL']
        self.assertEqual(position['position'], 100)
        self.assertEqual(position['avgCost'], 150.0)
    
    def test_error_handling(self):
        """測試錯誤處理"""
        # 測試市場數據錯誤
        self.client.req_id_map[1001] = {'symbol': 'AAPL', 'type': 'market_data'}
        self.client.error(1001, 162, "Market data error")
        
        # 驗證錯誤被正確分類
        self.assertIn('AAPL', self.client.subscription_errors)
        
    @patch('time.sleep')
    def test_rate_limiting(self, mock_sleep):
        """測試速率限制"""
        # 這裡添加速率限制測試邏輯
        pass

if __name__ == '__main__':
    unittest.main()
```

#### 集成測試
```python
# tests/test_integration.py
import unittest
import time
import threading
from app import create_app, EnhancedIBClient

class TestIBIntegration(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        cls.app = create_app(testing=True)
        cls.client = cls.app.test_client()
        
    def test_full_workflow(self):
        """測試完整工作流程"""
        # 1. 檢查健康狀態
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        
        # 2. 觸發數據更新
        response = self.client.post('/api/update')
        # 根據TWS連接狀態判斷預期結果
        
        # 3. 獲取持倉數據
        response = self.client.get('/api/portfolio')
        self.assertEqual(response.status_code, 200)
        
        # 4. 驗證數據格式
        data = response.get_json()
        self.assertIn('positions', data)
        self.assertIn('summary', data)
        self.assertIn('last_update', data)
```

### 4. 部署自動化

#### Docker容器化
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 複製需求文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用代碼
COPY . .

# 創建非root用戶
RUN useradd -m -u 1000 ibuser && chown -R ibuser:ibuser /app
USER ibuser

# 暴露端口
EXPOSE 8080

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# 啟動命令
CMD ["python", "app.py"]
```

#### CI/CD Pipeline
```yaml
# .github/workflows/deploy.yml
name: Deploy IB QuantTool

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        pytest tests/ --cov=./ --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v1

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Deploy to production
      run: |
        # 部署腳本
        ssh ${{ secrets.HOST }} 'cd /opt/ib_quantool && git pull && sudo systemctl restart ib_quantool'
```

---

## 結論

本指南提供了使用Claude Code開發IB量化工具的完整框架，從基礎的TWS API集成到生產環境的部署和維護。關鍵要點包括：

1. **穩健的架構設計**: 使用多繼承適配器模式和事件驅動架構
2. **全面的錯誤處理**: 分類處理不同類型的API錯誤
3. **高效的數據管理**: 合理的內存使用和數據持久化
4. **用戶友好的界面**: 響應式Web界面和實時數據更新
5. **生產級部署**: 包含監控、日誌和自動化部署

通過遵循這些最佳實踐，您可以構建出穩定、高效且易於維護的量化交易工具。

## 參考資源

- [IB TWS API官方文檔](https://interactivebrokers.github.io/tws-api/)
- [IBKR Campus API課程](https://ibkrcampus.com/trading-course/python-tws-api/)
- [Python ibapi包文檔](https://pypi.org/project/ibapi/)
- [Flask官方文檔](https://flask.palletsprojects.com/)
- [IB Cloud項目範例](https://github.com/your-repo/ib-cloud)

---

*本指南基於實際生產環境經驗編寫，持續更新中。如有問題或建議，請提交Issue或Pull Request。*