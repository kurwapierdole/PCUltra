#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration manager for PCUltra
"""

import os
import yaml
import secrets
import bcrypt
from pathlib import Path
from threading import Lock


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_path="config.yaml"):
        self.config_path = Path(config_path)
        self.lock = Lock()
        self.config = None
        
    def initialize(self):
        """Initialize configuration file"""
        if not self.config_path.exists():
            self.create_default_config()
        self.load_config()
        
        # Generate secret key if not set
        if not self.config['web']['secret_key']:
            self.config['web']['secret_key'] = secrets.token_hex(32)
            self.save_config()
    
    def has_admin_account(self):
        """Check if admin account is set up"""
        config = self.get_config()
        username = config['web'].get('admin_username', '')
        password_hash = config['web'].get('admin_password_hash', '')
        return bool(username and password_hash)
    
    def create_default_config(self):
        """Create default configuration file"""
        default_config = {
            'bot': {
                'token': '',
                'authorized_users': [],
                'command_timeout': 30,
                'auto_start': False
            },
            'web': {
                'host': '127.0.0.1',
                'port': 5000,
                'secret_key': '',
                'admin_username': '',
                'admin_password_hash': ''
            },
            'shortcuts': {
                'vpn': {
                    'command': '/vpn',
                    'action': 'launch_app',
                    'path': 'C:\\Program Files\\AmneziaVPN\\client.exe',
                    'args': []
                }
            },
            'permissions': {}
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
    
    def load_config(self):
        """Load configuration from file"""
        with self.lock:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        return self.config
    
    def save_config(self):
        """Save configuration to file"""
        with self.lock:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
    
    def get_config(self):
        """Get current configuration"""
        if self.config is None:
            self.load_config()
        return self.config
    
    def update_config(self, updates):
        """Update configuration with provided values"""
        self.load_config()
        
        def deep_update(base_dict, update_dict):
            for key, value in update_dict.items():
                if isinstance(value, dict) and key in base_dict:
                    deep_update(base_dict[key], value)
                else:
                    base_dict[key] = value
        
        deep_update(self.config, updates)
        self.save_config()
    
    def is_user_authorized(self, user_id):
        """Check if user is authorized"""
        config = self.get_config()
        authorized_users = config['bot'].get('authorized_users', [])
        
        # Handle case when authorized_users is None or empty list
        if not authorized_users:
            return True  # No restrictions, allow all
        
        # Handle case when it's a list
        if isinstance(authorized_users, list):
            return user_id in authorized_users
        
        return False
    
    def has_permission(self, user_id, command):
        """Check if user has permission for specific command"""
        config = self.get_config()
        permissions = config.get('permissions', {})
        
        # Handle case when permissions is None (from YAML null)
        if permissions is None or not isinstance(permissions, dict):
            return True  # No restrictions, allow all
        
        # If no permissions set for user, allow all
        if str(user_id) not in permissions:
            return True
        
        user_permissions = permissions.get(str(user_id), [])
        # Empty list means all commands allowed
        if not user_permissions:
            return True
        
        return command in user_permissions
    
    def get_shortcut(self, command):
        """Get shortcut configuration by command"""
        config = self.get_config()
        shortcuts = config.get('shortcuts', {})
        
        # Handle case when shortcuts is None (from YAML null)
        if shortcuts is None or not isinstance(shortcuts, dict):
            return None
        
        for shortcut_name, shortcut_config in shortcuts.items():
            if shortcut_config and isinstance(shortcut_config, dict):
                if shortcut_config.get('command') == command:
                    return shortcut_config
        return None
