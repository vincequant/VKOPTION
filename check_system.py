#!/usr/bin/env python3
"""
IB Portfolio Monitor - System Check Tool
系統診斷工具
"""

import os
import json
import socket
import subprocess
from datetime import datetime
from pathlib import Path

def check_port(host, port):
    """檢查端口是否可連接"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def check_tws_connection():
    """檢查 TWS 連接"""
    print("\n🔌 TWS 連接檢查:")
    if check_port('127.0.0.1', 7496):
        print("  ✅ TWS 端口 7496 開放")
        print("  📡 TWS 似乎正在運行")
        return True
    else:
        print("  ❌ TWS 端口 7496 未開放")
        print("  💡 請確保:")
        print("     1. TWS 正在運行")
        print("     2. API 設置已啟用 (File → Global Configuration → API → Settings)")
        print("     3. 勾選 'Enable ActiveX and Socket Clients'")
        print("     4. Socket port 設置為 7496")
        return False

def check_server_status():
    """檢查服務器狀態"""
    print("\n🌐 Web 服務器檢查:")
    if check_port('127.0.0.1', 8080):
        print("  ✅ 服務器正在運行 (端口 8080)")
        print("  🔗 訪問: http://localhost:8080")
        return True
    else:
        print("  ⚫ 服務器未運行")
        print("  💡 啟動命令: python3 app.py")
        return False

def check_data_status():
    """檢查數據狀態"""
    print("\n📊 數據狀態:")
    data_file = Path('portfolio_data.json')
    
    if not data_file.exists():
        print("  ❌ 數據文件不存在")
        print("  💡 啟動服務器後點擊「更新數據」按鈕獲取持倉")
        return False
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 獲取更新時間
        last_update = data.get('last_update', '未知')
        positions_count = len(data.get('positions', []))
        
        # 計算時間差
        if 'timestamp' in data:
            try:
                ts = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                age = (datetime.now() - ts.replace(tzinfo=None)).total_seconds()
                if age < 60:
                    age_str = f"{int(age)}秒前"
                elif age < 3600:
                    age_str = f"{int(age/60)}分鐘前"
                else:
                    age_str = f"{int(age/3600)}小時前"
            except:
                age_str = "未知"
        else:
            age_str = "未知"
        
        print(f"  ✅ 數據文件存在")
        print(f"  📈 持倉數量: {positions_count}")
        print(f"  🕐 最後更新: {last_update} ({age_str})")
        
        # 顯示持倉摘要
        if positions_count > 0:
            summary = data.get('summary', {})
            print(f"  💰 總市值: ${summary.get('total_market_value', 0):,.2f}")
            print(f"  📊 期權: {summary.get('options_count', 0)} | 股票: {summary.get('stocks_count', 0)}")
        
        return True
        
    except Exception as e:
        print(f"  ⚠️ 數據文件讀取錯誤: {e}")
        return False

def check_project_files():
    """檢查項目文件完整性"""
    print("\n📁 文件完整性檢查:")
    
    required_files = {
        'app.py': '主應用服務器',
        'dashboard.html': '網頁儀表板',
        'check_system.py': '系統診斷工具',
        'README.md': '項目說明文檔'
    }
    
    all_good = True
    for file, desc in required_files.items():
        if Path(file).exists():
            print(f"  ✅ {file} - {desc}")
        else:
            print(f"  ❌ {file} - {desc} (缺失)")
            all_good = False
    
    return all_good

def check_python_packages():
    """檢查 Python 依賴"""
    print("\n📦 Python 依賴檢查:")
    
    packages = ['flask', 'ibapi']
    missing = []
    
    for package in packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} (未安裝)")
            missing.append(package)
    
    if missing:
        print(f"\n  💡 安裝缺失的包:")
        print(f"     pip install {' '.join(missing)}")
        return False
    
    return True

def main():
    """主函數"""
    print("=" * 60)
    print("IB Portfolio Monitor - System Check")
    print("系統診斷工具")
    print("=" * 60)
    print(f"檢查時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 執行各項檢查
    checks = [
        ("項目文件", check_project_files()),
        ("Python 依賴", check_python_packages()),
        ("TWS 連接", check_tws_connection()),
        ("Web 服務器", check_server_status()),
        ("數據狀態", check_data_status()),
    ]
    
    # 總結
    print("\n" + "=" * 60)
    print("📋 檢查總結:")
    
    passed = sum(1 for _, status in checks if status)
    total = len(checks)
    
    print(f"\n通過檢查: {passed}/{total}")
    
    if passed == total:
        print("\n✅ 系統狀態良好！")
        if not check_port('127.0.0.1', 8080):
            print("\n💡 下一步: 運行 python3 app.py 啟動服務器")
    else:
        print("\n⚠️ 發現一些問題，請根據上述提示進行修復")
    
    print("=" * 60)

if __name__ == "__main__":
    main()