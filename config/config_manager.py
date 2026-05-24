"""配置管理 - 加载 conf.yaml 和 conf.local.yaml 并提供交易参数与账号信息"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """配置管理器 - 支持基础配置与本地覆盖配置的深度合并"""

    def __init__(self, config_file: Optional[str] = None):
        self.config = {}
        self._project_root = Path(__file__).parent.parent  # config/../
        self._load(config_file)

    def _resolve(self, path: str) -> str:
        """将相对路径解析为项目根目录下的绝对路径"""
        p = Path(path)
        if p.is_absolute():
            return str(p)
        return str(self._project_root / p)

    def _load(self, config_file: Optional[str] = None):
        base = Path(config_file or (Path(__file__).parent / 'conf.yaml'))
        if base.exists():
            with open(base, encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
        local = Path(__file__).parent / 'conf.local.yaml'
        if local.exists():
            with open(local, encoding='utf-8') as f:
                self._merge(self.config, yaml.safe_load(f) or {})

    def _merge(self, base: Dict, override: Dict):
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                self._merge(base[k], v)
            else:
                base[k] = v

    def get_strategy_config(self, strategy_name: str = "ma") -> Dict[str, Any]:
        """获取指定策略的配置参数

        支持多种 YAML 配置格式，按优先级查找:
          1. strategies 列表 (新格式): 按 name 字段匹配
          2. strategy_params + risk (旧 conf.yaml 格式)
          3. trading (测试兼容格式)

        Args:
            strategy_name: 策略名称，如 "ma"、"rsi"

        Returns:
            策略配置字典，包含该策略所有可配置参数
        """
        strategies = self.config.get('strategies')
        if isinstance(strategies, list):
            for item in strategies:
                if isinstance(item, dict) and item.get('name') == strategy_name:
                    return {k: v for k, v in item.items()
                            if k not in ('name', 'enabled')}

        sp = self.config.get('strategy_params', {})
        risk = self.config.get('risk', {})
        tc = self.config.get('trading', {})

        defaults = {
            'stop_loss_ratio': 0.03,
            'take_profit_ratio': 0.05,
            'position_ratio': 0.1,
            'kline_period': 5,
        }
        if strategy_name == 'ma':
            defaults['sma_short'] = 5
            defaults['sma_long'] = 20

        for k, default in defaults.items():
            if k not in tc and k not in sp and k not in risk:
                tc[k] = default

        return {**defaults, **sp, **risk, **tc}

    def get_trading_config(self) -> Dict[str, Any]:
        """获取交易配置 (兼容旧接口，委托给 get_strategy_config)"""
        return self.get_strategy_config('ma')

    def get_account_info(self) -> Dict[str, str]:
        """获取天勤 API 凭证，环境变量优先于配置文件

        优先级:
          1. 环境变量 TQSDK_API_KEY / TQSDK_API_SECRET (推荐，最高安全)
          2. config/conf.local.yaml 中的 api_key / api_secret (本地便利)
          3. 都不是真实值 → 返回空字典（占位符保护）

        推荐用法:
          export TQSDK_API_KEY="your_key"
          export TQSDK_API_SECRET="your_secret"
        """
        try:
            # 1. 环境变量优先
            ak = os.environ.get('TQSDK_API_KEY', '')
            sk = os.environ.get('TQSDK_API_SECRET', '')
            if ak and sk:
                return {'api_key': ak, 'api_secret': sk}

            # 2. 降级读配置文件
            svc = self._find_service('tqsdk')
            if not svc:
                return {}
            ak = svc.get('api_key', '')
            sk = svc.get('api_secret', '')
            if not ak or ak == 'PLACEHOLDER_API_KEY' or not sk or sk == 'PLACEHOLDER_API_SECRET':
                return {}
            return {'api_key': ak, 'api_secret': sk}
        except Exception:
            return {}

    def _find_service(self, name: str) -> Optional[Dict]:
        for s in self.config.get('third_party', {}).get('services', []):
            if s.get('name') == name:
                return s
        return None

    def get_data_config(self) -> Dict[str, str]:
        dc = self.config.get('data', {})
        return {
            'base_dir': self._resolve(dc.get('base_dir', '.quant_shared_data')),
            'export_dir': self._resolve(dc.get('export_dir', '.quant_shared_data/csv')),
            'db_path': self._resolve(dc.get('db_path', '.quant_shared_data/quant_shared.db')),
        }

    def get_export_config(self) -> Dict[str, str]:
        ec = self.config.get('export', {})
        return {
            'default_dir': self._resolve(ec.get('default_dir', '.quant_shared_data/csv')),
            'filename_template': ec.get('filename_template', '{symbol}_qlib.csv'),
        }

    def get_backtest_config(self) -> Dict[str, Any]:
        bc = self.config.get('backtest', {})
        split_cfg = bc.get('split', {})
        report_cfg = bc.get('report', {})
        return {
            'data_dir': self._resolve(bc.get('data_dir', '.quant_shared_data/csv')),
            'initial_capital': bc.get('initial_capital', 100000.0),
            'commission_rate': bc.get('commission_rate', 0.0003),
            'slippage': bc.get('slippage', 1.0),
            'price_tick': bc.get('price_tick', 1.0),
            'contract_size': bc.get('contract_size', 10),
            'interval': bc.get('interval', '1m'),
            'split': {
                'train_ratio': split_cfg.get('train_ratio', 0.6),
                'val_ratio': split_cfg.get('val_ratio', 0.2),
                'test_ratio': split_cfg.get('test_ratio', 0.2),
                'random_seed': split_cfg.get('random_seed', 42),
                'shuffle': split_cfg.get('shuffle', False),
            },
            'report': {
                'output_dir': self._resolve(report_cfg.get('output_dir', '.quant_shared_data/reports')),
                'save_trade_records': report_cfg.get('save_trade_records', True),
                'save_equity_curve': report_cfg.get('save_equity_curve', True),
                'format': report_cfg.get('format', 'json'),
            },
        }

    def validate_config(self) -> bool:
        try:
            sc = self.get_strategy_config('ma')
            if not (0 < sc['stop_loss_ratio'] <= 1 and 0 < sc['take_profit_ratio'] <= 1):
                return False
            if not (0 < sc['position_ratio'] <= 1):
                return False
            if 'sma_short' in sc and 'sma_long' in sc and sc['sma_short'] >= sc['sma_long']:
                return False

            bc = self.get_backtest_config()
            if bc['initial_capital'] <= 0:
                return False
            if not (0 <= bc['commission_rate'] < 1):
                return False
            if bc['slippage'] < 0:
                return False
            if bc['price_tick'] <= 0:
                return False
            if bc['contract_size'] <= 0:
                return False
            ratio = bc['split']['train_ratio'] + bc['split']['val_ratio'] + bc['split']['test_ratio']
            if abs(ratio - 1.0) > 1e-9:
                return False

            return True
        except Exception:
            return False

    def get_system_logging_config(self) -> Dict[str, str]:
        sl = self.config.get('system', {}).get('logging', {})
        return {
            'level': sl.get('level', 'INFO'),
            'format': sl.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        }
