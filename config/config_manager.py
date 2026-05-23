"""
配置管理模块

提供安全的配置文件读取和敏感信息访问功能。
支持从天勤量化配置文件加载账号信息和API密钥。

使用示例：
    config = ConfigManager()
    account_info = config.get_account_info()
    credentials = config.get_credentials()
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path


class ConfigManager:
    """
    天勤量化交易系统配置管理器
    
    负责加载、验证和管理配置文件中的敏感信息。
    提供安全的访问接口，避免敏感信息泄露。
    
    Attributes:
        config_path: 配置文件路径
        _config: 缓存的配置字典
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认使用项目根目录下的conf.yaml
        """
        if config_path is None:
            project_root = Path(__file__).parent.parent
            config_path = project_root / "conf.yaml"
        
        self.config_path = Path(config_path)
        self._config: Optional[Dict[str, Any]] = None
        
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        读取YAML配置文件并解析为Python字典。
        
        Returns:
            包含所有配置项的字典
            
        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML解析错误
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {self.config_path}\n"
                f"请检查配置文件路径或创建配置文件"
            )
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        return config if config else {}
    
    def load_config(self) -> Dict[str, Any]:
        """
        获取配置（带缓存）
        
        Returns:
            完整的配置字典
        """
        if self._config is None:
            self._config = self._load_config()
        return self._config
    
    def get_service_config(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定第三方服务的配置
        
        Args:
            service_name: 服务名称（如 'tqsdk', 'binance'）
            
        Returns:
            服务配置字典，如果服务不存在返回 None
        """
        config = self.load_config()
        third_party = config.get('third_party', {})
        services: List[Dict[str, Any]] = third_party.get('services', [])
        
        for service in services:
            if service.get('name') == service_name:
                return service
        
        return None
    
    def get_account_info(self) -> Dict[str, str]:
        """
        获取天勤量化账号信息
        
        从third_party.services中读取tqsdk服务的API密钥。
        注意：此方法不返回密码类敏感信息。
        
        Returns:
            包含账号信息的字典，格式：
            {
                'api_key': str,
                'api_secret': str
            }
            
        Raises:
            KeyError: 缺少必需的账号配置项
        """
        config = self.load_config()
        
        try:
            tq_service = self.get_service_config('tqsdk')
            
            if not tq_service:
                raise KeyError("配置文件中缺少 tqsdk 服务配置")
            
            account_info = {
                'api_key': tq_service.get('api_key', ''),
                'api_secret': tq_service.get('api_secret', '')
            }
            
            if not account_info['api_key'] or account_info['api_key'] == 'PLACEHOLDER_API_KEY':
                raise KeyError("配置文件中缺少有效的 api_key，请检查 conf.local.yaml")
            
            if not account_info['api_secret'] or account_info['api_secret'] == 'PLACEHOLDER_API_SECRET':
                raise KeyError("配置文件中缺少有效的 api_secret，请检查 conf.local.yaml")
            
            return account_info
            
        except Exception as e:
            raise KeyError(f"获取账号信息失败: {str(e)}")
    
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
        验证配置完整性
        
        检查所有必需的配置文件是否存在且格式正确。
        
        Returns:
            验证是否通过
            
        Raises:
            ValueError: 配置验证失败
        """
        try:
            account_info = self.get_account_info()
            
            if not account_info['api_key']:
                raise ValueError("api_key不能为空")
            
            if not account_info['api_secret']:
                raise ValueError("api_secret不能为空")
            
            return True
            
        except KeyError as e:
            raise ValueError(f"配置验证失败: {str(e)}")
    
    def get_trading_config(self) -> Dict[str, Any]:
        """
        获取交易策略配置
        
        返回交易相关的配置参数，如止损比例、止盈比例等。
        如果配置文件中没有定义，返回默认值。
        
        Returns:
            交易配置字典
        """
        config = self.load_config()
        
        trading_config = config.get('trading', {})
        
        return {
            'stop_loss_ratio': trading_config.get('stop_loss_ratio', 0.03),
            'take_profit_ratio': trading_config.get('take_profit_ratio', 0.05),
            'position_ratio': trading_config.get('position_ratio', 0.1),
            'sma_short': trading_config.get('sma_short', 5),
            'sma_long': trading_config.get('sma_long', 20)
        }


def load_config() -> Dict[str, Any]:
    """
    便捷函数：加载配置文件
    
    Returns:
        完整的配置字典
    """
    manager = ConfigManager()
    return manager.load_config()


def get_account_info() -> Dict[str, str]:
    """
    便捷函数：获取账号信息
    
    Returns:
        账号信息字典
    """
    manager = ConfigManager()
    return manager.get_account_info()


def get_credentials() -> Dict[str, str]:
    """
    便捷函数：获取凭证信息
    
    Returns:
        凭证字典
    """
    manager = ConfigManager()
    return manager.get_credentials()


if __name__ == "__main__":
    try:
        config_manager = ConfigManager()
        
        print("正在加载配置文件...")
        config = config_manager.load_config()
        print(f"配置文件加载成功: {config_manager.config_path}")
        
        print("\n正在验证配置...")
        config_manager.validate_config()
        print("配置验证通过")
        
        print("\n正在获取账号信息...")
        account_info = config_manager.get_account_info()
        print(f"账号信息: api_key={account_info['api_key']}, api_secret已隐藏")
        
    except Exception as e:
        print(f"错误: {str(e)}")
