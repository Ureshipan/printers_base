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

// Глобальный кэш принтеров для редактирования
let printersDataCache = [];

// Функция для рендеринга карточек принтеров
function renderPrinters(printers) {
  printersDataCache = printers; // Сохраняем для редактирования
  const printersGrid = document.getElementById('printersGrid');
  printersGrid.innerHTML = '';
  if (!printers.length) {
    printersGrid.innerHTML = '<div style="color:#8f94d1">Принтеры не найдены</div>';
    updatePrinterStats([]);
    return;
  }

  printers.forEach(p => {
    const isOffline = p.status === 'offline';

    let statusClass = '';
    if (p.status === 'work') statusClass = 'status-work';
    else if (p.status === 'idle') statusClass = 'status-idle';
    else if (p.status === 'error') statusClass = 'status-error';
    else if (p.status === 'service') statusClass = 'status-service';
    else if (p.status === 'offline') statusClass = 'status-offline';

    let progClass = '';
    if (p.status === 'work') progClass = 'progress-work';
    else if (p.status === 'idle') progClass = 'progress-idle';
    else if (p.status === 'error') progClass = 'progress-error';
    else if (p.status === 'service') progClass = 'progress-service';
    else if (p.status === 'offline') progClass = 'progress-offline';

    const statusText =
      p.status === 'work' ? 'В работе' :
      p.status === 'idle' ? 'Простаивает' :
      p.status === 'error' ? 'Ошибка' :
      p.status === 'offline' ? 'Нет связи' :
      'Тех. осмотр';

    const needsMaintenance = p.needs_maintenance || false;
    let cardClass = isOffline ? 'printer-card offline' : 'printer-card';
    if (needsMaintenance && !isOffline) cardClass += ' needs-maintenance';
    const offlineBadge = isOffline ? '<span class="offline-badge">⚠ НЕТ СВЯЗИ</span>' : '';
    const maintenanceBadge = (needsMaintenance && !isOffline) ? '<span class="maintenance-badge">🔧 ОБСЛУЖИВАНИЕ</span>' : '';

    printersGrid.innerHTML += `
      <div class="${cardClass}">
        ${offlineBadge}
        ${maintenanceBadge}
        <button class="edit-printer-btn" onclick="event.stopPropagation(); openEditPrinterModal(${p.id})" title="Редактировать">✎</button>
        <div class="printer-card-content" onclick="selectPrinter(${p.id})">
          <div class="printer-header">
            <span class="printer-icon">🖨️</span>
            <span>${p.name}</span>
          </div>
          <div class="printer-prop">Материал - ${p.material}</div>
          <div class="printer-prop">Текущая модель - ${isOffline ? '—' : p.model}</div>
          <div class="printer-prop printer-status ${statusClass}">${statusText}</div>
          <div class="progress-bar"><div class="progress-inner ${progClass}" style="width:${p.percent}%"></div></div>
          <div class="printer-prop">Обслужен: ${p.lastServed}</div>
        </div>
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
  const statOffline = document.getElementById('statOffline');

  const stats = { work: 0, idle: 0, error: 0, service: 0, offline: 0 };
  printers.forEach(p => {
    if (p.status === 'work') stats.work += 1;
    else if (p.status === 'offline') stats.offline += 1;
    else if (p.status === 'error') stats.error += 1;
    else if (p.status === 'service') stats.service += 1;
    else stats.idle += 1;
  });

  if (statTotal) statTotal.textContent = printers.length;
  if (statWork) statWork.textContent = stats.work;
  if (statIdle) statIdle.textContent = stats.idle;
  if (statError) statError.textContent = stats.error;
  if (statService) statService.textContent = stats.service;
  if (statOffline) statOffline.textContent = stats.offline;
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
  // Перенаправляем на страницу управления принтером с ID принтера
  window.location.href = `/printer-control?printer_id=${printerId}`;
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

  // Обработчики для редактирования принтера
  const editPrinterModal = document.getElementById('editPrinterModal');
  const closeEditPrinterBtn = document.getElementById('closeEditPrinterBtn');
  const cancelEditPrinterBtn = document.getElementById('cancelEditPrinterBtn');
  const editPrinterForm = document.getElementById('editPrinterForm');
  const deletePrinterBtn = document.getElementById('deletePrinterBtn');

  [closeEditPrinterBtn, cancelEditPrinterBtn].forEach(btn => {
    if (btn) {
      btn.addEventListener('click', closeEditPrinterModal);
    }
  });

  if (editPrinterForm) {
    editPrinterForm.addEventListener('submit', (e) => {
      e.preventDefault();
      submitEditPrinter();
    });
  }

  if (deletePrinterBtn) {
    deletePrinterBtn.addEventListener('click', () => {
      // Сначала открываем модалку подтверждения, потом закрываем редактирование
      // (чтобы currentEditPrinter не был null)
      openConfirmDeleteModal();
      document.getElementById('editPrinterModal').classList.remove('open');
    });
  }

  // Обработчики для подтверждения удаления
  const confirmDeleteModal = document.getElementById('confirmDeleteModal');
  const closeConfirmDeleteBtn = document.getElementById('closeConfirmDeleteBtn');
  const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
  const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');

  [closeConfirmDeleteBtn, cancelDeleteBtn].forEach(btn => {
    if (btn) {
      btn.addEventListener('click', closeConfirmDeleteModal);
    }
  });

  if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener('click', confirmDeletePrinter);
  }
});

// Переменная для хранения данных редактируемого принтера
let currentEditPrinter = null;

// Открытие модалки редактирования
function openEditPrinterModal(printerId) {
  const printer = printersDataCache.find(p => p.id === printerId);
  if (!printer) return;

  currentEditPrinter = printer;

  document.getElementById('editPrinterId').value = printer.id;
  document.getElementById('editPrinterName').value = printer.name || '';
  document.getElementById('editPrinterError').textContent = '';

  // Для виртуальных принтеров показываем статус, скрываем IP/порт
  const hostField = document.getElementById('editPrinterHostField');
  const portField = document.getElementById('editPrinterPortField');
  const statusField = document.getElementById('editPrinterStatusField');

  if (printer.is_virtual) {
    hostField.style.display = 'none';
    portField.style.display = 'none';
    statusField.style.display = 'block';
    document.getElementById('editPrinterStatus').value = printer.status || 'idle';
  } else {
    hostField.style.display = 'block';
    portField.style.display = 'block';
    statusField.style.display = 'none';
    // Для реальных принтеров нужно получить данные из API
    fetchPrinterDetails(printerId);
  }

  document.getElementById('editPrinterModal').classList.add('open');
}

// Получение детальной информации о принтере
async function fetchPrinterDetails(printerId) {
  try {
    const response = await fetch(`/api/printers/${printerId}`);
    if (response.ok) {
      const data = await response.json();
      if (data.success && data.printer) {
        document.getElementById('editPrinterHost').value = data.printer.host || '';
        document.getElementById('editPrinterPort').value = data.printer.port || 7125;
      }
    }
  } catch (error) {
    console.error('Ошибка получения данных принтера:', error);
  }
}

// Закрытие модалки редактирования
function closeEditPrinterModal() {
  document.getElementById('editPrinterModal').classList.remove('open');
  document.getElementById('editPrinterForm').reset();
  document.getElementById('editPrinterError').textContent = '';
  currentEditPrinter = null;
}

// Отправка изменений
async function submitEditPrinter() {
  const errorBox = document.getElementById('editPrinterError');
  errorBox.textContent = '';

  const printerId = document.getElementById('editPrinterId').value;
  const name = document.getElementById('editPrinterName').value.trim();

  if (!name) {
    errorBox.textContent = 'Введите название принтера';
    return;
  }

  const payload = { name };

  if (currentEditPrinter && currentEditPrinter.is_virtual) {
    payload.status = document.getElementById('editPrinterStatus').value;
  } else {
    const host = document.getElementById('editPrinterHost').value.trim();
    const port = parseInt(document.getElementById('editPrinterPort').value, 10) || 7125;
    if (host) {
      payload.host = host;
      payload.port = port;
    }
  }

  try {
    const response = await fetch(`/api/printers/${printerId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await response.json();

    if (!response.ok || !data.success) {
      errorBox.textContent = data.message || 'Не удалось обновить принтер';
      return;
    }

    closeEditPrinterModal();
    const printers = await fetchPrinters();
    renderPrinters(printers);
  } catch (error) {
    console.error('Ошибка при обновлении принтера:', error);
    errorBox.textContent = 'Ошибка подключения к серверу';
  }
}

// Открытие модалки подтверждения удаления
function openConfirmDeleteModal() {
  if (!currentEditPrinter) return;

  document.getElementById('deletePrinterName').textContent = currentEditPrinter.name;
  document.getElementById('deleteError').textContent = '';
  document.getElementById('confirmDeleteModal').classList.add('open');
}

// Закрытие модалки подтверждения удаления
function closeConfirmDeleteModal() {
  document.getElementById('confirmDeleteModal').classList.remove('open');
  document.getElementById('deleteError').textContent = '';
}

// Удаление принтера
async function confirmDeletePrinter() {
  if (!currentEditPrinter) return;

  const errorBox = document.getElementById('deleteError');
  errorBox.textContent = '';

  try {
    const response = await fetch(`/api/printers/${currentEditPrinter.id}`, {
      method: 'DELETE'
    });
    const data = await response.json();

    if (!response.ok || !data.success) {
      errorBox.textContent = data.message || 'Не удалось удалить принтер';
      return;
    }

    closeConfirmDeleteModal();
    currentEditPrinter = null;
    const printers = await fetchPrinters();
    renderPrinters(printers);
  } catch (error) {
    console.error('Ошибка при удалении принтера:', error);
    errorBox.textContent = 'Ошибка подключения к серверу';
  }
}
