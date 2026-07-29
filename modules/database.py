"""
LifeMaster AI - Database Module (Complete)
"""
import os, logging
from datetime import datetime, date, timedelta
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId

logger = logging.getLogger(__name__)
MONGO_URI = os.environ.get("MONGO_URI", "")

_client = None
_db     = None


def get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URI)
        _db     = _client["lifemaster"]
        _ensure_indexes()
        logger.info("✅ MongoDB Atlas — LifeMaster")
    return _db


def _ensure_indexes():
    db = _db
    db.users.create_index("user_id", unique=True)
    db.tasks.create_index([("user_id", ASCENDING), ("status", ASCENDING)])
    db.tasks.create_index([("user_id", ASCENDING), ("due_date", ASCENDING)])
    db.habits.create_index([("user_id", ASCENDING)])
    db.habit_logs.create_index([("user_id", ASCENDING), ("habit_id", ASCENDING), ("date", ASCENDING)])
    db.goals.create_index([("user_id", ASCENDING)])
    db.challenges.create_index([("status", ASCENDING), ("end_date", ASCENDING)])
    db.reminders.create_index([("user_id", ASCENDING), ("fire_at", ASCENDING), ("fired", ASCENDING)])
    db.task_completions.create_index([("user_id", ASCENDING), ("completed_at", ASCENDING)])


# ════════════════════════ USERS ══════════════════════════════
def get_user(user_id: int) -> dict | None:
    return get_db().users.find_one({"user_id": user_id})


def create_user(user_id: int, name: str, username: str = "") -> dict:
    user = {
        "user_id": user_id, "name": name, "username": username,
        "xp": 0, "level": 1, "rank": "مبتدئ", "rank_emoji": "🌱",
        "coins": 0, "streak": 0, "best_streak": 0,
        "last_active_date": None,
        "tasks_completed": 0, "habits_completed": 0,
        "achievements": [], "inventory": [], "friends": [],
        "equipped_title": "",
        "settings": {
            "notifications": True,
            "midnight_report": True,
            "reminder_times": ["09:00"],   # morning reminder
            "strict_mode": False,          # lose streak if >3 tasks missed
        },
        "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()
    }
    get_db().users.insert_one(user)
    return user


def get_or_create_user(user_id: int, name: str, username: str = "") -> dict:
    u = get_user(user_id)
    return u if u else create_user(user_id, name, username)


def update_user(user_id: int, updates: dict):
    updates["updated_at"] = datetime.utcnow()
    get_db().users.update_one({"user_id": user_id}, {"$set": updates})


def get_all_users() -> list:
    return list(get_db().users.find())


# ════════════════════════ TASKS ══════════════════════════════
def create_task(user_id: int, data: dict) -> str:
    task = {
        "user_id":      user_id,
        "title":        data.get("title", ""),
        "description":  data.get("description", ""),
        "notes":        data.get("notes", ""),
        "priority":     data.get("priority", "medium"),
        "category":     data.get("category", "⭐ عام"),
        "status":       "pending",
        "due_date":     data.get("due_date"),
        "start_time":   data.get("start_time"),
        "end_time":     data.get("end_time"),
        "repeat_type":  data.get("repeat_type", "once"),
        "reminder_times": data.get("reminder_times", []),
        "created_at":   datetime.utcnow(),
        "completed_at": None,
        "completed_hour": None,
    }
    r = get_db().tasks.insert_one(task)
    return str(r.inserted_id)


def get_task_by_id(task_id: str) -> dict | None:
    return get_db().tasks.find_one({"_id": ObjectId(task_id)})


def get_user_tasks(user_id: int, status: str = None, date_str: str = None) -> list:
    q = {"user_id": user_id}
    if status:  q["status"] = status
    if date_str: q["due_date"] = date_str
    return list(get_db().tasks.find(q).sort("created_at", DESCENDING))


def get_today_tasks(user_id: int) -> list:
    today = date.today().strftime("%Y-%m-%d")
    return list(get_db().tasks.find({
        "user_id": user_id,
        "due_date": today,
        "status": {"$in": ["pending", "done"]}
    }).sort("priority", ASCENDING))


def complete_task(task_id: str) -> dict | None:
    task = get_db().tasks.find_one({"_id": ObjectId(task_id)})
    if task:
        now = datetime.utcnow()
        get_db().tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": "done", "completed_at": now,
                      "completed_hour": now.hour}}
        )
        # Log for hour-analysis
        get_db().task_completions.insert_one({
            "user_id": task["user_id"],
            "task_id": task_id,
            "priority": task.get("priority", "medium"),
            "completed_at": now,
            "hour": now.hour,
            "weekday": now.weekday()
        })
    return task


def update_task(task_id: str, updates: dict):
    get_db().tasks.update_one({"_id": ObjectId(task_id)}, {"$set": updates})


def delete_task(task_id: str):
    get_db().tasks.delete_one({"_id": ObjectId(task_id)})


def skip_overdue_tasks(user_id: int, before_date: str) -> int:
    """Mark pending tasks before a date as skipped. Returns count."""
    r = get_db().tasks.update_many(
        {"user_id": user_id, "due_date": {"$lt": before_date},
         "status": "pending"},
        {"$set": {"status": "skipped"}}
    )
    return r.modified_count


# ════════════════════════ HABITS ═════════════════════════════
def create_habit(user_id: int, data: dict) -> str:
    habit = {
        "user_id":          user_id,
        "name":             data.get("name", ""),
        "icon":             data.get("icon", "⭐"),
        "description":      data.get("description", ""),
        "reminder_time":    data.get("reminder_time"),
        "streak":           0,
        "best_streak":      0,
        "total_completions": 0,
        "status":           "active",   # active / paused
        "created_at":       datetime.utcnow()
    }
    r = get_db().habits.insert_one(habit)
    return str(r.inserted_id)


def get_user_habits(user_id: int, status: str = "active") -> list:
    q = {"user_id": user_id}
    if status != "all":
        q["status"] = status
    return list(get_db().habits.find(q).sort("created_at", ASCENDING))


def pause_habit(habit_id: str, pause: bool = True):
    get_db().habits.update_one(
        {"_id": ObjectId(habit_id)},
        {"$set": {"status": "paused" if pause else "active"}}
    )


def log_habit(user_id: int, habit_id: str, action: str = "done") -> bool:
    today = date.today().strftime("%Y-%m-%d")
    if get_db().habit_logs.find_one({"user_id": user_id, "habit_id": habit_id, "date": today}):
        return False
    get_db().habit_logs.insert_one({
        "user_id": user_id, "habit_id": habit_id,
        "date": today, "action": action,
        "logged_at": datetime.utcnow()
    })
    if action == "done":
        h = get_db().habits.find_one({"_id": ObjectId(habit_id)})
        if h:
            ns = h.get("streak", 0) + 1
            best = max(h.get("best_streak", 0), ns)
            get_db().habits.update_one(
                {"_id": ObjectId(habit_id)},
                {"$set": {"streak": ns, "best_streak": best},
                 "$inc": {"total_completions": 1}}
            )
    return True


def get_habit_log_today(user_id: int) -> dict:
    today = date.today().strftime("%Y-%m-%d")
    logs  = get_db().habit_logs.find({"user_id": user_id, "date": today})
    return {l["habit_id"]: l["action"] for l in logs}


def delete_habit(habit_id: str):
    get_db().habits.delete_one({"_id": ObjectId(habit_id)})


def get_habit_streak_history(user_id: int, habit_id: str, days: int = 30) -> list:
    """Returns list of {'date', 'action'} for last N days."""
    db    = get_db()
    start = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    logs  = list(db.habit_logs.find({
        "user_id": user_id, "habit_id": habit_id,
        "date": {"$gte": start}
    }).sort("date", ASCENDING))
    return [{"date": l["date"], "action": l["action"]} for l in logs]


# ════════════════════════ GOALS ══════════════════════════════
def create_goal(user_id: int, data: dict) -> str:
    from modules.goals import create_goal as _cg
    return _cg(user_id, data)


def get_user_goals(user_id: int, status: str = "active") -> list:
    q = {"user_id": user_id}
    if status != "all": q["status"] = status
    return list(get_db().goals.find(q).sort("created_at", DESCENDING))


# ════════════════════════ STATS ══════════════════════════════
def get_daily_stats(user_id: int) -> dict:
    today  = date.today().strftime("%Y-%m-%d")
    tasks  = list(get_db().tasks.find({"user_id": user_id, "due_date": today}))
    total  = len(tasks)
    done   = sum(1 for t in tasks if t["status"] == "done")
    habits = get_user_habits(user_id)
    logs   = get_habit_log_today(user_id)
    hdone  = sum(1 for h in habits if logs.get(str(h["_id"])) == "done")
    return {
        "tasks_total": total, "tasks_done": done,
        "tasks_pending": total - done,
        "habits_total": len(habits), "habits_done": hdone,
        "completion_rate": round(done / total * 100 if total else 0, 1)
    }
