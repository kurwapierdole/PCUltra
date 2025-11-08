@echo off
echo PCUltra Setup Script
echo ====================

echo.
echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo Installing Playwright browsers...
playwright install chromium

echo.
echo Setup complete!
echo.
echo Next steps:
echo 1. Run: python main.py
echo 2. Open: http://127.0.0.1:5000
echo 3. Login with admin/admin and configure your bot token
echo.
pause
