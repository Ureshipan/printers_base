// Spools Page JavaScript

// Глобальные данные
let coilsData = [];
let filamentsData = [];
let vendorsData = [];
let currentTab = 'coils';

// DOM элементы - Табы
const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');
const tabActions = document.querySelectorAll('.tab-action');

// DOM элементы - Катушки
const coilsTableBody = document.getElementById('coilsTableBody');
const filterFilament = document.getElementById('filterFilament');
const filterVendor = document.getElementById('filterVendor');
const filterStatus = document.getElementById('filterStatus');
const searchInput = document.getElementById('searchInput');

// DOM элементы - Филаменты
const filamentsTableBody = document.getElementById('filamentsTableBody');
const filterFilamentVendor = document.getElementById('filterFilamentVendor');
const searchFilamentInput = document.getElementById('searchFilamentInput');

// DOM элементы - Производители
const vendorsTableBody = document.getElementById('vendorsTableBody');
const searchVendorInput = document.getElementById('searchVendorInput');

// Статистика
const statTotalCoils = document.getElementById('statTotalCoils');
const statTotalWeight = document.getElementById('statTotalWeight');
const statLowStock = document.getElementById('statLowStock');
const statArchived = document.getElementById('statArchived');
const statTotalFilaments = document.getElementById('statTotalFilaments');
const statTotalVendors = document.getElementById('statTotalVendors');

// Модальные окна
const coilModal = document.getElementById('coilModal');
const filamentModal = document.getElementById('filamentModal');
const vendorModal = document.getElementById('vendorModal');
const historyModal = document.getElementById('historyModal');
const adjustModal = document.getElementById('adjustModal');

// Формы
const coilForm = document.getElementById('coilForm');
const filamentForm = document.getElementById('filamentForm');
const vendorForm = document.getElementById('vendorForm');
const adjustForm = document.getElementById('adjustForm');

// Навигация по sidebar
document.querySelectorAll('.sidebar-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    window.location.href = btn.dataset.route;
  });
});

// =============== Табы ===============

function switchTab(tabName) {
  currentTab = tabName;

  // Переключение кнопок табов
  tabButtons.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });

  // Переключение контента табов
  tabContents.forEach(content => {
    content.classList.toggle('active', content.dataset.tab === tabName);
  });

  // Переключение кнопок действий
  tabActions.forEach(action => {
    action.classList.toggle('hidden', action.dataset.tab !== tabName);
  });
}

tabButtons.forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// =============== API Функции ===============

async function fetchCoils() {
  const includeArchived = filterStatus.value === 'all' || filterStatus.value === 'archived';
  let url = `/api/coils?include_archived=${includeArchived ? '1' : '0'}`;
  if (filterStatus.value === 'archived') {
    url += '&archived=true';
  }
  const response = await fetch(url);
  return response.json();
}

async function fetchFilaments() {
  const response = await fetch('/api/filaments');
  return response.json();
}

async function fetchVendors() {
  const response = await fetch('/api/vendors');
  return response.json();
}

async function createCoil(data) {
  const response = await fetch('/api/coils', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return response.json();
}

async function updateCoil(id, data) {
  const response = await fetch(`/api/coils/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return response.json();
}

async function deleteCoil(id) {
  const response = await fetch(`/api/coils/${id}`, { method: 'DELETE' });
  return response.json();
}

async function archiveCoil(id) {
  const response = await fetch(`/api/coils/${id}/archive`, { method: 'POST' });
  return response.json();
}

async function unarchiveCoil(id) {
  const response = await fetch(`/api/coils/${id}/unarchive`, { method: 'POST' });
  return response.json();
}

async function adjustCoilRemains(id, newRemains, notes) {
  const response = await fetch(`/api/coils/${id}/adjust`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_remains: newRemains, notes })
  });
  return response.json();
}

async function fetchCoilHistory(id) {
  const response = await fetch(`/api/coils/${id}/history`);
  return response.json();
}

// Filament API
async function createFilament(data) {
  const response = await fetch('/api/filaments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return response.json();
}

async function updateFilament(id, data) {
  const response = await fetch(`/api/filaments/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return response.json();
}

async function deleteFilament(id) {
  const response = await fetch(`/api/filaments/${id}`, { method: 'DELETE' });
  return response.json();
}

// Vendor API
async function createVendor(data) {
  const response = await fetch('/api/vendors', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return response.json();
}

async function updateVendor(id, data) {
  const response = await fetch(`/api/vendors/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return response.json();
}

async function deleteVendor(id) {
  const response = await fetch(`/api/vendors/${id}`, { method: 'DELETE' });
  return response.json();
}

// =============== Рендеринг Катушек ===============

function renderCoilsTable(coils) {
  const search = searchInput.value.toLowerCase();
  const filamentFilter = filterFilament.value;
  const vendorFilter = filterVendor.value;
  const statusFilter = filterStatus.value;

  let filtered = coils.filter(coil => {
    // Поиск
    if (search && !coil.name.toLowerCase().includes(search)) {
      return false;
    }
    // Фильтр филамента
    if (filamentFilter && coil.filament_id != filamentFilter) {
      return false;
    }
    // Фильтр производителя (через филамент)
    if (vendorFilter) {
      const vendorId = coil.filament?.vendor_id || coil.vendor_id;
      if (vendorId != vendorFilter) return false;
    }
    // Фильтр статуса
    if (statusFilter === 'low' && coil.remains_status !== 'critical') {
      return false;
    }
    return true;
  });

  coilsTableBody.innerHTML = filtered.map(coil => {
    const color = coil.color_hex || '#888888';
    const filamentName = coil.filament ? `${coil.filament.name} (${coil.filament.material || '?'})` : (coil.material || '—');
    const vendorName = coil.filament?.vendor_name || coil.vendor?.name || '—';
    const remainsPercent = coil.remains_percent ?? 0;
    const remainsStatus = coil.remains_status || 'unknown';

    return `
      <tr class="${coil.archived ? 'archived' : ''}">
        <td><span class="color-dot" style="background: ${color}"></span></td>
        <td>${coil.name}</td>
        <td>${filamentName}</td>
        <td>${vendorName}</td>
        <td class="remains-cell">
          <div class="remains-bar">
            <div class="remains-bar-track">
              <div class="remains-bar-fill status-${remainsStatus}" style="width: ${remainsPercent}%"></div>
            </div>
            <span class="remains-text">${coil.remains ?? 0} г (${remainsPercent}%)</span>
          </div>
        </td>
        <td>${coil.location || '—'}</td>
        <td class="action-btns">
          <button class="action-btn edit" onclick="editCoil(${coil.id})">Изм.</button>
          <button class="action-btn history" onclick="showHistory(${coil.id})">История</button>
          <button class="action-btn adjust" onclick="showAdjust(${coil.id})">Остаток</button>
          ${coil.archived
            ? `<button class="action-btn unarchive" onclick="handleUnarchive(${coil.id})">Вернуть</button>`
            : `<button class="action-btn archive" onclick="handleArchive(${coil.id})">В архив</button>`
          }
          <button class="action-btn delete" onclick="handleDeleteCoil(${coil.id})">Удалить</button>
        </td>
      </tr>
    `;
  }).join('');
}

function updateCoilsStats(coils) {
  const active = coils.filter(c => !c.archived);
  statTotalCoils.textContent = active.length;
  statTotalWeight.textContent = Math.round(active.reduce((sum, c) => sum + (c.remains || 0), 0)) + ' г';
  statLowStock.textContent = active.filter(c => c.remains_status === 'critical' || c.remains_status === 'warning').length;
  statArchived.textContent = coils.filter(c => c.archived).length;
}

// =============== Рендеринг Филаментов ===============

function renderFilamentsTable(filaments) {
  const search = searchFilamentInput.value.toLowerCase();
  const vendorFilter = filterFilamentVendor.value;

  let filtered = filaments.filter(f => {
    if (search && !f.name.toLowerCase().includes(search) && !(f.material || '').toLowerCase().includes(search)) {
      return false;
    }
    if (vendorFilter && f.vendor_id != vendorFilter) {
      return false;
    }
    return true;
  });

  filamentsTableBody.innerHTML = filtered.map(f => {
    const color = f.color_hex || '#888888';
    return `
      <tr>
        <td><span class="color-dot" style="background: ${color}"></span></td>
        <td>${f.name}</td>
        <td>${f.material || '—'}</td>
        <td>${f.vendor_name || '—'}</td>
        <td>${f.diameter || 1.75} мм</td>
        <td>${f.weight || 1000} г</td>
        <td class="action-btns">
          <button class="action-btn edit" onclick="editFilament(${f.id})">Изм.</button>
          <button class="action-btn delete" onclick="handleDeleteFilament(${f.id})">Удалить</button>
        </td>
      </tr>
    `;
  }).join('');

  statTotalFilaments.textContent = filaments.length;
}

// =============== Рендеринг Производителей ===============

function renderVendorsTable(vendors) {
  const search = searchVendorInput.value.toLowerCase();

  let filtered = vendors.filter(v => {
    if (search && !v.name.toLowerCase().includes(search)) {
      return false;
    }
    return true;
  });

  vendorsTableBody.innerHTML = filtered.map(v => `
    <tr>
      <td>${v.name}</td>
      <td>${v.empty_spool_weight ? v.empty_spool_weight + ' г' : '—'}</td>
      <td>${v.comment || '—'}</td>
      <td class="action-btns">
        <button class="action-btn edit" onclick="editVendor(${v.id})">Изм.</button>
        <button class="action-btn delete" onclick="handleDeleteVendor(${v.id})">Удалить</button>
      </td>
    </tr>
  `).join('');

  statTotalVendors.textContent = vendors.length;
}

// =============== Загрузка данных ===============

async function loadAllData() {
  try {
    [coilsData, filamentsData, vendorsData] = await Promise.all([
      fetchCoils(),
      fetchFilaments(),
      fetchVendors()
    ]);

    renderCoilsTable(coilsData);
    updateCoilsStats(coilsData);
    renderFilamentsTable(filamentsData);
    renderVendorsTable(vendorsData);
    populateFilters();
  } catch (err) {
    console.error('Ошибка загрузки данных:', err);
    showToast('Ошибка загрузки данных', 'error');
  }
}

function populateFilters() {
  // Фильтр филаментов (для катушек)
  filterFilament.innerHTML = '<option value="">Все филаменты</option>' +
    filamentsData.map(f => `<option value="${f.id}">${f.name} (${f.material || '?'})</option>`).join('');

  // Фильтр производителей (для катушек)
  filterVendor.innerHTML = '<option value="">Все производители</option>' +
    vendorsData.map(v => `<option value="${v.id}">${v.name}</option>`).join('');

  // Фильтр производителей (для филаментов)
  filterFilamentVendor.innerHTML = '<option value="">Все производители</option>' +
    vendorsData.map(v => `<option value="${v.id}">${v.name}</option>`).join('');

  // Селекты в формах
  populateFormSelects();
}

function populateFormSelects() {
  // Селект филаментов в форме катушки
  const filamentSelect = coilForm.querySelector('[name="filament_id"]');
  filamentSelect.innerHTML = '<option value="">Выберите...</option>' +
    filamentsData.map(f => {
      const vendorName = f.vendor_name ? ` (${f.vendor_name})` : '';
      return `<option value="${f.id}">${f.name} - ${f.material || '?'}${vendorName}</option>`;
    }).join('');

  // Селект производителей в форме филамента
  const vendorSelect = filamentForm.querySelector('[name="vendor_id"]');
  vendorSelect.innerHTML = '<option value="">Не указан</option>' +
    vendorsData.map(v => `<option value="${v.id}">${v.name}</option>`).join('');
}

// =============== Модальные окна - Катушки ===============

// Элементы для расчёта весов
const totalWeightInput = document.getElementById('totalWeight');
const initialWeightInput = document.getElementById('initialWeight');
const spoolWeightInput = document.getElementById('spoolWeight');
const calculatedWeightEl = document.getElementById('calculatedWeight');
const remainsField = document.getElementById('remainsField');

// Режим ввода: 'total' (из общего веса) или 'direct' (прямой ввод пластика)
let weightInputMode = null;
let isCalculating = false; // Флаг для предотвращения рекурсии

// Расчёт веса пластика
function calculateWeight() {
  if (isCalculating) return 0;
  isCalculating = true;

  const totalWeight = parseFloat(totalWeightInput.value) || 0;
  const spoolWeight = parseFloat(spoolWeightInput.value) || 0;
  const directWeight = parseFloat(initialWeightInput.value) || 0;

  let filamentWeight = 0;

  if (weightInputMode === 'total' && totalWeight > 0) {
    // Режим: рассчитываем из общего веса
    filamentWeight = Math.max(0, totalWeight - spoolWeight);
    initialWeightInput.value = filamentWeight > 0 ? filamentWeight : '';
  } else if (weightInputMode === 'direct' && directWeight > 0) {
    // Режим: прямой ввод веса пластика
    filamentWeight = directWeight;
    // Рассчитываем общий вес если есть вес катушки
    if (spoolWeight > 0) {
      totalWeightInput.value = directWeight + spoolWeight;
    }
  } else if (totalWeight > 0) {
    // Fallback: есть общий вес
    filamentWeight = Math.max(0, totalWeight - spoolWeight);
    initialWeightInput.value = filamentWeight > 0 ? filamentWeight : '';
  } else if (directWeight > 0) {
    // Fallback: есть прямой вес пластика
    filamentWeight = directWeight;
    if (spoolWeight > 0) {
      totalWeightInput.value = directWeight + spoolWeight;
    }
  }

  // Обновляем отображение "Итого пластика"
  if (filamentWeight > 0) {
    calculatedWeightEl.textContent = filamentWeight + ' г';
    calculatedWeightEl.classList.add('calculated');
  } else {
    calculatedWeightEl.textContent = '—';
    calculatedWeightEl.classList.remove('calculated');
  }

  // Устанавливаем скрытое поле остатка (для новой катушки = начальному весу)
  remainsField.value = filamentWeight || '';

  isCalculating = false;
  return filamentWeight;
}

// Автозаполнение веса катушки при выборе филамента
// Приоритет: filament.empty_spool_weight → vendor.empty_spool_weight → 200г
function updateSpoolWeightFromFilament() {
  const filamentId = parseInt(coilForm.querySelector('[name="filament_id"]').value);
  if (!filamentId) return;

  // Если вес катушки уже заполнен - не перезаписываем
  if (spoolWeightInput.value) return;

  const filament = filamentsData.find(f => f.id === filamentId);
  let spoolWeight = 200; // Значение по умолчанию

  if (filament) {
    // Сначала пробуем вес пустой катушки из филамента
    if (filament.empty_spool_weight) {
      spoolWeight = filament.empty_spool_weight;
    } else if (filament.vendor_id) {
      // Если нет - берём из производителя
      const vendor = vendorsData.find(v => v.id === filament.vendor_id);
      if (vendor && vendor.empty_spool_weight) {
        spoolWeight = vendor.empty_spool_weight;
      }
    }
  }

  spoolWeightInput.value = spoolWeight;
  calculateWeight();
}

// Сброс режима ввода (при открытии формы)
function resetWeightInputMode() {
  weightInputMode = null;
  isCalculating = false;
}

// Обработчики событий для расчёта весов
totalWeightInput.addEventListener('input', () => {
  if (isCalculating) return;
  // Устанавливаем режим "из общего веса"
  weightInputMode = 'total';
  // Очищаем прямой ввод пластика (будет рассчитан)
  initialWeightInput.value = '';
  calculateWeight();
});

initialWeightInput.addEventListener('input', () => {
  if (isCalculating) return;
  // Устанавливаем режим "прямой ввод пластика"
  weightInputMode = 'direct';
  // Очищаем общий вес (будет рассчитан если есть вес катушки)
  totalWeightInput.value = '';
  calculateWeight();
});

spoolWeightInput.addEventListener('input', () => {
  if (isCalculating) return;
  calculateWeight();
});

coilForm.querySelector('[name="filament_id"]').addEventListener('change', updateSpoolWeightFromFilament);

document.getElementById('openCoilModal').addEventListener('click', () => {
  coilForm.reset();
  document.getElementById('coilId').value = '';
  document.getElementById('coilModalTitle').textContent = 'Новая катушка';
  calculatedWeightEl.textContent = '—';
  calculatedWeightEl.classList.remove('calculated');
  resetWeightInputMode(); // Сброс режима ввода весов
  coilModal.classList.remove('hidden');
});

document.getElementById('closeCoilModal').addEventListener('click', () => coilModal.classList.add('hidden'));
document.getElementById('cancelCoil').addEventListener('click', () => coilModal.classList.add('hidden'));

coilForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const formData = new FormData(coilForm);
  const coilId = formData.get('coil_id');

  // Рассчитываем итоговый вес пластика
  const filamentWeight = calculateWeight();
  if (!filamentWeight || filamentWeight <= 0) {
    showToast('Укажите вес пластика или общий вес катушки', 'error');
    return;
  }

  // Определяем: это новая катушка или редактирование?
  const existingCoil = coilId ? coilsData.find(c => c.id === parseInt(coilId)) : null;

  // Для редактирования: если вес пластика изменился - обновляем остаток
  // (пользователь взвесил катушку и скорректировал вес)
  let newRemains = filamentWeight;
  if (existingCoil) {
    const oldInitialWeight = existingCoil.initial_weight || 0;
    if (Math.abs(filamentWeight - oldInitialWeight) < 0.01) {
      // Вес не изменился - сохраняем текущий остаток
      newRemains = existingCoil.remains;
    }
    // Иначе: вес изменился - новый остаток = новый вес пластика
  }

  const data = {
    name: formData.get('name'),
    filament_id: parseInt(formData.get('filament_id')),
    remains: newRemains,
    initial_weight: filamentWeight,
    spool_weight: formData.get('spool_weight') ? parseFloat(formData.get('spool_weight')) : null,
    price: formData.get('price') ? parseFloat(formData.get('price')) : null,
    location: formData.get('location') || null,
    lot_nr: formData.get('lot_nr') || null,
    comment: formData.get('comment') || null,
  };

  try {
    let result;
    if (coilId) {
      result = await updateCoil(coilId, data);
    } else {
      result = await createCoil(data);
    }

    if (result.success) {
      showToast(coilId ? 'Катушка обновлена' : 'Катушка создана', 'success');
      coilModal.classList.add('hidden');
      await loadAllData();
    } else {
      showToast(result.message || 'Ошибка', 'error');
    }
  } catch (err) {
    showToast('Ошибка сохранения', 'error');
  }
});

window.editCoil = function(id) {
  const coil = coilsData.find(c => c.id === id);
  if (!coil) return;

  document.getElementById('coilId').value = coil.id;
  document.getElementById('coilModalTitle').textContent = 'Редактирование катушки';

  coilForm.querySelector('[name="name"]').value = coil.name || '';
  coilForm.querySelector('[name="filament_id"]').value = coil.filament_id || '';

  // Определяем вес пустой катушки (приоритет: катушка → филамент → вендор → 200г)
  let spoolWeight = coil.spool_weight;
  if (!spoolWeight && coil.filament_id) {
    const filament = filamentsData.find(f => f.id === coil.filament_id);
    if (filament) {
      // Сначала пробуем вес из филамента
      if (filament.empty_spool_weight) {
        spoolWeight = filament.empty_spool_weight;
      } else if (filament.vendor_id) {
        // Затем из вендора
        const vendor = vendorsData.find(v => v.id === filament.vendor_id);
        if (vendor && vendor.empty_spool_weight) {
          spoolWeight = vendor.empty_spool_weight;
        }
      }
    }
  }
  if (!spoolWeight) {
    spoolWeight = 200; // Значение по умолчанию
  }

  // Сброс и установка режима для редактирования
  resetWeightInputMode();
  weightInputMode = 'total'; // Режим "общий вес" для удобного пересчёта

  // Поля весов - показываем все значения
  const initialWeight = coil.initial_weight || 0;
  spoolWeightInput.value = spoolWeight;
  initialWeightInput.value = initialWeight || '';
  // Рассчитываем и показываем общий вес
  totalWeightInput.value = initialWeight > 0 ? (initialWeight + spoolWeight) : '';

  coilForm.querySelector('[name="price"]').value = coil.price || '';
  coilForm.querySelector('[name="location"]').value = coil.location || '';
  coilForm.querySelector('[name="lot_nr"]').value = coil.lot_nr || '';
  coilForm.querySelector('[name="comment"]').value = coil.comment || '';

  // Обновляем отображение рассчитанного веса
  calculateWeight();

  coilModal.classList.remove('hidden');
};

window.handleDeleteCoil = async function(id) {
  if (!confirm('Удалить катушку?')) return;
  const result = await deleteCoil(id);
  if (result.success) {
    showToast('Катушка удалена', 'success');
    await loadAllData();
  } else {
    showToast(result.message || 'Ошибка удаления', 'error');
  }
};

window.handleArchive = async function(id) {
  const result = await archiveCoil(id);
  if (result.success) {
    showToast('Катушка архивирована', 'success');
    await loadAllData();
  }
};

window.handleUnarchive = async function(id) {
  const result = await unarchiveCoil(id);
  if (result.success) {
    showToast('Катушка восстановлена', 'success');
    await loadAllData();
  }
};

// =============== Модальные окна - Филаменты ===============

document.getElementById('openFilamentModal').addEventListener('click', () => {
  filamentForm.reset();
  document.getElementById('filamentId').value = '';
  document.getElementById('filamentModalTitle').textContent = 'Новый филамент';
  syncColorInputs('filamentColorPicker', 'filamentColorHexText');
  filamentModal.classList.remove('hidden');
});

document.getElementById('closeFilamentModal').addEventListener('click', () => filamentModal.classList.add('hidden'));
document.getElementById('cancelFilament').addEventListener('click', () => filamentModal.classList.add('hidden'));

filamentForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const formData = new FormData(filamentForm);
  const filamentId = formData.get('filament_id');

  const data = {
    name: formData.get('name'),
    vendor_id: formData.get('vendor_id') ? parseInt(formData.get('vendor_id')) : null,
    material: formData.get('material'),
    color_hex: formData.get('color_hex_text') || formData.get('color_hex'),
    diameter: parseFloat(formData.get('diameter')) || 1.75,
    weight: formData.get('weight') ? parseInt(formData.get('weight')) : 1000,
    empty_spool_weight: formData.get('empty_spool_weight') ? parseInt(formData.get('empty_spool_weight')) : 200,
    density: formData.get('density') ? parseFloat(formData.get('density')) : null,
    description: formData.get('description') || null,
  };

  try {
    let result;
    if (filamentId) {
      result = await updateFilament(filamentId, data);
    } else {
      result = await createFilament(data);
    }

    if (result.success) {
      showToast(filamentId ? 'Филамент обновлён' : 'Филамент создан', 'success');
      filamentModal.classList.add('hidden');
      await loadAllData();
    } else {
      showToast(result.message || 'Ошибка', 'error');
    }
  } catch (err) {
    showToast('Ошибка сохранения', 'error');
  }
});

window.editFilament = function(id) {
  const filament = filamentsData.find(f => f.id === id);
  if (!filament) return;

  document.getElementById('filamentId').value = filament.id;
  document.getElementById('filamentModalTitle').textContent = 'Редактирование филамента';

  filamentForm.querySelector('[name="name"]').value = filament.name || '';
  filamentForm.querySelector('[name="vendor_id"]').value = filament.vendor_id || '';
  filamentForm.querySelector('[name="material"]').value = filament.material || '';
  filamentForm.querySelector('[name="color_hex"]').value = filament.color_hex || '#FFFFFF';
  filamentForm.querySelector('[name="color_hex_text"]').value = filament.color_hex || '';
  filamentForm.querySelector('[name="diameter"]').value = filament.diameter || '1.75';
  filamentForm.querySelector('[name="weight"]').value = filament.weight || 1000;
  filamentForm.querySelector('[name="empty_spool_weight"]').value = filament.empty_spool_weight || 200;
  filamentForm.querySelector('[name="density"]').value = filament.density || '';
  filamentForm.querySelector('[name="description"]').value = filament.description || '';

  filamentModal.classList.remove('hidden');
};

window.handleDeleteFilament = async function(id) {
  if (!confirm('Удалить филамент? Это также удалит связанные катушки!')) return;
  const result = await deleteFilament(id);
  if (result.success) {
    showToast('Филамент удалён', 'success');
    await loadAllData();
  } else {
    showToast(result.message || 'Ошибка удаления', 'error');
  }
};

// =============== Модальные окна - Производители ===============

document.getElementById('openVendorModal').addEventListener('click', () => {
  vendorForm.reset();
  document.getElementById('vendorId').value = '';
  document.getElementById('vendorModalTitle').textContent = 'Новый производитель';
  vendorModal.classList.remove('hidden');
});

document.getElementById('closeVendorModal').addEventListener('click', () => vendorModal.classList.add('hidden'));
document.getElementById('cancelVendor').addEventListener('click', () => vendorModal.classList.add('hidden'));

vendorForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const formData = new FormData(vendorForm);
  const vendorId = formData.get('vendor_id');

  // Валидация веса пустой катушки
  const emptySpoolWeight = formData.get('empty_spool_weight');
  if (!emptySpoolWeight || parseFloat(emptySpoolWeight) <= 0) {
    showToast('Укажите вес пустой катушки (больше 0)', 'error');
    return;
  }

  const data = {
    name: formData.get('name'),
    empty_spool_weight: parseFloat(emptySpoolWeight),
    comment: formData.get('comment') || null,
  };

  try {
    let result;
    if (vendorId) {
      result = await updateVendor(vendorId, data);
    } else {
      result = await createVendor(data);
    }

    if (result.success) {
      showToast(vendorId ? 'Производитель обновлён' : 'Производитель создан', 'success');
      vendorModal.classList.add('hidden');
      await loadAllData();
    } else {
      showToast(result.message || 'Ошибка', 'error');
    }
  } catch (err) {
    showToast('Ошибка сохранения', 'error');
  }
});

window.editVendor = function(id) {
  const vendor = vendorsData.find(v => v.id === id);
  if (!vendor) return;

  document.getElementById('vendorId').value = vendor.id;
  document.getElementById('vendorModalTitle').textContent = 'Редактирование производителя';

  vendorForm.querySelector('[name="name"]').value = vendor.name || '';
  vendorForm.querySelector('[name="empty_spool_weight"]').value = vendor.empty_spool_weight || '';
  vendorForm.querySelector('[name="comment"]').value = vendor.comment || '';

  vendorModal.classList.remove('hidden');
};

window.handleDeleteVendor = async function(id) {
  if (!confirm('Удалить производителя?')) return;
  const result = await deleteVendor(id);
  if (result.success) {
    showToast('Производитель удалён', 'success');
    await loadAllData();
  } else {
    showToast(result.message || 'Ошибка удаления', 'error');
  }
};

// =============== История и корректировка ===============

window.showHistory = async function(id) {
  const coil = coilsData.find(c => c.id === id);
  if (!coil) return;

  document.getElementById('historyCoilName').textContent = coil.name;
  document.getElementById('historyUsedWeight').textContent = coil.used_weight || 0;

  try {
    const history = await fetchCoilHistory(id);
    const tbody = document.getElementById('historyTableBody');
    tbody.innerHTML = history.map(h => `
      <tr>
        <td>${new Date(h.timestamp).toLocaleString('ru-RU')}</td>
        <td>${h.task_id ? `Задача #${h.task_id}` : '—'}</td>
        <td>${h.used_weight} г</td>
        <td>${h.notes || '—'}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Ошибка загрузки истории:', err);
  }

  historyModal.classList.remove('hidden');
};

document.getElementById('closeHistoryModal').addEventListener('click', () => historyModal.classList.add('hidden'));

window.showAdjust = function(id) {
  const coil = coilsData.find(c => c.id === id);
  if (!coil) return;

  document.getElementById('adjustCoilId').value = coil.id;
  document.getElementById('adjustCoilName').textContent = coil.name;
  document.getElementById('adjustCurrentRemains').textContent = coil.remains || 0;
  adjustForm.querySelector('[name="new_remains"]').value = coil.remains || 0;
  adjustForm.querySelector('[name="adjust_notes"]').value = '';

  adjustModal.classList.remove('hidden');
};

document.getElementById('closeAdjustModal').addEventListener('click', () => adjustModal.classList.add('hidden'));
document.getElementById('cancelAdjust').addEventListener('click', () => adjustModal.classList.add('hidden'));

adjustForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const formData = new FormData(adjustForm);
  const coilId = formData.get('adjust_coil_id');
  const newRemains = parseFloat(formData.get('new_remains'));
  const notes = formData.get('adjust_notes');

  const result = await adjustCoilRemains(coilId, newRemains, notes);
  if (result.success) {
    showToast('Остаток скорректирован', 'success');
    adjustModal.classList.add('hidden');
    await loadAllData();
  } else {
    showToast(result.message || 'Ошибка', 'error');
  }
});

// =============== Утилиты ===============

function syncColorInputs(pickerId, textId) {
  const picker = document.getElementById(pickerId);
  const text = document.getElementById(textId);

  picker.addEventListener('input', () => {
    text.value = picker.value.toUpperCase();
  });

  text.addEventListener('input', () => {
    if (/^#[0-9A-Fa-f]{6}$/.test(text.value)) {
      picker.value = text.value;
    }
  });

  text.value = picker.value.toUpperCase();
}

function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// Фильтры
filterFilament.addEventListener('change', () => renderCoilsTable(coilsData));
filterVendor.addEventListener('change', () => renderCoilsTable(coilsData));
filterStatus.addEventListener('change', async () => {
  coilsData = await fetchCoils();
  renderCoilsTable(coilsData);
  updateCoilsStats(coilsData);
});
searchInput.addEventListener('input', () => renderCoilsTable(coilsData));
searchFilamentInput.addEventListener('input', () => renderFilamentsTable(filamentsData));
filterFilamentVendor.addEventListener('change', () => renderFilamentsTable(filamentsData));
searchVendorInput.addEventListener('input', () => renderVendorsTable(vendorsData));

// Синхронизация цветов при загрузке (только для филамента, у катушки цвет берётся от филамента)
syncColorInputs('filamentColorPicker', 'filamentColorHexText');

// Закрытие модалок по клику на backdrop
[coilModal, filamentModal, vendorModal, historyModal, adjustModal].forEach(modal => {
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.add('hidden');
    });
  }
});

// Загрузка данных при старте
loadAllData();
