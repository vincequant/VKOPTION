#!/usr/bin/env python3
"""
Cloud Data Uploader Module for IB Portfolio Monitor
雲端數據上傳模塊 - 用於將本地數據同步到 PythonAnywhere
"""

import json
import requests
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
import hashlib
import os

logger = logging.getLogger(__name__)

class CloudUploader:
    """處理數據上傳到 PythonAnywhere 的類"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化上傳器
        
        Args:
            config: 配置字典，包含:
                - api_url: PythonAnywhere API 端點
                - api_key: API 認證密鑰
                - username: PythonAnywhere 用戶名
                - retry_count: 重試次數
                - timeout: 請求超時時間
        """
        self.api_url = config.get('api_url', '')
        self.api_key = config.get('api_key', '')
        self.username = config.get('username', '')
        self.retry_count = config.get('retry_count', 3)
        self.timeout = config.get('timeout', 30)
        
        # 生成 API 認證頭
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'X-Client-Version': '1.0'
        }
        
    def prepare_data(self, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        準備要上傳的數據
        
        Args:
            portfolio_data: 原始倉位數據
            
        Returns:
            處理後的數據字典
        """
        # 複製數據避免修改原始數據
        data = portfolio_data.copy()
        
        # 添加元數據
        data['upload_metadata'] = {
            'timestamp': datetime.now().isoformat(),
            'source': 'ib_gateway_local',
            'version': '1.0',
            'data_hash': self._calculate_hash(portfolio_data)
        }
        
        # 移除敏感信息（如果需要）
        # data.pop('account_number', None)  # 根據需要移除
        
        return data
    
    def _calculate_hash(self, data: Dict[str, Any]) -> str:
        """計算數據哈希值用於驗證"""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
    
    def upload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        上傳數據到雲端
        
        Args:
            data: 要上傳的數據
            
        Returns:
            上傳結果字典
        """
        prepared_data = self.prepare_data(data)
        
        for attempt in range(self.retry_count):
            try:
                logger.info(f"開始上傳數據到雲端 (嘗試 {attempt + 1}/{self.retry_count})")
                
                response = requests.post(
                    self.api_url,
                    json=prepared_data,
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    logger.info("數據上傳成功")
                    return {
                        'success': True,
                        'message': '數據上傳成功',
                        'timestamp': datetime.now().isoformat(),
                        'response': response.json()
                    }
                elif response.status_code == 401:
                    logger.error("API 認證失敗")
                    return {
                        'success': False,
                        'message': 'API 認證失敗，請檢查密鑰',
                        'error_code': 401
                    }
                else:
                    logger.warning(f"上傳失敗，狀態碼: {response.status_code}")
                    if attempt < self.retry_count - 1:
                        time.sleep(2 ** attempt)  # 指數退避
                        continue
                        
            except requests.exceptions.Timeout:
                logger.error(f"上傳超時 (嘗試 {attempt + 1})")
                if attempt < self.retry_count - 1:
                    time.sleep(2 ** attempt)
                    continue
                    
            except requests.exceptions.ConnectionError:
                logger.error(f"連接錯誤 (嘗試 {attempt + 1})")
                if attempt < self.retry_count - 1:
                    time.sleep(2 ** attempt)
                    continue
                    
            except Exception as e:
                logger.error(f"上傳時發生錯誤: {str(e)}")
                return {
                    'success': False,
                    'message': f'上傳錯誤: {str(e)}',
                    'error_type': type(e).__name__
                }
        
        return {
            'success': False,
            'message': f'上傳失敗，已重試 {self.retry_count} 次',
            'timestamp': datetime.now().isoformat()
        }
    
    def verify_connection(self) -> bool:
        """驗證與雲端的連接"""
        try:
            response = requests.get(
                f"{self.api_url}/status",
                headers=self.headers,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def get_last_update_time(self) -> Optional[datetime]:
        """獲取雲端最後更新時間"""
        try:
            response = requests.get(
                f"{self.api_url}/last_update",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return datetime.fromisoformat(data.get('last_update'))
        except:
            pass
        return None


# 配置模板
CLOUD_CONFIG_TEMPLATE = {
    'api_url': 'https://YOUR_USERNAME.pythonanywhere.com/api/portfolio',
    'api_key': 'YOUR_SECRET_API_KEY',  # 請生成一個安全的密鑰
    'username': 'YOUR_PYTHONANYWHERE_USERNAME',
    'retry_count': 3,
    'timeout': 30
}

def create_config_file():
    """創建配置文件模板"""
    config_path = 'cloud_config.json'
    if not os.path.exists(config_path):
        with open(config_path, 'w') as f:
            json.dump(CLOUD_CONFIG_TEMPLATE, f, indent=2)
        logger.info(f"已創建配置文件模板: {config_path}")
        logger.info("請編輯該文件填入您的 PythonAnywhere 配置信息")
        return False
    return True

def load_cloud_config():
    """加載雲端配置"""
    config_path = 'cloud_config.json'
    if not os.path.exists(config_path):
        create_config_file()
        return None
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # 驗證必要字段
        if config.get('api_url') == CLOUD_CONFIG_TEMPLATE['api_url']:
            logger.warning("請先配置 cloud_config.json 文件")
            return None
            
        return config
    except Exception as e:
        logger.error(f"加載配置文件失敗: {e}")
        return None


if __name__ == "__main__":
    # 測試上傳器
    logging.basicConfig(level=logging.INFO)
    
    config = load_cloud_config()
    if config:
        uploader = CloudUploader(config)
        
        # 測試連接
        if uploader.verify_connection():
            logger.info("雲端連接測試成功")
        else:
            logger.error("雲端連接測試失敗")
    else:
        logger.info("請先配置 cloud_config.json 文件")