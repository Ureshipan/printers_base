#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color
BOLD='\033[1m'

clear
echo -e "${BOLD}${GREEN}======================================================"
echo -e "              ИНСТРУМЕНТЫ MOONRAKER API"
echo -e "======================================================${NC}"

show_menu() {
    clear
    echo -e "${BOLD}${GREEN}======================================================"
    echo -e "              ИНСТРУМЕНТЫ MOONRAKER API"
    echo -e "======================================================${NC}"
    echo ""
    echo -e " Выберите инструмент для запуска:"
    echo ""
    echo -e " ${BLUE}1.${NC} Тест API (test_moonraker_api.py)"
    echo -e " ${BLUE}2.${NC} Мониторинг принтера (monitor_printer.py)"
    echo -e " ${BLUE}3.${NC} WebSocket слушатель (websocket_listener.py)"
    echo -e " ${BLUE}4.${NC} Отправка G-Code команд (send_gcode.py)"
    echo -e " ${BLUE}5.${NC} Интерактивный инструмент (moonraker_tool.py)"
    echo ""
    echo -e " ${YELLOW}i.${NC} Установить зависимости"
    echo -e " ${YELLOW}c.${NC} Настроить IP-адрес принтера"
    echo -e " ${YELLOW}q.${NC} Выход"
    echo ""
    echo -ne "Выберите опцию: "
    read choice
}

run_api_test() {
    clear
    echo -e "${BLUE}Запуск проверки API...${NC}"
    python3 test_moonraker_api.py
    echo ""
    read -p "Нажмите Enter для продолжения..."
}

run_monitor() {
    clear
    echo ""
    echo -e "${BLUE}Запуск мониторинга принтера...${NC}"
    echo ""
    read -p "Введите IP-адрес принтера (или нажмите Enter для 192.168.10.14): " host
    read -p "Введите интервал опроса в секундах (или нажмите Enter для 5): " interval
    
    host=${host:-192.168.10.14}
    interval=${interval:-5}
    
    clear
    python3 monitor_printer.py --host $host --interval $interval
    echo ""
    read -p "Нажмите Enter для продолжения..."
}

run_websocket() {
    clear
    echo ""
    echo -e "${BLUE}Запуск WebSocket слушателя...${NC}"
    echo ""
    read -p "Введите IP-адрес принтера (или нажмите Enter для 192.168.10.14): " host
    
    host=${host:-192.168.10.14}
    
    clear
    python3 websocket_listener.py --host $host
    echo ""
    read -p "Нажмите Enter для продолжения..."
}

run_gcode() {
    clear
    echo ""
    echo -e "${BLUE}Отправка G-Code команд...${NC}"
    echo ""
    read -p "Введите IP-адрес принтера (или нажмите Enter для 192.168.10.14): " host
    read -p "Введите G-Code команду (или нажмите Enter для интерактивного режима): " gcode
    
    host=${host:-192.168.10.14}
    
    clear
    if [ -z "$gcode" ]; then
        python3 send_gcode.py --host $host
    else
        python3 send_gcode.py --host $host --gcode "$gcode"
    fi
    echo ""
    read -p "Нажмите Enter для продолжения..."
}

run_tool() {
    clear
    echo ""
    echo -e "${BLUE}Запуск интерактивного инструмента...${NC}"
    echo ""
    read -p "Введите IP-адрес принтера (или нажмите Enter для 192.168.10.14): " host
    
    host=${host:-192.168.10.14}
    
    clear
    python3 moonraker_tool.py --host $host
    echo ""
    read -p "Нажмите Enter для продолжения..."
}

install_deps() {
    clear
    echo ""
    echo -e "${BLUE}Установка зависимостей...${NC}"
    echo ""
    pip3 install -r requirements.txt
    echo ""
    echo -e "${GREEN}Зависимости установлены!${NC}"
    read -p "Нажмите Enter для продолжения..."
}

config() {
    clear
    echo ""
    echo -e "${BLUE}Текущий IP-адрес принтера в скриптах: 192.168.10.14${NC}"
    echo ""
    read -p "Введите новый IP-адрес принтера: " new_ip
    
    if [ -z "$new_ip" ]; then
        return
    fi
    
    echo ""
    echo -e "${BLUE}Обновление IP-адреса в скриптах...${NC}"
    echo ""
    
    sed -i "s/192\.168\.10\.14/$new_ip/g" test_moonraker_api.py
    sed -i "s/192\.168\.10\.14/$new_ip/g" monitor_printer.py
    sed -i "s/192\.168\.10\.14/$new_ip/g" websocket_listener.py
    sed -i "s/192\.168\.10\.14/$new_ip/g" send_gcode.py
    sed -i "s/192\.168\.10\.14/$new_ip/g" moonraker_tool.py
    
    echo -e "${GREEN}IP-адрес обновлен во всех скриптах!${NC}"
    read -p "Нажмите Enter для продолжения..."
}

# Делаем скрипт исполняемым
chmod +x "$0"

# Основной цикл программы
while true; do
    show_menu
    
    case $choice in
        1) run_api_test ;;
        2) run_monitor ;;
        3) run_websocket ;;
        4) run_gcode ;;
        5) run_tool ;;
        i) install_deps ;;
        c) config ;;
        q) 
            clear
            echo ""
            echo -e "${GREEN}Благодарим за использование инструментов Moonraker API!${NC}"
            echo ""
            sleep 2
            exit 0
            ;;
        *) 
            echo -e "${YELLOW}Неверный выбор. Пожалуйста, попробуйте снова.${NC}"
            sleep 2
            ;;
    esac
done 