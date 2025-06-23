# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Interactive Brokers (IB) position monitoring system that fetches real-time portfolio data via TWS API and displays it in a web dashboard. Supports US options, HK options, and stocks with automatic price updates and expiration value calculations.

## Development Commands

### Running the Application
```bash
# Use virtual environment (recommended)
/Users/vk/Library/CloudStorage/Dropbox/Vkquantapp/IB倉位監控/ib_env/bin/python app.py

# Or use the startup script
./start.sh

# Access the application
# Main dashboard: http://localhost:8080
# Test page: http://localhost:8080/test
```

### Testing Specific Components
```bash
# Test TWS connection
./ib_env/bin/python test_connection.py

# Test Hong Kong options
./ib_env/bin/python test_hk_options.py

# Test PnL and Greeks
./ib_env/bin/python test_pnl_greeks.py

# Test HSI pricing
./ib_env/bin/python test_hsi_pricing.py

# Test VXX stock price
./ib_env/bin/python test_vxx_price.py
```

### Frontend Development (cloud-frontend)
```bash
cd cloud-frontend
npm run dev        # Development server
npm run build      # Production build
npm run lint       # Run ESLint
npm run type-check # TypeScript type checking
```

## Architecture Overview

### Core Components

1. **EnhancedIBClient (app.py:166-872)**
   - Multi-inheritance adapter pattern combining EWrapper and EClient
   - Event-driven architecture with callback methods
   - Thread-safe state management using dictionaries and threading events
   - Request ID mapping for tracking asynchronous operations

2. **Data Flow Pipeline**
   ```
   TWS API → EnhancedIBClient → JSON File → Flask API → Web Dashboard
                                    ↓
                              FMP API (stock prices)
   ```

3. **Update Mechanisms**
   - **Auto-connect on startup**: Establishes TWS connection and fetches initial data
   - **Manual updates**: `/api/update` endpoint with thread locking
   - **Auto-refresh**: Background thread updates every 300 seconds
   - **Real-time subscriptions**: Market data streams for positions

4. **Error Handling Strategy**
   - Categorized errors: Informational (ignored), Expected (warnings), Real (errors)
   - Error tracking with timestamps and symbol mapping
   - Subscription error tracking for UI alerts
   - Graceful degradation with cached data fallback

### Key Data Structures

**portfolio_data_enhanced.json**
```json
{
  "last_update": "timestamp",
  "positions": [
    {
      "symbol": "AAPL",
      "contract_type": "Option/Stock",
      "position": -5,
      "avg_cost": 1.5,
      "current_price": 1.2,
      "market_value": -600,
      "unrealized_pnl": 150,
      "has_market_data": true,
      "has_pnl_data": true,
      "underlying_price": 150.00,
      "distance_percent": 5.2,
      "actual_expiration_value": 750
    }
  ],
  "summary": {
    "net_liquidation": 100000,
    "total_cash": 50000,
    "us_options_expiration_value": 5000
  },
  "subscription_errors": ["SYMBOL1", "SYMBOL2"]
}
```

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Main dashboard (dashboard_new.html) |
| GET | `/test` | API test page (test_api_data.html) |
| GET | `/api/portfolio` | Get current portfolio data |
| POST | `/api/update` | Trigger portfolio data update |
| GET | `/api/status` | System connection status |
| POST | `/api/stock-prices` | Fetch stock prices from FMP API |
| GET | `/api/cloud-config` | Get cloud upload configuration |
| POST | `/api/cloud-config` | Update cloud upload settings |
| POST | `/api/upload-to-cloud` | Upload data to cloud endpoint |

### Threading Model

1. **Main Thread**: Flask web server
2. **IB API Thread**: Daemon thread running EClient.run()
3. **Auto-update Thread**: Periodic data refresh loop
4. **Timer Callbacks**: Delayed operations (e.g., dataCollectionComplete)

Thread synchronization:
- `update_lock`: Mutex preventing concurrent updates
- `connection_ready`: Event signaling TWS connection established
- `update_complete`: Event signaling data collection finished
- `market_data_ready`: Event signaling market data received

### Configuration (app.py:37-47)

```python
CONFIG = {
    'TWS_HOST': '127.0.0.1',
    'TWS_PORT': 7496,
    'CLIENT_ID': 9999,          # High ID to avoid conflicts
    'SERVER_PORT': 8080,
    'AUTO_UPDATE_INTERVAL': 300, # 5 minutes
    'FMP_API_KEY': 'xxx',       # Financial Modeling Prep API
}
```

### TWS API Integration Notes

1. **Connection Requirements**
   - TWS must be running with API enabled (port 7496)
   - Read-Only API checkbox should be checked
   - Client ID 9999 avoids conflicts with other applications

2. **Market Data Subscriptions**
   - Some stocks/options require paid subscriptions (e.g., BATS for VXX)
   - Hong Kong options may have contract definition issues
   - System tracks subscription errors and displays warnings

3. **Option Contract Handling**
   - Automatically sets exchange to "SMART" if not specified
   - Calculates distance from strike and actual expiration values
   - Special handling for Short Put positions

### Frontend Architecture

**dashboard_new.html**
- Tab-based UI for US options, HK options, and stocks
- Real-time updates via polling `/api/portfolio`
- Sortable tables with custom formatting
- Dynamic expiration value calculations
- Subscription warning system

**Key JavaScript Functions**
- `updateDashboard()`: Main update loop
- `calculateSummaryData()`: Aggregates statistics
- `formatOptionsTable()`: Renders option positions
- `updateStockPrices()`: Fetches external price data
- `switchPositionTab()`: Tab navigation

### Development Patterns

1. **Error Recovery**: Always check TWS connection before operations
2. **Data Persistence**: JSON file serves as cache between restarts
3. **API Rate Limiting**: Batch requests when possible
4. **Resource Cleanup**: Proper shutdown via atexit handlers
5. **Logging**: Comprehensive logging for debugging

### Common Issues & Solutions

1. **Connection Failed**: Ensure TWS is running and API is enabled
2. **Missing Prices**: Check market data subscriptions or FMP API key
3. **HK Options Errors**: Known issue with contract definitions
4. **Update Hangs**: Check for thread deadlocks in logs
5. **Port Conflicts**: Change CLIENT_ID if needed

## Current Development Focus

Recent updates have focused on:
- Option expiration value calculations with underlying price consideration
- Tab-based UI organization
- Subscription error tracking and warnings
- Integration with Financial Modeling Prep API
- Project structure optimization (reduced from 40+ to 19 core files)

See README.md for user-facing documentation and deployment instructions.