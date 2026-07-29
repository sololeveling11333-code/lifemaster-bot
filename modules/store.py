"""
LifeMaster AI - Store & Mystery Boxes
"""
import random
import logging
from modules.database import get_db, get_user, update_user

logger = logging.getLogger(__name__)

# ─── Store Items ─────────────────────────────────────────────
STORE_ITEMS = {
    # ── Titles ──
    "title_warrior":   {"id": "title_warrior",   "type": "title",  "name": "⚔️ المحارب الأسطوري",  "price": 200,  "desc": "لقب حصري للمحاربين"},
    "title_champion":  {"id": "title_champion",  "type": "title",  "name": "🏆 بطل الإنجاز",       "price": 350,  "desc": "لقب أبطال الإنجاز"},
    "title_iron":      {"id": "title_iron",       "type": "title",  "name": "🔩 الإرادة الفولاذية","price": 500,  "desc": "لقب أصحاب الالتزام"},
    "title_emperor":   {"id": "title_emperor",   "type": "title",  "name": "🔱 الإمبراطور",        "price": 1000, "desc": "اللقب الأعلى"},
    # ── Badges ──
    "badge_fire":      {"id": "badge_fire",      "type": "badge",  "name": "🔥 شارة النار",        "price": 150,  "desc": "للمتميزين في السلاسل"},
    "badge_diamond":   {"id": "badge_diamond",   "type": "badge",  "name": "💎 شارة الماس",        "price": 300,  "desc": "للمثابرين"},
    "badge_star":      {"id": "badge_star",      "type": "badge",  "name": "🌟 شارة النجم",        "price": 250,  "desc": "لأصحاب الإنجازات"},
    "badge_crown":     {"id": "badge_crown",     "type": "badge",  "name": "👑 شارة التاج",        "price": 600,  "desc": "للقادة فقط"},
    # ── Boxes ──
    "box_small":       {"id": "box_small",       "type": "box",    "name": "📦 صندوق صغير",        "price": 100,  "desc": "مفاجأة صغيرة"},
    "box_medium":      {"id": "box_medium",      "type": "box",    "name": "🎁 صندوق متوسط",       "price": 250,  "desc": "مفاجأة متوسطة"},
    "box_legendary":   {"id": "box_legendary",   "type": "box",    "name": "✨ صندوق أسطوري",      "price": 600,  "desc": "مفاجأة نادرة!"},
    # ── XP Boosts ──
    "xp_boost_small":  {"id": "xp_boost_small",  "type": "boost",  "name": "⭐ معزز XP صغير",     "price": 120,  "desc": "+50 XP فوري"},
    "xp_boost_large":  {"id": "xp_boost_large",  "type": "boost",  "name": "🌟 معزز XP كبير",     "price": 300,  "desc": "+150 XP فوري"},
}

# ─── Box Rewards ─────────────────────────────────────────────
BOX_REWARDS = {
    "box_small": [
        {"type": "xp",    "amount": 30,  "label": "⭐ +30 XP",       "weight": 40},
        {"type": "xp",    "amount": 60,  "label": "⭐ +60 XP",       "weight": 30},
        {"type": "coins", "amount": 50,  "label": "💰 +50 عملة",     "weight": 20},
        {"type": "coins", "amount": 100, "label": "💰 +100 عملة",    "weight": 10},
    ],
    "box_medium": [
        {"type": "xp",    "amount": 100, "label": "⭐ +100 XP",      "weight": 35},
        {"type": "xp",    "amount": 200, "label": "⭐ +200 XP",      "weight": 25},
        {"type": "coins", "amount": 200, "label": "💰 +200 عملة",    "weight": 25},
        {"type": "coins", "amount": 400, "label": "💰 +400 عملة",    "weight": 10},
        {"type": "badge", "id": "badge_fire", "label": "🔥 شارة النار", "weight": 5},
    ],
    "box_legendary": [
        {"type": "xp",    "amount": 500, "label": "⭐ +500 XP",      "weight": 25},
        {"type": "coins", "amount": 800, "label": "💰 +800 عملة",    "weight": 25},
        {"type": "title", "id": "title_warrior", "label": "⚔️ لقب المحارب",  "weight": 20},
        {"type": "badge", "id": "badge_diamond",  "label": "💎 شارة الماس",  "weight": 20},
        {"type": "xp",    "amount": 1000,"label": "🌟 +1000 XP JACKPOT!", "weight": 10},
    ],
}


def get_store_items_by_type(item_type: str = None) -> list:
    if item_type:
        return [i for i in STORE_ITEMS.values() if i["type"] == item_type]
    return list(STORE_ITEMS.values())


def buy_item(user_id: int, item_id: str) -> dict:
    """Returns {success, message, item, reward}"""
    db = get_db()
    user = get_user(user_id)
    item = STORE_ITEMS.get(item_id)

    if not item:
        return {"success": False, "message": "العنصر غير موجود!"}
    if not user:
        return {"success": False, "message": "المستخدم غير موجود!"}

    coins = user.get("coins", 0)
    if coins < item["price"]:
        return {"success": False, "message": f"رصيدك غير كافٍ! تحتاج {item['price']} عملة، لديك {coins}."}

    inventory = user.get("inventory", [])

    # Boxes can be bought multiple times; other items are one-time
    if item["type"] != "box" and item_id in inventory:
        return {"success": False, "message": "لديك هذا العنصر بالفعل!"}

    # Deduct coins
    new_coins = coins - item["price"]
    update_data = {"coins": new_coins}

    reward = None

    if item["type"] == "box":
        reward = _open_box(item_id, user_id)
        result_msg = f"✅ اشتريت وفتحت {item['name']}!\n\n🎁 حصلت على: *{reward['label']}*"
    else:
        inventory.append(item_id)
        update_data["inventory"] = inventory
        result_msg = f"✅ اشتريت *{item['name']}* بنجاح!"

        # Auto-equip title
        if item["type"] == "title":
            update_data["equipped_title"] = item["name"]

    db.users.update_one({"user_id": user_id}, {"$set": update_data})

    return {"success": True, "message": result_msg, "item": item, "reward": reward}


def _open_box(box_id: str, user_id: str) -> dict:
    """Pick a random reward from a box and apply it."""
    from modules.xp_system import add_xp
    rewards = BOX_REWARDS.get(box_id, [])
    if not rewards:
        return {"type": "xp", "amount": 50, "label": "⭐ +50 XP"}

    weights = [r["weight"] for r in rewards]
    chosen = random.choices(rewards, weights=weights, k=1)[0]

    if chosen["type"] == "xp":
        add_xp(user_id, chosen["amount"], 0)
    elif chosen["type"] == "coins":
        db = get_db()
        db.users.update_one({"user_id": user_id}, {"$inc": {"coins": chosen["amount"]}})
    elif chosen["type"] in ("badge", "title"):
        item_id = chosen.get("id")
        if item_id:
            user = get_user(user_id)
            inv = user.get("inventory", [])
            if item_id not in inv:
                inv.append(item_id)
                update_data = {"inventory": inv}
                if chosen["type"] == "title":
                    update_data["equipped_title"] = STORE_ITEMS[item_id]["name"]
                get_db().users.update_one({"user_id": user_id}, {"$set": update_data})

    return chosen


def get_inventory(user_id: int) -> list:
    user = get_user(user_id)
    if not user:
        return []
    inv_ids = user.get("inventory", [])
    return [STORE_ITEMS[i] for i in inv_ids if i in STORE_ITEMS]
