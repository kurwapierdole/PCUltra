#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot Agent for PCUltra with Inline Keyboard menus and ConversationHandler
"""
import asyncio
import logging
import pyautogui
import os
import psutil
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler
)
import threading
import time
from pc_controller import PCController, get_playwright_executor
from config_manager import ConfigManager
import shlex # Добавлен импорт для разбора аргументов

# --- КОНФИГУРАЦИЯ ЛОГГИРОВАНИЯ ---
# Настраиваем логирование здесь, в главном файле
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
# ---------------------------------


# Conversation states
WAITING_TEXT, WAITING_FOLDER, WAITING_NOTIFY, WAITING_URL = range(4)

class BotAgent:
    """Telegram bot agent for remote PC control"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.application = None
        self.controller = PCController()
        self.running = False
        self.event_loop = None
        self.thread = None
        self.mouse_step = 50  # Pixels to move mouse per button press
    
    def is_running(self):
        """Check if bot is running"""
        return self.running
    
    def start(self):
        """Start bot in separate thread"""
        if self.running:
            logger.warning("Bot is already running")
            return
            
        config = self.config_manager.get_config()
        token = config['bot']['token']
        if not token:
            raise ValueError("Telegram bot token not configured")
            
        self.thread = threading.Thread(target=self._run_bot, daemon=True)
        self.thread.start()
        self.running = True
    
    def stop(self):
        """Stop bot properly"""
        if not self.running:
            return
            
        logger.info("Stopping bot...")
        self.running = False
        
        if self.application and self.event_loop:
            try:
                # Stop polling
                future = asyncio.run_coroutine_threadsafe(
                    self.application.stop(),
                    self.event_loop
                )
                future.result(timeout=5)
                
                # Shutdown application
                future = asyncio.run_coroutine_threadsafe(
                    self.application.shutdown(),
                    self.event_loop
                )
                future.result(timeout=5)
            except Exception as e:
                logger.error(f"Error stopping bot: {e}")
                
        if self.thread:
            self.thread.join(timeout=10)
            
        logger.info("Bot stopped")
    
    def _run_bot(self):
        """Run bot in event loop"""
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        
        config = self.config_manager.get_config()
        token = config['bot']['token']
        
        # Create application
        self.application = Application.builder().token(token).build()
        
        # Register handlers
        self._register_handlers()
        
        # Start bot
        logger.info("Starting Telegram bot...")
        try:
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                stop_signals=None,
                drop_pending_updates=True
            )
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
        finally:
            self.running = False
            logger.info("Bot polling stopped")
    
    def _register_handlers(self):
        """Register command handlers"""
        
        # Conversation handler for text input
        text_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self._start_text_input, pattern="^keyboard_input$")],
            states={
                WAITING_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text_input),
                    CommandHandler("done", self._cancel_input)
                ],
            },
            fallbacks=[CommandHandler("done", self._cancel_input)],
        )
        
        # Conversation handler for folder navigation
        folder_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self._start_folder_input, pattern="^system_open_folder$")],
            states={
                WAITING_FOLDER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_folder_input),
                    CallbackQueryHandler(self._handle_folder_callback),
                    CommandHandler("done", self._cancel_input)
                ],
            },
            fallbacks=[CommandHandler("done", self._cancel_input)],
        )
        
        # Conversation handler for notification
        notify_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self._start_notify_input, pattern="^system_notify$")],
            states={
                WAITING_NOTIFY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_notify_input),
                    CommandHandler("done", self._cancel_input)
                ],
            },
            fallbacks=[CommandHandler("done", self._cancel_input)],
        )
        
        # Conversation handler for browser URL
        url_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self._start_url_input, pattern="^browser_navigate$")],
            states={
                WAITING_URL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_url_input),
                    CommandHandler("done", self._cancel_input)
                ],
            },
            fallbacks=[CommandHandler("done", self._cancel_input)],
        )
        
        # Basic commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        self.application.add_handler(CommandHandler("done", self._cancel_input))
        
        # Conversation handlers (must be added before callback handler)
        self.application.add_handler(text_conv_handler)
        self.application.add_handler(folder_conv_handler)
        self.application.add_handler(notify_conv_handler)
        self.application.add_handler(url_conv_handler)
        
        # Callback query handler for inline buttons (must be last)
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    def _get_main_menu(self):
        """Create main menu keyboard"""
        keyboard = [
            [InlineKeyboardButton("🖱️ Управление мышью", callback_data="menu_mouse")],
            [InlineKeyboardButton("⌨️ Клавиатура", callback_data="menu_keyboard")],
            [InlineKeyboardButton("🎵 Медиа", callback_data="menu_media")], # ИЗМЕНЕНО: Аудио -> Медиа
            [InlineKeyboardButton("📸 Скриншот", callback_data="action_screenshot")],
            [InlineKeyboardButton("💻 Система", callback_data="menu_system")],
            [InlineKeyboardButton("🌐 Браузер", callback_data="menu_browser")],
            [InlineKeyboardButton("⚡ Shortcuts", callback_data="menu_shortcuts")],
            [InlineKeyboardButton("📊 Статус", callback_data="action_status")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_mouse_menu(self):
        """Create mouse control menu"""
        keyboard = [
            [
                InlineKeyboardButton("⬆️", callback_data="mouse_up"),
                InlineKeyboardButton("↕️", callback_data="mouse_center") # Center
            ],
            [
                InlineKeyboardButton("⬅️", callback_data="mouse_left"),
                InlineKeyboardButton("🖱️", callback_data="mouse_click_l"),
                InlineKeyboardButton("➡️", callback_data="mouse_right")
            ],
            [
                InlineKeyboardButton("⬇️", callback_data="mouse_down"),
                InlineKeyboardButton("🔄", callback_data="mouse_reset") # Reset (same as center)
            ],
            [
                InlineKeyboardButton("🖱️ ЛКМ", callback_data="mouse_click_l"),
                InlineKeyboardButton("🖱️ ПКМ", callback_data="mouse_click_r"),
                InlineKeyboardButton("🖱️ СКМ", callback_data="mouse_click_m")
            ],
            [
                InlineKeyboardButton("📜 Вверх", callback_data="mouse_scroll_up"),
                InlineKeyboardButton("📜 Вниз", callback_data="mouse_scroll_down")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_keyboard_menu(self):
        """Create keyboard control menu"""
        keyboard = [
            [
                InlineKeyboardButton("Win+D", callback_data="hotkey_win_d"),
                InlineKeyboardButton("Win+R", callback_data="hotkey_win_r")
            ],
            [
                InlineKeyboardButton("Ctrl+C", callback_data="hotkey_ctrl_c"),
                InlineKeyboardButton("Ctrl+V", callback_data="hotkey_ctrl_v"),
                InlineKeyboardButton("Ctrl+X", callback_data="hotkey_ctrl_x")
            ],
            [
                InlineKeyboardButton("Ctrl+A", callback_data="hotkey_ctrl_a"),
                InlineKeyboardButton("Ctrl+Z", callback_data="hotkey_ctrl_z"),
                InlineKeyboardButton("Ctrl+Y", callback_data="hotkey_ctrl_y")
            ],
            [
                InlineKeyboardButton("Alt+Tab", callback_data="hotkey_alt_tab"),
                InlineKeyboardButton("Esc", callback_data="hotkey_esc")
            ],
            [InlineKeyboardButton("⌨️ Ввести текст", callback_data="keyboard_input")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_media_menu(self): # ИЗМЕНЕНО: _get_audio_menu -> _get_media_menu
        """Create media control menu (formerly audio)"""
        
        keyboard = [
            # КНОПКИ ГРОМКОСТИ УДАЛЕНЫ
            [
                InlineKeyboardButton("⏮️ Пред", callback_data="audio_prev"),
                InlineKeyboardButton("⏯️ Пауза", callback_data="audio_playpause"),
                InlineKeyboardButton("⏭️ След", callback_data="audio_next")
            ],
            [
                InlineKeyboardButton("⏪ -10с", callback_data="audio_backward"),
                InlineKeyboardButton("⏩ +10с", callback_data="audio_forward")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_system_menu(self):
        """Create system control menu"""
        keyboard = [
            [InlineKeyboardButton("📁 Открыть папку", callback_data="system_open_folder")],
            [InlineKeyboardButton("🔔 Уведомление", callback_data="system_notify")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _get_browser_menu(self):
        """Create browser control menu"""
        keyboard = [
            [InlineKeyboardButton("🌐 Открыть браузер", callback_data="browser_open")],
            [InlineKeyboardButton("🔗 Перейти на URL", callback_data="browser_navigate")],
            [InlineKeyboardButton("❌ Закрыть браузер", callback_data="browser_close")], # Добавлена кнопка
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def _get_shortcuts_menu(self):
        """Create shortcuts menu"""
        keyboard = []
        # Force reload config to get fresh shortcuts
        self.config_manager.config = None
        self.config_manager.load_config()
        config = self.config_manager.get_config()
        
        shortcuts = config.get('shortcuts', {})
        
        if shortcuts and isinstance(shortcuts, dict):
            for shortcut_id, shortcut in shortcuts.items():
                if shortcut and isinstance(shortcut, dict):
                    # Use display_name if available, otherwise command
                    display_name = shortcut.get('display_name', shortcut.get('command', ''))
                    if display_name:
                        keyboard.append([InlineKeyboardButton(
                            f"⚡ {display_name}",
                            callback_data=f"shortcut_{shortcut_id}"
                        )])
                        
        if not keyboard:
            keyboard.append([InlineKeyboardButton("(нет shortcuts)", callback_data="noop")])
            
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_main")])
        return InlineKeyboardMarkup(keyboard)

    def _get_folder_keyboard(self, current_path):
        """Create folder navigation keyboard"""
        keyboard = []
        try:
            if not current_path or current_path == "":
                # Show drives
                import string
                drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
                for i in range(0, len(drives), 2):
                    row = []
                    row.append(InlineKeyboardButton(drives[i], callback_data=f"folder_{drives[i]}"))
                    if i + 1 < len(drives):
                        row.append(InlineKeyboardButton(drives[i + 1], callback_data=f"folder_{drives[i + 1]}"))
                    keyboard.append(row)
                
                # Add special folders
                special_folders = [
                    ("🏠 Рабочий стол", os.path.join(os.path.expanduser("~"), "Desktop")),
                    ("📁 Документы", os.path.join(os.path.expanduser("~"), "Documents")),
                    ("📥 Загрузки", os.path.join(os.path.expanduser("~"), "Downloads")),
                ]
                for name, path in special_folders:
                    if os.path.exists(path):
                        keyboard.append([InlineKeyboardButton(name, callback_data=f"folder_{path}")])
                
                # Add action buttons for root
                keyboard.append([InlineKeyboardButton("➕ Создать папку", callback_data=f"create_folder_{os.path.expanduser('~')}")])
                
            else:
                # Get parent directory button
                parent = os.path.dirname(current_path)
                if parent and parent != current_path:
                    keyboard.append([InlineKeyboardButton("⬆️ Назад", callback_data=f"folder_{parent}")])
                elif not parent or parent == current_path.rstrip('\\'):
                     keyboard.append([InlineKeyboardButton("⬆️ К дискам", callback_data="folder_")])

                # List folders in current directory
                try:
                    items = sorted(os.listdir(current_path))
                    folders = [item for item in items if os.path.isdir(os.path.join(current_path, item))]
                    
                    for folder in folders[:10]:  # Limit to 10 folders
                        folder_path = os.path.join(current_path, folder)
                        # Truncate long folder names
                        display_name = folder[:30] + "..." if len(folder) > 30 else folder
                        keyboard.append([InlineKeyboardButton(f"📁 {display_name}", callback_data=f"folder_{folder_path}")])
                        
                    if len(folders) > 10:
                        keyboard.append([InlineKeyboardButton("... (еще папки)", callback_data="noop")])
                        
                except PermissionError:
                    keyboard.append([InlineKeyboardButton("❌ Нет доступа к папке", callback_data="noop")])
                except Exception as e:
                    keyboard.append([InlineKeyboardButton(f"❌ Ошибка: {str(e)[:30]}", callback_data="noop")])
                    
                # Add action buttons
                keyboard.append([InlineKeyboardButton("✅ Открыть эту папку", callback_data=f"open_{current_path}")])
                keyboard.append([InlineKeyboardButton("➕ Создать папку", callback_data=f"create_folder_{current_path}")])
                
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_folder")])
            
        except Exception as e:
            logger.error(f"Error creating folder keyboard: {e}")
            keyboard.append([InlineKeyboardButton("❌ Ошибка", callback_data="noop")])
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_folder")])
            
        return InlineKeyboardMarkup(keyboard)

    async def _check_authorization(self, update: Update) -> bool:
        """Check if user is authorized"""
        user_id = update.effective_user.id
        if not self.config_manager.is_user_authorized(user_id):
            text = "❌ Доступ запрещен. Ваш ID не в whitelist."
            if update.callback_query:
                await update.callback_query.answer(text, show_alert=True)
            elif update.message:
                await update.message.reply_text(text)
            return False
        return True

    async def _check_permission(self, update: Update, command: str) -> bool:
        """Check if user has permission for command"""
        user_id = update.effective_user.id
        if not self.config_manager.has_permission(user_id, command):
            text = f"❌ Нет доступа к команде: {command}"
            if update.callback_query:
                await update.callback_query.answer(text, show_alert=True)
            elif update.message:
                await update.message.reply_text(text)
            return False
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not await self._check_authorization(update):
            return
            
        text = (
            "🤖 PCUltra Bot Active\n"
            "Добро пожаловать! Используйте кнопки ниже для управления ПК.\n"
            "Используйте /menu для открытия главного меню."
        )
        await update.message.reply_text(text, reply_markup=self._get_main_menu())

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command"""
        if not await self._check_authorization(update):
            return
            
        text = "📱 Главное меню PCUltra"
        await update.message.reply_text(text, reply_markup=self._get_main_menu())

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not await self._check_authorization(update):
            return
            
        help_text = (
            "🤖 PCUltra Bot - Справка\n"
            "Используйте /menu для открытия главного меню.\n"
            "Основные функции:\n"
            "🖱️ Управление мышью - движение, клики, прокрутка\n"
            "⌨️ Клавиатура - горячие клавиши и ввод текста\n"
            "🎵 Медиа - управление воспроизведением (Play/Pause, Next, Prev)\n" # ИЗМЕНЕНО: Справка обновлена
            "📸 Скриншот - снимок экрана\n"
            "💻 Система - управление системой\n"
            "🌐 Браузер - управление браузером\n"
            "⚡ Shortcuts - быстрые команды\n"
            "Используйте /done для отмены текущей операции."
        )
        await update.message.reply_text(help_text, reply_markup=self._get_main_menu())

    # Conversation handlers
    async def _start_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start text input conversation"""
        query = update.callback_query
        await query.answer()
        
        if not await self._check_authorization(update):
            return ConversationHandler.END
        if not await self._check_permission(update, "keyboard"):
            return ConversationHandler.END
            
        await query.edit_message_text("⌨️ Введите текст для ввода:\nДля отмены: /done")
        return WAITING_TEXT

    async def _handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input"""
        text = update.message.text
        try:
            self.controller.keyboard_type(text)
            await update.message.reply_text(f"✅ Введен текст: {text[:50]}{'...' if len(text) > 50 else ''}", reply_markup=self._get_main_menu())
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=self._get_main_menu())
            
        return ConversationHandler.END

    async def _start_folder_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start folder navigation conversation"""
        query = update.callback_query
        await query.answer()
        
        if not await self._check_authorization(update):
            return ConversationHandler.END
        if not await self._check_permission(update, "system"):
            return ConversationHandler.END
            
        current_path = ""
        await query.edit_message_text(
            "📁 Навигация по папкам\nВыберите папку:",
            reply_markup=self._get_folder_keyboard(current_path)
        )
        context.user_data['current_folder'] = current_path
        return WAITING_FOLDER

    async def _handle_folder_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle folder path input or folder name for creation"""
        text = update.message.text
        
        # Check if we're creating a folder
        if 'create_folder_parent' in context.user_data:
            parent_path = context.user_data['create_folder_parent']
            new_folder_path = os.path.join(parent_path, text)
            try:
                os.makedirs(new_folder_path, exist_ok=True)
                await update.message.reply_text(f"✅ Папка создана: {new_folder_path}", reply_markup=self._get_main_menu())
                del context.user_data['create_folder_parent']
                return ConversationHandler.END
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка создания папки: {str(e)}")
                return WAITING_FOLDER
                
        # Otherwise, treat as folder path
        folder_path = text
        try:
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                self.controller.open_folder(folder_path)
                await update.message.reply_text(f"✅ Папка открыта: {folder_path}", reply_markup=self._get_main_menu())
                return ConversationHandler.END
            else:
                await update.message.reply_text(f"❌ Папка не найдена: {folder_path}")
                return WAITING_FOLDER
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            return WAITING_FOLDER

    async def _handle_folder_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle folder navigation callback"""
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data == "cancel_folder":
            await query.edit_message_text("❌ Отменено", reply_markup=self._get_main_menu())
            return ConversationHandler.END
            
        if data.startswith("folder_"):
            folder_path = data.replace("folder_", "")
            context.user_data['current_folder'] = folder_path
            await query.edit_message_text(
                f"📁 {folder_path}\nВыберите папку:",
                reply_markup=self._get_folder_keyboard(folder_path)
            )
            return WAITING_FOLDER
            
        elif data.startswith("open_"):
            folder_path = data.replace("open_", "")
            try:
                self.controller.open_folder(folder_path)
                await query.edit_message_text(f"✅ Папка открыта: {folder_path}", reply_markup=self._get_main_menu())
            except Exception as e:
                await query.edit_message_text(f"❌ Ошибка: {str(e)}", reply_markup=self._get_main_menu())
            return ConversationHandler.END
            
        elif data.startswith("create_folder_"):
            parent_path = data.replace("create_folder_", "")
            await query.edit_message_text(f"📁 Создание папки в: {parent_path}\nВведите имя новой папки:\nДля отмены: /done")
            context.user_data['create_folder_parent'] = parent_path
            return WAITING_FOLDER
            
        return WAITING_FOLDER

    async def _start_notify_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start notification input conversation"""
        query = update.callback_query
        await query.answer()
        
        if not await self._check_authorization(update):
            return ConversationHandler.END
        if not await self._check_permission(update, "system"):
            return ConversationHandler.END
            
        await query.edit_message_text("🔔 Введите сообщение для уведомления:\nДля отмены: /done")
        return WAITING_NOTIFY

    async def _handle_notify_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle notification input"""
        message = update.message.text
        try:
            self.controller.show_notification("PCUltra", message)
            await update.message.reply_text(f"✅ Уведомление отправлено: {message}", reply_markup=self._get_main_menu())
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=self._get_main_menu())
            
        return ConversationHandler.END

    async def _start_url_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start URL input conversation"""
        query = update.callback_query
        await query.answer()
        
        if not await self._check_authorization(update):
            return ConversationHandler.END
        if not await self._check_permission(update, "browser"):
            return ConversationHandler.END
            
        await query.edit_message_text("🔗 Введите URL для перехода:\nДля отмены: /done")
        return WAITING_URL

    async def _handle_url_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle URL input"""
        url = update.message.text.strip()
        # Add http:// if not present
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
            
        try:
            await update.message.reply_text("🌐 Открываю браузер и перехожу на URL...")
            executor = get_playwright_executor()
            loop = asyncio.get_event_loop()
            
            # Используем public-функцию
            await loop.run_in_executor(executor, self.controller.browser_navigate, url)
            
            await update.message.reply_text(f"✅ Переход на: {url}", reply_markup=self._get_main_menu())
            
        except Exception as e:
            logger.error(f"Browser navigate error: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}", reply_markup=self._get_main_menu())
            
        return ConversationHandler.END

    async def _cancel_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current input"""
        if update.message:
            await update.message.reply_text("❌ Отменено", reply_markup=self._get_main_menu())
        elif update.callback_query:
            await update.callback_query.answer("❌ Отменено")
            await update.callback_query.edit_message_text("❌ Отменено", reply_markup=self._get_main_menu())
            
        return ConversationHandler.END

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if not await self._check_authorization(update):
            return
            
        data = query.data
        
        try:
            # Menu navigation
            if data == "menu_main":
                await query.edit_message_text("📱 Главное меню PCUltra", reply_markup=self._get_main_menu())
            elif data == "menu_mouse":
                if not await self._check_permission(update, "mouse"): return
                await query.edit_message_text("🖱️ Управление мышью", reply_markup=self._get_mouse_menu())
            elif data == "menu_keyboard":
                if not await self._check_permission(update, "keyboard"): return
                await query.edit_message_text("⌨️ Клавиатура", reply_markup=self._get_keyboard_menu())
            elif data == "menu_media": # ИЗМЕНЕНО: menu_audio -> menu_media
                if not await self._check_permission(update, "audio"): return
                await query.edit_message_text("🎵 Медиа управление", reply_markup=self._get_media_menu()) # ИЗМЕНЕНО: _get_audio_menu -> _get_media_menu
            elif data == "menu_system":
                if not await self._check_permission(update, "system"): return
                await query.edit_message_text("💻 Система", reply_markup=self._get_system_menu())
            elif data == "menu_browser":
                if not await self._check_permission(update, "browser"): return
                await query.edit_message_text("🌐 Браузер", reply_markup=self._get_browser_menu())
            elif data == "menu_shortcuts":
                await query.edit_message_text("⚡ Shortcuts", reply_markup=self._get_shortcuts_menu())
            
            # --- Browser actions (Добавлены) ---
            elif data == "browser_open":
                if not await self._check_permission(update, "browser"): return
                await self._handle_browser_action(data, query)
            elif data == "browser_close":
                if not await self._check_permission(update, "browser"): return
                await self._handle_browser_action(data, query)

            # Mouse actions
            elif data.startswith("mouse_"):
                if not await self._check_permission(update, "mouse"): return
                await self._handle_mouse_action(data, query)
            
            # Keyboard actions
            elif data.startswith("hotkey_"):
                if not await self._check_permission(update, "keyboard"): return
                await self._handle_hotkey_action(data, query)
            
            # Media actions (Media only, no volume/mute)
            elif data.startswith("audio_"):
                if not await self._check_permission(update, "audio"): return
                await self._handle_media_action(data, query) # ИЗМЕНЕНО: _handle_audio_action -> _handle_media_action (новая функция)
            
            # Action status
            elif data == "action_status":
                if not await self._check_permission(update, "status"): return
                await self._handle_status_action(query)
                
            # Screenshot action
            elif data == "action_screenshot":
                if not await self._check_permission(update, "screenshot"): return
                await self._handle_screenshot_action(query)
            
            # Shortcut action
            elif data.startswith("shortcut_"):
                if not await self._check_permission(update, "shortcut"): return
                await self._handle_shortcut_action(data, query)
                
            elif data == "noop":
                await query.answer("Действие недоступно.")
                
            else:
                await query.edit_message_text(f"❌ Неизвестная команда: {data}", reply_markup=self._get_main_menu())
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.edit_message_text(f"❌ Критическая ошибка: {str(e)[:100]}", reply_markup=self._get_main_menu())


    async def _handle_mouse_action(self, data, query: Update.callback_query):
        """Handle mouse movement and clicks"""
        action = data.replace("mouse_", "")
        step = self.mouse_step
        
        try:
            if action == "up":
                self.controller.mouse_move(pyautogui.position().x, pyautogui.position().y - step)
                msg = "Мышь вверх"
            elif action == "down":
                self.controller.mouse_move(pyautogui.position().x, pyautogui.position().y + step)
                msg = "Мышь вниз"
            elif action == "left":
                self.controller.mouse_move(pyautogui.position().x - step, pyautogui.position().y)
                msg = "Мышь влево"
            elif action == "right":
                self.controller.mouse_move(pyautogui.position().x + step, pyautogui.position().y)
                msg = "Мышь вправо"
            elif action == "center" or action == "reset":
                screen_width, screen_height = pyautogui.size()
                self.controller.mouse_move(screen_width // 2, screen_height // 2)
                msg = "Мышь в центр"
            elif action == "click_l":
                self.controller.mouse_click("L")
                msg = "ЛКМ клик"
            elif action == "click_r":
                self.controller.mouse_click("R")
                msg = "ПКМ клик"
            elif action == "click_m":
                self.controller.mouse_click("M")
                msg = "СКМ клик"
            elif action == "scroll_up":
                self.controller.scroll(20)
                msg = "Прокрутка вверх"
            elif action == "scroll_down":
                self.controller.scroll(-20)
                msg = "Прокрутка вниз"
            else:
                msg = "Неизвестное действие мыши"
                
            await query.answer(f"✅ {msg}")
            # Do not edit message for simple mouse movements/clicks, just answer the query
            
        except Exception as e:
            logger.error(f"Mouse action error: {e}")
            await query.answer(f"❌ Ошибка мыши: {str(e)}", show_alert=True)

    async def _handle_hotkey_action(self, data, query: Update.callback_query):
        """Handle hotkey presses"""
        hotkey = data.replace("hotkey_", "").replace("_", "+")
        try:
            self.controller.hotkey(hotkey)
            await query.answer(f"✅ Горячая клавиша: {hotkey.upper()}")
        except Exception as e:
            logger.error(f"Hotkey action error: {e}")
            await query.answer(f"❌ Ошибка горячей клавиши: {str(e)}", show_alert=True)

    async def _handle_media_action(self, data, query: Update.callback_query): # ИЗМЕНЕНО: _handle_audio_action -> _handle_media_action
        """Handle media controls (play/pause, next, prev, forward, backward)"""
        action = data.replace("audio_", "")
        
        try:
            if action == "playpause":
                self.controller.media_play_pause()
                msg = "⏯️ Play/Pause"
            elif action == "prev":
                self.controller.media_previous()
                msg = "⏮️ Previous track"
            elif action == "next":
                self.controller.media_next()
                msg = "⏭️ Next track"
            elif action == "forward":
                self.controller.media_forward()
                msg = "⏩ Forward 10s"
            elif action == "backward":
                self.controller.media_backward()
                msg = "⏪ Backward 10s"
            else:
                msg = "Неизвестное медиа-действие"
                
            await query.answer(f"✅ {msg}")
            # Обновляем меню, чтобы показать текущее состояние
            await query.edit_message_reply_markup(reply_markup=self._get_media_menu()) 
            
        except Exception as e:
            logger.error(f"Media action error: {e}")
            await query.answer(f"❌ Медиа-ошибка: {str(e)}", show_alert=True)

    async def _handle_status_action(self, query: Update.callback_query):
        """Handle status request"""
        try:
            cpu_percent = psutil.cpu_percent()
            mem_info = psutil.virtual_memory()
            disk_info = psutil.disk_usage(os.path.abspath(os.sep))
            
            status_text = (
                "📊 Статус ПК:\n"
                f"CPU: {cpu_percent}%\n"
                f"RAM: {mem_info.percent}% ({mem_info.used // (1024**3)}G/{mem_info.total // (1024**3)}G)\n"
                f"Disk C:\\: {disk_info.percent}% ({disk_info.used // (1024**3)}G/{disk_info.total // (1024**3)}G)"
            )
            await query.answer(status_text, show_alert=True)
            
        except Exception as e:
            logger.error(f"Status check error: {e}")
            await query.answer(f"❌ Ошибка статуса: {str(e)}", show_alert=True)

    async def _handle_screenshot_action(self, query: Update.callback_query):
        """Handle full screenshot request"""
        await query.answer("📸 Делаю скриншот...")
        try:
            filepath = self.controller.screenshot_full()
            
            # Send photo
            await query.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=filepath,
                caption="📸 Полный скриншот"
            )
            
            # Clean up
            os.remove(filepath)
            await query.edit_message_reply_markup(reply_markup=self._get_main_menu())
            
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            await query.edit_message_text(f"❌ Ошибка скриншота: {str(e)}", reply_markup=self._get_main_menu())

    async def _handle_browser_action(self, data, query: Update.callback_query):
        """Handle browser open and close actions"""
        action = data.replace("browser_", "")
        
        # Run in playwright thread
        def run_browser_action():
            if action == "open":
                self.controller.browser_open()
                return "🌐 Браузер открыт."
            elif action == "close":
                self.controller.browser_close()
                return "❌ Браузер закрыт."
            else:
                return "Неизвестное действие браузера."
        
        try:
            await query.answer(f"Выполняю: {action}...")
            executor = get_playwright_executor()
            loop = asyncio.get_event_loop()
            
            result_msg = await loop.run_in_executor(executor, run_browser_action)
            
            await query.edit_message_text(result_msg, reply_markup=self._get_browser_menu())
            
        except Exception as e:
            logger.error(f"Browser action error: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)}", reply_markup=self._get_browser_menu())

    async def _handle_shortcut_action(self, data, query: Update.callback_query):
        """Handle custom shortcuts from config"""
        shortcut_id = data.replace("shortcut_", "")
        
        self.config_manager.config = None
        self.config_manager.load_config()
        config = self.config_manager.get_config()
        shortcuts = config.get('shortcuts', {})
        
        shortcut = shortcuts.get(shortcut_id)
        
        if not shortcut:
            await query.answer("❌ Ярлык не найден.", show_alert=True)
            return

        command_line = shortcut.get('command')
        display_name = shortcut.get('display_name', command_line)

        if not command_line:
            await query.answer(f"❌ Команда для '{display_name}' не определена.", show_alert=True)
            return

        await query.answer(f"⚡ Запуск: {display_name}")

        try:
            # Используем shlex для безопасного разделения команд с аргументами
            args = shlex.split(command_line)
            app_path = args[0]
            app_args = args[1:]
            
            self.controller.open_app(app_path, app_args)
            await query.edit_message_text(f"✅ Запущено: {display_name}", reply_markup=self._get_shortcuts_menu())

        except FileNotFoundError:
            await query.edit_message_text(f"❌ Ошибка: Файл не найден по пути: {app_path}", reply_markup=self._get_shortcuts_menu())
        except Exception as e:
            logger.error(f"Shortcut action error for {command_line}: {e}")
            await query.edit_message_text(f"❌ Ошибка при запуске '{display_name}': {str(e)}", reply_markup=self._get_shortcuts_menu())