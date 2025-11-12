// Функция для получения данных о принтерах с сервера
async function fetchPrinters() {
  try {
    const response = await fetch('/api/printers');
    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.error('Ошибка при получении данных о принтерах:', error);
  }
  return [];
}

// Функция для рендеринга карточек принтеров
function renderPrinters(printers) {
  const printersGrid = document.getElementById('printersGrid');
  printersGrid.innerHTML = '';
  
  printers.forEach(p => {
    let statusClass = '';
    if (p.status === 'work') statusClass = 'status-work';
    else if (p.status === 'idle') statusClass = 'status-idle';
    else if (p.status === 'error') statusClass = 'status-error';
    else if (p.status === 'service') statusClass = 'status-service';

    let progClass = '';
    if (p.status === 'work') progClass = 'progress-work';
    else if (p.status === 'idle') progClass = 'progress-idle';
    else if (p.status === 'error') progClass = 'progress-error';
    else if (p.status === 'service') progClass = 'progress-service';

    printersGrid.innerHTML += `
      <div class="printer-card" onclick="selectPrinter(${p.id})">
        <div class="printer-header">
          <span class="printer-icon">🖨️</span>
          <span>${p.name}</span>
        </div>
        <div class="printer-prop">Материал - ${p.material}</div>
        <div class="printer-prop">Текущая модель - ${p.model}</div>
        <div class="printer-prop printer-status ${statusClass}">
          ${
            p.status === 'work' ? 'В работе' :
            p.status === 'idle' ? 'Простаивает' :
            p.status === 'error' ? 'Ошибка' :
            'Тех. осмотр'
          }
        </div>
        <div class="progress-bar"><div class="progress-inner ${progClass}" style="width:${p.percent}%"></div></div>
        <div class="printer-prop">Обслужен: ${p.lastServed}</div>
      </div>
    `;
  });
}

// Функция для выбора принтера
function selectPrinter(printerId) {
  // Перенаправляем на страницу управления принтером
  window.location.href = '/printer-control';
}

// Рендер таблицы материалов (оставляем как есть)
const materials = [
  { name: 'Катушка 1 от WHO', material: 'PLA', color: 'Голубой', amount: 32.3, price: '1 437,99' },
  { name: 'Катушка 1 от WHO', material: 'PLA', color: 'Чёрный', amount: 56.7, price: '1245' },
  { name: 'Катушка 1 от WHO', material: 'PLA', color: 'Жёлтый', amount: 23.1, price: '1 437,99' },
  { name: 'Катушка 1 от WHO', material: 'PLA', color: 'Красный', amount: 40, price: '1 437,99' }
];

const queue = [
  { model: 'АОАОТАО.GCODE?', printer: 'ENDER-FIGENDER', status: '99%' },
  { model: 'АОАОТАО.GCODE?', printer: 'ENDER-FIGENDER', status: '70%' },
  { model: 'ACUBE45', printer: 'ENDER-FIGENDER', status: '7%' },
  { model: 'CAT', printer: 'ENDER-FIGENDER', status: '0%' }
];

// Рендер таблицы материалов
const materialsTable = document.getElementById('materialsTable');
materials.forEach(m => {
  materialsTable.innerHTML += `
    <tr>
      <td>${m.name}</td>
      <td>${m.material}</td>
      <td>${m.color}</td>
      <td>${m.amount}</td>
      <td>${m.price}</td>
    </tr>
  `;
});

// Рендер очереди
const queueTable = document.getElementById('queueTable');
queue.forEach(q => {
  queueTable.innerHTML += `
    <tr>
      <td>${q.model}</td>
      <td>${q.printer}</td>
      <td style="text-align:right">${q.status}</td>
    </tr>
  `;
});

// Инициализация - загружаем данные о принтерах при загрузке страницы
document.addEventListener('DOMContentLoaded', async function() {
  // Добавляем обработчики для кнопок навигации
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
  
  const printers = await fetchPrinters();
  renderPrinters(printers);
});