#!/bin/bash
# 更新雲端數據的腳本

echo "🔄 正在更新雲端數據..."

# 確保在正確的目錄
cd "$(dirname "$0")"

# 檢查是否有未提交的更改（排除某些文件）
UNSTAGED=$(git status -s | grep -v "^??" | grep -v ".env" | grep -v "ib-frontend-clean")
if [[ -n $UNSTAGED ]]; then
    echo "⚠️  有未提交的更改，請先處理"
    git status -s
    exit 1
fi

# 檢查 portfolio_data_enhanced.json 是否存在
if [ ! -f "portfolio_data_enhanced.json" ]; then
    echo "❌ 找不到 portfolio_data_enhanced.json"
    echo "請先在本地運行應用並更新持倉數據"
    exit 1
fi

# 獲取文件大小
FILE_SIZE=$(ls -lh portfolio_data_enhanced.json | awk '{print $5}')
echo "📊 數據文件大小: $FILE_SIZE"

# 提交並推送
echo "📤 正在上傳到 GitHub..."
git add -f portfolio_data_enhanced.json
git commit -m "Update portfolio data - $(date '+%Y-%m-%d %H:%M:%S')"
git push

echo "✅ 雲端數據更新完成！"
echo "🌐 Railway 將在 1-2 分鐘內自動部署"
echo "📍 訪問: https://web-production-8026.up.railway.app"