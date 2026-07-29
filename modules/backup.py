"""
LifeMaster AI - Backup & Export
نسخ احتياطي وتصدير البيانات
"""
import json
import logging
from datetime import datetime, date
from modules.database import get_db, get_user, get_user_tasks, get_user_habits, get_user_goals

logger = logging.getLogger(__name__)


def export_user_data(user_id: int) -> dict:
    """Export all user data as a dict (JSON-serialisable)."""
    db    = get_db()
    user  = get_user(user_id)
    if not user:
        return {}

    def _clean(obj):
        """Remove MongoDB ObjectId and convert datetime."""
        if isinstance(obj, list):
            return [_clean(i) for i in obj]
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items() if k != "_id"}
        if hasattr(obj, "isoformat"):   # datetime / date
            return obj.isoformat()
        return obj

    tasks  = list(db.tasks.find({"user_id": user_id}))
    habits = list(db.habits.find({"user_id": user_id}))
    goals  = list(db.goals.find({"user_id": user_id})) if hasattr(db, "goals") else []

    data = {
        "exported_at": datetime.utcnow().isoformat(),
        "user": _clean(user),
        "tasks":  _clean(tasks),
        "habits": _clean(habits),
        "goals":  _clean(goals),
    }
    return data


def export_as_json_bytes(user_id: int) -> bytes:
    data = export_user_data(user_id)
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def build_text_report(user_id: int) -> str:
    """Human-readable text summary."""
    db    = get_db()
    user  = get_user(user_id)
    if not user:
        return "لا توجد بيانات."

    tasks_done  = user.get("tasks_completed", 0)
    habits_done = user.get("habits_completed", 0)
    xp          = user.get("xp", 0)
    coins       = user.get("coins", 0)
    streak      = user.get("streak", 0)
    best_streak = user.get("best_streak", 0)
    rank        = user.get("rank", "مبتدئ")
    level       = user.get("level", 1)
    achievements= len(user.get("achievements", []))
    joined      = user.get("created_at")
    joined_str  = joined.strftime("%Y-%m-%d") if joined else "غير معروف"

    habits = list(db.habits.find({"user_id": user_id, "status": "active"}))
    habit_lines = "\n".join(
        f"  - {h.get('icon','⭐')} {h['name']}: 🔥{h.get('streak',0)} يوم"
        for h in habits
    ) or "  لا توجد عادات."

    report = (
        f"📊 تقرير LifeMaster AI\n"
        f"{'='*30}\n"
        f"👤 الاسم: {user.get('name','')}\n"
        f"📅 تاريخ الانضمام: {joined_str}\n\n"
        f"🎖️ الرتبة: {rank} (المستوى {level})\n"
        f"⭐ XP: {xp:,}\n"
        f"💰 العملات: {coins:,}\n"
        f"🔥 السلسلة: {streak} يوم\n"
        f"🏅 أعلى سلسلة: {best_streak} يوم\n\n"
        f"✅ مهام منجزة: {tasks_done}\n"
        f"🔥 عادات منجزة: {habits_done}\n"
        f"🏆 إنجازات: {achievements}\n\n"
        f"🔥 العادات الحالية:\n{habit_lines}\n"
    )
    return report
