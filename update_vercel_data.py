#!/usr/bin/env python3
"""
更新 Vercel 部署的數據
這個腳本將本地的 portfolio_data_enhanced.json 複製到前端項目並提交到 GitHub
"""

import json
import shutil
import subprocess
import os
from datetime import datetime
from pathlib import Path

def update_vercel_data():
    """更新 Vercel 上的數據"""
    
    # 文件路徑
    source_file = Path(__file__).parent / "portfolio_data_enhanced.json"
    target_dir = Path(__file__).parent / "ib-frontend-clean"
    target_file = target_dir / "public" / "portfolio_data_enhanced.json"
    
    # 檢查源文件是否存在
    if not source_file.exists():
        print("❌ 錯誤：找不到 portfolio_data_enhanced.json")
        return False
    
    # 檢查目標目錄是否存在
    if not target_dir.exists():
        print("❌ 錯誤：找不到 ib-frontend-clean 目錄")
        return False
    
    try:
        # 讀取源文件
        with open(source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 更新時間戳
        data['last_cloud_update'] = datetime.now().isoformat()
        
        # 寫入目標文件
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 數據已複製到: {target_file}")
        
        # 切換到前端目錄
        os.chdir(target_dir)
        
        # Git 操作
        commands = [
            ["git", "add", "public/portfolio_data_enhanced.json"],
            ["git", "commit", "-m", f"Update portfolio data - {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            ["git", "push", "origin", "main"]
        ]
        
        for cmd in commands:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Git 命令失敗: {' '.join(cmd)}")
                print(f"錯誤: {result.stderr}")
                return False
            print(f"✅ 執行成功: {' '.join(cmd)}")
        
        print("\n🎉 數據已成功更新到 Vercel！")
        print(f"訪問 https://ib-portfolio-frontend.vercel.app 查看更新")
        return True
        
    except Exception as e:
        print(f"❌ 更新失敗: {e}")
        return False

if __name__ == "__main__":
    update_vercel_data()