#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PC Controller - System control functions
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

# Disable PyAutoGUI failsafe for remote control
pyautogui.FAILSAFE = False

# Global Playwright state (thread-safe)
_playwright_state = {
    'playwright': None,
    'browser': None,
    'context': None,
    'page': None,
    'lock': threading.Lock()
}

# Thread pool for Playwright operations (single worker to ensure same thread)
_playwright_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

def get_playwright_executor():
    """Get Playwright executor for use in async context"""
    return _playwright_executor


class PCController:
    """Controls PC functions"""
    
    def __init__(self):
        pass
    
    def _run_in_playwright_thread(self, func):
        """Run function in Playwright thread using executor"""
        # Always use executor to ensure Playwright runs in same thread
        # This prevents greenlet switching issues
        future = _playwright_executor.submit(func)
        return future.result(timeout=30)
    
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
        # Parse hotkey string like "Win+D" or "Ctrl+C"
        keys = keys_str.split("+")
        key_list = []
        
        for key in keys:
            key = key.strip().lower()
            key_map = {
                "win": "win",
                "ctrl": "ctrl",
                "alt": "alt",
                "shift": "shift",
                "tab": "tab",
                "enter": "enter",
                "escape": "esc",
                "esc": "esc",
                "delete": "delete",
                "backspace": "backspace",
                "up": "up",
                "down": "down",
                "left": "left",
                "right": "right",
                "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
                "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
                "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
            }
            
            if key in key_map:
                key_list.append(key_map[key])
            elif len(key) == 1:
                key_list.append(key)
            else:
                # Try to map common keys
                if key == "d":
                    key_list.append("d")
                elif key == "c":
                    key_list.append("c")
                elif key == "v":
                    key_list.append("v")
                elif key == "x":
                    key_list.append("x")
                elif key == "a":
                    key_list.append("a")
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
            monitor = {
                "top": y,
                "left": x,
                "width": width,
                "height": height
            }
            sct.shot(mon=monitor, output=str(filepath))
        
        return str(filepath)
    
    def open_app(self, app_path, args=None):
        """Open application"""
        if args is None:
            args = []
        
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
            # Use Windows 10/11 toast notification
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
        except ImportError:
            try:
                # Fallback to simple message box
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, message, title, 1)
            except Exception as e:
                print(f"Notification error: {e}")
        except Exception as e:
            print(f"Notification error: {e}")
    
    def _browser_open_sync(self):
        """Open browser with Playwright (sync, must be called in Playwright thread)"""
        from playwright.sync_api import sync_playwright
        
        with _playwright_state['lock']:
            # Close existing browser if any
            if _playwright_state['page']:
                try:
                    _playwright_state['page'].close()
                except:
                    pass
            if _playwright_state['context']:
                try:
                    _playwright_state['context'].close()
                except:
                    pass
            if _playwright_state['browser']:
                try:
                    _playwright_state['browser'].close()
                except:
                    pass
            if _playwright_state['playwright']:
                try:
                    _playwright_state['playwright'].stop()
                except:
                    pass
            
            # Initialize new browser
            _playwright_state['playwright'] = sync_playwright().start()
            _playwright_state['browser'] = _playwright_state['playwright'].chromium.launch(headless=False)
            _playwright_state['context'] = _playwright_state['browser'].new_context()
            _playwright_state['page'] = _playwright_state['context'].new_page()
        
        return True
    
    def browser_open(self):
        """Open browser with Playwright (runs in separate thread)"""
        try:
            return self._run_in_playwright_thread(self._browser_open_sync)
        except Exception as e:
            raise RuntimeError(f"Failed to open browser: {e}")
    
    def _browser_navigate_sync(self, url):
        """Navigate browser to URL (sync, must be called in Playwright thread)"""
        with _playwright_state['lock']:
            # Auto-open browser if not open
            if not _playwright_state['page'] or not _playwright_state['playwright']:
                # Close any existing browser first
                if _playwright_state['page']:
                    try:
                        _playwright_state['page'].close()
                    except:
                        pass
                if _playwright_state['context']:
                    try:
                        _playwright_state['context'].close()
                    except:
                        pass
                if _playwright_state['browser']:
                    try:
                        _playwright_state['browser'].close()
                    except:
                        pass
                if _playwright_state['playwright']:
                    try:
                        _playwright_state['playwright'].stop()
                    except:
                        pass
                
                # Open new browser
                from playwright.sync_api import sync_playwright
                _playwright_state['playwright'] = sync_playwright().start()
                _playwright_state['browser'] = _playwright_state['playwright'].chromium.launch(headless=False)
                _playwright_state['context'] = _playwright_state['browser'].new_context()
                _playwright_state['page'] = _playwright_state['context'].new_page()
            
            _playwright_state['page'].goto(url, wait_until='domcontentloaded', timeout=30000)
        return True
    
    def browser_navigate(self, url):
        """Navigate browser to URL (runs in separate thread)"""
        try:
            return self._run_in_playwright_thread(self._browser_navigate_sync, url)
        except Exception as e:
            raise RuntimeError(f"Failed to navigate: {e}")
    
    def _browser_click_sync(self, selector):
        """Click element in browser (sync, must be called in Playwright thread)"""
        with _playwright_state['lock']:
            if not _playwright_state['page']:
                raise RuntimeError("Browser not open")
            
            _playwright_state['page'].click(selector)
        return True
    
    def browser_click(self, selector):
        """Click element in browser (runs in separate thread)"""
        try:
            return self._run_in_playwright_thread(self._browser_click_sync, selector)
        except Exception as e:
            raise RuntimeError(f"Failed to click: {e}")
    
    def _browser_execute_js_sync(self, js_code):
        """Execute JavaScript in browser (sync, must be called in Playwright thread)"""
        with _playwright_state['lock']:
            if not _playwright_state['page']:
                raise RuntimeError("Browser not open")
            
            return _playwright_state['page'].evaluate(js_code)
    
    def browser_execute_js(self, js_code):
        """Execute JavaScript in browser (runs in separate thread)"""
        try:
            return self._run_in_playwright_thread(self._browser_execute_js_sync, js_code)
        except Exception as e:
            raise RuntimeError(f"Failed to execute JS: {e}")
    
    def _browser_close_sync(self):
        """Close browser (sync, must be called in Playwright thread)"""
        with _playwright_state['lock']:
            if _playwright_state['page']:
                try:
                    _playwright_state['page'].close()
                    _playwright_state['page'] = None
                except:
                    pass
            
            if _playwright_state['context']:
                try:
                    _playwright_state['context'].close()
                    _playwright_state['context'] = None
                except:
                    pass
            
            if _playwright_state['browser']:
                try:
                    _playwright_state['browser'].close()
                    _playwright_state['browser'] = None
                except:
                    pass
            
            if _playwright_state['playwright']:
                try:
                    _playwright_state['playwright'].stop()
                    _playwright_state['playwright'] = None
                except:
                    pass
        
        return True
    
    def browser_close(self):
        """Close browser (runs in separate thread)"""
        try:
            return self._run_in_playwright_thread(self._browser_close_sync)
        except Exception as e:
            print(f"Error closing browser: {e}")
