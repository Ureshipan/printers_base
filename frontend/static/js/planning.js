let tasks = [];
let projects = [];
let printers = [];
let coils = [];
let currentTaskId = null;
let currentProjectId = null;

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

  projectSelect.innerHTML = '';
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
    const option = document.createElement('option');
    option.value = coil.id;
    option.textContent = coil.material
      ? `${coil.name} (${coil.material})`
      : coil.name;
    coilSelect.appendChild(option);
  });
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
  return `
    <div class="gcode-info">
      <span>${name}</span>
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

  try {
    if (currentTaskId) {
      await fetchJson(`/api/tasks/${currentTaskId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      showMessage('Задача обновлена');
    } else {
      await fetchJson('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      showMessage('Задача создана');
    }
    closeTaskModal();
    await loadTasks();
    populateProjectsList();
  } catch (error) {
    showMessage(error.message, true);
  }
}

function showMessage(text, isError = false) {
  planningMessage.textContent = text;
  planningMessage.hidden = false;
  planningMessage.classList.toggle('error', isError);
  setTimeout(() => {
    planningMessage.hidden = true;
  }, 4000);
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

