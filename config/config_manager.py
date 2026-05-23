"""配置管理 - 加载 conf.yaml 和 conf.local.yaml 并提供交易参数与账号信息"""

import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """配置管理器 - 支持基础配置与本地覆盖配置的深度合并"""

    def __init__(self, config_file: Optional[str] = None):
        self.config = {}
        self._load(config_file)

    def _load(self, config_file: Optional[str] = None):
        base = Path(config_file or (Path(__file__).parent / 'conf.yaml'))
        if base.exists():
            self.config = yaml.safe_load(open(base, encoding='utf-8')) or {}
        local = Path(__file__).parent / 'conf.local.yaml'
        if local.exists():
            self._merge(self.config, yaml.safe_load(open(local, encoding='utf-8')) or {})

    def _merge(self, base: Dict, override: Dict):
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                self._merge(base[k], v)
            else:
                base[k] = v

    def get_trading_config(self) -> Dict[str, float]:
        tc = self.config.get('trading', {})
        return {
            'stop_loss_ratio': tc.get('stop_loss_ratio', 0.03),
            'take_profit_ratio': tc.get('take_profit_ratio', 0.05),
            'position_ratio': tc.get('position_ratio', 0.1),
            'sma_short': tc.get('sma_short', 5),
            'sma_long': tc.get('sma_long', 20),
            'kline_period': tc.get('kline_period', 5),
        }

    def get_account_info(self) -> Dict[str, str]:
        try:
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
            'base_dir': dc.get('base_dir', '.quant_shared_data'),
            'export_dir': dc.get('export_dir', '.quant_shared_data/csv'),
            'db_path': dc.get('db_path', '.quant_shared_data/quant_shared.db'),
        }

    def get_export_config(self) -> Dict[str, str]:
        ec = self.config.get('export', {})
        return {
            'default_dir': ec.get('default_dir', '.quant_shared_data/csv'),
            'filename_template': ec.get('filename_template', '{symbol}_qlib.csv'),
        }

    def get_backtest_config(self) -> Dict[str, Any]:
        bc = self.config.get('backtest', {})
        split_cfg = bc.get('split', {})
        report_cfg = bc.get('report', {})
        return {
            'data_dir': bc.get('data_dir', '.quant_shared_data/csv'),
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
                'output_dir': report_cfg.get('output_dir', '.quant_shared_data/reports'),
                'save_trade_records': report_cfg.get('save_trade_records', True),
                'save_equity_curve': report_cfg.get('save_equity_curve', True),
                'format': report_cfg.get('format', 'json'),
            },
        }

    def validate_config(self) -> bool:
        try:
            tc = self.get_trading_config()
            if not (0 < tc['stop_loss_ratio'] <= 1 and 0 < tc['take_profit_ratio'] <= 1):
                return False
            if not (0 < tc['position_ratio'] <= 1):
                return False
            if tc['sma_short'] >= tc['sma_long']:
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
