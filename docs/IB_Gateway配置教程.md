# IB Gateway 配置新手教程

本教程将详细指导您如何设置和配置Interactive Broker Gateway，以便与我们的仓位监控系统正常工作。

## 📋 前置条件

### 1. 账户要求
- ✅ 拥有Interactive Broker账户
- ✅ 账户已激活并有实际资金或模拟交易权限
- ✅ 知道您的账户号码和登录凭据

### 2. 软件要求
- ✅ Windows 10+ 或 macOS 10.15+ 或 Linux
- ✅ 稳定的网络连接
- ✅ 至少2GB可用内存

## 🚀 第一步：下载和安装IB Gateway

### 1. 下载IB Gateway
1. 访问IB官网：https://www.interactivebrokers.com
2. 点击"Trading" → "Trading Software" → "IB Gateway"
3. 选择适合您操作系统的版本：
   - **Windows**: IBGateway-standalone-win-x64.exe
   - **macOS**: IBGateway-standalone-macos-x64.dmg
   - **Linux**: IBGateway-standalone-linux-x64.sh

### 2. 安装过程
**Windows用户：**
```bash
# 1. 双击下载的 .exe 文件
# 2. 按照安装向导完成安装
# 3. 默认安装路径：C:\Jts\ibgateway\
```

**macOS用户：**
```bash
# 1. 双击下载的 .dmg 文件
# 2. 将IB Gateway拖拽到Applications文件夹
# 3. 首次运行时允许系统安全设置
```

**Linux用户：**
```bash
# 1. 给安装文件执行权限
chmod +x IBGateway-standalone-linux-x64.sh

# 2. 运行安装程序
./IBGateway-standalone-linux-x64.sh

# 3. 按照提示完成安装
```

## ⚙️ 第二步：IB Gateway 初始配置

### 1. 首次启动配置

1. **启动IB Gateway**
   - Windows: 开始菜单 → IB Gateway
   - macOS: Applications → IB Gateway
   - Linux: 命令行运行 `ibgateway`

2. **登录设置**
   ```
   用户名: [您的IB账户用户名]
   密码: [您的密码]
   交易模式: 
   - Live Trading (实盘交易)
   - Paper Trading (模拟交易) - 推荐新手先使用
   ```

### 2. API设置配置

**重要：这是最关键的步骤！**

1. **启用API访问**
   - 登录后，IB Gateway会显示主界面
   - 点击"Configure" → "Settings" → "API"
   - ✅ 勾选 "Enable ActiveX and Socket Clients"
   - ✅ 勾选 "Allow connections from localhost only" (安全推荐)

2. **端口配置**
   ```
   Socket Port: 7497 (实盘) 或 7498 (模拟)
   ⚠️ 确保端口号与系统配置一致
   ```

3. **客户端ID设置**
   ```
   Master Client ID: 0
   Read-Only API: 不勾选 (我们需要读写权限)
   ```

4. **应用设置**
   - ✅ 点击"OK"保存设置
   - ✅ 重启IB Gateway让设置生效

### 3. 防火墙和网络设置

**Windows防火墙设置：**
```powershell
# 以管理员身份运行PowerShell
New-NetFirewallRule -DisplayName "IB Gateway" -Direction Inbound -Port 7497 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "IB Gateway Paper" -Direction Inbound -Port 7498 -Protocol TCP -Action Allow
```

**macOS防火墙设置：**
1. 系统偏好设置 → 安全性与隐私 → 防火墙
2. 点击"防火墙选项"
3. 添加"IB Gateway"到允许列表

## 🔧 第三步：验证连接

### 1. 手动测试连接

创建一个简单的Python测试脚本：

```python
# test_ib_connection.py
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
import time

class TestWrapper(EWrapper):
    def __init__(self):
        EWrapper.__init__(self)
        self.connected = False
    
    def connectAck(self):
        print("✅ 连接成功！")
        self.connected = True
    
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        print(f"❌ 错误 {errorCode}: {errorString}")

class TestClient(EClient):
    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)

# 测试连接
wrapper = TestWrapper()
client = TestClient(wrapper)

print("🔄 正在连接IB Gateway...")
client.connect("127.0.0.1", 7497, 1)  # 模拟账户用7498

# 等待连接
time.sleep(3)

if wrapper.connected:
    print("🎉 IB Gateway配置成功！")
else:
    print("❌ 连接失败，请检查配置")

client.disconnect()
```

### 2. 运行测试
```bash
# 确保IB Gateway正在运行
python test_ib_connection.py
```

**期望输出：**
```
🔄 正在连接IB Gateway...
✅ 连接成功！
🎉 IB Gateway配置成功！
```

## 📱 第四步：启动仓位监控系统

### 1. 环境配置

创建 `.env` 文件：
```bash
# 复制示例配置
cp .env.example .env

# 编辑配置文件
nano .env
```

修改以下配置：
```env
# IB Gateway配置
IB_HOST=127.0.0.1
IB_PORT=7497    # 实盘交易
# IB_PORT=7498  # 模拟交易
IB_CLIENT_ID=1

# 安全配置
SECRET_KEY=your-unique-secret-key-here
ALLOWED_API_KEYS=your-api-key-here
PUBLIC_ACCESS=true  # 设为false需要API密钥访问
```

### 2. 启动系统
```bash
# 启动所有服务
docker-compose up -d

# 查看日志确认启动成功
docker-compose logs -f backend
```

**成功启动的日志示例：**
```
backend_1  | INFO: Connected to IB Gateway successfully
backend_1  | INFO: Requested position data
backend_1  | INFO: Requested account summary
```

### 3. 访问系统
- 🌐 前端界面: http://localhost:3000
- 📊 API文档: http://localhost:8000/docs
- ❤️ 健康检查: http://localhost:8000/api/health

## 🔍 常见问题排查

### 问题1: "Connection refused" 错误
**可能原因：**
- IB Gateway未启动
- 端口号配置错误
- API设置未启用

**解决方法：**
```bash
# 1. 确认IB Gateway正在运行
ps aux | grep ibgateway

# 2. 检查端口是否开放
netstat -an | grep 7497

# 3. 重新配置API设置
```

### 问题2: "Login failed" 错误
**可能原因：**
- 用户名密码错误
- 账户被锁定
- 网络连接问题

**解决方法：**
1. 验证登录凭据
2. 检查账户状态
3. 尝试网页版登录测试

### 问题3: "Permission denied" 错误
**可能原因：**
- API权限未启用
- 防火墙阻拦
- 客户端ID冲突

**解决方法：**
```bash
# 检查API设置
# 确保"Enable ActiveX and Socket Clients"已勾选

# 更改客户端ID
IB_CLIENT_ID=2  # 尝试不同的ID
```

### 问题4: 数据不更新
**可能原因：**
- 市场休市
- 订阅权限问题
- 网络延迟

**解决方法：**
```bash
# 手动刷新数据
curl -X POST http://localhost:8000/api/refresh

# 检查WebSocket连接
# 浏览器开发者工具 -> Network -> WS
```

## 🛡️ 安全最佳实践

### 1. 生产环境配置
```env
# 生产环境设置
DEBUG=False
PUBLIC_ACCESS=false
SECRET_KEY=use-strong-random-key-here
ALLOWED_API_KEYS=production-key-very-secure
```

### 2. 网络安全
- 🔒 只允许本地连接 (127.0.0.1)
- 🔑 使用强API密钥
- 🚫 不要在公网暴露IB Gateway端口

### 3. 监控和日志
```bash
# 设置日志监控
docker-compose logs -f --tail=100

# 监控连接状态
watch -n 5 "curl -s http://localhost:8000/api/health | jq"
```

## 🆘 获取帮助

如果您遇到问题：

1. **查看日志**
   ```bash
   docker-compose logs backend
   docker-compose logs frontend
   ```

2. **检查系统状态**
   ```bash
   curl http://localhost:8000/api/health
   ```

3. **联系支持**
   - 📧 项目GitHub Issues
   - 📖 IB官方文档: https://interactivebrokers.github.io/tws-api/
   - 🤝 IB客服支持

## ✅ 配置完成检查清单

- [ ] IB Gateway已安装并能正常启动
- [ ] API设置已启用 (Enable ActiveX and Socket Clients)
- [ ] 端口配置正确 (7497/7498)
- [ ] 防火墙规则已添加
- [ ] 测试连接脚本运行成功
- [ ] 系统环境变量配置正确
- [ ] Docker服务启动成功
- [ ] 前端界面可以访问
- [ ] 能看到实时仓位数据

🎉 **恭喜！您已成功配置IB Gateway仓位监控系统！**

现在您可以实时监控您的投资组合，并通过网页界面随时查看仓位状况。