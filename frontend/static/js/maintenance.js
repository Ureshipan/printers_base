/**
 * Модуль технического обслуживания принтеров
 */

// Состояние
let maintenanceTypes = [];
let maintenanceRecords = [];
let printerMaintenanceStatus = [];
let printers = [];

// DOM элементы
const upcomingList = document.getElementById('upcomingList');
const printersStatusList = document.getElementById('printersStatusList');
const historyTableBody = document.getElementById('historyTableBody');
const filterPrinterStatus = document.getElementById('filterPrinterStatus');
const filterHistoryPrinter = document.getElementById('filterHistoryPrinter');
const filterHistoryType = document.getElementById('filterHistoryType');
const toastContainer = document.getElementById('toastContainer');

// Модальные окна
const maintenanceModal = document.getElementById('maintenanceModal');
const forceMaintenanceModal = document.getElementById('forceMaintenanceModal');

// === Инициализация ===
document.addEventListener('DOMContentLoaded', async () => {
    initNavigation();
    await loadAllData();
    renderAll();
    registerEventListeners();
});

function initNavigation() {
    document.querySelectorAll('.sidebar-btn').forEach(btn => {
        const route = btn.getAttribute('data-route');
        if (route) {
            btn.addEventListener('click', () => {
                if (window.location.pathname !== route) {
                    window.location.href = route;
                }
            });
        }
    });
}

// === Загрузка данных ===
async function loadAllData() {
    try {
        const [types, upcoming, records, printersData] = await Promise.all([
            fetchJson('/api/maintenance/types'),
            fetchJson('/api/maintenance/upcoming'),
            fetchJson('/api/maintenance/records'),
            fetchJson('/api/printers'),
        ]);
        maintenanceTypes = types;
        printerMaintenanceStatus = upcoming;
        maintenanceRecords = records;
        printers = printersData;

        // Заполняем фильтры
        populateFilters();
    } catch (error) {
        showToast('Ошибка загрузки данных: ' + error.message, true);
    }
}

function populateFilters() {
    // Фильтр принтеров для истории
    filterHistoryPrinter.innerHTML = '<option value="">Все принтеры</option>';
    printers.forEach(p => {
        filterHistoryPrinter.innerHTML += `<option value="${p.id}">${p.name}</option>`;
    });

    // Фильтр типов для истории
    filterHistoryType.innerHTML = '<option value="">Все типы</option>';
    maintenanceTypes.forEach(t => {
        filterHistoryType.innerHTML += `<option value="${t.id}">${t.name}</option>`;
    });

    // Заполняем select для принудительного обслуживания
    const forceTypeSelect = document.getElementById('forceTypeSelect');
    forceTypeSelect.innerHTML = '<option value="">Выберите тип...</option>';
    maintenanceTypes.forEach(t => {
        forceTypeSelect.innerHTML += `<option value="${t.id}">${t.name}</option>`;
    });
}

// === Рендеринг ===
function renderAll() {
    renderUpcoming();
    renderPrintersStatus();
    renderHistory();
}

function renderUpcoming() {
    if (printerMaintenanceStatus.length === 0) {
        upcomingList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">✓</div>
                <p>Нет данных об обслуживании</p>
            </div>`;
        return;
    }

    // Берём первые 10 записей (уже отсортированы по API)
    const items = printerMaintenanceStatus.slice(0, 10);

    upcomingList.innerHTML = items.map(item => {
        const statusClass = item.is_overdue ? 'overdue' :
                           (item.hours_remaining < item.interval_hours * 0.2 ? 'warning' : 'ok');
        const labelClass = item.is_overdue ? 'overdue-label' :
                          (item.hours_remaining < item.interval_hours * 0.2 ? 'warning-label' : 'ok-label');

        const statusText = item.is_overdue
            ? `Просрочено на ${Math.abs(item.hours_remaining).toFixed(1)}ч`
            : `через ${item.hours_remaining.toFixed(1)}ч`;

        return `
            <div class="upcoming-item ${statusClass}">
                <div class="upcoming-info">
                    <strong>${item.printer_name}</strong>
                    <span>${item.type_name}</span>
                </div>
                <div class="upcoming-status">
                    <span class="${labelClass}">${statusText}</span>
                    <button class="action-btn primary"
                            onclick="openMaintenanceModal(${item.printer_id}, ${item.type_id}, '${item.printer_name}', '${item.type_name}')">
                        Выполнено
                    </button>
                </div>
            </div>`;
    }).join('');
}

function renderPrintersStatus() {
    const filter = filterPrinterStatus.value;

    // Группируем по принтерам
    const printerMap = new Map();
    printerMaintenanceStatus.forEach(item => {
        if (!printerMap.has(item.printer_id)) {
            printerMap.set(item.printer_id, {
                printer_id: item.printer_id,
                printer_name: item.printer_name,
                print_hours: item.print_hours,
                maintenance: []
            });
        }
        printerMap.get(item.printer_id).maintenance.push(item);
    });

    let printersList = Array.from(printerMap.values());

    // Применяем фильтр
    if (filter === 'overdue') {
        printersList = printersList.filter(p => p.maintenance.some(m => m.is_overdue));
    } else if (filter === 'ok') {
        printersList = printersList.filter(p => !p.maintenance.some(m => m.is_overdue));
    }

    if (printersList.length === 0) {
        printersStatusList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🖨️</div>
                <p>Нет принтеров для отображения</p>
            </div>`;
        return;
    }

    printersStatusList.innerHTML = printersList.map(printer => {
        const barsHtml = printer.maintenance.map(m => {
            const percent = Math.max(0, Math.min(100, (m.hours_since_last / m.interval_hours) * 100));
            const statusClass = m.is_overdue ? 'overdue' :
                               (m.hours_remaining < m.interval_hours * 0.2 ? 'warning' : 'ok');

            const remainingText = m.is_overdue
                ? `Просрочено: ${Math.abs(m.hours_remaining).toFixed(1)}ч`
                : `Осталось: ${m.hours_remaining.toFixed(1)}ч`;

            return `
                <div class="maintenance-bar-item">
                    <div class="maintenance-bar-label">
                        <span>${m.type_name}</span>
                        <span class="remaining ${statusClass}">${remainingText}</span>
                    </div>
                    <div class="maintenance-bar-track">
                        <div class="maintenance-bar-fill ${statusClass}" style="width: ${percent}%"></div>
                    </div>
                </div>`;
        }).join('');

        return `
            <div class="printer-status-item">
                <div class="printer-status-header">
                    <span class="printer-status-name">${printer.printer_name}</span>
                    <span class="printer-status-hours">${printer.print_hours.toFixed(1)}ч печати</span>
                </div>
                <div class="maintenance-bars">
                    ${barsHtml}
                </div>
                <div class="printer-status-actions">
                    ${printer.maintenance.map(m => `
                        <button class="action-btn secondary"
                                onclick="openMaintenanceModal(${printer.printer_id}, ${m.type_id}, '${printer.printer_name}', '${m.type_name}')">
                            ${m.type_name}
                        </button>
                    `).join('')}
                    <button class="action-btn warning"
                            onclick="openForceModal(${printer.printer_id}, '${printer.printer_name}')">
                        Затребовать
                    </button>
                </div>
            </div>`;
    }).join('');
}

function renderHistory() {
    const printerFilter = filterHistoryPrinter.value;
    const typeFilter = filterHistoryType.value;

    let filtered = maintenanceRecords;

    if (printerFilter) {
        filtered = filtered.filter(r => r.printer_id === parseInt(printerFilter));
    }
    if (typeFilter) {
        filtered = filtered.filter(r => r.maintenance_type_id === parseInt(typeFilter));
    }

    if (filtered.length === 0) {
        historyTableBody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 24px; color: #9fa3d1;">
                    Нет записей об обслуживании
                </td>
            </tr>`;
        return;
    }

    historyTableBody.innerHTML = filtered.slice(0, 50).map(r => `
        <tr>
            <td>${formatDate(r.performed_at)}</td>
            <td>${r.printer_name || '—'}</td>
            <td>${r.type_name || '—'}</td>
            <td>${r.print_hours_at.toFixed(1)}ч</td>
            <td>${r.notes || '—'}</td>
            <td>
                <button class="action-btn destructive" onclick="deleteRecord(${r.id})">
                    Удалить
                </button>
            </td>
        </tr>
    `).join('');
}

// === Обработчики событий ===
function registerEventListeners() {
    // Фильтры
    filterPrinterStatus.addEventListener('change', renderPrintersStatus);
    filterHistoryPrinter.addEventListener('change', renderHistory);
    filterHistoryType.addEventListener('change', renderHistory);

    // Кнопка обновления
    document.getElementById('refreshBtn').addEventListener('click', async () => {
        await loadAllData();
        renderAll();
        showToast('Данные обновлены');
    });

    // Модальное окно отметки обслуживания
    document.getElementById('closeMaintenanceModal').addEventListener('click', closeMaintenanceModal);
    document.getElementById('cancelMaintenance').addEventListener('click', closeMaintenanceModal);
    document.getElementById('maintenanceForm').addEventListener('submit', handleMaintenanceSubmit);

    // Модальное окно принудительного обслуживания
    document.getElementById('closeForceModal').addEventListener('click', closeForceModal);
    document.getElementById('cancelForce').addEventListener('click', closeForceModal);
    document.getElementById('forceMaintenanceForm').addEventListener('submit', handleForceSubmit);

    // Закрытие модалок по клику на фон
    maintenanceModal.addEventListener('click', (e) => {
        if (e.target === maintenanceModal) closeMaintenanceModal();
    });
    forceMaintenanceModal.addEventListener('click', (e) => {
        if (e.target === forceMaintenanceModal) closeForceModal();
    });
}

// === Модальные окна ===
function openMaintenanceModal(printerId, typeId, printerName, typeName) {
    document.getElementById('maintenancePrinterId').value = printerId;
    document.getElementById('maintenanceTypeId').value = typeId;
    document.getElementById('maintenancePrinterName').textContent = printerName;
    document.getElementById('maintenanceTypeName').textContent = typeName;
    document.querySelector('#maintenanceForm textarea[name="notes"]').value = '';
    maintenanceModal.classList.remove('hidden');
}

function closeMaintenanceModal() {
    maintenanceModal.classList.add('hidden');
}

function openForceModal(printerId, printerName) {
    document.getElementById('forcePrinterId').value = printerId;
    document.getElementById('forcePrinterName').textContent = printerName;
    document.getElementById('forceTypeSelect').value = '';
    forceMaintenanceModal.classList.remove('hidden');
}

function closeForceModal() {
    forceMaintenanceModal.classList.add('hidden');
}

async function handleMaintenanceSubmit(e) {
    e.preventDefault();

    const printerId = document.getElementById('maintenancePrinterId').value;
    const typeId = document.getElementById('maintenanceTypeId').value;
    const notes = document.querySelector('#maintenanceForm textarea[name="notes"]').value.trim();

    try {
        const response = await fetchJson('/api/maintenance/records', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                printer_id: parseInt(printerId),
                maintenance_type_id: parseInt(typeId),
                notes: notes || null,
            }),
        });

        if (response.success) {
            showToast('Обслуживание отмечено');
            closeMaintenanceModal();
            await loadAllData();
            renderAll();
        } else {
            showToast(response.message || 'Ошибка при сохранении', true);
        }
    } catch (error) {
        showToast('Ошибка: ' + error.message, true);
    }
}

async function handleForceSubmit(e) {
    e.preventDefault();

    const printerId = document.getElementById('forcePrinterId').value;
    const typeId = document.getElementById('forceTypeSelect').value;

    if (!typeId) {
        showToast('Выберите тип обслуживания', true);
        return;
    }

    try {
        const response = await fetchJson(`/api/maintenance/force/${printerId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                maintenance_type_id: parseInt(typeId),
            }),
        });

        if (response.success) {
            showToast('Обслуживание затребовано');
            closeForceModal();
            await loadAllData();
            renderAll();
        } else {
            showToast(response.message || 'Ошибка', true);
        }
    } catch (error) {
        showToast('Ошибка: ' + error.message, true);
    }
}

async function deleteRecord(recordId) {
    if (!confirm('Удалить эту запись обслуживания?')) return;

    try {
        const response = await fetchJson(`/api/maintenance/records/${recordId}`, {
            method: 'DELETE',
        });

        if (response.success) {
            showToast('Запись удалена');
            await loadAllData();
            renderAll();
        } else {
            showToast(response.message || 'Ошибка удаления', true);
        }
    } catch (error) {
        showToast('Ошибка: ' + error.message, true);
    }
}

// === Утилиты ===
async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
        const text = await response.text();
        throw new Error(text || response.statusText);
    }
    return response.json();
}

function formatDate(isoString) {
    if (!isoString) return '—';
    const date = new Date(isoString);
    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function showToast(message, isError = false) {
    const toast = document.createElement('div');
    toast.className = `toast${isError ? ' toast-error' : ''}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-8px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
