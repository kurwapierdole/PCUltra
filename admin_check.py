#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility to check and request administrator privileges
"""

import sys
import ctypes
import os


def is_admin():
    """Check if the script is running with administrator privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def request_admin():
    """Request administrator privileges by restarting the script"""
    if is_admin():
        return True
    else:
        # Re-run the program with admin rights
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            return False  # Original process exits
        except:
            print("Failed to request administrator privileges")
            return False


def check_and_request_admin():
    """Check admin rights and request if needed"""
    if not is_admin():
        print("Требуются права администратора для работы приложения.")
        print("Запускается запрос прав администратора...")
        if request_admin():
            return True
        else:
            sys.exit(0)
    return True

