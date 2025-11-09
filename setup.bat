@echo off
echo PCUltra Setup Script
echo ====================

echo.
echo Installing playwright
pip install playwright

echo.
echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo Installing Playwright browsers...
playwright install chromium

echo.
echo Setup complete!
echo.
echo Start script
python main.py

echo Open: http://127.0.0.1:5000
echo Login with admin/admin and configure your bot token
echo.
pause
