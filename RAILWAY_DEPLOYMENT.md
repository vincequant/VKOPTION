# Railway 部署指南

## 概述
本指南說明如何將 IB Portfolio Monitor 部署到 Railway 平台。

## 部署步驟

### 1. 準備工作
- 確保已安裝 Git
- 確保有 Railway 賬號
- 在本地測試應用正常運行

### 2. 環境變量設置
在 Railway 項目中設置以下環境變量：

```
ENVIRONMENT=production
FMP_API_KEY=你的FMP_API_KEY（可選，用於獲取股票價格）
PORT=8080（Railway 會自動設置）
```

### 3. 部署流程

1. **初始化 Git 倉庫**（如果還沒有）
```bash
git init
git add .
git commit -m "Initial commit for Railway deployment"
```

2. **連接到 Railway**
```bash
# 安裝 Railway CLI（可選）
npm install -g @railway/cli

# 登錄 Railway
railway login

# 創建新項目
railway init

# 或連接到現有項目
railway link
```

3. **部署應用**
```bash
# 使用 Railway CLI
railway up

# 或使用 Git
git push railway main
```

### 4. 數據文件管理

由於 Railway 環境無法連接到 TWS，需要：

1. **本地更新數據**
   - 在本地運行應用
   - 點擊「更新持倉」獲取最新數據
   - 數據保存在 `portfolio_data_enhanced.json`

2. **上傳數據到 Railway**
   - 將數據文件提交到 Git
   - 推送到 Railway
   ```bash
   git add portfolio_data_enhanced.json
   git commit -m "Update portfolio data"
   railway up
   ```

### 5. 訪問應用

部署成功後，Railway 會提供一個 URL：
```
https://your-app-name.up.railway.app
```

## 功能限制

在 Railway 環境中：
- ✅ 可以查看持倉數據
- ✅ 可以查看測試頁面
- ✅ 可以獲取股票價格（通過 FMP API）
- ❌ 無法直接連接 TWS 更新數據
- ❌ 無法使用自動更新功能

## 更新流程

1. 在本地環境更新數據
2. 提交數據文件到 Git
3. 推送到 Railway

```bash
# 本地更新數據後
git add portfolio_data_enhanced.json
git commit -m "Update portfolio data - $(date)"
railway up
```

## 故障排除

### 常見問題

1. **頁面顯示 404**
   - 檢查 static 目錄是否包含 HTML 文件
   - 確認環境變量 ENVIRONMENT=production

2. **數據未更新**
   - 確保已提交最新的 portfolio_data_enhanced.json
   - 檢查 Git 狀態確認文件已推送

3. **應用啟動失敗**
   - 查看 Railway 日誌
   - 檢查 requirements.txt 是否完整
   - 確認 Python 版本兼容性

### 查看日誌
```bash
railway logs
```

## 備份方案

建議定期備份：
1. portfolio_data_enhanced.json（持倉數據）
2. cloud_upload_config.json（雲端配置）

## 安全建議

1. 不要將敏感信息提交到 Git
2. 使用環境變量管理 API 密鑰
3. 定期更新依賴包