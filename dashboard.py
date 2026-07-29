"""
LifeMaster AI - Web Dashboard
لوحة مراقبة الإحصائيات
"""

import os
import logging
from flask import Flask, render_template_string, jsonify
from datetime import datetime, date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "")

_db = None


def get_db():
    global _db
    if _db is None and MONGO_URI:
        try:
            from pymongo import MongoClient
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            _db = client["lifemaster"]
        except Exception as e:
            logger.error(f"DB connection failed: {e}")
            _db = None
    return _db


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LifeMaster AI - لوحة التحكم</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', Tahoma, sans-serif;
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    min-height: 100vh;
    color: #fff;
    padding: 20px;
  }
  .header {
    text-align: center;
    padding: 30px 0;
  }
  .header h1 {
    font-size: 2.5rem;
    background: linear-gradient(90deg, #f7971e, #ffd200);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
  }
  .header p { color: #aaa; font-size: 1rem; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 20px;
    max-width: 1100px;
    margin: 30px auto;
  }
  .card {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    backdrop-filter: blur(10px);
    transition: transform 0.2s;
  }
  .card:hover { transform: translateY(-4px); }
  .card .icon { font-size: 2.5rem; margin-bottom: 12px; }
  .card .value {
    font-size: 2.2rem;
    font-weight: bold;
    color: #ffd200;
    margin-bottom: 4px;
  }
  .card .label { color: #aaa; font-size: 0.9rem; }
  .section-title {
    text-align: center;
    font-size: 1.4rem;
    color: #ffd200;
    margin: 40px 0 20px;
  }
  .status {
    display: inline-block;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: bold;
    margin-top: 10px;
  }
  .status.online { background: rgba(0,200,100,0.2); color: #00c864; border: 1px solid #00c864; }
  .status.offline { background: rgba(255,50,50,0.2); color: #ff5050; border: 1px solid #ff5050; }
  .footer { text-align: center; color: #555; padding: 40px 0 20px; font-size: 0.85rem; }
  table {
    width: 100%;
    max-width: 900px;
    margin: 0 auto;
    border-collapse: collapse;
  }
  th, td {
    padding: 12px 16px;
    text-align: right;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  th { color: #ffd200; font-size: 0.9rem; }
  td { color: #ddd; font-size: 0.9rem; }
  tr:hover td { background: rgba(255,255,255,0.04); }
  .rank-badge {
    display: inline-block;
    background: rgba(255,210,0,0.15);
    border: 1px solid rgba(255,210,0,0.3);
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 0.8rem;
  }
</style>
</head>
<body>
<div class="header">
  <h1>⚡ LifeMaster AI</h1>
  <p>لوحة مراقبة النظام</p>
  <span class="status {{ 'online' if db_connected else 'offline' }}">
    {{ '🟢 متصل' if db_connected else '🔴 غير متصل' }}
  </span>
</div>

<div class="grid">
  <div class="card">
    <div class="icon">👥</div>
    <div class="value">{{ stats.total_users }}</div>
    <div class="label">إجمالي المستخدمين</div>
  </div>
  <div class="card">
    <div class="icon">📅</div>
    <div class="value">{{ stats.active_today }}</div>
    <div class="label">نشطون اليوم</div>
  </div>
  <div class="card">
    <div class="icon">✅</div>
    <div class="value">{{ stats.total_tasks_done }}</div>
    <div class="label">مهام مكتملة</div>
  </div>
  <div class="card">
    <div class="icon">🔥</div>
    <div class="value">{{ stats.total_habits }}</div>
    <div class="label">إجمالي العادات</div>
  </div>
  <div class="card">
    <div class="icon">⭐</div>
    <div class="value">{{ stats.total_xp }}</div>
    <div class="label">إجمالي XP</div>
  </div>
</div>

{% if users %}
<h2 class="section-title">🏆 أفضل المستخدمين</h2>
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>الاسم</th>
      <th>الرتبة</th>
      <th>XP</th>
      <th>🔥 السلسلة</th>
      <th>✅ المهام</th>
    </tr>
  </thead>
  <tbody>
    {% for u in users %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ u.name }}</td>
      <td><span class="rank-badge">{{ u.rank_emoji }} {{ u.rank }}</span></td>
      <td>{{ "{:,}".format(u.xp) }}</td>
      <td>{{ u.streak }}</td>
      <td>{{ u.tasks_completed }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

<div class="footer">LifeMaster AI © 2026 — نظام إنتاجية ذكي</div>
</body>
</html>"""


@app.route("/")
def dashboard():
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")
    db_connected = db is not None

    stats = {
        "total_users": 0,
        "active_today": 0,
        "total_tasks_done": 0,
        "total_habits": 0,
        "total_xp": 0
    }
    users = []

    if db_connected:
        try:
            all_users = list(db.users.find().sort("xp", -1))
            stats["total_users"] = len(all_users)
            stats["active_today"] = sum(1 for u in all_users if u.get("last_active_date") == today)
            stats["total_tasks_done"] = sum(u.get("tasks_completed", 0) for u in all_users)
            stats["total_habits"] = db.habits.count_documents({})
            stats["total_xp"] = sum(u.get("xp", 0) for u in all_users)

            users = [
                {
                    "name": u.get("name", "مجهول"),
                    "rank": u.get("rank", "مبتدئ"),
                    "rank_emoji": u.get("rank_emoji", "🌱"),
                    "xp": u.get("xp", 0),
                    "streak": u.get("streak", 0),
                    "tasks_completed": u.get("tasks_completed", 0)
                }
                for u in all_users[:20]
            ]
        except Exception as e:
            logger.error(f"DB error: {e}")

    return render_template_string(
        DASHBOARD_HTML,
        stats=stats,
        users=users,
        db_connected=db_connected
    )


@app.route("/api/stats")
def api_stats():
    db = get_db()
    if not db:
        return jsonify({"error": "DB not connected"}), 503
    today = date.today().strftime("%Y-%m-%d")
    all_users = list(db.users.find())
    return jsonify({
        "total_users": len(all_users),
        "active_today": sum(1 for u in all_users if u.get("last_active_date") == today),
        "total_tasks_done": sum(u.get("tasks_completed", 0) for u in all_users),
        "total_xp": sum(u.get("xp", 0) for u in all_users),
        "status": "running"
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "LifeMaster AI"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 لوحة LifeMaster AI تعمل على المنفذ {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
