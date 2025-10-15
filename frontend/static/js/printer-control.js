let currentDistance = 0.1;
let updateInterval;
let extruderTempValue = 210; // Храним значение температуры экструдера
let bedTempValue = 60; // Храним значение температуры стола

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
  // Printer dropdown functionality
  const printerTitle = document.getElementById('printerTitle');
  const printerDropdown = document.getElementById('printerDropdown');
  const body = document.body;
  
  // Modal elements
  const maintenanceModal = document.getElementById('maintenanceModal');
  const closeModal = document.getElementById('closeModal');
  const confirmMaintenance = document.getElementById('confirmMaintenance');
  
  // Filament modal elements
  const filamentModal = document.getElementById('filamentModal');
  const closeFilamentModal = document.getElementById('closeFilamentModal');
  const confirmFilament = document.getElementById('confirmFilament');
  
  // Добавляем обработчики для кнопок навигации
  const sidebarButtons = document.querySelectorAll('.sidebar-btn');
  sidebarButtons[0].addEventListener('click', function() {
    // Переход на панель управления
    window.location.href = '/';
  });
  
  printerTitle.addEventListener('click', function() {
    printerDropdown.classList.toggle('show');
  });
  
  // Close dropdown when clicking outside
  document.addEventListener('click', function(event) {
    if (!printerTitle.contains(event.target) && !printerDropdown.contains(event.target)) {
      printerDropdown.classList.remove('show');
    }
  });
  
  // Maintenance Modal event handlers
  closeModal.addEventListener('click', function() {
    maintenanceModal.style.display = 'none';
  });
  
  confirmMaintenance.addEventListener('click', function() {
    maintenanceModal.style.display = 'none';
  });
  
  // Filament Modal event handlers
  closeFilamentModal.addEventListener('click', function() {
    filamentModal.style.display = 'none';
  });
  
  confirmFilament.addEventListener('click', function() {
    filamentModal.style.display = 'none';
  });
  
  window.addEventListener('click', function(event) {
    if (event.target == maintenanceModal) {
      maintenanceModal.style.display = 'none';
    }
    if (event.target == filamentModal) {
      filamentModal.style.display = 'none';
    }
  });
  
  // Handle printer selection
  document.querySelectorAll('.dropdown-item').forEach(item => {
    item.addEventListener('click', function() {
      const printerText = this.textContent;
      const printerState = this.dataset.state;
      
      // Update printer title
      printerTitle.textContent = printerText;
      printerDropdown.classList.remove('show');
      
      // Update theme based on printer state (only button colors)
      body.className = '';
      body.classList.add(`theme-${printerState}`);
      
      // Update printer status based on selection
      const printerStatus = document.querySelector('.printer-status');
      switch(printerState) {
        case 'ready':
          printerStatus.textContent = 'Готов к работе';
          printerStatus.className = 'printer-status';
          break;
        case 'working':
          printerStatus.textContent = 'В работе • 67%';
          printerStatus.className = 'printer-status status-work';
          break;
        case 'finished':
          printerStatus.textContent = 'Печать завершена';
          printerStatus.className = 'printer-status';
          break;
        case 'maintenance':
          printerStatus.textContent = 'Требуется обслуживание';
          printerStatus.className = 'printer-status status-work';
          // Show maintenance warning modal
          maintenanceModal.style.display = 'block';
          break;
        case 'filament':
          printerStatus.textContent = 'Закончился филамент';
          printerStatus.className = 'printer-status status-work';
          // Show filament warning modal
          filamentModal.style.display = 'block';
          break;
        default:
          printerStatus.textContent = 'Готов к работе';
          printerStatus.className = 'printer-status';
      }
    });
  });
  
  document.querySelectorAll('.distance-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      document.querySelectorAll('.distance-btn').forEach(b => b.classList.remove('active'));
      this.classList.add('active');
      currentDistance = parseFloat(this.dataset.distance);
    });
  });
  
  // Инициализируем значения температур
  document.getElementById('extruderTemp').value = extruderTempValue;
  document.getElementById('bedTemp').value = bedTempValue;
  
  // Добавляем обработчики событий для полей ввода температуры
  document.getElementById('extruderTemp').addEventListener('change', function() {
    extruderTempValue = parseInt(this.value) || 0;
  });
  
  document.getElementById('bedTemp').addEventListener('change', function() {
    bedTempValue = parseInt(this.value) || 0;
  });
  
  // Начинаем обновление данных в реальном времени
  startRealTimeUpdates();
});

function getCurrentDistance() { return currentDistance; }

// Функция для начала обновления данных в реальном времени
function startRealTimeUpdates() {
  // Обновляем данные сразу при загрузке
  updatePrinterState();
  
  // Затем обновляем каждую секунду
  updateInterval = setInterval(updatePrinterState, 1000);
}

// Функция для обновления состояния принтера
async function updatePrinterState() {
  try {
    const response = await fetch('/api/state');
    if (response.ok) {
      const state = await response.json();
      
      // Обновляем отображение температур в новом формате
      updateTemperatureDisplay('extruder', state.temperature.extruder, state.target_temperature.extruder);
      updateTemperatureDisplay('bed', state.temperature.bed, state.target_temperature.bed);
      
      // Обновляем позиции
      document.getElementById('posX').textContent = state.position.x.toFixed(1);
      document.getElementById('posY').textContent = state.position.y.toFixed(1);
      document.getElementById('posZ').textContent = state.position.z.toFixed(1);
      
      // Обновляем статус принтера
      const printerStatus = document.querySelector('.printer-status');
      if (state.status === 'printing') {
        printerStatus.textContent = 'В работе';
        printerStatus.className = 'printer-status status-work';
      } else if (state.status === 'ready') {
        printerStatus.textContent = 'Готов к работе';
        printerStatus.className = 'printer-status';
      } else {
        printerStatus.textContent = state.status;
        printerStatus.className = 'printer-status';
      }
    }
  } catch (error) {
    console.error('Ошибка при обновлении состояния принтера:', error);
  }
}

// Функция для обновления отображения температуры
function updateTemperatureDisplay(type, currentTemp, targetTemp) {
  const currentTempElement = document.getElementById(`${type}CurrentTemp`);
  const targetTempElement = document.getElementById(`${type}TargetTemp`);
  
  // Обновляем текущую температуру
  currentTempElement.textContent = Math.round(currentTemp) + '°C';
  
  // Обновляем целевую температуру
  if (targetTemp > 0) {
    targetTempElement.textContent = Math.round(targetTemp) + '°C';
    // Меняем цвет текущей температуры на красный, если задана целевая температура
    currentTempElement.className = 'current-temp current-temp-red';
  } else {
    targetTempElement.textContent = '0';
    // Меняем цвет текущей температуры на синий, если целевая температура не задана
    currentTempElement.className = 'current-temp current-temp-blue';
  }
}

// Температурные функции
function setExtruderTemp() {
  // Используем сохраненное значение, а не значение из поля (которое может быть изменено API)
  sendCommand('temperature', { target: 'extruder', temperature: extruderTempValue });
  addConsoleMessage(`> Установка температуры экструдера: ${extruderTempValue}°C`);
}
function setBedTemp() {
  // Используем сохраненное значение, а не значение из поля (которое может быть изменено API)
  sendCommand('temperature', { target: 'bed', temperature: bedTempValue });
  addConsoleMessage(`> Установка температуры стола: ${bedTempValue}°C`);
}

// Управление осями
function moveAxis(axis, distance) {
  const command = `G91\nG1 ${axis}${distance} F3000\nG90`;
  sendCommand('command', { command: command });
  addConsoleMessage(`> Перемещение ${axis} на ${distance}мм`);
  // updatePosition(axis, distance); // Убираем симуляцию, так как получаем реальные данные
}
function homeAxis(axes) {
  const command = `G28 ${axes}`;
  sendCommand('home', { axis: axes === '●' ? 'all' : axes });
  addConsoleMessage(`> Возврат в ноль: ${axes}`);
  // Сбрасываем позиции на 0 (будут обновлены через API)
  // document.getElementById('posX').textContent = '0.0';
  // document.getElementById('posY').textContent = '0.0';
  // document.getElementById('posZ').textContent = '0.0';
}
function extrudeFilament(amount) {
  const command = `G91\nG1 E${amount} F300\nG90`;
  sendCommand('command', { command: command });
  const action = amount > 0 ? 'Подача' : 'Втягивание';
  addConsoleMessage(`> ${action} филамента: ${Math.abs(amount)}мм`);
}

// Функция для отправки команд на сервер
async function sendCommand(endpoint, data) {
  try {
    const response = await fetch(`/api/${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data)
    });
    
    const result = await response.json();
    if (result.success) {
      addConsoleMessage(`< ${result.message}`);
    } else {
      addConsoleMessage(`< Ошибка: ${result.message}`, 'error');
    }
    
    return result;
  } catch (error) {
    console.error('Ошибка при отправке команды:', error);
    addConsoleMessage(`< Ошибка: ${error.message}`, 'error');
    return { success: false, message: error.message };
  }
}

// G-code функции
function sendCustomGcode() {
  const input = document.getElementById('gcodeInput');
  const gcode = input.value.trim();
  if (gcode) {
    sendCommand('command', { command: gcode });
    input.value = '';
  }
}
function handleGcodeEnter(event) {
  if (event.key === 'Enter') { sendCustomGcode(); }
}

// Консольные функции
function addConsoleMessage(message, type = 'normal') {
  const output = document.getElementById('consoleOutput');
  const line = document.createElement('div');
  line.className = 'console-line';
  if (type === 'error') { line.style.color = '#ff6666'; }
  else if (message.startsWith('<')) { line.style.color = '#66ff66'; }
  else if (message.startsWith('>')) { line.style.color = '#6666ff'; }
  line.textContent = message;
  output.appendChild(line);
  output.scrollTop = output.scrollHeight;
}

// Обновление позиций теперь происходит через API, поэтому убираем симуляцию
// function updatePosition(axis, delta) {
//   if (axis.match(/[XYZ]/)) {
//     const posElement = document.getElementById('pos' + axis);
//     const currentPos = parseFloat(posElement.textContent);
//     posElement.textContent = (currentPos + delta).toFixed(1);
//   }
// }

// Убираем симуляцию времени печати, так как получаем реальные данные
// setInterval(() => {
//   const timeElement = document.getElementById('printTime');
//   const [hours, minutes, seconds] = timeElement.textContent.split(':').map(Number);
//   const totalSeconds = hours * 3600 + minutes * 60 + seconds + 1;
//   const newHours = Math.floor(totalSeconds / 3600);
//   const newMinutes = Math.floor((totalSeconds % 3600) / 60);
//   const newSecs = totalSeconds % 60;
//   timeElement.textContent = 
//     `${String(newHours).padStart(2, '0')}:${String(newMinutes).padStart(2, '0')}:${String(newSecs).padStart(2, '0')}`;
// }, 1000);