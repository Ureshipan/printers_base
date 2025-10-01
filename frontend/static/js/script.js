// Примерные данные, далее их можно динамизировать
const printers = [
  {
    name: 'Принтер 1', status: 'work', percent: 67, lastServed: '23.04.2025', material: 'PLA', model: 'ACUBE45'
  },
  {
    name: 'Принтер 2', status: 'error', percent: 0, lastServed: '12.07.2023', material: 'PLA', model: 'CAT'
  },
  {
    name: 'Принтер 3', status: 'idle', percent: 0, lastServed: '23.04.2025', material: 'PLA', model: 'поме'
  },
  {
    name: 'Принтер 4', status: 'service', percent: 0, lastServed: '23.04.2025', material: 'PLA', model: 'поме'
  },
  {
    name: 'Принтер 5', status: 'work', percent: 34, lastServed: '23.04.2025', material: 'PLA', model: 'ACUBE45'
  },
  {
    name: 'Принтер 6', status: 'work', percent: 99, lastServed: '23.04.2025', material: 'PLA', model: 'ACUBE45'
  }
];

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

// Рендер карточек принтеров
const printersGrid = document.getElementById('printersGrid');
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
    <div class="printer-card">
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
