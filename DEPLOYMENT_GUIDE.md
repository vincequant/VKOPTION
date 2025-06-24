# 部署指南 - IB Portfolio Monitor 雲端版本

## 步驟 1: 在 Vercel 刪除現有項目
1. 登入 Vercel (https://vercel.com)
2. 刪除所有相關的 ib-portfolio-frontend 項目
3. 確保沒有舊的部署殘留

## 步驟 2: 準備好的文件
您的項目已經準備好了，包含：
- `/public/dashboard_new.html` - 完整的儀表板 HTML
- `/public/portfolio_data_enhanced.json` - 實際的持倉數據
- `/src/components/FullDashboard.tsx` - React 組件（使用 iframe 加載）
- `/src/app/page.tsx` - 主頁面

## 步驟 3: 在 Vercel 創建新項目
1. 點擊 "Add New Project"
2. 選擇 "Import Git Repository"
3. 選擇您的 GitHub 倉庫: `vincequant/ib-portfolio-frontend`
4. 配置設置：
   - Framework Preset: Next.js
   - Root Directory: ./
   - Build Command: npm run build
   - Output Directory: .next
   - Install Command: npm install

## 步驟 4: 環境變量（如果需要）
目前不需要任何環境變量

## 步驟 5: 部署
1. 點擊 "Deploy"
2. 等待部署完成（約 2-3 分鐘）
3. 訪問提供的 URL

## 驗證部署
部署成功後，您應該看到：
- 完整的儀表板界面
- 所有持倉數據（MSTR、QQQ、VXX 等）
- 三個標籤頁：美股期權、港股期權、股票
- 計算功能正常工作
- 雲端上傳按鈕

## 故障排除
如果看到空白頁面或舊版本：
1. 清除瀏覽器緩存
2. 檢查瀏覽器控制台是否有錯誤
3. 確認 public 目錄中的文件已經上傳
4. 在 Vercel 檢查部署日誌

## 技術說明
當前實現使用 iframe 方式加載完整的 dashboard_new.html，確保 100% 功能複製。