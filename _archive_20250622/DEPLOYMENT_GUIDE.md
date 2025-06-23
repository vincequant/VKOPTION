# PythonAnywhere 部署指南

本指南說明如何將 IB 倉位監控系統部署到 PythonAnywhere。

## 架構概述

```
[本地電腦]                         [PythonAnywhere]
IB Gateway/TWS                      Web 應用
     ↓                                 ↑
app.py + cloud_uploader  ---HTTP--->  pythonanywhere_app.py
                                       ↓
                                    SQLite 數據庫
```

## 部署步驟

### 1. PythonAnywhere 設置

1. 註冊 PythonAnywhere 賬戶（免費版即可）
2. 創建新的 Web 應用：
   - 選擇 Flask
   - Python 版本選擇 3.8 或以上

### 2. 上傳後端代碼

1. 在 PythonAnywhere 的 Files 頁面，導航到您的應用目錄
2. 上傳 `pythonanywhere_app.py` 作為主應用文件
3. 在 Web 頁面設置 WSGI 配置文件，確保導入正確：
   ```python
   from pythonanywhere_app import app as application
   ```

### 3. 設置環境變量

在 PythonAnywhere 的 Web 頁面，設置環境變量：
```
API_SECRET_KEY = "生成一個安全的隨機密鑰"
```

生成安全密鑰的方法：
```python
import secrets
print(secrets.token_urlsafe(32))
```

### 4. 配置本地上傳器

編輯本地的 `cloud_config.json`：
```json
{
  "api_url": "https://YOUR_USERNAME.pythonanywhere.com/api/portfolio",
  "api_key": "與上面設置的 API_SECRET_KEY 相同",
  "username": "YOUR_PYTHONANYWHERE_USERNAME",
  "retry_count": 3,
  "timeout": 30
}
```

### 5. 測試連接

在本地運行測試：
```bash
python cloud_uploader.py
```

應該看到 "雲端連接測試成功" 的消息。

### 6. 修改前端頁面

創建新的雲端版本前端頁面，從 PythonAnywhere API 讀取數據。

## 使用流程

### 日常使用

1. **本地更新數據**：
   ```bash
   # 啟動本地應用
   /path/to/ib_env/bin/python app.py
   ```
   數據會自動上傳到雲端

2. **查看倉位**：
   訪問 `https://YOUR_USERNAME.pythonanywhere.com`

### 手動上傳

如果需要手動觸發上傳，可以使用 API：
```bash
curl -X POST http://localhost:8080/api/upload-to-cloud
```

## 安全建議

1. **使用強密鑰**：API_SECRET_KEY 應該是隨機生成的長字符串
2. **HTTPS**：PythonAnywhere 自動提供 HTTPS，確保使用 https:// URL
3. **定期更換密鑰**：建議每幾個月更換一次 API 密鑰
4. **限制 IP**：如果可能，在 PythonAnywhere 設置 IP 白名單

## 故障排除

### 問題：上傳失敗，顯示 401 錯誤
**解決**：檢查 cloud_config.json 中的 api_key 是否與 PythonAnywhere 環境變量匹配

### 問題：連接超時
**解決**：
1. 確認 PythonAnywhere 應用正在運行
2. 檢查 URL 是否正確（注意用戶名拼寫）
3. 嘗試增加 timeout 值

### 問題：數據不更新
**解決**：
1. 檢查本地 app.log 查看上傳日誌
2. 在 PythonAnywhere 查看錯誤日誌
3. 確認數據庫權限正確

## 高級功能

### 數據清理
後端會自動保留最近 100 條記錄，避免數據庫過大。

### 數據新鮮度
API 返回數據時會包含 `data_age_hours` 字段，顯示數據的新鮮程度。

### 批量更新
如果需要批量更新歷史數據，可以編寫腳本循環調用上傳 API。

## 下一步

1. 創建雲端版本的 dashboard.html
2. 添加數據可視化功能
3. 實現數據歷史記錄查詢
4. 添加更多安全功能（如請求簽名）