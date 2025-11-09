#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCUltra - Windows Desktop Remote Control System
Main entry point with system tray integration
"""

import sys
import os
import threading
import time
import subprocess
import pystray
from PIL import Image, ImageDraw
from werkzeug.serving import make_server
import webbrowser

from bot_agent import BotAgent
from web_ui import create_app
from config_manager import ConfigManager
from admin_check import check_and_request_admin


class SystemTrayApp:
    """System tray application for PCUltra"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.bot_agent = None
        self.web_server = None
        self.web_thread = None
        self.icon = None
        self.running = False
        
    def create_icon(self):
        """Create system tray icon"""
        # Create a simple icon image
        image = Image.new('RGB', (64, 64), color='blue')
        draw = ImageDraw.Draw(image)
        draw.ellipse([16, 16, 48, 48], fill='white')
        return image
    
    def setup_icon(self):
        """Setup system tray icon menu"""
        menu = pystray.Menu(
            pystray.MenuItem("Открыть Web UI", self.open_web_ui),
            pystray.MenuItem("Статус бота", self.show_bot_status),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Запустить бота", self.start_bot, enabled=lambda item: not self.is_bot_running()),
            pystray.MenuItem("Остановить бота", self.stop_bot, enabled=lambda item: self.is_bot_running()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self.quit_application)
        )
        self.icon = pystray.Icon("PCUltra", self.create_icon(), "PCUltra", menu)
    
    def open_web_ui(self, icon=None, item=None):
        """Open web UI in default browser"""
        config = self.config_manager.get_config()
        # Ensure web config exists
        if 'web' not in config:
            config['web'] = {'host': '127.0.0.1', 'port': 5000}
        host = config['web'].get('host', '127.0.0.1')
        port = config['web'].get('port', 5000)
        url = f"http://{host}:{port}"
        # On Windows, use subprocess with 'start' command for reliable default browser opening
        if os.name == 'nt':
            subprocess.Popen(['start', url], shell=True)
        else:
            webbrowser.open(url)
    
    
    def show_bot_status(self, icon, item):
        """Show bot status notification"""
        status = "Работает" if self.is_bot_running() else "Остановлен"
        self.icon.notify(f"Статус бота: {status}", "PCUltra")
    
    def is_bot_running(self):
        """Check if bot is running"""
        return self.bot_agent is not None and self.bot_agent.is_running()
    
    def start_bot(self, icon, item):
        """Start Telegram bot"""
        if self.bot_agent is None:
            try:
                self.bot_agent = BotAgent(self.config_manager)
                self.bot_agent.start()
                self.icon.notify("Бот успешно запущен", "PCUltra")
            except Exception as e:
                self.icon.notify(f"Ошибка запуска бота: {str(e)}", "PCUltra")
        else:
            self.icon.notify("Бот уже работает", "PCUltra")
    
    def stop_bot(self, icon, item):
        """Stop Telegram bot"""
        if self.bot_agent is not None:
            try:
                self.bot_agent.stop()
                self.bot_agent = None
                self.icon.notify("Бот остановлен", "PCUltra")
            except Exception as e:
                self.icon.notify(f"Ошибка остановки бота: {str(e)}", "PCUltra")
    
    def start_web_server(self):
        """Start web UI server in separate thread"""
        app = create_app(self.config_manager, self)
        config = self.config_manager.get_config()
        # Ensure web config exists
        if 'web' not in config:
            config['web'] = {'host': '127.0.0.1', 'port': 5000}
        host = config['web'].get('host', '127.0.0.1')
        port = config['web'].get('port', 5000)
        self.web_server = make_server(
            host,
            port,
            app
        )
        self.web_thread = threading.Thread(target=self.web_server.serve_forever, daemon=True)
        self.web_thread.start()
        print(f"Web UI started at http://{host}:{port}")
    
    def quit_application(self, icon, item):
        """Quit application"""
        if self.bot_agent is not None:
            self.bot_agent.stop()
        if self.web_server is not None:
            self.web_server.shutdown()
        self.icon.stop()
        sys.exit(0)
    
    def run(self):
        """Run system tray application"""
        # Check and request admin privileges
        if not check_and_request_admin():
            return
        
        # Initialize configuration
        self.config_manager.initialize()
        
        # Start web server
        self.start_web_server()
        
        # Auto-start bot if enabled in config
        config = self.config_manager.get_config()
        # Ensure bot config exists
        if 'bot' not in config:
            config['bot'] = {}
        if config['bot'].get('auto_start', False) and config['bot'].get('token'):
            try:
                time.sleep(1)  # Wait a bit for web server to start
                self.bot_agent = BotAgent(self.config_manager)
                self.bot_agent.start()
                print("Bot auto-started (auto_start enabled in config)")
            except Exception as e:
                print(f"Failed to auto-start bot: {e}")
        
        # Setup and run system tray
        self.setup_icon()
        self.running = True
        
        # Open Web UI automatically on startup (in background thread)
        def open_ui_delayed():
            time.sleep(2)  # Wait for server to start
            self.open_web_ui()
        
        ui_thread = threading.Thread(target=open_ui_delayed, daemon=True)
        ui_thread.start()
        
        self.icon.run()


def main():
    """Main entry point"""
    app = SystemTrayApp()
    app.run()


if __name__ == "__main__":
    main()
