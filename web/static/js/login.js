document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('error');
    
    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            window.location.href = '/api/dashboard';
        } else {
            errorDiv.textContent = data.error || 'Неверные учетные данные';
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        errorDiv.textContent = 'Ошибка подключения к серверу';
        errorDiv.style.display = 'block';
    }
});
