#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Raspberry Pi IP Advertiser Service using UDP broadcast
Broadcasts printer ID and IP address on local subnet broadcast address
"""

import socket
import time
import json
import argparse
from discovery.utils import get_local_ip

BROADCAST_IP = '255.255.255.255'
PORT = 50000
BROADCAST_INTERVAL = 3  # seconds


def advertise_printer(printer_id, interface='wlan0', interval=BROADCAST_INTERVAL):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    print(f"Starting broadcast advertiser for '{printer_id}'")
    print(f"Broadcasting to {BROADCAST_IP}:{PORT} on interface {interface}")
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
                sock.sendto(message.encode('utf-8'), (BROADCAST_IP, PORT))
                broadcast_count += 1
                print(f"[{broadcast_count}] Broadcasted: {printer_id} -> {ip}")
            else:
                print(f"Warning: Could not get IP for interface {interface}")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopping advertiser...")
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(
        description='Raspberry Pi IP Advertiser (Broadcast)'
    )
    parser.add_argument('printer_id', help='Unique printer identifier')
    parser.add_argument('-i', '--interface', default='wlan0',
                        help='Network interface name (default: wlan0)')
    parser.add_argument('-t', '--interval', type=int, default=BROADCAST_INTERVAL,
                        help='Broadcast interval in seconds (default: 3)')
    args = parser.parse_args()

    advertise_printer(args.printer_id, args.interface, args.interval)


if __name__ == '__main__':
    main()
