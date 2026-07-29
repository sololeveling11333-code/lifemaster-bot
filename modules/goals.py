"""
LifeMaster AI - Goals System (الأهداف)
"""
import logging
from datetime import datetime, date
from bson import ObjectId
from modules.database import get_db

logger = logging.getLogger(__name__)


def create_goal(user_id: int, data: dict) -> str:
    db = get_db()
    goal = {
        "user_id":     user_id,
        "title":       data.get("title", ""),
        "description": data.get("description", ""),
        "category":    data.get("category", "عام"),
        "target":      data.get("target", 100),   # target value (e.g. 100 pages, 10 kg, ...)
        "unit":        data.get("unit", "%"),      # unit label
        "progress":    0,
        "status":      "active",                   # active / done / cancelled
        "deadline":    data.get("deadline"),       # YYYY-MM-DD
        "milestones":  [],                         # [{value, label, done}]
        "created_at":  datetime.utcnow(),
    }
    r = db.goals.insert_one(goal)
    db.goals.create_index([("user_id", 1)])
    return str(r.inserted_id)


def get_user_goals(user_id: int, status: str = "active") -> list:
    db = get_db()
    q  = {"user_id": user_id}
    if status:
        q["status"] = status
    return list(db.goals.find(q).sort("created_at", -1))


def update_goal_progress(goal_id: str, new_progress: int) -> dict | None:
    db   = get_db()
    goal = db.goals.find_one({"_id": ObjectId(goal_id)})
    if not goal:
        return None
    new_progress = min(new_progress, goal.get("target", 100))
    status = "done" if new_progress >= goal.get("target", 100) else "active"
    db.goals.update_one(
        {"_id": ObjectId(goal_id)},
        {"$set": {"progress": new_progress, "status": status}}
    )
    goal["progress"] = new_progress
    goal["status"]   = status
    return goal


def delete_goal(goal_id: str):
    get_db().goals.delete_one({"_id": ObjectId(goal_id)})


def goal_progress_bar(progress: int, target: int, width: int = 10) -> str:
    pct    = min(100, int(progress / target * 100)) if target else 0
    filled = int(width * pct / 100)
    return f"{'█' * filled}{'░' * (width - filled)} {pct}%"
