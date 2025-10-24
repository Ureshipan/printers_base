#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Printer Discovery Client
Listens for Raspberry Pi advertisements via UDP multicast
Cross-platform (Windows/Linux/macOS)
"""

import socket
import struct
import json
import time
import argparse
from typing import Dict
from utils import save_discovered_printers

MULTICAST_GROUP = '239.255.255.250'
MULTICAST_PORT = 50000


class PrinterListener:
    """Class for listening to printer advertisements"""

    def __init__(self):
        self.discovered_printers = {}
        self.sock = None

    def listen(self, timeout=10, continuous=False):
        """
        Listen for printer advertisements

        Args:
            timeout: Listening timeout in seconds (default: 10)
            continuous: Keep listening indefinitely (default: False)

        Returns:
            Dictionary of discovered printers {printer_id: ip_address}
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.sock.bind(('', MULTICAST_PORT))
        except OSError as e:
            print(f"Error binding to port {MULTICAST_PORT}: {e}")
            print("Make sure no other instance is running.")
            return {}

        # Join multicast group
        mreq = struct.pack('4sl', socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        if not continuous:
            self.sock.settimeout(timeout)

        print(f"Listening for printer advertisements on {MULTICAST_GROUP}:{MULTICAST_PORT}")
        print(f"Timeout: {timeout}s" if not continuous else "Mode: Continuous")
        print("-" * 70)

        try:
            while True:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    message = json.loads(data.decode('utf-8'))

                    printer_id = message.get('id')
                    ip_address = message.get('ip')
                    timestamp = message.get('timestamp', time.time())

                    if printer_id and ip_address:
                        # Update or add printer
                        is_new = printer_id not in self.discovered_printers
                        self.discovered_printers[printer_id] = {
                            'ip': ip_address,
                            'timestamp': timestamp,
                            'source': addr[0]
                        }

                        status = "NEW" if is_new else "UPDATE"
                        print(f"[{status}] {printer_id:20s} -> {ip_address:15s} (from {addr[0]})")

                except socket.timeout:
                    if not continuous:
                        break
                except json.JSONDecodeError:
                    print("Warning: Received invalid JSON data")

        except KeyboardInterrupt:
            print("\n\nStopping listener...")
        finally:
            self.sock.close()

        return self.get_printer_map()

    def get_printer_map(self) -> Dict[str, str]:
        """Get simple printer_id -> ip mapping"""
        return {pid: info['ip'] for pid, info in self.discovered_printers.items()}

    def get_detailed_info(self) -> Dict:
        """Get detailed information about discovered printers"""
        return self.discovered_printers


def listen_for_printers(timeout=10):
    """
    Simple function to discover printers

    Args:
        timeout: Listening timeout in seconds

    Returns:
        Dictionary {printer_id: ip_address}
    """
    listener = PrinterListener()
    return listener.listen(timeout=timeout)


def main():
    parser = argparse.ArgumentParser(
        description='Printer Discovery Client - Find Raspberry Pi printers in LAN'
    )
    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=10,
        help='Discovery timeout in seconds (default: 10)'
    )
    parser.add_argument(
        '-c', '--continuous',
        action='store_true',
        help='Continuous listening mode (Ctrl+C to stop)'
    )
    parser.add_argument(
        '-s', '--save',
        action='store_true',
        help='Save discovered printers to printers.json'
    )
    parser.add_argument(
        '-o', '--output',
        default='discovered_printers.json',
        help='Output file for discovered printers (default: discovered_printers.json)'
    )

    args = parser.parse_args()

    listener = PrinterListener()
    printers = listener.listen(timeout=args.timeout, continuous=args.continuous)

    print("\n" + "=" * 70)
    print(f"Discovery complete. Found {len(printers)} printer(s):")
    print("=" * 70)

    if printers:
        for printer_id, ip in printers.items():
            print(f"  {printer_id:25s} -> {ip}")

        if args.save:
            save_discovered_printers(printers, args.output)
            print(f"\n✓ Saved to {args.output}")
    else:
        print("  (no printers found)")

    print("=" * 70)


if __name__ == '__main__':
    main()
