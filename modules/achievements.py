"""
LifeMaster AI - Achievements System
"""

import logging
from modules.database import get_user, update_user

logger = logging.getLogger(__name__)

ACHIEVEMENTS = {
    "first_task": {
        "id": "first_task",
        "name": "🎯 أول خطوة",
        "desc": "أنجز أول مهمة",
        "icon": "🎯",
        "xp_bonus": 50,
        "coins_bonus": 25
    },
    "tasks_10": {
        "id": "tasks_10",
        "name": "⚡ منجز نشيط",
        "desc": "أنجز 10 مهام",
        "icon": "⚡",
        "xp_bonus": 100,
        "coins_bonus": 50
    },
    "tasks_100": {
        "id": "tasks_100",
        "name": "🏆 بطل الإنجاز",
        "desc": "أنجز 100 مهمة",
        "icon": "🏆",
        "xp_bonus": 500,
        "coins_bonus": 200
    },
    "streak_7": {
        "id": "streak_7",
        "name": "🔥 أسبوع متواصل",
        "desc": "7 أيام متتالية",
        "icon": "🔥",
        "xp_bonus": 150,
        "coins_bonus": 75
    },
    "streak_30": {
        "id": "streak_30",
        "name": "💎 شهر من الالتزام",
        "desc": "30 يوم متواصل",
        "icon": "💎",
        "xp_bonus": 500,
        "coins_bonus": 250
    },
    "streak_100": {
        "id": "streak_100",
        "name": "🌟 مئة يوم",
        "desc": "100 يوم متواصل",
        "icon": "🌟",
        "xp_bonus": 1000,
        "coins_bonus": 500
    },
    "first_habit": {
        "id": "first_habit",
        "name": "🌱 عادة جديدة",
        "desc": "أنشئ أول عادة",
        "icon": "🌱",
        "xp_bonus": 30,
        "coins_bonus": 15
    },
    "habits_30": {
        "id": "habits_30",
        "name": "💪 إرادة فولاذية",
        "desc": "أنجز 30 عادة",
        "icon": "💪",
        "xp_bonus": 200,
        "coins_bonus": 100
    },
    "level_up": {
        "id": "level_up",
        "name": "⬆️ ترقية",
        "desc": "ارتقِ مستوى",
        "icon": "⬆️",
        "xp_bonus": 0,
        "coins_bonus": 30
    },
    "emperor": {
        "id": "emperor",
        "name": "🔱 الإمبراطور",
        "desc": "بلغ مرتبة الإمبراطور",
        "icon": "🔱",
        "xp_bonus": 2000,
        "coins_bonus": 1000
    }
}


def check_and_award(user_id: int) -> list:
    """Check all achievements and award new ones. Returns list of newly unlocked."""
    from modules.database import get_db
    from modules.xp_system import add_xp

    user = get_user(user_id)
    if not user:
        return []

    earned = user.get("achievements", [])
    new_achievements = []

    def check(achievement_id: str, condition: bool):
        if condition and achievement_id not in earned:
            ach = ACHIEVEMENTS[achievement_id]
            earned.append(achievement_id)
            if ach["xp_bonus"] > 0:
                add_xp(user_id, ach["xp_bonus"], ach["coins_bonus"])
            new_achievements.append(ach)

    tasks_done = user.get("tasks_completed", 0)
    habits_done = user.get("habits_completed", 0)
    streak = user.get("streak", 0)
    level = user.get("level", 1)

    check("first_task", tasks_done >= 1)
    check("tasks_10", tasks_done >= 10)
    check("tasks_100", tasks_done >= 100)
    check("streak_7", streak >= 7)
    check("streak_30", streak >= 30)
    check("streak_100", streak >= 100)
    check("habits_30", habits_done >= 30)
    check("level_up", level >= 2)
    check("emperor", level >= 8)

    if new_achievements:
        update_user(user_id, {"achievements": earned})

    return new_achievements


def check_first_habit(user_id: int) -> list:
    from modules.xp_system import add_xp
    user = get_user(user_id)
    if not user:
        return []
    earned = user.get("achievements", [])
    if "first_habit" not in earned:
        earned.append("first_habit")
        ach = ACHIEVEMENTS["first_habit"]
        add_xp(user_id, ach["xp_bonus"], ach["coins_bonus"])
        update_user(user_id, {"achievements": earned})
        return [ach]
    return []


def get_user_achievements(user_id: int) -> list:
    user = get_user(user_id)
    if not user:
        return []
    earned_ids = user.get("achievements", [])
    return [ACHIEVEMENTS[aid] for aid in earned_ids if aid in ACHIEVEMENTS]


def get_all_achievements_status(user_id: int) -> list:
    user = get_user(user_id)
    earned_ids = user.get("achievements", []) if user else []
    result = []
    for ach_id, ach in ACHIEVEMENTS.items():
        result.append({**ach, "unlocked": ach_id in earned_ids})
    return result
