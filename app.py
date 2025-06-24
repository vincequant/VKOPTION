#!/usr/bin/env python3
"""
IB Portfolio Monitor - Enhanced Version with All Available Data
IB 倉位監控系統 - 增強版（獲取所有可用數據）
"""


from flask import Flask, jsonify, send_file, render_template_string, request, send_from_directory
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
import atexit
import requests
import webbrowser
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
    'TWS_HOST': os.environ.get('TWS_HOST', '127.0.0.1'),
    'TWS_PORT': int(os.environ.get('TWS_PORT', '7496')),
    'CLIENT_ID': int(os.environ.get('CLIENT_ID', '8888')),
    'SERVER_PORT': int(os.environ.get('PORT', '8080')),  # Railway uses PORT env var
    'DATA_FILE': 'portfolio_data_enhanced.json',
    'DASHBOARD_FILE': 'dashboard_new.html',
    'AUTO_UPDATE_INTERVAL': int(os.environ.get('AUTO_UPDATE_INTERVAL', '300')),
    'FMP_API_KEY': os.environ.get('FMP_API_KEY', ''),  # API key should be set via environment variable
    'CLOUD_CONFIG_FILE': 'cloud_upload_config.json',
    'ENVIRONMENT': os.environ.get('ENVIRONMENT', 'development'),
    'TARGET_ACCOUNT': os.environ.get('TARGET_ACCOUNT', '')  # 目標賬戶，從環境變量讀取
}

# 全局變量
ib_client = None
update_lock = threading.Lock()
auto_update_thread = None
stop_auto_update = threading.Event()
cloud_config = None

# 雲端上傳功能
def load_cloud_config():
    """載入雲端上傳配置"""
    global cloud_config
    config_file = Path(CONFIG['CLOUD_CONFIG_FILE'])
    
    default_config = {
        'api_url': '',
        'api_key': '',
        'account_number': '',
        'enabled': False
    }
    
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                default_config.update(saved_config)
        except Exception as e:
            logger.error(f"載入雲端配置失敗: {e}")
    
    cloud_config = default_config
    return cloud_config

def save_cloud_config():
    """保存雲端上傳配置"""
    global cloud_config
    if cloud_config:
        try:
            config_file = Path(CONFIG['CLOUD_CONFIG_FILE'])
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(cloud_config, f, ensure_ascii=False, indent=2)
            logger.info("雲端配置已保存")
        except Exception as e:
            logger.error(f"保存雲端配置失敗: {e}")

def calculate_cloud_data():
    """計算所有需要上傳到雲端的數據，包含完整的計算邏輯"""
    try:
        # 讀取當前數據文件
        data_file = Path(CONFIG['DATA_FILE'])
        if not data_file.exists():
            return None
            
        with open(data_file, 'r', encoding='utf-8') as f:
            portfolio_data = json.load(f)
        
        # 常量定義
        USD_TO_HKD = 7.8
        
        # 初始化計算結果
        calculations = {
            'us_options': {
                'total_expiry_value': 0,
                'actual_expiry_value': 0,
                'max_capital_required': 0,
                'total_pnl': 0,
                'positions': []
            },
            'hk_options': {
                'total_expiry_value': 0,
                'positions': []
            },
            'stocks': {
                'total_value': 0,
                'total_pnl': 0,
                'positions': []
            },
            'summary': {
                'net_liquidation_usd': 0,
                'net_liquidation_hkd': 0,
                'available_funds_usd': 0,
                'available_funds_hkd': 0,
                'max_return_rate': 0,
                'current_return_rate': 0
            },
            'expiry_groups': []
        }
        
        # 獲取賬戶摘要數據
        if 'summary' in portfolio_data:
            summary = portfolio_data['summary']
            if 'NetLiquidation' in summary:
                calculations['summary']['net_liquidation_usd'] = float(summary['NetLiquidation']) / USD_TO_HKD
                calculations['summary']['net_liquidation_hkd'] = float(summary['NetLiquidation'])
            if 'AvailableFunds' in summary:
                calculations['summary']['available_funds_usd'] = float(summary['AvailableFunds']) / USD_TO_HKD
                calculations['summary']['available_funds_hkd'] = float(summary['AvailableFunds'])
        
        # 處理每個持倉
        positions = portfolio_data.get('positions', [])
        for pos in positions:
            # 計算通用字段
            pos_calc = {
                'symbol': pos.get('symbol'),
                'contract_type': pos.get('secType'),
                'currency': pos.get('currency'),
                'position': pos.get('position', 0),
                'avg_cost': pos.get('avg_cost', 0),
                'market_value': pos.get('market_value', 0),
                'pnl': pos.get('pnl'),
                'has_market_data': pos.get('has_market_data', False)
            }
            
            # 期權特定計算
            if pos.get('secType') == 'OPT':
                strike = pos.get('strike', 0)
                underlying_price = pos.get('underlying_price', 0)
                right = pos.get('right', '')
                expiry = pos.get('expiry', '')
                days_to_expiry = pos.get('days_to_expiry', 0)
                
                pos_calc.update({
                    'strike': strike,
                    'right': right,
                    'expiry': expiry,
                    'days_to_expiry': days_to_expiry,
                    'underlying_price': underlying_price
                })
                
                # 計算距離幅度
                if underlying_price > 0 and strike > 0:
                    distance_percent = ((underlying_price - strike) / strike) * 100
                    pos_calc['distance_percent'] = distance_percent
                else:
                    pos_calc['distance_percent'] = None
                
                # 計算實際到期價值
                if right == 'P' and pos.get('position', 0) < 0:  # Short Put
                    avg_cost = pos.get('avg_cost', pos.get('avgCost', 0))
                    position_size = abs(pos.get('position', 0))
                    
                    if underlying_price > 0:
                        if underlying_price >= strike:
                            # 不會被行權，收取權利金
                            actual_expiry_value = avg_cost * position_size * 100
                        else:
                            # 會被行權，計算損失
                            loss = (strike - underlying_price - avg_cost) * position_size * 100
                            actual_expiry_value = -loss
                    else:
                        # 沒有底層價格，保守估計
                        actual_expiry_value = avg_cost * position_size * 100
                    
                    pos_calc['actual_expiry_value'] = actual_expiry_value
                    
                    # 計算接貨資金
                    capital_required = (strike - avg_cost) * position_size * 100
                    pos_calc['capital_required'] = capital_required
                else:
                    # 其他期權類型
                    pos_calc['actual_expiry_value'] = abs(pos.get('market_value', 0))
                    pos_calc['capital_required'] = 0
                
                # 分類統計
                if pos.get('currency') == 'USD':
                    calculations['us_options']['positions'].append(pos_calc)
                    calculations['us_options']['total_expiry_value'] += abs(pos.get('market_value', 0))
                    calculations['us_options']['actual_expiry_value'] += pos_calc['actual_expiry_value']
                    calculations['us_options']['max_capital_required'] += pos_calc.get('capital_required', 0)
                    if pos.get('pnl') is not None:
                        calculations['us_options']['total_pnl'] += pos.get('pnl', 0)
                elif pos.get('currency') == 'HKD':
                    calculations['hk_options']['positions'].append(pos_calc)
                    calculations['hk_options']['total_expiry_value'] += abs(pos.get('market_value', 0))
            
            # 股票特定計算
            elif pos.get('secType') == 'STK':
                current_price = underlying_price if underlying_price > 0 else 0
                
                if current_price > 0:
                    market_value = pos.get('position', 0) * current_price
                    cost = pos.get('position', 0) * pos.get('avg_cost', 0)
                    pnl = market_value - cost
                    pnl_percent = (pnl / cost * 100) if cost > 0 else 0
                    
                    pos_calc.update({
                        'current_price': current_price,
                        'calculated_market_value': market_value,
                        'calculated_pnl': pnl,
                        'pnl_percent': pnl_percent
                    })
                else:
                    pos_calc.update({
                        'current_price': 0,
                        'calculated_market_value': pos.get('market_value', 0),
                        'calculated_pnl': 0,
                        'pnl_percent': 0
                    })
                
                calculations['stocks']['positions'].append(pos_calc)
                calculations['stocks']['total_value'] += pos_calc.get('calculated_market_value', 0)
                calculations['stocks']['total_pnl'] += pos_calc.get('calculated_pnl', 0)
        
        # 計算回報率
        if calculations['us_options']['max_capital_required'] > 0:
            calculations['summary']['max_return_rate'] = (
                calculations['us_options']['actual_expiry_value'] / 
                calculations['us_options']['max_capital_required'] * 100
            )
        
        if calculations['summary']['net_liquidation_usd'] > 0:
            calculations['summary']['current_return_rate'] = (
                calculations['us_options']['actual_expiry_value'] / 
                calculations['summary']['net_liquidation_usd'] * 100
            )
        
        # 處理到期日分組
        if 'options_by_expiry' in portfolio_data:
            for expiry_group in portfolio_data['options_by_expiry']:
                group_calc = {
                    'expiry': expiry_group.get('expiry'),
                    'expiry_formatted': expiry_group.get('expiry_formatted'),
                    'days_to_expiry': expiry_group.get('days_to_expiry', 0),
                    'us_options': {
                        'count': 0,
                        'total_value': 0,
                        'total_pnl': 0,
                        'capital_required': 0
                    },
                    'hk_options': {
                        'count': 0,
                        'total_value': 0
                    }
                }
                
                # 統計每個到期日的數據
                for symbol in expiry_group.get('positions', []):
                    pos = next((p for p in positions if p.get('symbol') == symbol and p.get('expiry') == expiry_group.get('expiry')), None)
                    if pos:
                        if pos.get('currency') == 'USD':
                            group_calc['us_options']['count'] += 1
                            group_calc['us_options']['total_value'] += abs(pos.get('market_value', 0))
                            if pos.get('pnl') is not None:
                                group_calc['us_options']['total_pnl'] += pos.get('pnl', 0)
                            if pos.get('right') == 'P' and pos.get('position', 0) < 0:
                                avg_cost = pos.get('avg_cost', pos.get('avgCost', 0))
                                capital = (pos.get('strike', 0) - avg_cost) * abs(pos.get('position', 0)) * 100
                                group_calc['us_options']['capital_required'] += capital
                        elif pos.get('currency') == 'HKD':
                            group_calc['hk_options']['count'] += 1
                            group_calc['hk_options']['total_value'] += abs(pos.get('market_value', 0))
                
                calculations['expiry_groups'].append(group_calc)
        
        return calculations
        
    except Exception as e:
        logger.error(f"計算雲端數據失敗: {str(e)}")
        return None

def upload_to_cloud(calculated_summary=None):
    """上傳當前數據到雲端，包含完整的計算邏輯"""
    global cloud_config
    
    if not cloud_config or not cloud_config.get('enabled'):
        return {'success': False, 'message': '雲端上傳未啟用'}
    
    required_fields = ['api_url', 'api_key', 'account_number']
    for field in required_fields:
        if not cloud_config.get(field):
            return {'success': False, 'message': f'雲端配置缺失: {field}'}
    
    try:
        # 讀取當前數據文件
        data_file = Path(CONFIG['DATA_FILE'])
        if not data_file.exists():
            return {'success': False, 'message': '找不到本地數據文件'}
        
        with open(data_file, 'r', encoding='utf-8') as f:
            portfolio_data = json.load(f)
        
        # 計算所有需要的數據
        calculated_data = calculate_cloud_data()
        if not calculated_data:
            return {'success': False, 'message': '計算數據失敗'}
        
        # 準備上傳數據
        upload_payload = {
            'portfolio_data': portfolio_data,
            'calculated_data': calculated_data,  # 包含所有計算結果
            'upload_timestamp': datetime.now().isoformat(),
            'source': 'local_dashboard_upload',
            'version': '2.0',  # 標記新版本格式
            'calculation_formulas': {
                'distance_percent': '((underlying_price - strike) / strike) * 100',
                'short_put_expiry_value': {
                    'not_exercised': 'avg_cost * position * 100',
                    'exercised': '-((strike - underlying_price - avg_cost) * position * 100)'
                },
                'capital_required': '(strike - avg_cost) * position * 100',
                'stock_pnl': '(position * current_price) - (position * avg_cost)',
                'return_rates': {
                    'max_return': '(actual_expiry_value / max_capital_required) * 100',
                    'current_return': '(actual_expiry_value / net_liquidation) * 100'
                }
            },
            'constants': {
                'USD_TO_HKD': 7.8
            }
        }
        
        # 如果有額外的計算汇總數據，也添加進去
        if calculated_summary:
            upload_payload['additional_summary'] = calculated_summary
        
        headers = {
            'Authorization': f'Bearer {cloud_config["api_key"]}',
            'Content-Type': 'application/json'
        }
        
        logger.info(f"正在上傳完整數據到雲端: {cloud_config['api_url']}")
        logger.info(f"上傳數據包含: {len(portfolio_data.get('positions', []))} 個持倉，{len(calculated_data['expiry_groups'])} 個到期組")
        
        response = requests.post(
            cloud_config['api_url'],
            json=upload_payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            positions_count = len(portfolio_data.get('positions', []))
            logger.info(f"雲端上傳成功: {positions_count} 個持倉及完整計算數據")
            return {
                'success': True, 
                'message': f'成功上傳 {positions_count} 個持倉及完整計算邏輯到雲端',
                'positions_count': positions_count,
                'calculations_included': True
            }
        else:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_detail = response.json().get('detail', response.text)
                error_msg += f": {error_detail}"
            except:
                error_msg += f": {response.text[:200]}"
            
            logger.error(f"雲端上傳失敗: {error_msg}")
            return {'success': False, 'message': f'上傳失敗: {error_msg}'}
            
    except Exception as e:
        logger.error(f"雲端上傳異常: {str(e)}")
        return {'success': False, 'message': f'上傳異常: {str(e)}'}

# 初始化雲端配置
load_cloud_config()

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
        self.pnl_data = {}  # 盈虧數據 (renamed from self.pnl to avoid conflict)
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
        
        # 賬戶信息
        self.account = None  # 將存儲主賬戶號
        
        # 錯誤追蹤
        self.errors = []  # 存儲所有錯誤信息
        
        # 雲端功能已移除
        
    def nextReqId(self):
        """生成下一個請求ID"""
        self.req_id_counter += 1
        return self.req_id_counter
        
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """錯誤處理"""
        # 忽略資訊性消息
        info_codes = [
            2104,  # Market data farm connection is OK
            2106,  # HMDS data farm connection is OK
            2107,  # HMDS data farm connection is inactive
            2108,  # Market data farm connection is inactive
            2158,  # Sec-def data farm connection is OK
            2119,  # Market data farm is connecting
            2110,  # Connectivity between TWS and server is broken
        ]
        
        # 預期的錯誤（如沒有權限的市場數據）
        expected_errors = [
            321,   # Error validating request
            354,   # Requested market data is not subscribed
            10167, # Requested market data is not subscribed
            10090, # Part of requested market data is not subscribed
            10091, # Subscription required for market data
            162,   # Historical data error for options
            200,   # No security definition found
            102,   # Duplicate ticker id
            2103,  # Market data farm connection broken
            2105,  # Historical data farm connection broken
        ]
        
        # 記錄錯誤信息
        error_info = {
            'reqId': reqId,
            'errorCode': errorCode,
            'errorString': errorString,
            'timestamp': datetime.now().isoformat(),
            'symbol': self.req_id_map.get(reqId, 'Unknown') if reqId > 0 else 'System'
        }
        
        if errorCode in info_codes:
            return
        elif errorCode in expected_errors:
            error_info['level'] = 'warning'
            self.errors.append(error_info)
            logger.warning(f"Expected error {errorCode}: {errorString} (reqId: {reqId})")
        else:
            error_info['level'] = 'error'
            self.errors.append(error_info)
            logger.error(f"IB API Error {errorCode}: {errorString} (reqId: {reqId})")
            
        # 限制錯誤列表大小
        if len(self.errors) > 100:
            self.errors = self.errors[-100:]
    
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
    
    def managedAccounts(self, accountsList: str):
        """接收管理的賬戶列表"""
        super().managedAccounts(accountsList)
        accounts = accountsList.split(",")
        # 使用指定的目標賬戶（如果有）
        target_account = CONFIG['TARGET_ACCOUNT']
        if target_account and target_account in accounts:
            self.account = target_account
            logger.info(f"Managed accounts: {len(accounts)} available")
            logger.info(f"Using target account: {target_account[:2]}******")
        elif accounts and accounts[0]:
            # 如果沒有指定目標賬戶，使用第一個可用賬戶
            self.account = accounts[0]
            logger.info(f"Managed accounts: {len(accounts)} available")
            logger.info(f"Using first available account: {self.account[:2]}******")
        else:
            logger.warning(f"No valid accounts found in: {accountsList}")
        
    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """接收持倉數據"""
        # 只處理目標賬戶的持倉
        if self.account and account != self.account:
            return
            
        if position != 0:
            symbol = contract.symbol
            
            # 如果是期權，需要包含更多信息來區分不同的期權合約
            if contract.secType == 'OPT':
                symbol = f"{contract.symbol}_{contract.lastTradeDateOrContractMonth}_{contract.right}_{contract.strike}"
            
            # 存儲完整的contract對象
            self.contracts[symbol] = contract
            
            # 存儲持倉信息
            self.positions[symbol] = {
                'account': account,
                'symbol': contract.symbol,  # 保持原始symbol
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
                # 設置期權的交易所（如果未設置）
                if not contract.exchange or contract.exchange == "" or contract.exchange == "SMART":
                    if contract.currency == "HKD":
                        contract.exchange = "HKFE"  # 香港期權使用HKFE
                        # 對於香港期權，需要特殊的symbol設置
                        # 根據 tradingClass 設置正確的 symbol
                        if hasattr(contract, 'tradingClass') and contract.tradingClass:
                            # 對於香港期權，symbol 應該是 tradingClass
                            self.positions[symbol]['underlying_symbol'] = contract.symbol
                            self.positions[symbol]['hk_trading_class'] = contract.tradingClass
                    else:
                        contract.exchange = "SMART"  # 美國期權使用SMART
                
            logger.info(f"Received position: {symbol} {position}")
            
    def positionEnd(self):
        """持倉數據接收完成"""
        logger.info(f"Received {len(self.positions)} positions")
        # 請求額外數據
        self.requestAdditionalData()
        
    def requestAdditionalData(self):
        """請求所有額外數據"""
        logger.info("Requesting additional data...")
        
        # 檢查是否需要使用延遲數據
        self.use_delayed_data = False  # 可以設置為 True 來使用延遲數據
        
        # 計算賬戶總資產和盈虧
        self.total_unrealized_pnl = 0
        self.total_realized_pnl = 0
        self.total_daily_pnl = 0
        
        # 1. 請求賬戶摘要 - 只請求目標賬戶
        if self.account:
            self.reqAccountSummary(9001, self.account, 
                "NetLiquidation,TotalCashValue,SettledCash,AccruedCash,BuyingPower,"
                "EquityWithLoanValue,PreviousEquityWithLoanValue,GrossPositionValue,"
                "InitMarginReq,MaintMarginReq,AvailableFunds,ExcessLiquidity,Cushion,"
                "DayTradesRemaining,Leverage,Currency")
        else:
            logger.warning("No target account available for account summary request")
        
        # 2. 請求賬戶更新 - 只請求目標賬戶
        if self.account:
            self.reqAccountUpdates(True, self.account)
        else:
            logger.warning("Not requesting account updates - no target account available")
        
        # 3. 為每個持倉請求市場數據
        for symbol, pos_data in self.positions.items():
            contract = self.contracts[symbol]
            req_id = self.nextReqId()
            self.req_id_map[req_id] = symbol
            
            # 設置外匯合約的交易所
            if contract.secType == 'CASH' and not contract.exchange:
                contract.exchange = "IDEALPRO"
            
            # 請求實時市場數據
            if contract.secType == 'OPT':
                # 對於香港期權，創建正確的合約對象
                if contract.currency == "HKD" and contract.exchange == "HKFE":
                    # 特別處理有問題的香港股票期權
                    if symbol in ['1024', '700']:
                        logger.warning(f"Skipping problematic HK stock option: {symbol} - Contract definition issues")
                        # 記錄合約資訊供調試
                        logger.info(f"Contract details - Symbol: {contract.symbol}, LocalSymbol: {contract.localSymbol}, " +
                                   f"TradingClass: {getattr(contract, 'tradingClass', 'N/A')}, ConId: {contract.conId}")
                        # 跳過這些合約的市場數據請求
                        continue
                    
                    # 使用原合約請求數據
                    self.reqMktData(req_id, contract, 
                        "232",  # 使用 232 包括收盤價
                        False, False, [])
                    logger.info(f"Requesting market data for HK option: {symbol} (conId: {contract.conId})")
                else:
                    # 非香港期權使用原合約
                    # 對於期權，優先嘗試使用延遲數據（免費）
                    # 使用 "232" 來獲取包括收盤價在內的快照數據
                    self.reqMktData(req_id, contract, 
                        "232",  # 232 包括收盤價
                        False, False, [])  # 不使用監管快照
            else:
                # 股票的標準tick類型
                self.reqMktData(req_id, contract, "233", False, False, [])
            
            # 請求歷史數據
            # 期權嘗試請求 TRADES 數據來獲取收盤價
            hist_req_id = self.nextReqId()
            self.req_id_map[hist_req_id] = symbol
            
            if contract.secType == 'OPT':
                # 期權使用 TRADES 數據類型
                self.reqHistoricalData(
                    hist_req_id, contract, "", "1 D", "1 day", 
                    "TRADES", 1, 1, False, []
                )
            else:
                # 股票和其他使用 MIDPOINT
                self.reqHistoricalData(
                    hist_req_id, contract, "", "5 D", "1 day", 
                    "MIDPOINT", 1, 1, False, []
                )
            
        # 設置超時，等待數據收集
        threading.Timer(10.0, self.dataCollectionComplete).start()
    
    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """接收賬戶摘要"""
        # 只處理目標賬戶的數據
        if self.account and account == self.account:
            self.account_summary[tag] = {
                'value': value,
                'currency': currency,
                'account': account
            }
            logger.info(f"Account Summary - {account} {tag}: {value} {currency}")
    
    def accountSummaryEnd(self, reqId: int):
        """賬戶摘要結束"""
        logger.info("Account summary completed")
        self.account_data_ready.set()
    
    def updateAccountValue(self, key: str, val: str, currency: str, accountName: str):
        """更新賬戶價值"""
        # 只處理目標賬戶的數據
        if self.account and accountName == self.account:
            self.account_values[key] = {
                'value': val,
                'currency': currency,
                'account': accountName
            }
        
    def updatePortfolio(self, contract: Contract, position: float, marketPrice: float, 
                       marketValue: float, averageCost: float, unrealizedPNL: float, 
                       realizedPNL: float, accountName: str):
        """更新持倉組合（來自reqAccountUpdates）"""
        # 只處理目標賬戶的數據
        if self.account and accountName != self.account:
            return
            
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
                
                # 如果獲得了last或close價格，也設置為當前價格
                if tickType in [4, 9]:  # last or close
                    self.market_data[symbol]['currentPrice'] = price
                    
                # 對於期權，如果沒有收盤價但有平均成本，使用平均成本作為參考
                if tickType == 1 and price == -1:  # bid 為 -1 表示市場關閉
                    if symbol in self.positions and self.positions[symbol].get('secType') == 'OPT':
                        avg_cost = self.positions[symbol].get('avg_cost', 0)
                        if avg_cost > 0 and 'close' not in self.market_data[symbol]:
                            # 使用平均成本作為參考收盤價
                            self.market_data[symbol]['close'] = avg_cost
                            logger.info(f"Using avg cost as close price for {symbol}: {avg_cost}")
    
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
        self.pnl_data['account'] = {
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
            self.pnl_data[symbol] = {
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
            
            # 將最新的收盤價添加到 market_data
            if symbol in self.historical_data and self.historical_data[symbol]:
                latest_bar = self.historical_data[symbol][-1]  # 獲取最新的數據
                if symbol not in self.market_data:
                    self.market_data[symbol] = {}
                
                # 保存收盤價
                self.market_data[symbol]['close'] = latest_bar['close']
                logger.info(f"Set close price for {symbol}: {latest_bar['close']}")
    
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
            
            # 隱藏真實賬戶號碼（用於公開版本）
            if 'account' in position_data:
                # 將賬戶號碼替換為匿名版本
                account = position_data['account']
                if account.startswith('U'):
                    # 保留首字母U，其餘用星號替換
                    position_data['account'] = 'U' + '*' * (len(account) - 1)
                else:
                    position_data['account'] = 'DEMO'
            
            # 添加市場數據
            if symbol in self.market_data:
                position_data['market_data'] = self.market_data[symbol]
                position_data['has_market_data'] = True
            else:
                position_data['has_market_data'] = False
            
            # 添加PnL數據
            if symbol in self.pnl_data:
                position_data['pnl_data'] = self.pnl_data[symbol]
                position_data['has_pnl_data'] = True
            else:
                position_data['has_pnl_data'] = False
            
            # 添加期權希臘值
            if symbol in self.options_data:
                position_data['options_data'] = self.options_data[symbol]
                position_data['has_options_data'] = True
            else:
                position_data['has_options_data'] = False
            
            # 檢查是否為無法獲取數據的香港期權
            position_data['data_unavailable'] = False
            if pos['secType'] == 'OPT' and pos['currency'] == 'HKD':
                # 檢查是否有市場數據訂閱錯誤
                has_subscription_error = any(
                    err['reqId'] in self.req_id_map and self.req_id_map[err['reqId']] == symbol 
                    and err['errorCode'] in [200, 10090, 10091, 354]
                    for err in self.errors
                )
                if has_subscription_error:
                    position_data['data_unavailable'] = True
            
            # 添加歷史數據
            if symbol in self.historical_data:
                position_data['historical_data'] = self.historical_data[symbol]
            
            # 計算一些衍生數據
            if pos['secType'] == 'OPT':
                # 期權的市值計算
                # HSI特殊處理
                if pos['symbol'] == 'HSI':
                    # HSI使用用戶指定的固定平均價格
                    avg_cost = 169.3
                else:
                    avg_cost = pos['avgCost'] / 100  # 其他期權轉換為單位價格
                position_data['avg_cost'] = avg_cost
                
                # 獲取當前市場價格
                current_price = 0
                if symbol in self.market_data:
                    # 對於HSI，如果只有close價格而沒有實時價格，標記為數據不可用
                    market_data = self.market_data[symbol]
                    if (pos['symbol'] == 'HSI' and 
                        market_data.get('bid', -1) == -1 and 
                        market_data.get('ask', -1) == -1 and
                        market_data.get('last') is None):
                        position_data['data_unavailable'] = True
                    
                    current_price = (market_data.get('currentPrice') or 
                                   market_data.get('last') or 
                                   market_data.get('close') or 
                                   market_data.get('markPrice') or 0)
                position_data['current_price'] = current_price
                
                # 計算盈虧
                if pos['position'] < 0:  # Short position
                    if position_data.get('data_unavailable', False):
                        # 如果數據不可用，設置pnl為None
                        position_data['pnl'] = None
                    elif current_price > 0:
                        # 賣出期權的盈虧 = (收取的權利金 - 當前市值) * 數量
                        position_data['pnl'] = (avg_cost - current_price) * abs(pos['position']) * 100
                    else:
                        position_data['pnl'] = 0
                else:
                    position_data['pnl'] = 0
                
                # 如果有市場價格，使用市場價格計算市值；否則使用成本價
                multiplier = float(position_data.get('multiplier', '100'))
                if current_price > 0:
                    position_data['market_value'] = pos['position'] * current_price * multiplier
                else:
                    if pos['symbol'] == 'HSI':
                        # HSI使用固定的平均價格 × 數量 × 乘數
                        position_data['market_value'] = pos['position'] * 169.3 * multiplier
                    else:
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
                    
                # 添加行權價信息
                position_data['strike'] = pos.get('strike', 0)
            else:
                # 股票的市值計算
                current_price = 0
                if symbol in self.market_data:
                    current_price = (self.market_data[symbol].get('currentPrice') or 
                                   self.market_data[symbol].get('last') or 
                                   self.market_data[symbol].get('close') or 0)
                position_data['current_price'] = current_price
                
                if current_price > 0:
                    position_data['market_value'] = pos['position'] * current_price
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
        
        # 分析數據訂閱狀態
        subscription_errors = {}
        for error in self.errors:
            if error['errorCode'] in [10090, 10091, 354, 10167]:
                symbol = error.get('symbol', 'Unknown')
                if symbol != 'System' and symbol != 'Unknown':
                    subscription_errors[symbol] = {
                        'error_code': error['errorCode'],
                        'message': '需要付費訂閱市場數據',
                        'error_string': error['errorString']
                    }
        
        # 獲取底層股票價格（使用 FMP API）
        underlying_prices = self.fetch_underlying_prices(positions_data)
        
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
            'account_pnl': self.pnl_data.get('account', {}),
            'options_by_expiry': list(options_by_expiry.values()),
            'underlying_prices': underlying_prices,  # 新增：底層股票價格
            'source': 'ib_api_enhanced',
            'status': 'updated',
            'errors': self.errors[-20:],  # 只包含最近20個錯誤
            'subscription_errors': subscription_errors  # 新增：訂閱錯誤信息
        }
        
        # 保存到文件
        try:
            temp_file = CONFIG['DATA_FILE'] + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(portfolio_data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, CONFIG['DATA_FILE'])
            logger.info(f"Enhanced portfolio data saved to {CONFIG['DATA_FILE']}")
            
            # 保存成功
            
        except Exception as e:
            logger.error(f"Failed to save portfolio data: {e}")
    
    def fetch_underlying_prices(self, positions_data):
        """獲取底層股票價格（使用 FMP API）"""
        try:
            # 收集所有需要獲取價格的股票符號
            underlying_symbols = set()
            
            for pos in positions_data:
                if pos['secType'] == 'OPT' and pos.get('tradingClass'):
                    # 期權的底層股票
                    underlying_symbols.add(pos['tradingClass'])
                elif pos['secType'] == 'STK':
                    # 股票持倉
                    underlying_symbols.add(pos['symbol'])
            
            if not underlying_symbols:
                return {}
            
            logger.info(f"正在獲取 {len(underlying_symbols)} 個股票的價格數據...")
            
            # 使用 FMP API 獲取價格
            prices = {}
            symbols_list = list(underlying_symbols)
            batch_size = 50  # FMP API 批量限制
            
            for i in range(0, len(symbols_list), batch_size):
                batch = symbols_list[i:i+batch_size]
                symbols_str = ",".join(batch)
                
                url = f"https://financialmodelingprep.com/api/v3/quote/{symbols_str}?apikey={CONFIG['FMP_API_KEY']}"
                
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        quotes = response.json()
                        logger.info(f"FMP API 返回 {len(quotes)} 個報價")
                        for quote in quotes:
                            symbol = quote.get('symbol')
                            if symbol:
                                logger.info(f"獲取到 {symbol} 的價格: ${quote.get('price', 0)}")
                                prices[symbol] = {
                                    'price': quote.get('price', 0),
                                    'changesPercentage': quote.get('changesPercentage', 0),
                                    'dayHigh': quote.get('dayHigh', 0),
                                    'dayLow': quote.get('dayLow', 0),
                                    'previousClose': quote.get('previousClose', 0),
                                    'timestamp': quote.get('timestamp', 0)
                                }
                                logger.info(f"獲取到 {symbol} 價格: ${quote.get('price', 0):.2f}")
                    else:
                        logger.error(f"FMP API 錯誤: {response.status_code}")
                except Exception as e:
                    logger.error(f"獲取批量報價錯誤: {e}")
            
            logger.info(f"成功獲取 {len(prices)} 個股票的價格數據")
            return prices
            
        except Exception as e:
            logger.error(f"獲取底層股票價格時發生錯誤: {e}")
            return {}
    

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
    if CONFIG['ENVIRONMENT'] == 'production':
        # Railway 環境使用 static 目錄
        return send_from_directory('static', 'dashboard_new.html')
    else:
        # 本地開發環境
        dashboard_path = Path(CONFIG['DASHBOARD_FILE'])
        if dashboard_path.exists():
            return send_file(dashboard_path)
        else:
            return "Dashboard file not found", 404

@app.route('/test')
def test_page():
    """測試頁面 - 顯示所有可用數據"""
    if CONFIG['ENVIRONMENT'] == 'production':
        # Railway 環境使用 static 目錄
        return send_from_directory('static', 'test_api_data.html')
    else:
        # 本地開發環境
        test_path = Path('test_api_data.html')
        if test_path.exists():
            return send_file(test_path)
        else:
            return "Test page not found", 404

# 以下路由已被移除，統一使用主頁面
# @app.route('/dashboard')  - 完整儀表板
# @app.route('/dashboard_categorized.html')  - 分類版
# @app.route('/dashboard_enhanced.html')  - 增強版

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
    
    # Railway 生產環境不支持 TWS 連接
    if CONFIG['ENVIRONMENT'] == 'production':
        return jsonify({
            "success": False,
            "error": "Not available in production",
            "message": "Railway 環境無法連接到 TWS。請在本地環境更新數據後上傳。"
        }), 503
    
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
            
            try:
                ib_client.connect(CONFIG['TWS_HOST'], CONFIG['TWS_PORT'], clientId=CONFIG['CLIENT_ID'])
            except Exception as e:
                logger.error(f"Connection failed: {e}")
                return jsonify({
                    "success": False,
                    "error": "Connection failed",
                    "message": f"無法連接到 TWS：{str(e)}。請檢查：\n1. TWS 是否正在運行\n2. API 設置是否啟用（端口 7496）\n3. 防火牆是否阻擋連接"
                }), 503
            
            if not ib_client.connection_ready.wait(timeout=10):
                logger.error("Connection timeout - did not receive nextValidId")
                return jsonify({
                    "success": False,
                    "error": "Connection timeout",
                    "message": "連接超時。請確保：\n1. TWS 已登錄\n2. API 設置中啟用了 'Enable ActiveX and Socket Clients'\n3. 端口設置為 7496"
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

# 雲端上傳相關路由

@app.route('/api/cloud-config', methods=['GET'])
def get_cloud_config():
    """API: 獲取雲端配置"""
    global cloud_config
    if not cloud_config:
        load_cloud_config()
    
    # 返回配置但隱藏API Key
    safe_config = cloud_config.copy()
    if safe_config.get('api_key'):
        safe_config['api_key'] = safe_config['api_key'][:8] + '***'
    
    return jsonify({
        "success": True,
        "config": safe_config,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/cloud-config', methods=['POST'])
def update_cloud_config():
    """API: 更新雲端配置"""
    global cloud_config
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "無效的JSON數據"}), 400
        
        # 更新配置
        if not cloud_config:
            load_cloud_config()
        
        # 只更新允許的字段
        allowed_fields = ['api_url', 'api_key', 'account_number', 'enabled']
        for field in allowed_fields:
            if field in data:
                cloud_config[field] = data[field]
        
        # 保存配置
        save_cloud_config()
        
        logger.info("雲端配置已更新")
        return jsonify({
            "success": True,
            "message": "雲端配置已更新",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"更新雲端配置錯誤: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/upload-to-cloud', methods=['POST'])
def api_upload_to_cloud():
    """API: 上傳數據到雲端（使用 GitHub 更新）"""
    try:
        # 執行更新腳本
        import subprocess
        script_path = Path(__file__).parent / "update_vercel_data.py"
        
        if not script_path.exists():
            # 如果沒有更新腳本，使用原來的方法
            request_data = request.get_json() or {}
            calculated_summary = request_data.get('calculated_summary', {})
            result = upload_to_cloud(calculated_summary)
        else:
            # 執行更新腳本
            process = subprocess.run(
                ["python3", str(script_path)],
                capture_output=True,
                text=True
            )
            
            if process.returncode == 0:
                result = {
                    'success': True,
                    'message': '數據已更新到 Vercel',
                    'positions_count': len(ib_client.positions) if ib_client else 0
                }
            else:
                result = {
                    'success': False,
                    'message': f'更新失敗: {process.stderr}'
                }
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": result['message'],
                "positions_count": result.get('positions_count', 0),
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "success": False,
                "error": result['message'],
                "timestamp": datetime.now().isoformat()
            }), 400
            
    except Exception as e:
        logger.error(f"API上傳到雲端錯誤: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/test-cloud-connection', methods=['POST'])
def test_cloud_connection():
    """API: 測試雲端連接"""
    global cloud_config
    
    try:
        if not cloud_config or not cloud_config.get('api_url'):
            return jsonify({
                "success": False,
                "error": "雲端API URL未配置"
            }), 400
        
        # 測試健康檢查端點
        health_url = cloud_config['api_url'].replace('/api/portfolio/upload', '/health')
        
        response = requests.get(health_url, timeout=10)
        
        if response.status_code == 200:
            return jsonify({
                "success": True,
                "message": "雲端連接測試成功",
                "status_code": response.status_code,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "success": False,
                "error": f"雲端連接測試失敗: HTTP {response.status_code}",
                "timestamp": datetime.now().isoformat()
            }), 400
            
    except Exception as e:
        logger.error(f"測試雲端連接錯誤: {e}")
        return jsonify({
            "success": False,
            "error": f"連接測試異常: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/stock-prices', methods=['POST'])
def get_stock_prices():
    """API: 獲取股票現價（使用 Financial Modeling Prep API）"""
    try:
        # 獲取請求中的股票符號列表
        data = request.get_json()
        symbols = data.get('symbols', [])
        
        if not symbols:
            return jsonify({"error": "No symbols provided"}), 400
        
        # 去重並過濾
        symbols = list(set(symbols))
        
        # 使用 FMP API 獲取股票報價
        prices = {}
        batch_size = 50  # FMP API 批量限制
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            symbols_str = ",".join(batch)
            
            url = f"https://financialmodelingprep.com/api/v3/quote/{symbols_str}?apikey={CONFIG['FMP_API_KEY']}"
            
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    quotes = response.json()
                    for quote in quotes:
                        symbol = quote.get('symbol')
                        if symbol:
                            prices[symbol] = {
                                'price': quote.get('price', 0),
                                'changesPercentage': quote.get('changesPercentage', 0),
                                'dayHigh': quote.get('dayHigh', 0),
                                'dayLow': quote.get('dayLow', 0),
                                'previousClose': quote.get('previousClose', 0),
                                'timestamp': quote.get('timestamp', 0)
                            }
                else:
                    logger.error(f"FMP API error: {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching batch quotes: {e}")
        
        return jsonify({
            "success": True,
            "prices": prices,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in get_stock_prices: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

def auto_update_data():
    """自動更新數據的線程函數"""
    global ib_client
    
    while not stop_auto_update.is_set():
        # 等待指定的時間間隔
        if stop_auto_update.wait(CONFIG['AUTO_UPDATE_INTERVAL']):
            break
            
        with update_lock:
            try:
                logger.info("Starting automatic data update...")
                
                if not ib_client or not ib_client.isConnected():
                    logger.warning("IB client not connected, skipping auto update")
                    continue
                
                # 清空舊數據
                ib_client.positions = {}
                ib_client.contracts = {}
                ib_client.market_data = {}
                ib_client.account_summary = {}
                ib_client.pnl_data = {}
                ib_client.options_data = {}
                ib_client.historical_data = {}
                ib_client.errors = []  # 清空錯誤列表
                
                # 重置事件
                ib_client.update_complete.clear()
                
                # 請求新數據
                ib_client.reqPositions()
                
                # 等待數據收集完成
                if ib_client.update_complete.wait(timeout=20):
                    logger.info(f"Auto update completed: {len(ib_client.positions)} positions")
                else:
                    logger.warning("Auto update timeout")
                    
            except Exception as e:
                logger.error(f"Auto update error: {e}")

def update_underlying_prices():
    """更新底層股票價格到數據文件"""
    try:
        # 讀取現有數據
        data_file = Path(CONFIG['DATA_FILE'])
        if not data_file.exists():
            return
            
        with open(data_file, 'r', encoding='utf-8') as f:
            portfolio_data = json.load(f)
        
        # 收集所有期權的底層股票符號
        underlying_symbols = set()
        for pos in portfolio_data.get('positions', []):
            if pos.get('secType') == 'OPT' and pos.get('tradingClass'):
                underlying_symbols.add(pos['tradingClass'])
        
        if not underlying_symbols:
            return
        
        print(f"🔄 正在獲取 {len(underlying_symbols)} 個底層股票價格...")
        
        # 使用 FMP API 獲取股票價格
        prices = {}
        batch_size = 50
        symbols_list = list(underlying_symbols)
        
        for i in range(0, len(symbols_list), batch_size):
            batch = symbols_list[i:i+batch_size]
            symbols_str = ",".join(batch)
            url = f"https://financialmodelingprep.com/api/v3/quote/{symbols_str}?apikey={CONFIG['FMP_API_KEY']}"
            
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    quotes = response.json()
                    for quote in quotes:
                        symbol = quote.get('symbol')
                        if symbol:
                            prices[symbol] = {
                                'price': quote.get('price', 0),
                                'changesPercentage': quote.get('changesPercentage', 0),
                                'dayHigh': quote.get('dayHigh', 0),
                                'dayLow': quote.get('dayLow', 0),
                                'previousClose': quote.get('previousClose', 0),
                                'timestamp': quote.get('timestamp', 0)
                            }
            except Exception as e:
                logger.error(f"Error fetching batch quotes: {e}")
        
        # 更新數據文件中的底層股票價格
        portfolio_data['underlying_prices'] = prices
        portfolio_data['underlying_prices_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 保存回文件
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(portfolio_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 成功更新 {len(prices)} 個底層股票價格")
        
    except Exception as e:
        logger.error(f"Error updating underlying prices: {e}")
        print(f"⚠️  更新底層股票價格失敗: {e}")

def initialize_ib_connection():
    """初始化 IB 連接並獲取初始數據"""
    global ib_client, auto_update_thread
    
    # Railway 生產環境跳過 TWS 連接
    if CONFIG['ENVIRONMENT'] == 'production':
        print("🌐 Railway 生產環境 - 跳過 TWS 連接")
        print("📊 使用已保存的數據文件")
        
        # 更新底層股票價格
        if Path(CONFIG['DATA_FILE']).exists():
            update_underlying_prices()
        
        return False
    
    print("🔄 正在連接到 IB TWS...")
    
    try:
        ib_client = EnhancedIBClient()
        ib_client.connection_ready.clear()
        ib_client.update_complete.clear()
        
        # 連接到 TWS
        ib_client.connect(CONFIG['TWS_HOST'], CONFIG['TWS_PORT'], clientId=CONFIG['CLIENT_ID'])
        
        # 等待連接就緒
        if not ib_client.connection_ready.wait(timeout=5):
            print("⚠️  TWS 連接超時，將在無連接狀態下啟動")
            print("   請確保 TWS 正在運行並已啟用 API")
            print("   您可以稍後通過測試頁面手動更新數據")
            return False
        
        print("✅ TWS 連接成功")
        print("🔄 正在獲取初始數據...")
        
        # 請求持倉數據
        ib_client.reqPositions()
        
        # 等待數據收集完成
        if ib_client.update_complete.wait(timeout=20):
            print(f"✅ 成功獲取 {len(ib_client.positions)} 個持倉數據")
            
            # 獲取底層股票價格
            update_underlying_prices()
            
            # 啟動自動更新線程
            stop_auto_update.clear()
            auto_update_thread = threading.Thread(target=auto_update_data, daemon=True)
            auto_update_thread.start()
            print(f"🔄 自動更新已啟動（每 {CONFIG['AUTO_UPDATE_INTERVAL']} 秒更新一次）")
            
            return True
        else:
            print("⚠️  數據獲取超時，部分數據可能不完整")
            return False
            
    except Exception as e:
        print(f"⚠️  連接失敗: {e}")
        print("   將在無連接狀態下啟動")
        return False

def main():
    """主函數 - 啟動應用"""
    print("=" * 60)
    print("IB Portfolio Monitor - Enhanced Version")
    print("=" * 60)
    print(f"🌍 Environment: {CONFIG['ENVIRONMENT']}")
    print(f"📁 Working Directory: {os.getcwd()}")
    print(f"📊 Data File: {CONFIG['DATA_FILE']}")
    
    if CONFIG['ENVIRONMENT'] != 'production':
        print(f"🔌 TWS Connection: {CONFIG['TWS_HOST']}:{CONFIG['TWS_PORT']}")
    
    print("=" * 60)
    
    # 嘗試初始化 IB 連接
    ib_connected = initialize_ib_connection()
    
    # 如果已有數據文件但沒有連接TWS，仍然更新底層股票價格
    if not ib_connected and Path(CONFIG['DATA_FILE']).exists():
        print("🔄 無 TWS 連接，但正在更新底層股票價格...")
        update_underlying_prices()
    
    print("=" * 60)
    print(f"🚀 Starting server on port {CONFIG['SERVER_PORT']}...")
    
    if CONFIG['ENVIRONMENT'] == 'production':
        print(f"🌐 Railway URL will be assigned after deployment")
    else:
        print(f"🌐 Dashboard URL: http://localhost:{CONFIG['SERVER_PORT']}")
        print(f"🧪 Test page URL: http://localhost:{CONFIG['SERVER_PORT']}/test")
    
    print("=" * 60)
    
    # 在生產環境使用 gunicorn，否則使用 Flask 內建服務器
    if CONFIG['ENVIRONMENT'] == 'production':
        # Railway 會使用 gunicorn 啟動，這裡只需要提供 app
        print("🚀 Running in production mode with gunicorn")
    else:
        print("💡 Press Ctrl+C to stop the server")
        
        # 啟動服務器線程
        def run_server():
            app.run(
                host='0.0.0.0',
                port=CONFIG['SERVER_PORT'],
                debug=False,
                use_reloader=False
            )
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # 等待服務器啟動
        time.sleep(2)
        
        # 自動打開瀏覽器（僅在開發環境）
        dashboard_url = f"http://localhost:{CONFIG['SERVER_PORT']}"
        print(f"🌐 正在打開瀏覽器: {dashboard_url}")
        try:
            webbrowser.open(dashboard_url)
            print("✅ 瀏覽器已打開IB倉位監控頁面")
        except Exception as e:
            print(f"⚠️ 無法自動打開瀏覽器: {e}")
            print(f"請手動訪問: {dashboard_url}")
        
        print("\n" + "=" * 60)
        print("🎯 使用說明:")
        print("   1. 確保TWS已連接並啟用API")
        print("   2. 點擊「更新持倉」獲取最新數據")
        print("   3. 點擊「上傳雲端」配置雲端同步")
        print("   4. 配置完成後可一鍵同步到雲端")
        print("=" * 60)
        
        try:
            # 保持主線程運行
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user")
            cleanup()
        except Exception as e:
            logger.error(f"Server error: {e}")
            print(f"\n❌ Server error: {e}")
            cleanup()

def cleanup():
    """清理資源"""
    global ib_client, auto_update_thread, stop_auto_update
    
    print("🧹 正在清理資源...")
    
    # 停止自動更新
    if auto_update_thread and auto_update_thread.is_alive():
        stop_auto_update.set()
        auto_update_thread.join(timeout=5)
        print("✅ 自動更新已停止")
    
    # 斷開 IB 連接
    if ib_client and ib_client.isConnected():
        try:
            ib_client.disconnect()
            print("✅ IB 連接已斷開")
        except:
            pass
    
    print("✅ 清理完成")

# 註冊退出處理
atexit.register(cleanup)

if __name__ == "__main__":
    main()