document.addEventListener('DOMContentLoaded', () => {
    const registerForm = document.getElementById('registerForm');
    if (!registerForm) return;
    
    let isSubmitting = false;
    
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (isSubmitting) return;
        
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm_password').value;
        const errorDiv = document.getElementById('error');
        
        // Clear previous errors
        errorDiv.style.display = 'none';
        errorDiv.textContent = '';
        
        // Client-side validation
        if (!username) {
            showError('Имя пользователя не может быть пустым');
            return;
        }
        
        if (username.length < 3) {
            showError('Имя пользователя должно содержать минимум 3 символа');
            return;
        }
        
        if (password.length < 6) {
            showError('Пароль должен содержать минимум 6 символов');
            return;
        }
        
        if (password !== confirmPassword) {
            showError('Пароли не совпадают');
            return;
        }
        
        // Set submitting state
        isSubmitting = true;
        const submitButton = registerForm.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.textContent;
        submitButton.disabled = true;
        submitButton.textContent = 'Регистрация...';
        
        try {
            const response = await fetch('/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ 
                    username, 
                    password, 
                    confirm_password: confirmPassword 
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Redirect to dashboard with success message
                window.location.href = '/api/dashboard';
            } else {
                showError(data.error || 'Ошибка регистрации');
            }
        } catch (error) {
            console.error('Registration error:', error);
            showError('Ошибка подключения к серверу');
        } finally {
            // Reset submitting state
            isSubmitting = false;
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText;
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
            errorDiv.style.display = 'none';
        }, 10000);
    }
    
    // Real-time validation
    document.getElementById('username').addEventListener('input', function() {
        if (this.value.length > 2) {
            this.setCustomValidity('');
        } else {
            this.setCustomValidity('Минимум 3 символа');
        }
    });
    
    document.getElementById('password').addEventListener('input', function() {
        if (this.value.length >= 6) {
            this.setCustomValidity('');
        } else {
            this.setCustomValidity('Минимум 6 символов');
        }
        
        // Check password match in real-time
        const confirmPasswordInput = document.getElementById('confirm_password');
        if (confirmPasswordInput.value) {
            validatePasswordMatch();
        }
    });
    
    document.getElementById('confirm_password').addEventListener('input', validatePasswordMatch);
    
    function validatePasswordMatch() {
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm_password').value;
        
        if (password !== confirmPassword) {
            document.getElementById('confirm_password').setCustomValidity('Пароли не совпадают');
        } else {
            document.getElementById('confirm_password').setCustomValidity('');
        }
    }
});