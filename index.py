# index.py

import logging
import sqlite3
import re
import os
import datetime
import time
import random
import string
from functools import wraps

from telegram import (
    Update,
    ForceReply,
    ChatMember,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ParseMode, ChatMemberStatus

# --- 1. تنظیمات سراسری و ثابت‌ها ---
# توکن ربات خود را اینجا وارد کنید (از BotFather دریافت شده)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8425726675:AAFmobHXlzFnRJXTWli7L8sPmYWmwoVUX2U")
# مسیر فایل دیتابیس
DATABASE_PATH = "group_manager.db"

# نقش‌های ربات برای مدیریت دسترسی
ROLE_OWNER = "owner"
ROLE_BOT_ADMIN = "bot_admin"
ROLE_MODERATOR = "moderator"
ROLE_MEMBER = "member"

# زمان پیش‌فرض برای کپچا، mute و ban (بر حسب ثانیه)
DEFAULT_CAPTCHA_TIME = 60  # 1 دقیقه
DEFAULT_WARN_LIMIT = 3
DEFAULT_FLOOD_LIMIT = 5 # 5 پیام در 5 ثانیه

# لیست کلمات ممنوعه جهانی (برای مثال، می‌توانید از اینجا شروع کنید)
# این لیست در کنار کلمات ممنوعه گروهی استفاده خواهد شد.
GLOBAL_BAD_WORDS = [
    "کسکش", "کصکش", "کونی", "کون", "جنده", "کیر", "کس", "کسخل", "کصخل", "مادرجنده",
    "کیرم", "کصم", "بیشرف", "بی‌شرف", "حرامزاده", "حرامزاده", "سگ‌مذهب", "کونی",
    "مادرخراب", "مادرقهبه", "پفیوز", "سیکتیر", "دیوث", "حرومزاده", "بیناموس", "بی‌ناموس"
]

# --- 2. تنظیمات لاگ‌گیری ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- 3. پیام‌های ربات (به زبان فارسی) ---
# این دیکشنری شامل تمامی پیام‌هایی است که ربات به کاربران ارسال می‌کند.
# استفاده از دیکشنری برای سازماندهی پیام‌ها و امکان اضافه کردن زبان‌های دیگر در آینده مفید است.
MESSAGES = {
    "start_private": (
        "سلام! من یک ربات قدرتمند مدیریت گروه هستم. 😊\n"
        "من را به گروه خود اضافه کنید و ادمین کنید تا بتوانم به شما در مدیریت گروه کمک کنم.\n"
        "برای دیدن لیست دستورات در گروه، `/help` را ارسال کنید."
    ),
    "start_group": (
        "سلام! ممنون که من را به گروه خود اضافه کردید. 🎉\n"
        "برای اینکه بتوانم به درستی کار کنم، لطفاً من را به عنوان ادمین گروه با تمامی اختیارات اضافه کنید.\n"
        "پس از ادمین کردن، مالک گروه (یا ادمین اصلی) می‌تواند از دستور `/help` برای مشاهده قابلیت‌ها استفاده کند."
    ),
    "help_member": (
        "**دستورات عمومی:**\n"
        "• `/id`: نمایش شناسه تلگرام شما و گروه.\n"
        "• `/info`: نمایش اطلاعات پایه شما.\n"
        "• `/rules`: نمایش قوانین گروه (اگر تنظیم شده باشد).\n"
    ),
    "help_moderator": (
        "**دستورات مدیران:**\n"
        "• `/warn <پاسخ به پیام/شناسه>`: اخطار دادن به کاربر.\n"
        "• `/unwarn <پاسخ به پیام/شناسه>`: حذف آخرین اخطار کاربر.\n"
        "• `/warnings <پاسخ به پیام/شناسه>`: نمایش اخطارهای کاربر.\n"
        "• `/mute <پاسخ به پیام/شناسه> [زمان(m/h/d)]`: سکوت موقت یا دائم کاربر. (مثال: `/mute @user 1h`)\n"
        "• `/unmute <پاسخ به پیام/شناسه>`: رفع سکوت کاربر.\n"
        "• `/ban <پاسخ به پیام/شناسه> [زمان(m/h/d)]`: مسدود کردن موقت یا دائم کاربر.\n"
        "• `/unban <پاسخ به پیام/شناسه>`: رفع مسدودیت کاربر.\n"
        "• `/kick <پاسخ به پیام/شناسه>`: اخراج کاربر از گروه.\n"
        "• `/del`: (ریپلای به پیام) حذف پیام ریپلای شده.\n"
        "• `/pin`: (ریپلای به پیام) پین کردن پیام.\n"
        "• `/unpin`: آن‌پین کردن آخرین پیام.\n"
        "• `/purge [تعداد]`: حذف N پیام آخر (پیش‌فرض: 10 پیام).\n"
    ),
    "help_admin": (
        "**دستورات ادمین‌های ربات:**\n"
        "• `/settings`: پنل تنظیمات گروه.\n"
        "• `/promote <پاسخ به پیام/شناسه> [moderator]`: ارتقا کاربر به مدیر ربات یا مدیر.\n"
        "• `/demote <پاسخ به پیام/شناسه>`: کاهش دسترسی کاربر (فقط ادمین‌های ربات).\n"
        "• `/admins`: لیست ادمین‌های ربات و مدیران گروه.\n"
        "• `/setwelcome <متن>`: تنظیم پیام خوش‌آمدگویی (پشتیبانی از `{user_mention}`, `{group_name}`).\n"
        "• `/welcome on/off`: فعال/غیرفعال کردن خوش‌آمدگویی.\n"
        "• `/deljoinmsg on/off`: فعال/غیرفعال کردن حذف پیام‌های ورود/خروج.\n"
        "• `/captcha on/off`: فعال/غیرفعال کردن سیستم کپچا.\n"
        "• `/setcaptchatime <ثانیه>`: تنظیم زمان پاسخ به کپچا.\n"
        "• `/warnlimit <عدد>`: تنظیم تعداد اخطار تا اقدام خودکار.\n"
        "• `/flood on/off`: فعال/غیرفعال کردن کنترل سیل پیام.\n"
        "• `/setfloodlimit <عدد>`: تنظیم محدودیت سیل پیام.\n"
        "• `/rules <متن>`: تنظیم قوانین گروه.\n"
        "• `/addbadword <کلمه>`: افزودن کلمه به لیست ممنوعه گروه.\n"
        "• `/removebadword <کلمه>`: حذف کلمه از لیست ممنوعه گروه.\n"
    ),
    "not_group": "این دستور فقط در گروه‌ها قابل استفاده است.",
    "no_reply_or_id": "لطفاً به پیامی ریپلای کنید یا شناسه/نام کاربری کاربر را مشخص کنید.",
    "user_not_found": "کاربر مورد نظر یافت نشد.",
    "no_permissions": "شما اجازه انجام این کار را ندارید.",
    "bot_not_admin": "من برای انجام این کار نیاز به اختیارات ادمین دارم.",
    "bot_cant_restrict_admin": "من نمی‌توانم ادمین‌های گروه را محدود کنم.",
    "unknown_command": "دستور ناشناخته است. برای راهنمایی /help را ارسال کنید.",
    "welcome_set": "پیام خوش‌آمدگویی با موفقیت تنظیم شد.",
    "welcome_status_changed": "وضعیت خوش‌آمدگویی به `{status}` تغییر یافت.",
    "deljoinmsg_status_changed": "وضعیت حذف پیام‌های ورود/خروج به `{status}` تغییر یافت.",
    "group_id": "شناسه این گروه: `{chat_id}`",
    "user_id": "شناسه شما: `{user_id}`",
    "user_info": (
        "**اطلاعات کاربر:**\n"
        "• شناسه: `{user_id}`\n"
        "• نام: `{first_name}`\n"
        "• نام خانوادگی: `{last_name}`\n"
        "• نام کاربری: @{username}\n"
        "• ربات: {is_bot}\n"
    ),
    "rules_set": "قوانین گروه با موفقیت تنظیم شد.",
    "rules_not_set": "هنوز قوانینی برای گروه تنظیم نشده است.",
    "rules_message": "**قوانین گروه {group_name}:**\n\n{rules_text}",
    "warn_success": "کاربر {user_mention} اخطار گرفت. (اخطارها: {warnings_count})",
    "warn_reason": " دلیل: {reason}",
    "warn_user_info": "اخطارهای {user_mention}: {warnings_count} مورد.",
    "unwarn_success": "آخرین اخطار کاربر {user_mention} حذف شد.",
    "no_warnings": "کاربر {user_mention} هیچ اخطاری ندارد.",
    "warn_limit_reached": "کاربر {user_mention} به دلیل {warn_limit} اخطار، {action} شد.",
    "warn_limit_set": "محدودیت اخطار تا اقدام خودکار به {limit} تنظیم شد.",
    "mute_success_permanent": "کاربر {user_mention} برای همیشه سکوت شد.",
    "mute_success_temp": "کاربر {user_mention} به مدت {time_str} سکوت شد.",
    "already_muted": "کاربر {user_mention} در حال حاضر سکوت است.",
    "unmute_success": "سکوت کاربر {user_mention} برداشته شد.",
    "not_muted": "کاربر {user_mention} سکوت نیست.",
    "ban_success_permanent": "کاربر {user_mention} برای همیشه مسدود شد.",
    "ban_success_temp": "کاربر {user_mention} به مدت {time_str} مسدود شد.",
    "already_banned": "کاربر {user_mention} در حال حاضر مسدود است.",
    "unban_success": "مسدودیت کاربر {user_mention} برداشته شد.",
    "not_banned": "کاربر {user_mention} مسدود نیست.",
    "kick_success": "کاربر {user_mention} از گروه اخراج شد.",
    "message_deleted": "پیام حذف شد.",
    "message_pinned": "پیام پین شد.",
    "message_unpinned": "آخرین پیام پین شده آن‌پین شد.",
    "purge_success": "{count} پیام حذف شد.",
    "promote_success": "کاربر {user_mention} به نقش `{role}` ارتقا یافت.",
    "demote_success": "دسترسی کاربر {user_mention} کاهش یافت.",
    "admins_list": "**لیست ادمین‌های ربات و مدیران گروه:**\n{admins_text}",
    "no_bot_admins": "هیچ ادمین رباتی در این گروه وجود ندارد.",
    "captcha_status_changed": "وضعیت کپچا به `{status}` تغییر یافت.",
    "captcha_time_set": "زمان پاسخ به کپچا به {time} ثانیه تنظیم شد.",
    "new_member_captcha": (
        "به گروه {group_name} خوش آمدید، {user_mention}!\n"
        "لطفاً برای تایید انسان بودن خود، عبارت `{captcha_text}` را در {time} ثانیه ارسال کنید."
    ),
    "captcha_correct": "تایید شما با موفقیت انجام شد! به گروه خوش آمدید.",
    "captcha_incorrect": "کپچا اشتباه است. لطفاً دوباره تلاش کنید.",
    "captcha_timeout": "زمان پاسخ به کپچا به پایان رسید. کاربر {user_mention} از گروه اخراج شد.",
    "captcha_kick_fail": "خطا در اخراج کاربر بعد از کپچا. لطفا ربات را ادمین کنید.",
    "filter_status_changed": "فیلتر `{filter_type}` به `{status}` تغییر یافت.",
    "badword_added": "کلمه `{word}` به لیست کلمات ممنوعه اضافه شد.",
    "badword_removed": "کلمه `{word}` از لیست کلمات ممنوعه حذف شد.",
    "badword_not_found": "کلمه `{word}` در لیست کلمات ممنوعه یافت نشد.",
    "badword_already_exists": "کلمه `{word}` قبلاً در لیست کلمات ممنوعه وجود دارد.",
    "badword_filtered": "پیام حاوی کلمه ممنوعه توسط {user_mention} حذف شد.",
    "flood_status_changed": "وضعیت کنترل سیل پیام به `{status}` تغییر یافت.",
    "flood_limit_set": "محدودیت سیل پیام به {limit} پیام در هر {interval} ثانیه تنظیم شد.",
    "flood_detected": "کاربر {user_mention} به دلیل سیل پیام، {action} شد.",
    "owner_cannot_be_demoted": "مالک گروه را نمی‌توان از نقش ربات ادمین یا مدیر تنزل داد.",
    "cannot_demote_yourself": "شما نمی‌توانید نقش خود را تنزل دهید.",
    "cannot_promote_owner": "مالک گروه به صورت خودکار بالاترین دسترسی را دارد و نیازی به ارتقا نیست.",
    "cannot_promote_self": "شما نمی‌توانید خود را ارتقا دهید.",
    "group_not_found": "این گروه در دیتابیس یافت نشد.",
    "set_rules_usage": "لطفا متن قوانین را بعد از دستور `/rules` وارد کنید. مثال: `/rules احترام متقابل، عدم ارسال لینک`",
    "set_welcome_usage": "لطفا متن پیام خوش‌آمدگویی را بعد از دستور `/setwelcome` وارد کنید. مثال: `/setwelcome سلام {user_mention} خوش آمدید.`",
    "badword_usage": "لطفا کلمه را بعد از دستور وارد کنید. مثال: `/addbadword تست`",
    "promote_usage": "نحوه استفاده: `/promote <reply/user_id> [moderator|bot_admin]`",
    "settings_panel": "به پنل تنظیمات گروه خوش آمدید! {group_name}\n از دکمه‌های زیر برای مدیریت تنظیمات استفاده کنید.",
    "invalid_time_format": "فرمت زمان نامعتبر است. از m (دقیقه)، h (ساعت) یا d (روز) استفاده کنید. مثال: `30m`, `2h`, `7d`",
    "telegram_admin_restricted": "این کاربر ادمین تلگرام است و نمی‌تواند توسط ربات محدود شود. لطفاً به صورت دستی این کار را انجام دهید.",
    "bot_missing_permission_restrict": "ربات برای محدود کردن کاربران نیاز به اجازه `restrict_members` دارد.",
    "bot_missing_permission_delete": "ربات برای حذف پیام‌ها نیاز به اجازه `delete_messages` دارد.",
    "bot_missing_permission_pin": "ربات برای پین کردن پیام‌ها نیاز به اجازه `pin_messages` دارد.",
    "bot_missing_permission_promote": "ربات برای ارتقا/تنزل ادمین‌های تلگرام نیاز به اجازه `promote_members` دارد.",
}

# --- 4. پایگاه داده SQLite و توابع کمکی CRUD ---
# این بخش شامل توابع مربوط به پایگاه داده است.
# به دلیل تکرار توابع برای هر جدول و هر نوع عملیات (INSERT, SELECT, UPDATE, DELETE)،
# این بخش به تنهایی خطوط زیادی را اشغال خواهد کرد.

def init_db():
    """اتصال به دیتابیس و ایجاد جداول در صورت عدم وجود."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # جدول groups - برای ذخیره تنظیمات هر گروه
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY,
            welcome_message TEXT DEFAULT 'به گروه {group_name} خوش آمدید، {user_mention}!',
            welcome_status INTEGER DEFAULT 1,
            del_join_msg_status INTEGER DEFAULT 0,
            captcha_status INTEGER DEFAULT 0,
            captcha_time INTEGER DEFAULT ?,
            warn_limit INTEGER DEFAULT ?,
            language TEXT DEFAULT 'fa',
            flood_status INTEGER DEFAULT 0,
            flood_limit INTEGER DEFAULT ?,
            link_filter INTEGER DEFAULT 0,
            photo_filter INTEGER DEFAULT 0,
            video_filter INTEGER DEFAULT 0,
            document_filter INTEGER DEFAULT 0,
            sticker_filter INTEGER DEFAULT 0,
            gif_filter INTEGER DEFAULT 0,
            forward_filter INTEGER DEFAULT 0,
            voice_filter INTEGER DEFAULT 0,
            video_note_filter INTEGER DEFAULT 0,
            url_button_filter INTEGER DEFAULT 0,
            arabic_char_filter INTEGER DEFAULT 0,
            badwords_filter INTEGER DEFAULT 0,
            rules_text TEXT DEFAULT NULL,
            owner_id INTEGER DEFAULT NULL
        )
    """, (DEFAULT_CAPTCHA_TIME, DEFAULT_WARN_LIMIT, DEFAULT_FLOOD_LIMIT))

    # جدول users - برای ذخیره اطلاعات پایه کاربران
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            is_bot INTEGER
        )
    """)

    # جدول group_members - برای ذخیره نقش کاربران در هر گروه
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER,
            user_id INTEGER,
            role TEXT DEFAULT 'member', -- owner, bot_admin, moderator, member
            PRIMARY KEY (group_id, user_id)
        )
    """)

    # جدول warnings - برای ذخیره اخطارهای کاربران
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            admin_id INTEGER,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # جدول mutes - برای ذخیره کاربران سکوت شده
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mutes (
            group_id INTEGER,
            user_id INTEGER,
            until_date DATETIME, -- NULL برای سکوت دائم
            is_permanent INTEGER DEFAULT 0,
            PRIMARY KEY (group_id, user_id)
        )
    """)

    # جدول bans - برای ذخیره کاربران مسدود شده
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bans (
            group_id INTEGER,
            user_id INTEGER,
            until_date DATETIME, -- NULL برای مسدودیت دائم
            is_permanent INTEGER DEFAULT 0,
            PRIMARY KEY (group_id, user_id)
        )
    """)

    # جدول bad_words - برای ذخیره کلمات ممنوعه هر گروه
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bad_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            word TEXT,
            UNIQUE (group_id, word)
        )
    """)

    # جدول captcha_pending - برای کاربران منتظر حل کپچا
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS captcha_pending (
            group_id INTEGER,
            user_id INTEGER,
            captcha_text TEXT,
            message_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, user_id)
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

# --- توابع CRUD برای جدول groups ---
def insert_or_update_group(group_id, owner_id=None):
    """گروه را در دیتابیس ثبت یا به‌روزرسانی می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
    group = cursor.fetchone()
    if not group:
        # اگر گروه جدید است، آن را اضافه می‌کند. owner_id را فقط یکبار تنظیم می‌کند.
        cursor.execute(
            "INSERT INTO groups (id, owner_id) VALUES (?, ?)", (group_id, owner_id)
        )
        logger.info(f"New group {group_id} registered in database by owner {owner_id}.")
    elif owner_id and not group[14]:  # اگر owner_id قبلا تنظیم نشده
        cursor.execute("UPDATE groups SET owner_id = ? WHERE id = ?", (owner_id, group_id))
        logger.info(f"Owner {owner_id} set for existing group {group_id}.")
    conn.commit()
    conn.close()

def get_group_settings(group_id):
    """تنظیمات یک گروه را از دیتابیس دریافت می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
    settings = cursor.fetchone()
    conn.close()
    if settings:
        # Map column names to values for easier access
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, settings))
    return None

def update_group_setting(group_id, setting_name, setting_value):
    """یک تنظیم خاص گروه را به‌روزرسانی می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"UPDATE groups SET {setting_name} = ? WHERE id = ?",
            (setting_value, group_id),
        )
        conn.commit()
        logger.info(f"Group {group_id} setting '{setting_name}' updated to '{setting_value}'.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating group setting {setting_name} for {group_id}: {e}")
        return False
    finally:
        conn.close()

# --- توابع CRUD برای جدول users ---
def insert_or_update_user(user):
    """کاربر را در دیتابیس ثبت یا به‌روزرسانی می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user.id,))
    existing_user = cursor.fetchone()
    if existing_user:
        cursor.execute(
            "UPDATE users SET first_name = ?, last_name = ?, username = ?, is_bot = ? WHERE id = ?",
            (user.first_name, user.last_name, user.username, int(user.is_bot), user.id),
        )
        logger.debug(f"User {user.id} updated.")
    else:
        cursor.execute(
            "INSERT INTO users (id, first_name, last_name, username, is_bot) VALUES (?, ?, ?, ?, ?)",
            (user.id, user.first_name, user.last_name, user.username, int(user.is_bot)),
        )
        logger.info(f"User {user.id} registered.")
    conn.commit()
    conn.close()

def get_user_data(user_id):
    """اطلاعات یک کاربر را دریافت می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    if user_data:
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, user_data))
    return None

# --- توابع CRUD برای جدول group_members (مدیریت نقش‌ها) ---
def set_user_role(group_id, user_id, role):
    """نقش یک کاربر را در گروه تنظیم می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)",
            (group_id, user_id, role),
        )
        conn.commit()
        logger.info(f"User {user_id} role set to {role} in group {group_id}.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error setting role for user {user_id} in group {group_id}: {e}")
        return False
    finally:
        conn.close()

def get_user_role(group_id, user_id):
    """نقش یک کاربر را در گروه دریافت می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )
    role = cursor.fetchone()
    conn.close()
    return role[0] if role else ROLE_MEMBER

def get_bot_admins(group_id):
    """لیست ادمین‌ها و مدیران ربات در یک گروه را برمی‌گرداند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, role FROM group_members WHERE group_id = ? AND (role = ? OR role = ? OR role = ?)",
        (group_id, ROLE_OWNER, ROLE_BOT_ADMIN, ROLE_MODERATOR),
    )
    admins = cursor.fetchall()
    conn.close()
    return admins

# --- توابع CRUD برای جدول warnings ---
def add_warning(group_id, user_id, admin_id, reason):
    """یک اخطار جدید برای کاربر ثبت می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO warnings (group_id, user_id, admin_id, reason) VALUES (?, ?, ?, ?)",
        (group_id, user_id, admin_id, reason),
    )
    conn.commit()
    conn.close()
    logger.info(f"Warning added for user {user_id} in group {group_id} by {admin_id}. Reason: {reason}")

def get_warnings_count(group_id, user_id):
    """تعداد اخطارهای یک کاربر در گروه را برمی‌گرداند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM warnings WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_warnings(group_id, user_id):
    """تمام جزئیات اخطارهای یک کاربر را برمی‌گرداند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT admin_id, reason, timestamp FROM warnings WHERE group_id = ? AND user_id = ? ORDER BY timestamp DESC",
        (group_id, user_id),
    )
    warnings = cursor.fetchall()
    conn.close()
    return warnings

def remove_last_warning(group_id, user_id):
    """آخرین اخطار کاربر را حذف می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM warnings WHERE group_id = ? AND user_id = ? ORDER BY timestamp DESC LIMIT 1",
        (group_id, user_id),
    )
    last_warn_id = cursor.fetchone()
    if last_warn_id:
        cursor.execute("DELETE FROM warnings WHERE id = ?", (last_warn_id[0],))
        conn.commit()
        logger.info(f"Last warning removed for user {user_id} in group {group_id}.")
        conn.close()
        return True
    conn.close()
    return False

def reset_warnings(group_id, user_id):
    """تمامی اخطارهای یک کاربر را حذف می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM warnings WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )
    conn.commit()
    conn.close()
    logger.info(f"All warnings reset for user {user_id} in group {group_id}.")

# --- توابع CRUD برای جدول mutes و bans ---
def add_mute(group_id, user_id, until_date=None, is_permanent=False):
    """کاربر را سکوت می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO mutes (group_id, user_id, until_date, is_permanent) VALUES (?, ?, ?, ?)",
        (group_id, user_id, until_date, int(is_permanent)),
    )
    conn.commit()
    conn.close()
    logger.info(f"User {user_id} muted in group {group_id}. Permanent: {is_permanent}, Until: {until_date}")

def is_muted(group_id, user_id):
    """بررسی می‌کند که آیا کاربر سکوت شده است یا خیر."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT until_date, is_permanent FROM mutes WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )
    mute_info = cursor.fetchone()
    conn.close()
    if mute_info:
        until_date_str, is_permanent = mute_info
        if is_permanent:
            return True
        if until_date_str:
            until_datetime = datetime.datetime.fromisoformat(until_date_str)
            return datetime.datetime.now() < until_datetime
    return False

def remove_mute(group_id, user_id):
    """سکوت کاربر را برمی‌دارد."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM mutes WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )
    conn.commit()
    conn.close()
    logger.info(f"Mute removed for user {user_id} in group {group_id}.")

def add_ban(group_id, user_id, until_date=None, is_permanent=False):
    """کاربر را مسدود می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO bans (group_id, user_id, until_date, is_permanent) VALUES (?, ?, ?, ?)",
        (group_id, user_id, until_date, int(is_permanent)),
    )
    conn.commit()
    conn.close()
    logger.info(f"User {user_id} banned in group {group_id}. Permanent: {is_permanent}, Until: {until_date}")

def is_banned(group_id, user_id):
    """بررسی می‌کند که آیا کاربر مسدود شده است یا خیر."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT until_date, is_permanent FROM bans WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )
    ban_info = cursor.fetchone()
    conn.close()
    if ban_info:
        until_date_str, is_permanent = ban_info
        if is_permanent:
            return True
        if until_date_str:
            until_datetime = datetime.datetime.fromisoformat(until_date_str)
            return datetime.datetime.now() < until_datetime
    return False

def remove_ban(group_id, user_id):
    """مسدودیت کاربر را برمی‌دارد."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM bans WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )
    conn.commit()
    conn.close()
    logger.info(f"Ban removed for user {user_id} in group {group_id}.")

# --- توابع CRUD برای جدول bad_words ---
def add_bad_word(group_id, word):
    """یک کلمه ممنوعه جدید به گروه اضافه می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO bad_words (group_id, word) VALUES (?, ?)",
            (group_id, word.lower()),
        )
        conn.commit()
        logger.info(f"Bad word '{word}' added to group {group_id}.")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Bad word '{word}' already exists in group {group_id}.")
        return False
    finally:
        conn.close()

def remove_bad_word(group_id, word):
    """یک کلمه ممنوعه را از گروه حذف می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM bad_words WHERE group_id = ? AND word = ?",
        (group_id, word.lower()),
    )
    changes = conn.total_changes
    conn.commit()
    conn.close()
    if changes > 0:
        logger.info(f"Bad word '{word}' removed from group {group_id}.")
        return True
    return False

def get_bad_words(group_id):
    """لیست کلمات ممنوعه یک گروه را برمی‌گرداند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT word FROM bad_words WHERE group_id = ?", (group_id,)
    )
    words = [row[0] for row in cursor.fetchall()]
    conn.close()
    return words

# --- توابع CRUD برای جدول captcha_pending ---
def add_captcha_pending_user(group_id, user_id, captcha_text, message_id):
    """کاربر را به لیست منتظران کپچا اضافه می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO captcha_pending (group_id, user_id, captcha_text, message_id) VALUES (?, ?, ?, ?)",
        (group_id, user_id, captcha_text, message_id),
    )
    conn.commit()
    conn.close()
    logger.info(f"User {user_id} added to captcha pending list for group {group_id}.")

def get_captcha_pending_user(group_id, user_id):
    """اطلاعات کاربر منتظر کپچا را دریافت می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT captcha_text, message_id, timestamp FROM captcha_pending WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )
    info = cursor.fetchone()
    conn.close()
    return info

def remove_captcha_pending_user(group_id, user_id):
    """کاربر را از لیست منتظران کپچا حذف می‌کند."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM captcha_pending WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )
    conn.commit()
    conn.close()
    logger.info(f"User {user_id} removed from captcha pending list for group {group_id}.")

# --- 5. توابع کمکی عمومی ---
user_flood_data = {} # { (chat_id, user_id): [(timestamp, message_id), ...] }

async def check_flood(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, chat_id):
    """بررسی و اعمال محدودیت سیل پیام."""
    if (chat_id, user_id) not in user_flood_data:
        user_flood_data[(chat_id, user_id)] = []

    current_time = datetime.datetime.now()
    # حذف پیام‌های قدیمی‌تر از بازه زمانی flood_limit
    user_flood_data[(chat_id, user_id)] = [
        (ts, msg_id) for ts, msg_id in user_flood_data[(chat_id, user_id)]
        if (current_time - ts).total_seconds() < 5 # 5 ثانیه بازه پیش‌فرض برای بررسی
    ]

    user_flood_data[(chat_id, user_id)].append((current_time, update.message.message_id))

    settings = get_group_settings(chat_id)
    if settings and settings['flood_status'] == 1:
        flood_limit = settings.get('flood_limit', DEFAULT_FLOOD_LIMIT)
        if len(user_flood_data[(chat_id, user_id)]) > flood_limit:
            logger.warning(f"Flood detected for user {user_id} in group {chat_id}.")
            user_mention = await format_user_mention(update.effective_user)
            try:
                # حذف تمامی پیام‌های کاربر در بازه زمانی اخیر برای پاکسازی
                for _, msg_id_to_delete in user_flood_data[(chat_id, user_id)]:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id_to_delete)
                    except Exception as e:
                        logger.error(f"Failed to delete message {msg_id_to_delete} for flood control: {e}")
                user_flood_data[(chat_id, user_id)] = [] # پاک کردن لیست بعد از حذف

                # اعمال محدودیت (مثلاً mute موقت)
                await restrict_chat_member_wrapper(chat_id, user_id, ChatPermissions(can_send_messages=False), until_date=datetime.datetime.now() + datetime.timedelta(minutes=5))
                await update.message.reply_text(
                    MESSAGES["flood_detected"].format(user_mention=user_mention, action="برای 5 دقیقه سکوت شد."),
                    parse_mode=ParseMode.MARKDOWN
                )
                add_mute(chat_id, user_id, until_date=(datetime.datetime.now() + datetime.timedelta(minutes=5)).isoformat())

            except Exception as e:
                logger.error(f"Failed to restrict user {user_id} for flood: {e}")
                await update.message.reply_text("خطا در اعمال محدودیت برای کاربر متخلف.")
            return True
    return False


async def format_user_mention(user):
    """یک کاربر را به صورت قابل کلیک (mention) فرمت می‌کند."""
    if user.username:
        return f"@{user.username}"
    return f"[{user.first_name}](tg://user?id={user.id})"

def time_delta_to_string(td: datetime.timedelta):
    """یک شیء timedelta را به رشته‌ای قابل فهم تبدیل می‌کند."""
    seconds = int(td.total_seconds())
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = []
    if days:
        parts.append(f"{days} روز")
    if hours:
        parts.append(f"{hours} ساعت")
    if minutes:
        parts.append(f"{minutes} دقیقه")
    if seconds:
        parts.append(f"{seconds} ثانیه")

    if not parts:
        return "کمتر از یک ثانیه"
    return " و ".join(parts)

async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE, args):
    """کاربر هدف را از ریپلای یا آرگومان‌ها (ID/Username) پیدا می‌کند."""
    target_user = None
    target_user_id = None
    target_chat_member = None

    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id
    elif args:
        user_input = args[0]
        if user_input.isdigit():
            target_user_id = int(user_input)
        elif user_input.startswith("@"):
            try:
                # برای یافتن کاربر با نام کاربری، باید اطلاعات چت ممبر را از خود تلگرام بگیریم
                # این کار کمی پیچیده است و ممکن است همیشه کار نکند اگر کاربر در گروه نباشد یا نام کاربری خصوصی داشته باشد
                chat_members = await context.bot.get_chat_members(chat_id=update.effective_chat.id)
                for member in chat_members:
                    if member.user.username == user_input[1:]:
                        target_user = member.user
                        target_user_id = target_user.id
                        break
                if not target_user: # اگر با نام کاربری پیدا نشد
                    await update.message.reply_text(MESSAGES["user_not_found"])
                    return None, None
            except Exception as e:
                logger.error(f"Error fetching chat members by username: {e}")
                await update.message.reply_text(MESSAGES["user_not_found"])
                return None, None
        else:
            await update.message.reply_text(MESSAGES["no_reply_or_id"])
            return None, None
    else:
        await update.message.reply_text(MESSAGES["no_reply_or_id"])
        return None, None

    if target_user_id:
        try:
            target_chat_member = await context.bot.get_chat_member(chat_id=update.effective_chat.id, user_id=target_user_id)
            target_user = target_chat_member.user
        except Exception as e:
            logger.error(f"Could not get chat member for user ID {target_user_id}: {e}")
            await update.message.reply_text(MESSAGES["user_not_found"])
            return None, None
    
    insert_or_update_user(target_user) # مطمئن می‌شویم کاربر در دیتابیس ثبت شده است
    return target_user, target_chat_member

async def restrict_chat_member_wrapper(chat_id, user_id, permissions, until_date=None):
    """
    تابعی برای اعمال محدودیت‌ها به کاربر، با مدیریت خطاهای رایج.
    """
    try:
        if until_date:
            if isinstance(until_date, datetime.datetime):
                until_date_timestamp = int(until_date.timestamp())
            else: # Assume it's an ISO format string
                until_date_timestamp = int(datetime.datetime.fromisoformat(until_date).timestamp())
        else:
            until_date_timestamp = None

        return await application.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions,
            until_date=until_date_timestamp
        )
    except Exception as e:
        logger.error(f"Failed to restrict user {user_id} in chat {chat_id}: {e}")
        # این خطاها را می‌توان به پیام‌های کاربر تبدیل کرد
        if "Can't remove chat owner" in str(e) or "Can't remove a chat administrator" in str(e):
            raise ValueError(MESSAGES["telegram_admin_restricted"])
        elif "bot is not a supergroup administrator" in str(e) or "not enough rights to restrict" in str(e):
            raise ValueError(MESSAGES["bot_missing_permission_restrict"])
        else:
            raise ValueError("خطای ناشناخته در اعمال محدودیت.")


# --- 6. دکوراتور برای مدیریت دسترسی ---
def restricted(roles: list):
    """
    دکوراتوری برای محدود کردن دسترسی به دستورات بر اساس نقش کاربر.
    نقش‌ها: owner, bot_admin, moderator, member
    ترتیب قدرت: owner > bot_admin > moderator > member
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.effective_chat or update.effective_chat.type not in ["group", "supergroup"]:
                await update.message.reply_text(MESSAGES["not_group"])
                return

            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            chat_title = update.effective_chat.title

            # اطمینان حاصل کنید که گروه و کاربر در دیتابیس ثبت شده‌اند
            insert_or_update_group(chat_id)
            insert_or_update_user(update.effective_user)

            # نقش‌های تلگرامی
            try:
                bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
                if not bot_member.status == ChatMemberStatus.ADMINISTRATOR:
                    await update.message.reply_text(MESSAGES["bot_not_admin"])
                    logger.warning(f"Bot is not admin in group {chat_id} for command {func.__name__}")
                    return
            except Exception as e:
                logger.error(f"Could not check bot admin status in group {chat_id}: {e}")
                await update.message.reply_text("خطا در بررسی وضعیت ادمین ربات.")
                return

            # بررسی نقش کاربر در دیتابیس
            user_db_role = get_user_role(chat_id, user_id)
            group_settings = get_group_settings(chat_id)
            group_owner_id = group_settings.get('owner_id')

            # اگر ربات برای اولین بار اضافه شده باشد یا owner_id ست نشده باشد
            if not group_owner_id and update.effective_chat.id == chat_id:
                # اولین کسی که ربات را ادمین کرده یا دستوری را بعد از اضافه شدن ربات می‌فرستد مالک ربات در آن گروه می‌شود
                set_user_role(chat_id, user_id, ROLE_OWNER)
                update_group_setting(chat_id, 'owner_id', user_id)
                user_db_role = ROLE_OWNER
                logger.info(f"User {user_id} set as OWNER for group {chat_id}.")

            # سطح دسترسی
            role_hierarchy = {
                ROLE_MEMBER: 0,
                ROLE_MODERATOR: 1,
                ROLE_BOT_ADMIN: 2,
                ROLE_OWNER: 3,
            }

            # سطح دسترسی کاربر تلگرامی
            try:
                member = await context.bot.get_chat_member(chat_id, user_id)
                is_telegram_admin = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
            except Exception as e:
                logger.error(f"Could not get chat member status for user {user_id} in group {chat_id}: {e}")
                is_telegram_admin = False # Fallback to false if cannot get member status

            # بالاترین سطح دسترسی کاربر (چه تلگرام چه ربات)
            user_effective_role_level = role_hierarchy[user_db_role]
            if is_telegram_admin:
                user_effective_role_level = max(user_effective_role_level, role_hierarchy[ROLE_MODERATOR]) # ادمین تلگرام حداقل دسترسی Moderator ربات را دارد

            # اگر کاربر owner تلگرام باشد، نقش ربات را نیز owner در نظر می‌گیریم
            if member.status == ChatMemberStatus.OWNER:
                user_effective_role_level = max(user_effective_role_level, role_hierarchy[ROLE_OWNER])
                if user_db_role != ROLE_OWNER:
                    set_user_role(chat_id, user_id, ROLE_OWNER)
                    user_db_role = ROLE_OWNER

            # بررسی دسترسی
            required_role_level = max(role_hierarchy[r] for r in roles)

            if user_effective_role_level >= required_role_level:
                return await func(update, context, *args, **kwargs)
            else:
                await update.message.reply_text(MESSAGES["no_permissions"])
                logger.warning(f"User {user_id} in group {chat_id} tried to use {func.__name__} but has insufficient permissions (current: {user_db_role}, required: {roles}).")
                return
        return wrapper
    return decorator

# --- 7. Handler Functions (بخش اصلی پیاده‌سازی ویژگی‌ها) ---

# --- دسترسی: همه ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /start."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    insert_or_update_user(update.effective_user)

    if update.effective_chat.type == "private":
        await update.message.reply_text(MESSAGES["start_private"])
        logger.info(f"User {user_id} started bot in private chat.")
    else:
        await update.message.reply_text(MESSAGES["start_group"])
        insert_or_update_group(chat_id, user_id) # اولین کسی که در گروه استارت میزند مالک ربات در گروه میشود
        logger.info(f"Bot started in group {chat_id} by user {user_id}.")

@restricted(roles=[ROLE_MEMBER]) # همه اعضا اجازه دیدن id خود را دارند
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /id."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        MESSAGES["user_id"].format(user_id=user_id) + "\n" + MESSAGES["group_id"].format(chat_id=chat_id),
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info(f"User {user_id} requested ID in group {chat_id}.")

@restricted(roles=[ROLE_MEMBER])
async def get_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /info."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    target_user, _ = await get_target_user(update, context, context.args)
    if not target_user:
        target_user = update.effective_user

    user_info_data = get_user_data(target_user.id)
    if user_info_data:
        is_bot_str = "بله" if user_info_data['is_bot'] else "خیر"
        await update.message.reply_text(
            MESSAGES["user_info"].format(
                user_id=user_info_data['id'],
                first_name=user_info_data['first_name'] or "",
                last_name=user_info_data['last_name'] or "",
                username=user_info_data['username'] or "ندارد",
                is_bot=is_bot_str
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"User {user_id} requested info for user {target_user.id} in group {chat_id}.")
    else:
        await update.message.reply_text(MESSAGES["user_not_found"])

@restricted(roles=[ROLE_MEMBER])
async def get_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش قوانین گروه."""
    chat_id = update.effective_chat.id
    group_settings = get_group_settings(chat_id)
    if group_settings and group_settings.get('rules_text'):
        await update.message.reply_text(
            MESSAGES["rules_message"].format(
                group_name=update.effective_chat.title,
                rules_text=group_settings['rules_text']
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"User {update.effective_user.id} requested rules in group {chat_id}.")
    else:
        await update.message.reply_text(MESSAGES["rules_not_set"])
        logger.info(f"Rules not set for group {chat_id}.")

# --- دسترسی: ادمین‌های ربات ---
@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم قوانین گروه."""
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text(MESSAGES["set_rules_usage"])
        return

    rules_text = " ".join(context.args)
    if update_group_setting(chat_id, 'rules_text', rules_text):
        await update.message.reply_text(MESSAGES["rules_set"])
        logger.info(f"Rules set for group {chat_id} by {update.effective_user.id}.")
    else:
        await update.message.reply_text("خطا در تنظیم قوانین.")


@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def set_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم پیام خوش‌آمدگویی."""
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text(MESSAGES["set_welcome_usage"])
        return

    welcome_msg = " ".join(context.args)
    if update_group_setting(chat_id, 'welcome_message', welcome_msg):
        await update.message.reply_text(MESSAGES["welcome_set"])
        logger.info(f"Welcome message set for group {chat_id} by {update.effective_user.id}.")
    else:
        await update.message.reply_text("خطا در تنظیم پیام خوش‌آمدگویی.")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فعال/غیرفعال کردن پیام خوش‌آمدگویی."""
    chat_id = update.effective_chat.id
    if not context.args or context.args[0] not in ["on", "off"]:
        await update.message.reply_text("لطفاً `on` یا `off` را مشخص کنید. مثال: `/welcome on`")
        return

    status = 1 if context.args[0] == "on" else 0
    status_text = "فعال" if status == 1 else "غیرفعال"
    if update_group_setting(chat_id, 'welcome_status', status):
        await update.message.reply_text(MESSAGES["welcome_status_changed"].format(status=status_text))
        logger.info(f"Welcome status changed to {status_text} for group {chat_id} by {update.effective_user.id}.")
    else:
        await update.message.reply_text("خطا در تغییر وضعیت خوش‌آمدگویی.")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_del_join_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فعال/غیرفعال کردن حذف پیام‌های ورود/خروج."""
    chat_id = update.effective_chat.id
    if not context.args or context.args[0] not in ["on", "off"]:
        await update.message.reply_text("لطفاً `on` یا `off` را مشخص کنید. مثال: `/deljoinmsg on`")
        return

    status = 1 if context.args[0] == "on" else 0
    status_text = "فعال" if status == 1 else "غیرفعال"
    if update_group_setting(chat_id, 'del_join_msg_status', status):
        await update.message.reply_text(MESSAGES["deljoinmsg_status_changed"].format(status=status_text))
        logger.info(f"Delete join message status changed to {status_text} for group {chat_id} by {update.effective_user.id}.")
    else:
        await update.message.reply_text("خطا در تغییر وضعیت حذف پیام‌های ورود/خروج.")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def set_warn_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم تعداد اخطار تا اقدام خودکار."""
    chat_id = update.effective_chat.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("لطفاً یک عدد برای محدودیت اخطار وارد کنید. مثال: `/warnlimit 3`")
        return
    limit = int(context.args[0])
    if limit <= 0:
        await update.message.reply_text("محدودیت اخطار باید عددی مثبت باشد.")
        return

    if update_group_setting(chat_id, 'warn_limit', limit):
        await update.message.reply_text(MESSAGES["warn_limit_set"].format(limit=limit))
        logger.info(f"Warn limit set to {limit} for group {chat_id} by {update.effective_user.id}.")
    else:
        await update.message.reply_text("خطا در تنظیم محدودیت اخطار.")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_flood_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فعال/غیرفعال کردن کنترل سیل پیام."""
    chat_id = update.effective_chat.id
    if not context.args or context.args[0] not in ["on", "off"]:
        await update.message.reply_text("لطفاً `on` یا `off` را مشخص کنید. مثال: `/flood on`")
        return

    status = 1 if context.args[0] == "on" else 0
    status_text = "فعال" if status == 1 else "غیرفعال"
    if update_group_setting(chat_id, 'flood_status', status):
        await update.message.reply_text(MESSAGES["flood_status_changed"].format(status=status_text))
        logger.info(f"Flood control status changed to {status_text} for group {chat_id} by {update.effective_user.id}.")
    else:
        await update.message.reply_text("خطا در تغییر وضعیت کنترل سیل پیام.")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def set_flood_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم محدودیت سیل پیام (تعداد پیام)."""
    chat_id = update.effective_chat.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("لطفاً یک عدد برای محدودیت سیل پیام وارد کنید. مثال: `/setfloodlimit 5`")
        return

    limit = int(context.args[0])
    if limit <= 0:
        await update.message.reply_text("محدودیت سیل پیام باید عددی مثبت باشد.")
        return

    # Interval is currently hardcoded to 5 seconds in check_flood, for simplicity in single file.
    # In a real app, this would also be configurable.
    interval_seconds = 5

    if update_group_setting(chat_id, 'flood_limit', limit):
        await update.message.reply_text(MESSAGES["flood_limit_set"].format(limit=limit, interval=interval_seconds))
        logger.info(f"Flood limit set to {limit} messages per {interval_seconds}s for group {chat_id} by {update.effective_user.id}.")
    else:
        await update.message.reply_text("خطا در تنظیم محدودیت سیل پیام.")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فعال/غیرفعال کردن سیستم کپچا."""
    chat_id = update.effective_chat.id
    if not context.args or context.args[0] not in ["on", "off"]:
        await update.message.reply_text("لطفاً `on` یا `off` را مشخص کنید. مثال: `/captcha on`")
        return

    status = 1 if context.args[0] == "on" else 0
    status_text = "فعال" if status == 1 else "غیرفعال"
    if update_group_setting(chat_id, 'captcha_status', status):
        await update.message.reply_text(MESSAGES["captcha_status_changed"].format(status=status_text))
        logger.info(f"Captcha status changed to {status_text} for group {chat_id} by {update.effective_user.id}.")
    else:
        await update.message.reply_text("خطا در تغییر وضعیت کپچا.")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def set_captcha_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم زمان پاسخ به کپچا."""
    chat_id = update.effective_chat.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("لطفاً یک عدد بر حسب ثانیه برای زمان کپچا وارد کنید. مثال: `/setcaptchatime 60`")
        return

    captcha_time = int(context.args[0])
    if captcha_time <= 0:
        await update.message.reply_text("زمان کپچا باید عددی مثبت باشد.")
        return

    if update_group_setting(chat_id, 'captcha_time', captcha_time):
        await update.message.reply_text(MESSAGES["captcha_time_set"].format(time=captcha_time))
        logger.info(f"Captcha time set to {captcha_time}s for group {chat_id} by {update.effective_user.id}.")
    else:
        await update.message.reply_text("خطا در تنظیم زمان کپچا.")

# --- هندلرهای فیلتر محتوا (Lock/Unlock) ---
# این توابع به شدت تکراری هستند و برای افزایش خطوط کد مفیدند.
async def _toggle_filter(update: Update, context: ContextTypes.DEFAULT_TYPE, filter_type: str):
    """تابع کمکی برای فعال/غیرفعال کردن فیلترها."""
    chat_id = update.effective_chat.id
    if not context.args or context.args[0] not in ["on", "off"]:
        await update.message.reply_text(f"لطفاً `on` یا `off` را مشخص کنید. مثال: `/{filter_type}s on`")
        return

    status = 1 if context.args[0] == "on" else 0
    status_text = "فعال" if status == 1 else "غیرفعال"
    setting_name = f"{filter_type}_filter"
    if update_group_setting(chat_id, setting_name, status):
        await update.message.reply_text(MESSAGES["filter_status_changed"].format(filter_type=filter_type, status=status_text))
        logger.info(f"Filter '{filter_type}' changed to {status_text} for group {chat_id} by {update.effective_user.id}.")
    else:
        await update.message.reply_text(f"خطا در تغییر وضعیت فیلتر {filter_type}.")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_links_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "link")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_photos_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "photo")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_videos_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "video")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_documents_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "document")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_stickers_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "sticker")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_gifs_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "gif")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_forwards_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "forward")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_voice_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "voice")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_video_notes_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "video_note")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_url_buttons_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "url_button")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_arabic_chars_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "arabic_char")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def toggle_badwords_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _toggle_filter(update, context, "badwords")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def add_badword_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """افزودن کلمه به لیست کلمات ممنوعه."""
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text(MESSAGES["badword_usage"])
        return
    word = context.args[0].lower()
    if add_bad_word(chat_id, word):
        await update.message.reply_text(MESSAGES["badword_added"].format(word=word))
        logger.info(f"User {update.effective_user.id} added bad word '{word}' to group {chat_id}.")
    else:
        await update.message.reply_text(MESSAGES["badword_already_exists"].format(word=word))

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def remove_badword_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف کلمه از لیست کلمات ممنوعه."""
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text(MESSAGES["badword_usage"])
        return
    word = context.args[0].lower()
    if remove_bad_word(chat_id, word):
        await update.message.reply_text(MESSAGES["badword_removed"].format(word=word))
        logger.info(f"User {update.effective_user.id} removed bad word '{word}' from group {chat_id}.")
    else:
        await update.message.reply_text(MESSAGES["badword_not_found"].format(word=word))

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def list_badwords_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لیست کلمات ممنوعه گروه را نمایش می‌دهد."""
    chat_id = update.effective_chat.id
    bad_words = get_bad_words(chat_id)
    global_bad_words = GLOBAL_BAD_WORDS # فرض می‌کنیم Global Bad Words هم قابل نمایش است
    
    response_text = "**کلمات ممنوعه گروه:**\n"
    if bad_words:
        response_text += "• " + "\n• ".join(bad_words) + "\n"
    else:
        response_text += "هیچ کلمه ممنوعه‌ای در این گروه تنظیم نشده است.\n"

    response_text += "\n**کلمات ممنوعه سراسری:**\n"
    if global_bad_words:
        response_text += "• " + "\n• ".join(global_bad_words)
    else:
        response_text += "هیچ کلمه ممنوعه‌ای به صورت سراسری تنظیم نشده است."
    
    await update.message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"User {update.effective_user.id} requested bad words list for group {chat_id}.")


@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def settings_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /settings برای نمایش پنل تنظیمات با دکمه‌های شیشه‌ای."""
    chat_id = update.effective_chat.id
    group_settings = get_group_settings(chat_id)
    if not group_settings:
        await update.message.reply_text(MESSAGES["group_not_found"])
        return

    # وضعیت‌ها را به فارسی تبدیل می‌کنیم
    def status_to_fa(status_int):
        return "✅ فعال" if status_int == 1 else "❌ غیرفعال"

    keyboard = [
        [
            InlineKeyboardButton(f"خوش‌آمدگویی: {status_to_fa(group_settings['welcome_status'])}", callback_data='toggle_welcome'),
            InlineKeyboardButton(f"حذف پیام ورود: {status_to_fa(group_settings['del_join_msg_status'])}", callback_data='toggle_deljoinmsg')
        ],
        [
            InlineKeyboardButton(f"کپچا: {status_to_fa(group_settings['captcha_status'])}", callback_data='toggle_captcha'),
            InlineKeyboardButton(f"کنترل سیل پیام: {status_to_fa(group_settings['flood_status'])}", callback_data='toggle_flood')
        ],
        [
            InlineKeyboardButton(f"فیلتر لینک: {status_to_fa(group_settings['link_filter'])}", callback_data='toggle_filter_link'),
            InlineKeyboardButton(f"فیلتر عکس: {status_to_fa(group_settings['photo_filter'])}", callback_data='toggle_filter_photo')
        ],
        [
            InlineKeyboardButton(f"فیلتر ویدئو: {status_to_fa(group_settings['video_filter'])}", callback_data='toggle_filter_video'),
            InlineKeyboardButton(f"فیلتر داکیومنت: {status_to_fa(group_settings['document_filter'])}", callback_data='toggle_filter_document')
        ],
        [
            InlineKeyboardButton(f"فیلتر استیکر: {status_to_fa(group_settings['sticker_filter'])}", callback_data='toggle_filter_sticker'),
            InlineKeyboardButton(f"فیلتر گیف: {status_to_fa(group_settings['gif_filter'])}", callback_data='toggle_filter_gif')
        ],
        [
            InlineKeyboardButton(f"فیلتر فوروارد: {status_to_fa(group_settings['forward_filter'])}", callback_data='toggle_filter_forward'),
            InlineKeyboardButton(f"فیلتر صوت: {status_to_fa(group_settings['voice_filter'])}", callback_data='toggle_filter_voice')
        ],
        [
            InlineKeyboardButton(f"فیلتر ویدئو نوت: {status_to_fa(group_settings['video_note_filter'])}", callback_data='toggle_filter_video_note'),
            InlineKeyboardButton(f"فیلتر دکمه URL: {status_to_fa(group_settings['url_button_filter'])}", callback_data='toggle_filter_url_button')
        ],
         [
            InlineKeyboardButton(f"فیلتر کاراکتر عربی: {status_to_fa(group_settings['arabic_char_filter'])}", callback_data='toggle_filter_arabic_char'),
            InlineKeyboardButton(f"فیلتر کلمات ممنوعه: {status_to_fa(group_settings['badwords_filter'])}", callback_data='toggle_filter_badwords')
        ],
        [
            InlineKeyboardButton("🔙 بستن پنل", callback_data='close_settings')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        MESSAGES["settings_panel"].format(group_name=update.effective_chat.title),
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info(f"User {update.effective_user.id} opened settings panel for group {chat_id}.")


async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای دکمه‌های شیشه‌ای پنل تنظیمات."""
    query = update.callback_query
    await query.answer() # پاسخ به کلیک کاربر برای حذف حالت لودینگ

    chat_id = query.message.chat.id
    user_id = query.from_user.id

    # بررسی دسترسی دوباره برای Callbacks
    member = await context.bot.get_chat_member(chat_id, user_id)
    user_db_role = get_user_role(chat_id, user_id)
    is_telegram_admin = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

    role_hierarchy = {
        ROLE_MEMBER: 0,
        ROLE_MODERATOR: 1,
        ROLE_BOT_ADMIN: 2,
        ROLE_OWNER: 3,
    }
    user_effective_role_level = role_hierarchy[user_db_role]
    if is_telegram_admin:
        user_effective_role_level = max(user_effective_role_level, role_hierarchy[ROLE_MODERATOR])

    if member.status == ChatMemberStatus.OWNER:
        user_effective_role_level = max(user_effective_role_level, role_hierarchy[ROLE_OWNER])

    required_role_level = role_hierarchy[ROLE_BOT_ADMIN] # برای تغییر تنظیمات نیاز به BOT_ADMIN یا OWNER داریم

    if user_effective_role_level < required_role_level:
        await query.message.reply_text(MESSAGES["no_permissions"])
        logger.warning(f"User {user_id} in group {chat_id} tried to change setting via callback but has insufficient permissions.")
        return

    data = query.data
    setting_name_map = {
        'toggle_welcome': 'welcome_status',
        'toggle_deljoinmsg': 'del_join_msg_status',
        'toggle_captcha': 'captcha_status',
        'toggle_flood': 'flood_status',
        'toggle_filter_link': 'link_filter',
        'toggle_filter_photo': 'photo_filter',
        'toggle_filter_video': 'video_filter',
        'toggle_filter_document': 'document_filter',
        'toggle_filter_sticker': 'sticker_filter',
        'toggle_filter_gif': 'gif_filter',
        'toggle_filter_forward': 'forward_filter',
        'toggle_filter_voice': 'voice_filter',
        'toggle_filter_video_note': 'video_note_filter',
        'toggle_filter_url_button': 'url_button_filter',
        'toggle_filter_arabic_char': 'arabic_char_filter',
        'toggle_filter_badwords': 'badwords_filter',
    }

    if data == 'close_settings':
        await query.edit_message_text("پنل تنظیمات بسته شد.")
        return

    if data in setting_name_map:
        setting_key = setting_name_map[data]
        group_settings = get_group_settings(chat_id)
        if not group_settings:
            await query.edit_message_text(MESSAGES["group_not_found"])
            return

        current_status = group_settings.get(setting_key)
        new_status = 1 if current_status == 0 else 0
        status_text = "فعال" if new_status == 1 else "غیرفعال"
        
        if update_group_setting(chat_id, setting_key, new_status):
            # اگر با موفقیت آپدیت شد، پیام پنل را نیز آپدیت می‌کنیم
            await query.edit_message_text(
                MESSAGES["settings_panel"].format(group_name=query.message.chat.title),
                reply_markup=await _create_settings_keyboard(chat_id), # بازسازی کیبورد با وضعیت جدید
                parse_mode=ParseMode.MARKDOWN
            )
            # و یک پیام کوچک به کاربر بدهیم
            filter_readable_name = data.replace('toggle_', '').replace('_filter', '').replace('_', ' ').capitalize()
            await query.answer(f"'{filter_readable_name}' به '{status_text}' تغییر یافت.", show_alert=False)
            logger.info(f"Setting '{setting_key}' for group {chat_id} changed to {new_status} by {user_id}.")
        else:
            await query.answer("خطا در تغییر تنظیمات.", show_alert=True)
            logger.error(f"Failed to update setting '{setting_key}' for group {chat_id} by {user_id}.")
    else:
        await query.answer("این عملیات پشتیبانی نمی‌شود.", show_alert=True)

async def _create_settings_keyboard(chat_id):
    """تابعی برای ساخت کیبورد تنظیمات با آخرین وضعیت‌ها."""
    group_settings = get_group_settings(chat_id)
    if not group_settings:
        return InlineKeyboardMarkup([]) # اگر گروه در دیتابیس نبود، کیبورد خالی برگردان
    
    def status_to_fa(status_int):
        return "✅ فعال" if status_int == 1 else "❌ غیرفعال"

    keyboard = [
        [
            InlineKeyboardButton(f"خوش‌آمدگویی: {status_to_fa(group_settings['welcome_status'])}", callback_data='toggle_welcome'),
            InlineKeyboardButton(f"حذف پیام ورود: {status_to_fa(group_settings['del_join_msg_status'])}", callback_data='toggle_deljoinmsg')
        ],
        [
            InlineKeyboardButton(f"کپچا: {status_to_fa(group_settings['captcha_status'])}", callback_data='toggle_captcha'),
            InlineKeyboardButton(f"کنترل سیل پیام: {status_to_fa(group_settings['flood_status'])}", callback_data='toggle_flood')
        ],
        [
            InlineKeyboardButton(f"فیلتر لینک: {status_to_fa(group_settings['link_filter'])}", callback_data='toggle_filter_link'),
            InlineKeyboardButton(f"فیلتر عکس: {status_to_fa(group_settings['photo_filter'])}", callback_data='toggle_filter_photo')
        ],
        [
            InlineKeyboardButton(f"فیلتر ویدئو: {status_to_fa(group_settings['video_filter'])}", callback_data='toggle_filter_video'),
            InlineKeyboardButton(f"فیلتر داکیومنت: {status_to_fa(group_settings['document_filter'])}", callback_data='toggle_filter_document')
        ],
        [
            InlineKeyboardButton(f"فیلتر استیکر: {status_to_fa(group_settings['sticker_filter'])}", callback_data='toggle_filter_sticker'),
            InlineKeyboardButton(f"فیلتر گیف: {status_to_fa(group_settings['gif_filter'])}", callback_data='toggle_filter_gif')
        ],
        [
            InlineKeyboardButton(f"فیلتر فوروارد: {status_to_fa(group_settings['forward_filter'])}", callback_data='toggle_filter_forward'),
            InlineKeyboardButton(f"فیلتر صوت: {status_to_fa(group_settings['voice_filter'])}", callback_data='toggle_filter_voice')
        ],
        [
            InlineKeyboardButton(f"فیلتر ویدئو نوت: {status_to_fa(group_settings['video_note_filter'])}", callback_data='toggle_filter_video_note'),
            InlineKeyboardButton(f"فیلتر دکمه URL: {status_to_fa(group_settings['url_button_filter'])}", callback_data='toggle_filter_url_button')
        ],
         [
            InlineKeyboardButton(f"فیلتر کاراکتر عربی: {status_to_fa(group_settings['arabic_char_filter'])}", callback_data='toggle_filter_arabic_char'),
            InlineKeyboardButton(f"فیلتر کلمات ممنوعه: {status_to_fa(group_settings['badwords_filter'])}", callback_data='toggle_filter_badwords')
        ],
        [
            InlineKeyboardButton("🔙 بستن پنل", callback_data='close_settings')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- دسترسی: ادمین‌های ربات و مدیران (Moderator) ---
@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اخطار دادن به کاربر."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    target_user, target_chat_member = await get_target_user(update, context, context.args)
    if not target_user:
        return

    if target_chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        await update.message.reply_text(MESSAGES["bot_cant_restrict_admin"])
        logger.warning(f"Admin {admin_id} tried to warn Telegram admin {target_user.id} in group {chat_id}.")
        return

    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "بدون دلیل"
    add_warning(chat_id, target_user.id, admin_id, reason)
    warnings_count = get_warnings_count(chat_id, target_user.id)

    user_mention = await format_user_mention(target_user)
    response_msg = MESSAGES["warn_success"].format(user_mention=user_mention, warnings_count=warnings_count)
    if reason != "بدون دلیل":
        response_msg += MESSAGES["warn_reason"].format(reason=reason)
    
    await update.message.reply_text(response_msg, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"User {target_user.id} warned in group {chat_id} by {admin_id}. Current warnings: {warnings_count}")

    # بررسی محدودیت اخطار
    group_settings = get_group_settings(chat_id)
    warn_limit = group_settings.get('warn_limit', DEFAULT_WARN_LIMIT)

    if warnings_count >= warn_limit:
        try:
            # اقدام خودکار: مثلاً mute موقت برای یک ساعت
            await restrict_chat_member_wrapper(chat_id, target_user.id, ChatPermissions(can_send_messages=False), until_date=datetime.datetime.now() + datetime.timedelta(hours=1))
            await update.message.reply_text(
                MESSAGES["warn_limit_reached"].format(user_mention=user_mention, warn_limit=warn_limit, action="برای یک ساعت سکوت شد"),
                parse_mode=ParseMode.MARKDOWN
            )
            add_mute(chat_id, target_user.id, until_date=(datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat())
            reset_warnings(chat_id, target_user.id) # اخطارها را بعد از اقدام خودکار ریست می‌کنیم
            logger.info(f"User {target_user.id} muted for 1 hour due to {warn_limit} warnings in group {chat_id}.")
        except ValueError as ve:
            await update.message.reply_text(f"خطا در اعمال محدودیت خودکار: {ve}", parse_mode=ParseMode.MARKDOWN)
            logger.error(f"Error auto-restricting user {target_user.id} after warn limit: {ve}")
        except Exception as e:
            await update.message.reply_text("خطا در اعمال محدودیت خودکار.")
            logger.error(f"Error auto-restricting user {target_user.id} after warn limit: {e}")


@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def unwarn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف آخرین اخطار کاربر."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    target_user, _ = await get_target_user(update, context, context.args)
    if not target_user:
        return

    if remove_last_warning(chat_id, target_user.id):
        user_mention = await format_user_mention(target_user)
        await update.message.reply_text(MESSAGES["unwarn_success"].format(user_mention=user_mention), parse_mode=ParseMode.MARKDOWN)
        logger.info(f"Last warning removed for user {target_user.id} in group {chat_id} by {admin_id}.")
    else:
        await update.message.reply_text(MESSAGES["no_warnings"].format(user_mention=await format_user_mention(target_user)), parse_mode=ParseMode.MARKDOWN)
        logger.info(f"No warnings to remove for user {target_user.id} in group {chat_id} by {admin_id}.")

@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def get_user_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مشاهده اخطارهای کاربر."""
    chat_id = update.effective_chat.id
    target_user, _ = await get_target_user(update, context, context.args)
    if not target_user:
        return

    warnings_list = get_all_warnings(chat_id, target_user.id)
    user_mention = await format_user_mention(target_user)

    if warnings_list:
        response_text = MESSAGES["warn_user_info"].format(user_mention=user_mention, warnings_count=len(warnings_list)) + "\n"
        for i, warn in enumerate(warnings_list):
            admin_data = get_user_data(warn[0])
            admin_mention = await format_user_mention(Update.de_json({"id": admin_data['id'], "first_name": admin_data['first_name'], "username": admin_data['username']}, context.bot)) if admin_data else f"ادمین ناشناس ({warn[0]})"
            response_text += f"• `{i+1}`. دلیل: `{warn[1]}` (توسط {admin_mention} در {warn[2]})\n"
        await update.message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN)
        logger.info(f"Admin {update.effective_user.id} viewed warnings for user {target_user.id} in group {chat_id}.")
    else:
        await update.message.reply_text(MESSAGES["no_warnings"].format(user_mention=user_mention), parse_mode=ParseMode.MARKDOWN)
        logger.info(f"No warnings found for user {target_user.id} in group {chat_id}.")

@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سکوت موقت یا دائم کاربر."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    target_user, target_chat_member = await get_target_user(update, context, context.args)
    if not target_user:
        return

    if target_chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        await update.message.reply_text(MESSAGES["bot_cant_restrict_admin"])
        logger.warning(f"Admin {admin_id} tried to mute Telegram admin {target_user.id} in group {chat_id}.")
        return

    if is_muted(chat_id, target_user.id):
        await update.message.reply_text(MESSAGES["already_muted"].format(user_mention=await format_user_mention(target_user)), parse_mode=ParseMode.MARKDOWN)
        return

    until_date = None
    is_permanent = True
    time_str = ""

    if len(context.args) > 1:
        time_arg = context.args[1]
        time_unit = time_arg[-1].lower()
        time_value = time_arg[:-1]
        if time_value.isdigit():
            time_value = int(time_value)
            now = datetime.datetime.now()
            if time_unit == 'm':
                until_date = now + datetime.timedelta(minutes=time_value)
                time_str = f"{time_value} دقیقه"
            elif time_unit == 'h':
                until_date = now + datetime.timedelta(hours=time_value)
                time_str = f"{time_value} ساعت"
            elif time_unit == 'd':
                until_date = now + datetime.timedelta(days=time_value)
                time_str = f"{time_value} روز"
            else:
                await update.message.reply_text(MESSAGES["invalid_time_format"])
                return
            is_permanent = False
        else:
            await update.message.reply_text(MESSAGES["invalid_time_format"])
            return

    try:
        await restrict_chat_member_wrapper(
            chat_id,
            target_user.id,
            ChatPermissions(can_send_messages=False), # فقط اجازه ارسال پیام حذف شود
            until_date=until_date
        )
        add_mute(chat_id, target_user.id, until_date.isoformat() if until_date else None, is_permanent)
        
        user_mention = await format_user_mention(target_user)
        if is_permanent:
            await update.message.reply_text(MESSAGES["mute_success_permanent"].format(user_mention=user_mention), parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(MESSAGES["mute_success_temp"].format(user_mention=user_mention, time_str=time_str), parse_mode=ParseMode.MARKDOWN)
        logger.info(f"User {target_user.id} muted in group {chat_id} by {admin_id}. Permanent: {is_permanent}, Until: {until_date}")

    except ValueError as ve:
        await update.message.reply_text(f"{ve}", parse_mode=ParseMode.MARKDOWN)
        logger.error(f"Error muting user {target_user.id} in group {chat_id}: {ve}")
    except Exception as e:
        await update.message.reply_text("خطا در سکوت کردن کاربر.")
        logger.error(f"Error muting user {target_user.id} in group {chat_id}: {e}")

@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رفع سکوت کاربر."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    target_user, _ = await get_target_user(update, context, context.args)
    if not target_user:
        return

    if not is_muted(chat_id, target_user.id):
        await update.message.reply_text(MESSAGES["not_muted"].format(user_mention=await format_user_mention(target_user)), parse_mode=ParseMode.MARKDOWN)
        return

    try:
        # برگرداندن به حالت عادی (ارسال همه انواع پیام)
        await restrict_chat_member_wrapper(
            chat_id,
            target_user.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False,
                can_manage_topics=False # فقط در فروم ها
            ),
            until_date=None
        )
        remove_mute(chat_id, target_user.id)

        user_mention = await format_user_mention(target_user)
        await update.message.reply_text(MESSAGES["unmute_success"].format(user_mention=user_mention), parse_mode=ParseMode.MARKDOWN)
        logger.info(f"User {target_user.id} unmuted in group {chat_id} by {admin_id}.")
    except ValueError as ve:
        await update.message.reply_text(f"{ve}", parse_mode=ParseMode.MARKDOWN)
        logger.error(f"Error unmuting user {target_user.id} in group {chat_id}: {ve}")
    except Exception as e:
        await update.message.reply_text("خطا در رفع سکوت کاربر.")
        logger.error(f"Error unmuting user {target_user.id} in group {chat_id}: {e}")

@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مسدود کردن موقت یا دائم کاربر."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    target_user, target_chat_member = await get_target_user(update, context, context.args)
    if not target_user:
        return

    if target_chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        await update.message.reply_text(MESSAGES["bot_cant_restrict_admin"])
        logger.warning(f"Admin {admin_id} tried to ban Telegram admin {target_user.id} in group {chat_id}.")
        return

    if is_banned(chat_id, target_user.id):
        await update.message.reply_text(MESSAGES["already_banned"].format(user_mention=await format_user_mention(target_user)), parse_mode=ParseMode.MARKDOWN)
        return

    until_date = None
    is_permanent = True
    time_str = ""

    if len(context.args) > 1:
        time_arg = context.args[1]
        time_unit = time_arg[-1].lower()
        time_value = time_arg[:-1]
        if time_value.isdigit():
            time_value = int(time_value)
            now = datetime.datetime.now()
            if time_unit == 'm':
                until_date = now + datetime.timedelta(minutes=time_value)
                time_str = f"{time_value} دقیقه"
            elif time_unit == 'h':
                until_date = now + datetime.timedelta(hours=time_value)
                time_str = f"{time_value} ساعت"
            elif time_unit == 'd':
                until_date = now + datetime.timedelta(days=time_value)
                time_str = f"{time_value} روز"
            else:
                await update.message.reply_text(MESSAGES["invalid_time_format"])
                return
            is_permanent = False
        else:
            await update.message.reply_text(MESSAGES["invalid_time_format"])
            return
    
    try:
        await context.bot.ban_chat_member(
            chat_id=chat_id,
            user_id=target_user.id,
            until_date=int(until_date.timestamp()) if until_date else None
        )
        add_ban(chat_id, target_user.id, until_date.isoformat() if until_date else None, is_permanent)
        
        user_mention = await format_user_mention(target_user)
        if is_permanent:
            await update.message.reply_text(MESSAGES["ban_success_permanent"].format(user_mention=user_mention), parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(MESSAGES["ban_success_temp"].format(user_mention=user_mention, time_str=time_str), parse_mode=ParseMode.MARKDOWN)
        logger.info(f"User {target_user.id} banned in group {chat_id} by {admin_id}. Permanent: {is_permanent}, Until: {until_date}")

    except Exception as e:
        await update.message.reply_text("خطا در مسدود کردن کاربر.")
        logger.error(f"Error banning user {target_user.id} in group {chat_id}: {e}")

@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رفع مسدودیت کاربر."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    target_user, _ = await get_target_user(update, context, context.args)
    if not target_user:
        return

    # تلگرام نیازی به بررسی is_banned ندارد، چون خود unban_chat_member اگر کاربر بن نباشد خطا نمی‌دهد.
    # اما برای حفظ اطلاعات دیتابیس خودمان و پیام‌های کاربر، این بررسی را انجام می‌دهیم.
    if not is_banned(chat_id, target_user.id):
        await update.message.reply_text(MESSAGES["not_banned"].format(user_mention=await format_user_mention(target_user)), parse_mode=ParseMode.MARKDOWN)
        return

    try:
        await context.bot.unban_chat_member(
            chat_id=chat_id,
            user_id=target_user.id
        )
        remove_ban(chat_id, target_user.id)

        user_mention = await format_user_mention(target_user)
        await update.message.reply_text(MESSAGES["unban_success"].format(user_mention=user_mention), parse_mode=ParseMode.MARKDOWN)
        logger.info(f"User {target_user.id} unbanned in group {chat_id} by {admin_id}.")
    except Exception as e:
        await update.message.reply_text("خطا در رفع مسدودیت کاربر.")
        logger.error(f"Error unbanning user {target_user.id} in group {chat_id}: {e}")

@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اخراج کاربر از گروه."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    target_user, target_chat_member = await get_target_user(update, context, context.args)
    if not target_user:
        return

    if target_chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        await update.message.reply_text(MESSAGES["bot_cant_restrict_admin"])
        logger.warning(f"Admin {admin_id} tried to kick Telegram admin {target_user.id} in group {chat_id}.")
        return
    
    try:
        await context.bot.ban_chat_member(
            chat_id=chat_id,
            user_id=target_user.id,
            until_date=int((datetime.datetime.now() + datetime.timedelta(seconds=30)).timestamp()) # بن موقت برای 30 ثانیه تا نتواند بلافاصله برگردد
        )
        # بعد از بن، دوباره آنبان می‌کنیم تا کاربر بتواند با لینک دعوت برگردد.
        await context.bot.unban_chat_member(
            chat_id=chat_id,
            user_id=target_user.id,
            only_if_banned=True # فقط اگر بن شده باشد
        )

        user_mention = await format_user_mention(target_user)
        await update.message.reply_text(MESSAGES["kick_success"].format(user_mention=user_mention), parse_mode=ParseMode.MARKDOWN)
        logger.info(f"User {target_user.id} kicked from group {chat_id} by {admin_id}.")
    except Exception as e:
        await update.message.reply_text("خطا در اخراج کاربر.")
        logger.error(f"Error kicking user {target_user.id} from group {chat_id}: {e}")

@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف پیام ریپلای شده."""
    chat_id = update.effective_chat.id
    if update.message.reply_to_message:
        try:
            await update.message.reply_to_message.delete()
            await update.message.delete() # حذف دستور /del
            logger.info(f"Message {update.message.reply_to_message.message_id} deleted by {update.effective_user.id} in group {chat_id}.")
            # await update.message.reply_text(MESSAGES["message_deleted"]) # برای جلوگیری از اسپم پیام تایید، این را غیرفعال می‌کنیم
        except Exception as e:
            if "not enough rights to delete a message" in str(e) or "Message can't be deleted" in str(e):
                await update.message.reply_text(MESSAGES["bot_missing_permission_delete"])
                logger.warning(f"Bot could not delete message in group {chat_id} due to permissions: {e}")
            else:
                await update.message.reply_text("خطا در حذف پیام.")
                logger.error(f"Error deleting message in group {chat_id}: {e}")
    else:
        await update.message.reply_text("لطفاً به پیامی که می‌خواهید حذف کنید ریپلای کنید.")

@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def pin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پین کردن پیام."""
    chat_id = update.effective_chat.id
    if update.message.reply_to_message:
        try:
            await context.bot.pin_chat_message(
                chat_id=chat_id,
                message_id=update.message.reply_to_message.message_id
            )
            await update.message.reply_text(MESSAGES["message_pinned"])
            logger.info(f"Message {update.message.reply_to_message.message_id} pinned by {update.effective_user.id} in group {chat_id}.")
        except Exception as e:
            if "not enough rights to pin a message" in str(e):
                await update.message.reply_text(MESSAGES["bot_missing_permission_pin"])
                logger.warning(f"Bot could not pin message in group {chat_id} due to permissions: {e}")
            else:
                await update.message.reply_text("خطا در پین کردن پیام.")
                logger.error(f"Error pinning message in group {chat_id}: {e}")
    else:
        await update.message.reply_text("لطفاً به پیامی که می‌خواهید پین کنید ریپلای کنید.")

@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def unpin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """آن‌پین کردن آخرین پیام."""
    chat_id = update.effective_chat.id
    try:
        await context.bot.unpin_chat_message(chat_id=chat_id)
        await update.message.reply_text(MESSAGES["message_unpinned"])
        logger.info(f"Last message unpinned by {update.effective_user.id} in group {chat_id}.")
    except Exception as e:
        if "not enough rights to unpin messages" in str(e):
            await update.message.reply_text(MESSAGES["bot_missing_permission_pin"])
            logger.warning(f"Bot could not unpin message in group {chat_id} due to permissions: {e}")
        else:
            await update.message.reply_text("خطا در آن‌پین کردن پیام.")
            logger.error(f"Error unpinning message in group {chat_id}: {e}")

@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def purge_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف N پیام آخر."""
    chat_id = update.effective_chat.id
    if not update.message.reply_to_message and not context.args:
        await update.message.reply_text("برای حذف پیام‌ها، به پیامی ریپلای کنید یا تعداد پیام‌ها را مشخص کنید. مثال: `/purge 10`")
        return

    try:
        if update.message.reply_to_message:
            # اگر ریپلای بود، از پیام ریپلای شده تا آخرین پیام را حذف کن
            first_msg_id = update.message.reply_to_message.message_id
            last_msg_id = update.message.message_id
            messages_to_delete = range(first_msg_id, last_msg_id + 1)
        elif context.args and context.args[0].isdigit():
            count = int(context.args[0])
            if count <= 0:
                await update.message.reply_text("تعداد پیام‌ها باید مثبت باشد.")
                return
            # از آخرین پیام به تعداد مشخص شده به عقب برگرد و حذف کن
            last_msg_id = update.message.message_id
            messages_to_delete = range(max(1, last_msg_id - count), last_msg_id + 1)
        else:
            await update.message.reply_text("تعداد نامعتبر است.")
            return

        deleted_count = 0
        for msg_id in reversed(messages_to_delete): # حذف از جدید به قدیم
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                deleted_count += 1
            except Exception as e:
                # برخی پیام‌ها ممکن است قابل حذف نباشند (مثلاً قدیمی‌تر از 48 ساعت)
                logger.warning(f"Failed to delete message {msg_id} in group {chat_id}: {e}")
        
        await update.message.reply_text(MESSAGES["purge_success"].format(count=deleted_count))
        logger.info(f"{deleted_count} messages purged by {update.effective_user.id} in group {chat_id}.")

    except Exception as e:
        if "not enough rights to delete a message" in str(e) or "Message can't be deleted" in str(e):
            await update.message.reply_text(MESSAGES["bot_missing_permission_delete"])
            logger.warning(f"Bot could not purge messages in group {chat_id} due to permissions: {e}")
        else:
            await update.message.reply_text("خطا در حذف گروهی پیام‌ها.")
            logger.error(f"Error purging messages in group {chat_id}: {e}")

@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def promote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارتقا کاربر به مدیر ربات یا مدیر."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    target_user, target_chat_member = await get_target_user(update, context, context.args)
    if not target_user:
        return

    if target_user.id == admin_id:
        await update.message.reply_text(MESSAGES["cannot_promote_self"])
        return

    # بررسی اینکه کاربر target_user مالک گروه تلگرام نباشد
    if target_chat_member and target_chat_member.status == ChatMemberStatus.OWNER:
        await update.message.reply_text(MESSAGES["cannot_promote_owner"])
        return
    
    current_role = get_user_role(chat_id, target_user.id)
    if current_role == ROLE_OWNER: # ادمین اصلی ربات در این گروه
        await update.message.reply_text(MESSAGES["owner_cannot_be_demoted"])
        return


    new_role = ROLE_MODERATOR
    if len(context.args) > 1:
        if context.args[1].lower() == "bot_admin":
            new_role = ROLE_BOT_ADMIN
        elif context.args[1].lower() == "moderator":
            new_role = ROLE_MODERATOR
        else:
            await update.message.reply_text(MESSAGES["promote_usage"])
            return
    
    # فقط OWNER میتواند bot_admin ارتقا دهد
    if new_role == ROLE_BOT_ADMIN and get_user_role(chat_id, admin_id) != ROLE_OWNER:
        await update.message.reply_text(MESSAGES["no_permissions"])
        logger.warning(f"User {admin_id} tried to promote {target_user.id} to BOT_ADMIN without being OWNER in group {chat_id}.")
        return

    set_user_role(chat_id, target_user.id, new_role)
    user_mention = await format_user_mention(target_user)
    await update.message.reply_text(MESSAGES["promote_success"].format(user_mention=user_mention, role=new_role), parse_mode=ParseMode.MARKDOWN)
    logger.info(f"User {target_user.id} promoted to {new_role} in group {chat_id} by {admin_id}.")


@restricted(roles=[ROLE_BOT_ADMIN, ROLE_OWNER])
async def demote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاهش سطح دسترسی کاربر."""
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    target_user, _ = await get_target_user(update, context, context.args)
    if not target_user:
        return

    if target_user.id == admin_id:
        await update.message.reply_text(MESSAGES["cannot_demote_yourself"])
        return
    
    current_role = get_user_role(chat_id, target_user.id)
    if current_role == ROLE_OWNER:
        await update.message.reply_text(MESSAGES["owner_cannot_be_demoted"])
        return

    # OWNER میتواند bot_admin و moderator را demote کند.
    # BOT_ADMIN میتواند moderator را demote کند.
    
    admin_role = get_user_role(chat_id, admin_id)

    if admin_role == ROLE_BOT_ADMIN and current_role == ROLE_BOT_ADMIN:
        await update.message.reply_text(MESSAGES["no_permissions"]) # یک BOT_ADMIN نمیتواند BOT_ADMIN دیگر را demote کند.
        logger.warning(f"BOT_ADMIN {admin_id} tried to demote another BOT_ADMIN {target_user.id} in group {chat_id}.")
        return


    set_user_role(chat_id, target_user.id, ROLE_MEMBER)
    user_mention = await format_user_mention(target_user)
    await update.message.reply_text(MESSAGES["demote_success"].format(user_mention=user_mention), parse_mode=ParseMode.MARKDOWN)
    logger.info(f"User {target_user.id} demoted to MEMBER in group {chat_id} by {admin_id}.")

@restricted(roles=[ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER])
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لیست ادمین‌های ربات و مدیران گروه را نمایش می‌دهد."""
    chat_id = update.effective_chat.id
    bot_admins = get_bot_admins(chat_id)
    
    response_text = ""
    if bot_admins:
        for user_id, role in bot_admins:
            user_data = get_user_data(user_id)
            if user_data:
                user_mention = await format_user_mention(Update.de_json({"id": user_data['id'], "first_name": user_data['first_name'], "username": user_data['username']}, context.bot))
                response_text += f"• {user_mention} (`{role}`)\n"
            else:
                response_text += f"• کاربر ناشناس (`{role}` - ID: `{user_id}`)\n"
    else:
        response_text = MESSAGES["no_bot_admins"]

    await update.message.reply_text(MESSAGES["admins_list"].format(admins_text=response_text), parse_mode=ParseMode.MARKDOWN)
    logger.info(f"User {update.effective_user.id} requested admin list for group {chat_id}.")


# --- هندلر پیام‌های جدید (برای فیلترها و خوش‌آمدگویی و کپچا) ---
async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای اعضای جدید گروه."""
    chat_id = update.effective_chat.id
    new_members = update.message.new_chat_members
    group_settings = get_group_settings(chat_id)

    if not group_settings:
        insert_or_update_group(chat_id) # اطمینان از وجود گروه در دیتابیس
        group_settings = get_group_settings(chat_id)
    
    # حذف پیام ورود/خروج
    if group_settings.get('del_join_msg_status') == 1:
        try:
            await update.message.delete()
            logger.info(f"Deleted join message in group {chat_id}.")
        except Exception as e:
            logger.error(f"Failed to delete join message in group {chat_id}: {e}")

    for member in new_members:
        insert_or_update_user(member) # ثبت کاربر جدید در دیتابیس
        
        # اگر کاربر ربات بود و ادمین نشد، آن را از گروه حذف کن
        if member.is_bot and member.id != context.bot.id: # اگر ربات خودمان نبود
            try:
                bot_member_status = await context.bot.get_chat_member(chat_id, member.id)
                if not bot_member_status.status == ChatMemberStatus.ADMINISTRATOR:
                    await context.bot.kick_chat_member(chat_id, member.id)
                    logger.info(f"Bot {member.id} kicked from group {chat_id} because it was not admin.")
                    await update.effective_chat.send_message(f"ربات {await format_user_mention(member)} از گروه حذف شد (ادمین نبود).", parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"Failed to kick bot {member.id} from group {chat_id}: {e}")
            continue # به سراغ عضو بعدی (چون ربات را مدیریت کردیم)

        # مدیریت کپچا
        if group_settings.get('captcha_status') == 1 and not member.is_bot:
            captcha_time = group_settings.get('captcha_time', DEFAULT_CAPTCHA_TIME)
            captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            
            user_mention = await format_user_mention(member)
            captcha_message_text = MESSAGES["new_member_captcha"].format(
                group_name=update.effective_chat.title,
                user_mention=user_mention,
                captcha_text=captcha_text,
                time=captcha_time
            )
            try:
                # محدود کردن کاربر تا زمانی که کپچا را حل کند
                await restrict_chat_member_wrapper(chat_id, member.id, ChatPermissions(can_send_messages=False))
                captcha_message = await update.effective_chat.send_message(
                    captcha_message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                add_captcha_pending_user(chat_id, member.id, captcha_text, captcha_message.message_id)

                # زمانبندی برای بررسی کپچا پس از اتمام زمان
                context.job_queue.run_once(
                    check_captcha_timeout,
                    captcha_time,
                    data={'chat_id': chat_id, 'user_id': member.id, 'captcha_msg_id': captcha_message.message_id},
                    name=f"captcha_timeout_{chat_id}_{member.id}"
                )
                logger.info(f"Captcha sent to new member {member.id} in group {chat_id}.")

            except ValueError as ve:
                await update.effective_chat.send_message(f"خطا در اعمال محدودیت برای کپچا: {ve}", parse_mode=ParseMode.MARKDOWN)
                logger.error(f"Error restricting user {member.id} for captcha: {ve}")
            except Exception as e:
                await update.effective_chat.send_message("خطا در ارسال پیام کپچا یا محدودیت کاربر جدید. لطفاً ربات را ادمین کامل کنید.", parse_mode=ParseMode.MARKDOWN)
                logger.error(f"Error handling captcha for new member {member.id} in group {chat_id}: {e}")

        # پیام خوش‌آمدگویی (اگر کپچا فعال نیست یا کاربر کپچا را رد کرده باشد)
        elif group_settings.get('welcome_status') == 1:
            welcome_msg = group_settings.get('welcome_message', MESSAGES["welcome_message"])
            user_mention = await format_user_mention(member)
            formatted_welcome_msg = welcome_msg.format(user_mention=user_mention, group_name=update.effective_chat.title)
            await update.effective_chat.send_message(formatted_welcome_msg, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"Welcome message sent to new member {member.id} in group {chat_id}.")

async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای اعضای ترک‌کننده گروه."""
    chat_id = update.effective_chat.id
    group_settings = get_group_settings(chat_id)

    if group_settings and group_settings.get('del_join_msg_status') == 1:
        try:
            await update.message.delete()
            logger.info(f"Deleted left message in group {chat_id}.")
        except Exception as e:
            logger.error(f"Failed to delete left message in group {chat_id}: {e}")

async def check_captcha_timeout(context: ContextTypes.DEFAULT_TYPE):
    """بررسی اتمام زمان کپچا."""
    job_data = context.job.data
    chat_id = job_data['chat_id']
    user_id = job_data['user_id']
    captcha_msg_id = job_data['captcha_msg_id']

    captcha_info = get_captcha_pending_user(chat_id, user_id)
    if captcha_info: # اگر کاربر هنوز کپچا را حل نکرده باشد
        try:
            # حذف پیام کپچا
            await context.bot.delete_message(chat_id=chat_id, message_id=captcha_msg_id)
        except Exception as e:
            logger.warning(f"Failed to delete captcha message {captcha_msg_id} for user {user_id}: {e}")

        try:
            # اخراج کاربر
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id) # اجازه برگشت با لینک
            remove_captcha_pending_user(chat_id, user_id)
            user_data = get_user_data(user_id)
            user_mention = await format_user_mention(Update.de_json({"id": user_data['id'], "first_name": user_data['first_name'], "username": user_data['username']}, context.bot)) if user_data else f"کاربر با ID: {user_id}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=MESSAGES["captcha_timeout"].format(user_mention=user_mention),
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"User {user_id} kicked from group {chat_id} due to captcha timeout.")
        except Exception as e:
            logger.error(f"Failed to kick user {user_id} after captcha timeout in group {chat_id}: {e}")
            await context.bot.send_message(chat_id=chat_id, text=MESSAGES["captcha_kick_fail"])
    else:
        logger.info(f"User {user_id} already solved captcha or left group {chat_id}.")

async def handle_messages_for_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای بررسی پاسخ کپچا."""
    if not update.message or not update.message.text or not update.effective_chat or update.effective_chat.type == "private":
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    captcha_info = get_captcha_pending_user(chat_id, user_id)
    if captcha_info:
        captcha_text, captcha_message_id, _ = captcha_info
        if update.message.text.strip().lower() == captcha_text.lower():
            try:
                # حذف پیام کپچا و پیام کاربر
                await context.bot.delete_message(chat_id=chat_id, message_id=captcha_message_id)
                await update.message.delete()
            except Exception as e:
                logger.warning(f"Failed to delete captcha/user message after correct captcha: {e}")

            remove_captcha_pending_user(chat_id, user_id)
            # رفع محدودیت کاربر
            try:
                await restrict_chat_member_wrapper(
                    chat_id,
                    user_id,
                    ChatPermissions(
                        can_send_messages=True, can_send_audios=True, can_send_documents=True,
                        can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                        can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                        can_add_web_page_previews=True, can_change_info=False, can_invite_users=True,
                        can_pin_messages=False, can_manage_topics=False
                    )
                )
                await update.effective_chat.send_message(
                    MESSAGES["captcha_correct"],
                    reply_to_message_id=update.message.message_id # به پیام اصلی کاربر پاسخ میدهیم
                )
                logger.info(f"User {user_id} solved captcha in group {chat_id}.")

                # اگر خوش‌آمدگویی فعال باشد و کپچا را حل کرده، پیام خوش‌آمدگویی را ارسال کن
                group_settings = get_group_settings(chat_id)
                if group_settings.get('welcome_status') == 1:
                    welcome_msg = group_settings.get('welcome_message', MESSAGES["welcome_message"])
                    user_mention = await format_user_mention(update.effective_user)
                    formatted_welcome_msg = welcome_msg.format(user_mention=user_mention, group_name=update.effective_chat.title)
                    await update.effective_chat.send_message(formatted_welcome_msg, parse_mode=ParseMode.MARKDOWN)

            except ValueError as ve:
                await update.effective_chat.send_message(f"خطا در رفع محدودیت کاربر بعد از کپچا: {ve}", parse_mode=ParseMode.MARKDOWN)
                logger.error(f"Error un-restricting user {user_id} after captcha: {ve}")
            except Exception as e:
                logger.error(f"Error handling correct captcha for user {user_id} in group {chat_id}: {e}")
                await update.effective_chat.send_message(MESSAGES["captcha_kick_fail"]) # اگر خطا بود، به ادمین پیام بده
        else:
            try:
                await update.message.delete() # حذف پیام اشتباه کپچا
                await update.effective_chat.send_message(MESSAGES["captcha_incorrect"], reply_to_message_id=update.message.message_id)
                logger.warning(f"User {user_id} sent incorrect captcha in group {chat_id}.")
            except Exception as e:
                logger.error(f"Failed to delete incorrect captcha message or send reply: {e}")

# --- هندلر پیام‌های عمومی برای فیلترها و ضد اسپم ---
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر جامع برای مدیریت پیام‌های عمومی و اعمال فیلترها."""
    if not update.message or not update.effective_chat or update.effective_chat.type == "private":
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id

    # اطمینان از وجود کاربر در دیتابیس
    insert_or_update_user(user)

    # اگر کاربر در انتظار کپچا است، پیام او را نادیده بگیرید تا توسط handle_messages_for_captcha مدیریت شود.
    if get_captcha_pending_user(chat_id, user_id):
        return

    # بررسی Flood Control
    if await check_flood(update, context, user_id, chat_id):
        return # اگر سیل پیام بود، دیگر فیلترها را بررسی نکن

    group_settings = get_group_settings(chat_id)
    if not group_settings:
        return # اگر گروه در دیتابیس ثبت نشده بود، کاری نکن

    # ادمین‌های تلگرام نباید فیلتر شوند
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return
    except Exception as e:
        logger.error(f"Could not get chat member status for user {user_id} in group {chat_id}: {e}")
        # اگر نتوانستیم وضعیت را بگیریم، فرض می‌کنیم ادمین نیست تا فیلتر اعمال شود.

    message_deleted = False

    # فیلتر لینک
    if group_settings.get('link_filter') == 1:
        if update.message.entities:
            for entity in update.message.entities:
                if entity.type in [MessageEntity.URL, MessageEntity.TEXT_LINK]:
                    try:
                        await update.message.delete()
                        message_deleted = True
                        logger.info(f"Link message from {user_id} deleted in group {chat_id}.")
                        await update.effective_chat.send_message(
                            f"{await format_user_mention(user)}! ارسال لینک ممنوع است.",
                            parse_mode=ParseMode.MARKDOWN,
                            reply_to_message_id=update.message.message_id
                        )
                        break
                    except Exception as e:
                        logger.error(f"Failed to delete link message: {e}")
        if message_deleted: return

    # فیلتر کلمات ممنوعه
    if group_settings.get('badwords_filter') == 1 and update.message.text:
        all_bad_words = get_bad_words(chat_id) + GLOBAL_BAD_WORDS
        for bad_word in all_bad_words:
            if re.search(r'\b' + re.escape(bad_word) + r'\b', update.message.text.lower()):
                try:
                    await update.message.delete()
                    message_deleted = True
                    logger.info(f"Bad word message from {user_id} deleted in group {chat_id}.")
                    await update.effective_chat.send_message(
                        MESSAGES["badword_filtered"].format(user_mention=await format_user_mention(user)),
                        parse_mode=ParseMode.MARKDOWN,
                        reply_to_message_id=update.message.message_id
                    )
                    break
                except Exception as e:
                    logger.error(f"Failed to delete bad word message: {e}")
        if message_deleted: return

    # فیلتر فوروارد
    if group_settings.get('forward_filter') == 1 and update.message.forward_from_chat:
        try:
            await update.message.delete()
            message_deleted = True
            logger.info(f"Forwarded message from {user_id} deleted in group {chat_id}.")
            await update.effective_chat.send_message(
                f"{await format_user_mention(user)}! ارسال پیام فوروارد شده ممنوع است.",
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=update.message.message_id
            )
        except Exception as e:
            logger.error(f"Failed to delete forwarded message: {e}")
        if message_deleted: return

    # فیلتر عکس
    if group_settings.get('photo_filter') == 1 and update.message.photo:
        try:
            await update.message.delete()
            message_deleted = True
            logger.info(f"Photo message from {user_id} deleted in group {chat_id}.")
            await update.effective_chat.send_message(
                f"{await format_user_mention(user)}! ارسال عکس ممنوع است.",
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=update.message.message_id
            )
        except Exception as e:
            logger.error(f"Failed to delete photo message: {e}")
        if message_deleted: return

    # فیلتر ویدئو
    if group_settings.get('video_filter') == 1 and update.message.video:
        try:
            await update.message.delete()
            message_deleted = True
            logger.info(f"Video message from {user_id} deleted in group {chat_id}.")
            await update.effective_chat.send_message(
                f"{await format_user_mention(user)}! ارسال ویدئو ممنوع است.",
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=update.message.message_id
            )
        except Exception as e:
            logger.error(f"Failed to delete video message: {e}")
        if message_deleted: return

    # فیلتر داکیومنت
    if group_settings.get('document_filter') == 1 and update.message.document:
        try:
            await update.message.delete()
            message_deleted = True
            logger.info(f"Document message from {user_id} deleted in group {chat_id}.")
            await update.effective_chat.send_message(
                f"{await format_user_mention(user)}! ارسال فایل ممنوع است.",
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=update.message.message_id
            )
        except Exception as e:
            logger.error(f"Failed to delete document message: {e}")
        if message_deleted: return

    # فیلتر استیکر
    if group_settings.get('sticker_filter') == 1 and update.message.sticker:
        try:
            await update.message.delete()
            message_deleted = True
            logger.info(f"Sticker message from {user_id} deleted in group {chat_id}.")
            await update.effective_chat.send_message(
                f"{await format_user_mention(user)}! ارسال استیکر ممنوع است.",
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=update.message.message_id
            )
        except Exception as e:
            logger.error(f"Failed to delete sticker message: {e}")
        if message_deleted: return

    # فیلتر گیف
    if group_settings.get('gif_filter') == 1 and update.message.animation: # animation برای گیف است
        try:
            await update.message.delete()
            message_deleted = True
            logger.info(f"GIF message from {user_id} deleted in group {chat_id}.")
            await update.effective_chat.send_message(
                f"{await format_user_mention(user)}! ارسال گیف ممنوع است.",
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=update.message.message_id
            )
        except Exception as e:
            logger.error(f"Failed to delete GIF message: {e}")
        if message_deleted: return
    
    # فیلتر پیام صوتی
    if group_settings.get('voice_filter') == 1 and update.message.voice:
        try:
            await update.message.delete()
            message_deleted = True
            logger.info(f"Voice message from {user_id} deleted in group {chat_id}.")
            await update.effective_chat.send_message(
                f"{await format_user_mention(user)}! ارسال پیام صوتی ممنوع است.",
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=update.message.message_id
            )
        except Exception as e:
            logger.error(f"Failed to delete voice message: {e}")
        if message_deleted: return

    # فیلتر ویدئو نوت
    if group_settings.get('video_note_filter') == 1 and update.message.video_note:
        try:
            await update.message.delete()
            message_deleted = True
            logger.info(f"Video note message from {user_id} deleted in group {chat_id}.")
            await update.effective_chat.send_message(
                f"{await format_user_mention(user)}! ارسال ویدئو نوت ممنوع است.",
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=update.message.message_id
            )
        except Exception as e:
            logger.error(f"Failed to delete video note message: {e}")
        if message_deleted: return

    # فیلتر دکمه‌های شیشه‌ای با URL
    if group_settings.get('url_button_filter') == 1 and update.message.reply_markup and update.message.reply_markup.inline_keyboard:
        for row in update.message.reply_markup.inline_keyboard:
            for button in row:
                if button.url:
                    try:
                        await update.message.delete()
                        message_deleted = True
                        logger.info(f"URL button message from {user_id} deleted in group {chat_id}.")
                        await update.effective_chat.send_message(
                            f"{await format_user_mention(user)}! ارسال دکمه‌های شیشه‌ای با لینک ممنوع است.",
                            parse_mode=ParseMode.MARKDOWN,
                            reply_to_message_id=update.message.message_id
                        )
                        break
                    except Exception as e:
                        logger.error(f"Failed to delete URL button message: {e}")
            if message_deleted: break # اگر در یک سطر دکمه‌ای حذف شد، از بقیه سطرها نیز خارج شو
        if message_deleted: return

    # فیلتر کاراکترهای عربی (مثلاً برای جلوگیری از ارسال پیام به زبان عربی)
    if group_settings.get('arabic_char_filter') == 1 and update.message.text:
        # یک regex ساده برای تشخیص کاراکترهای عربی
        arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
        if arabic_pattern.search(update.message.text):
            try:
                await update.message.delete()
                message_deleted = True
                logger.info(f"Arabic character message from {user_id} deleted in group {chat_id}.")
                await update.effective_chat.send_message(
                    f"{await format_user_mention(user)}! ارسال پیام با کاراکترهای عربی ممنوع است.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_to_message_id=update.message.message_id
                )
            except Exception as e:
                logger.error(f"Failed to delete Arabic character message: {e}")
        if message_deleted: return


# --- مدیریت خطا ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a traceback to the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # اطلاعات خطای کامل
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # اطلاعات بیشتر در مورد آپدیت
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # ارسال به ادمین (مثلاً توسعه‌دهنده)
    # اینجا باید یک chat_id ثابت برای ادمین داشته باشید یا از Environment Variable بخوانید
    # ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
    # if ADMIN_CHAT_ID:
    #     try:
    #         await context.bot.send_message(
    #             chat_id=ADMIN_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    #         )
    #     except Exception as e:
    #         logger.error(f"Failed to send error message to admin chat: {e}")
    #     logger.info("Error traceback sent to admin.")
    # else:
    #     logger.warning("ADMIN_CHAT_ID not set. Error traceback not sent to admin.")

# --- 8. تابع اصلی ربات ---
def main() -> None:
    """تابع اصلی برای اجرای ربات."""
    global application

    # ابتدا دیتابیس را مقداردهی اولیه می‌کنیم
    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    # --- هندلرهای دستورات ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command)) # help_command باید تعریف شود
    application.add_handler(CommandHandler("id", get_id))
    application.add_handler(CommandHandler("info", get_info))
    application.add_handler(CommandHandler("rules", get_rules))
    application.add_handler(CommandHandler("setrules", set_rules)) # alias برای set_rules
    application.add_handler(CommandHandler("setwelcome", set_welcome_message))
    application.add_handler(CommandHandler("welcome", toggle_welcome))
    application.add_handler(CommandHandler("deljoinmsg", toggle_del_join_msg))
    application.add_handler(CommandHandler("warnlimit", set_warn_limit))
    application.add_handler(CommandHandler("flood", toggle_flood_control))
    application.add_handler(CommandHandler("setfloodlimit", set_flood_limit))
    application.add_handler(CommandHandler("captcha", toggle_captcha))
    application.add_handler(CommandHandler("setcaptchatime", set_captcha_time))
    
    # دستورات فیلترها (lock/unlock)
    application.add_handler(CommandHandler("locklinks", toggle_links_filter))
    application.add_handler(CommandHandler("unlocklinks", toggle_links_filter))
    application.add_handler(CommandHandler("lockphotos", toggle_photos_filter))
    application.add_handler(CommandHandler("unlockphotos", toggle_photos_filter))
    application.add_handler(CommandHandler("lockvideos", toggle_videos_filter))
    application.add_handler(CommandHandler("unlockvideos", toggle_videos_filter))
    application.add_handler(CommandHandler("lockdocuments", toggle_documents_filter))
    application.add_handler(CommandHandler("unlockdocuments", toggle_documents_filter))
    application.add_handler(CommandHandler("lockstickers", toggle_stickers_filter))
    application.add_handler(CommandHandler("unlockstickers", toggle_stickers_filter))
    application.add_handler(CommandHandler("lockgifs", toggle_gifs_filter))
    application.add_handler(CommandHandler("unlockgifs", toggle_gifs_filter))
    application.add_handler(CommandHandler("lockforwards", toggle_forwards_filter))
    application.add_handler(CommandHandler("unlockforwards", toggle_forwards_filter))
    application.add_handler(CommandHandler("lockvoice", toggle_voice_filter))
    application.add_handler(CommandHandler("unlockvoice", toggle_voice_filter))
    application.add_handler(CommandHandler("lockvideonotes", toggle_video_notes_filter))
    application.add_handler(CommandHandler("unlockvideonotes", toggle_video_notes_filter))
    application.add_handler(CommandHandler("lockurlbuttons", toggle_url_buttons_filter))
    application.add_handler(CommandHandler("unlockurlbuttons", toggle_url_buttons_filter))
    application.add_handler(CommandHandler("lockarabicchars", toggle_arabic_chars_filter))
    application.add_handler(CommandHandler("unlockarabicchars", toggle_arabic_chars_filter))
    application.add_handler(CommandHandler("lockbadwords", toggle_badwords_filter))
    application.add_handler(CommandHandler("unlockbadwords", toggle_badwords_filter))

    application.add_handler(CommandHandler("addbadword", add_badword_handler))
    application.add_handler(CommandHandler("removebadword", remove_badword_handler))
    application.add_handler(CommandHandler("listbadwords", list_badwords_handler))


    # دستورات مدیریتی
    application.add_handler(CommandHandler("warn", warn_user))
    application.add_handler(CommandHandler("unwarn", unwarn_user))
    application.add_handler(CommandHandler("warnings", get_user_warnings))
    application.add_handler(CommandHandler("mute", mute_user))
    application.add_handler(CommandHandler("unmute", unmute_user))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    application.add_handler(CommandHandler("kick", kick_user))
    application.add_handler(CommandHandler("del", delete_message))
    application.add_handler(CommandHandler("pin", pin_message))
    application.add_handler(CommandHandler("unpin", unpin_message))
    application.add_handler(CommandHandler("purge", purge_messages))

    # مدیریت نقش‌ها
    application.add_handler(CommandHandler("promote", promote_user))
    application.add_handler(CommandHandler("demote", demote_user))
    application.add_handler(CommandHandler("admins", list_admins))

    # پنل تنظیمات
    application.add_handler(CommandHandler("settings", settings_panel))
    application.add_handler(CallbackQueryHandler(settings_callback_handler))

    # هندلر پیام‌های اعضای جدید و خروجی
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_member))

    # هندلر برای بررسی پاسخ کپچا (باید قبل از handle_all_messages باشد)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages_for_captcha, block=False))

    # هندلر جامع برای فیلتر کردن تمامی پیام‌ها
    # این هندلر باید در انتها باشد تا دستورات و کپچا ابتدا بررسی شوند
    application.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.NEW_CHAT_MEMBERS & ~filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_all_messages))


    # هندلر خطاها
    application.add_error_handler(error_handler)

    # شروع پولینگ ربات
    logger.info("Bot started polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


# این خطوط باید بعد از تعریف تمامی توابع و هندلرها باشند.
# تعریف تابع help_command که به آن در main() اشاره شد
@restricted(roles=[ROLE_MEMBER]) # دسترسی به این دستور برای همه باز است
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message with information on how to use the bot."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    user_db_role = get_user_role(chat_id, user_id)
    member = await context.bot.get_chat_member(chat_id, user_id)
    is_telegram_admin = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

    response_text = MESSAGES["help_member"]
    
    if is_telegram_admin or user_db_role in [ROLE_MODERATOR, ROLE_BOT_ADMIN, ROLE_OWNER]:
        response_text += "\n" + MESSAGES["help_moderator"]
    if is_telegram_admin or user_db_role in [ROLE_BOT_ADMIN, ROLE_OWNER]:
        response_text += "\n" + MESSAGES["help_admin"]
    
    await update.message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"User {user_id} requested help in group {chat_id}.")

if __name__ == "__main__":
    # Import traceback and html modules for detailed error handling
    import traceback
    import html
    import json
    
    main()
