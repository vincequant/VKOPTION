#!/usr/bin/env python3
"""
測試雲端上傳功能 - 直接上傳數據到 Railway
"""

import json
import requests
from pathlib import Path

CONFIG = {
    'DATA_FILE': 'portfolio_data_enhanced.json'
}

def test_direct_upload():
    """直接測試上傳數據到 Railway"""
    print("=== 直接測試上傳數據到 Railway ===\n")
    
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
    
    # 準備上傳數據
    upload_payload = {
        'portfolio_data': portfolio_data
    }
    
    # 上傳到 Railway
    url = 'https://ib-monitor.up.railway.app/api/portfolio/upload'
    headers = {
        'Authorization': 'Bearer test123',
        'Content-Type': 'application/json'
    }
    
    print(f"\n正在上傳到: {url}")
    
    try:
        response = requests.post(url, json=upload_payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 上傳成功!")
            print(f"   - 持倉數量: {result.get('positions_count', 0)}")
            print(f"   - 時間戳: {result.get('timestamp', 'N/A')}")
            
            # 驗證上傳結果
            print("\n正在驗證上傳結果...")
            verify_response = requests.get('https://ib-monitor.up.railway.app/api/portfolio')
            if verify_response.status_code == 200:
                verify_data = verify_response.json()
                positions_count = len(verify_data.get('positions', []))
                print(f"✅ 驗證成功: 雲端有 {positions_count} 個持倉")
                print(f"   - 最後更新: {verify_data.get('last_update', 'N/A')}")
            else:
                print(f"❌ 驗證失敗: {verify_response.status_code}")
                
        else:
            print(f"❌ 上傳失敗: {response.status_code}")
            print(f"   錯誤信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 上傳出錯: {e}")
    
    print("\n=== 測試完成 ===")

if __name__ == "__main__":
    test_direct_upload()