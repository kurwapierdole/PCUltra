#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build script for PCUltra
Creates executable using PyInstaller
"""

import os
import sys
import shutil
from pathlib import Path

def build_executable():
    """Build executable using PyInstaller"""
    
    # Clean previous builds
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('PCUltra.spec'):
        os.remove('PCUltra.spec')
    
    # PyInstaller command
    cmd = [
        'pyinstaller',
        '--name=PCUltra',
        '--onefile',
        '--windowed',
        '--icon=NONE',  # Add icon file if available
        '--add-data=config.yaml;.',
        '--add-data=web;web',
        '--hidden-import=flask',
        '--hidden-import=flask_login',
        '--hidden-import=flask_cors',
        '--hidden-import=telegram',
        '--hidden-import=telegram.ext',
        '--hidden-import=playwright',
        '--hidden-import=pystray',
        '--hidden-import=PIL',
        '--hidden-import=yaml',
        '--hidden-import=bcrypt',
        '--hidden-import=psutil',
        '--hidden-import=pyautogui',
        '--hidden-import=pynput',
        '--hidden-import=mss',
        '--hidden-import=win10toast',
        'main.py'
    ]
    
    print("Building executable...")
    os.system(' '.join(cmd))
    
    print("\nBuild complete! Executable is in the 'dist' folder.")
    print("Note: Playwright browsers need to be installed separately.")
    print("Run: playwright install chromium")

if __name__ == '__main__':
    build_executable()
