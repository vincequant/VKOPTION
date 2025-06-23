#!/usr/bin/env python3
"""
測試 VXX 價格獲取
"""

import requests
import json

# FMP API 配置
FMP_API_KEY = 'sFc5p2fbvwbYgbNo9IZDdqK8fMtn34zm'

def test_fmp_api():
    """測試 Financial Modeling Prep API 獲取 VXX 價格"""
    print("測試 FMP API 獲取 VXX 價格...")
    
    # 測試單個股票
    symbol = 'VXX'
    url = f'https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={FMP_API_KEY}'
    
    try:
        response = requests.get(url)
        print(f"狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nVXX 數據:")
            print(json.dumps(data, indent=2))
            
            if data and len(data) > 0:
                quote = data[0]
                print(f"\n價格: ${quote.get('price', 'N/A')}")
                print(f"漲跌幅: {quote.get('changesPercentage', 'N/A')}%")
        else:
            print(f"錯誤: {response.text}")
            
    except Exception as e:
        print(f"請求失敗: {e}")

def test_local_api():
    """測試本地 API 端點"""
    print("\n\n測試本地 /api/stock-prices 端點...")
    
    url = 'http://localhost:8080/api/stock-prices'
    data = {
        'symbols': ['VXX', 'SPY', 'QQQ']
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n結果:")
            print(json.dumps(result, indent=2))
        else:
            print(f"錯誤: {response.text}")
            
    except Exception as e:
        print(f"請求失敗（確保本地服務器正在運行）: {e}")

if __name__ == "__main__":
    test_fmp_api()
    test_local_api()