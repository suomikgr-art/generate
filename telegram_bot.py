#!/usr/bin/env python3
"""
telegram_bot.py — TSun FF Generator Bot
أوامر:
  /start      — القائمة الرئيسية
  /gen        — توليد حسابات
  /stop       — إيقاف التوليد
  /status     — عرض التقدم
  /proxy      — حالة البروكسيات
  /addproxy   — إضافة بروكسيات يدوياً
  /checkproxy — فحص البروكسيات وحذف الميتة
  /fetchproxy — جلب بروكسيات مجانية تلقائياً
  /clearproxy — حذف كل البروكسيات
"""

from __future__ import annotations

import os
import sys
import threading
import json

import telebot
from telebot import types

import config.settings as settings
from core.generator import worker
from core.proxy import (
    get_proxy_stats,
    refresh_proxy_pool,
    check_proxy_pool,
    PROXY_FILE,
)
from core.proxy_fetcher import (
    fetch_and_test_proxies,
    load_proxies_from_text,
    clear_proxies,
    count_proxies,
)

# ── رمز البوت ────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8866966452:AAEfEeJFRQPc4PpA8KVAy5W024TMKEvEDVc").strip()
if not BOT_TOKEN:
    print("❌ BOT_TOKEN غير مضبوط.")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ── الحالة المشتركة ───────────────────────────────────────────────────────────

_gen_threads: list[threading.Thread] = []
_gen_lock = threading.Lock()

REGIONS = sorted(r for r in settings.REGION_LANG if r != "BR")

_sessions: dict[int, dict] = {}

_proxy_op_running = False
_proxy_op_lock    = threading.Lock()


def _new_session() -> dict:
    return {
        "step":     "region",
        "region":   None,
        "is_ghost": False,
        "count":    0,
        "name":     "",
        "password": "",
        "threads":  1,
    }


def _cancel_session(chat_id: int):
    _sessions.pop(chat_id, None)


# ── مساعدات الحسابات ──────────────────────────────────────────────────────────

def _account_folders() -> list[tuple[str, str]]:
    return [
        ("عادي",   settings.ACCOUNTS_FOLDER),
        ("نادر",   settings.RARE_ACCOUNTS_FOLDER),
        ("كابلز",  settings.COUPLES_ACCOUNTS_FOLDER),
        ("غوست",   settings.GHOST_ACCOUNTS_FOLDER),
    ]


def _count_saved_accounts() -> dict[str, int]:
    result = {}
    for label, folder in _account_folders():
        count = 0
        if os.path.exists(folder):
            for f in os.listdir(folder):
                if f.endswith(".json"):
                    try:
                        with open(os.path.join(folder, f), "r", encoding="utf-8") as fh:
                            data = json.load(fh)
                            if isinstance(data, list):
                                count += len(data)
                    except Exception:
                        pass
        result[label] = count
    return result


def _send_account_files(chat_id: int):
    any_sent = False
    for label, folder in _account_folders():
        if not os.path.exists(folder):
            continue
        for fname in os.listdir(folder):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(folder, fname)
            try:
                if os.path.getsize(fpath) < 5:
                    continue
                with open(fpath, "rb") as f:
                    bot.send_document(
                        chat_id, f,
                        visible_file_name=fname,
                        caption=f"📁 {label}: {fname}",
                    )
                any_sent = True
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ تعذّر إرسال {fname}: {e}")

    if not any_sent:
        bot.send_message(chat_id, "📭 لا توجد ملفات حسابات محفوظة حالياً.")


# ── التحقق من التشغيل ─────────────────────────────────────────────────────────

def _is_running() -> bool:
    return any(t.is_alive() for t in _gen_threads)


def _reset_counters(count: int):
    settings.EXIT_FLAG        = False
    settings.SUCCESS_COUNTER  = 0
    settings.INFLIGHT_COUNTER = 0
    settings.TARGET_ACCOUNTS  = count
    settings.RARE_COUNTER     = 0
    settings.COUPLES_COUNTER  = 0


# ── /start ────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(msg: types.Message):
    counts  = _count_saved_accounts()
    total   = sum(counts.values())
    state   = "🟢 يعمل" if _is_running() else "⚫ متوقف"
    proxies = count_proxies()
    px_info = f"✅ {proxies} بروكسي محمّل" if proxies > 0 else "❌ لا يوجد — يستخدم IP مباشر (خطر حظر!)"

    lines = [
        "💀 TSun FF Generator",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📡 الحالة   : {state}",
        f"🌐 البروكسي : {px_info}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "📁 الحسابات المحفوظة:",
        f"  🎮 عادي   : {counts['عادي']}",
        f"  💎 نادر   : {counts['نادر']}",
        f"  💑 كابلز  : {counts['كابلز']}",
        f"  👻 غوست   : {counts['غوست']}",
        f"  📊 المجموع: {total}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "⚙️ الأوامر:",
        "  /gen        — 🎯 توليد حسابات",
        "  /stop       — 🛑 إيقاف التوليد",
        "  /status     — 📊 عرض التقدم",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "🌐 أوامر البروكسي:",
        "  /proxy      — 📋 حالة البروكسيات",
        "  /addproxy   — ➕ إضافة بروكسيات",
        "  /fetchproxy — 🔄 جلب بروكسيات مجانية",
        "  /checkproxy — 🔍 فحص وتنظيف الميت",
        "  /clearproxy — 🗑️ حذف كل البروكسيات",
    ]
    bot.send_message(msg.chat.id, "\n".join(lines))


# ── /gen ──────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["gen"])
def cmd_gen(msg: types.Message):
    chat_id = msg.chat.id
    if _is_running():
        bot.send_message(chat_id, "⚠️ التوليد يعمل حالياً!\nاستخدم /stop أولاً.")
        return

    proxies = count_proxies()
    if proxies == 0:
        bot.send_message(
            chat_id,
            "⚠️ تحذير: لا توجد بروكسيات!\n\n"
            "🚫 سيتم استخدام IP تبعك مباشرة\n"
            "⛔ Garena قد تحظره!\n\n"
            "💡 استخدم /fetchproxy لجلب بروكسيات مجانية\n"
            "أو /addproxy لإضافة بروكسياتك الخاصة.\n\n"
            "⏳ سيستمر التوليد بدون بروكسيات..."
        )

    _sessions[chat_id] = _new_session()
    _ask_region(chat_id)


def _ask_region(chat_id: int):
    lines = ["🌍 اختر المنطقة:\n"]
    for i, r in enumerate(REGIONS, 1):
        lines.append(f"  {i}) {r} ({settings.REGION_LANG[r]})")
    lines.append(f"  {len(REGIONS)+1}) 👻 وضع GHOST")
    lines.append("\n📩 أرسل الرقم:")
    bot.send_message(chat_id, "\n".join(lines))


def _ask_count(chat_id: int):
    bot.send_message(chat_id, "🎯 كم عدد الحسابات المطلوبة؟")


def _ask_name(chat_id: int):
    bot.send_message(chat_id, "👤 أدخل بادئة اسم الحساب:")


def _ask_password(chat_id: int):
    bot.send_message(chat_id, "🔑 أدخل بادئة كلمة المرور:")


def _ask_threads(chat_id: int):
    bot.send_message(chat_id, "🧵 كم عدد الـ Threads؟ (1-10، موصى: 3)")


# ── معالج النصوص ──────────────────────────────────────────────────────────────

@bot.message_handler(func=lambda m: (
    m.chat.id in _sessions
    and not m.text.startswith("/")
))
def handle_step(msg: types.Message):
    chat_id = msg.chat.id
    text    = msg.text.strip()
    s       = _sessions.get(chat_id)
    if not s:
        return
    step = s.get("step")

    # ── وضع إدخال البروكسيات
    if step == "awaiting_proxies":
        _sessions.pop(chat_id, None)
        added = load_proxies_from_text(text)
        refresh_proxy_pool()
        total = count_proxies()
        if added == 0:
            bot.send_message(
                chat_id,
                "❌ لم أجد بروكسيات صالحة!\n\n"
                "📋 الصيغة الصحيحة:\n"
                "  ip:port\n"
                "  (سطر واحد لكل بروكسي)"
            )
        else:
            bot.send_message(
                chat_id,
                f"✅ تمت إضافة {added} بروكسي بنجاح!\n"
                f"📦 المجموع في المجموعة: {total}\n\n"
                f"🔍 استخدم /checkproxy للتحقق من صلاحيتها مع Garena."
            )
        return

    # ── خطوات التوليد
    if step == "region":
        chosen, is_ghost = None, False
        if text.isdigit():
            n = int(text)
            if 1 <= n <= len(REGIONS):
                chosen, is_ghost = REGIONS[n - 1], False
            elif n == len(REGIONS) + 1:
                chosen, is_ghost = "BR", True
            else:
                bot.send_message(chat_id, "❌ رقم غير صحيح. حاول مرة أخرى:"); return
        elif text.upper() in REGIONS:
            chosen, is_ghost = text.upper(), False
        elif text.upper() == "GHOST":
            chosen, is_ghost = "BR", True
        else:
            bot.send_message(chat_id, "❌ منطقة غير معروفة. أرسل رقماً:"); return
        s["region"], s["is_ghost"], s["step"] = chosen, is_ghost, "count"
        _ask_count(chat_id)

    elif step == "count":
        if not text.isdigit() or int(text) < 1:
            bot.send_message(chat_id, "❌ أدخل عدداً صحيحاً (الحد الأدنى 1):"); return
        s["count"], s["step"] = int(text), "name"
        _ask_name(chat_id)

    elif step == "name":
        if not text:
            bot.send_message(chat_id, "❌ الاسم لا يمكن أن يكون فارغاً:"); return
        s["name"], s["step"] = text, "password"
        _ask_password(chat_id)

    elif step == "password":
        if not text:
            bot.send_message(chat_id, "❌ كلمة المرور لا يمكن أن تكون فارغة:"); return
        s["password"], s["step"] = text, "threads"
        _ask_threads(chat_id)

    elif step == "threads":
        if not text.isdigit() or not (1 <= int(text) <= 10):
            bot.send_message(chat_id, "❌ أدخل رقماً بين 1 و 10:"); return
        s["threads"] = int(text)
        _start_generation(chat_id, s)


# ── بدء التوليد ───────────────────────────────────────────────────────────────

def _start_generation(chat_id: int, s: dict):
    _cancel_session(chat_id)
    region, is_ghost  = s["region"], s["is_ghost"]
    count, name       = s["count"], s["name"]
    password, threads = s["password"], s["threads"]

    mode    = "👻 وضع GHOST" if is_ghost else f"🌍 {region} ({settings.REGION_LANG.get(region, '')})"
    proxies = count_proxies()
    use_px  = proxies > 0
    px_info = f"✅ {proxies} بروكسي (دوراني)" if use_px else "❌ مباشر (بدون بروكسيات)"

    bot.send_message(
        chat_id,
        f"🚀 بدء التوليد...\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌍 المنطقة   : {mode}\n"
        f"🎯 الهدف     : {count} حساب\n"
        f"👤 الاسم     : {name}\n"
        f"🔑 الباسورد  : {password}\n"
        f"🧵 Threads   : {threads}\n"
        f"🌐 البروكسي  : {px_info}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    with _gen_lock:
        _gen_threads.clear()
        _reset_counters(count)
        actual_region = "BR" if is_ghost else region
        for i in range(1, threads + 1):
            t = threading.Thread(
                target=worker,
                args=(actual_region, name, password, count, i, is_ghost, True),
                daemon=True,
            )
            t.start()
            _gen_threads.append(t)

    def _monitor():
        for t in _gen_threads:
            t.join()
        done    = settings.SUCCESS_COUNTER
        rare    = settings.RARE_COUNTER
        couples = settings.COUPLES_COUNTER
        counts  = _count_saved_accounts()
        total   = sum(counts.values())
        bot.send_message(
            chat_id,
            f"✅ انتهى التوليد!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 تم إنشاء  : {done}/{count} حساب\n"
            f"💎 نادر      : {rare}\n"
            f"💑 كابلز     : {couples}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 المجموع المحفوظ: {total}\n"
            f"  🎮 عادي   : {counts['عادي']}\n"
            f"  💎 نادر   : {counts['نادر']}\n"
            f"  💑 كابلز  : {counts['كابلز']}\n"
            f"  👻 غوست   : {counts['غوست']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📤 جارٍ إرسال الملفات..."
        )
        _send_account_files(chat_id)

    threading.Thread(target=_monitor, daemon=True).start()


# ── /stop ─────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["stop"])
def cmd_stop(msg: types.Message):
    _cancel_session(msg.chat.id)
    if not _is_running():
        bot.send_message(msg.chat.id, "ℹ️ لا يوجد توليد جارٍ حالياً.")
        return
    settings.EXIT_FLAG = True
    bot.send_message(msg.chat.id, "🛑 تم إرسال إشارة الإيقاف...\n⏳ سيتوقف التوليد قريباً.")


# ── /status ───────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["status"])
def cmd_status(msg: types.Message):
    counts  = _count_saved_accounts()
    saved   = sum(counts.values())
    state   = "🟢 يعمل" if _is_running() else "⚫ متوقف"
    proxies = count_proxies()
    bot.send_message(
        msg.chat.id,
        f"📊 حالة البوت\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 الحالة    : {state}\n"
        f"🎯 الجلسة   : {settings.SUCCESS_COUNTER}/{settings.TARGET_ACCOUNTS}\n"
        f"💎 النادر    : {settings.RARE_COUNTER}\n"
        f"💑 الكابلز   : {settings.COUPLES_COUNTER}\n"
        f"🌐 البروكسيات: {proxies} محمّل\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 المجموع المحفوظ: {saved}\n"
        f"  🎮 عادي   : {counts['عادي']}\n"
        f"  💎 نادر   : {counts['نادر']}\n"
        f"  💑 كابلز  : {counts['كابلز']}\n"
        f"  👻 غوست   : {counts['غوست']}"
    )


# ── /proxy ────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["proxy"])
def cmd_proxy(msg: types.Message):
    valid, invalid, path = get_proxy_stats()
    if valid == 0:
        bot.send_message(
            msg.chat.id,
            "🌐 مجموعة البروكسيات: فارغة ❌\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ سيستخدم المولّد IP تبعك مباشرة!\n\n"
            "💡 للإصلاح:\n"
            "  /fetchproxy — 🔄 جلب بروكسيات مجانية تلقائياً\n"
            "  /addproxy   — ➕ إضافة بروكسياتك الخاصة"
        )
    else:
        bot.send_message(
            msg.chat.id,
            f"🌐 حالة البروكسيات\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ صالح    : {valid}\n"
            f"❌ غير صالح: {invalid}\n"
            f"🔄 الدوران : تلقائي لكل طلب\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🔍 /checkproxy — فحص وحذف الميت\n"
            f"  🔄 /fetchproxy — إضافة المزيد\n"
            f"  🗑️ /clearproxy — حذف الكل"
        )


# ── /addproxy ─────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["addproxy"])
def cmd_addproxy(msg: types.Message):
    text   = msg.text.strip()
    inline = text.replace("/addproxy", "", 1).strip()
    if inline:
        added = load_proxies_from_text(inline)
        refresh_proxy_pool()
        bot.send_message(
            msg.chat.id,
            f"✅ تمت إضافة {added} بروكسي!\n"
            f"📦 المجموع الآن: {count_proxies()}\n\n"
            f"🔍 استخدم /checkproxy للتحقق منها."
        )
    else:
        _sessions[msg.chat.id] = {"step": "awaiting_proxies"}
        bot.send_message(
            msg.chat.id,
            "📋 أرسل قائمة البروكسيات الآن\n"
            "(سطر واحد لكل بروكسي)\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ الصيغ المدعومة:\n"
            "  ip:port\n"
            "  ip:port:user:pass\n"
            "  user:pass@ip:port\n"
            "  http://user:pass@ip:port\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📝 مثال:\n"
            "  1.2.3.4:8080\n"
            "  5.6.7.8:3128"
        )


# ── /checkproxy ───────────────────────────────────────────────────────────────

@bot.message_handler(commands=["checkproxy"])
def cmd_checkproxy(msg: types.Message):
    global _proxy_op_running
    chat_id = msg.chat.id
    with _proxy_op_lock:
        if _proxy_op_running:
            bot.send_message(chat_id, "⚠️ عملية بروكسي تعمل بالفعل!\nانتظر حتى تنتهي."); return
        _proxy_op_running = True

    total = count_proxies()
    if total == 0:
        with _proxy_op_lock:
            _proxy_op_running = False
        bot.send_message(chat_id, "❌ لا توجد بروكسيات للفحص!\nاستخدم /addproxy أو /fetchproxy أولاً.")
        return

    smsg = bot.send_message(
        chat_id,
        f"🔍 جارٍ فحص {total} بروكسي مع Garena...\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ قد يستغرق 1-2 دقيقة\n"
        f"🧵 فحص بـ 50 thread متوازي"
    )

    def _run():
        global _proxy_op_running
        try:
            summary = check_proxy_pool(timeout=8, max_workers=50)
            alive   = len(summary.alive)
            dead    = len(summary.dead)
            extra   = (
                "\n━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚠️ كل البروكسيات ميتة!\n"
                "🔄 استخدم /fetchproxy لجلب جديدة."
            ) if alive == 0 else ""
            bot.edit_message_text(
                f"✅ انتهى الفحص!\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ شغّال  : {alive}\n"
                f"❌ ميت    : {dead}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 البروكسيات الميتة → offline_proxies.txt\n"
                f"📦 المجموعة الآن: {alive} بروكسي جاهز." + extra,
                chat_id, smsg.message_id,
            )
        except Exception as e:
            bot.send_message(chat_id, f"❌ فشل الفحص: {e}")
        finally:
            with _proxy_op_lock:
                _proxy_op_running = False

    threading.Thread(target=_run, daemon=True).start()


# ── /fetchproxy ───────────────────────────────────────────────────────────────

@bot.message_handler(commands=["fetchproxy"])
def cmd_fetchproxy(msg: types.Message):
    global _proxy_op_running
    chat_id = msg.chat.id
    with _proxy_op_lock:
        if _proxy_op_running:
            bot.send_message(chat_id, "⚠️ عملية بروكسي تعمل بالفعل!\nانتظر حتى تنتهي."); return
        _proxy_op_running = True

    smsg = bot.send_message(
        chat_id,
        "🌐 جارٍ جلب بروكسيات مجانية...\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📡 جلب من 8 مصادر بالتوازي\n"
        "⏳ يستغرق 30-60 ثانية..."
    )

    def _run():
        global _proxy_op_running
        try:
            def on_progress(tested, total_test, alive):
                if tested % 40 == 0:
                    try:
                        bot.edit_message_text(
                            f"🔍 جارٍ فحص البروكسيات مع Garena...\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📊 مفحوص: {tested}/{total_test}\n"
                            f"✅ شغّال : {alive}",
                            chat_id, smsg.message_id,
                        )
                    except Exception:
                        pass

            alive_count, total_tested = fetch_and_test_proxies(
                max_test=300, max_alive=60, on_progress=on_progress,
            )
            refresh_proxy_pool()
            total_now = count_proxies()

            if alive_count > 0:
                bot.edit_message_text(
                    f"✅ انتهى جلب البروكسيات!\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔍 تم فحص    : {total_tested} بروكسي\n"
                    f"✅ شغّال     : {alive_count} مع Garena\n"
                    f"📦 في المجموعة: {total_now}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🚀 المولّد جاهز! استخدم /gen للبدء.",
                    chat_id, smsg.message_id,
                )
            else:
                bot.edit_message_text(
                    f"⚠️ لم ينجح أي بروكسي مع Garena!\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔍 تم فحص: {total_tested} بروكسي\n\n"
                    f"💡 جرّب مرة أخرى لاحقاً\n"
                    f"أو أضف بروكسيات مدفوعة عبر /addproxy",
                    chat_id, smsg.message_id,
                )
        except Exception as e:
            bot.send_message(chat_id, f"❌ فشل الجلب: {e}")
        finally:
            with _proxy_op_lock:
                _proxy_op_running = False

    threading.Thread(target=_run, daemon=True).start()


# ── /clearproxy ───────────────────────────────────────────────────────────────

@bot.message_handler(commands=["clearproxy"])
def cmd_clearproxy(msg: types.Message):
    removed = clear_proxies()
    refresh_proxy_pool()
    if removed == 0:
        bot.send_message(msg.chat.id, "ℹ️ مجموعة البروكسيات كانت فارغة أصلاً.")
    else:
        bot.send_message(
            msg.chat.id,
            f"🗑️ تم حذف {removed} بروكسي!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ سيستخدم المولّد اتصال مباشر الآن.\n\n"
            f"💡 استخدم /fetchproxy أو /addproxy\n"
            f"لإضافة بروكسيات جديدة."
        )


# ── التشغيل ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    px = count_proxies()
    if px > 0:
        print(f"✅ البوت شغّال | {px} بروكسي محمّل من proxies.txt")
    else:
        print("✅ البوت شغّال | ⚠️ لا توجد بروكسيات — استخدم /fetchproxy أو /addproxy")
    print("الأوامر: /start /gen /stop /status /proxy /addproxy /fetchproxy /checkproxy /clearproxy")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
