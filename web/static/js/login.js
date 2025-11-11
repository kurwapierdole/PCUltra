document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    if (!loginForm) return;
    
    let isSubmitting = false;
    let attemptCount = 0;
    const MAX_ATTEMPTS = 5;
    const LOCKOUT_TIME = 30; // seconds
    
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (isSubmitting) return;
        
        // Check for lockout
        if (attemptCount >= MAX_ATTEMPTS) {
            showError(`Слишком много попыток входа. Попробуйте через ${LOCKOUT_TIME} секунд.`);
            return;
        }
        
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;
        const errorDiv = document.getElementById('error');
        
        // Clear previous errors
        errorDiv.style.display = 'none';
        errorDiv.textContent = '';
        
        // Client-side validation
        if (!username) {
            showError('Введите имя пользователя');
            return;
        }
        
        if (!password) {
            showError('Введите пароль');
            return;
        }
        
        // Set submitting state
        isSubmitting = true;
        attemptCount++;
        const submitButton = loginForm.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.textContent;
        submitButton.disabled = true;
        submitButton.textContent = 'Вход...';
        
        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Success - redirect to dashboard
                window.location.href = '/api/dashboard';
            } else {
                showError(data.error || 'Неверные учетные данные');
                
                // Handle lockout
                if (attemptCount >= MAX_ATTEMPTS) {
                    submitButton.disabled = true;
                    submitButton.textContent = 'Подождите...';
                    
                    setTimeout(() => {
                        attemptCount = 0;
                        submitButton.disabled = false;
                        submitButton.textContent = originalButtonText;
                        
                        if (errorDiv.textContent.includes('Слишком много попыток')) {
                            errorDiv.style.display = 'none';
                        }
                    }, LOCKOUT_TIME * 1000);
                }
            }
        } catch (error) {
            console.error('Login error:', error);
            showError('Ошибка подключения к серверу');
        } finally {
            // Reset submitting state
            setTimeout(() => {
                isSubmitting = false;
                if (attemptCount < MAX_ATTEMPTS) {
                    submitButton.disabled = false;
                    submitButton.textContent = originalButtonText;
                }
            }, 1000);
        }
    });
    
    function showError(message) {
        const errorDiv = document.getElementById('error');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        errorDiv.setAttribute('aria-live', 'polite');
        errorDiv.setAttribute('role', 'alert');
        
        // Auto-hide after 10 seconds
        setTimeout(() => {
            if (!errorDiv.textContent.includes('Слишком много попыток')) {
                errorDiv.style.display = 'none';
            }
        }, 10000);
    }
    
    // Support for enter key
    document.getElementById('password').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !isSubmitting) {
            loginForm.requestSubmit();
        }
    });
});