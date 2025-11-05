#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discovery module for automatic Raspberry Pi detection via UDP multicast
Supports multiple printers without router configuration
"""

__version__ = "2.0.0"
__author__ = "fylhtq7779"

#from .pi_discover import listen_for_printers, PrinterListener
from discovery.pi_advertiser import advertise_printer
from discovery.utils import get_local_ip, save_discovered_printers, load_discovered_printers

__all__ = [
    #'listen_for_printers',
    #'PrinterListener',
    'advertise_printer',
    'get_local_ip',
    'save_discovered_printers',
    'load_discovered_printers'
]
