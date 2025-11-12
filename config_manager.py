#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration manager for PCUltra
"""

import os
import yaml
import secrets
import bcrypt
import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


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
        
        # Ensure config has required structure
        if 'web' not in self.config:
            self.config['web'] = {}
        if 'bot' not in self.config:
            self.config['bot'] = {}
        if 'shortcuts' not in self.config:
            self.config['shortcuts'] = {}
        if 'permissions' not in self.config:
            self.config['permissions'] = {}
        if 'updates' not in self.config or not isinstance(self.config['updates'], dict):
            self.config['updates'] = {}
        
        updates_section = self.config['updates']
        updates_modified = False
        if 'enabled' not in updates_section:
            updates_section['enabled'] = True
            updates_modified = True
        if 'check_interval_minutes' not in updates_section:
            updates_section['check_interval_minutes'] = 2
            updates_modified = True
        if 'github_token' not in updates_section:
            updates_section['github_token'] = ''
            updates_modified = True
        
        if updates_modified:
            self.save_config()
        
        # Generate secret key if not set
        if not self.config['web'].get('secret_key'):
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
            'permissions': {},
            'updates': {
                'enabled': True,
                'check_interval_minutes': 2,
                'github_token': ''
            }
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
    
    def load_config(self):
        """Load configuration from file"""
        with self.lock:
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
                    if self.config is None:
                        self.config = {}
            except FileNotFoundError:
                logger.warning(f"Config file not found, creating default")
                self.create_default_config()
                self.load_config()
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                self.config = {}
        return self.config
    
    def save_config(self):
        """Save configuration to file"""
        with self.lock:
            try:
                logger.info(f"Saving config. Shortcuts to save: {list(self.config.get('shortcuts', {}).keys())}")
                
                # Create backup before saving
                if self.config_path.exists():
                    backup_path = self.config_path.with_suffix('.yaml.bak')
                    import shutil
                    shutil.copy2(self.config_path, backup_path)
                
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
                
                logger.info(f"Config saved to {self.config_path}")
            except Exception as e:
                logger.error(f"Error saving config: {e}")
                raise
    
    def get_config(self):
        """Get current configuration"""
        if self.config is None:
            self.load_config()
        return self.config
    
    def update_config(self, updates):
        """Update configuration with provided values"""
        # Always reload from file first to get latest state
        self.load_config()
        
        def deep_update(base_dict, update_dict):
            for key, value in update_dict.items():
                # Special handling for shortcuts - replace entirely, don't merge
                if key == 'shortcuts':
                    base_dict[key] = value
                elif isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                    # For other dicts, do deep merge
                    deep_update(base_dict[key], value)
                else:
                    base_dict[key] = value
        
        deep_update(self.config, updates)
        self.save_config()
        
        # Reload after save to ensure consistency
        self.load_config()
        
        # Log for debugging
        logger.info(f"Config updated. Current shortcuts: {list(self.config.get('shortcuts', {}).keys())}")
    
    def is_user_authorized(self, user_id):
        """Check if user is authorized"""
        config = self.get_config()
        # Ensure bot config exists
        if 'bot' not in config:
            config['bot'] = {}
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
        # Always reload to get fresh data from file
        self.config = None
        self.load_config()
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