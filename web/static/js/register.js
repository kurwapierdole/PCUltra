document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    const errorDiv = document.getElementById('error');
    
    // Clear previous errors
    errorDiv.style.display = 'none';
    errorDiv.textContent = '';
    
    // Client-side validation
    if (!username) {
        errorDiv.textContent = 'Имя пользователя не может быть пустым';
        errorDiv.style.display = 'block';
        return;
    }
    
    if (password.length < 6) {
        errorDiv.textContent = 'Пароль должен содержать минимум 6 символов';
        errorDiv.style.display = 'block';
        return;
    }
    
    if (password !== confirmPassword) {
        errorDiv.textContent = 'Пароли не совпадают';
        errorDiv.style.display = 'block';
        return;
    }
    
    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                username, 
                password, 
                confirm_password: confirmPassword 
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Redirect to dashboard
            window.location.href = '/api/dashboard';
        } else {
            errorDiv.textContent = data.error || 'Ошибка регистрации';
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        errorDiv.textContent = 'Ошибка подключения к серверу';
        errorDiv.style.display = 'block';
    }
});
