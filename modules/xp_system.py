"""
LifeMaster AI - XP & Leveling System
"""

import logging
from modules.database import get_db, update_user, get_user

logger = logging.getLogger(__name__)

# ─── XP Values ──────────────────────────────────────────────
XP_TASK = {
    "low": 10,
    "medium": 20,
    "high": 35,
    "urgent": 50
}

COINS_TASK = {
    "low": 5,
    "medium": 10,
    "high": 20,
    "urgent": 30
}

XP_HABIT = 15
COINS_HABIT = 8
XP_ALL_TASKS_BONUS = 25
XP_WEEKLY_BONUS = 100

# ─── Levels ──────────────────────────────────────────────────
LEVELS = [
    (0,     1, "مبتدئ",      "🌱"),
    (500,   2, "متدرب",      "⚔️"),
    (1500,  3, "محارب",      "🗡️"),
    (4000,  4, "فارس",       "🛡️"),
    (8000,  5, "قائد",       "👑"),
    (15000, 6, "سيد",        "💎"),
    (25000, 7, "أسطورة",     "🌟"),
    (40000, 8, "إمبراطور",   "🔱"),
]


def get_level_info(xp: int) -> dict:
    current = LEVELS[0]
    next_level = None

    for i, (req, lvl, name, emoji) in enumerate(LEVELS):
        if xp >= req:
            current = (req, lvl, name, emoji)
            if i + 1 < len(LEVELS):
                next_level = LEVELS[i + 1]

    req, lvl, name, emoji = current
    xp_for_next = next_level[0] if next_level else None
    progress = 0

    if next_level:
        span = next_level[0] - req
        earned = xp - req
        progress = min(100, int((earned / span) * 100))

    return {
        "level": lvl,
        "rank": name,
        "rank_emoji": emoji,
        "current_xp": xp,
        "xp_for_next": xp_for_next,
        "progress": progress,
        "next_rank": next_level[2] if next_level else None,
    }


def add_xp(user_id: int, xp_amount: int, coins_amount: int = 0) -> dict:
    """Add XP and coins to user, handle level up. Returns result dict."""
    user = get_user(user_id)
    if not user:
        return {}

    old_xp = user.get("xp", 0)
    old_info = get_level_info(old_xp)

    new_xp = old_xp + xp_amount
    new_coins = user.get("coins", 0) + coins_amount
    new_info = get_level_info(new_xp)

    leveled_up = new_info["level"] > old_info["level"]

    update_user(user_id, {
        "xp": new_xp,
        "coins": new_coins,
        "level": new_info["level"],
        "rank": new_info["rank"],
        "rank_emoji": new_info["rank_emoji"]
    })

    return {
        "xp_gained": xp_amount,
        "coins_gained": coins_amount,
        "total_xp": new_xp,
        "total_coins": new_coins,
        "leveled_up": leveled_up,
        "old_rank": old_info["rank"],
        "new_rank": new_info["rank"],
        "new_rank_emoji": new_info["rank_emoji"],
        "level": new_info["level"],
        "progress": new_info["progress"],
        "xp_for_next": new_info["xp_for_next"]
    }


def award_task_completion(user_id: int, priority: str) -> dict:
    xp = XP_TASK.get(priority, 20)
    coins = COINS_TASK.get(priority, 10)
    result = add_xp(user_id, xp, coins)
    # Increment tasks_completed
    db = get_db()
    db.users.update_one({"user_id": user_id}, {"$inc": {"tasks_completed": 1}})
    return result


def award_habit_completion(user_id: int, streak: int) -> dict:
    xp = XP_HABIT
    coins = COINS_HABIT

    # Streak bonuses
    if streak >= 30:
        xp = int(xp * 2.0)
        coins = int(coins * 2)
    elif streak >= 7:
        xp = int(xp * 1.5)
        coins = int(coins * 1.5)

    result = add_xp(user_id, xp, coins)
    db = get_db()
    db.users.update_one({"user_id": user_id}, {"$inc": {"habits_completed": 1}})
    return result


def update_streak(user_id: int) -> int:
    """Update daily streak. Returns new streak value."""
    from datetime import date, timedelta
    user = get_user(user_id)
    if not user:
        return 0

    today = date.today().strftime("%Y-%m-%d")
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    last_active = user.get("last_active_date")

    if last_active == today:
        return user.get("streak", 0)
    elif last_active == yesterday:
        new_streak = user.get("streak", 0) + 1
    else:
        new_streak = 1

    best_streak = max(user.get("best_streak", 0), new_streak)
    update_user(user_id, {
        "streak": new_streak,
        "best_streak": best_streak,
        "last_active_date": today
    })
    return new_streak


def get_xp_bar(progress: int, width: int = 10) -> str:
    """Returns visual XP bar like ████░░░░░░ 40%"""
    filled = int(width * progress / 100)
    empty = width - filled
    return f"{'█' * filled}{'░' * empty} {progress}%"
