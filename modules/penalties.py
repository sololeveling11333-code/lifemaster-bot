"""
LifeMaster AI - Penalty System
خصم XP عند تجاهل المهام عند منتصف الليل
"""
import logging
from datetime import date
from modules.database import get_db, get_user, update_user
from modules.xp_system import get_level_info

logger = logging.getLogger(__name__)

XP_PENALTY_PER_TASK = {
    "low":    5,
    "medium": 10,
    "high":   20,
    "urgent": 35,
}
COINS_PENALTY_PER_TASK = {
    "low":    2,
    "medium": 5,
    "high":   10,
    "urgent": 20,
}


def apply_midnight_penalties(user_id: int) -> dict:
    """
    Check today's pending tasks and apply XP/coin penalties.
    Returns penalty summary.
    """
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")
    user = get_user(user_id)
    if not user:
        return {}

    # Find incomplete tasks with a due date of today
    pending = list(db.tasks.find({
        "user_id": user_id,
        "due_date": today,
        "status": "pending"
    }))

    if not pending:
        return {"xp_lost": 0, "coins_lost": 0, "tasks_missed": 0}

    total_xp_lost = 0
    total_coins_lost = 0

    for task in pending:
        priority = task.get("priority", "medium")
        xp_penalty = XP_PENALTY_PER_TASK.get(priority, 10)
        coins_penalty = COINS_PENALTY_PER_TASK.get(priority, 5)

        # Don't go below 0
        current_xp = user.get("xp", 0) - total_xp_lost
        actual_xp = min(xp_penalty, max(0, current_xp))
        actual_coins = min(coins_penalty, max(0, user.get("coins", 0) - total_coins_lost))

        total_xp_lost += actual_xp
        total_coins_lost += actual_coins

        # Mark as skipped
        from bson import ObjectId
        db.tasks.update_one({"_id": task["_id"]}, {"$set": {"status": "skipped"}})

    # Apply penalty
    new_xp = max(0, user.get("xp", 0) - total_xp_lost)
    new_coins = max(0, user.get("coins", 0) - total_coins_lost)
    level_info = get_level_info(new_xp)

    update_user(user_id, {
        "xp": new_xp,
        "coins": new_coins,
        "level": level_info["level"],
        "rank": level_info["rank"],
        "rank_emoji": level_info["rank_emoji"],
    })

    # Break streak if too many missed
    missed_rate = len(pending)
    if missed_rate >= 3:
        # Reset streak
        update_user(user_id, {"streak": 0})
        streak_lost = True
    else:
        streak_lost = False

    return {
        "xp_lost": total_xp_lost,
        "coins_lost": total_coins_lost,
        "tasks_missed": len(pending),
        "streak_lost": streak_lost,
    }
