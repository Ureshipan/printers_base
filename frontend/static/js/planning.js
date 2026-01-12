let tasks = [];
let projects = [];
let printers = [];
let coils = [];
let currentTaskId = null;
let currentProjectId = null;
let pendingGcodeFile = null;  // Файл G-code для загрузки при создании задачи
let parsedEstimatedTime = null;  // Время печати из G-code (минуты) для авторасчёта даты окончания

const taskModal = document.getElementById('taskModal');
const openTaskModalBtn = document.getElementById('openTaskModal');
const closeTaskModalBtn = document.getElementById('closeTaskModal');
const cancelTaskChangesBtn = document.getElementById('cancelTaskChanges');
const taskForm = document.getElementById('taskForm');
const tasksTableBody = document.getElementById('tasksTableBody');
const projectsList = document.getElementById('projectsList');
const planningMessage = document.getElementById('planningMessage');
const filterProject = document.getElementById('filterProject');
const filterStatus = document.getElementById('filterStatus');
const modalTitle = document.getElementById('modalTitle');
const gcodeFileInput = document.getElementById('gcodeFileInput');
const projectModal = document.getElementById('projectModal');
const projectForm = document.getElementById('projectForm');
const openProjectModalBtn = document.getElementById('openProjectModal');
const closeProjectModalBtn = document.getElementById('closeProjectModal');
const cancelProjectChangesBtn = document.getElementById('cancelProjectChanges');
const projectModalTitle = document.getElementById('projectModalTitle');

// Элементы для загрузки G-code в модальном окне
const taskGcodeInput = document.getElementById('taskGcodeInput');
const gcodeFileName = document.getElementById('gcodeFileName');
const gcodeParseInfo = document.getElementById('gcodeParseInfo');
const gcodeUploadSection = taskGcodeInput?.closest('.gcode-upload-section');

const STATUS_LABELS = {
  pending: 'Ожидает',
  queued: 'В очереди',
  printing: 'Печатается',
  paused: 'Пауза',
  completed: 'Завершена',
  cancelled: 'Отменена'
};

document.addEventListener('DOMContentLoaded', async () => {
  initializeNavigation();
  registerEventListeners();
  await loadInitialData();
});

function initializeNavigation() {
  const sidebarButtons = document.querySelectorAll('.sidebar-btn');
  const currentPath = window.location.pathname;
  sidebarButtons.forEach(button => {
    const route = button.dataset.route;
    if (!route) { return; }
    if (route === currentPath) {
      button.classList.add('active');
    } else {
      button.classList.remove('active');
    }
    button.addEventListener('click', () => {
      if (window.location.pathname !== route) {
        window.location.href = route;
      }
    });
  });
}

function registerEventListeners() {
  openTaskModalBtn.addEventListener('click', () => openTaskModal());
  closeTaskModalBtn.addEventListener('click', closeTaskModal);
  cancelTaskChangesBtn.addEventListener('click', closeTaskModal);
  taskModal.addEventListener('click', (event) => {
    if (event.target === taskModal) {
      closeTaskModal();
    }
  });
  taskForm.addEventListener('submit', handleTaskSubmit);
  filterProject.addEventListener('change', renderTasks);
  filterStatus.addEventListener('change', renderTasks);
  gcodeFileInput.addEventListener('change', handleGcodeFileSelect);
  // Обработчик загрузки G-code в модальном окне создания задачи
  if (taskGcodeInput) {
    taskGcodeInput.addEventListener('change', handleTaskGcodeSelect);
  }
  // Авторасчёт даты окончания при изменении даты начала
  const timeStartInput = taskForm.elements['time_start'];
  if (timeStartInput) {
    timeStartInput.addEventListener('change', updateTimeEnd);
  }
  openProjectModalBtn.addEventListener('click', () => openProjectModal());
  closeProjectModalBtn.addEventListener('click', closeProjectModal);
  cancelProjectChangesBtn.addEventListener('click', closeProjectModal);
  projectModal.addEventListener('click', (event) => {
    if (event.target === projectModal) {
      closeProjectModal();
    }
  });
  projectForm.addEventListener('submit', handleProjectSubmit);
}

async function loadInitialData() {
  try {
    const [projectsData, printersData, coilsData] = await Promise.all([
      fetchJson('/api/projects'),
      fetchJson('/api/printers'),
      fetchJson('/api/coils')
    ]);

    projects = projectsData;
    printers = printersData;
    coils = coilsData;

    populateSelectOptions();
    populateProjectsList();
    populateProjectFilter();
    await loadTasks();
  } catch (error) {
    showMessage('Не удалось загрузить данные: ' + error.message, true);
  }
}

async function loadTasks() {
  try {
    const response = await fetchJson('/api/tasks');
    tasks = response;
    renderTasks();
    populateProjectsList();
  } catch (error) {
    showMessage('Не удалось загрузить задачи: ' + error.message, true);
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const message = await safeReadJsonMessage(response);
    throw new Error(message || `HTTP ${response.status}`);
  }
  return response.json();
}

async function safeReadJsonMessage(response) {
  try {
    const data = await response.json();
    return data.message || JSON.stringify(data);
  } catch (err) {
    return response.statusText;
  }
}

function populateSelectOptions() {
  const projectSelect = taskForm.elements['project_id'];
  const printerSelect = taskForm.elements['printer_id'];
  const coilSelect = taskForm.elements['coil_id'];

  projectSelect.innerHTML = '<option value=\"\">Выберите проект</option>';
  projects.forEach(project => {
    const option = document.createElement('option');
    option.value = project.id;
    option.textContent = project.name;
    projectSelect.appendChild(option);
  });

  printerSelect.innerHTML = '';
  printers.forEach(printer => {
    const option = document.createElement('option');
    option.value = printer.id;
    option.textContent = printer.name;
    printerSelect.appendChild(option);
  });

  coilSelect.innerHTML = '<option value="">Не выбрано</option>';
  coils.forEach(coil => {
    // Пропускаем архивные катушки
    if (coil.archived) return;

    const option = document.createElement('option');
    option.value = coil.id;
    // Показываем: название (материал) - остаток г / %
    const remainsText = coil.remains != null
      ? `${Math.round(coil.remains)}г`
      : '';
    const percentText = coil.remains_percent != null
      ? ` (${coil.remains_percent}%)`
      : '';
    const colorDot = coil.color_hex ? `● ` : '';

    option.textContent = coil.material
      ? `${colorDot}${coil.name} (${coil.material}) - ${remainsText}${percentText}`
      : `${colorDot}${coil.name} - ${remainsText}${percentText}`;

    // Цветовой код для статуса
    if (coil.color_hex) {
      option.style.color = coil.color_hex;
    }

    // Сохраняем данные для проверки
    option.dataset.remains = coil.remains || 0;
    option.dataset.status = coil.remains_status || 'unknown';

    coilSelect.appendChild(option);
  });

  // Добавляем обработчик для проверки достаточности материала
  coilSelect.addEventListener('change', checkMaterialSufficiency);
}

// Проверка достаточности материала при выборе катушки
function checkMaterialSufficiency() {
  const coilSelect = taskForm.elements['coil_id'];
  const selectedOption = coilSelect.selectedOptions[0];
  const estimatedFilament = parseFloat(taskForm.elements['material_amount']?.value) || 0;

  // Удаляем старое предупреждение
  const oldWarning = document.getElementById('coilWarning');
  if (oldWarning) oldWarning.remove();

  if (!selectedOption || !selectedOption.value) return;

  const remains = parseFloat(selectedOption.dataset.remains) || 0;

  if (estimatedFilament > 0 && remains < estimatedFilament) {
    const warning = document.createElement('div');
    warning.id = 'coilWarning';
    warning.className = 'coil-warning';
    warning.innerHTML = `⚠️ Недостаточно материала! Требуется ${Math.round(estimatedFilament)}г, на катушке ${Math.round(remains)}г`;
    coilSelect.parentNode.appendChild(warning);
  }
}

function populateProjectsList() {
  projectsList.innerHTML = '';
  projects.forEach(project => {
    const item = document.createElement('li');
    item.className = 'project-item';
    item.style.borderLeftColor = project.color || '#8a8dff';
    item.innerHTML = `
      <h3>
        <span class="project-color-dot" style="background:${project.color || '#8a8dff'}"></span>
        ${project.name}
      </h3>
      ${project.desc ? `<p>${project.desc}</p>` : ''}
      <span class="project-count">${countTasksForProject(project.id)} задач</span>
      <div class="project-actions">
        <button class="action-btn secondary" data-project-edit="${project.id}">Редактировать</button>
        <button class="action-btn destructive" data-project-delete="${project.id}">Удалить</button>
      </div>
    `;
    item.addEventListener('click', handleProjectAction);
    projectsList.appendChild(item);
  });
}

function countTasksForProject(projectId) {
  return tasks.filter(task => task.project && task.project.id === projectId).length;
}

function populateProjectFilter() {
  const previousValue = filterProject.value;
  filterProject.innerHTML = '<option value="">Все проекты</option>';
  projects.forEach(project => {
    const option = document.createElement('option');
    option.value = project.id;
    option.textContent = project.name;
    filterProject.appendChild(option);
  });
  if (previousValue && projects.some(project => String(project.id) === previousValue)) {
    filterProject.value = previousValue;
  } else {
    filterProject.value = '';
  }
}

function renderTasks() {
  tasksTableBody.innerHTML = '';
  const projectFilter = filterProject.value;
  const statusFilter = filterStatus.value;

  const filteredTasks = tasks.filter(task => {
    const matchProject = projectFilter ? String(task.project?.id) === projectFilter : true;
    const matchStatus = statusFilter ? task.status === statusFilter : true;
    return matchProject && matchStatus;
  });

  if (filteredTasks.length === 0) {
    const emptyRow = document.createElement('tr');
    emptyRow.innerHTML = `
      <td colspan="7" style="text-align:center; padding: 32px; color: #8f94d1;">
        Задачи не найдены. Создайте новую задачу, чтобы начать планирование.
      </td>`;
    tasksTableBody.appendChild(emptyRow);
    return;
  }

  filteredTasks.forEach(task => {
    const row = document.createElement('tr');
    row.style.borderLeft = `4px solid ${task.project?.color || 'transparent'}`;
    row.innerHTML = `
      <td class="task-name">${task.name || 'Без названия'}</td>
      <td>
        <span class="task-project">
          <span class="project-color-dot" style="background:${task.project?.color || '#8a8dff'}"></span>
          ${task.project?.name || '—'}
        </span>
      </td>
      <td>${task.printer?.name || '—'}</td>
      <td>
        ${renderStatusChip(task)}
      </td>
      <td>
        ${formatMaterialAndTime(task)}
      </td>
      <td>
        ${renderGcodeInfo(task)}
      </td>
      <td>
        <div class="gcode-actions">
          ${renderPrintActions(task)}
          <button class="action-btn primary" data-action="edit" data-id="${task.id}">Изм.</button>
          <button class="action-btn secondary" data-action="upload" data-id="${task.id}">G-code</button>
          <button class="action-btn destructive" data-action="delete" data-id="${task.id}">Удалить</button>
        </div>
      </td>
    `;
    row.addEventListener('click', handleRowAction);
    tasksTableBody.appendChild(row);
  });
}

function renderStatusChip(task) {
  const statusKey = task.status || 'pending';
  const label = STATUS_LABELS[statusKey] || statusKey;
  const progressPart = typeof task.progress === 'number' ? ` · ${task.progress}%` : '';
  return `<span class="status-chip status-${statusKey}">${label}${progressPart}</span>`;
}

function formatMaterialAndTime(task) {
  const material = task.estimated_filament ?? task.material_amount;
  const time = task.estimated_time_minutes;
  if (!material && !time) {
    return '<span style="color:#7378b8">—</span>';
  }
  const materialText = material ? `${Number(material).toFixed(1)} г` : '—';
  const timeText = time ? `${Number(time).toFixed(0)} мин` : '—';
  return `${materialText} · ${timeText}`;
}

function renderGcodeInfo(task) {
  if (!task.gcode?.has_file) {
    return '<span style="color:#9094d0">Файл не загружен</span>';
  }
  const name = task.gcode.original_name || task.gcode.download_url.split('/').pop();
  const gcode = task.gcode;

  // Собираем метаданные для отображения
  const metaItems = [];
  if (gcode.layer_count) {
    metaItems.push(`${gcode.layer_count} слоёв`);
  }
  if (gcode.layer_height) {
    metaItems.push(`${gcode.layer_height} мм`);
  }
  if (gcode.nozzle_temp) {
    metaItems.push(`🔥 ${gcode.nozzle_temp}°`);
  }
  if (gcode.bed_temp) {
    metaItems.push(`🛏️ ${gcode.bed_temp}°`);
  }

  const metaLine = metaItems.length > 0
    ? `<div class="gcode-meta">${metaItems.join(' · ')}</div>`
    : '';

  const slicerLine = gcode.slicer
    ? `<div class="gcode-slicer">${gcode.slicer}</div>`
    : '';

  return `
    <div class="gcode-info">
      <div class="gcode-file-name">${name}</div>
      ${metaLine}
      ${slicerLine}
      <div class="gcode-links">
        <a href="${task.gcode.download_url}" class="action-btn secondary" data-download>Скачать</a>
        <button class="action-btn destructive" data-remove-gcode data-id="${task.id}">Удалить</button>
      </div>
    </div>
  `;
}

function renderPrintActions(task) {
  const status = task.status || 'pending';
  const hasGcode = task.gcode?.has_file;
  const hasPrinter = !!task.printer?.id;

  // Проверяем, является ли принтер оффлайн (виртуальным)
  const printer = printers.find(p => p.id === task.printer?.id);
  const isOfflinePrinter = printer?.is_virtual || false;

  // Для оффлайн-принтеров - специальные кнопки ручного управления
  if (isOfflinePrinter && hasPrinter) {
    if (status === 'pending' || status === 'queued') {
      return `<button class="action-btn print-start offline-action" data-offline-action="start" data-id="${task.id}" title="Начать (ручной трекинг)">▶ Начать</button>`;
    }
    if (status === 'printing') {
      return `
        <button class="action-btn offline-progress" data-offline-action="progress" data-id="${task.id}" title="Обновить прогресс">📊</button>
        <button class="action-btn print-complete" data-offline-action="complete" data-id="${task.id}" title="Завершить">✓</button>
        <button class="action-btn print-cancel" data-offline-action="cancel" data-id="${task.id}" title="Отменить">✕</button>
      `;
    }
    if (status === 'paused') {
      return `
        <button class="action-btn print-resume" data-offline-action="resume" data-id="${task.id}" title="Продолжить">▶</button>
        <button class="action-btn print-cancel" data-offline-action="cancel" data-id="${task.id}" title="Отменить">✕</button>
      `;
    }
    return '';
  }

  // Кнопка запуска - только для pending/queued с G-code и принтером
  if ((status === 'pending' || status === 'queued') && hasGcode && hasPrinter) {
    return `<button class="action-btn print-start" data-print-action="start" data-id="${task.id}" title="Запустить печать">▶</button>`;
  }

  // Кнопки для печатающейся задачи
  if (status === 'printing') {
    return `
      <button class="action-btn print-pause" data-print-action="pause" data-id="${task.id}" title="Пауза">⏸</button>
      <button class="action-btn print-cancel" data-print-action="cancel" data-id="${task.id}" title="Отмена">✕</button>
    `;
  }

  // Кнопки для задачи на паузе
  if (status === 'paused') {
    return `
      <button class="action-btn print-resume" data-print-action="resume" data-id="${task.id}" title="Возобновить">▶</button>
      <button class="action-btn print-cancel" data-print-action="cancel" data-id="${task.id}" title="Отмена">✕</button>
    `;
  }

  return '';
}

function handleRowAction(event) {
  const actionButton = event.target.closest('[data-action], [data-remove-gcode], [data-download], [data-print-action], [data-offline-action]');
  if (!actionButton) {
    return;
  }
  event.stopPropagation();

  if (actionButton.dataset.download !== undefined) {
    // let the link proceed naturally
    return;
  }

  const taskId = parseInt(actionButton.dataset.id, 10);

  // Обработка действий печати
  const printAction = actionButton.dataset.printAction;
  if (printAction) {
    handlePrintAction(printAction, taskId);
    return;
  }

  // Обработка оффлайн-действий
  const offlineAction = actionButton.dataset.offlineAction;
  if (offlineAction) {
    handleOfflineAction(offlineAction, taskId);
    return;
  }

  if (actionButton.dataset.removeGcode !== undefined) {
    confirmAndRemoveGcode(taskId);
    return;
  }

  const action = actionButton.dataset.action;
  if (action === 'edit') {
    openTaskModal(taskId);
  } else if (action === 'delete') {
    confirmAndDeleteTask(taskId);
  } else if (action === 'upload') {
    triggerGcodeUpload(taskId);
  }
}

function openTaskModal(taskId = null) {
  currentTaskId = taskId;
  taskModal.classList.remove('hidden');
  taskForm.reset();
  populateSelectOptions();
  resetGcodeUploadUI();  // Сброс состояния загрузки G-code
  parsedEstimatedTime = null;  // Сброс времени из gcode

  // Управление видимостью полей edit-only (Статус, Прогресс)
  const editOnlyFields = taskForm.querySelectorAll('.edit-only');

  if (taskId) {
    modalTitle.textContent = 'Редактирование задачи';
    // Показываем поля edit-only при редактировании
    editOnlyFields.forEach(el => el.classList.remove('hidden'));

    const task = tasks.find(item => item.id === taskId);
    if (task) {
      taskForm.elements['name'].value = task.name || '';
      taskForm.elements['project_id'].value = task.project?.id || '';
      taskForm.elements['printer_id'].value = task.printer?.id || '';
      taskForm.elements['coil_id'].value = task.coil?.id || '';
      taskForm.elements['status'].value = task.status || 'pending';
      taskForm.elements['progress'].value = task.progress ?? 0;
      taskForm.elements['material_amount'].value = task.material_amount ?? '';
      taskForm.elements['time_start'].value = toInputDateTime(task.time_start);
      taskForm.elements['time_end'].value = toInputDateTime(task.time_end);
      taskForm.elements['notes'].value = task.notes || '';

      // Сохраняем время печати из gcode для авторасчёта
      if (task.estimated_time_minutes) {
        parsedEstimatedTime = task.estimated_time_minutes;
      }

      // Показываем информацию о загруженном G-code файле
      if (task.gcode?.has_file && gcodeFileName) {
        gcodeFileName.textContent = task.gcode.original_name || 'Файл загружен';
        gcodeUploadSection?.classList.add('has-file');
      }
    }
  } else {
    modalTitle.textContent = 'Новая задача';
    // Скрываем поля edit-only при создании новой задачи
    editOnlyFields.forEach(el => el.classList.add('hidden'));
    taskForm.elements['progress'].value = 0;
  }
}

function closeTaskModal() {
  taskModal.classList.add('hidden');
  currentTaskId = null;
}

function toInputDateTime(value) {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

async function handleTaskSubmit(event) {
  event.preventDefault();
  const formData = new FormData(taskForm);

  const payload = {
    name: formData.get('name')?.trim() || null,
    project_id: parseInt(formData.get('project_id'), 10),
    printer_id: parseInt(formData.get('printer_id'), 10),
    status: formData.get('status'),
    progress: formData.get('progress') ? Number(formData.get('progress')) : 0,
    material_amount: formData.get('material_amount') ? Number(formData.get('material_amount')) : null,
    time_start: formData.get('time_start') || null,
    time_end: formData.get('time_end') || null,
    notes: formData.get('notes')?.trim() || null
  };

  const coilId = formData.get('coil_id');
  if (coilId) {
    payload.coil_id = parseInt(coilId, 10);
  }

  if (!payload.project_id || Number.isNaN(payload.project_id)) {
    showMessage('Выберите проект для задачи', true);
    return;
  }
  if (!payload.printer_id || Number.isNaN(payload.printer_id)) {
    showMessage('Выберите принтер для задачи', true);
    return;
  }

  try {
    let taskId = currentTaskId;

    if (currentTaskId) {
      await fetchJson(`/api/tasks/${currentTaskId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      showMessage('Задача обновлена');
    } else {
      // Создаём задачу и получаем её ID
      const response = await fetchJson('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      taskId = response.task?.id;
      showMessage('Задача создана');
    }

    // Загружаем G-code файл, если он был выбран при создании
    if (pendingGcodeFile && taskId) {
      const gcodeFormData = new FormData();
      gcodeFormData.append('file', pendingGcodeFile);
      try {
        await fetchJson(`/api/tasks/${taskId}/gcode`, {
          method: 'POST',
          body: gcodeFormData
        });
        showMessage('G-code загружен');
      } catch (gcodeError) {
        showMessage('Задача создана, но G-code не загружен: ' + gcodeError.message, true);
      }
    }

    closeTaskModal();
    await loadTasks();
    populateProjectsList();
  } catch (error) {
    showMessage(error.message, true);
  }
}

function showMessage(text, isError = false) {
  const container = document.getElementById('toastContainer');
  if (!container) {
    console.warn(text);
    return;
  }
  const toast = document.createElement('div');
  toast.className = `toast${isError ? ' toast-error' : ''}`;
  toast.textContent = text;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 3200);
}

function triggerGcodeUpload(taskId) {
  gcodeFileInput.dataset.taskId = String(taskId);
  gcodeFileInput.value = '';
  gcodeFileInput.click();
}

async function handleGcodeFileSelect(event) {
  const file = event.target.files?.[0];
  const taskId = parseInt(event.target.dataset.taskId, 10);
  if (!taskId || !file) {
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    await fetchJson(`/api/tasks/${taskId}/gcode`, {
      method: 'POST',
      body: formData
    });
    showMessage('G-code загружен');
    await loadTasks();
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    delete gcodeFileInput.dataset.taskId;
    gcodeFileInput.value = '';
  }
}

/**
 * Обработчик выбора G-code файла в модальном окне создания задачи.
 * Парсит файл и автоматически заполняет поля формы.
 */
async function handleTaskGcodeSelect(event) {
  const file = event.target.files?.[0];
  if (!file) {
    resetGcodeUploadUI();
    return;
  }

  pendingGcodeFile = file;

  // Показываем имя файла
  if (gcodeFileName) {
    gcodeFileName.textContent = file.name;
  }
  if (gcodeUploadSection) {
    gcodeUploadSection.classList.add('has-file');
  }

  // Показываем индикатор загрузки
  if (gcodeParseInfo) {
    gcodeParseInfo.classList.remove('hidden');
    gcodeParseInfo.classList.add('loading');
    gcodeParseInfo.innerHTML = '⏳ Анализ файла...';
  }

  // Парсим файл на сервере
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch('/api/gcode/parse', {
      method: 'POST',
      body: formData
    });
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.message || 'Ошибка парсинга');
    }

    // Автозаполнение полей формы
    fillFormFromGcodeData(data);

    // Показываем информацию о файле
    renderGcodeParseInfo(data);

  } catch (error) {
    if (gcodeParseInfo) {
      gcodeParseInfo.classList.remove('loading');
      gcodeParseInfo.innerHTML = `<span style="color:#ff8aa8">⚠️ ${error.message}</span>`;
    }
    showMessage('Не удалось распарсить G-code: ' + error.message, true);
  }
}

/**
 * Заполняет поля формы данными из распарсенного G-code.
 */
function fillFormFromGcodeData(data) {
  // Название задачи (только если поле пустое)
  const nameInput = taskForm.elements['name'];
  if (nameInput && !nameInput.value && data.suggested_name) {
    nameInput.value = data.suggested_name;
  }

  // Расход материала
  const materialInput = taskForm.elements['material_amount'];
  if (materialInput && data.estimated_filament) {
    materialInput.value = data.estimated_filament;
  }

  // Сохраняем время печати для авторасчёта даты окончания
  if (data.estimated_time_minutes) {
    parsedEstimatedTime = data.estimated_time_minutes;
    // Пересчитываем дату окончания если указана дата начала
    updateTimeEnd();
  }
}

/**
 * Автоматически рассчитывает дату окончания на основе даты начала и времени печати из G-code.
 */
function updateTimeEnd() {
  const timeStartInput = taskForm.elements['time_start'];
  const timeEndInput = taskForm.elements['time_end'];

  if (!timeStartInput || !timeEndInput || !parsedEstimatedTime) {
    return;
  }

  const startValue = timeStartInput.value;
  if (!startValue) {
    return;
  }

  // Парсим дату начала и прибавляем время печати
  const startDate = new Date(startValue);
  if (isNaN(startDate.getTime())) {
    return;
  }

  // Прибавляем время печати (в минутах)
  const endDate = new Date(startDate.getTime() + parsedEstimatedTime * 60 * 1000);

  // Форматируем для datetime-local input (YYYY-MM-DDTHH:MM)
  const pad = n => n.toString().padStart(2, '0');
  const endFormatted = `${endDate.getFullYear()}-${pad(endDate.getMonth() + 1)}-${pad(endDate.getDate())}T${pad(endDate.getHours())}:${pad(endDate.getMinutes())}`;

  timeEndInput.value = endFormatted;
}

/**
 * Отображает информацию о распарсенном G-code файле.
 */
function renderGcodeParseInfo(data) {
  if (!gcodeParseInfo) return;

  gcodeParseInfo.classList.remove('loading', 'hidden');

  const rows = [];

  if (data.estimated_filament) {
    rows.push(`<div class="parse-row"><span class="parse-label">Филамент:</span><span class="parse-value">${data.estimated_filament.toFixed(1)} г</span></div>`);
  }
  if (data.estimated_time_minutes) {
    const hours = Math.floor(data.estimated_time_minutes / 60);
    const mins = Math.round(data.estimated_time_minutes % 60);
    const timeStr = hours > 0 ? `${hours}ч ${mins}м` : `${mins} мин`;
    rows.push(`<div class="parse-row"><span class="parse-label">Время печати:</span><span class="parse-value">${timeStr}</span></div>`);
  }
  if (data.layer_count) {
    rows.push(`<div class="parse-row"><span class="parse-label">Слоёв:</span><span class="parse-value">${data.layer_count}</span></div>`);
  }
  if (data.layer_height) {
    rows.push(`<div class="parse-row"><span class="parse-label">Высота слоя:</span><span class="parse-value">${data.layer_height} мм</span></div>`);
  }
  if (data.nozzle_temp) {
    rows.push(`<div class="parse-row"><span class="parse-label">Температура сопла:</span><span class="parse-value">${data.nozzle_temp}°C</span></div>`);
  }
  if (data.bed_temp) {
    rows.push(`<div class="parse-row"><span class="parse-label">Температура стола:</span><span class="parse-value">${data.bed_temp}°C</span></div>`);
  }
  if (data.slicer) {
    rows.push(`<div class="parse-row"><span class="parse-label">Слайсер:</span><span class="parse-value">${data.slicer}</span></div>`);
  }

  if (rows.length > 0) {
    gcodeParseInfo.innerHTML = rows.join('');
  } else {
    gcodeParseInfo.innerHTML = '<span style="color:#7378b8">Метаданные не найдены</span>';
  }
}

/**
 * Сбрасывает UI загрузки G-code.
 */
function resetGcodeUploadUI() {
  pendingGcodeFile = null;
  if (taskGcodeInput) {
    taskGcodeInput.value = '';
  }
  if (gcodeFileName) {
    gcodeFileName.textContent = '';
  }
  if (gcodeUploadSection) {
    gcodeUploadSection.classList.remove('has-file');
  }
  if (gcodeParseInfo) {
    gcodeParseInfo.classList.add('hidden');
    gcodeParseInfo.innerHTML = '';
  }
}

async function confirmAndDeleteTask(taskId) {
  const confirmed = window.confirm('Удалить задачу?');
  if (!confirmed) { return; }
  try {
    await fetchJson(`/api/tasks/${taskId}`, { method: 'DELETE' });
    showMessage('Задача удалена');
    await loadTasks();
    populateProjectsList();
  } catch (error) {
    showMessage(error.message, true);
  }
}

async function confirmAndRemoveGcode(taskId) {
  const confirmed = window.confirm('Удалить G-code файл?');
  if (!confirmed) { return; }
  try {
    await fetchJson(`/api/tasks/${taskId}/gcode`, { method: 'DELETE' });
    showMessage('G-code удален');
    await loadTasks();
  } catch (error) {
    showMessage(error.message, true);
  }
}

function openProjectModal(projectId = null) {
  currentProjectId = projectId;
  projectModal.classList.remove('hidden');
  projectForm.reset();
  if (projectId) {
    projectModalTitle.textContent = 'Редактирование проекта';
    const project = projects.find(p => p.id === projectId);
    if (project) {
      projectForm.elements['name'].value = project.name || '';
      projectForm.elements['desc'].value = project.desc || '';
      projectForm.elements['color'].value = project.color || '';
    }
  } else {
    projectModalTitle.textContent = 'Новый проект';
  }
}

function closeProjectModal() {
  projectModal.classList.add('hidden');
  currentProjectId = null;
}

async function handleProjectSubmit(event) {
  event.preventDefault();
  const formData = new FormData(projectForm);
  const payload = {
    name: formData.get('name')?.toString().trim() || '',
    desc: formData.get('desc')?.toString().trim() || '',
    color: formData.get('color')?.toString().trim() || ''
  };

  if (!payload.name) {
    showMessage('Название проекта обязательно', true);
    return;
  }

  const requestOptions = {
    method: currentProjectId ? 'PATCH' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  };

  try {
    if (currentProjectId) {
      await fetchJson(`/api/projects/${currentProjectId}`, requestOptions);
      showMessage('Проект обновлен');
    } else {
      await fetchJson('/api/projects', requestOptions);
      showMessage('Проект создан');
    }
    closeProjectModal();
    await reloadProjects();
  } catch (error) {
    showMessage(error.message, true);
  }
}

async function reloadProjects() {
  try {
    const selectedProject = filterProject.value;
    projects = await fetchJson('/api/projects');
    populateProjectsList();
    populateProjectFilter();
    if (selectedProject && projects.some(project => String(project.id) === selectedProject)) {
      filterProject.value = selectedProject;
    }
    renderTasks();
  } catch (error) {
    showMessage(error.message, true);
  }
}

function handleProjectAction(event) {
  const editBtn = event.target.closest('[data-project-edit]');
  const deleteBtn = event.target.closest('[data-project-delete]');
  if (!editBtn && !deleteBtn) {
    return;
  }
  event.stopPropagation();

  if (editBtn) {
    const projectId = parseInt(editBtn.dataset.projectEdit, 10);
    openProjectModal(projectId);
    return;
  }

  if (deleteBtn) {
    const projectId = parseInt(deleteBtn.dataset.projectDelete, 10);
    confirmAndDeleteProject(projectId);
  }
}

async function confirmAndDeleteProject(projectId) {
  const relatedTasks = countTasksForProject(projectId);
  const warningMessage = relatedTasks > 0
    ? `У проекта есть ${relatedTasks} задач. Сначала переназначьте или удалите их, иначе удаление может завершиться ошибкой.\nУдалить проект?`
    : 'Удалить проект?';
  const confirmed = window.confirm(warningMessage);
  if (!confirmed) {
    return;
  }
  try {
    await fetchJson(`/api/projects/${projectId}`, { method: 'DELETE' });
    showMessage('Проект удален');
    await reloadProjects();
    await loadTasks();
  } catch (error) {
    showMessage(error.message, true);
  }
}

// ---------------------------------------------------------------------------
// Print Control Functions
// ---------------------------------------------------------------------------

async function handlePrintAction(action, taskId) {
  const task = tasks.find(t => t.id === taskId);
  if (!task) {
    showMessage('Задача не найдена', true);
    return;
  }

  const confirmMessages = {
    start: `Запустить печать задачи "${task.name || 'Без названия'}"?`,
    pause: `Приостановить печать задачи "${task.name || 'Без названия'}"?`,
    resume: `Возобновить печать задачи "${task.name || 'Без названия'}"?`,
    cancel: `Отменить печать задачи "${task.name || 'Без названия'}"?\nМатериал будет списан частично.`
  };

  const confirmed = window.confirm(confirmMessages[action] || 'Выполнить действие?');
  if (!confirmed) {
    return;
  }

  try {
    const response = await fetchJson(`/api/tasks/${taskId}/print/${action}`, { method: 'POST' });
    if (response.success) {
      const successMessages = {
        start: 'Печать запущена',
        pause: 'Печать приостановлена',
        resume: 'Печать возобновлена',
        cancel: 'Печать отменена'
      };
      showMessage(successMessages[action] || 'Действие выполнено');
      await loadTasks();
    } else {
      showMessage(response.message || 'Ошибка выполнения', true);
    }
  } catch (error) {
    showMessage(error.message || 'Ошибка сети', true);
  }
}

// Автообновление списка задач для отслеживания прогресса печати
let autoRefreshInterval = null;

function startAutoRefresh() {
  if (autoRefreshInterval) {
    return;
  }
  autoRefreshInterval = setInterval(async () => {
    // Проверяем есть ли печатающиеся или приостановленные задачи
    const hasPrintingTasks = tasks.some(t => t.status === 'printing' || t.status === 'paused');
    if (hasPrintingTasks) {
      await loadTasks();
    }
  }, 5000); // Обновляем каждые 5 секунд
}

function stopAutoRefresh() {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
    autoRefreshInterval = null;
  }
}

// Запускаем автообновление при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
  startAutoRefresh();
});

// Останавливаем при уходе со страницы
window.addEventListener('beforeunload', () => {
  stopAutoRefresh();
});

// ---------------------------------------------------------------------------
// Offline Task Control Functions (для оффлайн-принтеров)
// ---------------------------------------------------------------------------

async function handleOfflineAction(action, taskId) {
  const task = tasks.find(t => t.id === taskId);
  if (!task) {
    showMessage('Задача не найдена', true);
    return;
  }

  switch (action) {
    case 'start':
      await offlineStartTask(taskId);
      break;
    case 'progress':
      openOfflineProgressModal(taskId);
      break;
    case 'complete':
      await offlineCompleteTask(taskId);
      break;
    case 'cancel':
      if (window.confirm(`Отменить задачу "${task.name || 'Без названия'}"?`)) {
        await offlineUpdateTask(taskId, { status: 'cancelled' });
      }
      break;
    case 'resume':
      await offlineUpdateTask(taskId, { status: 'printing' });
      showMessage('Печать возобновлена');
      break;
  }
}

async function offlineStartTask(taskId) {
  const task = tasks.find(t => t.id === taskId);
  if (!task) return;

  const confirmed = window.confirm(`Начать ручной трекинг задачи "${task.name || 'Без названия'}"?`);
  if (!confirmed) return;

  await offlineUpdateTask(taskId, { status: 'printing', progress: 0 });
  showMessage('Печать начата (ручной трекинг)');
}

async function offlineCompleteTask(taskId) {
  const task = tasks.find(t => t.id === taskId);
  if (!task) return;

  let deductMaterial = false;
  let message = `Завершить задачу "${task.name || 'Без названия'}"?`;

  // Если есть катушка и расход материала - предложить списать
  if (task.coil?.id && task.estimated_filament) {
    deductMaterial = window.confirm(
      `${message}\n\nСписать ${task.estimated_filament.toFixed(1)}г материала с катушки "${task.coil.name}"?`
    );
    if (!deductMaterial) {
      // Спросить подтверждение без списания
      const justComplete = window.confirm('Завершить без списания материала?');
      if (!justComplete) return;
    }
  } else {
    if (!window.confirm(message)) return;
  }

  try {
    const response = await fetchJson(`/api/tasks/${taskId}/offline/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        deduct_material: deductMaterial,
        amount: task.estimated_filament
      })
    });

    if (response.success) {
      let msg = 'Задача завершена';
      if (response.material_deducted) {
        msg += ` (списано ${response.material_deducted.toFixed(1)}г)`;
      }
      showMessage(msg);
      await loadTasks();
      // Обновляем катушки если был расход
      if (response.material_deducted) {
        coils = await fetchJson('/api/coils');
      }
    }
  } catch (error) {
    showMessage(error.message || 'Ошибка завершения задачи', true);
  }
}

async function offlineUpdateTask(taskId, data) {
  try {
    const response = await fetchJson(`/api/tasks/${taskId}/offline/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });

    if (response.success) {
      await loadTasks();
      return response;
    } else {
      showMessage(response.message || 'Ошибка обновления', true);
    }
  } catch (error) {
    showMessage(error.message || 'Ошибка сети', true);
  }
  return null;
}

// Переменная для хранения текущей оффлайн-задачи при обновлении прогресса
let currentOfflineTaskId = null;

function openOfflineProgressModal(taskId) {
  const task = tasks.find(t => t.id === taskId);
  if (!task) return;

  currentOfflineTaskId = taskId;

  const modal = document.getElementById('offlineProgressModal');
  if (!modal) {
    // Модальное окно еще не добавлено в HTML - создаём динамически
    createOfflineProgressModal();
  }

  const progressInput = document.getElementById('offlineProgressInput');
  const progressSlider = document.getElementById('offlineProgressSlider');
  const taskNameEl = document.getElementById('offlineTaskName');

  if (taskNameEl) taskNameEl.textContent = task.name || 'Без названия';
  if (progressInput) progressInput.value = task.progress || 0;
  if (progressSlider) progressSlider.value = task.progress || 0;

  document.getElementById('offlineProgressModal').classList.remove('hidden');
}

function createOfflineProgressModal() {
  const modal = document.createElement('div');
  modal.id = 'offlineProgressModal';
  modal.className = 'modal-backdrop hidden';
  modal.innerHTML = `
    <div class="modal-window">
      <div class="modal-header">
        <h2>Обновить прогресс</h2>
        <button class="close-btn" onclick="closeOfflineProgressModal()" aria-label="Закрыть">&times;</button>
      </div>
      <div class="modal-content">
        <p>Задача: <strong id="offlineTaskName"></strong></p>
        <div class="form-row">
          <label>Прогресс (%)</label>
          <div class="progress-input-group">
            <input type="number" id="offlineProgressInput" min="0" max="100" value="0">
            <input type="range" id="offlineProgressSlider" min="0" max="100" value="0" class="progress-slider">
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="ghost-btn" onclick="closeOfflineProgressModal()">Отмена</button>
        <button class="primary-btn" onclick="submitOfflineProgress()">Сохранить</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  // Синхронизация слайдера и инпута
  const progressInput = document.getElementById('offlineProgressInput');
  const progressSlider = document.getElementById('offlineProgressSlider');
  progressInput.addEventListener('input', () => { progressSlider.value = progressInput.value; });
  progressSlider.addEventListener('input', () => { progressInput.value = progressSlider.value; });

  // Закрытие по клику на фон
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeOfflineProgressModal();
  });
}

function closeOfflineProgressModal() {
  const modal = document.getElementById('offlineProgressModal');
  if (modal) modal.classList.add('hidden');
  currentOfflineTaskId = null;
}

async function submitOfflineProgress() {
  if (!currentOfflineTaskId) return;

  const progressInput = document.getElementById('offlineProgressInput');
  const progress = parseInt(progressInput.value, 10) || 0;

  await offlineUpdateTask(currentOfflineTaskId, { progress: Math.max(0, Math.min(100, progress)) });
  showMessage('Прогресс обновлён');
  closeOfflineProgressModal();
}
