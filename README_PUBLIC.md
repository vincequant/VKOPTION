# VKOption - Interactive Brokers Portfolio Monitor

An open-source portfolio monitoring system for Interactive Brokers TWS API, featuring real-time position tracking and web dashboard visualization.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## 🌟 Features

- **Real-time Portfolio Monitoring**: Track stocks and options positions via TWS API
- **Web Dashboard**: Clean, responsive interface for position visualization
- **Options Analytics**: 
  - Greeks display
  - Days to expiration tracking
  - Strike distance calculations
  - P&L analysis
- **Multi-currency Support**: USD/HKD conversion
- **Auto-refresh**: Configurable automatic data updates
- **Cloud Deployment Ready**: Supports Railway/Vercel deployment

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Interactive Brokers TWS or IB Gateway
- TWS API enabled (port 7496)

### Installation

1. Clone the repository
```bash
git clone https://github.com/vincequant/vkoption.git
cd vkoption
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure environment
```bash
cp .env.example .env
# Edit .env with your settings
```

4. Run the application
```bash
python app.py
```

5. Open browser to `http://localhost:8080`

## 📖 Documentation

### TWS Configuration
1. Enable API connections in TWS
2. File → Global Configuration → API → Settings
3. Enable "Enable ActiveX and Socket Clients"
4. Set Socket port to 7496

### Environment Variables
- `TWS_HOST`: TWS connection host (default: 127.0.0.1)
- `TWS_PORT`: TWS API port (default: 7496)
- `CLIENT_ID`: API client ID (default: 8888)
- `FMP_API_KEY`: Financial Modeling Prep API key (optional)

## 🛠️ Development

### Project Structure
```
vkoption/
├── app.py              # Main Flask application
├── static/             # Static HTML files
├── requirements.txt    # Python dependencies
├── railway.json       # Railway deployment config
└── README.md          # This file
```

### API Endpoints
- `GET /` - Main dashboard
- `GET /api/portfolio` - Get portfolio data
- `POST /api/update` - Update portfolio from TWS
- `GET /api/status` - System status

## 🚀 Deployment

### Railway
1. Fork this repository
2. Connect to Railway
3. Set environment variables
4. Deploy

### Local Development
```bash
./start.sh
```

## 🔒 Security Note

This is a personal portfolio monitoring tool. Never commit sensitive data:
- Account numbers
- API keys
- Position data
- Personal information

## 📄 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## ⚠️ Disclaimer

This software is for educational purposes only. Use at your own risk. Not affiliated with Interactive Brokers.

## 📧 Contact

- GitHub: [@vincequant](https://github.com/vincequant)
- Project: [VKOption](https://github.com/vincequant/vkoption)

---

**Note**: This project requires an Interactive Brokers account and TWS API access. Position data is fetched locally and never transmitted to third parties.