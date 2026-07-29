"""
LifeMaster AI - Challenges & Friends
تحديات بين المستخدمين وإضافة أصدقاء
"""
import logging
from datetime import datetime, date, timedelta
from bson import ObjectId
from modules.database import get_db, get_user

logger = logging.getLogger(__name__)


# ─── Friends ────────────────────────────────────────────────
def send_friend_request(from_id: int, to_id: int) -> str:
    """Returns: 'sent' | 'already_friends' | 'already_sent' | 'not_found'"""
    db    = get_db()
    to_u  = get_user(to_id)
    if not to_u:
        return "not_found"

    from_u = get_user(from_id)
    friends = from_u.get("friends", [])
    if to_id in friends:
        return "already_friends"

    existing = db.friend_requests.find_one({
        "from_id": from_id, "to_id": to_id, "status": "pending"
    })
    if existing:
        return "already_sent"

    db.friend_requests.insert_one({
        "from_id":    from_id,
        "to_id":      to_id,
        "status":     "pending",
        "created_at": datetime.utcnow()
    })
    return "sent"


def accept_friend(request_id: str):
    db  = get_db()
    req = db.friend_requests.find_one({"_id": ObjectId(request_id)})
    if not req:
        return
    db.friend_requests.update_one({"_id": ObjectId(request_id)}, {"$set": {"status": "accepted"}})
    db.users.update_one({"user_id": req["from_id"]}, {"$addToSet": {"friends": req["to_id"]}})
    db.users.update_one({"user_id": req["to_id"]},   {"$addToSet": {"friends": req["from_id"]}})


def get_pending_requests(user_id: int) -> list:
    db = get_db()
    return list(db.friend_requests.find({"to_id": user_id, "status": "pending"}))


def get_friends(user_id: int) -> list:
    user = get_user(user_id)
    if not user:
        return []
    friends_ids = user.get("friends", [])
    db = get_db()
    return list(db.users.find({"user_id": {"$in": friends_ids}}))


# ─── Challenges ─────────────────────────────────────────────
def create_challenge(creator_id: int, data: dict) -> str:
    db = get_db()
    end_date = (date.today() + timedelta(days=data.get("duration_days", 7))).strftime("%Y-%m-%d")
    ch = {
        "creator_id":   creator_id,
        "title":        data.get("title", "تحدٍّ"),
        "description":  data.get("description", ""),
        "type":         data.get("type", "tasks"),   # tasks | habits | xp
        "target":       data.get("target", 10),
        "participants": [{"user_id": creator_id, "progress": 0}],
        "status":       "active",
        "start_date":   date.today().strftime("%Y-%m-%d"),
        "end_date":     end_date,
        "created_at":   datetime.utcnow()
    }
    r = db.challenges.insert_one(ch)
    return str(r.inserted_id)


def join_challenge(challenge_id: str, user_id: int) -> bool:
    db = get_db()
    ch = db.challenges.find_one({"_id": ObjectId(challenge_id)})
    if not ch or ch["status"] != "active":
        return False
    # Check not already in
    for p in ch.get("participants", []):
        if p["user_id"] == user_id:
            return False
    db.challenges.update_one(
        {"_id": ObjectId(challenge_id)},
        {"$push": {"participants": {"user_id": user_id, "progress": 0}}}
    )
    return True


def update_challenge_progress(user_id: int, challenge_type: str, amount: int = 1):
    """Called after a task/habit completion to update relevant challenges."""
    db   = get_db()
    today = date.today().strftime("%Y-%m-%d")
    chs  = db.challenges.find({
        "status":      "active",
        "end_date":    {"$gte": today},
        "type":        challenge_type,
        "participants.user_id": user_id
    })
    for ch in chs:
        db.challenges.update_one(
            {"_id": ch["_id"], "participants.user_id": user_id},
            {"$inc": {"participants.$.progress": amount}}
        )


def get_active_challenges(user_id: int) -> list:
    db    = get_db()
    today = date.today().strftime("%Y-%m-%d")
    return list(db.challenges.find({
        "status":   "active",
        "end_date": {"$gte": today},
        "participants.user_id": user_id
    }))


def get_open_challenges(limit: int = 5) -> list:
    db    = get_db()
    today = date.today().strftime("%Y-%m-%d")
    return list(db.challenges.find({
        "status":   "active",
        "end_date": {"$gte": today}
    }).limit(limit))
