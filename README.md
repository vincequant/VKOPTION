# VKOPTION - Interactive Brokers 期權倉位監控系統

[English Version](#english-version)

## 📊 項目簡介

VKOPTION 是一個開源的 Interactive Brokers 倉位監控系統，專為期權交易者設計。通過 TWS API 實時獲取持倉數據，並在網頁儀表板上清晰展示您的投資組合。

### 主要特色
- 🔄 **實時數據同步** - 通過 TWS API 自動更新持倉信息
- 📈 **期權分析工具** - 顯示 Greeks、到期天數、行權距離等關鍵指標
- 💱 **多幣種支持** - 自動處理 USD/HKD 匯率轉換
- 🌐 **雲端部署** - 支持 Railway/Vercel 一鍵部署
- 📱 **響應式設計** - 完美適配桌面和移動設備

## 🚀 快速開始

### 環境要求
- Python 3.8 或更高版本
- Interactive Brokers TWS 或 IB Gateway
- 已啟用 TWS API（端口 7496）

### 安裝步驟

1. **克隆項目**
```bash
git clone https://github.com/vincequant/VKOPTION.git
cd VKOPTION
```

2. **安裝依賴**
```bash
pip install -r requirements.txt
```

3. **配置環境變量**
```bash
cp .env.example .env
# 編輯 .env 文件，填入您的配置
```

4. **啟動應用**
```bash
python app.py
# 或使用快速啟動腳本
./start.sh
```

5. **訪問網頁**
   - 主頁面：http://localhost:8080
   - 測試頁面：http://localhost:8080/test

## 📖 詳細配置

### TWS 設置
1. 打開 TWS → File → Global Configuration → API → Settings
2. 勾選 "Enable ActiveX and Socket Clients"
3. Socket port 設置為 7496
4. 勾選 "Read-Only API"（推薦）

### 環境變量說明
- `TWS_HOST`：TWS 連接地址（默認：127.0.0.1）
- `TWS_PORT`：TWS API 端口（默認：7496）
- `CLIENT_ID`：API 客戶端 ID（默認：8888）
- `FMP_API_KEY`：Financial Modeling Prep API 密鑰（可選，用於獲取股票價格）

## 📱 功能展示

### 主要功能
1. **持倉總覽** - 查看所有股票和期權持倉
2. **期權分析** - 包含以下指標：
   - 隱含波動率 (IV)
   - Delta、Gamma、Theta、Vega
   - 到期天數倒計時
   - 行權價與標的價格距離
   - 實時盈虧計算
3. **自動更新** - 可設置自動更新頻率
4. **數據導出** - 支持導出 JSON 格式數據

## 🚀 部署指南

### Railway 部署
1. Fork 本項目
2. 在 Railway 創建新項目
3. 連接 GitHub 倉庫
4. 設置環境變量
5. 部署完成

詳細部署文檔請參考 [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)

## 🔒 安全提醒

- **永遠不要**將真實的賬戶數據提交到 Git
- **永遠不要**在代碼中硬編碼 API 密鑰
- 使用 `.env` 文件管理敏感配置
- 定期更新依賴包以修復安全漏洞

## 🤝 貢獻指南

歡迎提交 Pull Request！在提交前請確保：
1. 代碼通過所有測試
2. 遵循現有的代碼風格
3. 更新相關文檔
4. 不包含任何敏感信息

## 📄 開源協議

本項目採用 MIT 協議開源，詳見 [LICENSE](LICENSE) 文件。

## ⚠️ 免責聲明

本軟件僅供學習和研究使用。使用者需自行承擔使用風險。本項目與 Interactive Brokers 公司無任何關聯。

## 📧 聯繫方式

- GitHub: [@vincequant](https://github.com/vincequant)
- 項目主頁: [VKOPTION](https://github.com/vincequant/VKOPTION)

---

<a name="english-version"></a>

# VKOPTION - Interactive Brokers Portfolio Monitor

## 📊 Overview

VKOPTION is an open-source portfolio monitoring system for Interactive Brokers, designed specifically for options traders. It fetches real-time position data via TWS API and displays your portfolio on a clean web dashboard.

### Key Features
- 🔄 **Real-time Sync** - Automatic position updates via TWS API
- 📈 **Options Analytics** - Display Greeks, DTE, strike distance, and more
- 💱 **Multi-currency** - Automatic USD/HKD conversion
- 🌐 **Cloud Ready** - One-click deployment to Railway/Vercel
- 📱 **Responsive** - Works perfectly on desktop and mobile

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Interactive Brokers TWS or IB Gateway
- TWS API enabled (port 7496)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/vincequant/VKOPTION.git
cd VKOPTION
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Run the application**
```bash
python app.py
```

5. **Open browser**
   - Dashboard: http://localhost:8080
   - Test page: http://localhost:8080/test

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational purposes only. Use at your own risk. Not affiliated with Interactive Brokers.