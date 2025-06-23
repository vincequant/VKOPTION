#!/bin/bash
# 請先在 GitHub 創建倉庫，然後替換下面的 REPO_NAME

REPO_NAME="ib-portfolio-frontend"  # 替換為您的倉庫名稱

echo "準備推送到 GitHub..."
echo "倉庫: https://github.com/vincequant/$REPO_NAME"

# 添加遠程倉庫
git remote add origin "https://github.com/vincequant/$REPO_NAME.git"

# 確保在 main 分支
git branch -M main

# 推送代碼
git push -u origin main

echo "推送完成！"
echo "請檢查: https://github.com/vincequant/$REPO_NAME"