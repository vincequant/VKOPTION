#!/usr/bin/env python3
"""
生成測試數據以確保儀表板正常工作
基於手機截圖的真實持倉結構
"""

import json
from datetime import datetime

# 基於手機截圖的持倉數據
test_positions = [
    # SPY期權
    {"symbol": "SPY", "sec_type": "OPT", "strike": 609, "right": "P", "expiry": "20250117", "position": -5, "avg_cost": 20.32},
    {"symbol": "SPY", "sec_type": "OPT", "strike": 596, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 16.59},
    {"symbol": "SPY", "sec_type": "OPT", "strike": 583, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 13.31},
    {"symbol": "SPY", "sec_type": "OPT", "strike": 575, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 11.67},
    {"symbol": "SPY", "sec_type": "OPT", "strike": 557, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 8.80},
    {"symbol": "SPY", "sec_type": "OPT", "strike": 544, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 6.93},
    {"symbol": "SPY", "sec_type": "OPT", "strike": 531, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 5.41},
    {"symbol": "SPY", "sec_type": "OPT", "strike": 518, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 4.20},
    {"symbol": "SPY", "sec_type": "OPT", "strike": 505, "right": "P", "expiry": "20250117", "position": -20, "avg_cost": 3.25},
    {"symbol": "SPY", "sec_type": "OPT", "strike": 479, "right": "P", "expiry": "20250117", "position": -20, "avg_cost": 1.91},
    {"symbol": "SPY", "sec_type": "OPT", "strike": 453, "right": "P", "expiry": "20250117", "position": -20, "avg_cost": 1.09},
    
    # QQQ期權
    {"symbol": "QQQ", "sec_type": "OPT", "strike": 535, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 16.95},
    {"symbol": "QQQ", "sec_type": "OPT", "strike": 522, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 13.66},
    {"symbol": "QQQ", "sec_type": "OPT", "strike": 509, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 10.88},
    {"symbol": "QQQ", "sec_type": "OPT", "strike": 496, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 8.58},
    {"symbol": "QQQ", "sec_type": "OPT", "strike": 483, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 6.70},
    {"symbol": "QQQ", "sec_type": "OPT", "strike": 470, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 5.16},
    {"symbol": "QQQ", "sec_type": "OPT", "strike": 444, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 2.91},
    {"symbol": "QQQ", "sec_type": "OPT", "strike": 418, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 1.59},
    
    # IWM期權
    {"symbol": "IWM", "sec_type": "OPT", "strike": 239, "right": "P", "expiry": "20250117", "position": -5, "avg_cost": 5.41},
    {"symbol": "IWM", "sec_type": "OPT", "strike": 230, "right": "P", "expiry": "20250117", "position": -7, "avg_cost": 3.66},
    {"symbol": "IWM", "sec_type": "OPT", "strike": 221, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 2.43},
    {"symbol": "IWM", "sec_type": "OPT", "strike": 212, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 1.58},
    {"symbol": "IWM", "sec_type": "OPT", "strike": 203, "right": "P", "expiry": "20250117", "position": -10, "avg_cost": 1.00},
    {"symbol": "IWM", "sec_type": "OPT", "strike": 185, "right": "P", "expiry": "20250117", "position": -20, "avg_cost": 0.37},
    
    # 股票持倉
    {"symbol": "MSTY", "sec_type": "STK", "position": 3000, "avg_cost": 98.97},
]

# 處理每個持倉
processed_positions = []
for pos in test_positions:
    position_data = {
        'account': 'DU1234567',
        'symbol': pos['symbol'],
        'sec_type': pos['sec_type'],
        'currency': 'USD',
        'exchange': 'SMART',
        'position': pos['position'],
        'avg_cost': pos['avg_cost'],
        'contract_id': 0,
        'timestamp': datetime.now().isoformat(),
        'last_update': datetime.now().isoformat()
    }
    
    # 期權額外信息
    if pos['sec_type'] == 'OPT':
        position_data.update({
            'strike': pos['strike'],
            'right': pos['right'],
            'expiry': pos['expiry'],
            'multiplier': '100',
            'local_symbol': f"{pos['symbol']} {pos['expiry'][2:6]} {pos['strike']}{pos['right']}",
            'expiry_formatted': f"{pos['expiry'][:4]}-{pos['expiry'][4:6]}-{pos['expiry'][6:8]}",
            'days_to_expiry': 28,  # 簡化計算
            'option_type': pos['right'],
            'option_type_name': '看漲 (Call)' if pos['right'] == 'C' else '看跌 (Put)',
            'name': f"{pos['symbol']} {pos['expiry'][:4]}-{pos['expiry'][4:6]}-{pos['expiry'][6:8]} ${pos['strike']} {pos['right']}"
        })
        # 計算市場價值
        position_data['market_value'] = pos['position'] * pos['avg_cost'] * 100
        position_data['market_price'] = pos['avg_cost']
    else:
        position_data['name'] = f"{pos['symbol']} - {pos['sec_type']}"
        position_data['market_value'] = pos['position'] * pos['avg_cost']
        position_data['market_price'] = pos['avg_cost']
    
    position_data['unrealized_pnl'] = 0  # 暫時設為0
    processed_positions.append(position_data)

# 計算統計
options_count = len([p for p in processed_positions if p['sec_type'] == 'OPT'])
stocks_count = len([p for p in processed_positions if p['sec_type'] == 'STK'])
total_market_value = sum(p['market_value'] for p in processed_positions)

# 生成完整數據
portfolio_data = {
    'timestamp': datetime.now().isoformat(),
    'last_update': datetime.now().strftime('%H:%M:%S'),
    'positions': processed_positions,
    'summary': {
        'total_positions': len(processed_positions),
        'options_count': options_count,
        'stocks_count': stocks_count,
        'total_market_value': total_market_value,
        'total_unrealized_pnl': 0,
        'net_liquidation': 14000000,  # 基於截圖
        'day_change': 0,
        'day_change_percent': 0
    },
    'account_summary': {
        'DU1234567': {
            'NetLiquidation': {'value': '14000000', 'currency': 'USD'},
            'TotalCashValue': {'value': '10000000', 'currency': 'USD'},
            'GrossPositionValue': {'value': str(abs(total_market_value)), 'currency': 'USD'}
        }
    },
    'source': 'test_data',
    'status': 'test'
}

# 保存數據
with open('live_portfolio_data.json', 'w', encoding='utf-8') as f:
    json.dump(portfolio_data, f, indent=2, ensure_ascii=False)

print("✅ 測試數據已生成")
print(f"📊 總計: {len(processed_positions)} 個持倉")
print(f"   - 期權: {options_count}")
print(f"   - 股票: {stocks_count}")
print(f"💰 總市值: ${total_market_value:,.2f}")
print("💾 數據已保存到 live_portfolio_data.json")
print("\n🚀 現在可以運行:")
print("   python3 simple_start.py")
print("   然後訪問 http://localhost:5001")