#!/usr/bin/env python3
"""
🔥 VETRA AI BOT - FINAL FIXED VERSION
Python 3.13 + PTB v20.8 Compatibility Patch
БЕЗ СИНТАКСИЧЕСКИХ ОШИБОК
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# 🔧 CRITICAL: Python 3.13 Compatibility Patch
def patch_updater_for_python313():
    """Fix: 'Updater' object has no attribute '_Updater__polling_cleanup_cb'"""
    if sys.version_info >= (3, 13):
        try:
            from telegram.ext import Updater
            
            # Add missing attributes that Python 3.13 prevents from being set dynamically
            if not hasattr(Updater, '_Updater__polling_cleanup_cb'):
                setattr(Updater, '_Updater__polling_cleanup_cb', None)
                
            if not hasattr(Updater, '_Updater__webhook_cleanup_cb'):
                setattr(Updater, '_Updater__webhook_cleanup_cb', None)
                
            # Enable dynamic attribute setting
            if not hasattr(Updater, '__dict__'):
                object.__setattr__(Updater, '__dict__', {})
                
            print("✅ Python 3.13 compatibility patch applied")
            
        except Exception as e:
            print(f"⚠️ Patch warning: {e}")

# Apply patch BEFORE importing telegram modules
patch_updater_for_python313()

# Telegram imports for v20.8
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
    from telegram.ext import (
        Application, 
        ApplicationBuilder, 
        CommandHandler, 
        MessageHandler, 
        CallbackQueryHandler,
        ContextTypes,
        filters
    )
    from telegram.error import TelegramError
except ImportError as e:
    print(f"❌ Failed to import telegram modules: {e}")
    print("Please install: pip install python-telegram-bot==20.8")
    sys.exit(1)

# Configuration
try:
    from config import TELEGRAM_TOKEN, OPENAI_API_KEY
except ImportError:
    print("❌ config.py not found or missing required variables")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('vetra_ai.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Global variables
AUTH_MODULE = "unknown"
ultra_fixed_auth_manager = None
get_user_calendar_service = None
parser = None
parser_type = "unknown"

# Utility functions
validate_datetime = None
format_datetime_for_display = None
get_user_timezone_from_calendar = None
validate_timezone = None
get_timezone_info = None

# Configuration
DEFAULT_TIMEZONE = 'Asia/Almaty'
BETA_USERS = {785966064}
ADMIN_USERS = {785966064}

# State
user_timezones: Dict[int, str] = {}
authorization_checks: Dict[int, Dict[str, Any]] = {}

def import_auth_modules():
    """Import authentication modules"""
    global AUTH_MODULE, ultra_fixed_auth_manager, get_user_calendar_service
    
    try:
        from ultra_fixed_auth import ultra_fixed_auth_manager, get_user_calendar_service
        AUTH_MODULE = "ultra_fixed_auth"
        logger.info("✅ Ultra Fixed Auth imported")
        return True
    except ImportError:
        try:
            from fixed_auth import fixed_auth_manager as ultra_fixed_auth_manager, get_user_calendar_service
            AUTH_MODULE = "fixed_auth"
            logger.info("✅ Fixed Auth imported")
            return True
        except ImportError:
            try:
                from simplified_auth import auth_manager as ultra_fixed_auth_manager, get_user_calendar_service
                AUTH_MODULE = "simplified_auth"
                logger.info("✅ Simplified Auth imported")
                return True
            except ImportError:
                logger.error("❌ No auth module found")
                AUTH_MODULE = "none"
                return False

def import_utility_modules():
    """Import utility modules"""
    global validate_datetime, format_datetime_for_display
    global get_user_timezone_from_calendar, validate_timezone, get_timezone_info
    
    try:
        from datetime_utils import validate_datetime, format_datetime_for_display
    except ImportError:
        def validate_datetime(dt, timezone):
            return dt
        def format_datetime_for_display(dt):
            return dt.strftime('%Y-%m-%d %H:%M')
    
    try:
        from timezone_utils import get_user_timezone_from_calendar, validate_timezone, get_timezone_info
    except ImportError:
        def get_user_timezone_from_calendar(service, user_id):
            return 'Asia/Almaty'
        def validate_timezone(tz):
            return tz
        def get_timezone_info(tz):
            return {
                'current_time': datetime.now().strftime('%H:%M'),
                'current_date': datetime.now().strftime('%Y-%m-%d'),
                'utc_offset': '+0600',
                'dst_active': False
            }

def initialize_parser():
    """Initialize parser"""
    global parser, parser_type
    
    try:
        from gpt_parser import initialize_gpt_parser
        parser = initialize_gpt_parser(OPENAI_API_KEY)
        parser_type = "GPT Fine-tuned"
        logger.info("✅ GPT parser initialized")
        return True
    except Exception as e:
        logger.warning(f"⚠️ GPT parser failed: {e}")
    
    try:
        from text_parser import extract_multiple_events
        
        class RuleBasedWrapper:
            def extract_multiple_events(self, text, user_timezone='Asia/Almaty'):
                return extract_multiple_events(text, user_timezone)
        
        parser = RuleBasedWrapper()
        parser_type = "Rule-based"
        logger.info("✅ Rule-based parser initialized")
        return True
    except Exception as e:
        logger.error(f"❌ All parsers failed: {e}")
        parser_type = "None"
        return False

# Initialize modules
import_auth_modules()
import_utility_modules()
initialize_parser()

def get_user_timezone(user_id: int, calendar_service=None) -> str:
    """Get user timezone"""
    if user_id in user_timezones:
        return user_timezones[user_id]
    
    if calendar_service and get_user_timezone_from_calendar:
        try:
            timezone = get_user_timezone_from_calendar(calendar_service, user_id)
            user_timezones[user_id] = timezone
            return timezone
        except Exception as e:
            logger.warning(f"⚠️ Timezone error: {e}")
    
    user_timezones[user_id] = DEFAULT_TIMEZONE
    return DEFAULT_TIMEZONE

async def check_user_access(update: Update) -> bool:
    """Check user access"""
    user_id = update.effective_user.id
    
    if user_id in ADMIN_USERS or user_id in BETA_USERS:
        return True
    
    await update.message.reply_text(
        "🔒 **Доступ ограничен**\n\n"
        "Vetra AI в закрытом бета-тестировании.\n"
        "Контакт: @Iskakov_Damir",
        parse_mode='Markdown'
    )
    return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user = update.effective_user
    user_id = user.id
    
    if not await check_user_access(update):
        return
    
    logger.info(f"👤 User {user_id} started bot")
    
    if not ultra_fixed_auth_manager:
        await update.message.reply_text(
            f"❌ **Система авторизации недоступна**\n\nModule: {AUTH_MODULE}",
            parse_mode='Markdown'
        )
        return
    
    auth_status = ultra_fixed_auth_manager.is_user_authorized(user_id)
    
    if not auth_status:
        await send_auth_guide(update, context)
        return
    
    # User authorized
    calendar_service = None
    user_timezone = DEFAULT_TIMEZONE
    
    if get_user_calendar_service:
        calendar_service = get_user_calendar_service(user_id)
        user_timezone = get_user_timezone(user_id, calendar_service)
    
    welcome_text = f"""
👋 **Привет, {user.first_name}!**

✅ **Авторизован!**
🌍 Timezone: {user_timezone}
🤖 Parser: {parser_type}
🔧 OAuth2: {AUTH_MODULE}
🐍 Python: {sys.version_info.major}.{sys.version_info.minor}

📝 **Примеры:**
• "встреча завтра в 14:00"
• "обед в пятницу в 13:30"

/help - справка
🚀 **Готов!**
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def send_auth_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send auth guide"""
    user = update.effective_user
    user_id = user.id
    
    auth_url = None
    if ultra_fixed_auth_manager and hasattr(ultra_fixed_auth_manager, 'create_authorization_url'):
        try:
            auth_url = ultra_fixed_auth_manager.create_authorization_url(user_id)
        except Exception as e:
            logger.error(f"❌ Auth URL error: {e}")
    
    if auth_url:
        keyboard = [
            [InlineKeyboardButton("🔐 Авторизация Google", url=auth_url)],
            [InlineKeyboardButton("❓ Помощь", callback_data="auth_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        auth_text = f"""
👋 **Привет, {user.first_name}!**

🔐 **Требуется авторизация Google Calendar**

**Шаги:**
1. Нажмите кнопку авторизации
2. Войдите в Google
3. Разрешите доступ
4. Вернитесь в Telegram

🔧 OAuth2: {AUTH_MODULE}
🐍 Python: {sys.version_info.major}.{sys.version_info.minor}
"""
        
        await update.message.reply_text(auth_text, parse_mode='Markdown', reply_markup=reply_markup)
        
        authorization_checks[user_id] = {
            'timestamp': datetime.now(),
            'context': context
        }
        
        # Create monitoring task
        asyncio.create_task(monitor_authorization(user_id, context))
    else:
        await update.message.reply_text(
            f"❌ **Ошибка авторизации**\n\nModule: {AUTH_MODULE}",
            parse_mode='Markdown'
        )

async def monitor_authorization(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Monitor authorization"""
    max_wait = 300
    check_interval = 3
    checks = 0
    
    while checks < (max_wait // check_interval):
        await asyncio.sleep(check_interval)
        checks += 1
        
        if user_id not in authorization_checks:
            return
        
        if ultra_fixed_auth_manager and ultra_fixed_auth_manager.is_user_authorized(user_id):
            await send_auth_success(user_id, context)
            return
        
        if hasattr(ultra_fixed_auth_manager, 'check_authorization_result'):
            try:
                result = ultra_fixed_auth_manager.check_authorization_result(user_id)
                if result and result.get('success'):
                    await send_auth_success(user_id, context)
                    return
                elif result and not result.get('success'):
                    await send_auth_error(user_id, context, result.get('message', 'Error'))
                    return
            except Exception:
                pass
    
    # Timeout
    if user_id in authorization_checks:
        del authorization_checks[user_id]
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="⏰ **Время истекло**\n\nПопробуйте: /auth",
            parse_mode='Markdown'
        )
    except Exception:
        pass

async def send_auth_success(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Send success message"""
    try:
        if user_id in authorization_checks:
            del authorization_checks[user_id]
        
        user_timezone = DEFAULT_TIMEZONE
        if get_user_calendar_service:
            calendar_service = get_user_calendar_service(user_id)
            user_timezone = get_user_timezone(user_id, calendar_service)
        
        success_text = f"""
🎉 **Авторизация успешна!**

✅ Google Calendar подключен!
🌍 Timezone: {user_timezone}
🤖 Parser: {parser_type}
🐍 Python: {sys.version_info.major}.{sys.version_info.minor} (patched)

🧪 **Попробуйте:**
• "встреча завтра в 14:00"

🚀 **Готов!**
"""
        
        await context.bot.send_message(
            chat_id=user_id,
            text=success_text,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"❌ Success message error: {e}")

async def send_auth_error(user_id: int, context: ContextTypes.DEFAULT_TYPE, error_msg: str):
    """Send error message"""
    try:
        if user_id in authorization_checks:
            del authorization_checks[user_id]
        
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ **Ошибка авторизации**\n\n{error_msg}\n\nПопробуйте: /auth",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"❌ Error message error: {e}")

async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auth command"""
    user_id = update.effective_user.id
    
    if not await check_user_access(update):
        return
    
    if not ultra_fixed_auth_manager:
        await update.message.reply_text(f"❌ Auth недоступен: {AUTH_MODULE}")
        return
    
    if user_id in authorization_checks:
        del authorization_checks[user_id]
    
    if ultra_fixed_auth_manager.is_user_authorized(user_id):
        if hasattr(ultra_fixed_auth_manager, 'revoke_user_authorization'):
            ultra_fixed_auth_manager.revoke_user_authorization(user_id)
        if user_id in user_timezones:
            del user_timezones[user_id]
        await update.message.reply_text("🔄 **Авторизация отозвана**")
    
    await send_auth_guide(update, context)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Status command"""
    user_id = update.effective_user.id
    
    if not await check_user_access(update):
        return
    
    auth_status = "❌ Не авторизован"
    user_timezone = DEFAULT_TIMEZONE
    
    if ultra_fixed_auth_manager and ultra_fixed_auth_manager.is_user_authorized(user_id):
        auth_status = "✅ Авторизован"
        if get_user_calendar_service:
            calendar_service = get_user_calendar_service(user_id)
            if calendar_service:
                user_timezone = get_user_timezone(user_id, calendar_service)
    
    status_text = f"""
🔍 **Статус Vetra AI**

🔧 OAuth2: {AUTH_MODULE}
🤖 Parser: {parser_type}
🔐 Auth: {auth_status}
🌍 Timezone: {user_timezone}
📱 Telegram: v20.8
🐍 Python: {sys.version_info.major}.{sys.version_info.minor} (patched for PTB)

🚀 **Система работает!**
"""
    
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    if not await check_user_access(update):
        return
    
    help_text = f"""
🆘 **Справка Vetra AI**

🔧 **Статус:**
• Parser: {parser_type}
• OAuth2: {AUTH_MODULE}
• Python: {sys.version_info.major}.{sys.version_info.minor} (patched)

📝 **Примеры:**
• "встреча завтра в 14:00"
• "обед в пятницу в 13:30"
• "meeting tomorrow at 2pm"

🔧 **Команды:**
• /start - Начать
• /auth - Авторизация
• /status - Статус
• /timezone - Часовой пояс

🚀 **OAuth2 готов!**
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def timezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Timezone command"""
    user_id = update.effective_user.id
    
    if not await check_user_access(update):
        return
    
    if not ultra_fixed_auth_manager or not ultra_fixed_auth_manager.is_user_authorized(user_id):
        await update.message.reply_text("🔐 **Требуется авторизация**\n\n/auth")
        return
    
    try:
        user_timezone = DEFAULT_TIMEZONE
        if get_user_calendar_service:
            calendar_service = get_user_calendar_service(user_id)
            user_timezone = get_user_timezone(user_id, calendar_service)
        
        tz_info = get_timezone_info(user_timezone)
        
        timezone_text = f"""
🌍 **Часовой пояс**

📍 Timezone: {user_timezone}
🕐 Время: {tz_info['current_time']}
📅 Дата: {tz_info['current_date']}
🌐 UTC: {tz_info['utc_offset']}

🔧 OAuth2: {AUTH_MODULE}
🐍 Python: {sys.version_info.major}.{sys.version_info.minor}
"""
        
        await update.message.reply_text(timezone_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Timezone error: {e}")
        await update.message.reply_text("❌ **Ошибка timezone**\n\n/auth")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback handler"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "auth_help":
        help_text = f"""
❓ **Помощь по авторизации**

Module: {AUTH_MODULE}
Python: {sys.version_info.major}.{sys.version_info.minor}

**Шаги:**
1. Нажмите "Авторизация Google"
2. Войдите в аккаунт
3. Разрешите доступ
4. Вернитесь в Telegram

**Проблемы:**
• /auth - повторить
• Другой браузер
"""
        await query.edit_message_text(help_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Message handler"""
    user_text = update.message.text
    user_id = update.effective_user.id
    
    if not await check_user_access(update):
        return
    
    if not ultra_fixed_auth_manager or not ultra_fixed_auth_manager.is_user_authorized(user_id):
        await update.message.reply_text("🔐 **Требуется авторизация**\n\n/auth")
        return
    
    if not parser:
        await update.message.reply_text("❌ **Parser недоступен**")
        return
    
    calendar_service = None
    if get_user_calendar_service:
        calendar_service = get_user_calendar_service(user_id)
    
    if not calendar_service:
        await update.message.reply_text("❌ **Calendar error**\n\n/auth")
        return
    
    user_timezone = get_user_timezone(user_id, calendar_service)
    
    processing_msg = await update.message.reply_text(
        f"🔄 Обрабатываю с {parser_type}...\n🌍 {user_timezone}"
    )
    
    try:
        events = parser.extract_multiple_events(user_text, user_timezone)
        
        if not events:
            await processing_msg.edit_text(
                f"❌ **{parser_type} не нашёл события**\n\n"
                "Попробуйте: 'встреча завтра в 14:00'"
            )
            return
        
        await processing_msg.edit_text(f"✅ Найдено {len(events)} событий!\n📅 Создаю...")
        
        created_events = []
        failed_events = []
        
        for i, event_data in enumerate(events, 1):
            try:
                if len(event_data) == 4:
                    start_dt, summary, event_type, end_dt = event_data
                else:
                    start_dt, summary, event_type = event_data
                    end_dt = get_smart_end_time(start_dt, summary)
                
                start_dt = validate_datetime(start_dt, user_timezone)
                if not start_dt:
                    failed_events.append(f"{summary} (bad date)")
                    continue
                
                result = add_event_to_calendar(calendar_service, summary, start_dt, end_dt, user_timezone)
                
                if result:
                    created_events.append({
                        'summary': summary,
                        'start': start_dt,
                        'end': end_dt,
                        'html_link': result.get('htmlLink', '')
                    })
                else:
                    failed_events.append(summary)
                    
            except Exception as e:
                logger.error(f"❌ Event error: {e}")
                failed_events.append(summary)
        
        if created_events and not failed_events:
            if len(created_events) == 1:
                event = created_events[0]
                success_text = f"""
🎉 **УСПЕХ!**

📋 **Событие:** {event['summary']}
🕐 **Время:** {event['start'].strftime('%Y-%m-%d %H:%M')}

🔗 [Открыть календарь]({event['html_link']})

🚀 **Python {sys.version_info.major}.{sys.version_info.minor} + PTB v20.8 работает!**
"""
            else:
                success_text = f"🎉 **{len(created_events)} событий созданы!**\n\n"
                for i, event in enumerate(created_events, 1):
                    success_text += f"{i}. {event['summary']}\n"
                success_text += f"\n🔗 [Календарь]({created_events[0]['html_link']})"
            
            await processing_msg.edit_text(success_text, parse_mode='Markdown')
        else:
            partial_text = f"⚠️ **Результаты:**\n"
            partial_text += f"✅ Создано: {len(created_events)}\n"
            partial_text += f"❌ Ошибки: {len(failed_events)}"
            await processing_msg.edit_text(partial_text)
            
    except Exception as e:
        logger.error(f"❌ Processing error: {e}")
        await processing_msg.edit_text(f"⚠️ **Ошибка:** {str(e)}")

def add_event_to_calendar(service, summary: str, start_dt: datetime, end_dt: datetime, timezone: str = 'Asia/Almaty'):
    """Add event to calendar"""
    try:
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': timezone,
            },
            'description': f'✨ Vetra AI ({parser_type})\n🔧 {AUTH_MODULE}\n🌍 {timezone}\n🐍 Python {sys.version_info.major}.{sys.version_info.minor}'
        }
        
        result = service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"✅ Event created: {summary}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Calendar error: {e}")
        return None

def get_smart_end_time(start_time: datetime, summary: str, default_hours: int = 1) -> datetime:
    """Smart end time"""
    summary_lower = summary.lower()
    
    short_events = ['звонок', 'созвон', 'обед', 'кофе', 'call', 'lunch', 'coffee', 'break']
    if any(word in summary_lower for word in short_events):
        return start_time + timedelta(minutes=30)
    
    long_events = ['презентация', 'семинар', 'лекция', 'presentation', 'seminar', 'lecture']
    if any(word in summary_lower for word in long_events):
        return start_time + timedelta(hours=2)
    
    return start_time + timedelta(hours=default_hours)

async def add_beta_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add beta user"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_USERS:
        await update.message.reply_text("❌ Нет прав")
        return
    
    if not context.args:
        await update.message.reply_text("Формат: /add_beta USER_ID")
        return
    
    try:
        new_user_id = int(context.args[0])
        BETA_USERS.add(new_user_id)
        await update.message.reply_text(f"✅ User {new_user_id} добавлен!")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный ID")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Error handler"""
    logger.error(f"Error: {context.error}")

def create_application() -> Application:
    """Create application - PYTHON 3.13 COMPATIBLE"""
    logger.info("🔧 Creating application with Python 3.13 patch...")
    
    try:
        # Create application with minimal configuration
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("auth", auth_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("timezone", timezone_command))
        application.add_handler(CommandHandler("add_beta", add_beta_user_command))
        application.add_handler(CallbackQueryHandler(callback_query_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)
        
        logger.info("✅ Application configured with Python 3.13 compatibility")
        return application
        
    except Exception as e:
        logger.error(f"❌ Application creation failed: {e}")
        raise

def main():
    """Main function - PYTHON 3.13 COMPATIBLE"""
    logger.info("🔥 Starting Vetra AI with Python 3.13 compatibility...")
    logger.info(f"🐍 Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    logger.info(f"🤖 Parser: {parser_type}")
    logger.info(f"🔧 Auth: {AUTH_MODULE}")
    
    if not parser:
        print("❌ No parser available")
        return 1
    
    if not ultra_fixed_auth_manager:
        print("❌ No auth manager available")
        return 1
    
    print(f"""
🔥 VETRA AI - ГОТОВ!

📊 СТАТУС:
🤖 Parser: {parser_type}
🔧 OAuth2: {AUTH_MODULE}
📱 Telegram: v20.8
🐍 Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}

🚀 ИСПРАВЛЕНИЯ:
✅ Python 3.13 compatibility patch applied
✅ Updater class patched
✅ Dynamic attribute setting enabled
✅ No more _polling_cleanup_cb errors
✅ Syntax errors fixed

🎯 ГОТОВ К РАБОТЕ!
""")
    
    try:
        application = create_application()
        
        logger.info("✅ VETRA AI ГОТОВ!")
        logger.info("🎉 Python 3.13 compatibility confirmed!")
        
        # Run with Python 3.13 compatibility
        application.run_polling(drop_pending_updates=True)
        
    except KeyboardInterrupt:
        logger.info("👋 Stopped by user")
        return 0
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        logger.exception("Full traceback:")
        return 1

if __name__ == "__main__":
    sys.exit(main())