"""
LifeMaster AI - Analytics (Complete)
"""
import logging
from datetime import date, timedelta
from modules.database import get_db, get_user

logger = logging.getLogger(__name__)

DAYS_AR = ["الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت","الأحد"]


# ── Weekly ────────────────────────────────────────────────────
def get_weekly_stats(user_id: int) -> dict:
    db    = get_db()
    today = date.today()
    days  = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    daily = []
    for ds in days:
        tasks  = list(db.tasks.find({"user_id": user_id, "due_date": ds}))
        total  = len(tasks)
        done   = sum(1 for t in tasks if t["status"] == "done")
        habits = list(db.habits.find({"user_id": user_id, "status": "active"}))
        hdone  = sum(
            1 for h in habits
            if db.habit_logs.find_one({"user_id": user_id, "habit_id": str(h["_id"]),
                                       "date": ds, "action": "done"})
        )
        rate = round(done / total * 100 if total else 0)
        daily.append({"date": ds,
                      "day_name": DAYS_AR[date.fromisoformat(ds).weekday()],
                      "tasks_total": total, "tasks_done": done,
                      "habits_done": hdone, "rate": rate})

    total_done  = sum(d["tasks_done"]  for d in daily)
    total_tasks = sum(d["tasks_total"] for d in daily)
    with_data   = [d for d in daily if d["tasks_total"] > 0]
    best  = max(with_data,  key=lambda d: d["rate"], default=None)
    worst = min(with_data,  key=lambda d: d["rate"], default=None)
    return {"daily": daily, "total_done": total_done, "total_tasks": total_tasks,
            "weekly_rate": round(total_done / total_tasks * 100 if total_tasks else 0),
            "best_day": best, "worst_day": worst}


# ── Monthly ───────────────────────────────────────────────────
def get_monthly_stats(user_id: int) -> dict:
    db    = get_db()
    today = date.today()
    days  = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(29, -1, -1)]
    total_done = total_tasks = perfect = 0
    for ds in days:
        tasks = list(db.tasks.find({"user_id": user_id, "due_date": ds}))
        t = len(tasks); d = sum(1 for x in tasks if x["status"] == "done")
        total_tasks += t; total_done += d
        if t > 0 and d == t:
            perfect += 1
    return {"total_done": total_done, "total_tasks": total_tasks,
            "monthly_rate": round(total_done / total_tasks * 100 if total_tasks else 0),
            "perfect_days": perfect}


# ── Habit analytics ───────────────────────────────────────────
def get_habit_analytics(user_id: int) -> dict:
    db    = get_db()
    today = date.today()
    last30 = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
    habits = list(db.habits.find({"user_id": user_id, "status": "active"}))
    result = []
    for h in habits:
        hid  = str(h["_id"])
        done = db.habit_logs.count_documents({
            "user_id": user_id, "habit_id": hid,
            "date": {"$in": last30}, "action": "done"
        })
        result.append({"name": h["name"], "icon": h.get("icon","⭐"),
                       "streak": h.get("streak",0), "best_streak": h.get("best_streak",0),
                       "rate_30d": round(done/30*100),
                       "total": h.get("total_completions",0)})
    result.sort(key=lambda x: x["rate_30d"])
    return {"habits": result,
            "most_neglected": result[0]  if result else None,
            "most_consistent": result[-1] if result else None}


# ── Most productive hour ──────────────────────────────────────
def get_most_productive_hour(user_id: int) -> dict:
    db   = get_db()
    pipe = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$hour", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 3}
    ]
    rows = list(db.task_completions.aggregate(pipe))
    if not rows:
        return {"best_hour": None, "top_hours": []}
    def fmt(h):
        return f"{h:02d}:00–{h:02d}:59"
    return {"best_hour": fmt(rows[0]["_id"]),
            "top_hours": [{"hour": fmt(r["_id"]), "count": r["count"]} for r in rows]}


# ── Most productive weekday ───────────────────────────────────
def get_most_productive_day(user_id: int) -> dict:
    db   = get_db()
    pipe = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$weekday", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 3}
    ]
    rows = list(db.task_completions.aggregate(pipe))
    if not rows:
        return {"best_day": None, "top_days": []}
    return {"best_day": DAYS_AR[rows[0]["_id"]],
            "top_days": [{"day": DAYS_AR[r["_id"]], "count": r["count"]} for r in rows]}


# ── Habit streak graph (text) ─────────────────────────────────
def build_habit_streak_graph(user_id: int, habit_id: str, days: int = 21) -> str:
    from modules.database import get_habit_streak_history
    logs    = get_habit_streak_history(user_id, habit_id, days)
    log_map = {l["date"]: l["action"] for l in logs}
    today   = date.today()
    cells   = []
    for i in range(days - 1, -1, -1):
        ds = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        a  = log_map.get(ds)
        cells.append("🟢" if a == "done" else "🔴" if a == "skip" else "⬜")
    rows = []
    for i in range(0, len(cells), 7):
        rows.append(" ".join(cells[i:i+7]))
    return "\n".join(rows)


# ── Calendar ─────────────────────────────────────────────────
def build_calendar_text(user_id: int) -> str:
    import calendar as cal_lib
    db    = get_db()
    today = date.today()
    y, m  = today.year, today.month
    _, dim = cal_lib.monthrange(y, m)
    MONTHS_AR = ["","يناير","فبراير","مارس","أبريل","مايو","يونيو",
                 "يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]

    text = f"📆 *{MONTHS_AR[m]} {y}*\n\n🟢 ممتاز  🟡 جيد  🔴 ضعيف  ⬜ بدون مهام\n\n"
    first_wd = date(y, m, 1).weekday()
    cells = ["  "] * first_wd
    for d in range(1, dim + 1):
        ds    = f"{y}-{m:02d}-{d:02d}"
        tasks = list(db.tasks.find({"user_id": user_id, "due_date": ds}))
        total = len(tasks); done = sum(1 for t in tasks if t["status"] == "done")
        rate  = round(done/total*100) if total else -1
        if   rate == -1: cells.append("⬜")
        elif rate >= 80: cells.append("🟢")
        elif rate >= 50: cells.append("🟡")
        else:            cells.append("🔴")
    while len(cells) % 7: cells.append("  ")
    header = "إث  ثل  أر  خم  جم  سب  أح"
    text  += header + "\n"
    for i in range(0, len(cells), 7):
        text += "  ".join(cells[i:i+7]) + "\n"
    rates = []
    for d in range(1, dim + 1):
        ds = f"{y}-{m:02d}-{d:02d}"
        ts = list(db.tasks.find({"user_id": user_id, "due_date": ds}))
        if ts: rates.append(sum(1 for t in ts if t["status"]=="done")/len(ts)*100)
    if rates:
        text += f"\n📊 متوسط الشهر: *{round(sum(rates)/len(rates))}%*"
    return text


# ── Weekly chart ─────────────────────────────────────────────
def build_weekly_chart(weekly: dict) -> str:
    text = "📊 *إنجاز الأسبوع*\n\n"
    for d in weekly["daily"]:
        r   = d["rate"]
        bar = "█" * int(r/10) + "░" * (10 - int(r/10))
        em  = "🟢" if r >= 80 else "🟡" if r >= 50 else "🔴" if r > 0 else "⬜"
        text += f"{em} {d['day_name'][:3]}: `{bar}` {r}%\n"
    text += f"\n✅ {weekly['total_done']}/{weekly['total_tasks']} | معدل: {weekly['weekly_rate']}%"
    return text
