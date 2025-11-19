#!/bin/bash

PRINTER_ID="$1"
INTERFACE="${2:-wlan0}"
INTERVAL="${3:-3}"
BROADCAST_IP="255.255.255.255"
PORT="50000"

get_local_ip() {
    local interface="$1"
    local ip=""
    
    if command -v ip >/dev/null 2>&1; then
        ip=$(ip addr show "$interface" 2>/dev/null | grep -oP 'inet \K[\d.]+' | head -1)
    fi
    
    if [ -z "$ip" ] && command -v ifconfig >/dev/null 2>&1; then
        ip=$(ifconfig "$interface" 2>/dev/null | grep -oP 'inet \K[\d.]+' | head -1)
    fi
    
    if [ -z "$ip" ]; then
        ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi
    
    echo "$ip"
}

create_message() {
    local printer_id="$1"
    local ip="$2"
    local timestamp=$(date +%s)
    echo "{\"id\":\"$printer_id\",\"ip\":\"$ip\",\"timestamp\":$timestamp}"
}

send_broadcast() {
    local message="$1"
    local broadcast_ip="$2"
    local port="$3"
    
    if command -v nc >/dev/null 2>&1; then
        echo "$message" | nc -u -w 0 "$broadcast_ip" "$port" 2>/dev/null &
    elif command -v socat >/dev/null 2>&1; then
        echo "$message" | socat - UDP4-DATAGRAM:"$broadcast_ip":"$port",broadcast 2>/dev/null &
    else
        echo "$message" > /dev/udp/"$broadcast_ip"/"$port" 2>/dev/null &
    fi
}

show_usage() {
    echo "Usage: $0 <printer_id> [interface] [interval]"
    echo "  printer_id: Unique printer identifier (required)"
    echo "  interface:  Network interface (default: wlan0)"
    echo "  interval:   Broadcast interval in seconds (default: 3)"
    echo ""
    echo "Examples:"
    echo "  $0 my_printer_001"
    echo "  $0 my_printer_001 eth0 5"
}

main() {
    if [ -z "$PRINTER_ID" ]; then
        echo "Error: Printer ID is required"
        show_usage
        exit 1
    fi
    
    if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [ "$INTERVAL" -lt 1 ]; then
        echo "Error: Interval must be a positive integer"
        show_usage
        exit 1
    fi
    
    echo "Starting IP Advertiser for printer: $PRINTER_ID"
    echo "Interface: $INTERFACE"
    echo "Broadcast IP: $BROADCAST_IP"
    echo "Port: $PORT"
    echo "Interval: ${INTERVAL}s"
    echo "----------------------------------------"
    
    local broadcast_count=0
    local last_ip=""
    
    while true; do
        local current_ip=$(get_local_ip "$INTERFACE")
        
        if [ -n "$current_ip" ]; then
            if [ "$current_ip" != "$last_ip" ] || [ $broadcast_count -eq 0 ]; then
                local message=$(create_message "$PRINTER_ID" "$current_ip")
                send_broadcast "$message" "$BROADCAST_IP" "$PORT"
                
                broadcast_count=$((broadcast_count + 1))
                echo "[$broadcast_count] Broadcasted: $PRINTER_ID -> $current_ip"
                last_ip="$current_ip"
            else
                echo "[$broadcast_count] IP unchanged: $current_ip (skipping broadcast)"
            fi
        else
            echo "Warning: Could not get IP address for interface $INTERFACE"
        fi
        
        sleep "$INTERVAL"
    done
}

cleanup() {
    echo ""
    echo "Stopping IP Advertiser..."
    pkill -P $$ 2>/dev/null
    exit 0
}

trap cleanup INT TERM

main