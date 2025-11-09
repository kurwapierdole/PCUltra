#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web UI for PCUltra
"""

import os
import json
import logging
import yaml
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin
from flask_cors import CORS
import bcrypt
import psutil

from config_manager import ConfigManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class User(UserMixin):
    """User class for Flask-Login"""
    def __init__(self, id):
        self.id = id


def create_app(config_manager: ConfigManager, system_tray_app=None):
    """Create Flask application"""
    app = Flask(__name__, 
                template_folder='web/templates',
                static_folder='web/static')
    
    # Load configuration
    config = config_manager.get_config()
    app.config['SECRET_KEY'] = config['web']['secret_key']
    
    # Enable CORS
    CORS(app)
    
    # Setup Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User(user_id)
    
    @app.route('/')
    def index():
        """Redirect to dashboard if logged in, else to login/register"""
        if session.get('logged_in'):
            return redirect(url_for('dashboard'))
        
        # Check if admin account exists
        if config_manager.has_admin_account():
            return redirect(url_for('login'))
        else:
            return redirect(url_for('register'))
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """Registration page - shown only if no admin account exists"""
        # If admin account already exists, redirect to login
        if config_manager.has_admin_account():
            return redirect(url_for('login'))
        
        if request.method == 'POST':
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '')
            confirm_password = data.get('confirm_password', '')
            
            # Validation
            if not username:
                return jsonify({'success': False, 'error': 'Имя пользователя не может быть пустым'}), 400
            
            if len(password) < 6:
                return jsonify({'success': False, 'error': 'Пароль должен содержать минимум 6 символов'}), 400
            
            if password != confirm_password:
                return jsonify({'success': False, 'error': 'Пароли не совпадают'}), 400
            
            # Check if account already exists (race condition check)
            if config_manager.has_admin_account():
                return jsonify({'success': False, 'error': 'Администратор уже зарегистрирован'}), 400
            
            # Create admin account
            password_hash = bcrypt.hashpw(
                password.encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')
            
            config_manager.update_config({
                'web': {
                    'admin_username': username,
                    'admin_password_hash': password_hash
                }
            })
            
            # Auto-login after registration
            user = User(username)
            login_user(user)
            session['logged_in'] = True
            return jsonify({'success': True})
        
        return render_template('register.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Login page"""
        # If no admin account exists, redirect to registration
        if not config_manager.has_admin_account():
            return redirect(url_for('register'))
        
        if request.method == 'POST':
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            
            config = config_manager.get_config()
            admin_username = config['web'].get('admin_username', '')
            password_hash = config['web'].get('admin_password_hash', '')
            
            if username == admin_username and password_hash:
                if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                    user = User(username)
                    login_user(user)
                    session['logged_in'] = True
                    return jsonify({'success': True})
            
            return jsonify({'success': False, 'error': 'Неверные учетные данные'}), 401
        
        return render_template('login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        """Logout"""
        logout_user()
        session.pop('logged_in', None)
        return redirect(url_for('login'))
    
    @app.route('/api/dashboard')
    @login_required
    def dashboard():
        """Dashboard page"""
        return render_template('dashboard.html')
    
    @app.route('/api/status')
    @login_required
    def api_status():
        """Get bot and system status"""
        bot_running = False
        if system_tray_app and system_tray_app.bot_agent:
            bot_running = system_tray_app.bot_agent.is_running()
        
        # System resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        return jsonify({
            'bot': {
                'running': bot_running
            },
            'system': {
                'cpu': cpu_percent,
                'memory': {
                    'used': memory.used,
                    'total': memory.total,
                    'percent': memory.percent
                }
            }
        })
    
    @app.route('/api/config')
    @login_required
    def api_get_config():
        """Get configuration"""
        config = config_manager.get_config()
        # Don't send password hash to frontend
        safe_config = config.copy()
        safe_config['web']['admin_password_hash'] = '***'
        return jsonify(safe_config)
    
    @app.route('/api/config', methods=['POST'])
    @login_required
    def api_update_config():
        """Update configuration"""
        data = request.get_json()
        
        try:
            # Handle password update
            if 'web' in data and 'admin_password' in data['web']:
                password = data['web']['admin_password']
                if password:
                    password_hash = bcrypt.hashpw(
                        password.encode('utf-8'),
                        bcrypt.gensalt()
                    ).decode('utf-8')
                    data['web']['admin_password_hash'] = password_hash
                del data['web']['admin_password']
            
            config_manager.update_config(data)
            
            # Auto-restart bot if running and bot config changed
            if system_tray_app and system_tray_app.bot_agent and system_tray_app.bot_agent.is_running():
                if 'bot' in data:
                    # Stop bot properly
                    system_tray_app.bot_agent.stop()
                    import time
                    time.sleep(2)  # Wait for bot to stop
                    system_tray_app.bot_agent = None
                    # Restart bot
                    from bot_agent import BotAgent
                    system_tray_app.bot_agent = BotAgent(config_manager)
                    system_tray_app.bot_agent.start()
            
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Config update error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bot/start', methods=['POST'])
    @login_required
    def api_bot_start():
        """Start bot"""
        if system_tray_app:
            try:
                if system_tray_app.bot_agent is None:
                    from bot_agent import BotAgent
                    system_tray_app.bot_agent = BotAgent(config_manager)
                    system_tray_app.bot_agent.start()
                    return jsonify({'success': True})
                else:
                    return jsonify({'success': False, 'error': 'Bot is already running'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        return jsonify({'success': False, 'error': 'System tray app not available'}), 500
    
    @app.route('/api/bot/stop', methods=['POST'])
    @login_required
    def api_bot_stop():
        """Stop bot"""
        if system_tray_app:
            try:
                if system_tray_app.bot_agent:
                    system_tray_app.bot_agent.stop()
                    system_tray_app.bot_agent = None
                    return jsonify({'success': True})
                else:
                    return jsonify({'success': False, 'error': 'Bot is not running'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        return jsonify({'success': False, 'error': 'System tray app not available'}), 500
    
    @app.route('/api/bot/restart', methods=['POST'])
    @login_required
    def api_bot_restart():
        """Restart bot"""
        if system_tray_app:
            try:
                # Stop bot properly
                if system_tray_app.bot_agent:
                    system_tray_app.bot_agent.stop()
                    # Wait for bot to stop completely
                    import time
                    time.sleep(3)
                    system_tray_app.bot_agent = None
                
                # Start bot
                from bot_agent import BotAgent
                system_tray_app.bot_agent = BotAgent(config_manager)
                system_tray_app.bot_agent.start()
                
                return jsonify({'success': True})
            except Exception as e:
                logger.error(f"Bot restart error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        return jsonify({'success': False, 'error': 'System tray app not available'}), 500
    
    @app.route('/api/shortcuts')
    @login_required
    def api_get_shortcuts():
        """Get shortcuts"""
        # Reload config to get fresh data
        config_manager.load_config()
        config = config_manager.get_config()
        shortcuts = config.get('shortcuts', {})
        # Ensure shortcuts is a dict
        if shortcuts is None:
            shortcuts = {}
        return jsonify(shortcuts)
    
    @app.route('/api/shortcuts', methods=['POST'])
    @login_required
    def api_add_shortcut():
        """Add shortcut"""
        data = request.get_json()
        
        try:
            # Validate input
            command = data.get('command', '').strip()
            if not command:
                return jsonify({'success': False, 'error': 'Command is required'}), 400
            
            action = data.get('action', '').strip()
            if action not in ['launch_app', 'open_url', 'execute_script']:
                return jsonify({'success': False, 'error': 'Invalid action'}), 400
            
            path = data.get('path', '').strip()
            if not path:
                return jsonify({'success': False, 'error': 'Path is required'}), 400
            
            # Remove leading slash if present
            shortcut_id = command.lstrip('/')
            
            # Parse args from string to list
            args = data.get('args', '')
            if isinstance(args, str):
                args = [arg.strip() for arg in args.split(',') if arg.strip()]
            
            # Read current config with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with config_manager.lock:
                        with open(config_manager.config_path, 'r', encoding='utf-8') as f:
                            file_config = yaml.safe_load(f)
                        
                        if file_config is None:
                            file_config = {}
                        
                        shortcuts = file_config.get('shortcuts', {})
                        if shortcuts is None:
                            shortcuts = {}
                        
                        # Add new shortcut
                        shortcuts[shortcut_id] = {
                            'command': command,
                            'display_name': data.get('display_name', command),
                            'action': action,
                            'path': path,
                            'args': args
                        }
                        
                        # Update config
                        file_config['shortcuts'] = shortcuts
                        
                        # Write back to file
                        with open(config_manager.config_path, 'w', encoding='utf-8') as f:
                            yaml.dump(file_config, f, default_flow_style=False, allow_unicode=True)
                        
                        # Force reload in memory
                        config_manager.config = None
                        config_manager.load_config()
                    
                    logger.info(f"Successfully added shortcut: {shortcut_id}")
                    return jsonify({'success': True, 'id': shortcut_id})
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Retry {attempt + 1}/{max_retries} for add shortcut: {e}")
                        time.sleep(0.5)
                    else:
                        raise
            
        except Exception as e:
            logger.error(f"Add shortcut error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/shortcuts/<shortcut_id>', methods=['DELETE'])
    @login_required
    def api_delete_shortcut(shortcut_id):
        """Delete shortcut"""
        try:
            logger.info(f"DELETE request for shortcut: {shortcut_id}")
            
            # Direct file manipulation with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with config_manager.lock:
                        # Read current config from file
                        with open(config_manager.config_path, 'r', encoding='utf-8') as f:
                            file_config = yaml.safe_load(f)
                        
                        if file_config is None:
                            file_config = {}
                        
                        shortcuts = file_config.get('shortcuts', {})
                        if shortcuts is None:
                            shortcuts = {}
                        
                        logger.info(f"Shortcuts before deletion: {list(shortcuts.keys())}")
                        
                        if shortcut_id in shortcuts:
                            # Delete from dict
                            del shortcuts[shortcut_id]
                            logger.info(f"Shortcuts after deletion: {list(shortcuts.keys())}")
                            
                            # Update file config
                            file_config['shortcuts'] = shortcuts
                            
                            # Write back to file
                            with open(config_manager.config_path, 'w', encoding='utf-8') as f:
                                yaml.dump(file_config, f, default_flow_style=False, allow_unicode=True)
                            
                            # Force reload in memory
                            config_manager.config = None
                            config_manager.load_config()
                            
                            logger.info(f"Successfully deleted shortcut: {shortcut_id}")
                            
                            # Verify deletion
                            verify_config = config_manager.get_config()
                            verify_shortcuts = verify_config.get('shortcuts', {})
                            logger.info(f"Verification - shortcuts in memory: {list(verify_shortcuts.keys() if verify_shortcuts else [])}")
                            
                            return jsonify({'success': True, 'reload': True})
                        else:
                            logger.warning(f"Shortcut not found: {shortcut_id}")
                            return jsonify({'success': False, 'error': f'Shortcut "{shortcut_id}" not found'}), 404
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Retry {attempt + 1}/{max_retries} for delete shortcut: {e}")
                        time.sleep(0.5)
                    else:
                        raise
                        
        except Exception as e:
            logger.error(f"Delete shortcut error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/users')
    @login_required
    def api_get_users():
        """Get authorized users"""
        config = config_manager.get_config()
        return jsonify(config.get('bot', {}).get('authorized_users', []))
    
    @app.route('/api/users', methods=['POST'])
    @login_required
    def api_add_user():
        """Add authorized user"""
        data = request.get_json()
        user_id = data.get('user_id')
        
        try:
            user_id = int(user_id)
            config = config_manager.get_config()
            authorized_users = config['bot'].get('authorized_users', [])
            
            if user_id not in authorized_users:
                authorized_users.append(user_id)
                config_manager.update_config({'bot': {'authorized_users': authorized_users}})
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'User already authorized'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/users/<user_id>', methods=['DELETE'])
    @login_required
    def api_delete_user(user_id):
        """Remove authorized user"""
        try:
            user_id = int(user_id)
            config = config_manager.get_config()
            authorized_users = config['bot'].get('authorized_users', [])
            
            if user_id in authorized_users:
                authorized_users.remove(user_id)
                config_manager.update_config({'bot': {'authorized_users': authorized_users}})
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'User not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return app