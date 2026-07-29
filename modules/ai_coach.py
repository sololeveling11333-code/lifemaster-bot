"""
LifeMaster AI - AI Coach Module (Groq)
"""

import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
_client = None


def get_groq_client():
    global _client
    if not GROQ_API_KEY:
        return None
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


SYSTEM_PROMPT = """أنت "المدرب الذكي" في تطبيق LifeMaster AI — مساعد شخصي ذكي للإنتاجية وتطوير الذات.

شخصيتك:
- محفّز وإيجابي لكن صريح ومباشر
- تتحدث بالعربية الفصيحة السهلة
- تعطي نصائح عملية وقابلة للتطبيق
- تعرف بيانات المستخدم وتحللها
- ردودك مختصرة (3-5 جمل عادةً) إلا إذا طُلب منك التفصيل
- تستخدم الإيموجي بشكل معتدل

قدراتك:
- تحليل عادات المستخدم ونقاط ضعفه
- اقتراح خطط يومية وأسبوعية
- إنشاء خطط دراسية ورياضية
- تحفيز المستخدم عند الإخفاق
- الإجابة على أسئلة الإنتاجية وتطوير الذات"""


def ask_coach(user_message: str, user_context: dict = None) -> str:
    client = get_groq_client()
    if not client:
        return "❌ مفتاح Groq غير محدد. أضف GROQ_API_KEY في متغيرات البيئة."

    context_text = ""
    if user_context:
        name = user_context.get("name", "المستخدم")
        rank = user_context.get("rank", "مبتدئ")
        xp = user_context.get("xp", 0)
        streak = user_context.get("streak", 0)
        tasks_done = user_context.get("tasks_completed", 0)
        context_text = f"\n\nبيانات المستخدم: الاسم: {name} | الرتبة: {rank} | XP: {xp} | السلسلة: {streak} يوم | المهام المنجزة: {tasks_done}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + context_text},
        {"role": "user", "content": user_message}
    ]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return "⚠️ حدث خطأ في التواصل مع المدرب الذكي. حاول مرة أخرى."


def generate_daily_plan(user_context: dict) -> str:
    prompt = "اصنع لي خطة يوم مثالية بناءً على بياناتي. اجعلها عملية ومحددة بالأوقات."
    return ask_coach(prompt, user_context)


def analyze_habits(user_context: dict, habits_data: list) -> str:
    habits_text = "\n".join([f"- {h['name']}: {h['streak']} يوم متتالي" for h in habits_data[:5]])
    prompt = f"حلّل عاداتي التالية وأعطني نصيحة:\n{habits_text}"
    return ask_coach(prompt, user_context)


def motivate(user_context: dict) -> str:
    streak = user_context.get("streak", 0)
    prompt = f"أنا على سلسلة {streak} يوم. حفّزني للاستمرار."
    return ask_coach(prompt, user_context)
