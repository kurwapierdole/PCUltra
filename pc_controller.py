#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PC Controller - System control functions (Media Only)
"""

import os
import subprocess
import time
import tempfile
from pathlib import Path
import pyautogui
import mss
from PIL import Image
import threading
from concurrent.futures import ThreadPoolExecutor
import asyncio
import logging
import webbrowser
import psutil

# --- ИМПОРТЫ ДЛЯ ЗВУКА УДАЛЕНЫ ---

# Настройка базового логгера
logger = logging.getLogger(__name__)

# Disable PyAutoGUI failsafe for remote control
pyautogui.FAILSAFE = False

# Browser process tracking for closing
_browser_processes = []
_browser_lock = threading.Lock()

def get_playwright_executor():
    """Get executor for async operations (kept for compatibility)"""
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="browser")


class PCController:
    """Controls PC functions"""
    
    def __init__(self):
        # Аудиоинтерфейс больше не кэшируется
        pass
    
    # --- ФУНКЦИИ _get_audio_endpoint и _ensure_audio_endpoint УДАЛЕНЫ ---

    
    
    def mouse_move(self, x, y):
        """Move mouse to absolute position"""
        pyautogui.moveTo(x, y, duration=0.1)
    
    def mouse_click(self, button="L"):
        """Click mouse button (L, R, M)"""
        button_map = {
            "L": pyautogui.LEFT,
            "R": pyautogui.RIGHT,
            "M": pyautogui.MIDDLE
        }
        pyautogui.click(button=button_map.get(button, pyautogui.LEFT))
    
    def mouse_drag(self, x1, y1, x2, y2, duration=0.5):
        """Drag mouse from (x1, y1) to (x2, y2)"""
        pyautogui.moveTo(x1, y1, duration=0.1)
        pyautogui.dragTo(x2, y2, duration=duration, button=pyautogui.LEFT)
    
    def scroll(self, amount):
        """Scroll mouse wheel"""
        pyautogui.scroll(amount)
    
    def keyboard_type(self, text):
        """Type text"""
        pyautogui.write(text, interval=0.05)
    
    def hotkey(self, keys_str):
        """Send hotkey combination"""
        keys = keys_str.split("+")
        key_list = []
        
        for key in keys:
            key = key.strip().lower()
            key_map = {
                "win": "win", "ctrl": "ctrl", "alt": "alt", "shift": "shift",
                "tab": "tab", "enter": "enter", "escape": "esc", "esc": "esc",
                "delete": "delete", "backspace": "backspace", "up": "up",
                "down": "down", "left": "left", "right": "right",
                "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
                "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
                "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
            }
            if key in key_map:
                key_list.append(key_map[key])
            elif len(key) == 1:
                key_list.append(key)
            else:
                key_list.append(key)
        pyautogui.hotkey(*key_list)
    
    def screenshot_full(self):
        """Take full screenshot"""
        screenshot_dir = Path(tempfile.gettempdir()) / "pcultra_screenshots"
        screenshot_dir.mkdir(exist_ok=True)
        filename = f"screenshot_{int(time.time())}.png"
        filepath = screenshot_dir / filename
        with mss.mss() as sct:
            sct.shot(output=str(filepath))
        return str(filepath)
    
    def screenshot_partial(self, x, y, width, height):
        """Take partial screenshot"""
        screenshot_dir = Path(tempfile.gettempdir()) / "pcultra_screenshots"
        screenshot_dir.mkdir(exist_ok=True)
        filename = f"screenshot_{int(time.time())}.png"
        filepath = screenshot_dir / filename
        with mss.mss() as sct:
            monitor = {"top": y, "left": x, "width": width, "height": height}
            sct.shot(mon=monitor, output=str(filepath))
        return str(filepath)
    
    def open_app(self, app_path, args=None):
        """Open application"""
        if args is None: args = []
        if not os.path.exists(app_path):
            raise FileNotFoundError(f"Application not found: {app_path}")
        subprocess.Popen([app_path] + args, shell=False)
    
    def open_folder(self, folder_path):
        """Open folder in Explorer"""
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        os.startfile(folder_path)
    
    def show_notification(self, title, message):
        """Show Windows toast notification"""
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
        except ImportError:
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, message, title, 1)
            except Exception as e:
                print(f"Notification error: {e}")
        except Exception as e:
            print(f"Notification error: {e}")
    
    
    def browser_open(self, url=None):
        """Open default system browser"""
        try:
            # Use yandex.ru as default URL to open browser
            target_url = url if url else 'https://yandex.ru'
            
            # Ensure URL has protocol
            if not target_url.startswith(('http://', 'https://')):
                target_url = 'https://' + target_url
            
            # On Windows, use subprocess with 'start' command which respects default browser
            # This is more reliable than webbrowser module or os.startfile for URLs
            if os.name == 'nt':  # Windows
                # Use subprocess to run 'start' command which opens URL in default browser
                subprocess.Popen(['start', target_url], shell=True)
            else:
                # For other OS, use webbrowser module
                browser = webbrowser.get()
                browser.open(target_url)
            
            # Track browser process for potential closing
            with _browser_lock:
                _browser_processes.append(time.time())
                # Keep only last 10 entries
                if len(_browser_processes) > 10:
                    _browser_processes.pop(0)
            
            return True
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")
            raise RuntimeError(f"Failed to open browser: {e}")
    
    def browser_navigate(self, url):
        """Navigate to URL in default system browser"""
        try:
            # Ensure URL has protocol (prefer https)
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # On Windows, use subprocess with 'start' command which respects default browser
            # This is more reliable than webbrowser module or os.startfile for URLs
            if os.name == 'nt':  # Windows
                # Use subprocess to run 'start' command which opens URL in default browser
                subprocess.Popen(['start', url], shell=True)
            else:
                # For other OS, use webbrowser module
                browser = webbrowser.get()
                browser.open(url)
            
            # Track browser process
            with _browser_lock:
                _browser_processes.append(time.time())
                if len(_browser_processes) > 10:
                    _browser_processes.pop(0)
            
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to URL: {e}")
            raise RuntimeError(f"Failed to navigate: {e}")
    
    def browser_close(self):
        """Close browser windows (closes all browser processes)"""
        try:
            # Common browser process names on Windows
            browser_names = [
                'chrome.exe',
                'msedge.exe',
                'firefox.exe',
                'opera.exe',
                'brave.exe',
                'vivaldi.exe',
                'iexplore.exe'
            ]
            
            closed_count = 0
            
            # Find and close all browser processes
            # Note: This closes ALL browser processes on the system
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name'].lower()
                    if any(browser in proc_name for browser in browser_names):
                        try:
                            # Try graceful termination first
                            proc.terminate()
                            # Wait up to 3 seconds for process to terminate
                            try:
                                proc.wait(timeout=3)
                            except psutil.TimeoutExpired:
                                # Force kill if terminate didn't work
                                proc.kill()
                                proc.wait(timeout=1)
                            closed_count += 1
                            logger.info(f"Closed browser process: {proc_name} (PID: {proc.info['pid']})")
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            logger.warning(f"Could not close process {proc_name} (PID: {proc.info['pid']}): {e}")
                        except psutil.TimeoutExpired:
                            logger.warning(f"Process {proc_name} (PID: {proc.info['pid']}) did not terminate in time")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            # Clear tracked processes
            with _browser_lock:
                _browser_processes.clear()
            
            if closed_count > 0:
                logger.info(f"Closed {closed_count} browser process(es)")
                return True
            else:
                logger.info("No browser processes found to close")
                return False
                
        except Exception as e:
            logger.error(f"Error closing browser: {e}", exc_info=True)
            return False
    
    def browser_click(self, selector):
        """Browser click not supported with system browser"""
        raise NotImplementedError("Browser click is not supported when using system browser. Use Playwright for advanced browser control.")
    
    def browser_execute_js(self, js_code):
        """Browser JS execution not supported with system browser"""
        raise NotImplementedError("Browser JS execution is not supported when using system browser. Use Playwright for advanced browser control.")

    # --- ФУНКЦИИ ГРОМКОСТИ УДАЛЕНЫ (get_volume, set_volume, volume_up/down, toggle_mute, is_muted) ---
    
    def media_play_pause(self):
        """Play/Pause media"""
        try:
            pyautogui.press('playpause')
        except Exception as e:
            logger.error(f"Media play/pause error: {e}")
    
    def media_next(self):
        """Next track"""
        try:
            pyautogui.press('nexttrack')
        except Exception as e:
            logger.error(f"Media next error: {e}")
    
    def media_previous(self):
        """Previous track"""
        try:
            pyautogui.press('prevtrack')
        except Exception as e:
            logger.error(f"Media previous error: {e}")
    
    def media_forward(self, seconds=10):
        """Forward media (simulate arrow key presses)"""
        try:
            pyautogui.press('right')
            time.sleep(0.1)
            pyautogui.press('right')
        except Exception as e:
            logger.error(f"Media forward error: {e}")
    
    def media_backward(self, seconds=10):
        """Backward media (simulate arrow key presses)"""
        try:
            pyautogui.press('left')
            time.sleep(0.1)
            pyautogui.press('left')
        except Exception as e:
            logger.error(f"Media backward error: {e}")