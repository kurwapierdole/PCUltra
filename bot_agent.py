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
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
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
            [InlineKeyboardButton("🔊 Аудио", callback_data="menu_audio")],
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
                InlineKeyboardButton("↕️", callback_data="mouse_center")
            ],
            [
                InlineKeyboardButton("⬅️", callback_data="mouse_left"),
                InlineKeyboardButton("🖱️", callback_data="mouse_click_l"),
                InlineKeyboardButton("➡️", callback_data="mouse_right")
            ],
            [
                InlineKeyboardButton("⬇️", callback_data="mouse_down"),
                InlineKeyboardButton("🔄", callback_data="mouse_reset")
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
    def _get_audio_menu(self):
        """Create audio control menu"""
        try:
            volume = self.controller.get_volume()
            muted = self.controller.is_muted()
            mute_text = "🔇 Выкл звук" if not muted else "🔊 Вкл звук"
        except:
            volume = "?"
            mute_text = "🔇 Выкл звук"
        keyboard = [
            [InlineKeyboardButton(f"🔊 Громкость: {volume}%", callback_data="noop")],
            [
                InlineKeyboardButton("➖➖", callback_data="audio_vol_down_10"),
                InlineKeyboardButton("➖", callback_data="audio_vol_down_5"),
                InlineKeyboardButton("➕", callback_data="audio_vol_up_5"),
                InlineKeyboardButton("➕➕", callback_data="audio_vol_up_10")
            ],
            [InlineKeyboardButton(mute_text, callback_data="audio_mute")],
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
            [InlineKeyboardButton("⚡ VPN", callback_data="shortcut_vpn")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    def _get_browser_menu(self):
        """Create browser control menu"""
        keyboard = [
            [InlineKeyboardButton("🌐 Открыть браузер", callback_data="browser_open")],
            [InlineKeyboardButton("🔗 Перейти на URL", callback_data="browser_navigate")],
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
                elif not parent:
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
            "🔊 Аудио - громкость, проигрывание\n"
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
            await update.message.reply_text(f"✅ Введен текст: {text[:50]}{'...' if len(text) > 50 else ''}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
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
                await update.message.reply_text(f"✅ Папка создана: {new_folder_path}")
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
                await update.message.reply_text(f"✅ Папка открыта: {folder_path}")
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
            await update.message.reply_text(f"✅ Уведомление отправлено: {message}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
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
            # Navigate will auto-open browser if needed
            await loop.run_in_executor(executor, self.controller._browser_navigate_sync, url)
            await update.message.reply_text(f"✅ Переход на: {url}")
        except Exception as e:
            logger.error(f"Browser navigate error: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
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
                if not await self._check_permission(update, "mouse"):
                    return
                await query.edit_message_text("🖱️ Управление мышью\nИспользуйте кнопки для управления", reply_markup=self._get_mouse_menu())
            elif data == "menu_keyboard":
                if not await self._check_permission(update, "keyboard"):
                    return
                await query.edit_message_text("⌨️ Клавиатура\nВыберите действие", reply_markup=self._get_keyboard_menu())
            elif data == "menu_audio":
                if not await self._check_permission(update, "audio"):
                    return
                await query.edit_message_text("🔊 Управление аудио\nИспользуйте кнопки для управления", reply_markup=self._get_audio_menu())
            elif data == "menu_system":
                if not await self._check_permission(update, "system"):
                    return
                await query.edit_message_text("💻 Система\nВыберите действие", reply_markup=self._get_system_menu())
            elif data == "menu_browser":
                if not await self._check_permission(update, "browser"):
                    return
                await query.edit_message_text("🌐 Браузер\nВыберите действие", reply_markup=self._get_browser_menu())
            elif data == "menu_shortcuts":
                await query.edit_message_text("⚡ Shortcuts\nВыберите команду", reply_markup=self._get_shortcuts_menu())
            # Mouse actions
            elif data.startswith("mouse_"):
                if not await self._check_permission(update, "mouse"):
                    return
                await self._handle_mouse_action(data, query)
            # Keyboard actions
            elif data.startswith("hotkey_"):
                if not await self._check_permission(update, "keyboard"):
                    return
                await self._handle_hotkey_action(data, query)
            # Audio actions
            elif data.startswith("audio_"):
                if not await self._check_permission(update, "audio"):
                    return
                await self._handle_audio_action(data, query)
            # Screenshot
            elif data == "action_screenshot":
                if not await self._check_permission(update, "screenshot"):
                    return
                await self._handle_screenshot(query)
            # Status
            elif data == "action_status":
                await self._handle_status(query)
            # Browser actions
            elif data == "browser_open":
                if not await self._check_permission(update, "browser"):
                    return
                await self._handle_browser_open(query)
            # Shortcuts
            elif data.startswith("shortcut_"):
                if not await self._check_permission(update, "system"):
                    return
                await self._handle_shortcut(data, query)
            elif data == "noop":
                pass
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

    async def _handle_audio_action(self, data: str, query):
        """Handle audio actions based on callback data."""
        if data == "audio_vol_up_5":
            self.controller.change_volume(5)
            await query.answer("🔊 +5%")
        elif data == "audio_vol_up_10":
            self.controller.change_volume(10)
            await query.answer("🔊 +10%")
        elif data == "audio_vol_down_5":
            self.controller.change_volume(-5)
            await query.answer("🔇 -5%")
        elif data == "audio_vol_down_10":
            self.controller.change_volume(-10)
            await query.answer("🔇 -10%")
        elif data == "audio_mute":
            self.controller.toggle_mute()
            try:
                muted = self.controller.is_muted()
                status = "🔇 Выключен" if muted else "🔊 Включен"
                await query.answer(f"Звук {status}")
            except:
                await query.answer("Звук переключен")
        elif data == "audio_prev":
            self.controller.media_prev()
            await query.answer("⏮️ Предыдущий")
        elif data == "audio_playpause":
            self.controller.media_play_pause()
            await query.answer("⏯️ Пауза/Воспроизведение")
        elif data == "audio_next":
            self.controller.media_next()
            await query.answer("⏭️ Следующий")
        elif data == "audio_backward":
            self.controller.media_backward(10) # Assuming 10 seconds
            await query.answer("⏪ Назад на 10с")
        elif data == "audio_forward":
            self.controller.media_forward(10) # Assuming 10 seconds
            await query.answer("⏩ Вперед на 10с")
        else:
            await query.answer("❌ Неизвестная аудио команда", show_alert=True)

    async def _handle_mouse_action(self, data: str, query):
        """Handle mouse actions"""
        current_x, current_y = pyautogui.position()
        if data == "mouse_up":
            self.controller.mouse_move(current_x, current_y - self.mouse_step)
            await query.answer("⬆️ Вверх")
        elif data == "mouse_down":
            self.controller.mouse_move(current_x, current_y + self.mouse_step)
            await query.answer("⬇️ Вниз")
        elif data == "mouse_left":
            self.controller.mouse_move(current_x - self.mouse_step, current_y)
            await query.answer("⬅️ Влево")
        elif data == "mouse_right":
            self.controller.mouse_move(current_x + self.mouse_step, current_y)
            await query.answer("➡️ Вправо")
        elif data == "mouse_center":
            screen_width, screen_height = pyautogui.size()
            self.controller.mouse_move(screen_width // 2, screen_height // 2)
            await query.answer("↕️ Центр")
        elif data == "mouse_reset":
            self.controller.mouse_move(0, 0)
            await query.answer("🔄 Сброс")
        elif data == "mouse_click_l":
            self.controller.mouse_click("L")
            await query.answer("🖱️ ЛКМ")
        elif data == "mouse_click_r":
            self.controller.mouse_click("R")
            await query.answer("🖱️ ПКМ")
        elif data == "mouse_click_m":
            self.controller.mouse_click("M")
            await query.answer("🖱️ СКМ")
        elif data == "mouse_scroll_up":
            self.controller.scroll(3)
            await query.answer("📜 Вверх")
        elif data == "mouse_scroll_down":
            self.controller.scroll(-3)
            await query.answer("📜 Вниз")
    async def _handle_hotkey_action(self, data: str, query):
        """Handle hotkey actions"""
        hotkey_map = {
            "hotkey_win_d": "win+d",
            "hotkey_win_r": "win+r",
            "hotkey_ctrl_c": "ctrl+c",
            "hotkey_ctrl_v": "ctrl+v",
            "hotkey_ctrl_x": "ctrl+x",
            "hotkey_ctrl_a": "ctrl+a",
            "hotkey_ctrl_z": "ctrl+z",
            "hotkey_ctrl_y": "ctrl+y",
            "hotkey_alt_tab": "alt+tab",
            "hotkey_esc": "esc"
        }
        hotkey = hotkey_map.get(data)
        if hotkey:
            self.controller.hotkey(hotkey)
            await query.answer(f"✅ {hotkey.upper()}")
        else:
            await query.answer("❌ Неизвестная горячая клавиша", show_alert=True)
    async def _handle_screenshot(self, query):
        """Handle screenshot action"""
        await query.answer("📸 Делаю скриншот...")
        try:
            photo_path = self.controller.screenshot_full()
            with open(photo_path, 'rb') as photo:
                await query.message.reply_photo(photo, caption="📸 Скриншот экрана")
        except Exception as e:
            await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    async def _handle_status(self, query):
        """Handle status action"""
        try:
            status = "🟢 Работает" if self.running else "🔴 Остановлен"
            # Get system resources
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            status_text = (
                f"📊 Статус системы\n"
                f"Бот: {status}\n"
                f"💻 CPU: {cpu_percent:.1f}%\n"
                f"💾 Память: {memory.percent:.1f}%\n"
                f"   Использовано: {memory.used / (1024**3):.2f} GB\n"
                f"   Всего: {memory.total / (1024**3):.2f} GB"
            )
            await query.edit_message_text(status_text, reply_markup=self._get_main_menu())
            await query.answer("📊 Статус обновлен")
        except Exception as e:
            logger.error(f"Status error: {e}")
            await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    async def _handle_browser_open(self, query):
        """Handle browser open action"""
        try:
            await query.answer("🌐 Открываю браузер...")
            executor = get_playwright_executor()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(executor, self.controller._browser_open_sync)
            await query.edit_message_text("✅ Браузер открыт", reply_markup=self._get_browser_menu())
        except Exception as e:
            logger.error(f"Browser open error: {e}")
            await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    async def _handle_shortcut(self, data: str, query):
        """Handle shortcut execution"""
        shortcut_id = data.replace("shortcut_", "")
        shortcut = self.config_manager.get_shortcut(f"/{shortcut_id}")
        if not shortcut:
            # Try to get shortcut by ID from config
            config = self.config_manager.get_config()
            shortcuts = config.get('shortcuts', {})
            if shortcuts and isinstance(shortcuts, dict):
                shortcut = shortcuts.get(shortcut_id)
        if shortcut and isinstance(shortcut, dict):
            try:
                action = shortcut.get('action')
                if action == 'launch_app':
                    path = shortcut.get('path')
                    args = shortcut.get('args', [])
                    self.controller.open_app(path, args)
                    command = shortcut.get('command', shortcut_id)
                    await query.answer(f"✅ {command} выполнено")
                else:
                    await query.answer("❌ Неизвестное действие", show_alert=True)
            except Exception as e:
                await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
        else:
            await query.answer("❌ Shortcut не найден", show_alert=True)
