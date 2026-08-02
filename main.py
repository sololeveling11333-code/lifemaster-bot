"""
LifeMaster AI — Telegram Bot (Full)
مهام · عادات · أهداف · XP · متجر · تحليلات · تقويم · تحديات · ذكاء اصطناعي
"""
import os
import logging
import io
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run).start()

from datetime import datetime, time, date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters,
)

from modules.database import (
    get_or_create_user, get_user, update_user, get_all_users,
    get_today_tasks, get_user_tasks, get_task_by_id,
    create_task, complete_task, update_task, delete_task,
    get_user_habits, get_habit_log_today, log_habit,
    create_habit, delete_habit, pause_habit, get_habit_streak_history,
    get_user_goals, get_daily_stats,
)
from modules.xp_system import (
    award_task_completion, award_habit_completion,
    get_level_info, get_xp_bar, update_streak,
)
from modules.keyboards import (
    main_menu_keyboard, tasks_menu_keyboard, habits_menu_keyboard,
    priority_keyboard, due_date_keyboard, task_actions_keyboard,
    habit_action_keyboard, category_keyboard, store_menu_keyboard,
    analytics_menu_keyboard, back_keyboard, PRIORITY_LABELS, CATEGORY_LABELS,
)
from modules.achievements import check_and_award, check_first_habit, get_all_achievements_status
from modules.ai_coach import ask_coach, generate_daily_plan, motivate, analyze_habits
from modules.store import get_store_items_by_type, buy_item, get_inventory
from modules.analytics import (
    get_weekly_stats, get_monthly_stats, get_habit_analytics,
    get_most_productive_hour, get_most_productive_day,
    build_calendar_text, build_weekly_chart, build_habit_streak_graph,
)
from modules.penalties import apply_midnight_penalties
from modules.goals import create_goal, get_user_goals as _goals_list, update_goal_progress, delete_goal, goal_progress_bar
from modules.challenges import (
    get_active_challenges, get_open_challenges,
    create_challenge, join_challenge, update_challenge_progress,
    send_friend_request, get_pending_requests, accept_friend, get_friends,
)
from modules.backup import export_as_json_bytes, build_text_report
from modules.database import (
    create_reminder, get_due_reminders, mark_reminder_fired,
    get_user_reminders, delete_user_reminders,
)

import sys
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URI = os.environ.get("MONGO_URI", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# ── Conversation states ──────────────────────────────────────
(
    TASK_TITLE, TASK_PRIORITY, TASK_CATEGORY, TASK_DUE_DATE, TASK_REPEAT,
    HABIT_NAME, HABIT_ICON,
    GOAL_TITLE, GOAL_TARGET, GOAL_UNIT, GOAL_DEADLINE,
    GOAL_UPDATE_VALUE,
    CHALLENGE_TITLE, CHALLENGE_TYPE, CHALLENGE_TARGET,
    FRIEND_ID,
    AI_CHAT,
    EDIT_TASK_FIELD, EDIT_TASK_VALUE,
    REMINDER_TIME, SET_MORNING_TIME, SET_EVENING_TIME,
) = range(22)

_tmp: dict = {}   # per-user temp data during conversations


# ════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════
def fmt_priority(p): return PRIORITY_LABELS.get(p, p)

def fmt_date(d):
    if not d: return "بدون تاريخ"
    today = date.today().strftime("%Y-%m-%d")
    tom   = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    if d == today: return "📅 اليوم"
    if d == tom:   return "📅 غداً"
    return f"📅 {d}"

async def _edit(update: Update, text: str, kb, parse_mode="Markdown"):
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=parse_mode, reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=kb)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict):
    xp  = user.get("xp", 0)
    lv  = get_level_info(xp)
    bar = get_xp_bar(lv["progress"])
    nxt = f"`{lv['xp_for_next']:,}`" if lv["xp_for_next"] else "MAX 🔱"
    ttl = f" · _{user.get('equipped_title','')}_" if user.get("equipped_title") else ""
    txt = (
        f"👋 *{user['name']}*{ttl}\n\n"
        f"{lv['rank_emoji']} *{lv['rank']}* — المستوى {lv['level']}\n"
        f"⭐ `{xp:,}` XP  →  {nxt}\n"
        f"`{bar}`\n"
        f"💰 {user.get('coins',0):,} عملة  |  🔥 {user.get('streak',0)} يوم\n\n"
        f"اختر من القائمة:"
    )
    await _edit(update, txt, main_menu_keyboard())

async def _ach_popups(update: Update, ach_list: list):
    for a in ach_list:
        await update.effective_message.reply_text(
            f"🎉 *إنجاز جديد!*\n\n{a['icon']} *{a['name']}*\n_{a['desc']}_\n\n"
            f"⭐ +{a['xp_bonus']} XP | 💰 +{a['coins_bonus']} عملة",
            parse_mode="Markdown")


# ════════════════════════════════════════════════════════════
#  COMMANDS
# ════════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg   = update.effective_user
    user = get_or_create_user(tg.id, tg.first_name, tg.username or "")
    update_streak(tg.id)
    user = get_user(tg.id)
    new  = user.get("tasks_completed", 0) == 0 and user.get("habits_completed", 0) == 0
    if new:
        await update.message.reply_text(
            f"🌟 *أهلاً {tg.first_name} في LifeMaster AI!*\n\n"
            "نظامك الشخصي للإنتاجية وتطوير الذات.\n\n"
            "📅 تتبّع مهامك اليومية\n"
            "🔥 ابنِ عادات قوية\n"
            "🎯 حقّق أهدافك\n"
            "⭐ اكسب XP وارتقِ في المراتب\n"
            "🤖 استشر مدرباً ذكياً\n"
            "🛒 افتح صناديق وتسوّق\n"
            "👥 تحدَّ أصدقاءك\n\n"
            "ابدأ الآن! 👇",
            parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
    else:
        await show_main_menu(update, context, user)

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg = update.effective_user
    user = get_or_create_user(tg.id, tg.first_name)
    update_streak(tg.id); user = get_user(tg.id)
    await show_main_menu(update, context, user)

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_create_user(update.effective_user.id, update.effective_user.first_name)
    await _show_profile(update, user)

async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    data = export_as_json_bytes(uid)
    bio  = io.BytesIO(data)
    bio.name = f"lifemaster_backup_{date.today()}.json"
    await update.message.reply_document(bio, caption="📦 نسخة احتياطية من بياناتك ✅")


# ════════════════════════════════════════════════════════════
#  PROFILE
# ════════════════════════════════════════════════════════════
async def _show_profile(update: Update, user: dict):
    xp  = user.get("xp", 0)
    lv  = get_level_info(xp)
    bar = get_xp_bar(lv["progress"])
    nxt = f"`{lv['xp_for_next']:,}`" if lv["xp_for_next"] else "MAX 🔱"
    ttl = f"🏷️ اللقب: *{user.get('equipped_title','')}*\n" if user.get("equipped_title") else ""
    txt = (
        f"👤 *ملف {user['name']}*\n{'─'*22}\n"
        f"{lv['rank_emoji']} *{lv['rank']}* — المستوى {lv['level']}\n"
        f"⭐ XP: `{xp:,}`\n"
        f"📊 `{bar}` → {nxt}\n\n"
        f"{ttl}"
        f"💰 `{user.get('coins',0):,}` عملة\n"
        f"🔥 السلسلة: `{user.get('streak',0)}` يوم\n"
        f"🏅 الأعلى: `{user.get('best_streak',0)}` يوم\n\n"
        f"✅ مهام: `{user.get('tasks_completed',0)}`\n"
        f"🔥 عادات: `{user.get('habits_completed',0)}`\n"
        f"🏆 إنجازات: `{len(user.get('achievements',[]))}`"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎒 حقيبتي",          callback_data="store_inventory")],
        [InlineKeyboardButton("📦 نسخة احتياطية",   callback_data="backup_json")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")],
    ])
    await _edit(update, txt, kb)


# ════════════════════════════════════════════════════════════
#  MAIN CALLBACK ROUTER
# ════════════════════════════════════════════════════════════
async def cb_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()
    d   = q.data
    uid = update.effective_user.id
    user = get_or_create_user(uid, update.effective_user.first_name)

    # ── Navigation ──────────────────────────────────────────
    if   d == "back_main":         await show_main_menu(update, context, get_user(uid))
    elif d == "menu_tasks":        await _tasks_menu(update)
    elif d == "menu_habits":       await _habits_menu(update)
    elif d == "menu_goals":        await _goals_menu(update, uid)
    elif d == "menu_analytics":    await _analytics_menu(update)
    elif d == "menu_calendar":     await _show_calendar(update, uid)
    elif d == "menu_ai":           await _ai_menu(update, user)
    elif d == "menu_achievements": await _achievements_page(update, uid)
    elif d == "menu_store":        await _store_main(update)
    elif d == "menu_community":    await _community_menu(update, uid)
    elif d == "menu_leaderboard":  await _leaderboard(update, uid)
    elif d == "menu_profile":      await _show_profile(update, user)
    elif d == "menu_settings":     await _settings_page(update, user)

    # ── Tasks ────────────────────────────────────────────────
    elif d == "task_today":        await _today_tasks(update, uid)
    elif d == "task_all":          await _all_tasks(update, uid)
    elif d == "task_done_list":    await _done_tasks(update, uid)
    elif d.startswith("view_task_"):
        await _task_detail(update, d[len("view_task_"):])
    elif d.startswith("done_task_"):
        await _complete_task_cb(update, uid, d[len("done_task_"):])
    elif d.startswith("edit_task_"):
        await _edit_task_menu(update, context, d[len("edit_task_"):])
    elif d.startswith("del_task_"):
        delete_task(d[len("del_task_"):]); await _today_tasks(update, uid)

    # ── Habits ───────────────────────────────────────────────
    elif d == "habit_list":        await _habits_list(update, uid)
    elif d == "habit_log_today":   await _habit_log_today_page(update, uid)
    elif d == "habit_stats":       await _habit_stats_page(update, uid)
    elif d.startswith("view_habit_"):
        await _habit_detail(update, uid, d[len("view_habit_"):])
    elif d.startswith("done_habit_"):
        await _log_habit_cb(update, uid, d[len("done_habit_"):], "done")
    elif d.startswith("skip_habit_"):
        await _log_habit_cb(update, uid, d[len("skip_habit_"):], "skip")
    elif d.startswith("pause_habit_"):
        pause_habit(d[len("pause_habit_"):], True)
        await q.edit_message_text("⏸️ تم إيقاف العادة مؤقتاً.", reply_markup=habits_menu_keyboard())
    elif d.startswith("resume_habit_"):
        pause_habit(d[len("resume_habit_"):], False)
        await q.edit_message_text("▶️ تم استئناف العادة!", reply_markup=habits_menu_keyboard())
    elif d.startswith("graph_habit_"):
        await _habit_graph(update, uid, d[len("graph_habit_"):])
    elif d.startswith("del_habit_"):
        delete_habit(d[len("del_habit_"):]); await _habits_menu(update)
    elif d == "already_done":
        await q.answer("✅ سبق تسجيلها اليوم!", show_alert=True)

    # ── Goals ────────────────────────────────────────────────
    elif d.startswith("view_goal_"):
        await _goal_detail(update, uid, d[len("view_goal_"):])
    elif d.startswith("del_goal_"):
        delete_goal(d[len("del_goal_"):]); await _goals_menu(update, uid)

    # ── Analytics ────────────────────────────────────────────
    elif d == "analytics_weekly":  await _analytics_weekly(update, uid)
    elif d == "analytics_monthly": await _analytics_monthly(update, uid)
    elif d == "analytics_habits":  await _analytics_habits(update, uid)
    elif d == "analytics_peak":    await _analytics_peak(update, uid)

    # ── Store ────────────────────────────────────────────────
    elif d == "store_titles":    await _store_items(update, uid, "title")
    elif d == "store_badges":    await _store_items(update, uid, "badge")
    elif d == "store_boxes":     await _store_items(update, uid, "box")
    elif d == "store_boosts":    await _store_items(update, uid, "boost")
    elif d == "store_inventory": await _inventory_page(update, uid)
    elif d.startswith("buy_"):   await _buy_item(update, uid, d[4:])

    # ── AI ───────────────────────────────────────────────────
    elif d == "ai_daily_plan":
        await q.edit_message_text("⏳ جاري إعداد خطة اليوم...")
        plan = generate_daily_plan(user)
        await q.edit_message_text(f"📅 *خطة يومك*\n\n{plan}", parse_mode="Markdown",
                                   reply_markup=back_keyboard("menu_ai"))
    elif d == "ai_weekly_plan":
        await q.edit_message_text("⏳ جاري إعداد خطة الأسبوع...")
        plan = ask_coach("اصنع لي خطة أسبوع مثالية مع توزيع المهام على أيام الأسبوع.", user)
        await q.edit_message_text(f"📅 *خطة أسبوعك*\n\n{plan}", parse_mode="Markdown",
                                   reply_markup=back_keyboard("menu_ai"))
    elif d == "ai_study_plan":
        await q.edit_message_text("⏳ جاري إعداد خطة دراسة...")
        plan = ask_coach("اصنع لي خطة دراسية مفصلة تناسب شخصاً يريد تطوير نفسه.", user)
        await q.edit_message_text(f"📚 *خطة الدراسة*\n\n{plan}", parse_mode="Markdown",
                                   reply_markup=back_keyboard("menu_ai"))
    elif d == "ai_fitness_plan":
        await q.edit_message_text("⏳ جاري إعداد خطة رياضية...")
        plan = ask_coach("اصنع لي خطة رياضية أسبوعية للمبتدئين، متوازنة وقابلة للتطبيق.", user)
        await q.edit_message_text(f"🏋️ *الخطة الرياضية*\n\n{plan}", parse_mode="Markdown",
                                   reply_markup=back_keyboard("menu_ai"))
    elif d == "ai_motivate":
        await q.edit_message_text("⏳...")
        msg = motivate(user)
        await q.edit_message_text(f"💪 *تحفيز*\n\n{msg}", parse_mode="Markdown",
                                   reply_markup=back_keyboard("menu_ai"))
    elif d == "ai_analyze":
        habits = get_user_habits(uid)
        if not habits:
            await q.answer("لا توجد عادات بعد!", show_alert=True); return
        await q.edit_message_text("⏳ جاري التحليل...")
        analysis = analyze_habits(user, habits)
        await q.edit_message_text(f"📊 *تحليل عاداتك*\n\n{analysis}", parse_mode="Markdown",
                                   reply_markup=back_keyboard("menu_ai"))
    elif d == "ai_weakness":
        await q.edit_message_text("⏳ جاري تحليل نقاط ضعفك...")
        stats   = get_daily_stats(uid)
        ha_data = get_habit_analytics(uid)
        neglected = ha_data["most_neglected"]["name"] if ha_data.get("most_neglected") else "لا توجد"
        prompt  = (f"استناداً إلى بياناتي: معدل الإنجاز اليومي {stats['completion_rate']}%، "
                   f"أكثر عادة أهملتها: {neglected}. حلّل نقاط ضعفي واقترح تحسينات.")
        msg = ask_coach(prompt, user)
        await q.edit_message_text(f"🔍 *تحليل نقاط ضعفك*\n\n{msg}", parse_mode="Markdown",
                                   reply_markup=back_keyboard("menu_ai"))
    # ── Community ────────────────────────────────────────────
    elif d == "comm_challenges":   await _challenges_page(update, uid)
    elif d == "comm_leaderboard":  await _leaderboard(update, uid)
    elif d == "comm_friends":      await _friends_page(update, uid)
    elif d == "comm_requests":     await _friend_requests_page(update, uid)
    elif d.startswith("join_ch_"):
        ok = join_challenge(d[len("join_ch_"):], uid)
        await q.answer("✅ انضممت للتحدي!" if ok else "سبق انضمامك!", show_alert=True)
        await _challenges_page(update, uid)
    elif d.startswith("accept_fr_"):
        accept_friend(d[len("accept_fr_"):])
        await q.answer("✅ تم قبول الطلب!", show_alert=True)
        await _friends_page(update, uid)

    # ── Settings ─────────────────────────────────────────────
    elif d.startswith("rdone_"):
        await _complete_task_cb(update, uid, d[len("rdone_"):])
    elif d == "reminder_skip":
        await q.answer("حسناً! سنذكّرك لاحقاً 💪", show_alert=True)
    elif d.startswith("remind_task_"):
        return await remind_task_start(update, context)
    elif d == "my_reminders":
        await my_reminders_page(update, uid)
    elif d == "toggle_notif":
        s = user.get("settings", {})
        s["notifications"] = not s.get("notifications", True)
        update_user(uid, {"settings": s})
        await _settings_page(update, get_user(uid))
    elif d == "toggle_report":
        s = user.get("settings", {})
        s["midnight_report"] = not s.get("midnight_report", True)
        update_user(uid, {"settings": s})
        await _settings_page(update, get_user(uid))
    elif d == "toggle_strict":
        s = user.get("settings", {})
        s["strict_mode"] = not s.get("strict_mode", False)
        update_user(uid, {"settings": s})
        await _settings_page(update, get_user(uid))

    # ── Backup ───────────────────────────────────────────────
    elif d == "backup_json":
        data = export_as_json_bytes(uid)
        bio  = io.BytesIO(data); bio.name = f"backup_{date.today()}.json"
        await update.effective_message.reply_document(bio, caption="📦 نسخة احتياطية ✅")
    elif d == "backup_report":
        txt = build_text_report(uid)
        await update.effective_message.reply_text(f"```\n{txt}\n```", parse_mode="Markdown")

    elif d == "cancel":
        _tmp.pop(uid, None)
        await show_main_menu(update, context, user)


# ════════════════════════════════════════════════════════════
#  TASKS
# ════════════════════════════════════════════════════════════
async def _tasks_menu(update):
    await _edit(update, "📅 *المهام*\n\nاختر:", tasks_menu_keyboard())

async def _today_tasks(update, uid):
    tasks = get_today_tasks(uid)
    pi    = {"low":"🟢","medium":"🟡","high":"🟠","urgent":"🔴"}
    if not tasks:
        await _edit(update, "📋 *مهام اليوم*\n\nلا توجد مهام لليوم.", InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ أضف مهمة", callback_data="task_add")],
            [InlineKeyboardButton("🔙 رجوع",     callback_data="menu_tasks")],
        ])); return
    done  = sum(1 for t in tasks if t["status"] == "done")
    total = len(tasks)
    pct   = int(done/total*100)
    bar   = "█"*int(pct/10) + "░"*(10-int(pct/10))
    txt   = f"📋 *مهام اليوم* `{bar}` {done}/{total}\n\n"
    rows  = []
    for t in tasks:
        st  = "✅" if t["status"] == "done" else "⬜"
        lbl = f"{st} {pi.get(t['priority'],'⚪')} {t['title'][:32]}"
        rows.append([InlineKeyboardButton(lbl, callback_data=f"view_task_{t['_id']}")])
    rows.append([
        InlineKeyboardButton("➕ مهمة جديدة", callback_data="task_add"),
        InlineKeyboardButton("🔙 رجوع",       callback_data="menu_tasks"),
    ])
    await _edit(update, txt, InlineKeyboardMarkup(rows))

async def _all_tasks(update, uid):
    tasks = get_user_tasks(uid, status="pending")
    pi    = {"low":"🟢","medium":"🟡","high":"🟠","urgent":"🔴"}
    if not tasks:
        await _edit(update, "📂 لا توجد مهام معلّقة!", InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ أضف مهمة", callback_data="task_add")],
            [InlineKeyboardButton("🔙 رجوع",     callback_data="menu_tasks")],
        ])); return
    rows = []
    for t in tasks[:15]:
        hint = f" • {fmt_date(t.get('due_date'))}" if t.get("due_date") else ""
        lbl  = f"{pi.get(t['priority'],'⚪')} {t['title'][:28]}{hint}"
        rows.append([InlineKeyboardButton(lbl, callback_data=f"view_task_{t['_id']}")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_tasks")])
    await _edit(update, f"📂 *المهام المعلّقة* ({len(tasks)})\n\n", InlineKeyboardMarkup(rows))

async def _done_tasks(update, uid):
    tasks = get_user_tasks(uid, status="done")
    txt   = f"✅ *المكتملة* ({len(tasks)})\n\n" + ("".join(f"✅ {t['title']}\n" for t in tasks[:12]) if tasks else "لا توجد.")
    await _edit(update, txt, back_keyboard("menu_tasks"))

async def _task_detail(update, task_id):
    task = get_task_by_id(task_id)
    if not task:
        await update.callback_query.answer("المهمة غير موجودة!", show_alert=True); return
    pi   = {"low":"🟢 منخفضة","medium":"🟡 متوسطة","high":"🟠 عالية","urgent":"🔴 عاجلة"}
    st   = "✅ مكتملة" if task["status"] == "done" else "⬜ معلّقة"
    rpt  = {"once":"مرة واحدة","daily":"يومي","weekly":"أسبوعي","monthly":"شهري"}.get(task.get("repeat_type","once"),"")
    st_t = f"\n⏰ من: {task['start_time']} → {task['end_time']}" if task.get("start_time") else ""
    txt  = (
        f"📋 *{task['title']}*\n{'─'*20}\n"
        f"🎯 {pi.get(task['priority'],task['priority'])}\n"
        f"📁 {task.get('category','عام')}\n"
        f"📅 {fmt_date(task.get('due_date'))}  🔄 {rpt}"
        f"{st_t}\n"
        f"📊 {st}\n"
    )
    if task.get("notes"): txt += f"\n📝 {task['notes']}"
    rows = []
    if task["status"] == "pending":
        rows.append([InlineKeyboardButton("✅ أنجزت", callback_data=f"done_task_{task_id}")])
        rows.append([InlineKeyboardButton("⏰ ذكّرني", callback_data=f"remind_task_{task_id}")])
    rows.append([
        InlineKeyboardButton("✏️ تعديل",  callback_data=f"edit_task_{task_id}"),
        InlineKeyboardButton("🗑️ حذف",   callback_data=f"del_task_{task_id}"),
    ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="task_today")])
    await update.callback_query.edit_message_text(txt, parse_mode="Markdown",
                                                   reply_markup=InlineKeyboardMarkup(rows))

def _create_next_repeat(task: dict, uid: int):
    """ينشئ نسخة التالية من المهمة المتكررة."""
    from datetime import timedelta
    repeat = task.get("repeat_type", "once")
    if repeat == "once" or not task.get("due_date"): return
    try:
        old_date = date.fromisoformat(task["due_date"])
        if repeat == "daily":   new_date = old_date + timedelta(days=1)
        elif repeat == "weekly": new_date = old_date + timedelta(weeks=1)
        elif repeat == "monthly":
            m = old_date.month % 12 + 1
            y = old_date.year + (1 if old_date.month == 12 else 0)
            new_date = old_date.replace(year=y, month=m)
        else: return
        data = {k: task[k] for k in
                ["title","priority","category","notes","repeat_type","start_time","end_time"]
                if k in task}
        data["due_date"] = new_date.strftime("%Y-%m-%d")
        create_task(uid, data)
    except Exception as e:
        logger.warning(f"repeat task error: {e}")

async def _complete_task_cb(update, uid, task_id):
    task   = complete_task(task_id)
    if not task:
        if update.callback_query:
            await update.callback_query.answer("المهمة غير موجودة!", show_alert=True)
        return
    result = award_task_completion(uid, task.get("priority","medium"))
    update_challenge_progress(uid, "tasks")
    new_ach = check_and_award(uid)

    # أنشئ التكرار التالي تلقائياً
    _create_next_repeat(task, uid)
    repeat_lbl = {"daily":"📅 تكررت غداً","weekly":"📅 تكررت الأسبوع القادم",
                  "monthly":"📅 تكررت الشهر القادم"}.get(task.get("repeat_type","once"),"")

    txt = (
        f"✅ *مهمة مكتملة!*\n\n📋 {task['title']}\n\n"
        f"⭐ +{result['xp_gained']} XP  |  💰 +{result['coins_gained']} عملة\n"
        f"`{get_xp_bar(result['progress'])}`"
    )
    if result["leveled_up"]:
        txt += f"\n\n🎊 *ترقية!* → {result['new_rank_emoji']} *{result['new_rank']}*"
    if repeat_lbl:
        txt += f"\n\n🔄 _{repeat_lbl} تلقائياً_"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 مهام اليوم", callback_data="task_today")],
        [InlineKeyboardButton("🏠 القائمة",    callback_data="back_main")],
    ])
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.effective_message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)
    await _ach_popups(update, new_ach)

async def _edit_task_menu(update, context, task_id):
    context.user_data["editing_task"] = task_id
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ العنوان",      callback_data="etf_title"),
         InlineKeyboardButton("🎯 الأولوية",     callback_data="etf_priority")],
        [InlineKeyboardButton("📅 التاريخ",      callback_data="etf_date"),
         InlineKeyboardButton("📝 ملاحظات",      callback_data="etf_notes")],
        [InlineKeyboardButton("❌ إلغاء",         callback_data="cancel")],
    ])
    await update.callback_query.edit_message_text("✏️ *تعديل المهمة*\n\nاختر الحقل:", parse_mode="Markdown", reply_markup=kb)
    return EDIT_TASK_FIELD

async def edit_task_field_chosen(update, context):
    q   = update.callback_query; await q.answer()
    fld = q.data.replace("etf_","")
    context.user_data["edit_field"] = fld
    prompts = {"title":"اكتب العنوان الجديد:","priority":"اكتب الأولوية (low/medium/high/urgent):","date":"اكتب التاريخ (YYYY-MM-DD) أو 'none':","notes":"اكتب الملاحظات:"}
    await q.edit_message_text(prompts.get(fld,"اكتب القيمة الجديدة:"))
    return EDIT_TASK_VALUE

async def edit_task_value_received(update, context):
    uid   = update.effective_user.id
    tid   = context.user_data.get("editing_task")
    fld   = context.user_data.get("edit_field")
    val   = update.message.text.strip()
    if not tid or not fld:
        await update.message.reply_text("❌ خطأ. أعد المحاولة."); return ConversationHandler.END
    db_field = {"title":"title","priority":"priority","date":"due_date","notes":"notes"}.get(fld, fld)
    update_task(tid, {db_field: None if val.lower()=="none" else val})
    await update.message.reply_text("✅ تم التعديل!", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
#  ADD TASK CONVERSATION
# ════════════════════════════════════════════════════════════
async def add_task_start(update, context):
    uid = update.effective_user.id
    _tmp[uid] = {"flow":"task"}
    await _edit(update, "📝 *مهمة جديدة*\n\nاكتب العنوان:",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]]))
    return TASK_TITLE

async def task_got_title(update, context):
    uid   = update.effective_user.id
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("❌ العنوان لا يمكن أن يكون فارغاً:"); return TASK_TITLE
    _tmp.setdefault(uid,{})["title"] = title
    await update.message.reply_text(f"✏️ *{title}*\n\nاختر الأولوية:", parse_mode="Markdown",
                                     reply_markup=priority_keyboard())
    return TASK_PRIORITY

async def task_got_priority(update, context):
    q = update.callback_query; await q.answer()
    uid = update.effective_user.id
    pri = q.data.replace("priority_","")
    _tmp.setdefault(uid,{})["priority"] = pri
    await q.edit_message_text(f"✏️ *{_tmp[uid]['title']}*\n🎯 {fmt_priority(pri)}\n\nاختر الفئة:",
                               parse_mode="Markdown", reply_markup=category_keyboard())
    return TASK_CATEGORY

async def task_got_category(update, context):
    q = update.callback_query; await q.answer()
    uid = update.effective_user.id
    cat = CATEGORY_LABELS.get(q.data,"⭐ عام")
    _tmp.setdefault(uid,{})["category"] = cat
    t   = _tmp[uid]
    await q.edit_message_text(
        f"✏️ *{t['title']}*\n🎯 {fmt_priority(t['priority'])}\n📁 {cat}\n\nمتى موعد المهمة؟",
        parse_mode="Markdown", reply_markup=due_date_keyboard())
    return TASK_DUE_DATE

async def task_got_due(update, context):
    q = update.callback_query; await q.answer()
    uid = update.effective_user.id
    due = None if q.data=="due_none" else q.data.replace("due_","")
    _tmp.setdefault(uid,{})["due_date"] = due
    await q.edit_message_text(
        f"🔄 *هل تتكرر المهمة؟*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("1️⃣ مرة واحدة", callback_data="repeat_once"),
             InlineKeyboardButton("📅 يومية",       callback_data="repeat_daily")],
            [InlineKeyboardButton("📆 أسبوعية",    callback_data="repeat_weekly"),
             InlineKeyboardButton("🗓️ شهرية",      callback_data="repeat_monthly")],
        ]))
    return TASK_REPEAT

async def task_got_repeat(update, context):
    q = update.callback_query; await q.answer()
    uid    = update.effective_user.id
    repeat = q.data.replace("repeat_","")
    _tmp.setdefault(uid,{})["repeat_type"] = repeat
    data    = _tmp.pop(uid,{})
    task_id = create_task(uid, data)
    xp_hint = {"low":10,"medium":20,"high":35,"urgent":50}.get(data.get("priority","medium"),20)
    rpt_lbl = {"once":"مرة واحدة","daily":"يومية","weekly":"أسبوعية","monthly":"شهرية"}.get(repeat,"")
    txt = (
        f"✅ *تمت الإضافة!*\n\n"
        f"📋 {data['title']}\n"
        f"🎯 {fmt_priority(data.get('priority','medium'))}\n"
        f"📁 {data.get('category','عام')}\n"
        f"📅 {fmt_date(data.get('due_date'))}  🔄 {rpt_lbl}\n\n"
        f"⭐ ستكسب *{xp_hint} XP* عند الإنجاز!"
    )
    await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 مهام اليوم", callback_data="task_today")],
        [InlineKeyboardButton("➕ مهمة أخرى",  callback_data="task_add")],
        [InlineKeyboardButton("🏠 القائمة",    callback_data="back_main")],
    ]))
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
#  HABITS
# ════════════════════════════════════════════════════════════
async def _habits_menu(update):
    await _edit(update, "🔥 *العادات*\n\nاختر:", habits_menu_keyboard())

async def _habits_list(update, uid):
    habits = get_user_habits(uid, status="all")
    if not habits:
        await _edit(update, "🔥 لا توجد عادات بعد.", InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ عادة جديدة", callback_data="habit_add")],
            [InlineKeyboardButton("🔙 رجوع",       callback_data="menu_habits")],
        ])); return
    rows = []
    for h in habits:
        st  = "⏸️" if h.get("status") == "paused" else "🟢"
        lbl = f"{st} {h.get('icon','⭐')} {h['name']} · 🔥{h.get('streak',0)}"
        rows.append([InlineKeyboardButton(lbl, callback_data=f"view_habit_{h['_id']}")])
    rows.append([InlineKeyboardButton("➕ جديدة", callback_data="habit_add"),
                 InlineKeyboardButton("🔙 رجوع", callback_data="menu_habits")])
    await _edit(update, f"🔥 *عاداتي* ({len(habits)})\n\n", InlineKeyboardMarkup(rows))

async def _habit_log_today_page(update, uid):
    habits = get_user_habits(uid)
    if not habits:
        await update.callback_query.answer("لا توجد عادات! أضف عادة أولاً.", show_alert=True); return
    logs  = get_habit_log_today(uid)
    done  = sum(1 for h in habits if logs.get(str(h["_id"])) == "done")
    rows  = []
    for h in habits:
        hid    = str(h["_id"])
        logged = logs.get(hid)
        p      = "✅" if logged=="done" else "⏭️" if logged=="skip" else "⬜"
        rows.append([InlineKeyboardButton(f"{p} {h.get('icon','⭐')} {h['name']}", callback_data=f"view_habit_{hid}")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_habits")])
    await _edit(update, f"✅ *تسجيل اليوم* ({done}/{len(habits)})\n\n", InlineKeyboardMarkup(rows))

async def _habit_detail(update, uid, habit_id):
    from bson import ObjectId
    from modules.database import get_db
    h = get_db().habits.find_one({"_id": ObjectId(habit_id)})
    if not h:
        await update.callback_query.answer("العادة غير موجودة!", show_alert=True); return
    logs   = get_habit_log_today(uid)
    logged = logs.get(habit_id)
    paused = h.get("status") == "paused"
    txt    = (
        f"{h.get('icon','⭐')} *{h['name']}*\n{'─'*18}\n"
        f"🔥 السلسلة: *{h.get('streak',0)}* يوم\n"
        f"🏅 الأعلى: *{h.get('best_streak',0)}* يوم\n"
        f"✅ الإجمالي: *{h.get('total_completions',0)}* مرة\n"
        f"📊 الحالة: {'⏸️ موقوف مؤقتاً' if paused else '🟢 نشط'}\n"
    )
    rows = []
    if not paused:
        if logged:
            rows.append([InlineKeyboardButton("✅ سُجِّلت اليوم", callback_data="already_done")])
        else:
            rows.append([
                InlineKeyboardButton("✅ أنجزت",   callback_data=f"done_habit_{habit_id}"),
                InlineKeyboardButton("⏭️ تخطّيت", callback_data=f"skip_habit_{habit_id}"),
            ])
        rows.append([InlineKeyboardButton("📊 الرسم البياني", callback_data=f"graph_habit_{habit_id}")])
        rows.append([InlineKeyboardButton("⏸️ إيقاف مؤقت",   callback_data=f"pause_habit_{habit_id}")])
    else:
        rows.append([InlineKeyboardButton("▶️ استئناف",       callback_data=f"resume_habit_{habit_id}")])
    rows.append([InlineKeyboardButton("🗑️ حذف", callback_data=f"del_habit_{habit_id}"),
                 InlineKeyboardButton("🔙 رجوع", callback_data="habit_log_today")])
    await update.callback_query.edit_message_text(txt, parse_mode="Markdown",
                                                   reply_markup=InlineKeyboardMarkup(rows))

async def _log_habit_cb(update, uid, habit_id, action):
    from bson import ObjectId
    from modules.database import get_db
    h  = get_db().habits.find_one({"_id": ObjectId(habit_id)})
    if not h:
        await update.callback_query.answer("العادة غير موجودة!", show_alert=True); return
    ok = log_habit(uid, habit_id, action)
    if not ok:
        await update.callback_query.answer("✅ سبق تسجيلها اليوم!", show_alert=True); return
    if action == "done":
        ns     = h.get("streak",0) + 1
        result = award_habit_completion(uid, ns)
        update_challenge_progress(uid, "habits")
        new_ach = check_and_award(uid) + (check_first_habit(uid) if h.get("total_completions",0)==0 else [])
        txt = (
            f"✅ *عادة مكتملة!*\n\n{h.get('icon','⭐')} {h['name']}\n"
            f"🔥 السلسلة: *{ns}* يوم\n\n"
            f"⭐ +{result['xp_gained']} XP  |  💰 +{result['coins_gained']} عملة"
        )
        if ns in (7,14,21,30,60,100):
            txt += f"\n🎉 *{ns} يوم متواصل!* رائع!"
        if result["leveled_up"]:
            txt += f"\n\n🎊 ترقية → {result['new_rank_emoji']} *{result['new_rank']}*"
        await update.callback_query.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ تسجيل اليوم", callback_data="habit_log_today")],
                [InlineKeyboardButton("🏠 القائمة",     callback_data="back_main")],
            ]))
        await _ach_popups(update, new_ach)
    else:
        await update.callback_query.edit_message_text(
            f"⏭️ تم تخطّي *{h['name']}* اليوم.", parse_mode="Markdown",
            reply_markup=back_keyboard("habit_log_today"))

async def _habit_graph(update, uid, habit_id):
    from bson import ObjectId
    from modules.database import get_db
    h = get_db().habits.find_one({"_id": ObjectId(habit_id)})
    if not h:
        await update.callback_query.answer("غير موجود!", show_alert=True); return
    graph = build_habit_streak_graph(uid, habit_id, 21)
    txt   = f"📊 *{h.get('icon','⭐')} {h['name']} — آخر 21 يوم*\n\n{graph}\n\n🟢 أنجزت  🔴 تخطّيت  ⬜ لم تُسجَّل"
    await update.callback_query.edit_message_text(txt, parse_mode="Markdown",
                                                   reply_markup=back_keyboard(f"view_habit_{habit_id}"))

async def _habit_stats_page(update, uid):
    habits = get_user_habits(uid)
    if not habits:
        await update.callback_query.answer("لا توجد عادات!", show_alert=True); return
    txt = "📊 *تحليل العادات*\n\n"
    for h in habits[:8]:
        txt += (f"{h.get('icon','⭐')} *{h['name']}*\n"
                f"   🔥 {h.get('streak',0)} · 🏅 {h.get('best_streak',0)} · ✅ {h.get('total_completions',0)}\n\n")
    await _edit(update, txt, back_keyboard("menu_habits"))


# ════════════════════════════════════════════════════════════
#  ADD HABIT CONVERSATION
# ════════════════════════════════════════════════════════════
async def add_habit_start(update, context):
    uid = update.effective_user.id; _tmp[uid] = {"flow":"habit"}
    await _edit(update, "🌱 *عادة جديدة*\n\nاكتب اسم العادة:",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]]))
    return HABIT_NAME

async def habit_got_name(update, context):
    uid = update.effective_user.id; name = update.message.text.strip()
    _tmp.setdefault(uid,{})["name"] = name
    await update.message.reply_text(f"✏️ *{name}*\n\nاختر أيقونة:", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💪", callback_data="icon_💪"),
             InlineKeyboardButton("📚", callback_data="icon_📚"),
             InlineKeyboardButton("🏃", callback_data="icon_🏃"),
             InlineKeyboardButton("💧", callback_data="icon_💧")],
            [InlineKeyboardButton("🧘", callback_data="icon_🧘"),
             InlineKeyboardButton("🌙", callback_data="icon_🌙"),
             InlineKeyboardButton("✍️", callback_data="icon_✍️"),
             InlineKeyboardButton("🎯", callback_data="icon_🎯")],
            [InlineKeyboardButton("⭐ افتراضي", callback_data="icon_⭐")],
        ]))
    return HABIT_ICON

async def habit_got_icon(update, context):
    uid = update.effective_user.id
    if update.callback_query:
        await update.callback_query.answer()
        icon = update.callback_query.data.replace("icon_","")
    else:
        icon = (update.message.text.strip()[:2] or "⭐")
    _tmp.setdefault(uid,{})["icon"] = icon
    data = _tmp.pop(uid,{})
    create_habit(uid, data)
    txt = f"✅ *تمت الإضافة!*\n\n{icon} *{data['name']}*\n\n⭐ ستكسب *15 XP* يومياً!"
    kb  = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ سجّلها اليوم", callback_data="habit_log_today")],
        [InlineKeyboardButton("🏠 القائمة",      callback_data="back_main")],
    ])
    if update.callback_query: await update.callback_query.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)
    else:                      await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
#  GOALS
# ════════════════════════════════════════════════════════════
async def _goals_menu(update, uid):
    goals = _goals_list(uid)
    if not goals:
        await _edit(update, "🎯 *الأهداف*\n\nلا توجد أهداف بعد.\nأضف هدفاً وتتبّع تقدمك!", InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ هدف جديد", callback_data="goal_add")],
            [InlineKeyboardButton("🔙 القائمة",   callback_data="back_main")],
        ])); return
    rows = []
    for g in goals:
        pct = int(g.get("progress",0)/g.get("target",100)*100) if g.get("target") else 0
        lbl = f"🎯 {g['title'][:25]} — {pct}%"
        rows.append([InlineKeyboardButton(lbl, callback_data=f"view_goal_{g['_id']}")])
    rows.append([InlineKeyboardButton("➕ هدف جديد", callback_data="goal_add"),
                 InlineKeyboardButton("🔙 القائمة",   callback_data="back_main")])
    await _edit(update, f"🎯 *أهدافي* ({len(goals)})\n\n", InlineKeyboardMarkup(rows))

async def _goal_detail(update, uid, goal_id):
    from bson import ObjectId
    from modules.database import get_db
    g = get_db().goals.find_one({"_id": ObjectId(goal_id)})
    if not g:
        await update.callback_query.answer("الهدف غير موجود!", show_alert=True); return
    bar = goal_progress_bar(g.get("progress",0), g.get("target",100))
    dl  = f"📅 الموعد: {g.get('deadline','غير محدد')}\n" if g.get("deadline") else ""
    txt = (
        f"🎯 *{g['title']}*\n{'─'*20}\n"
        f"📁 {g.get('category','عام')}\n"
        f"📊 التقدم: `{bar}`\n"
        f"🔢 {g.get('progress',0)} / {g.get('target',100)} {g.get('unit','%')}\n"
        f"{dl}"
        f"📌 الحالة: {'✅ مكتمل' if g.get('status')=='done' else '🔄 جارٍ'}\n"
    )
    rows = []
    if g.get("status") != "done":
        rows.append([InlineKeyboardButton("📈 تحديث التقدم", callback_data=f"update_goal_{goal_id}")])
    rows.append([InlineKeyboardButton("🗑️ حذف",  callback_data=f"del_goal_{goal_id}"),
                 InlineKeyboardButton("🔙 رجوع",  callback_data="menu_goals")])
    await update.callback_query.edit_message_text(txt, parse_mode="Markdown",
                                                   reply_markup=InlineKeyboardMarkup(rows))

async def goal_update_start(update, context):
    q   = update.callback_query
    await q.answer()
    goal_id = q.data[len("update_goal_"):]
    context.user_data["updating_goal"] = goal_id
    await q.edit_message_text("📝 كم وصلت؟ اكتب الرقم الجديد (مثال: 45):")
    return GOAL_UPDATE_VALUE

async def goal_update_value(update, context):
    uid   = update.effective_user.id
    gid   = context.user_data.get("updating_goal","")
    try:  val = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً:"); return GOAL_UPDATE_VALUE
    g = update_goal_progress(gid, val)
    if not g:
        await update.message.reply_text("❌ الهدف غير موجود."); return ConversationHandler.END
    bar = goal_progress_bar(g["progress"], g.get("target",100))
    done_msg = "\n\n🎉 *تهانينا! أنجزت الهدف!*" if g["status"]=="done" else ""
    await update.message.reply_text(
        f"✅ تم التحديث!\n\n`{bar}`\n{g['progress']}/{g.get('target',100)} {g.get('unit','%')}{done_msg}",
        parse_mode="Markdown", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
#  ADD GOAL CONVERSATION
# ════════════════════════════════════════════════════════════
async def add_goal_start(update, context):
    uid = update.effective_user.id; _tmp[uid] = {"flow":"goal"}
    await _edit(update, "🎯 *هدف جديد*\n\nاكتب عنوان الهدف (مثال: إنهاء كتاب، خسارة 10 كيلو):",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]]))
    return GOAL_TITLE

async def goal_got_title(update, context):
    uid = update.effective_user.id; _tmp.setdefault(uid,{})["title"] = update.message.text.strip()
    await update.message.reply_text("🔢 ما هو الهدف الرقمي؟ (مثال: 100 لصفحات كتاب، 10 لكيلوجرام)\nاكتب الرقم فقط:")
    return GOAL_TARGET

async def goal_got_target(update, context):
    uid = update.effective_user.id
    try:  target = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً (مثال: 100):"); return GOAL_TARGET
    _tmp.setdefault(uid,{})["target"] = target
    await update.message.reply_text("📏 ما هي الوحدة؟ (مثال: صفحة، كيلو، تمرين، %):")
    return GOAL_UNIT

async def goal_got_unit(update, context):
    uid = update.effective_user.id; _tmp.setdefault(uid,{})["unit"] = update.message.text.strip()
    await update.message.reply_text("📅 ما هو الموعد النهائي؟ (اكتب YYYY-MM-DD أو 'لا موعد'):")
    return GOAL_DEADLINE

async def goal_got_deadline(update, context):
    uid  = update.effective_user.id
    raw  = update.message.text.strip()
    dl   = None if "لا" in raw or "no" in raw.lower() else raw
    _tmp.setdefault(uid,{})["deadline"] = dl
    data = _tmp.pop(uid,{})
    create_goal(uid, data)
    await update.message.reply_text(
        f"✅ *هدف جديد!*\n\n🎯 {data['title']}\n🔢 الهدف: {data['target']} {data.get('unit','')}\n📅 الموعد: {dl or 'غير محدد'}",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 أهدافي",  callback_data="menu_goals")],
            [InlineKeyboardButton("🏠 القائمة", callback_data="back_main")],
        ]))
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
#  ANALYTICS
# ════════════════════════════════════════════════════════════
async def _analytics_menu(update):
    await _edit(update, "📊 *تحليلاتي*\n\nاختر:", analytics_menu_keyboard())

async def _analytics_weekly(update, uid):
    await update.callback_query.edit_message_text("⏳ جاري التحليل...")
    w   = get_weekly_stats(uid)
    txt = build_weekly_chart(w)
    if w["best_day"]:  txt += f"\n\n🏆 أفضل يوم: *{w['best_day']['day_name']}*"
    if w["worst_day"]: txt += f"\n⚠️ أضعف يوم: *{w['worst_day']['day_name']}*"
    await update.callback_query.edit_message_text(txt, parse_mode="Markdown",
                                                   reply_markup=analytics_menu_keyboard())

async def _analytics_monthly(update, uid):
    await update.callback_query.edit_message_text("⏳ جاري التحليل...")
    m   = get_monthly_stats(uid)
    bar = "█"*int(m["monthly_rate"]/10) + "░"*(10-int(m["monthly_rate"]/10))
    txt = (
        f"📆 *تحليل الشهر*\n{'─'*22}\n\n"
        f"✅ المنجزة: *{m['total_done']}/{m['total_tasks']}*\n"
        f"📊 المعدل: `{bar}` {m['monthly_rate']}%\n"
        f"🌟 أيام مثالية: *{m['perfect_days']}* يوم\n"
    )
    await update.callback_query.edit_message_text(txt, parse_mode="Markdown",
                                                   reply_markup=analytics_menu_keyboard())

async def _analytics_habits(update, uid):
    await update.callback_query.edit_message_text("⏳ جاري التحليل...")
    data = get_habit_analytics(uid)
    if not data["habits"]:
        await update.callback_query.edit_message_text("لا توجد عادات!", reply_markup=back_keyboard("menu_analytics")); return
    txt = "📊 *تحليل العادات (30 يوم)*\n\n"
    for h in data["habits"]:
        bar = "█"*int(h["rate_30d"]/10) + "░"*(10-int(h["rate_30d"]/10))
        txt += f"{h['icon']} *{h['name']}*\n`{bar}` {h['rate_30d']}% | 🔥{h['streak']}\n\n"
    if data["most_neglected"]:  txt += f"⚠️ الأكثر إهمالاً: *{data['most_neglected']['name']}*\n"
    if data["most_consistent"]: txt += f"🏆 الأكثر التزاماً: *{data['most_consistent']['name']}*\n"
    await update.callback_query.edit_message_text(txt, parse_mode="Markdown",
                                                   reply_markup=back_keyboard("menu_analytics"))

async def _analytics_peak(update, uid):
    hour_data = get_most_productive_hour(uid)
    day_data  = get_most_productive_day(uid)
    txt = "⏰ *أوقات ذروة الإنتاج*\n\n"
    if hour_data["best_hour"]:
        txt += f"🕐 أكثر ساعة إنتاجاً: *{hour_data['best_hour']}*\n"
        for h in hour_data["top_hours"]:
            txt += f"   {h['hour']}: {h['count']} مهمة\n"
    else:
        txt += "🕐 لا توجد بيانات كافية للساعات بعد.\n"
    txt += "\n"
    if day_data["best_day"]:
        txt += f"📅 أكثر يوم إنتاجاً: *{day_data['best_day']}*\n"
        for d in day_data["top_days"]:
            txt += f"   {d['day']}: {d['count']} مهمة\n"
    else:
        txt += "📅 لا توجد بيانات كافية للأيام بعد."
    txt += "\n\n_أنجز أكثر مهام لتظهر البيانات!_"
    await update.callback_query.edit_message_text(txt, parse_mode="Markdown",
                                                   reply_markup=back_keyboard("menu_analytics"))

async def _show_calendar(update, uid):
    await update.callback_query.edit_message_text("⏳ جاري بناء التقويم...")
    txt = build_calendar_text(uid)
    await update.callback_query.edit_message_text(txt, parse_mode="Markdown",
                                                   reply_markup=back_keyboard("back_main"))


# ════════════════════════════════════════════════════════════
#  STORE
# ════════════════════════════════════════════════════════════
async def _store_main(update):
    await _edit(update, "🛒 *المتجر*\n\nاختر فئة:", store_menu_keyboard())

async def _store_items(update, uid, itype):
    user  = get_user(uid)
    coins = user.get("coins",0) if user else 0
    items = get_store_items_by_type(itype)
    inv   = user.get("inventory",[]) if user else []
    ICONS = {"title":"🏷️ الألقاب","badge":"🏅 الشارات","box":"🎁 الصناديق","boost":"⭐ معزز XP"}
    txt   = f"{ICONS.get(itype,'🛒')}\n💰 رصيدك: *{coins:,}* عملة\n\n"
    rows  = []
    for it in items:
        owned  = it["id"] in inv and it["type"] != "box"
        status = "✅" if owned else ("💰" if coins >= it["price"] else "🔒")
        lbl    = f"{status} {it['name']} — {it['price']:,} عملة"
        cb     = "already_owned" if owned else f"buy_{it['id']}"
        rows.append([InlineKeyboardButton(lbl, callback_data=cb)])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_store")])
    await _edit(update, txt, InlineKeyboardMarkup(rows))

async def _buy_item(update, uid, item_id):
    result = buy_item(uid, item_id)
    user   = get_user(uid); coins = user.get("coins",0) if user else 0
    if result["success"]:
        rw  = result.get("reward")
        txt = f"{result['message']}" + (f"\n\n🎁 *جائزتك:*\n{rw['label']}" if rw else "") + f"\n\n💰 المتبقي: *{coins:,}*"
        kb  = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 المتجر", callback_data="menu_store")],
                                    [InlineKeyboardButton("🏠 القائمة", callback_data="back_main")]])
    else:
        txt = f"❌ {result['message']}"; kb = back_keyboard("menu_store")
    await update.callback_query.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)

async def _inventory_page(update, uid):
    items = get_inventory(uid); user = get_user(uid)
    if not items:
        await _edit(update, "🎒 *حقيبتي*\n\nفارغة! تسوّق من المتجر.", InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 المتجر", callback_data="menu_store")],
            [InlineKeyboardButton("🔙 رجوع",   callback_data="back_main")],
        ])); return
    ICONS = {"title":"🏷️","badge":"🏅","box":"🎁","boost":"⭐"}
    txt = "🎒 *حقيبتي*\n\n" + "".join(f"{ICONS.get(i['type'],'📦')} {i['name']}\n" for i in items)
    if user and user.get("equipped_title"):
        txt += f"\n✨ *اللقب المفعّل:* {user['equipped_title']}"
    await _edit(update, txt, back_keyboard("menu_store"))


# ════════════════════════════════════════════════════════════
#  LEADERBOARD
# ════════════════════════════════════════════════════════════
async def _leaderboard(update, uid):
    from modules.database import get_db
    db    = get_db()
    top   = list(db.users.find().sort("xp",-1).limit(10))
    medals= ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    txt   = "🏆 *الترتيب العالمي*\n\n"
    my_pos = None
    for i,u in enumerate(top):
        me   = " 👈" if u["user_id"]==uid else ""
        txt += f"{medals[i]} {u.get('rank_emoji','🌱')} *{u.get('name','?')[:15]}*{me}\n   ⭐ {u.get('xp',0):,} XP  🔥 {u.get('streak',0)} يوم\n\n"
        if u["user_id"]==uid: my_pos = i+1
    if not my_pos:
        all_u = list(db.users.find().sort("xp",-1))
        for i,u in enumerate(all_u):
            if u["user_id"]==uid: my_pos=i+1; break
        if my_pos: txt += f"📍 *مرتبتك:* #{my_pos}"
    await _edit(update, txt, back_keyboard("back_main"))


# ════════════════════════════════════════════════════════════
#  COMMUNITY
# ════════════════════════════════════════════════════════════
async def _community_menu(update, uid):
    reqs = get_pending_requests(uid)
    badge = f" ({len(reqs)})" if reqs else ""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 الترتيب العالمي", callback_data="comm_leaderboard")],
        [InlineKeyboardButton("⚔️ التحديات",         callback_data="comm_challenges")],
        [InlineKeyboardButton(f"👥 الأصدقاء{badge}", callback_data="comm_friends")],
        [InlineKeyboardButton("➕ إضافة صديق",       callback_data="friend_add")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")],
    ])
    await _edit(update, "👥 *المجتمع*\n\nتنافس وتحدَّ الآخرين:", kb)

async def _challenges_page(update, uid):
    my_chs   = get_active_challenges(uid)
    open_chs = get_open_challenges()
    txt  = "⚔️ *التحديات*\n\n"
    rows = []
    if my_chs:
        txt += f"*تحدياتك ({len(my_chs)}):*\n"
        for ch in my_chs:
            my_prog = next((p["progress"] for p in ch["participants"] if p["user_id"]==uid), 0)
            txt += f"• {ch['title']} — {my_prog}/{ch['target']}\n"
        txt += "\n"
    txt += "*تحديات مفتوحة:*\n"
    for ch in open_chs[:5]:
        joined = any(p["user_id"]==uid for p in ch.get("participants",[]))
        lbl    = f"✅ {ch['title']}" if joined else f"⚔️ {ch['title']} ({ch['target']} {ch['type']})"
        cb     = "already_joined" if joined else f"join_ch_{ch['_id']}"
        rows.append([InlineKeyboardButton(lbl, callback_data=cb)])
    rows.append([InlineKeyboardButton("➕ أنشئ تحدياً", callback_data="challenge_add")])
    rows.append([InlineKeyboardButton("🔙 رجوع",        callback_data="menu_community")])
    await _edit(update, txt, InlineKeyboardMarkup(rows))

async def _friends_page(update, uid):
    friends = get_friends(uid)
    reqs    = get_pending_requests(uid)
    txt  = "👥 *أصدقاؤك*\n\n"
    rows = []
    if friends:
        for f in friends:
            txt += f"{f.get('rank_emoji','🌱')} *{f.get('name','؟')}* — ⭐{f.get('xp',0):,}\n"
    else:
        txt += "لا توجد أصدقاء بعد.\n"
    if reqs:
        txt += f"\n📬 *طلبات معلّقة ({len(reqs)}):*\n"
        for r in reqs:
            from_u = get_user(r["from_id"])
            name   = from_u.get("name","؟") if from_u else "؟"
            txt   += f"• {name}\n"
            rows.append([InlineKeyboardButton(f"✅ قبول {name}", callback_data=f"accept_fr_{r['_id']}")])
    rows.append([InlineKeyboardButton("➕ إضافة صديق",  callback_data="friend_add")])
    rows.append([InlineKeyboardButton("🔙 رجوع",         callback_data="menu_community")])
    await _edit(update, txt, InlineKeyboardMarkup(rows))

async def _friend_requests_page(update, uid):
    await _friends_page(update, uid)


# ════════════════════════════════════════════════════════════
#  ADD FRIEND CONVERSATION
# ════════════════════════════════════════════════════════════
async def add_friend_start(update, context):
    await _edit(update, "➕ *إضافة صديق*\n\nأرسل معرّف المستخدم (User ID) للشخص الذي تريد إضافته:\n\n_يمكنه معرفة ID الخاص به بكتابة /start في البوت_",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]]))
    return FRIEND_ID

async def friend_id_received(update, context):
    uid = update.effective_user.id
    txt = update.message.text.strip()
    try:    fid = int(txt)
    except: await update.message.reply_text("❌ أدخل رقماً صحيحاً (User ID):"); return FRIEND_ID
    if fid == uid:
        await update.message.reply_text("❌ لا يمكنك إضافة نفسك!"); return FRIEND_ID
    result = send_friend_request(uid, fid)
    msgs = {"sent":"✅ تم إرسال طلب الصداقة!","already_friends":"✅ أنتما أصدقاء بالفعل.","already_sent":"⏳ سبق إرسال الطلب.","not_found":"❌ المستخدم غير موجود."}
    await update.message.reply_text(msgs.get(result,"❌"), reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
#  ADD CHALLENGE CONVERSATION
# ════════════════════════════════════════════════════════════
async def add_challenge_start(update, context):
    uid = update.effective_user.id; _tmp[uid] = {"flow":"challenge"}
    await _edit(update, "⚔️ *تحدٍّ جديد*\n\nاكتب عنوان التحدي:",
        InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]]))
    return CHALLENGE_TITLE

async def challenge_got_title(update, context):
    uid = update.effective_user.id; _tmp.setdefault(uid,{})["title"] = update.message.text.strip()
    await update.message.reply_text("📋 نوع التحدي:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ مهام",   callback_data="chtype_tasks"),
         InlineKeyboardButton("🔥 عادات", callback_data="chtype_habits")],
        [InlineKeyboardButton("⭐ XP",     callback_data="chtype_xp")],
    ]))
    return CHALLENGE_TYPE

async def challenge_got_type(update, context):
    q = update.callback_query; await q.answer()
    uid = update.effective_user.id
    _tmp.setdefault(uid,{})["type"] = q.data.replace("chtype_","")
    await q.edit_message_text("🔢 كم الهدف؟ (مثال: 10 مهام، 7 عادات):")
    return CHALLENGE_TARGET

async def challenge_got_target(update, context):
    uid = update.effective_user.id
    try:    target = int(update.message.text.strip())
    except: await update.message.reply_text("❌ أدخل رقماً:"); return CHALLENGE_TARGET
    _tmp.setdefault(uid,{})["target"] = target
    data = _tmp.pop(uid,{})
    create_challenge(uid, {**data, "duration_days": 7})
    await update.message.reply_text(
        f"✅ *تم إنشاء التحدي!*\n\n⚔️ {data['title']}\n🎯 الهدف: {target} {data.get('type','')}\n⏳ المدة: 7 أيام",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ التحديات", callback_data="comm_challenges")],
            [InlineKeyboardButton("🏠 القائمة",  callback_data="back_main")],
        ]))
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
#  AI
# ════════════════════════════════════════════════════════════
async def _ai_menu(update, user):
    txt = f"🤖 *المدرب الذكي*\n\nمرحباً {user['name']}! كيف أساعدك؟"
    kb  = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 خطة اليوم",       callback_data="ai_daily_plan"),
         InlineKeyboardButton("📆 خطة الأسبوع",     callback_data="ai_weekly_plan")],
        [InlineKeyboardButton("📚 خطة دراسة",       callback_data="ai_study_plan"),
         InlineKeyboardButton("🏋️ خطة رياضية",      callback_data="ai_fitness_plan")],
        [InlineKeyboardButton("💪 حفّزني",           callback_data="ai_motivate"),
         InlineKeyboardButton("🔍 نقاط ضعفي",       callback_data="ai_weakness")],
        [InlineKeyboardButton("📊 حلّل عاداتي",      callback_data="ai_analyze")],
        [InlineKeyboardButton("💬 تحدث معي بحرية",  callback_data="ai_free")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية",callback_data="back_main")],
    ])
    await _edit(update, txt, kb)

async def ai_free_start(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["ai_mode"] = True
    await q.edit_message_text(
        "🤖 *المدرب الذكي*\n\nاكتب سؤالك:\n\n_/menu للخروج_",
        parse_mode="Markdown"
    )
    return AI_CHAT

async def ai_free_chat(update, context):
    uid  = update.effective_user.id; user = get_user(uid)
    await update.message.reply_text("⏳ جاري التفكير...")
    reply = ask_coach(update.message.text, user)
    await update.message.reply_text(f"🤖 {reply}", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_main")]
    ]))
    return AI_CHAT


# ════════════════════════════════════════════════════════════
#  ACHIEVEMENTS
# ════════════════════════════════════════════════════════════
async def _achievements_page(update, uid):
    all_ach = get_all_achievements_status(uid)
    user    = get_user(uid)
    earned  = len(user.get("achievements",[]))
    txt     = f"🏆 *الإنجازات* ({earned}/{len(all_ach)})\n\n"
    for a in all_ach:
        txt += (f"✅ {a['icon']} *{a['name']}* — _{a['desc']}_\n" if a["unlocked"]
                else f"🔒 {a['name']}\n")
    await _edit(update, txt, back_keyboard("back_main"))


# ════════════════════════════════════════════════════════════
#  REMINDERS
# ════════════════════════════════════════════════════════════
async def remind_task_start(update, context):
    q = update.callback_query
    await q.answer()
    task_id = q.data[len("remind_task_"):]
    task = get_task_by_id(task_id)
    if not task:
        await q.answer("المهمة غير موجودة!", show_alert=True); return ConversationHandler.END
    context.user_data["remind_task_id"]    = task_id
    context.user_data["remind_task_title"] = task["title"]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ بعد 30 دقيقة", callback_data="rtime_30m"),
         InlineKeyboardButton("⏰ بعد ساعة",      callback_data="rtime_1h")],
        [InlineKeyboardButton("⏰ بعد ساعتين",    callback_data="rtime_2h"),
         InlineKeyboardButton("⏰ بعد 3 ساعات",   callback_data="rtime_3h")],
        [InlineKeyboardButton("✏️ وقت مخصص",      callback_data="rtime_custom")],
        [InlineKeyboardButton("❌ إلغاء",          callback_data="cancel")],
    ])
    await q.edit_message_text(
        f"⏰ *تذكير للمهمة:*\n_{task['title']}_\n\nاختر متى تريد التذكير:",
        parse_mode="Markdown", reply_markup=kb
    )
    return REMINDER_TIME

async def remind_task_quick(update, context):
    q = update.callback_query; await q.answer()
    from datetime import timedelta
    deltas = {"rtime_30m": 30, "rtime_1h": 60, "rtime_2h": 120, "rtime_3h": 180}
    minutes = deltas.get(q.data, 60)
    fire_at = datetime.utcnow() + timedelta(minutes=minutes)
    uid = update.effective_user.id
    create_reminder(uid, context.user_data["remind_task_id"],
                    context.user_data["remind_task_title"], fire_at)
    import pytz
    local = fire_at + timedelta(hours=3)  # GMT+3
    await q.edit_message_text(
        f"✅ تم ضبط التذكير!\n\n⏰ سيصلك الساعة *{local.strftime('%H:%M')}*",
        parse_mode="Markdown", reply_markup=back_keyboard("task_today")
    )
    return ConversationHandler.END

async def remind_task_custom(update, context):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "✏️ اكتب الوقت بصيغة *HH:MM* (مثال: 14:30)\n\n_التوقيت GMT+3_",
        parse_mode="Markdown"
    )
    return REMINDER_TIME

async def remind_task_time_text(update, context):
    uid = update.effective_user.id
    text = update.message.text.strip()
    try:
        h, m = map(int, text.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59): raise ValueError
    except ValueError:
        await update.message.reply_text("❌ صيغة خاطئة، اكتب مثل: 14:30"); return REMINDER_TIME
    from datetime import timedelta
    now_local = datetime.utcnow() + timedelta(hours=3)
    fire_local = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
    if fire_local <= now_local:
        fire_local += timedelta(days=1)
    fire_utc = fire_local - timedelta(hours=3)
    create_reminder(uid, context.user_data["remind_task_id"],
                    context.user_data["remind_task_title"], fire_utc)
    await update.message.reply_text(
        f"✅ تم ضبط التذكير!\n\n⏰ سيصلك الساعة *{fire_local.strftime('%H:%M')}*",
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

async def my_reminders_page(update, uid):
    reminders = get_user_reminders(uid)
    from datetime import timedelta
    if not reminders:
        await _edit(update, "⏰ *تذكيراتي*\n\nلا توجد تذكيرات نشطة.", back_keyboard("menu_settings"))
        return
    txt = "⏰ *تذكيراتي النشطة*\n\n"
    for r in reminders[:10]:
        local = r["fire_at"] + timedelta(hours=3)
        txt += f"• {r['task_title'][:30]} — *{local.strftime('%H:%M')} غداً/اليوم*\n"
    await _edit(update, txt, back_keyboard("menu_settings"))

# ════════════════════════════════════════════════════════════
#  SETTINGS
# ════════════════════════════════════════════════════════════
async def _settings_page(update, user):
    s      = user.get("settings",{})
    n      = "✅" if s.get("notifications",True)   else "❌"
    r      = "✅" if s.get("midnight_report",True)  else "❌"
    st     = "✅" if s.get("strict_mode",False)     else "❌"
    mt     = s.get("morning_time", "09:00")
    et     = s.get("evening_time", "21:00")
    txt    = (f"⚙️ *الإعدادات*\n\n"
              f"🔔 التنبيهات الصباحية: {n}  _(الساعة {mt})_\n"
              f"🌙 التقرير الليلي: {r}  _(الساعة {et})_\n"
              f"⚔️ الوضع الصارم (خسارة السلسلة): {st}\n")
    kb     = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔔 التنبيهات: {n}",           callback_data="toggle_notif")],
        [InlineKeyboardButton(f"☀️ وقت الصباح: {mt}",         callback_data="set_morning_time")],
        [InlineKeyboardButton(f"🌙 التقرير الليلي: {r}",       callback_data="toggle_report")],
        [InlineKeyboardButton(f"🌆 وقت المساء: {et}",          callback_data="set_evening_time")],
        [InlineKeyboardButton(f"⚔️ الوضع الصارم: {st}",       callback_data="toggle_strict")],
        [InlineKeyboardButton("⏰ تذكيراتي",                   callback_data="my_reminders")],
        [InlineKeyboardButton("📦 نسخة احتياطية JSON",         callback_data="backup_json")],
        [InlineKeyboardButton("📋 تقرير نصي",                  callback_data="backup_report")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية",           callback_data="back_main")],
    ])
    await _edit(update, txt, kb)

async def set_morning_time_start(update, context):
    q = update.callback_query; await q.answer()
    context.user_data["setting_time_type"] = "morning"
    await q.edit_message_text(
        "☀️ اكتب وقت التنبيه الصباحي بصيغة *HH:MM*\nمثال: 08:00",
        parse_mode="Markdown"
    )
    return SET_MORNING_TIME

async def set_evening_time_start(update, context):
    q = update.callback_query; await q.answer()
    context.user_data["setting_time_type"] = "evening"
    await q.edit_message_text(
        "🌆 اكتب وقت التقرير المسائي بصيغة *HH:MM*\nمثال: 21:00",
        parse_mode="Markdown"
    )
    return SET_EVENING_TIME

async def save_notif_time(update, context):
    uid  = update.effective_user.id
    text = update.message.text.strip()
    ttype = context.user_data.get("setting_time_type", "morning")
    try:
        h, m = map(int, text.split(":")); assert 0 <= h <= 23 and 0 <= m <= 59
    except Exception:
        await update.message.reply_text("❌ صيغة خاطئة، مثال: 09:00"); 
        return SET_MORNING_TIME if ttype == "morning" else SET_EVENING_TIME
    key = "morning_time" if ttype == "morning" else "evening_time"
    s = (get_user(uid) or {}).get("settings", {})
    s[key] = text
    update_user(uid, {"settings": s})
    emoji = "☀️" if ttype == "morning" else "🌆"
    await update.message.reply_text(
        f"{emoji} تم الضبط! سيصلك التنبيه الساعة *{text}* يومياً.",
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
#  SCHEDULED JOBS
# ════════════════════════════════════════════════════════════
async def job_check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """يعمل كل 5 دقائق — يرسل التذكيرات بأسلوب Solo Leveling."""
    due = get_due_reminders()
    for r in due:
        try:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ تم الإنجاز!", callback_data=f"rdone_{r['task_id']}"),
                 InlineKeyboardButton("⏭️ لاحقاً",     callback_data="reminder_skip")],
            ])
            await context.bot.send_message(
                r["user_id"],
                f"⚠️ *تنبيه من النظام*\n{'═'*20}\n\n"
                f"📋 *{r['task_title']}*\n\n"
                f"_النظام يراقبك يا صياد..._\n"
                f"_هل أنجزت مهمتك؟_",
                parse_mode="Markdown", reply_markup=kb
            )
            mark_reminder_fired(str(r["_id"]))
        except Exception as e:
            logger.warning(f"reminder {r['_id']}: {e}")

async def job_midnight(context: ContextTypes.DEFAULT_TYPE):
    """تقرير منتصف الليل — Solo Leveling style."""
    for user in get_all_users():
        uid = user["user_id"]
        if not user.get("settings",{}).get("midnight_report",True): continue
        try:
            pen   = apply_midnight_penalties(uid)
            user  = get_user(uid)
            stats = get_daily_stats(uid)
            xp    = user.get("xp",0)
            lv    = get_level_info(xp)
            rate  = stats["completion_rate"]
            today_xp    = stats["tasks_done"] * 20
            today_coins = stats["tasks_done"] * 10

            if rate >= 100:
                header = "🏆 *إنجاز مطلق — اليوم ملكٌ لك!*"
                footer = "_الصيادون الحقيقيون لا يتوقفون. غداً أقوى!_ ⚔️"
            elif rate >= 80:
                header = "✅ *أداء ممتاز — النظام راضٍ عنك*"
                footer = "_واصل المسار يا صياد. القمة قريبة!_ 💪"
            elif rate >= 50:
                header = "⚠️ *أداء متوسط — النظام يحذّرك*"
                footer = "_الضعف ليس خياراً. غداً لا عذر!_ 🔥"
            else:
                header = "💀 *فشل ذريع — النظام غاضب*"
                footer = "_هذا المستوى لا يُقبل. الصيادون لا يستسلمون!_ ⚠️"

            txt = (
                f"{header}\n{'═'*24}\n\n"
                f"📊 نسبة الإنجاز: *{rate}%*\n"
                f"✅ المهام: *{stats['tasks_done']}/{stats['tasks_total']}*\n"
                f"🔥 العادات: *{stats['habits_done']}/{stats['habits_total']}*\n"
                f"🏅 السلسلة: *{user.get('streak',0)}* يوم\n"
                f"⭐ XP اليوم: *+{today_xp}*\n"
                f"💰 العملات: *+{today_coins}*\n"
            )
            if pen.get("tasks_missed", 0):
                txt += (
                    f"\n💀 *عقوبة النظام:*\n"
                    f"   ⬇️ -{pen['xp_lost']} XP  |  -{pen['coins_lost']} عملة\n"
                    f"   ({pen['tasks_missed']} مهام تجاهلتَها)\n"
                )
            if pen.get("streak_lost"):
                txt += "\n💔 *انقطعت سلسلتك! النظام لا يرحم الضعفاء.*\n"
            txt += f"\n{lv['rank_emoji']} رتبتك: *{lv['rank']}*\n\n{footer}"
            await context.bot.send_message(uid, txt, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"midnight report {uid}: {e}")


async def job_morning(context: ContextTypes.DEFAULT_TYPE):
    """تنبيه الصباح — Solo Leveling: Daily Quest received!"""
    for user in get_all_users():
        if not user.get("settings",{}).get("notifications",True): continue
        try:
            uid   = user["user_id"]
            stats = get_daily_stats(uid)
            tasks = get_today_tasks(uid)
            if stats["tasks_total"] == 0: continue
            lv  = get_level_info(user.get("xp",0))
            pi  = {"low":"🟢","medium":"🟡","high":"🟠","urgent":"🔴"}
            task_list = "\n".join(
                f"  {pi.get(t['priority'],'⚪')} {t['title'][:35]}"
                for t in tasks[:5]
            )
            streak = user.get("streak",0)
            streak_warn = f"\n⚠️ _سلسلتك {streak} يوم — لا تكسرها!_" if streak > 0 else ""
            txt = (
                f"⚔️ *تنبيه من النظام*\n{'═'*22}\n\n"
                f"🌅 صياد {lv['rank_emoji']} *{user['name']}*\n"
                f"مهامك اليومية جاهزة!\n\n"
                f"📋 *المهام اليوم ({stats['tasks_total']}):*\n"
                f"{task_list}\n"
                f"{'  ...' if stats['tasks_total']>5 else ''}\n"
                f"{streak_warn}\n\n"
                f"_النظام يراقبك. أثبت قيمتك يا صياد!_ ⚡"
            )
            await context.bot.send_message(uid, txt, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 ابدأ المهام", callback_data="task_today")
                ]]))
        except Exception: pass


async def job_noon_warning(context: ContextTypes.DEFAULT_TYPE):
    """تحذير الظهيرة — للصيادين المتأخرين."""
    for user in get_all_users():
        if not user.get("settings",{}).get("notifications",True): continue
        try:
            uid   = user["user_id"]
            stats = get_daily_stats(uid)
            if stats["tasks_total"] == 0: continue
            pending = stats["tasks_pending"]
            if pending == 0: continue   # أنجز كل شيء، لا داعي للتحذير
            rate = stats["completion_rate"]
            txt = (
                f"🕛 *تحذير الظهيرة*\n{'═'*20}\n\n"
                f"⚠️ النهار نصفه مضى!\n\n"
                f"📋 لا يزال لديك *{pending}* مهمة معلّقة\n"
                f"📊 إنجازك حتى الآن: *{rate}%*\n\n"
                f"_الوقت يتسارع يا صياد.\nالنظام لن يرحم المتكاسلين!_ ⏳"
            )
            await context.bot.send_message(uid, txt, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚡ أنجز الآن!", callback_data="task_today")
                ]]))
        except Exception: pass


async def job_evening_warning(context: ContextTypes.DEFAULT_TYPE):
    """التحذير الأخير — قبل ساعتين من العقوبة."""
    for user in get_all_users():
        if not user.get("settings",{}).get("midnight_report",True): continue
        try:
            uid   = user["user_id"]
            stats = get_daily_stats(uid)
            if stats["tasks_total"] == 0: continue
            pending = stats["tasks_pending"]
            if pending == 0: continue
            lv = get_level_info(user.get("xp",0))
            # احسب العقوبة المتوقعة
            from modules.database import get_db as _gdb
            today = date.today().strftime("%Y-%m-%d")
            pending_tasks = list(_gdb().tasks.find(
                {"user_id": uid, "due_date": today, "status": "pending"}
            ))
            expected_xp_loss = sum(
                {"low":5,"medium":10,"high":20,"urgent":35}.get(t.get("priority","medium"),10)
                for t in pending_tasks
            )
            txt = (
                f"🚨 *تحذير أخير من النظام*\n{'═'*22}\n\n"
                f"⏰ تبقّى ساعتان قبل العقوبة!\n\n"
                f"📋 المهام المتبقية: *{pending}*\n"
                f"💀 XP ستخسره: *-{expected_xp_loss}*\n"
                f"🏅 رتبتك الحالية: {lv['rank_emoji']} *{lv['rank']}*\n\n"
                f"_آخر فرصة يا صياد!\nالنظام لا يمنح فرصاً ثانية!_ ⚠️"
            )
            await context.bot.send_message(uid, txt, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔥 أنجز قبل فوات الأوان!", callback_data="task_today")
                ]]))
        except Exception: pass

async def job_weekly_bonus(context: ContextTypes.DEFAULT_TYPE):
    """Every Sunday: bonus XP for users who completed all tasks this week."""
    from modules.xp_system import add_xp
    from modules.analytics import get_weekly_stats
    for user in get_all_users():
        try:
            w = get_weekly_stats(user["user_id"])
            if w["weekly_rate"] >= 80:
                result = add_xp(user["user_id"], 100, 50)
                await context.bot.send_message(
                    user["user_id"],
                    f"🎉 *مكافأة الأسبوع!*\n\n"
                    f"أنجزت *{w['weekly_rate']}%* من مهام الأسبوع!\n\n"
                    f"⭐ +100 XP  |  💰 +50 عملة",
                    parse_mode="Markdown"
                )
        except Exception: pass


# ════════════════════════════════════════════════════════════
#  CANCEL
# ════════════════════════════════════════════════════════════
async def cancel_conv(update, context):
    uid = update.effective_user.id; _tmp.pop(uid, None)
    user = get_user(uid) or {}
    if update.message:
        await update.message.reply_text("❌ تم الإلغاء.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════
def main():
    import asyncio

    # Python 3.12+ لا ينشئ event loop تلقائياً — ننشئه يدوياً
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير محدد! أضفه في Environment Variables")
        return
    if not MONGO_URI:
        logger.error("❌ MONGO_URI غير محدد! أضفه في Environment Variables")
        return

    logger.info("🔄 جاري تهيئة البوت...")

    # حذف أي webhook قديم قد يمنع الـ polling
    import requests as _req
    try:
        r = _req.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
        logger.info(f"🔗 deleteWebhook: {r.json().get('description','ok')}")
    except Exception as e:
        logger.warning(f"⚠️ تعذّر حذف الـ webhook: {e}")

    app = Application.builder().token(BOT_TOKEN).build()

    fallbacks = [
        CommandHandler("menu",  cancel_conv),
        CommandHandler("start", cancel_conv),
        CallbackQueryHandler(cancel_conv, pattern="^cancel$"),
    ]

    def conv(entry_patterns, states, extra_fallbacks=None):
        return ConversationHandler(
            entry_points=[CallbackQueryHandler(ep, pattern=p) for p, ep in entry_patterns],
            states=states,
            fallbacks=fallbacks + (extra_fallbacks or []),
            per_user=True, per_chat=True,
        )

    # تجهيز المسارات
    task_conv = conv(
        [("^task_add$", add_task_start)],
        {TASK_TITLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, task_got_title)],
         TASK_PRIORITY: [CallbackQueryHandler(task_got_priority, pattern="^priority_")],
         TASK_CATEGORY: [CallbackQueryHandler(task_got_category, pattern="^cat_")],
         TASK_DUE_DATE: [CallbackQueryHandler(task_got_due,      pattern="^due_")],
         TASK_REPEAT:   [CallbackQueryHandler(task_got_repeat,   pattern="^repeat_")]},
    )
    edit_task_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(_edit_task_menu, pattern="^edit_task_")],
        states={
            EDIT_TASK_FIELD: [CallbackQueryHandler(edit_task_field_chosen, pattern="^etf_")],
            EDIT_TASK_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_task_value_received)],
        },
        fallbacks=fallbacks, per_user=True, per_chat=True,
    )
    habit_conv = conv(
        [("^habit_add$", add_habit_start)],
        {HABIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, habit_got_name)],
         HABIT_ICON: [CallbackQueryHandler(habit_got_icon, pattern="^icon_"),
                      MessageHandler(filters.TEXT & ~filters.COMMAND, habit_got_icon)]},
    )
    goal_conv = conv(
        [("^goal_add$", add_goal_start)],
        {GOAL_TITLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_got_title)],
         GOAL_TARGET:   [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_got_target)],
         GOAL_UNIT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_got_unit)],
         GOAL_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_got_deadline)]},
    )
    goal_update_conv = conv(
        [("^update_goal_", goal_update_start)],
        {GOAL_UPDATE_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_update_value)]}
    )
    challenge_conv = conv(
        [("^challenge_add$", add_challenge_start)],
        {CHALLENGE_TITLE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, challenge_got_title)],
         CHALLENGE_TYPE:   [CallbackQueryHandler(challenge_got_type, pattern="^chtype_")],
         CHALLENGE_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, challenge_got_target)]},
    )
    friend_conv = conv(
        [("^friend_add$", add_friend_start)],
        {FRIEND_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, friend_id_received)]},
    )
    ai_conv = conv(
        [("^ai_free$", ai_free_start)],
        {AI_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_free_chat)]}
    )

    # تسجيل الأوامر
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("menu",    cmd_menu))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("backup",  cmd_backup))
    
    reminder_conv = conv(
        [("^remind_task_", remind_task_start)],
        {REMINDER_TIME: [
            CallbackQueryHandler(remind_task_quick,  pattern="^rtime_(30m|1h|2h|3h)$"),
            CallbackQueryHandler(remind_task_custom, pattern="^rtime_custom$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, remind_task_time_text),
        ]},
    )
    morning_time_conv = conv(
        [("^set_morning_time$", set_morning_time_start)],
        {SET_MORNING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_notif_time)]},
    )
    evening_time_conv = conv(
        [("^set_evening_time$", set_evening_time_start)],
        {SET_EVENING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_notif_time)]},
    )

    for h in [task_conv, edit_task_conv, habit_conv, goal_conv, goal_update_conv,
              challenge_conv, friend_conv, ai_conv,
              reminder_conv, morning_time_conv, evening_time_conv]:
        app.add_handler(h)

    app.add_handler(CallbackQueryHandler(cb_router))

    # التنبيهات التلقائية
    jq = app.job_queue
    if jq:
        jq.run_daily(job_morning,             time=time(9,  0, 0))   # الصباح — Daily Quest
        jq.run_daily(job_noon_warning,        time=time(12, 0, 0))   # الظهيرة — تحذير
        jq.run_daily(job_evening_warning,     time=time(19, 0, 0))   # المساء — تحذير أخير
        jq.run_daily(job_midnight,            time=time(21, 0, 0))   # الليل — العقوبة
        jq.run_daily(job_weekly_bonus,        time=time(20, 0, 0), days=(6,))
        jq.run_repeating(job_check_reminders, interval=300, first=10)  # كل 5 دقائق

    logger.info("🚀 البوت شغال الآن بنجاح!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
