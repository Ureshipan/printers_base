let currentDistance = 0.1;

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
});

function getCurrentDistance() { return currentDistance; }

// Температурные функции
function setExtruderTemp() {
  const temp = document.getElementById('extruderTemp').value;
  sendGcode(`M104 S${temp}`);
  addConsoleMessage(`> Установка температуры экструдера: ${temp}°C`);
}
function setBedTemp() {
  const temp = document.getElementById('bedTemp').value;
  sendGcode(`M140 S${temp}`);
  addConsoleMessage(`> Установка температуры стола: ${temp}°C`);
}

// Управление осями
function moveAxis(axis, distance) {
  sendGcode(`G91\nG1 ${axis}${distance} F3000\nG90`);
  addConsoleMessage(`> Перемещение ${axis} на ${distance}мм`);
  updatePosition(axis, distance);
}
function homeAxis(axes) {
  sendGcode(`G28 ${axes}`);
  addConsoleMessage(`> Возврат в ноль: ${axes}`);
  if (axes.includes('X') || axes === 'XY') document.getElementById('posX').textContent = '0.0';
  if (axes.includes('Y') || axes === 'XY') document.getElementById('posY').textContent = '0.0';
  if (axes.includes('Z')) document.getElementById('posZ').textContent = '0.0';
}
function extrudeFilament(amount) {
  sendGcode(`G91\nG1 E${amount} F300\nG90`);
  const action = amount > 0 ? 'Подача' : 'Втягивание';
  addConsoleMessage(`> ${action} филамента: ${Math.abs(amount)}мм`);
}

// G-code функции
function sendGcode(gcode) {
  console.log('Отправка G-code:', gcode);
  // Здесь будет реальная отправка команды на принтер
  setTimeout(() => {
    addConsoleMessage(`> ${gcode}`);
    addConsoleMessage('< ok');
  }, 100);
}

function sendCustomGcode() {
  const input = document.getElementById('gcodeInput');
  const gcode = input.value.trim();
  if (gcode) {
    sendGcode(gcode);
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

// Обновление позиций (симуляция)
function updatePosition(axis, delta) {
  if (axis.match(/[XYZ]/)) {
    const posElement = document.getElementById('pos' + axis);
    const currentPos = parseFloat(posElement.textContent);
    posElement.textContent = (currentPos + delta).toFixed(1);
  }
}

// Симуляция времени печати (можно отключить)
setInterval(() => {
  const timeElement = document.getElementById('printTime');
  const [hours, minutes, seconds] = timeElement.textContent.split(':').map(Number);
  const totalSeconds = hours * 3600 + minutes * 60 + seconds + 1;
  const newHours = Math.floor(totalSeconds / 3600);
  const newMinutes = Math.floor((totalSeconds % 3600) / 60);
  const newSecs = totalSeconds % 60;
  timeElement.textContent = 
    `${String(newHours).padStart(2, '0')}:${String(newMinutes).padStart(2, '0')}:${String(newSecs).padStart(2, '0')}`;
}, 1000);
