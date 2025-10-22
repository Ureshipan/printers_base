"""
Discovery модуль для автоматического обнаружения 3D-принтеров
Поддерживает Bluetooth, mDNS, SSDP и ручную конфигурацию
"""

from .config_manager import PrinterConfig
from .integration_module import PrinterDiscoveryManager

__version__ = "1.0.0"
__all__ = ['PrinterConfig', 'PrinterDiscoveryManager']
