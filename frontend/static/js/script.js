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

// Кэш предыдущих статусов и фильтр
let previousPrinterStatuses = {};
let showOnlyErrors = false;

// Запрос разрешения на браузерные уведомления
if ('Notification' in window && Notification.permission === 'default') {
  Notification.requestPermission();
}

// Проверка на новые ошибки и браузерное уведомление
function checkForNewErrors(printers) {
  printers.forEach(p => {
    const prevStatus = previousPrinterStatuses[p.id];
    if (p.status === 'error' && prevStatus !== 'error') {
      // Браузерное уведомление
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('Ошибка принтера', {
          body: `${p.name}: обнаружена ошибка!`,
          icon: '/static/img/error-icon.png'
        });
      }
    }
    // Показать модальное окно при завершении печати
    if (p.status === 'awaiting_removal' && prevStatus !== 'awaiting_removal') {
      showRemovalModal(p.id, p.name);
    }
    previousPrinterStatuses[p.id] = p.status;
  });
}

// Подтверждение уборки детали со стола
async function confirmRemoval(printerId) {
  try {
    const response = await fetch(`/api/printers/${printerId}/confirm-removal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await response.json();
    if (data.success) {
      // Перезагрузить список принтеров
      const printers = await fetchPrinters();
      renderPrinters(printers);
      // Закрыть модальное окно если открыто
      closeRemovalModal();
    }
  } catch (error) {
    console.error('Ошибка при подтверждении уборки:', error);
  }
}

// Модальное окно подтверждения уборки
let pendingRemovalPrinterId = null;

function showRemovalModal(printerId, printerName) {
  pendingRemovalPrinterId = printerId;
  const modal = document.getElementById('removalModal');
  const nameEl = document.getElementById('removalPrinterName');
  if (modal && nameEl) {
    nameEl.textContent = printerName;
    modal.classList.add('open');
  }
}

function closeRemovalModal() {
  const modal = document.getElementById('removalModal');
  if (modal) modal.classList.remove('open');
  pendingRemovalPrinterId = null;
}

function submitRemovalConfirm() {
  if (pendingRemovalPrinterId) {
    confirmRemoval(pendingRemovalPrinterId);
  }
}

// Функция для рендеринга карточек принтеров
function renderPrinters(printers) {
  printersDataCache = printers; // Сохраняем для редактирования

  // Проверка на новые ошибки и завершение печати
  checkForNewErrors(printers);

  const printersGrid = document.getElementById('printersGrid');
  printersGrid.innerHTML = '';

  // Применяем фильтр если включен
  let displayPrinters = printers;
  if (showOnlyErrors) {
    displayPrinters = printers.filter(p => p.status === 'error');
  }

  if (!displayPrinters.length) {
    printersGrid.innerHTML = showOnlyErrors
      ? '<div style="color:#8f94d1">Нет принтеров с ошибками</div>'
      : '<div style="color:#8f94d1">Принтеры не найдены</div>';
    updatePrinterStats(printers); // Статистика по всем принтерам
    return;
  }

  displayPrinters.forEach(p => {
    const isOffline = p.status === 'offline';
    const isError = p.status === 'error';
    const isAwaitingRemoval = p.status === 'awaiting_removal';
    const isVirtualPrinter = p.is_virtual || false;

    let statusClass = '';
    if (p.status === 'work') statusClass = 'status-work';
    else if (p.status === 'idle') statusClass = 'status-idle';
    else if (p.status === 'error') statusClass = 'status-error';
    else if (p.status === 'service') statusClass = 'status-service';
    else if (p.status === 'offline') statusClass = 'status-offline';
    else if (p.status === 'paused') statusClass = 'status-paused';
    else if (p.status === 'awaiting_removal') statusClass = 'status-awaiting_removal';

    let progClass = '';
    if (p.status === 'work') progClass = 'progress-work';
    else if (p.status === 'idle') progClass = 'progress-idle';
    else if (p.status === 'error') progClass = 'progress-error';
    else if (p.status === 'service') progClass = 'progress-service';
    else if (p.status === 'offline') progClass = 'progress-offline';
    else if (p.status === 'paused') progClass = 'progress-paused';

    const statusText =
      p.status === 'work' ? 'В работе' :
      p.status === 'idle' ? 'Простаивает' :
      p.status === 'error' ? 'Ошибка' :
      p.status === 'offline' ? 'Нет связи' :
      p.status === 'paused' ? 'Пауза' :
      p.status === 'awaiting_removal' ? 'Ожидает уборки' :
      'Тех. осмотр';

    const needsMaintenance = p.needs_maintenance || false;
    let cardClass = isOffline ? 'printer-card offline' : 'printer-card';
    if (needsMaintenance && !isOffline) cardClass += ' needs-maintenance';
    if (isError) cardClass += ' has-error';
    if (isAwaitingRemoval) cardClass += ' awaiting-removal';
    if (isVirtualPrinter) cardClass += ' offline-manual';

    const offlineBadge = isOffline ? '<span class="offline-badge">⚠ НЕТ СВЯЗИ</span>' : '';
    const virtualBadge = isVirtualPrinter && !isOffline ? '<span class="virtual-badge">ОФФЛАЙН</span>' : '';
    const maintenanceBadge = (needsMaintenance && !isOffline) ? '<span class="maintenance-badge">🔧 ОБСЛУЖИВАНИЕ</span>' : '';

    // Кнопка подтверждения уборки детали
    const removalButton = isAwaitingRemoval
      ? `<button class="confirm-removal-btn" onclick="event.stopPropagation(); confirmRemoval(${p.id})">✓ Деталь убрана</button>`
      : '';

    printersGrid.innerHTML += `
      <div class="${cardClass}">
        ${offlineBadge}
        ${virtualBadge}
        ${maintenanceBadge}
        <button class="edit-printer-btn" onclick="event.stopPropagation(); openEditPrinterModal(${p.id})" title="Редактировать">✎</button>
        <div class="printer-card-content" onclick="selectPrinter(${p.id})">
          <div class="printer-header">
            <span class="printer-icon">🖨️</span>
            <span>${p.name}</span>
          </div>
          <div class="printer-prop">Материал - ${p.material} | Сопло ${p.nozzle_diameter || 0.4} мм</div>
          <div class="printer-prop">Текущая модель - ${isOffline ? '—' : p.model}</div>
          <div class="printer-prop printer-status ${statusClass}">${statusText}</div>
          <div class="progress-bar"><div class="progress-inner ${progClass}" style="width:${p.percent}%"></div></div>
          <div class="printer-prop">Обслужен: ${p.lastServed}</div>
          ${removalButton}
        </div>
      </div>
    `;
  });

  updatePrinterStats(printers); // Статистика по всем принтерам
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
        <td>${c.remains != null ? parseFloat(c.remains).toFixed(1) : '—'}</td>
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

  // Обработчик фильтра "Только с ошибками"
  const filterErrorsBtn = document.getElementById('filterErrorsBtn');
  if (filterErrorsBtn) {
    filterErrorsBtn.addEventListener('click', () => {
      showOnlyErrors = !showOnlyErrors;
      filterErrorsBtn.classList.toggle('active', showOnlyErrors);
      filterErrorsBtn.textContent = showOnlyErrors ? '✕ Показать все' : '⚠️ Только ошибки';
      renderPrinters(printersDataCache);
    });
  }

  // Обработчики модального окна подтверждения уборки
  const closeRemovalBtn = document.getElementById('closeRemovalBtn');
  const cancelRemovalBtn = document.getElementById('cancelRemovalBtn');
  const confirmRemovalBtn = document.getElementById('confirmRemovalBtn');

  [closeRemovalBtn, cancelRemovalBtn].forEach(btn => {
    if (btn) btn.addEventListener('click', closeRemovalModal);
  });

  if (confirmRemovalBtn) {
    confirmRemovalBtn.addEventListener('click', submitRemovalConfirm);
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
  const offlineFields = document.getElementById('offlineFieldsGroup');

  if (printer.is_virtual) {
    hostField.style.display = 'none';
    portField.style.display = 'none';
    statusField.style.display = 'block';
    offlineFields.style.display = 'block';
    document.getElementById('editPrinterStatus').value = printer.status || 'idle';

    // Заполняем оффлайн-поля
    const filenameInput = document.getElementById('editPrinterFilename');
    const progressInput = document.getElementById('editPrinterProgress');
    const progressSlider = document.getElementById('editPrinterProgressSlider');

    filenameInput.value = printer.model !== 'Неизвестная модель' ? printer.model : '';
    progressInput.value = printer.percent || 0;
    progressSlider.value = printer.percent || 0;

    // Синхронизация слайдера с инпутом
    progressInput.oninput = () => { progressSlider.value = progressInput.value; };
    progressSlider.oninput = () => { progressInput.value = progressSlider.value; };
  } else {
    hostField.style.display = 'block';
    portField.style.display = 'block';
    statusField.style.display = 'none';
    offlineFields.style.display = 'none';
    // Для реальных принтеров нужно получить данные из API
    fetchPrinterDetails(printerId);
  }

  // Устанавливаем значение сопла из кэша
  document.getElementById('editPrinterNozzle').value = printer.nozzle_diameter || 0.4;

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

  // Диаметр сопла для всех принтеров
  const nozzle = parseFloat(document.getElementById('editPrinterNozzle').value) || 0.4;
  payload.nozzle_diameter = nozzle;

  if (currentEditPrinter && currentEditPrinter.is_virtual) {
    payload.status = document.getElementById('editPrinterStatus').value;
    // Оффлайн-поля
    const filename = document.getElementById('editPrinterFilename').value.trim();
    const progress = parseInt(document.getElementById('editPrinterProgress').value, 10) || 0;
    payload.manual_filename = filename || null;
    payload.manual_progress = progress;
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
