let tasks = [];
let projects = [];
let printers = [];
let coils = [];
let currentTaskId = null;
let currentProjectId = null;
let pendingGcodeFile = null;  // Файл G-code для загрузки при создании задачи

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
          <button class="action-btn primary" data-action="edit" data-id="${task.id}">Редактировать</button>
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

function handleRowAction(event) {
  const actionButton = event.target.closest('[data-action], [data-remove-gcode], [data-download]');
  if (!actionButton) {
    return;
  }
  event.stopPropagation();

  if (actionButton.dataset.download !== undefined) {
    // let the link proceed naturally
    return;
  }

  const taskId = parseInt(actionButton.dataset.id, 10);
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

  if (taskId) {
    modalTitle.textContent = 'Редактирование задачи';
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

      // Показываем информацию о загруженном G-code файле
      if (task.gcode?.has_file && gcodeFileName) {
        gcodeFileName.textContent = task.gcode.original_name || 'Файл загружен';
        gcodeUploadSection?.classList.add('has-file');
      }
    }
  } else {
    modalTitle.textContent = 'Новая задача';
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
