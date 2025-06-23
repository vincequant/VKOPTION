#!/usr/bin/env python3
"""
手動持倉數據輸入工具
如果 API 連接有問題，可以使用此工具手動輸入持倉數據
"""

import json
from datetime import datetime

def input_position():
    """輸入單個持倉"""
    print("\n" + "="*40)
    print("輸入持倉信息 (輸入 'done' 結束)")
    print("="*40)
    
    # 證券類型
    sec_type = input("證券類型 (STK/OPT) [默認: OPT]: ").upper() or "OPT"
    if sec_type not in ["STK", "OPT"]:
        print("❌ 無效的證券類型")
        return None
        
    # 基本信息
    symbol = input("代碼 (如 SPY): ").upper()
    if not symbol:
        return None
        
    position = input("持倉數量 (負數表示賣出): ")
    try:
        position = float(position)
    except:
        print("❌ 無效的數量")
        return None
        
    avg_cost = input("平均成本: ")
    try:
        avg_cost = float(avg_cost)
    except:
        print("❌ 無效的成本")
        return None
        
    # 構建持倉數據
    pos_data = {
        'account': 'Manual',
        'symbol': symbol,
        'sec_type': sec_type,
        'currency': 'USD',
        'exchange': 'SMART',
        'position': position,
        'avg_cost': avg_cost,
        'contract_id': 0,
        'timestamp': datetime.now().isoformat(),
        'last_update': datetime.now().isoformat()
    }
    
    # 期權額外信息
    if sec_type == "OPT":
        strike = input("行權價: ")
        try:
            strike = float(strike)
        except:
            print("❌ 無效的行權價")
            return None
            
        right = input("類型 (C/P): ").upper()
        if right not in ["C", "P"]:
            print("❌ 無效的期權類型")
            return None
            
        expiry = input("到期日 (YYYYMMDD): ")
        if len(expiry) != 8:
            print("❌ 無效的到期日格式")
            return None
            
        pos_data.update({
            'strike': strike,
            'right': right,
            'expiry': expiry,
            'multiplier': '100',
            'expiry_formatted': f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}",
            'option_type': right,
            'option_type_name': '看漲 (Call)' if right == 'C' else '看跌 (Put)',
            'name': f"{symbol} {expiry[:4]}-{expiry[4:6]}-{expiry[6:8]} ${strike} {right}",
            'market_value': position * avg_cost * 100,
            'market_price': avg_cost
        })
    else:
        pos_data['name'] = f"{symbol} - {sec_type}"
        pos_data['market_value'] = position * avg_cost
        pos_data['market_price'] = avg_cost
        
    pos_data['unrealized_pnl'] = 0
    
    # 顯示輸入的持倉
    print(f"\n✅ 已添加: {pos_data['name']} x{position}")
    
    return pos_data

def quick_option_input():
    """快速期權輸入模式"""
    print("\n快速期權輸入 (格式: 代碼 行權價 C/P 數量 成本)")
    print("例如: SPY 609 P -5 20.32")
    print("輸入 'done' 結束")
    
    positions = []
    
    while True:
        line = input("\n> ")
        if line.lower() == 'done':
            break
            
        parts = line.split()
        if len(parts) != 5:
            print("❌ 格式錯誤，需要5個參數")
            continue
            
        try:
            symbol = parts[0].upper()
            strike = float(parts[1])
            right = parts[2].upper()
            position = float(parts[3])
            avg_cost = float(parts[4])
            
            if right not in ["C", "P"]:
                print("❌ 期權類型必須是 C 或 P")
                continue
                
            # 默認到期日為2025年1月17日
            expiry = "20250117"
            
            pos_data = {
                'account': 'Manual',
                'symbol': symbol,
                'sec_type': 'OPT',
                'currency': 'USD',
                'exchange': 'SMART',
                'position': position,
                'avg_cost': avg_cost,
                'contract_id': 0,
                'timestamp': datetime.now().isoformat(),
                'last_update': datetime.now().isoformat(),
                'strike': strike,
                'right': right,
                'expiry': expiry,
                'multiplier': '100',
                'expiry_formatted': f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}",
                'option_type': right,
                'option_type_name': '看漲 (Call)' if right == 'C' else '看跌 (Put)',
                'name': f"{symbol} {expiry[:4]}-{expiry[4:6]}-{expiry[6:8]} ${strike} {right}",
                'market_value': position * avg_cost * 100,
                'market_price': avg_cost,
                'unrealized_pnl': 0
            }
            
            positions.append(pos_data)
            print(f"✅ 已添加: {pos_data['name']} x{position}")
            
        except Exception as e:
            print(f"❌ 輸入錯誤: {e}")
            
    return positions

def main():
    print("📝 手動持倉數據輸入工具")
    print("=" * 50)
    
    # 選擇輸入模式
    print("\n選擇輸入模式:")
    print("1. 詳細輸入 (逐個輸入每個字段)")
    print("2. 快速期權輸入 (一行輸入所有信息)")
    print("3. 使用測試數據")
    
    mode = input("\n選擇 (1/2/3): ")
    
    positions = []
    
    if mode == "1":
        # 詳細輸入模式
        while True:
            pos = input_position()
            if pos:
                positions.append(pos)
            else:
                break
                
    elif mode == "2":
        # 快速輸入模式
        positions = quick_option_input()
        
    elif mode == "3":
        # 使用測試數據
        print("使用預設的測試數據...")
        import subprocess
        subprocess.run([sys.executable, "generate_test_data.py"])
        print("\n✅ 測試數據已生成")
        print("🚀 現在可以運行: python3 simple_start.py")
        return
        
    else:
        print("❌ 無效的選擇")
        return
        
    if not positions:
        print("\n❌ 沒有輸入任何持倉")
        return
        
    # 計算統計
    options_count = len([p for p in positions if p['sec_type'] == 'OPT'])
    stocks_count = len([p for p in positions if p['sec_type'] == 'STK'])
    total_market_value = sum(p.get('market_value', 0) for p in positions)
    
    # 構建完整數據
    portfolio_data = {
        'timestamp': datetime.now().isoformat(),
        'last_update': datetime.now().strftime('%H:%M:%S'),
        'positions': positions,
        'summary': {
            'total_positions': len(positions),
            'options_count': options_count,
            'stocks_count': stocks_count,
            'total_market_value': total_market_value,
            'total_unrealized_pnl': 0,
            'net_liquidation': 14000000,  # 默認值
            'day_change': 0,
            'day_change_percent': 0
        },
        'account_summary': {
            'Manual': {
                'NetLiquidation': {'value': '14000000', 'currency': 'USD'}
            }
        },
        'source': 'manual_input',
        'status': 'manual'
    }
    
    # 保存數據
    with open('live_portfolio_data.json', 'w', encoding='utf-8') as f:
        json.dump(portfolio_data, f, indent=2, ensure_ascii=False)
        
    print("\n" + "="*50)
    print("✅ 數據已保存!")
    print(f"📊 總計: {len(positions)} 個持倉")
    print(f"   - 期權: {options_count}")
    print(f"   - 股票: {stocks_count}")
    print(f"💰 總市值: ${total_market_value:,.2f}")
    print("\n🚀 現在可以運行:")
    print("   python3 simple_start.py")
    print("   訪問 http://localhost:5001")

if __name__ == "__main__":
    import sys
    main()