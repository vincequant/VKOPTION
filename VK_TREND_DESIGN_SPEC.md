# VK Trend 完整设计规范文档

## 项目概述
VK Trend 是一个多市场股票分析 Web 应用，提供技术分析工具、实时数据可视化和市场监控功能，支持美股、港股、A股、外汇和加密货币市场。

## 系统架构

### 技术栈
- **后端**: Flask (Python 3.x)
- **前端**: 原生 HTML/CSS/JavaScript (无框架依赖)
- **数据存储**: Excel 文件 (openpyxl)
- **API**: Financial Modeling Prep API
- **异步处理**: aiohttp
- **图表**: Chart.js

### 目录结构
```
vktrend/
├── app.py                 # Flask 主应用
├── index.html            # 主页面
├── chart.html            # 图表页面
├── data/
│   ├── download_stocks.py    # 数据下载脚本
│   ├── get_market_top_stocks.py  # 获取TOP100股票
│   ├── stock_list.json       # 股票列表
│   ├── last_update.json      # 更新时间记录
│   ├── download_progress.json # 下载进度
│   ├── favorites.json        # 收藏列表
│   ├── us.xlsx              # 美股数据
│   ├── hk.xlsx              # 港股数据
│   ├── cn.xlsx              # A股数据
│   ├── forex.xlsx           # 外汇数据
│   └── crypto.xlsx          # 加密货币数据
├── js/
│   ├── stock-list.js        # 股票列表管理
│   ├── chart.js             # 图表功能
│   └── favorites-manager.js  # 收藏管理
└── css/
    └── styles.css           # 样式文件
```

## 核心技术指标计算

### 1. EMA (指数移动平均线) 计算
```python
def calculate_ema(prices, period):
    """计算EMA"""
    ema = []
    multiplier = 2 / (period + 1)
    
    # 第一个EMA值等于第一个价格
    ema.append(prices[0])
    
    # 从第二个值开始计算EMA
    for i in range(1, len(prices)):
        ema_value = (prices[i] * multiplier) + (ema[i-1] * (1 - multiplier))
        ema.append(ema_value)
    
    return ema

# 计算5种EMA
ema16 = calculate_ema(prices, 16)
ema32 = calculate_ema(prices, 32)
ema64 = calculate_ema(prices, 64)
ema128 = calculate_ema(prices, 128)
ema256 = calculate_ema(prices, 256)
```

### 2. 支撑位和阻力位计算

#### S1 (第一支撑位)
```python
# S1 = 短期EMA中的最小值
short_emas = [ema16[-1], ema32[-1], ema64[-1], ema128[-1]]
s1 = min(short_emas)
```

#### S2 (第二支撑位)
```python
# S2 = EMA256
s2 = ema256[-1]
```

#### R1 (第一阻力位)
```python
# R1 = 短期EMA中的最大值
r1 = max(short_emas)
```

#### R2 (第二阻力位)
```python
# R2 = 基于历史价格计算的动态阻力位
def calculate_r2(prices, ema16, ema32, ema64, ema128):
    # 计算价格相对于各EMA的偏离度
    price_ratios = []
    
    for i in range(len(prices)):
        ratios = []
        for ema in [ema16, ema32, ema64, ema128]:
            if i < len(ema) and ema[i] > 0:
                ratio = prices[i] / ema[i]
                ratios.append(ratio)
        
        if ratios:
            avg_ratio = sum(ratios) / len(ratios)
            price_ratios.append(avg_ratio)
    
    # 使用95百分位作为极端偏离度
    extreme_ratio = np.percentile(price_ratios, 95)
    
    # R2 = 当前均线均值 × 极端偏离度
    current_ema_avg = np.mean([ema16[-1], ema32[-1], ema64[-1], ema128[-1]])
    r2 = current_ema_avg * extreme_ratio
    
    return r2
```

### 3. SP值计算
```python
# SP = 基准值 / S1
# 基准值默认为2500，可由用户自定义
sp_value = base_value / s1 if s1 > 0 else None
```

### 4. DS天数计算
```python
def calculate_ds_days(prices, dates, s2_values):
    """
    DS天数：价格跌破S2后开始累计天数，
    直到突破MAX[R1,S1,S2]时停止
    """
    ds_days = 0
    is_counting = False
    
    for i in range(len(prices)):
        current_price = prices[i]
        s2 = s2_values[i]
        
        # 计算突破阈值
        threshold = max(r1_values[i], s1_values[i], s2)
        
        if current_price < s2 and not is_counting:
            # 开始计数
            is_counting = True
            ds_days = 1
        elif is_counting:
            if current_price > threshold:
                # 停止计数
                is_counting = False
            else:
                # 继续累加
                ds_days += 1
    
    return ds_days
```

### 5. H3/L3 计算
```python
def calculate_h3_l3(prices, dates, start_date):
    """
    H3: 指定日期后的最高价
    L3: 指定日期后的最低价
    """
    # 筛选指定日期后的数据
    filtered_prices = []
    for i, date in enumerate(dates):
        if date >= start_date:
            filtered_prices.append(prices[i])
    
    if filtered_prices:
        h3 = max(filtered_prices)
        l3 = min(filtered_prices)
    else:
        h3 = l3 = None
    
    return h3, l3
```

### 6. 黄金交叉/死亡交叉计算

#### 黄金交叉天数 (Golden Cross Days)
```python
def calculate_golden_cross_days(prices, ema16, ema256):
    """
    黄金交叉天数：EMA16 > EMA256 的持续天数
    
    公式：
    - 条件：EMA16 > EMA256
    - 从最新数据开始向前计算
    - 计算条件持续满足的天数
    - 当 EMA16 <= EMA256 时停止计数
    """
    # 获取最新有效数据
    latest_idx = -1
    for i in range(len(prices) - 1, -1, -1):
        if i < len(ema16) and i < len(ema256) and ema16[i] is not None and ema256[i] is not None:
            latest_idx = i
            break
    
    if latest_idx == -1:
        return 0
    
    # 检查当前是否处于黄金交叉状态
    if ema16[latest_idx] <= ema256[latest_idx]:
        return 0
    
    # 计算持续天数
    golden_cross_days = 0
    for i in range(latest_idx, -1, -1):
        if i >= len(ema16) or i >= len(ema256):
            break
        if ema16[i] is None or ema256[i] is None:
            break
            
        if ema16[i] > ema256[i]:  # 短期均线在长期均线上方
            golden_cross_days += 1
        else:
            break  # 找到交叉点，停止计数
    
    return golden_cross_days
```

#### 死亡交叉天数 (Death Cross Days)
```python
def calculate_death_cross_days(prices, ema16, ema256):
    """
    死亡交叉天数：EMA256 > EMA16 的持续天数
    
    公式：
    - 条件：EMA256 > EMA16
    - 从最新数据开始向前计算
    - 计算条件持续满足的天数
    - 当 EMA256 <= EMA16 时停止计数
    """
    # 获取最新有效数据
    latest_idx = -1
    for i in range(len(prices) - 1, -1, -1):
        if i < len(ema16) and i < len(ema256) and ema16[i] is not None and ema256[i] is not None:
            latest_idx = i
            break
    
    if latest_idx == -1:
        return 0
    
    # 检查当前是否处于死亡交叉状态
    if ema256[latest_idx] <= ema16[latest_idx]:
        return 0
    
    # 计算持续天数
    death_cross_days = 0
    for i in range(latest_idx, -1, -1):
        if i >= len(ema16) or i >= len(ema256):
            break
        if ema16[i] is None or ema256[i] is None:
            break
            
        if ema256[i] > ema16[i]:  # 长期均线在短期均线上方
            death_cross_days += 1
        else:
            break  # 找到交叉点，停止计数
    
    return death_cross_days
```

#### 交叉信号说明
- **黄金交叉（Golden Cross）**：短期均线（EMA16）向上突破长期均线（EMA256），通常被视为买入信号
- **死亡交叉（Death Cross）**：长期均线（EMA256）向上突破短期均线（EMA16），通常被视为卖出信号
- **持续天数**：表示当前交叉状态已经持续了多少个交易日
- **应用场景**：
  - 黄金交叉天数 > 0：股票处于上升趋势
  - 死亡交叉天数 > 0：股票处于下降趋势
  - 天数越大，趋势越稳定

## API 集成

### 1. Financial Modeling Prep API

#### 获取股票报价
```python
API_KEY = "sFc5p2fbvwbYgbNo9IZDdqK8fMtn34zm"

async def fetch_stock_quotes(symbols):
    """批量获取股票报价"""
    batch_size = 50  # FMP API 限制
    batches = [symbols[i:i+batch_size] for i in range(0, len(symbols), batch_size)]
    
    all_data = []
    async with aiohttp.ClientSession() as session:
        for batch in batches:
            symbols_str = ",".join(batch)
            url = f"https://financialmodelingprep.com/api/v3/quote/{symbols_str}?apikey={API_KEY}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    all_data.extend(data)
    
    return all_data
```

#### 获取历史价格
```python
async def fetch_historical_prices(symbol, days=400):
    """获取历史价格数据"""
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}?timeseries={days}&apikey={API_KEY}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('historical', [])
    
    return []
```

### 2. 获取TOP成交额股票

#### 股票市场 (美股/港股/A股)
```python
def get_top_volume_stocks_by_market(market, limit=100):
    """获取指定市场成交额最大的股票"""
    
    if market == 'us':
        # 使用 Stock Screener API
        params = {
            'exchange': 'NYSE,NASDAQ',
            'limit': limit * 2,  # 获取更多以便筛选
            'apikey': API_KEY
        }
        
        response = requests.get(
            'https://financialmodelingprep.com/api/v3/stock-screener',
            params=params
        )
        
        if response.status_code == 200:
            stocks = response.json()
            # 计算成交额并排序
            for stock in stocks:
                stock['dollarVolume'] = stock.get('price', 0) * stock.get('volume', 0)
            
            stocks.sort(key=lambda x: x['dollarVolume'], reverse=True)
            return [s['symbol'] for s in stocks[:limit]]
    
    elif market == 'hk':
        # 香港市场使用 exchange=HKSE
        params = {
            'exchange': 'HKSE',
            'limit': limit * 2,
            'apikey': API_KEY
        }
        # 类似处理...
    
    # 其他市场类似...
```

#### 加密货币市场 (动态获取)
```python
def get_crypto_pairs(limit=30):
    """获取CoinMarketCap成交额前30的加密货币对"""
    try:
        # 使用CoinMarketCap公开API
        url = 'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing'
        params = {
            'start': '1',
            'limit': str(limit),
            'sortBy': 'volume',  # 按成交额排序
            'sortType': 'desc',
            'convert': 'USD'
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'data' in data and 'cryptoCurrencyList' in data['data']:
            crypto_list = data['data']['cryptoCurrencyList']
            crypto_pairs = []
            
            for crypto in crypto_list[:limit]:
                symbol = crypto.get('symbol', '')
                # 排除稳定币
                if symbol and symbol not in ['USDT', 'USDC', 'BUSD', 'DAI']:
                    crypto_pairs.append(f"{symbol}USD")
            
            return crypto_pairs[:limit]
            
    except Exception as e:
        # 使用默认列表作为备用
        return default_crypto_pairs[:limit]
```

#### 外汇市场
```python
def get_forex_pairs(limit=10):
    """获取主要外汇对（前10个最活跃的）"""
    major_pairs = [
        'EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD', 'USDCAD',
        'USDCHF', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY'
    ]
    return major_pairs[:limit]
```

## 数据存储结构

### Excel 文件结构
每个市场的 Excel 文件包含两个工作表：

#### 1. data 工作表
| 列名 | 类型 | 说明 |
|------|------|------|
| symbol | string | 股票代码 |
| name | string | 股票名称 |
| price | float | 当前价格 |
| changesPercentage | float | 涨跌幅 |
| marketCap | float | 市值 |
| volume | float | 成交量 |
| r1 | float | 第一阻力位 |
| r2 | float | 第二阻力位 |
| s1 | float | 第一支撑位 |
| s2 | float | 第二支撑位 |
| r1_percent | float | R1相对价格百分比 |
| r2_percent | float | R2相对价格百分比 |
| s1_percent | float | S1相对价格百分比 |
| s2_percent | float | S2相对价格百分比 |
| sp | float | SP值 |
| ds_days | int | DS天数 |
| h3 | float | H3最高价 |
| l3 | float | L3最低价 |
| ema16 | float | 16日EMA |
| ema32 | float | 32日EMA |
| ema64 | float | 64日EMA |
| ema128 | float | 128日EMA |
| ema256 | float | 256日EMA |

#### 2. lastUpdate 工作表
| 列名 | 类型 | 说明 |
|------|------|------|
| lastUpdate | string | 最后更新时间 |

### JSON 文件结构

#### stock_list.json
```json
{
  "us": ["AAPL", "MSFT", "GOOGL", ...],
  "hk": ["0700.HK", "9988.HK", ...],
  "cn": ["600519.SS", "000001.SZ", ...],
  "forex": ["EURUSD", "USDJPY", ...],
  "crypto": ["BTCUSD", "ETHUSD", ...]
}
```

#### last_update.json
```json
{
  "lastUpdate": "2025-06-21 19:49:53",
  "statsMarkets": {
    "us": 100,
    "hk": 199,
    "cn": 441
  },
  "totalStocks": 740,
  "markets": ["us", "hk", "cn"]
}
```

#### download_progress.json
```json
{
  "status": "running",
  "progress": 45,
  "message": "正在计算技术指标... (45/100只完成)",
  "timestamp": 1750506593.999,
  "market": "us",
  "current_stocks": ["AAPL", "MSFT", "GOOGL"],
  "detail": "计算EMA、支撑位、阻力位、DS天数等指标"
}
```

## Flask API 端点

### 1. 获取股票数据
```python
@app.route('/api/excel/stocks', methods=['GET'])
def get_excel_stocks():
    """
    获取所有股票数据
    参数:
        category: 市场分类 (us/hk/cn/forex/crypto/all)
    返回:
        {
            "stocks": [...],
            "count": 100,
            "lastUpdate": "2025-06-21 19:49:53",
            "marketUpdates": {"us": "...", "hk": "..."}
        }
    """
```

### 2. 更新股票数据
```python
@app.route('/api/update-stocks-data', methods=['POST'])
def update_stocks_data():
    """
    触发指定市场的数据更新
    请求体:
        {
            "market": "us"  // 市场代码
        }
    """
```

### 3. 获取更新进度
```python
@app.route('/api/update-progress', methods=['GET'])
def get_update_progress():
    """
    获取数据更新进度
    返回:
        {
            "status": "running",
            "progress": 45,
            "message": "正在计算技术指标...",
            "timestamp": 1750506593.999
        }
    """
```

### 4. 收藏管理
```python
@app.route('/api/favorites', methods=['GET', 'POST'])
@app.route('/api/favorites/add/<symbol>', methods=['POST'])
@app.route('/api/favorites/remove/<symbol>', methods=['POST'])
```

## 前端实现

### 1. 股票列表显示
```javascript
// 加载并显示股票数据
async function loadStockData() {
    const response = await fetch('/api/excel/stocks');
    const data = await response.json();
    
    // 更新显示
    allStocks = data.stocks || [];
    lastUpdateTime = data.lastUpdate;
    
    // 筛选和排序
    filterAndDisplayStocks();
}

// 筛选逻辑
function filterStocks(stocks) {
    return stocks.filter(stock => {
        // 价格筛选
        if (filterConfig.minPrice && stock.price < filterConfig.minPrice) return false;
        if (filterConfig.maxPrice && stock.price > filterConfig.maxPrice) return false;
        
        // 支撑阻力位筛选
        if (filterConfig.belowS1 && stock.price >= stock.s1) return false;
        if (filterConfig.aboveR1 && stock.price <= stock.r1) return false;
        
        // 其他筛选条件...
        return true;
    });
}
```

### 2. 进度条更新
```javascript
async function pollUpdateProgress(marketName) {
    const pollInterval = setInterval(async () => {
        const response = await fetch('/api/update-progress');
        const progressData = await response.json();
        
        if (progressData.status === 'running') {
            updateProgress(progressData.progress, progressData.message);
        } else if (progressData.status === 'completed') {
            updateProgress(100, `${marketName}数据更新完成！`);
            clearInterval(pollInterval);
            // 刷新数据
            loadStockData();
        }
    }, 1000);
}
```

### 3. 排序功能
```javascript
function sortStocks(column, direction) {
    currentStocks.sort((a, b) => {
        let aVal = a[column];
        let bVal = b[column];
        
        // 处理空值
        if (aVal === null || aVal === undefined) aVal = -Infinity;
        if (bVal === null || bVal === undefined) bVal = -Infinity;
        
        // 数字排序
        if (typeof aVal === 'number' && typeof bVal === 'number') {
            return direction === 'asc' ? aVal - bVal : bVal - aVal;
        }
        
        // 字符串排序
        return direction === 'asc' ? 
            String(aVal).localeCompare(String(bVal)) : 
            String(bVal).localeCompare(String(aVal));
    });
}
```

## 性能优化

### 1. 异步批量处理
```python
async def process_stocks_async(stocks, batch_size=20):
    """异步批量处理股票数据"""
    batches = [stocks[i:i+batch_size] for i in range(0, len(stocks), batch_size)]
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for batch in batches:
            task = process_batch(session, batch)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
    
    return [item for batch in results for item in batch]
```

### 2. 数据缓存
```python
# 内存缓存
excel_data_cache = {}
cache_timestamp = {}

def read_stocks_from_excel_cached(category):
    """带缓存的Excel读取"""
    cache_key = f"{category}_stocks"
    
    # 检查缓存是否有效（5分钟）
    if cache_key in excel_data_cache:
        if time.time() - cache_timestamp.get(cache_key, 0) < 300:
            return excel_data_cache[cache_key]
    
    # 读取新数据
    data = read_stocks_from_excel()
    excel_data_cache[cache_key] = data
    cache_timestamp[cache_key] = time.time()
    
    return data
```

## 部署配置

### 1. 端口自动切换
```python
def find_available_port(start_port=5000, max_attempts=6):
    """查找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result != 0:
            return port
    return None
```

### 2. 路径兼容性
```python
# 支持 PythonAnywhere 部署
if 'pythonanywhere' in os.getcwd():
    BASE_DIR = '/home/vkquant/Trend'
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

## 错误处理

### 1. API 错误处理
```python
try:
    response = await session.get(url)
    if response.status == 429:
        # 速率限制
        await asyncio.sleep(60)
        return await fetch_with_retry(url)
    elif response.status != 200:
        print(f"API错误: {response.status}")
        return None
except Exception as e:
    print(f"网络错误: {e}")
    return None
```

### 2. 数据验证
```python
def validate_stock_data(stock):
    """验证股票数据完整性"""
    required_fields = ['symbol', 'price', 'name']
    
    for field in required_fields:
        if field not in stock or stock[field] is None:
            return False
    
    # 验证数值范围
    if stock['price'] <= 0:
        return False
    
    return True
```

## 运行命令

### 开发环境
```bash
# 安装依赖
pip install flask pandas requests aiohttp openpyxl numpy

# 启动服务器
python app.py

# 更新数据（使用TOP 100成交额股票）
python data/download_stocks.py
```

### 生产环境
```bash
# 使用 gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# 定时更新数据 (crontab)
0 */6 * * * cd /path/to/vktrend && python data/download_stocks.py
```

## 关键特性总结

1. **多市场支持**: 
   - 美股、港股、A股：动态获取成交额TOP 100
   - 外汇：前10个主要货币对
   - 加密货币：动态获取CoinMarketCap成交额TOP 30

2. **技术指标**: 
   - EMA (16, 32, 64, 128, 256)
   - 支撑阻力位 (S1, S2, R1, R2)
   - SP值、DS天数、H3/L3
   - 黄金交叉/死亡交叉天数

3. **动态数据获取**:
   - 股票：基于Financial Modeling Prep API的成交额排名
   - 加密货币：实时从CoinMarketCap获取成交额排名
   - 包含备用方案和默认列表

4. **实时进度**: 
   - 详细的更新进度反馈
   - 分阶段进度显示（报价获取、技术分析、文件保存）

5. **高性能**: 
   - 异步处理、批量操作
   - 数据缓存机制
   - 自动端口切换

6. **用户友好**: 
   - 排序、筛选、收藏管理
   - 多语言支持（中文/英文）
   - 响应式设计，支持移动端

## 最新更新

### 2025年6月更新
1. **加密货币动态获取**：
   - 集成CoinMarketCap API获取实时成交额TOP 30
   - 添加网页爬虫备用方案
   - 自动排除稳定币（USDT、USDC等）

2. **外汇市场优化**：
   - 将默认货币对从30个减少到10个最主要的
   - 保留扩展到30个的能力

3. **进度条增强**：
   - 显示详细的批次信息和当前处理股票
   - 实时更新百分比和状态描述

这份设计文档包含了完整的技术实现细节，可以用于在其他项目中复刻相同功能。