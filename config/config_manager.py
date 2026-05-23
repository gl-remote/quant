# -*- coding: utf-8 -*-
"""
配置管理模块

提供统一的配置加载和管理功能。
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path


class ConfigManager:
    """
    配置管理器
    
    负责加载和管理系统配置。
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，如果为None则使用默认路径
        """
        self.config = {}
        self._load_config(config_file)
    
    def _load_config(self, config_file: Optional[str] = None):
        """
        加载配置文件
        
        Args:
            config_file: 配置文件路径
        """
        if config_file is None:
            config_file = 'conf.yaml'
        
        base_path = Path(config_file)
        
        if base_path.exists():
            with open(base_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        
        local_path = Path('conf.local.yaml')
        if local_path.exists():
            with open(local_path, 'r', encoding='utf-8') as f:
                local_config = yaml.safe_load(f)
                self._merge_config(self.config, local_config)
    
    def _merge_config(self, base: Dict, override: Dict):
        """
        合并配置
        
        Args:
            base: 基础配置
            override: 覆盖配置
        """
        for key, value in override.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def get_config(self) -> Dict[str, Any]:
        """
        获取完整配置
        
        Returns:
            配置字典
        """
        return self.config
    
    def get_trading_config(self) -> Dict[str, float]:
        """
        获取交易配置
        
        Returns:
            交易配置字典
        """
        trading_config = self.config.get('trading', {})
        
        return {
            'stop_loss_ratio': trading_config.get('stop_loss_ratio', 0.03),
            'take_profit_ratio': trading_config.get('take_profit_ratio', 0.05),
            'position_ratio': trading_config.get('position_ratio', 0.1),
            'sma_short': trading_config.get('sma_short', 5),
            'sma_long': trading_config.get('sma_long', 20),
            'kline_period': trading_config.get('kline_period', 5)
        }
    
    def get_service_config(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        获取第三方服务配置
        
        Args:
            service_name: 服务名称
            
        Returns:
            服务配置字典，如果不存在则返回None
        """
        third_party = self.config.get('third_party', {})
        services = third_party.get('services', [])
        
        for service in services:
            if service.get('name') == service_name:
                return service
        
        return None
    
    def get_account_info(self) -> Dict[str, str]:
        """
        获取账号信息
        
        Returns:
            包含api_key和api_secret的字典，如果配置不存在则返回空字典
        """
        try:
            tq_service = self.get_service_config('tqsdk')
            
            if not tq_service:
                return {}
            
            account_info = {
                'api_key': tq_service.get('api_key', ''),
                'api_secret': tq_service.get('api_secret', '')
            }
            
            if not account_info['api_key'] or account_info['api_key'] == 'PLACEHOLDER_API_KEY':
                return {}
            
            if not account_info['api_secret'] or account_info['api_secret'] == 'PLACEHOLDER_API_SECRET':
                return {}
            
            return account_info
            
        except Exception as e:
            return {}
    
    def get_credentials(self) -> Dict[str, str]:
        """
        获取凭证信息（仅限内部使用）
        
        返回完整的凭证信息，包含API密钥。
        建议在生产环境中使用环境变量替代配置文件存储。
        
        Returns:
            包含凭证的字典
        """
        return self.get_account_info()
    
    def validate_config(self) -> bool:
        """
        验证配置是否有效
        
        Returns:
            如果配置有效返回True，否则返回False
        """
        try:
            trading_config = self.get_trading_config()
            
            if trading_config['stop_loss_ratio'] < 0 or trading_config['stop_loss_ratio'] > 1:
                return False
            
            if trading_config['take_profit_ratio'] < 0 or trading_config['take_profit_ratio'] > 1:
                return False
            
            if trading_config['position_ratio'] <= 0 or trading_config['position_ratio'] > 1:
                return False
            
            if trading_config['sma_short'] >= trading_config['sma_long']:
                return False
            
            return True
            
        except Exception as e:
            return False
    
    def get_logging_config(self) -> Dict[str, Any]:
        """
        获取日志配置
        
        Returns:
            日志配置字典
        """
        return self.config.get('logging', {})
    
    def get_environment(self) -> str:
        """
        获取当前环境
        
        Returns:
            环境名称
        """
        return self.config.get('environment', {}).get('name', 'development')
    
    def is_debug(self) -> bool:
        """
        是否为调试模式
        
        Returns:
            如果是调试模式返回True
        """
        return self.config.get('environment', {}).get('debug', False)
