@echo off
chcp 65001 > nul
color 0A
title Moonraker API Tools

echo ======================================================
echo              ИНСТРУМЕНТЫ MOONRAKER API
echo ======================================================

:menu
cls
echo.
echo  Выберите инструмент для запуска:
echo.
echo  1. Тест API (test_moonraker_api.py)
echo  2. Мониторинг принтера (monitor_printer.py)
echo  3. WebSocket слушатель (websocket_listener.py)
echo  4. Отправка G-Code команд (send_gcode.py)
echo  5. Интерактивный инструмент (moonraker_tool.py)
echo.
echo  i. Установить зависимости
echo  c. Настроить IP-адрес принтера
echo  q. Выход
echo.

set /p choice=Выберите опцию: 

if "%choice%"=="1" goto run_api_test
if "%choice%"=="2" goto run_monitor
if "%choice%"=="3" goto run_websocket
if "%choice%"=="4" goto run_gcode
if "%choice%"=="5" goto run_tool
if "%choice%"=="i" goto install_deps
if "%choice%"=="c" goto config
if "%choice%"=="q" goto end

echo Неверный выбор. Пожалуйста, попробуйте снова.
timeout /t 2 >nul
goto menu

:run_api_test
cls
echo Запуск проверки API...
python test_moonraker_api.py
echo.
pause
goto menu

:run_monitor
cls
echo.
echo Запуск мониторинга принтера...
echo.
set /p host=Введите IP-адрес принтера (или нажмите Enter для 192.168.10.14): 
set /p interval=Введите интервал опроса в секундах (или нажмите Enter для 5): 

if "%host%"=="" set host=192.168.10.14
if "%interval%"=="" set interval=5

cls
python monitor_printer.py --host %host% --interval %interval%
echo.
pause
goto menu

:run_websocket
cls
echo.
echo Запуск WebSocket слушателя...
echo.
set /p host=Введите IP-адрес принтера (или нажмите Enter для 192.168.10.14): 

if "%host%"=="" set host=192.168.10.14

cls
python websocket_listener.py --host %host%
echo.
pause
goto menu

:run_gcode
cls
echo.
echo Отправка G-Code команд...
echo.
set /p host=Введите IP-адрес принтера (или нажмите Enter для 192.168.10.14): 
set /p gcode=Введите G-Code команду (или нажмите Enter для интерактивного режима): 

if "%host%"=="" set host=192.168.10.14

cls
if "%gcode%"=="" (
    python send_gcode.py --host %host%
) else (
    python send_gcode.py --host %host% --gcode "%gcode%"
)
echo.
pause
goto menu

:run_tool
cls
echo.
echo Запуск интерактивного инструмента...
echo.
set /p host=Введите IP-адрес принтера (или нажмите Enter для 192.168.10.14): 

if "%host%"=="" set host=192.168.10.14

cls
python moonraker_tool.py --host %host%
echo.
pause
goto menu

:install_deps
cls
echo.
echo Установка зависимостей...
echo.
pip install -r requirements.txt
echo.
echo Зависимости установлены!
pause
goto menu

:config
cls
echo.
echo Текущий IP-адрес принтера в скриптах: 192.168.10.14
echo.
set /p new_ip=Введите новый IP-адрес принтера: 

if "%new_ip%"=="" goto menu

echo.
echo Обновление IP-адреса в скриптах...
echo.

powershell -Command "(Get-Content test_moonraker_api.py) -replace '192\.168\.10\.14', '%new_ip%' | Set-Content test_moonraker_api.py"
powershell -Command "(Get-Content monitor_printer.py) -replace '192\.168\.10\.14', '%new_ip%' | Set-Content monitor_printer.py"
powershell -Command "(Get-Content websocket_listener.py) -replace '192\.168\.10\.14', '%new_ip%' | Set-Content websocket_listener.py"
powershell -Command "(Get-Content send_gcode.py) -replace '192\.168\.10\.14', '%new_ip%' | Set-Content send_gcode.py"
powershell -Command "(Get-Content moonraker_tool.py) -replace '192\.168\.10\.14', '%new_ip%' | Set-Content moonraker_tool.py"

echo IP-адрес обновлен во всех скриптах!
pause
goto menu

:end
cls
echo.
echo Благодарим за использование инструментов Moonraker API!
echo.
timeout /t 3 >nul
exit 