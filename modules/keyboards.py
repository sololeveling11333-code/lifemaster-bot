"""
LifeMaster AI - Keyboards & Buttons
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# ─── Priority Labels ─────────────────────────────────────────
PRIORITY_LABELS = {
    "low":    "🟢 منخفضة",
    "medium": "🟡 متوسطة",
    "high":   "🟠 عالية",
    "urgent": "🔴 عاجلة"
}

CATEGORY_LABELS = {
    "cat_sport":   "🏋️ رياضة",
    "cat_study":   "📚 تعليم",
    "cat_work":    "💼 عمل",
    "cat_home":    "🏠 منزل",
    "cat_health":  "💪 صحة",
    "cat_general": "⭐ عام",
}


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 المهام",        callback_data="menu_tasks"),
            InlineKeyboardButton("🔥 العادات",       callback_data="menu_habits"),
        ],
        [
            InlineKeyboardButton("📊 تحليلاتي",     callback_data="menu_analytics"),
            InlineKeyboardButton("📆 التقويم",       callback_data="menu_calendar"),
        ],
        [
            InlineKeyboardButton("🤖 المدرب الذكي", callback_data="menu_ai"),
            InlineKeyboardButton("🏆 الإنجازات",    callback_data="menu_achievements"),
        ],
        [
            InlineKeyboardButton("🛒 المتجر",        callback_data="menu_store"),
            InlineKeyboardButton("👥 الترتيب",       callback_data="menu_leaderboard"),
        ],
        [
            InlineKeyboardButton("👤 ملفي",          callback_data="menu_profile"),
            InlineKeyboardButton("⚙️ الإعدادات",    callback_data="menu_settings"),
        ],
    ])


def tasks_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ مهمة جديدة",  callback_data="task_add"),
            InlineKeyboardButton("📋 مهام اليوم",   callback_data="task_today"),
        ],
        [
            InlineKeyboardButton("📂 كل المهام",    callback_data="task_all"),
            InlineKeyboardButton("✅ مكتملة",        callback_data="task_done"),
        ],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")],
    ])


def habits_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ عادة جديدة",    callback_data="habit_add"),
            InlineKeyboardButton("📋 عاداتي",         callback_data="habit_list"),
        ],
        [
            InlineKeyboardButton("✅ تسجيل اليوم",   callback_data="habit_log_today"),
            InlineKeyboardButton("📊 تحليل العادات", callback_data="habit_stats"),
        ],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")],
    ])


def priority_keyboard(prefix: str = "priority") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 منخفضة", callback_data=f"{prefix}_low"),
            InlineKeyboardButton("🟡 متوسطة", callback_data=f"{prefix}_medium"),
        ],
        [
            InlineKeyboardButton("🟠 عالية",   callback_data=f"{prefix}_high"),
            InlineKeyboardButton("🔴 عاجلة",   callback_data=f"{prefix}_urgent"),
        ],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")],
    ])


def due_date_keyboard() -> InlineKeyboardMarkup:
    from datetime import date, timedelta
    today    = date.today()
    tomorrow = today + timedelta(days=1)
    week     = today + timedelta(days=7)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 اليوم",           callback_data=f"due_{today.strftime('%Y-%m-%d')}"),
            InlineKeyboardButton("📅 غداً",             callback_data=f"due_{tomorrow.strftime('%Y-%m-%d')}"),
        ],
        [
            InlineKeyboardButton("📅 الأسبوع القادم",  callback_data=f"due_{week.strftime('%Y-%m-%d')}"),
            InlineKeyboardButton("⏭️ بدون تاريخ",      callback_data="due_none"),
        ],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")],
    ])


def task_actions_keyboard(task_id: str, status: str) -> InlineKeyboardMarkup:
    rows = []
    if status == "pending":
        rows.append([InlineKeyboardButton("✅ أنجزت المهمة", callback_data=f"done_task_{task_id}")])
    rows.append([
        InlineKeyboardButton("🗑️ حذف",   callback_data=f"del_task_{task_id}"),
        InlineKeyboardButton("🔙 رجوع",  callback_data="task_today"),
    ])
    return InlineKeyboardMarkup(rows)


def habit_action_keyboard(habit_id: str, logged: bool) -> InlineKeyboardMarkup:
    if logged:
        rows = [
            [InlineKeyboardButton("✅ سُجِّلت اليوم", callback_data="already_done")],
            [InlineKeyboardButton("🗑️ حذف العادة",    callback_data=f"del_habit_{habit_id}")],
            [InlineKeyboardButton("🔙 رجوع",           callback_data="habit_log_today")],
        ]
    else:
        rows = [
            [
                InlineKeyboardButton("✅ أنجزت",   callback_data=f"done_habit_{habit_id}"),
                InlineKeyboardButton("⏭️ تخطّيت", callback_data=f"skip_habit_{habit_id}"),
            ],
            [InlineKeyboardButton("🗑️ حذف العادة", callback_data=f"del_habit_{habit_id}")],
            [InlineKeyboardButton("🔙 رجوع",        callback_data="habit_log_today")],
        ]
    return InlineKeyboardMarkup(rows)


def category_keyboard() -> InlineKeyboardMarkup:
    cats = list(CATEGORY_LABELS.items())
    rows = []
    for i in range(0, len(cats), 2):
        row = [InlineKeyboardButton(v, callback_data=k) for k, v in cats[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def store_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏷️ الألقاب",     callback_data="store_titles"),
            InlineKeyboardButton("🏅 الشارات",      callback_data="store_badges"),
        ],
        [
            InlineKeyboardButton("🎁 الصناديق",     callback_data="store_boxes"),
            InlineKeyboardButton("⭐ معزز XP",      callback_data="store_boosts"),
        ],
        [
            InlineKeyboardButton("🎒 حقيبتي",       callback_data="store_inventory"),
        ],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")],
    ])


def analytics_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 هذا الأسبوع",  callback_data="analytics_weekly"),
            InlineKeyboardButton("📆 هذا الشهر",    callback_data="analytics_monthly"),
        ],
        [
            InlineKeyboardButton("🔥 تحليل العادات", callback_data="analytics_habits"),
        ],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")],
    ])


def back_keyboard(callback: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=callback)]])


def confirm_delete_keyboard(item_id: str, item_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ نعم، احذف",  callback_data=f"confirm_del_{item_type}_{item_id}"),
            InlineKeyboardButton("❌ لا",           callback_data="cancel"),
        ]
    ])
