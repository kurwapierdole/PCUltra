#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows Service installation script for PCUltra
"""

import os
import sys
import win32serviceutil
import win32service
import servicemanager
import socket

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from main import SystemTrayApp


class PCUltraService(win32serviceutil.ServiceFramework):
    """Windows Service for PCUltra"""
    
    _svc_name_ = "PCUltra"
    _svc_display_name_ = "PCUltra Remote Control Service"
    _svc_description_ = "Telegram bot for remote PC control"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32service.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.app = None
    
    def SvcStop(self):
        """Stop service"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.app:
            self.app.quit_application(None, None)
        win32service.SetEvent(self.stop_event)
    
    def SvcDoRun(self):
        """Run service"""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()
    
    def main(self):
        """Main service loop"""
        try:
            self.app = SystemTrayApp()
            self.app.run()
        except Exception as e:
            servicemanager.LogErrorMsg(f"Service error: {e}")


def install_service():
    """Install Windows service"""
    script_path = os.path.abspath(__file__)
    win32serviceutil.HandleCommandLine(PCUltraService)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PCUltraService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(PCUltraService)
