# LifeMaster AI — Telegram Bot

بوت تيليجرام متكامل لإدارة المهام والعادات والأهداف مع نظام XP وذكاء اصطناعي.

## المتطلبات (Environment Variables)
| المتغير | الوصف |
|---|---|
| `BOT_TOKEN` | توكن البوت من BotFather |
| `MONGO_URI` | رابط قاعدة بيانات MongoDB Atlas |
| `GROQ_API_KEY` | مفتاح Groq AI للمدرب الذكي |

## التشغيل على Render
- النوع: **Web Service** (لا worker)
- Build Command: `pip install -r requirements.txt`
- Start Command: `python main.py`
- الملف `render.yaml` جاهز بالإعدادات الصحيحة

## ملاحظة مهمة
بعد رفع الكود، يلزم ضبط المتغيرات الثلاث في Render Dashboard تحت **Environment**.

## User preferences
- اللغة: العربية
