#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Printer Discovery Client using UDP broadcast
Listens on local subnet broadcast address to discover printers
"""

import socket
import json
import time
import argparse
from typing import Dict
from utils import save_discovered_printers

PORT = 50000


class PrinterListener:
    def __init__(self):
        self.discovered = {}
        self.sock = None

    def listen(self, timeout=10, continuous=False):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.sock.bind(('', PORT))
        if not continuous:
            self.sock.settimeout(timeout)

        print(f"Listening for broadcasts on port {PORT}")
        print(f"Timeout={timeout}s" if not continuous else "Continuous listening mode")

        try:
            while True:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    msg = json.loads(data.decode('utf-8'))

                    pid = msg.get('id')
                    ip = msg.get('ip')
                    timestamp = msg.get('timestamp', time.time())

                    if pid and ip:
                        is_new = pid not in self.discovered
                        self.discovered[pid] = {
                            'ip': ip,
                            'timestamp': timestamp,
                            'source': addr[0]
                        }
                        status = 'NEW' if is_new else 'UPDATE'
                        print(f"[{status}] {pid:20s} -> {ip:15s} (from {addr[0]})")
                except socket.timeout:
                    if not continuous:
                        break
                except json.JSONDecodeError:
                    print("Received invalid JSON data")
        except KeyboardInterrupt:
            print("\nStopping listener...")
        finally:
            self.sock.close()

        return {pid: info['ip'] for pid, info in self.discovered.items()}


def listen_for_printers(timeout=10):
    listener = PrinterListener()
    return listener.listen(timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description='Printer Discovery Client (Broadcast)')
    parser.add_argument('-t', '--timeout', type=int, default=10, help='Listening timeout in seconds')
    parser.add_argument('-c', '--continuous', action='store_true', help='Continuous listen (Ctrl+C to exit)')
    parser.add_argument('-s', '--save', action='store_true', help='Save discovered printers')
    parser.add_argument('-o', '--output', default='discovered_printers.json', help='Output filename')

    args = parser.parse_args()

    listener = PrinterListener()
    printers = listener.listen(timeout=args.timeout, continuous=args.continuous)

    print("\n" + "=" * 70)
    print(f"Discovered {len(printers)} printer(s):")
    print("=" * 70)

    for pid, ip in printers.items():
        print(f"{pid:25s} -> {ip}")

    if args.save:
        save_discovered_printers(printers, args.output)
        print(f"Saved to {args.output}")


if __name__ == '__main__':
    main()
