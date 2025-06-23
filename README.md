# IB Portfolio Monitor - IB 倉位監控系統

一個專為 Interactive Brokers 設計的實時倉位監控系統，支持美股期權、港股期權及股票持倉的全面追蹤。

## 核心功能

- 📊 **實時倉位監控** - 自動連接 TWS 獲取持倉數據
- 📈 **期權分析** - 計算期權到期價值、距離幅度、實際損益
- 💰 **賬戶信息** - 顯示淨清算價值、可用資金等關鍵指標
- 🔄 **自動更新** - 每 5 分鐘自動更新數據
- 📱 **響應式設計** - 支持桌面和移動設備

## 快速開始

### 環境要求
- Python 3.8+
- Interactive Brokers TWS (Trader Workstation)
- 虛擬環境 (推薦)

### 安裝步驟

1. 克隆項目
```bash
cd /Users/vk/Library/CloudStorage/Dropbox/Vkquantapp/IB倉位監控
```

2. 啟動 TWS 並配置 API
- 打開 TWS
- File → Global Configuration → API → Settings
- 勾選 "Enable ActiveX and Socket Clients"
- Socket port: 7496

3. 運行程序
```bash
# 使用虛擬環境
./ib_env/bin/python app.py

# 或使用啟動腳本
./start.sh
```

4. 訪問界面
- 主頁面: http://localhost:8080
- 測試頁面: http://localhost:8080/test

## 項目結構

```
.
├── app.py                      # 主程序，處理 IB API 連接和數據獲取
├── dashboard_new.html          # 主界面，顯示持倉和分析數據
├── test_api_data.html         # 測試頁面，查看原始 API 數據
├── portfolio_data_enhanced.json # 數據存儲文件
├── CLAUDE.md                  # 詳細項目文檔
└── ib_env/                    # Python 虛擬環境
```

## 主要特性

### 1. 期權分析
- **距離幅度**: 顯示標的價格與行權價的百分比差異
- **實際到期價值**: 根據標的價格動態計算期權到期時的實際價值
- **Short Put 分析**: 特別優化了賣出看跌期權的資金需求和風險計算

### 2. 數據整合
- 自動從 Financial Modeling Prep API 獲取股票實時價格
- 整合 TWS 持倉數據與市場數據
- 支持美股和港股市場

### 3. 界面功能
- 分類顯示：美股期權、港股期權、股票
- 到期日分組：按到期日組織期權持倉
- 排序功能：支持多列排序
- 實時狀態：顯示連接狀態和更新時間

## 配置說明

主要配置在 `app.py` 中的 `CONFIG` 字典：

```python
CONFIG = {
    'TWS_HOST': '127.0.0.1',      # TWS 主機地址
    'TWS_PORT': 7496,             # TWS API 端口
    'CLIENT_ID': 9999,            # 客戶端 ID
    'SERVER_PORT': 8080,          # Web 服務端口
    'AUTO_UPDATE_INTERVAL': 300,   # 自動更新間隔（秒）
    'FMP_API_KEY': 'your_api_key' # FMP API 密鑰
}
```

## API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/` | 主頁面 |
| GET | `/test` | 測試頁面 |
| GET | `/api/portfolio` | 獲取持倉數據 |
| POST | `/api/update` | 更新持倉數據 |
| GET | `/api/status` | 系統狀態 |
| POST | `/api/stock-prices` | 獲取股票價格 |

## 故障排除

1. **連接失敗**
   - 確認 TWS 已啟動並啟用 API
   - 檢查端口 7496 是否正確
   - 確認防火牆設置

2. **數據不顯示**
   - 檢查 portfolio_data_enhanced.json 是否存在
   - 查看控制台日誌是否有錯誤
   - 手動點擊"更新持倉"按鈕

3. **價格數據缺失**
   - 確認 FMP API 密鑰有效
   - 檢查網絡連接
   - 某些股票可能需要付費訂閱

## 更多信息

詳細的技術文檔和更新歷史請參見 [CLAUDE.md](CLAUDE.md)

## 版本信息

- 版本: 2.0.0
- 更新日期: 2025-06-22
- 作者: VK Quant App

---

本項目為私人項目，僅供個人使用。# ib-cloud
