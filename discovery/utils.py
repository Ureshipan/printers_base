#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility functions for printer discovery
Cross-platform IP detection and configuration management
"""

import json
import socket
import platform
from typing import Optional, Dict


def get_local_ip(interface='wlan0') -> Optional[str]:
    """
    Get local IP address of network interface
    Cross-platform implementation

    Args:
        interface: Network interface name (Linux: wlan0/eth0, Windows: ignored)

    Returns:
        IP address as string or None if not found
    """
    system = platform.system()

    # Try netifaces first (most reliable on Linux)
    try:
        import netifaces
        if interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addrs:
                return addrs[netifaces.AF_INET][0]['addr']
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: connect to external host to determine local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass

    # Last resort: get hostname IP
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith('127.'):
            return ip
    except Exception:
        pass

    return None


def save_discovered_printers(printers: Dict[str, str], filename: str = 'discovered_printers.json'):
    """
    Save discovered printers to JSON file

    Args:
        printers: Dictionary of {printer_id: ip_address}
        filename: Output filename
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(printers, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving to {filename}: {e}")
        return False


def load_discovered_printers(filename: str = 'discovered_printers.json') -> Dict[str, str]:
    """
    Load discovered printers from JSON file

    Args:
        filename: Input filename

    Returns:
        Dictionary of {printer_id: ip_address}
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading from {filename}: {e}")
        return {}


def format_printer_list(printers: Dict[str, str]) -> str:
    """
    Format printer list for display

    Args:
        printers: Dictionary of {printer_id: ip_address}

    Returns:
        Formatted string
    """
    if not printers:
        return "No printers discovered"

    lines = []
    lines.append("=" * 60)
    lines.append(f"{'Printer ID':<25s} | {'IP Address':<15s}")
    lines.append("-" * 60)
    for pid, ip in printers.items():
        lines.append(f"{pid:<25s} | {ip:<15s}")
    lines.append("=" * 60)

    return "\n".join(lines)


if __name__ == '__main__':
    # Test utilities
    print("Testing utilities...")
    print(f"Local IP: {get_local_ip()}")

    # Test save/load
    test_printers = {
        'printer-01': '192.168.1.101',
        'printer-02': '192.168.1.102'
    }

    save_discovered_printers(test_printers, 'test_printers.json')
    loaded = load_discovered_printers('test_printers.json')
    print(f"\nLoaded printers: {loaded}")
    print(f"\nFormatted list:\n{format_printer_list(loaded)}")
