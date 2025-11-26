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

async function fetchCoils() {
  try {
    const response = await fetch('/api/coils');
    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.error('Ошибка при получении материалов:', error);
  }
  return [];
}

async function fetchTasks() {
  try {
    const response = await fetch('/api/tasks');
    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.error('Ошибка при получении задач:', error);
  }
  return [];
}

// Функция для рендеринга карточек принтеров
function renderPrinters(printers) {
  const printersGrid = document.getElementById('printersGrid');
  printersGrid.innerHTML = '';
  if (!printers.length) {
    printersGrid.innerHTML = '<div style="color:#8f94d1">Принтеры не найдены</div>';
    updatePrinterStats([]);
    return;
  }
  
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

  updatePrinterStats(printers);
}

function updatePrinterStats(printers) {
  const statTotal = document.getElementById('statTotal');
  const statWork = document.getElementById('statWork');
  const statIdle = document.getElementById('statIdle');
  const statError = document.getElementById('statError');
  const statService = document.getElementById('statService');

  const stats = { work: 0, idle: 0, error: 0, service: 0 };
  printers.forEach(p => {
    if (p.status === 'work') stats.work += 1;
    else if (p.status === 'error' || p.status === 'offline') stats.error += 1;
    else if (p.status === 'service') stats.service += 1;
    else stats.idle += 1;
  });

  if (statTotal) statTotal.textContent = printers.length;
  if (statWork) statWork.textContent = stats.work;
  if (statIdle) statIdle.textContent = stats.idle;
  if (statError) statError.textContent = stats.error;
  if (statService) statService.textContent = stats.service;
}

function renderMaterials(coils) {
  const materialsTable = document.getElementById('materialsTable');
  if (!materialsTable) return;
  materialsTable.innerHTML = '';
  if (!coils.length) {
    materialsTable.innerHTML = `<tr><td colspan="5" style="text-align:center; color:#8f94d1; padding:12px;">Нет данных о катушках</td></tr>`;
    return;
  }
  coils.forEach(c => {
    materialsTable.innerHTML += `
      <tr>
        <td>${c.name}</td>
        <td>${c.material || '—'}</td>
        <td>—</td>
        <td>${c.remains ?? '—'}</td>
        <td>—</td>
      </tr>
    `;
  });
}

function renderQueue(tasks) {
  const queueTable = document.getElementById('queueTable');
  if (!queueTable) return;
  queueTable.innerHTML = '';
  if (!tasks.length) {
    queueTable.innerHTML = `<tr><td colspan="3" style="text-align:center; color:#8f94d1; padding:12px;">Очередь пуста</td></tr>`;
    return;
  }

  const statusLabels = {
    pending: 'Ожидает',
    queued: 'В очереди',
    printing: 'Печатается',
    completed: 'Завершена',
    cancelled: 'Отменена'
  };

  const sortedTasks = [...tasks].sort((a, b) => {
    if (a.created_at && b.created_at) {
      return new Date(b.created_at) - new Date(a.created_at);
    }
    return 0;
  });

  sortedTasks.slice(0, 6).forEach(t => {
    queueTable.innerHTML += `
      <tr>
        <td>${t.name || t.gcode?.original_name || 'Модель'}</td>
        <td>${t.printer?.name || '—'}</td>
        <td style="text-align:right">${statusLabels[t.status] || t.status || '—'}</td>
      </tr>
    `;
  });
}

// Функция для выбора принтера
function selectPrinter(printerId) {
  // Перенаправляем на страницу управления принтером
  window.location.href = '/printer-control';
}

function openAddPrinterModal(modal, ipInput, errorBox, portInput) {
  errorBox.textContent = '';
  modal.classList.add('open');
  ipInput.focus();
}

function closeAddPrinterModal(modal, form, errorBox, portInput) {
  modal.classList.remove('open');
  if (form) form.reset();
  if (portInput) portInput.value = '7125';
  if (errorBox) errorBox.textContent = '';
}

async function submitAddPrinter(form, errorBox, ipInput, portInput) {
  errorBox.textContent = '';
  const host = ipInput.value.trim();
  const port = parseInt(portInput.value, 10) || 7125;
  if (!host) {
    errorBox.textContent = 'Введите IP адрес';
    return;
  }

  try {
    const response = await fetch('/api/printers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ host, port })
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      errorBox.textContent = data.message || 'Не удалось добавить принтер';
      return;
    }
    closeAddPrinterModal(
      document.getElementById('addPrinterModal'),
      form,
      errorBox,
      portInput
    );
    const printers = await fetchPrinters();
    renderPrinters(printers);
  } catch (error) {
    console.error('Ошибка при добавлении принтера:', error);
    errorBox.textContent = 'Ошибка подключения к серверу';
  }
}

function openAddVirtualModal(modal, nameInput, errorBox) {
  errorBox.textContent = '';
  modal.classList.add('open');
  nameInput.focus();
}

function closeAddVirtualModal(modal, form, errorBox) {
  modal.classList.remove('open');
  if (form) form.reset();
  if (errorBox) errorBox.textContent = '';
}

async function submitAddVirtual(form, errorBox, nameInput, statusInput) {
  errorBox.textContent = '';
  const name = nameInput.value.trim();
  const status = statusInput.value || 'idle';
  if (!name) {
    errorBox.textContent = 'Введите имя принтера';
    return;
  }

  try {
    const response = await fetch('/api/printers/virtual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, status })
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      errorBox.textContent = data.message || 'Не удалось добавить принтер';
      return;
    }
    closeAddVirtualModal(
      document.getElementById('addVirtualModal'),
      form,
      errorBox
    );
    const printers = await fetchPrinters();
    renderPrinters(printers);
  } catch (error) {
    console.error('Ошибка при добавлении виртуального принтера:', error);
    errorBox.textContent = 'Ошибка подключения к серверу';
  }
}

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
  const coils = await fetchCoils();
  renderMaterials(coils);
  const tasks = await fetchTasks();
  renderQueue(tasks);

  const addPrinterModal = document.getElementById('addPrinterModal');
  const openAddPrinterBtn = document.getElementById('openAddPrinterBtn');
  const closeAddPrinterBtn = document.getElementById('closeAddPrinterBtn');
  const cancelAddPrinterBtn = document.getElementById('cancelAddPrinterBtn');
  const addPrinterForm = document.getElementById('addPrinterForm');
  const addPrinterError = document.getElementById('addPrinterError');
  const printerIpInput = document.getElementById('printerIpInput');
  const printerPortInput = document.getElementById('printerPortInput');

  if (openAddPrinterBtn && addPrinterModal) {
    openAddPrinterBtn.addEventListener('click', () =>
      openAddPrinterModal(addPrinterModal, printerIpInput, addPrinterError, printerPortInput)
    );
  }
  [closeAddPrinterBtn, cancelAddPrinterBtn].forEach(btn => {
    if (btn) {
      btn.addEventListener('click', () =>
        closeAddPrinterModal(addPrinterModal, addPrinterForm, addPrinterError, printerPortInput)
      );
    }
  });

  if (addPrinterForm) {
    addPrinterForm.addEventListener('submit', (e) => {
      e.preventDefault();
      submitAddPrinter(addPrinterForm, addPrinterError, printerIpInput, printerPortInput);
    });
  }

  const addVirtualModal = document.getElementById('addVirtualModal');
  const openAddVirtualBtn = document.getElementById('openAddVirtualBtn');
  const closeAddVirtualBtn = document.getElementById('closeAddVirtualBtn');
  const cancelAddVirtualBtn = document.getElementById('cancelAddVirtualBtn');
  const addVirtualForm = document.getElementById('addVirtualForm');
  const addVirtualError = document.getElementById('addVirtualError');
  const virtualNameInput = document.getElementById('virtualNameInput');
  const virtualStatusInput = document.getElementById('virtualStatusInput');

  if (openAddVirtualBtn && addVirtualModal) {
    openAddVirtualBtn.addEventListener('click', () =>
      openAddVirtualModal(addVirtualModal, virtualNameInput, addVirtualError)
    );
  }
  [closeAddVirtualBtn, cancelAddVirtualBtn].forEach(btn => {
    if (btn) {
      btn.addEventListener('click', () =>
        closeAddVirtualModal(addVirtualModal, addVirtualForm, addVirtualError)
      );
    }
  });

  if (addVirtualForm) {
    addVirtualForm.addEventListener('submit', (e) => {
      e.preventDefault();
      submitAddVirtual(addVirtualForm, addVirtualError, virtualNameInput, virtualStatusInput);
    });
  }
});
