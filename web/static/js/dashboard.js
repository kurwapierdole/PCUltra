// PCUltra Dashboard - Core functionality
document.addEventListener('DOMContentLoaded', () => {
    // Initialize theme system
    initThemeSystem();
    
    // Set up navigation
    initNavigation();
    
    // Initialize bot controls
    initBotControls();
    
    // Initialize forms
    initForms();
    
    // Start status updates
    startStatusMonitoring();
    
    // Initialize data loading
    loadData();
    
    // Set up animated background
    setupAnimatedBackground();
    
    console.log('PCUltra Dashboard fully initialized');
});

// Theme system
let themeAnimationTimeout;
const THEME_STORAGE_KEY = 'pcu-theme-preference';

function initThemeSystem() {
    const themeSwitch = document.getElementById('theme-switch');
    if (!themeSwitch) return;
    
    // Apply stored theme
    let storedTheme = null;
    try {
        storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    } catch (error) {
        console.warn('Theme storage unavailable:', error);
    }
    
    applyTheme(storedTheme === 'light' ? 'light' : 'dark', { silent: true });
    
    // Set up theme switch
    themeSwitch.addEventListener('change', () => {
        applyTheme(themeSwitch.checked ? 'light' : 'dark');
    });
    
    // Set initial aria attributes
    themeSwitch.setAttribute('aria-label', 'Переключить светлую и тёмную темы');
    themeSwitch.setAttribute('aria-checked', themeSwitch.checked);
}

function applyTheme(theme, { silent = false } = {}) {
    if (!document.body) return;
    
    const normalized = theme === 'light' ? 'light' : 'dark';
    document.body.classList.remove('theme-dark', 'theme-light');
    document.body.classList.add(`theme-${normalized}`);
    document.body.setAttribute('data-theme', normalized);
    
    const themeSwitch = document.getElementById('theme-switch');
    if (themeSwitch) {
        themeSwitch.checked = normalized === 'light';
        themeSwitch.setAttribute('aria-checked', normalized === 'light');
    }
    
    // Save preference
    try {
        localStorage.setItem(THEME_STORAGE_KEY, normalized);
    } catch (error) {
        console.warn('Theme storage unavailable:', error);
    }
    
    // Update glow colors
    refreshGlowPalette();
    
    // Trigger ripple animation
    if (!silent) {
        triggerThemeRipple();
    }
}

function refreshGlowPalette() {
    if (!document.body) return;
    const styles = getComputedStyle(document.body);
    const primary = styles.getPropertyValue('--bg-glow-1').trim();
    const secondary = styles.getPropertyValue('--bg-glow-2').trim();
    
    if (primary && secondary) {
        document.documentElement.style.setProperty('--current-bg-glow-1', primary);
        document.documentElement.style.setProperty('--current-bg-glow-2', secondary);
    }
}

function triggerThemeRipple() {
    if (!document.body) return;
    document.body.classList.add('theme-animating');
    clearTimeout(themeAnimationTimeout);
    themeAnimationTimeout = setTimeout(() => {
        document.body.classList.remove('theme-animating');
    }, 720);
}

// Navigation system
function initNavigation() {
    // Set up main navigation
    document.querySelectorAll('.nav-link[data-page]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = link.getAttribute('data-page');
            showPanel(page);
            
            // Update active state
            document.querySelectorAll('.nav-link').forEach(l => {
                l.classList.remove('active');
                if (l.getAttribute('aria-current')) {
                    l.removeAttribute('aria-current');
                }
            });
            link.classList.add('active');
            link.setAttribute('aria-current', 'page');
            
            // Close mobile menu if needed
            closeMobileMenu();
        });
    });
    
    // Set initial active panel
    const initialPanel = document.querySelector('.nav-link.active')?.getAttribute('data-page') || 'dashboard';
    showPanel(initialPanel);
}

function showPanel(panelName) {
    // Hide all panels
    document.querySelectorAll('.content-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    
    // Show selected panel
    const panel = document.getElementById(`${panelName}-panel`);
    if (panel) {
        panel.classList.add('active');
    }
    
    // Update URL hash for history/navigation
    window.history.replaceState(null, null, `#${panelName}`);
    
    // Special handling for data loading
    if (panelName === 'shortcuts') {
        loadShortcuts();
    } else if (panelName === 'users') {
        loadUsers();
    }
}

function closeMobileMenu() {
    // Mobile-specific functionality would go here
    const sidebar = document.querySelector('.sidebar');
    if (sidebar && window.innerWidth <= 768) {
        // Logic to close sidebar on mobile would go here
    }
}

// Bot controls
let statusInterval;
let resourceInterval;

function initBotControls() {
    const startBtn = document.getElementById('btn-start-bot');
    const stopBtn = document.getElementById('btn-stop-bot');
    const restartBtn = document.getElementById('btn-restart-bot');
    
    if (startBtn) {
        startBtn.addEventListener('click', handleBotStart);
    }
    
    if (stopBtn) {
        stopBtn.addEventListener('click', handleBotStop);
    }
    
    if (restartBtn) {
        restartBtn.addEventListener('click', handleBotRestart);
    }
}

async function handleBotStart() {
    if (!confirm('Запустить бота?')) return;
    
    try {
        showLoadingState('btn-start-bot', true);
        const response = await fetch('/api/bot/start', { 
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification('success', 'Бот успешно запущен');
            await updateStatus();
        } else {
            showNotification('error', `Ошибка: ${data.error || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        console.error('Start bot error:', error);
        showNotification('error', 'Ошибка подключения к серверу');
    } finally {
        showLoadingState('btn-start-bot', false);
    }
}

async function handleBotStop() {
    if (!confirm('Остановить бота?')) return;
    
    try {
        showLoadingState('btn-stop-bot', true);
        const response = await fetch('/api/bot/stop', { 
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification('success', 'Бот успешно остановлен');
            await updateStatus();
        } else {
            showNotification('error', `Ошибка: ${data.error || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        console.error('Stop bot error:', error);
        showNotification('error', 'Ошибка подключения к серверу');
    } finally {
        showLoadingState('btn-stop-bot', false);
    }
}

async function handleBotRestart() {
    if (!confirm('Перезапустить бота?')) return;
    
    try {
        showLoadingState('btn-restart-bot', true);
        const response = await fetch('/api/bot/restart', { 
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification('success', 'Бот успешно перезапущен');
            await updateStatus();
        } else {
            showNotification('error', `Ошибка: ${data.error || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        console.error('Restart bot error:', error);
        showNotification('error', 'Ошибка подключения к серверу');
    } finally {
        showLoadingState('btn-restart-bot', false);
    }
}

// Status monitoring
function startStatusMonitoring() {
    // Initial update
    updateStatus();
    
    // Set up interval (5 seconds is enough for both status and resources)
    statusInterval = setInterval(updateStatus, 1000);
    
    // Clean up on page unload
    window.addEventListener('beforeunload', () => {
        if (statusInterval) clearInterval(statusInterval);
    });
}

async function updateStatus() {
    try {
        const response = await fetch('/api/status', {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update bot status
        if (data.bot && data.bot.running !== undefined) {
            updateBotStatusUI(data.bot.running);
        }
        
        // Update system resources - ИСПРАВЛЕНО: данные ресурсов в том же ответе
        if (data.system && data.system.cpu !== undefined && data.system.memory && data.system.memory.percent !== undefined) {
            updateResourceUI(data.system.cpu, data.system.memory.percent);
        }
    } catch (error) {
        console.error('Status update error:', error);
    }
}

function updateBotStatusUI(isRunning) {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.getElementById('bot-status-text');
    const startBtn = document.getElementById('btn-start-bot');
    const stopBtn = document.getElementById('btn-stop-bot');
    
    if (!statusDot || !statusText || !startBtn || !stopBtn) return;
    
    if (isRunning) {
        statusText.textContent = 'Запущен';
        statusDot.classList.add('running');
        statusDot.classList.remove('stopped');
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        statusText.textContent = 'Остановлен';
        statusDot.classList.add('stopped');
        statusDot.classList.remove('running');
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

function updateResourceUI(cpuPercent, memoryPercent) {
    const cpuProgress = document.getElementById('cpu-progress');
    const cpuText = document.getElementById('cpu-text');
    const memoryProgress = document.getElementById('memory-progress');
    const memoryText = document.getElementById('memory-text');
    
    if (cpuProgress) cpuProgress.style.width = `${Math.min(100, Math.max(0, cpuPercent))}%`;
    if (cpuText) cpuText.textContent = `${cpuPercent.toFixed(1)}%`;
    if (memoryProgress) memoryProgress.style.width = `${Math.min(100, Math.max(0, memoryPercent))}%`;
    if (memoryText) memoryText.textContent = `${memoryPercent.toFixed(1)}%`;
}

// Form handling
function initForms() {
    // Config forms
    setupForm('config-form', '/api/config', loadConfig);
    setupForm('web-config-form', '/api/config', null, () => {
        document.getElementById('admin-password').value = '';
    });
    
    // Shortcuts form
    setupForm('shortcut-form', '/api/shortcuts', loadShortcuts);
    
    // Users form
    setupForm('user-form', '/api/users', loadUsers);
}

function setupForm(formId, endpoint, onSuccessCallback, onFinallyCallback) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (form.classList.contains('submitting')) return;
        
        try {
            form.classList.add('submitting');
            const submitButton = form.querySelector('button[type="submit"]');
            const originalText = submitButton.textContent;
            submitButton.disabled = true;
            submitButton.textContent = 'Сохранение...';
            
            // Get form data
            const formData = getFormData(form);
            
            // Submit to API
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(formData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                showNotification('success', 'Данные успешно сохранены');
                if (typeof onSuccessCallback === 'function') {
                    onSuccessCallback();
                }
            } else {
                showNotification('error', `Ошибка: ${data.error || 'Неизвестная ошибка'}`);
            }
        } catch (error) {
            console.error('Form submit error:', error);
            showNotification('error', 'Ошибка подключения к серверу');
        } finally {
            form.classList.remove('submitting');
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = submitButton.dataset.originalText || submitButton.textContent;
            }
            
            if (typeof onFinallyCallback === 'function') {
                onFinallyCallback();
            }
        }
    });
}

function getFormData(form) {
    const formData = {};
    const inputs = form.querySelectorAll('input, select, textarea');
    
    inputs.forEach(input => {
        let value;
        if (input.type === 'checkbox') {
            value = input.checked;
        } else if (input.type === 'number') {
            value = input.value ? parseFloat(input.value) : null;
        } else {
            value = input.value.trim();
        }
        
        if (input.name) {
            formData[input.name] = value;
        }
    });
    
    return formData;
}

// Data loading
async function loadData() {
    try {
        await Promise.all([
            loadConfig(),
            loadShortcuts(),
            loadUsers()
        ]);
    } catch (error) {
        console.error('Initial data load error:', error);
    }
}

// Config loading
async function loadConfig() {
    try {
        const response = await fetch('/api/config', {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const config = await response.json();
        
        // Update UI with config values
        if (config.bot) {
            if (config.bot.token) document.getElementById('bot-token').value = config.bot.token;
            if (config.bot.command_timeout !== undefined) document.getElementById('command-timeout').value = config.bot.command_timeout;
            if (config.bot.auto_start !== undefined) document.getElementById('auto-start').checked = config.bot.auto_start;
        }
        
        if (config.web && config.web.admin_username) {
            document.getElementById('admin-username').value = config.web.admin_username;
        }
    } catch (error) {
        console.error('Config load error:', error);
    }
}

// Shortcuts loading and management
function loadShortcuts() {
    const listContainer = document.getElementById('shortcuts-list');
    if (!listContainer) return;
    
    // Show loading state
    listContainer.innerHTML = '<div class="loading-spinner"></div>';
    
    fetch('/api/shortcuts', {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return response.json();
    })
    .then(shortcuts => {
        renderShortcuts(shortcuts, listContainer);
    })
    .catch(error => {
        console.error('Shortcuts load error:', error);
        listContainer.innerHTML = `
            <div class="error-state">
                <p class="error-message">Ошибка загрузки команд</p>
                <button class="btn btn-small btn-primary" onclick="loadShortcuts()">Повторить</button>
            </div>
        `;
    });
}

function renderShortcuts(shortcuts, container) {
    if (!container) return;
    
    const shortcutEntries = Object.entries(shortcuts || {});
    
    if (shortcutEntries.length === 0) {
        container.innerHTML = '<p class="empty-state">Нет настроенных команд</p>';
        return;
    }
    
    container.innerHTML = '';
    
    shortcutEntries.forEach(([id, shortcut]) => {
        const item = document.createElement('div');
        item.className = 'shortcut-item';
        item.dataset.id = id;
        
        // Determine display name - use explicit display_name if available, else extract from command
        const displayName = shortcut.display_name || 
                           (shortcut.command.startsWith('/') ? shortcut.command.substring(1) : shortcut.command);
        
        item.innerHTML = `
            <div class="info">
                <div class="command">${escapeHtml(displayName)}</div>
                <div class="path">${escapeHtml(shortcut.path)}</div>
                <div class="action-type">
                    <span class="action-badge ${getActionBadgeClass(shortcut.action)}">
                        ${getActionDisplayName(shortcut.action)}
                    </span>
                </div>
            </div>
            <button class="btn btn-danger btn-small delete-shortcut" data-id="${escapeHtml(id)}" aria-label="Удалить команду ${escapeHtml(displayName)}">
                Удалить
            </button>
        `;
        
        container.appendChild(item);
    });
    
    // Add event listeners
    container.querySelectorAll('.delete-shortcut').forEach(button => {
        button.addEventListener('click', (e) => {
            const id = e.currentTarget.dataset.id;
            deleteShortcut(id);
        });
    });
}

function getActionDisplayName(action) {
    const actions = {
        'launch_app': 'Приложение',
        'open_url': 'Ссылка',
        'execute_script': 'Скрипт'
    };
    return actions[action] || action;
}

function getActionBadgeClass(action) {
    const classes = {
        'launch_app': 'badge-app',
        'open_url': 'badge-url',
        'execute_script': 'badge-script'
    };
    return classes[action] || '';
}

// Users loading and management
function loadUsers() {
    const listContainer = document.getElementById('users-list');
    if (!listContainer) return;
    
    // Show loading state
    listContainer.innerHTML = '<div class="loading-spinner"></div>';
    
    fetch('/api/users', {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return response.json();
    })
    .then(users => {
        renderUsers(users || [], listContainer);
    })
    .catch(error => {
        console.error('Users load error:', error);
        listContainer.innerHTML = `
            <div class="error-state">
                <p class="error-message">Ошибка загрузки пользователей</p>
                <button class="btn btn-small btn-primary" onclick="loadUsers()">Повторить</button>
            </div>
        `;
    });
}

function renderUsers(users, container) {
    if (!container) return;
    
    if (users.length === 0) {
        container.innerHTML = '<p class="empty-state">Нет авторизованных пользователей</p>';
        return;
    }
    
    container.innerHTML = '';
    
    users.forEach(userId => {
        const item = document.createElement('div');
        item.className = 'user-item';
        item.dataset.id = userId;
        
        item.innerHTML = `
            <div class="info">
                <div class="user-id">ID: ${escapeHtml(userId.toString())}</div>
            </div>
            <button class="btn btn-danger btn-small delete-user" data-id="${escapeHtml(userId.toString())}" aria-label="Удалить пользователя ${escapeHtml(userId.toString())}">
                Удалить
            </button>
        `;
        
        container.appendChild(item);
    });
    
    // Add event listeners
    container.querySelectorAll('.delete-user').forEach(button => {
        button.addEventListener('click', (e) => {
            const id = e.currentTarget.dataset.id;
            deleteUser(id);
        });
    });
}

// Delete functions
function deleteShortcut(id) {
    if (!id || !confirm(`Удалить команду "${id}"?`)) return;
    
    fetch(`/api/shortcuts/${encodeURIComponent(id)}`, { 
        method: 'DELETE',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showNotification('success', 'Команда успешно удалена');
            loadShortcuts();
        } else {
            throw new Error(data.error || 'Неизвестная ошибка');
        }
    })
    .catch(error => {
        console.error('Delete shortcut error:', error);
        showNotification('error', `Ошибка: ${error.message || 'Не удалось удалить команду'}`);
    });
}

function deleteUser(id) {
    if (!id || !confirm(`Удалить пользователя с ID "${id}"?`)) return;
    
    fetch(`/api/users/${encodeURIComponent(id)}`, { 
        method: 'DELETE',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showNotification('success', 'Пользователь успешно удален');
            loadUsers();
        } else {
            throw new Error(data.error || 'Неизвестная ошибка');
        }
    })
    .catch(error => {
        console.error('Delete user error:', error);
        showNotification('error', `Ошибка: ${error.message || 'Не удалось удалить пользователя'}`);
    });
}

// Animated background
let mouseX = 0;
let mouseY = 0;
let targetX = 50;
let targetY = 50;
let animationFrameId = null;

function setupAnimatedBackground() {
    const animatedBg = document.getElementById('animatedBg');
    if (!animatedBg) return;
    
    // Mouse tracking
    document.addEventListener('mousemove', (e) => {
        mouseX = (e.clientX / window.innerWidth) * 100;
        mouseY = (e.clientY / window.innerHeight) * 100;
    });
    
    // Start animation
    animateBackground();
    
    // Handle window resize
    window.addEventListener('resize', () => {
        cancelAnimationFrame(animationFrameId);
        animateBackground();
    });
    
    // Clean up on page unload
    window.addEventListener('beforeunload', () => {
        cancelAnimationFrame(animationFrameId);
    });
}

function animateBackground() {
    targetX += (mouseX - targetX) * 0.05;
    targetY += (mouseY - targetY) * 0.05;
    
    const animatedBg = document.getElementById('animatedBg');
    if (animatedBg) {
        const styles = getComputedStyle(document.body);
        const primaryGlow = styles.getPropertyValue('--bg-glow-1').trim() || 'rgba(139, 92, 246, 0.4)';
        const secondaryGlow = styles.getPropertyValue('--bg-glow-2').trim() || 'rgba(124, 58, 237, 0.2)';
        
        animatedBg.style.background = `
            radial-gradient(circle at ${targetX.toFixed(1)}% ${targetY.toFixed(1)}%, ${primaryGlow} 0%, transparent 70%),
            radial-gradient(circle at ${100 - targetX.toFixed(1)}% ${100 - targetY.toFixed(1)}%, ${secondaryGlow} 0%, transparent 60%)
        `;
    }
    
    animationFrameId = requestAnimationFrame(animateBackground);
}

// Utility functions
function showLoadingState(elementId, isLoading) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    if (isLoading) {
        element.disabled = true;
        element.dataset.originalText = element.textContent;
        element.textContent = 'Загрузка...';
        element.classList.add('loading');
    } else {
        element.disabled = false;
        if (element.dataset.originalText) {
            element.textContent = element.dataset.originalText;
            delete element.dataset.originalText;
        }
        element.classList.remove('loading');
    }
}

function showNotification(type, message) {
    // Create or update notification
    let notification = document.querySelector('.global-notification');
    
    if (!notification) {
        notification = document.createElement('div');
        notification.className = 'global-notification';
        notification.style.position = 'fixed';
        notification.style.top = '20px';
        notification.style.right = '20px';
        notification.style.padding = '15px 25px';
        notification.style.borderRadius = '12px';
        notification.style.color = 'white';
        notification.style.fontWeight = '500';
        notification.style.boxShadow = '0 4px 15px rgba(0,0,0,0.2)';
        notification.style.zIndex = '10000';
        notification.style.transform = 'translateX(400px)';
        notification.style.opacity = '0';
        notification.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
        document.body.appendChild(notification);
    }
    
    // Set styles based on type
    const styles = {
        success: {
            background: 'linear-gradient(135deg, #10b981, #34d399)',
            icon: '✓'
        },
        error: {
            background: 'linear-gradient(135deg, #ef4444, #f87171)',
            icon: '!'
        },
        info: {
            background: 'linear-gradient(135deg, #3b82f6, #60a5fa)',
            icon: 'i'
        }
    };
    
    const style = styles[type] || styles.info;
    notification.style.background = style.background;
    
    // Update content
    notification.innerHTML = `<span style="margin-right: 8px">${style.icon}</span>${escapeHtml(message)}`;
    
    // Show notification
    requestAnimationFrame(() => {
        notification.style.transform = 'translateX(0)';
        notification.style.opacity = '1';
        
        // Auto hide after 5 seconds
        setTimeout(() => {
            notification.style.transform = 'translateX(400px)';
            notification.style.opacity = '0';
            
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 5000);
    });
}

function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') return unsafe;
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "<")
        .replace(/>/g, ">")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboard);
} else {
    initDashboard();
}

function initDashboard() {
    console.log('PCUltra Dashboard initializing...');
    // Main initialization will happen through the DOMContentLoaded event listener
}