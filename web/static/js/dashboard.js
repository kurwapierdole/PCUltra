// Page navigation
document.querySelectorAll('.nav-link[data-page]').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const page = link.getAttribute('data-page');
        showPage(page);
        
        // Update active state
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
    });
});

function showPage(pageName) {
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById(`${pageName}-page`).classList.add('active');
}

// Status update
let statusInterval;

async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        // Update bot status
        const botStatus = document.getElementById('bot-status-text');
        const statusDot = document.querySelector('.status-dot');
        const btnStart = document.getElementById('btn-start-bot');
        const btnStop = document.getElementById('btn-stop-bot');
        
        if (data.bot.running) {
            botStatus.textContent = 'Запущен';
            statusDot.classList.add('running');
            statusDot.classList.remove('stopped');
            btnStart.disabled = true;
            btnStop.disabled = false;
        } else {
            botStatus.textContent = 'Остановлен';
            statusDot.classList.add('stopped');
            statusDot.classList.remove('running');
            btnStart.disabled = false;
            btnStop.disabled = true;
        }
        
        // Update system resources
        document.getElementById('cpu-text').textContent = `${data.system.cpu.toFixed(1)}%`;
        document.getElementById('cpu-progress').style.width = `${data.system.cpu}%`;
        
        const memoryPercent = data.system.memory.percent;
        document.getElementById('memory-text').textContent = `${memoryPercent.toFixed(1)}%`;
        document.getElementById('memory-progress').style.width = `${memoryPercent}%`;
    } catch (error) {
        console.error('Status update error:', error);
    }
}

// Bot controls
document.getElementById('btn-start-bot').addEventListener('click', async () => {
    if (confirm('Запустить бота?')) {
        try {
            const response = await fetch('/api/bot/start', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                alert('Бот запущен');
                updateStatus();
            } else {
                alert(`Ошибка: ${data.error}`);
            }
        } catch (error) {
            alert('Ошибка подключения к серверу');
        }
    }
});

document.getElementById('btn-stop-bot').addEventListener('click', async () => {
    if (confirm('Остановить бота?')) {
        try {
            const response = await fetch('/api/bot/stop', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                alert('Бот остановлен');
                updateStatus();
            } else {
                alert(`Ошибка: ${data.error}`);
            }
        } catch (error) {
            alert('Ошибка подключения к серверу');
        }
    }
});

document.getElementById('btn-restart-bot').addEventListener('click', async () => {
    if (confirm('Перезапустить бота?')) {
        try {
            const response = await fetch('/api/bot/restart', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                alert('Бот перезапущен');
                updateStatus();
            } else {
                alert(`Ошибка: ${data.error}`);
            }
        } catch (error) {
            alert('Ошибка подключения к серверу');
        }
    }
});

// Load configuration
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        
        document.getElementById('bot-token').value = config.bot.token || '';
        document.getElementById('command-timeout').value = config.bot.command_timeout || 30;
        document.getElementById('auto-start').checked = config.bot.auto_start || false;
        document.getElementById('admin-username').value = config.web.admin_username || 'admin';
    } catch (error) {
        console.error('Config load error:', error);
    }
}

// Save bot configuration
document.getElementById('config-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const updates = {
        bot: {
            token: document.getElementById('bot-token').value,
            command_timeout: parseInt(document.getElementById('command-timeout').value),
            auto_start: document.getElementById('auto-start').checked
        }
    };
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Конфигурация сохранена');
        } else {
            alert(`Ошибка: ${data.error}`);
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
});

// Save web configuration
document.getElementById('web-config-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const updates = {
        web: {
            admin_username: document.getElementById('admin-username').value,
            admin_password: document.getElementById('admin-password').value
        }
    };
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Конфигурация Web UI сохранена');
            document.getElementById('admin-password').value = '';
        } else {
            alert(`Ошибка: ${data.error}`);
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
});

// Load shortcuts
async function loadShortcuts() {
    try {
        const response = await fetch('/api/shortcuts');
        const shortcuts = await response.json();
        
        const list = document.getElementById('shortcuts-list');
        list.innerHTML = '';
        
        for (const [id, shortcut] of Object.entries(shortcuts)) {
            const item = document.createElement('div');
            item.className = 'shortcut-item';
            item.innerHTML = `
                <div class="info">
                    <div class="command">${shortcut.command}</div>
                    <div class="path">${shortcut.path}</div>
                </div>
                <button class="btn btn-danger btn-small" onclick="deleteShortcut('${id}')">Удалить</button>
            `;
            list.appendChild(item);
        }
    } catch (error) {
        console.error('Shortcuts load error:', error);
    }
}

// Add shortcut
document.getElementById('shortcut-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = {
        command: document.getElementById('shortcut-command').value,
        action: document.getElementById('shortcut-action').value,
        path: document.getElementById('shortcut-path').value,
        args: document.getElementById('shortcut-args').value.split(',').map(s => s.trim()).filter(s => s)
    };
    
    try {
        const response = await fetch('/api/shortcuts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Команда добавлена');
            document.getElementById('shortcut-form').reset();
            loadShortcuts();
        } else {
            alert(`Ошибка: ${data.error}`);
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
});

// Delete shortcut
window.deleteShortcut = async (id) => {
    if (confirm('Удалить команду?')) {
        try {
            const response = await fetch(`/api/shortcuts/${id}`, { method: 'DELETE' });
            const data = await response.json();
            if (data.success) {
                loadShortcuts();
            } else {
                alert(`Ошибка: ${data.error}`);
            }
        } catch (error) {
            alert('Ошибка подключения к серверу');
        }
    }
};

// Load users
async function loadUsers() {
    try {
        const response = await fetch('/api/users');
        const users = await response.json();
        
        const list = document.getElementById('users-list');
        list.innerHTML = '';
        
        users.forEach(userId => {
            const item = document.createElement('div');
            item.className = 'user-item';
            item.innerHTML = `
                <div class="info">User ID: ${userId}</div>
                <button class="btn btn-danger btn-small" onclick="deleteUser(${userId})">Удалить</button>
            `;
            list.appendChild(item);
        });
    } catch (error) {
        console.error('Users load error:', error);
    }
}

// Add user
document.getElementById('user-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const userId = parseInt(document.getElementById('user-id').value);
    
    try {
        const response = await fetch('/api/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Пользователь добавлен');
            document.getElementById('user-form').reset();
            loadUsers();
        } else {
            alert(`Ошибка: ${data.error}`);
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
});

// Delete user
window.deleteUser = async (userId) => {
    if (confirm('Удалить пользователя?')) {
        try {
            const response = await fetch(`/api/users/${userId}`, { method: 'DELETE' });
            const data = await response.json();
            if (data.success) {
                loadUsers();
            } else {
                alert(`Ошибка: ${data.error}`);
            }
        } catch (error) {
            alert('Ошибка подключения к серверу');
        }
    }
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    updateStatus();
    statusInterval = setInterval(updateStatus, 2000);
    loadConfig();
    loadShortcuts();
    loadUsers();
});
