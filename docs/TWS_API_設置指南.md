# TWS API 連接設置指南

## 🔧 TWS 設置步驟

### 1. 打開 TWS (Trader Workstation)

### 2. 進入 API 設置
- 點擊菜單: **File → Global Configuration**
- 選擇左側: **API → Settings**

### 3. 配置 API 設置
請確保以下選項已勾選:
- ✅ **Enable ActiveX and Socket Clients**
- ✅ **Download open orders on connection**
- ✅ **Include FX positions when sending portfolio**
- ✅ **Send status updates for EEP**

### 4. 設置連接參數
- **Socket port**: `7496` (實盤交易)
- **Master API client ID**: `0`
- ✅ **Allow connections from localhost only** (更安全)

### 5. 信任的 IP 地址
在 "Trusted IPs" 區域:
- 點擊 "Create" 添加: `127.0.0.1`
- 這允許本地連接

### 6. API 預警設置 (可選)
如果不想每次都看到彈窗:
- 取消勾選 "Bypass Order Precautions for API orders"
- 或在 "Precautionary Settings" 中調整

### 7. 應用設置
- 點擊 **Apply** 然後 **OK**
- 重啟 TWS 使設置生效

## 🚨 常見問題

### 問題: API 連接超時
**解決方案**:
1. 檢查 TWS 是否有彈窗要求確認連接
2. 檢查防火牆是否阻擋了本地連接
3. 確保沒有其他程序佔用相同的 Client ID

### 問題: "No security definition has been found"
**解決方案**:
- 這是正常的，表示某些合約可能已過期或不存在
- 不影響其他持倉的獲取

### 問題: Socket 連接成功但 API 連接失敗
**解決方案**:
1. 在 TWS 主窗口查看是否有連接請求彈窗
2. 檢查 TWS 右下角的 API 連接狀態圖標
3. 嘗試使用不同的 Client ID (如 123, 456, 789)

## 🔄 測試連接

設置完成後，運行以下命令測試:

```bash
# 測試基本連接
python3 socket_test.py

# 嘗試獲取數據
python3 threaded_api_test.py
```

## 📊 使用測試數據

如果 API 連接仍有問題，可以先使用測試數據查看儀表板:

```bash
# 生成測試數據
python3 generate_test_data.py

# 啟動網頁儀表板
python3 simple_start.py
```

然後訪問: http://localhost:5001

## 💡 提示

1. **首次連接**: TWS 可能會彈出窗口要求確認，請點擊"Accept"
2. **Client ID**: 每個連接必須使用唯一的 Client ID
3. **市場時間**: 某些數據僅在市場開放時間可用
4. **重試**: 如果連接失敗，等待幾秒後重試

## 🔗 有用的資源

- [IB API 文檔](https://interactivebrokers.github.io/)
- [TWS API 設置視頻教程](https://www.youtube.com/watch?v=IWDC9vcUlHQ)
- [常見問題解答](https://www.interactivebrokers.com/en/software/api/apiguide/tables/api_message_codes.htm)