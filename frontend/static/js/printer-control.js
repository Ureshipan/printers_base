let currentDistance = 0.1;
let updateInterval;
let extruderTempValue = 210; // Храним значение температуры экструдера
let bedTempValue = 60; // Храним значение температуры стола
let selectedPrinterId = null;
let printersCache = [];

// Инициализация
document.addEventListener('DOMContentLoaded', async function() {
  const printerTitle = document.getElementById('printerTitle');
  const printerDropdown = document.getElementById('printerDropdown');
  const printerStatus = document.getElementById('printerStatus');
  const maintenanceModal = document.getElementById('maintenanceModal');
  const closeModal = document.getElementById('closeModal');
  const confirmMaintenance = document.getElementById('confirmMaintenance');
  const filamentModal = document.getElementById('filamentModal');
  const closeFilamentModal = document.getElementById('closeFilamentModal');
  const confirmFilament = document.getElementById('confirmFilament');
  const body = document.body;

  // Навигация
  const sidebarButtons = document.querySelectorAll('.sidebar-btn');
  const currentPath = window.location.pathname;
  sidebarButtons.forEach(button => {
    const route = button.dataset.route;
    if (!route) {
      return;
    }
    if (route === currentPath) {
      button.classList.add('active');
    } else {
      button.classList.remove('active');
    }
    button.addEventListener('click', function() {
      if (window.location.pathname !== route) {
        window.location.href = route;
      }
    });
  });

  printerTitle.addEventListener('click', function() {
    if (!printersCache.length) return;
    printerDropdown.classList.toggle('show');
  });

  document.addEventListener('click', function(event) {
    if (!printerTitle.contains(event.target) && !printerDropdown.contains(event.target)) {
      printerDropdown.classList.remove('show');
    }
  });

  // Модалки предупреждений
  closeModal.addEventListener('click', function() {
    maintenanceModal.style.display = 'none';
  });
  confirmMaintenance.addEventListener('click', function() {
    maintenanceModal.style.display = 'none';
  });
  closeFilamentModal.addEventListener('click', function() {
    filamentModal.style.display = 'none';
  });
  confirmFilament.addEventListener('click', function() {
    filamentModal.style.display = 'none';
  });
  window.addEventListener('click', function(event) {
    if (event.target === maintenanceModal) {
      maintenanceModal.style.display = 'none';
    }
    if (event.target === filamentModal) {
      filamentModal.style.display = 'none';
    }
  });

  document.querySelectorAll('.distance-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      document.querySelectorAll('.distance-btn').forEach(b => b.classList.remove('active'));
      this.classList.add('active');
      currentDistance = parseFloat(this.dataset.distance);
    });
  });

  document.getElementById('extruderTemp').value = extruderTempValue;
  document.getElementById('bedTemp').value = bedTempValue;
  document.getElementById('extruderTemp').addEventListener('change', function() {
    extruderTempValue = parseInt(this.value) || 0;
  });
  document.getElementById('bedTemp').addEventListener('change', function() {
    bedTempValue = parseInt(this.value) || 0;
  });

  await loadPrinters(printerDropdown, printerTitle, printerStatus, body);
  startRealTimeUpdates();
});

function getCurrentDistance() { return currentDistance; }

async function loadPrinters(dropdown, titleEl, statusEl, body) {
  try {
    const response = await fetch('/api/printers');
    if (!response.ok) throw new Error('Не удалось загрузить принтеры');
    printersCache = await response.json();
  } catch (error) {
    console.error(error);
    printersCache = [];
  }

  dropdown.innerHTML = '';
  if (!printersCache.length) {
    dropdown.innerHTML = '<div class="dropdown-item disabled">Нет принтеров</div>';
    titleEl.textContent = '🖨️ Принтеры не найдены';
    statusEl.textContent = 'Нет данных';
    statusEl.className = 'printer-status';
    selectedPrinterId = null;
    return;
  }

  printersCache.forEach(printer => {
    const item = document.createElement('div');
    item.className = 'dropdown-item';
    item.dataset.printer = printer.id;
    item.textContent = `🖨️ ${printer.name}`;
    item.addEventListener('click', () => selectPrinter(printer.id, titleEl, statusEl, body, dropdown));
    dropdown.appendChild(item);
  });

  // Проверяем URL параметр printer_id
  const urlParams = new URLSearchParams(window.location.search);
  const requestedPrinterId = urlParams.get('printer_id');

  if (requestedPrinterId) {
    const printerId = parseInt(requestedPrinterId, 10);
    const printerExists = printersCache.some(p => p.id === printerId);
    if (printerExists) {
      selectPrinter(printerId, titleEl, statusEl, body, dropdown);
      return;
    }
  }

  // Если нет параметра или принтер не найден - выбираем первый
  selectPrinter(printersCache[0].id, titleEl, statusEl, body, dropdown);
}

function selectPrinter(printerId, titleEl, statusEl, body, dropdown) {
  selectedPrinterId = printerId;
  const printer = printersCache.find(p => p.id === printerId);
  if (!printer) {
    statusEl.textContent = 'Нет данных';
    statusEl.className = 'printer-status';
    return;
  }
  titleEl.textContent = `🖨️ ${printer.name}`;
  dropdown.classList.remove('show');
  updatePrinterStatusText(statusEl, printer.status, printer.percent);
  body.className = '';
  body.classList.add(`theme-${printer.status || 'idle'}`);

  // Очищаем консоль при смене принтера и показываем начальное сообщение
  clearConsole();
  addConsoleMessage(`> Выбран принтер: ${printer.name}`);

  // Сбрасываем флаг первого обновления для нового принтера
  isFirstUpdate = true;
  lastKnownStatus = null;

  // Обновляем сразу состояние выбранного принтера
  updatePrinterState();
}

function updatePrinterStatusText(statusEl, status, percent = 0) {
  const mapped = status === 'printing' ? 'work' :
    status === 'ready' || status === 'idle' || status === 'standby' ? 'idle' :
    status === 'paused' ? 'idle' :
    status === 'complete' ? 'idle' :
    status;

  let text = 'Готов к работе';
  let cls = 'printer-status';
  if (mapped === 'work') {
    text = `В работе${percent ? ` • ${percent}%` : ''}`;
    cls = 'printer-status status-work';
  } else if (mapped === 'error' || mapped === 'offline') {
    text = 'Ошибка/офлайн';
    cls = 'printer-status status-work';
  } else if (mapped === 'service') {
    text = 'Тех. осмотр';
    cls = 'printer-status status-work';
  }
  statusEl.textContent = text;
  statusEl.className = cls;
}

// Функция для начала обновления данных в реальном времени
function startRealTimeUpdates() {
  // Обновляем данные сразу при загрузке
  updatePrinterState();
  
  // Затем обновляем каждую секунду
  updateInterval = setInterval(updatePrinterState, 1000);
}

// Переменная для отслеживания первого обновления после выбора принтера
let isFirstUpdate = true;
let lastKnownStatus = null;

// Функция для обновления состояния принтера
async function updatePrinterState() {
  const statusEl = document.getElementById('printerStatus');
  if (!selectedPrinterId) {
    updateTemperatureDisplay('extruder', 0, 0);
    updateTemperatureDisplay('bed', 0, 0);
    statusEl.textContent = 'Нет принтера';
    statusEl.className = 'printer-status';
    return;
  }

  try {
    const response = await fetch(`/api/state?printer_id=${selectedPrinterId}`);
    if (!response.ok) {
      throw new Error('state request failed');
    }
    const state = await response.json();

    updateTemperatureDisplay('extruder', state.temperature.extruder, state.target_temperature.extruder);
    updateTemperatureDisplay('bed', state.temperature.bed, state.target_temperature.bed);

    document.getElementById('posX').textContent = state.position.x.toFixed(1);
    document.getElementById('posY').textContent = state.position.y.toFixed(1);
    document.getElementById('posZ').textContent = state.position.z.toFixed(1);

    updatePrinterStatusText(statusEl, state.status, state.progress);

    // Показываем информацию о состоянии при первом обновлении или при изменении статуса
    if (isFirstUpdate || lastKnownStatus !== state.status) {
      showStatusInConsole(state);
      lastKnownStatus = state.status;
      isFirstUpdate = false;
    }
  } catch (error) {
    console.error('Ошибка при обновлении состояния принтера:', error);
    updatePrinterStatusText(statusEl, 'error', 0);
    if (isFirstUpdate) {
      addConsoleMessage('> Не удалось получить данные принтера', 'error');
      isFirstUpdate = false;
    }
  }
}

// Показать состояние принтера в консоли
function showStatusInConsole(state) {
  const statusTexts = {
    'offline': 'Принтер офлайн',
    'error': 'Ошибка принтера',
    'printing': 'Идёт печать',
    'work': 'Идёт печать',
    'idle': 'Принтер готов к работе',
    'standby': 'Принтер в режиме ожидания',
    'paused': 'Печать приостановлена',
    'complete': 'Печать завершена'
  };

  const statusText = statusTexts[state.status] || `Статус: ${state.status}`;

  if (state.status === 'offline' || state.status === 'error') {
    addConsoleMessage(`> ${statusText}`, 'warning');
  } else {
    addConsoleMessage(`> ${statusText}`);
    // Показываем температуры только если принтер онлайн
    if (state.temperature.extruder > 0 || state.target_temperature.extruder > 0) {
      addConsoleMessage(`> Экструдер: ${Math.round(state.temperature.extruder)}°C / ${Math.round(state.target_temperature.extruder)}°C`);
    }
    if (state.temperature.bed > 0 || state.target_temperature.bed > 0) {
      addConsoleMessage(`> Стол: ${Math.round(state.temperature.bed)}°C / ${Math.round(state.target_temperature.bed)}°C`);
    }
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
    if (!selectedPrinterId) {
      addConsoleMessage('> Нет выбранного принтера');
      return;
    }
    const response = await fetch(`/api/${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ...data, printer_id: selectedPrinterId })
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
    addConsoleMessage(`> ${gcode}`);
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
  else if (type === 'warning') { line.style.color = '#ffaa66'; }
  else if (message.startsWith('<')) { line.style.color = '#66ff66'; }
  else if (message.startsWith('>')) { line.style.color = '#6666ff'; }
  line.textContent = message;
  output.appendChild(line);
  output.scrollTop = output.scrollHeight;
}

function clearConsole() {
  const output = document.getElementById('consoleOutput');
  output.innerHTML = '';
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
