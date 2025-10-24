#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Raspberry Pi IP Advertiser Service
Broadcasts printer ID and IP address via UDP multicast
Run this on each Raspberry Pi with unique printer_id
"""

import socket
import time
import json
import sys
import argparse
from utils import get_local_ip

MULTICAST_GROUP = '239.255.255.250'
MULTICAST_PORT = 50000
BROADCAST_INTERVAL = 3  # seconds


def advertise_printer(printer_id, interface='wlan0', interval=BROADCAST_INTERVAL):
    """
    Continuously broadcast printer ID and IP address

    Args:
        printer_id: Unique identifier for this printer
        interface: Network interface name (default: wlan0)
        interval: Seconds between broadcasts (default: 3)
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    print(f"Starting IP advertiser for '{printer_id}'")
    print(f"Broadcasting to {MULTICAST_GROUP}:{MULTICAST_PORT}")
    print(f"Interface: {interface}")
    print("-" * 50)

    broadcast_count = 0

    try:
        while True:
            ip = get_local_ip(interface)

            if ip:
                message = json.dumps({
                    'id': printer_id,
                    'ip': ip,
                    'timestamp': time.time()
                })

                sock.sendto(message.encode('utf-8'), (MULTICAST_GROUP, MULTICAST_PORT))
                broadcast_count += 1

                print(f"[{broadcast_count}] Advertised: {printer_id} -> {ip}")
            else:
                print(f"Warning: Could not get IP for interface {interface}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopping advertiser...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()
        print("Advertiser stopped")


def main():
    parser = argparse.ArgumentParser(
        description='Raspberry Pi IP Advertiser for Printer Discovery'
    )
    parser.add_argument(
        'printer_id',
        help='Unique printer identifier (e.g., printer-01, fdm-lab, resin-studio)'
    )
    parser.add_argument(
        '-i', '--interface',
        default='wlan0',
        help='Network interface name (default: wlan0)'
    )
    parser.add_argument(
        '-t', '--interval',
        type=int,
        default=BROADCAST_INTERVAL,
        help=f'Broadcast interval in seconds (default: {BROADCAST_INTERVAL})'
    )

    args = parser.parse_args()

    advertise_printer(args.printer_id, args.interface, args.interval)


if __name__ == '__main__':
    main()
