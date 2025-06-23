#!/usr/bin/env python3
"""
測試雲端上傳功能 - 驗證完整計算邏輯上傳
"""

import json
import os
from pathlib import Path

# 添加項目根目錄到 Python 路徑
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import calculate_cloud_data, CONFIG

def test_calculate_cloud_data():
    """測試計算雲端數據函數"""
    print("=== 測試雲端數據計算功能 ===\n")
    
    # 檢查數據文件是否存在
    data_file = Path(CONFIG['DATA_FILE'])
    if not data_file.exists():
        print(f"❌ 找不到數據文件: {data_file}")
        return
    
    print(f"✅ 找到數據文件: {data_file}")
    
    # 讀取當前數據
    with open(data_file, 'r', encoding='utf-8') as f:
        portfolio_data = json.load(f)
    
    print(f"📊 持倉總數: {len(portfolio_data.get('positions', []))}")
    
    # 計算雲端數據
    print("\n正在計算雲端數據...")
    calculated_data = calculate_cloud_data()
    
    if not calculated_data:
        print("❌ 計算失敗")
        return
    
    print("✅ 計算成功\n")
    
    # 顯示計算結果摘要
    print("=== 計算結果摘要 ===")
    
    # 美股期權
    us_options = calculated_data['us_options']
    print(f"\n📈 美股期權:")
    print(f"  - 持倉數量: {len(us_options['positions'])}")
    print(f"  - 到期總價值: ${us_options['total_expiry_value']:,.2f}")
    print(f"  - 實際到期價值: ${us_options['actual_expiry_value']:,.2f}")
    print(f"  - 最大資金需求: ${us_options['max_capital_required']:,.2f}")
    print(f"  - 總盈虧: ${us_options['total_pnl']:,.2f}")
    
    # 顯示 Short Put 詳情
    short_puts = [p for p in us_options['positions'] if p['right'] == 'P' and p['position'] < 0]
    if short_puts:
        print(f"\n  📌 Short Put 期權詳情 ({len(short_puts)} 個):")
        for sp in short_puts[:3]:  # 只顯示前3個
            print(f"    - {sp['symbol']} Strike ${sp['strike']}")
            print(f"      標的價格: ${sp['underlying_price']:.2f}")
            print(f"      距離幅度: {sp['distance_percent']:.1f}%" if sp['distance_percent'] else "      距離幅度: N/A")
            print(f"      實際到期價值: ${sp['actual_expiry_value']:,.2f}")
            print(f"      接貨資金: ${sp['capital_required']:,.2f}")
        if len(short_puts) > 3:
            print(f"    ... 還有 {len(short_puts) - 3} 個")
    
    # 港股期權
    hk_options = calculated_data['hk_options']
    print(f"\n📈 港股期權:")
    print(f"  - 持倉數量: {len(hk_options['positions'])}")
    print(f"  - 到期總價值: HK${hk_options['total_expiry_value']:,.2f}")
    
    # 股票
    stocks = calculated_data['stocks']
    print(f"\n📊 股票:")
    print(f"  - 持倉數量: {len(stocks['positions'])}")
    print(f"  - 總市值: ${stocks['total_value']:,.2f}")
    print(f"  - 總盈虧: ${stocks['total_pnl']:,.2f}")
    
    # 回報率
    summary = calculated_data['summary']
    print(f"\n💰 資金回報率:")
    print(f"  - 最大回報率: {summary['max_return_rate']:.2f}%")
    print(f"  - 當前回報率: {summary['current_return_rate']:.2f}%")
    
    # 到期日分組
    expiry_groups = calculated_data['expiry_groups']
    print(f"\n📅 到期日分組: {len(expiry_groups)} 個")
    for i, group in enumerate(expiry_groups[:3]):
        print(f"  - {group['expiry_formatted']} (剩餘 {group['days_to_expiry']} 天)")
        if group['us_options']['count'] > 0:
            print(f"    美股期權: {group['us_options']['count']} 個, 價值 ${group['us_options']['total_value']:,.0f}")
        if group['hk_options']['count'] > 0:
            print(f"    港股期權: {group['hk_options']['count']} 個, 價值 HK${group['hk_options']['total_value']:,.0f}")
    if len(expiry_groups) > 3:
        print(f"  ... 還有 {len(expiry_groups) - 3} 個到期組")
    
    # 保存計算結果到文件
    output_file = Path("calculated_cloud_data.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(calculated_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 計算結果已保存到: {output_file}")
    print("\n=== 測試完成 ===")

if __name__ == "__main__":
    test_calculate_cloud_data()