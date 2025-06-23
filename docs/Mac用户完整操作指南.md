# Mac用户完整操作指南

## 📥 第一步：下载和安装 IB Gateway

### 1.1 下载 IB Gateway
访问官方下载页面：
- **稳定版本（推荐）**：https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
- **最新版本**：https://www.interactivebrokers.com/en/trading/ibgateway-latest.php

**选择版本：**
- 如果您的Mac是 M1/M2/M3 芯片：选择 "Mac OS X with Apple Silicon"
- 如果您的Mac是 Intel 芯片：选择 "Mac OS X"

### 1.2 安装过程
```bash
# 1. 下载完成后，在 Downloads 文件夹找到 .dmg 文件
# 2. 双击 .dmg 文件打开
# 3. 将 IB Gateway 图标拖拽到 Applications 文件夹
# 4. 安装完成后，可以在 Applications 中找到 IB Gateway
```

### 1.3 首次启动授权
```bash
# 首次运行时，系统会显示安全警告
# 解决方法：
# 1. 打开 "系统偏好设置" > "安全性与隐私"
# 2. 点击 "通用" 标签页
# 3. 点击 "仍要打开" 允许 IB Gateway 运行
```

## ⚙️ 第二步：配置 IB Gateway

### 2.1 启动 IB Gateway
```bash
# 方法1：从 Applications 文件夹启动
open /Applications/IB\ Gateway.app

# 方法2：使用 Spotlight 搜索
# Command + Space，然后输入 "IB Gateway"
```

### 2.2 登录配置
当 IB Gateway 启动后，您会看到登录界面：

```
用户名: [您的IB账户用户名]
密码: [您的密码]
交易模式: 
  - Live Trading (实盘交易) - 如果您有真实资金
  - Paper Trading (模拟交易) - 推荐新手先使用
```

**重要提示：**
- 🔴 **实盘交易**：端口 7497，需要真实资金
- 🟢 **模拟交易**：端口 7498，推荐新手练习

### 2.3 关键API设置
登录成功后，进行以下设置：

1. **启用API访问**
   - 在IB Gateway界面，点击 "Configure" > "Settings" > "API"
   - ✅ **必须勾选**: "Enable ActiveX and Socket Clients"
   - ✅ **安全设置**: "Allow connections from localhost only"

2. **端口设置**
   ```
   Socket Port: 7498 (模拟交易) 或 7497 (实盘交易)
   Master Client ID: 0
   Read-Only API: 不要勾选
   ```

3. **保存设置**
   - 点击 "OK" 保存
   - **重要**: 必须重启 IB Gateway 让设置生效

## 🛡️ 第三步：macOS 安全设置

### 3.1 防火墙配置
```bash
# 如果启用了 macOS 防火墙，需要允许连接
# 1. 打开 "系统偏好设置" > "安全性与隐私" > "防火墙"
# 2. 点击 "防火墙选项"
# 3. 添加 "IB Gateway" 到允许列表
# 4. 选择 "允许传入连接"
```

### 3.2 网络权限
```bash
# 如果系统询问网络权限，请选择 "允许"
# IB Gateway 需要网络访问来连接到IB服务器
```

## 🔧 第四步：设置监控系统

### 4.1 创建项目目录
```bash
# 进入您想要放置项目的目录
cd ~/Desktop
# 或者
cd ~/Documents

# 如果项目已存在，进入项目目录
cd "IB倉位監控"
```

### 4.2 配置环境文件
```bash
# 复制环境配置模板
cp .env.example .env

# 使用文本编辑器打开配置文件
open -a TextEdit .env
# 或者使用其他编辑器，如：
# nano .env
# code .env (如果安装了VS Code)
```

### 4.3 修改配置文件
在 `.env` 文件中修改以下设置：

```env
# IB Gateway连接配置
IB_HOST=127.0.0.1
IB_PORT=7498          # 模拟交易用7498，实盘交易用7497
IB_CLIENT_ID=1

# 数据库配置（默认即可）
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://postgres:password@localhost:5432/ib_monitor

# 安全配置
SECRET_KEY=your-unique-secret-key-here-please-change-this
ALLOWED_API_KEYS=demo-key-123,your-custom-api-key
PUBLIC_ACCESS=true   # 设为true允许无密钥访问，false需要API密钥

# 应用配置
DEBUG=True
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
```

## 🚀 第五步：启动监控系统

### 5.1 检查 Docker 安装
```bash
# 检查 Docker 是否已安装
docker --version
docker-compose --version

# 如果未安装，请访问 https://www.docker.com/products/docker-desktop
# 下载 Docker Desktop for Mac
```

### 5.2 启动系统
```bash
# 方法1：使用一键部署脚本（推荐）
./scripts/deploy.sh

# 方法2：手动启动
docker-compose up -d
```

### 5.3 等待服务启动
```bash
# 查看启动日志
docker-compose logs -f

# 等待看到这些成功信息：
# ✅ "Connected to IB Gateway successfully"
# ✅ "Requested position data"  
# ✅ "Requested account summary"
```

## 🌐 第六步：访问系统

### 6.1 打开浏览器访问
- **前端界面**: http://localhost:3000
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/api/health

### 6.2 验证连接状态
在前端界面中，您应该看到：
- 🟢 连接状态显示为 "已连接"
- 📊 如果有持仓，会显示仓位数据
- ⏰ 最后更新时间会实时刷新

## 🔍 第七步：测试连接

### 7.1 创建测试脚本
创建文件 `test_connection.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time

def test_connection():
    """测试系统连接状态"""
    
    print("🔄 测试IB仓位监控系统连接...")
    
    try:
        # 测试健康检查
        print("\n1️⃣ 测试API健康状况...")
        health_response = requests.get("http://localhost:8000/api/health", timeout=5)
        
        if health_response.status_code == 200:
            health_data = health_response.json()
            print("✅ API服务正常")
            print(f"   IB连接状态: {'✅ 已连接' if health_data.get('ib_connected') else '❌ 未连接'}")
            print(f"   Redis状态: {'✅ 正常' if health_data.get('redis_connected') else '❌ 异常'}")
            print(f"   WebSocket连接数: {health_data.get('active_websockets', 0)}")
        else:
            print(f"❌ API健康检查失败: {health_response.status_code}")
            return False
            
        # 测试仓位数据
        print("\n2️⃣ 测试仓位数据获取...")
        positions_response = requests.get("http://localhost:8000/api/positions", timeout=10)
        
        if positions_response.status_code == 200:
            positions_data = positions_response.json()
            print("✅ 仓位数据获取成功")
            print(f"   数据来源: {positions_data.get('source', 'unknown')}")
            print(f"   仓位数量: {len(positions_data.get('positions', []))}")
            print(f"   更新时间: {positions_data.get('timestamp', 'unknown')}")
            
            if positions_data.get('positions'):
                print("   持仓详情:")
                for pos in positions_data['positions'][:3]:  # 只显示前3个
                    print(f"     • {pos.get('symbol', 'N/A')}: {pos.get('position', 0)} 股")
        else:
            print(f"❌ 仓位数据获取失败: {positions_response.status_code}")
            
        # 测试账户信息
        print("\n3️⃣ 测试账户信息获取...")
        account_response = requests.get("http://localhost:8000/api/account", timeout=10)
        
        if account_response.status_code == 200:
            account_data = account_response.json()
            print("✅ 账户信息获取成功")
            print(f"   账户数量: {len(account_data.get('accounts', []))}")
            
            if account_data.get('accounts'):
                for acc in account_data['accounts']:
                    print(f"   账户: {acc.get('account', 'N/A')}")
                    print(f"     净资产: ${acc.get('net_liquidation', 0):,.2f}")
        else:
            print(f"❌ 账户信息获取失败: {account_response.status_code}")
            
        print("\n🎉 连接测试完成！")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到API服务，请检查：")
        print("   1. Docker服务是否正在运行: docker-compose ps")
        print("   2. 端口是否被占用: lsof -i :8000")
        return False
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        return False

if __name__ == "__main__":
    test_connection()
```

### 7.2 运行测试
```bash
# 运行连接测试
python3 test_connection.py
```

## 🆘 常见问题解决

### Q1: IB Gateway 无法启动
```bash
# 解决方法：
# 1. 检查 macOS 版本兼容性
system_profiler SPSoftwareDataType

# 2. 重新下载对应版本（Intel vs Apple Silicon）
# 3. 检查安全设置是否允许运行
```

### Q2: API连接被拒绝
```bash
# 检查IB Gateway设置：
# 1. 确认已勾选 "Enable ActiveX and Socket Clients"
# 2. 确认端口号正确（7497或7498）
# 3. 重启IB Gateway让设置生效
```

### Q3: Docker服务无法启动
```bash
# 检查Docker状态
docker info

# 重启Docker Desktop
# 在应用程序中找到Docker，重新启动

# 检查端口占用
lsof -i :8000
lsof -i :3000
```

### Q4: 浏览器无法访问
```bash
# 检查服务状态
docker-compose ps

# 查看服务日志
docker-compose logs frontend
docker-compose logs backend

# 重启服务
docker-compose restart
```

## ✅ 完成检查清单

- [ ] 已下载并安装 IB Gateway
- [ ] 已登录IB Gateway（模拟或实盘账户）
- [ ] 已启用API设置 "Enable ActiveX and Socket Clients"
- [ ] 已设置正确的端口号（7497或7498）
- [ ] 已重启IB Gateway让设置生效
- [ ] 已安装Docker Desktop for Mac
- [ ] 已配置 .env 环境文件
- [ ] 已成功启动监控系统
- [ ] 能够访问 http://localhost:3000
- [ ] 连接测试脚本运行成功

## 🎯 下一步

完成以上步骤后，您就拥有了一个完整的IB仓位监控系统！

**您可以：**
- 📊 实时查看持仓情况
- 📈 监控盈亏变化  
- 📱 通过手机浏览器访问
- 🔄 设置自动刷新间隔
- 🛡️ 配置API密钥保护数据

**如果遇到问题：**
- 查看日志：`docker-compose logs -f`
- 重启服务：`docker-compose restart`
- 检查IB Gateway连接状态
- 运行测试脚本验证连接